"""
GitHub App authentication and PR file retrieval.

Uses PyGithub's GithubIntegration to handle the JWT-signing and
installation-token-exchange dance, so we don't hand-roll JWT/crypto code.
"""

import logging
from dataclasses import dataclass

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

    return Github(auth=Auth.Token(installation_auth.token))


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
