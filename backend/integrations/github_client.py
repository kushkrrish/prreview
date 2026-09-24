"""
GitHub App authentication and PR file retrieval.

Uses PyGithub's GithubIntegration to handle the JWT-signing and
installation-token-exchange dance, so we don't hand-roll JWT/crypto code.
"""
from urllib3.util import Retry
import base64
import logging
from dataclasses import dataclass
from typing import Iterable

from github import Auth, Github, GithubIntegration

from backend.settings import settings

logger = logging.getLogger(__name__)


@dataclass
class ChangedFile:
    """One file changed in a PR, ready to hand off to the chunking pipeline."""

    file_path: str
    status: str          # "added", "modified", "removed", "renamed"
    file_sha: str         # git blob SHA of the file's current content
    patch: str | None     # unified diff text (None for binary files)
    additions: int
    deletions: int


def _get_installation_client(installation_id: int) -> Github:
    """
    Authenticate as the GitHub App, then exchange for a short-lived
    installation access token scoped to this specific repo installation.
    """
    with open(settings.GITHUB_PRIVATE_KEY_PATH, "r") as key_file:
        private_key = key_file.read()

    auth = Auth.AppAuth(settings.GITHUB_APP_ID, private_key)
    integration = GithubIntegration(auth=auth)
    installation_auth = integration.get_access_token(installation_id)

    # Define a retry strategy for temporary network blips / WSL latency drops
    retry_strategy = Retry(
        total=3,
        backoff_factor=1,  # Waits 1s, 2s, 4s between retries
        status_forcelist=[500, 502, 503, 504],
        raise_on_status=False
    )

    # Pass the timeout and retry strategy into the Github client
    return Github(
        auth=Auth.Token(installation_auth.token),
        timeout=30,            # Increased from the 15s default
        retry=retry_strategy   # Automatically handle transient connection hiccups
    )


def get_pr_files(installation_id: int, repo_full_name: str, pr_number: int) -> list[ChangedFile]:
    """
    Fetch the list of changed files for a PR, authenticated as the
    GitHub App installation that received the webhook.

    repo_full_name is GitHub's "owner/repo" format, taken directly from
    the webhook payload's repository.full_name field.
    """
    client = _get_installation_client(installation_id)
    repo = client.get_repo(repo_full_name)
    pr = repo.get_pull(pr_number)

    changed_files = [
        ChangedFile(
            file_path=f.filename,
            status=f.status,
            file_sha=f.sha,
            patch=f.patch,  # None for files GitHub considers "too large" or binary
            additions=f.additions,
            deletions=f.deletions,
        )
        for f in pr.get_files()
    ]

    logger.info(
        "Fetched %d changed file(s) for %s PR #%d",
        len(changed_files), repo_full_name, pr_number,
    )
    return changed_files


def _compact_text(text: str, limit: int) -> str:
    """Keep model prose readable and bounded in a GitHub review comment."""
    normalized = " ".join(text.strip().split())
    return normalized if len(normalized) <= limit else f"{normalized[:limit - 1].rstrip()}…"


def format_security_comment(finding) -> str:
    """Render one concise, developer-oriented inline PR comment."""
    severity = getattr(finding.severity, "value", finding.severity)
    category = _compact_text(finding.category.replace("_", " "), 40)
    summary = _compact_text(finding.summary, 120)
    rationale = _compact_text(finding.rationale, 320)
    suggestion = _compact_text(finding.suggestion, 400)
    return (
        f"**{str(severity).upper()} | {category}** - {summary}\n\n"
        f"{rationale}\n\n"
        f"**Suggested fix:** {suggestion}"
    )


def publish_pr_review_comments(
    installation_id: int,
    repo_full_name: str,
    pr_number: int,
    head_sha: str,
    findings: Iterable,
) -> int:
    """Publish validated findings as inline comments on the PR's reviewed commit.

    A failed individual comment is logged and does not prevent other useful
    findings from reaching the developer. Findings are already restricted to
    lines visible in the diff by the security agent.
    """
    client = _get_installation_client(installation_id)
    pull_request = client.get_repo(repo_full_name).get_pull(pr_number)
    existing = {
        (comment.commit_id, comment.path, comment.line, comment.body)
        for comment in pull_request.get_review_comments()
    }
    published = 0
    for finding in findings:
        body = format_security_comment(finding)
        key = (head_sha, finding.file_path, finding.line_end, body)
        if key in existing:
            logger.info(
                "Skipping already-published security finding for %s PR #%d at %s:%d",
                repo_full_name,
                pr_number,
                finding.file_path,
                finding.line_end,
            )
            continue
        try:
            pull_request.create_review_comment(
                body=body,
                commit=head_sha,
                path=finding.file_path,
                line=finding.line_end,
                side="RIGHT",
            )
            published += 1
            existing.add(key)
        except Exception:  # noqa: BLE001 - one rejected line must not hide others
            logger.exception(
                "Could not publish security finding for %s PR #%d at %s:%d",
                repo_full_name,
                pr_number,
                finding.file_path,
                finding.line_end,
            )
    logger.info("Published %d/%d inline security comment(s) for %s PR #%d", published, len(findings), repo_full_name, pr_number)
    return published



@dataclass
class RepoFile:
    """One file from a full-repo scan, with its full content (not a diff)."""
    file_path: str
    content: str
    file_sha: str


def get_all_repo_files(installation_id: int, repo_full_name: str, max_file_size_kb: int = 300) -> list[RepoFile]:
    """
    Walk the ENTIRE default branch tree and return every text file's full
    content + git blob sha. This is the "baseline scan" -- run once per
    repo (or periodically), NOT per PR.

    Skips binary files (can't decode as UTF-8) and anything over
    max_file_size_kb, since huge files (lockfiles, generated code, assets)
    add embedding cost without much review value.
    """
    client = _get_installation_client(installation_id)
    repo = client.get_repo(repo_full_name)
    default_branch = repo.default_branch

    tree = repo.get_git_tree(default_branch, recursive=True)

    files: list[RepoFile] = []
    for entry in tree.tree:
        if entry.type != "blob":
            continue
        if entry.size > max_file_size_kb * 1024:
            logger.info("Skipping %s (%.1f KB, over size limit)", entry.path, entry.size / 1024)
            continue

        blob = repo.get_git_blob(entry.sha)
        try:
            content = base64.b64decode(blob.content).decode("utf-8")
        except UnicodeDecodeError:
            logger.info("Skipping %s (binary file, can't decode as text)", entry.path)
            continue

        files.append(RepoFile(file_path=entry.path, content=content, file_sha=entry.sha))

    logger.info("Full repo scan: found %d text file(s) in %s", len(files), repo_full_name)
    return files

