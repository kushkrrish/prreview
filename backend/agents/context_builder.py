"""Build the agent-agnostic part of the prompt ONCE per review run.

Output is a single string (``ReviewContext.shared_prompt``) made of three
delimited blocks: PR METADATA, PR DIFF, REFERENCE CONTEXT. Every agent reuses
it, so the same prefix can later be prompt-cached.

Retrieval itself (the pgvector query) lives elsewhere; this module only
*selects, trims and labels* whatever chunks it is handed.
"""
from __future__ import annotations

import secrets
from dataclasses import dataclass, field
from typing import Literal, Sequence

from backend.agents.diff_utils import FileDiff, parse_patch, render_file_diff

REFERENCE_LABEL = "Reference only - do NOT review this code."

# --- skip list: burns tokens, produces junk findings -------------------------
_SKIP_NAMES = {"package-lock.json", "pnpm-lock.yaml", "go.sum"}
_SKIP_SUFFIXES = (
    ".lock", ".min.js", ".min.css", ".map", ".snap", ".pb.go", "_pb2.py",
    ".svg", ".png", ".jpg", ".jpeg", ".gif", ".ico", ".pdf",
    ".woff", ".woff2", ".ttf", ".zip", ".gz",
)
_SKIP_DIRS = ("node_modules/", "vendor/", "dist/", "build/", ".git/", "__pycache__/")


@dataclass
class PatchFile:
    """One changed file as returned by GitHub (PyGithub ``File``)."""
    path: str
    patch: str | None  # GitHub omits this for binary or very large diffs
    status: str = "modified"  # added | modified | removed | renamed


@dataclass
class RetrievedChunk:
    file_path: str
    content: str
    source: Literal["pr_diff", "full_file"]
    similarity: float  # cosine similarity in 0..1  (= 1 - pgvector `<=>` distance)
    chunk_index: int = 0


@dataclass
class SkippedFile:
    path: str
    reason: str


@dataclass
class ContextLimits:
    # Starting values. Tune from agent_events data, don't treat as truth.
    max_diff_chars: int = 60_000
    max_reference_chars: int = 24_000
    max_chars_per_reference: int = 6_000
    max_references: int = 6
    min_similarity: float = 0.5
    max_description_chars: int = 2_000
    reference_sources: tuple[str, ...] = ("full_file",)


@dataclass
class ReviewContext:
    repo: str
    pr_number: int
    head_sha: str
    files: list[FileDiff]  # files actually sent to the model
    skipped: list[SkippedFile]  # feeds the "what was skipped" line in the summary
    reference_paths: list[str]
    shared_prompt: str
    nonce: str = field(repr=False, default="")


# --------------------------------------------------------------------------- #
def _skip_reason(pf: PatchFile) -> str | None:
    name = pf.path.rsplit("/", 1)[-1]
    if pf.status == "removed":
        return "deleted file"
    if name in _SKIP_NAMES or pf.path.endswith(_SKIP_SUFFIXES):
        return "lockfile / minified / generated / binary type"
    if any(pf.path.startswith(d) or f"/{d}" in pf.path for d in _SKIP_DIRS):
        return "vendored or build output directory"
    if not pf.patch:
        return "no patch available (binary or too large for GitHub to return)"
    return None


def _clip(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[:limit] + "\n... [truncated]"


def _block(name: str, body: str, nonce: str) -> str:
    return f"=====BEGIN {name} [{nonce}]=====\n{body}\n=====END {name} [{nonce}]====="


def select_references(
    chunks: Sequence[RetrievedChunk], limits: ContextLimits
) -> list[RetrievedChunk]:
    """Keep the best-matching, relevant, de-duplicated chunks inside the budget."""
    picked: list[RetrievedChunk] = []
    seen: set[tuple[str, int]] = set()
    used = 0
    for c in sorted(chunks, key=lambda c: c.similarity, reverse=True):
        if len(picked) >= limits.max_references:
            break
        if c.source not in limits.reference_sources:
            continue  # e.g. other PRs' diffs are history, not the codebase
        if c.similarity < limits.min_similarity:
            continue  # top-N always returns N; a threshold returns "relevant"
        key = (c.file_path, c.chunk_index)
        if key in seen:
            continue
        content = _clip(c.content, limits.max_chars_per_reference)
        if used + len(content) > limits.max_reference_chars:
            continue
        seen.add(key)
        used += len(content)
        picked.append(RetrievedChunk(c.file_path, content, c.source, c.similarity, c.chunk_index))
    return picked


def _render_references(refs: list[RetrievedChunk], changed_paths: set[str], nonce: str) -> str:
    header = (
        f"{REFERENCE_LABEL} It is a snapshot of the repository's default branch, "
        "so it shows the code as it was BEFORE this PR (and may be slightly "
        "outdated). Use it ONLY to check how the changed code is called or used. "
        "Never report findings on it."
    )
    if not refs:
        return _block("REFERENCE CONTEXT", header + "\n\n(no relevant reference code found)", nonce)

    parts = [header]
    for i, r in enumerate(refs, 1):
        note = (
            "a file this PR modifies - this is the version BEFORE the PR"
            if r.file_path in changed_paths
            else "not modified by this PR"
        )
        parts.append(f"--- REFERENCE {i}: {r.file_path} ({note}) ---\n{r.content}\n--- END REFERENCE {i} ---")
    return _block("REFERENCE CONTEXT", "\n\n".join(parts), nonce)


def build_review_context(
    *,
    repo: str,
    pr_number: int,
    head_sha: str,
    title: str,
    description: str | None,
    files: Sequence[PatchFile],
    retrieved: Sequence[RetrievedChunk] = (),
    limits: ContextLimits | None = None,
    nonce: str | None = None,
) -> ReviewContext:
    limits = limits or ContextLimits()
    # Unpredictable per request: PR content cannot forge a closing delimiter
    # because the attacker does not know the token when they write the PR.
    nonce = nonce or secrets.token_hex(4)

    reviewable: list[FileDiff] = []
    skipped: list[SkippedFile] = []
    rendered: list[str] = []
    used = 0

    for pf in files:
        reason = _skip_reason(pf)
        if reason:
            skipped.append(SkippedFile(pf.path, reason))
            continue
        fd = parse_patch(pf.path, pf.patch or "", pf.status)
        if not fd.hunks:
            skipped.append(SkippedFile(pf.path, "empty diff"))
            continue
        text = render_file_diff(fd)
        if used + len(text) > limits.max_diff_chars:
            skipped.append(SkippedFile(pf.path, "diff size budget exceeded"))
            continue
        used += len(text)
        reviewable.append(fd)
        rendered.append(text)

    changed_paths = {f.path for f in reviewable}
    refs = select_references(retrieved, limits)

    metadata = (
        f"Repository: {repo}\nPR #{pr_number}\nHead commit: {head_sha}\n"
        f"Title: {title}\n"
        f"Description:\n{_clip(description or '(none)', limits.max_description_chars)}"
    )
    diff_body = "\n\n".join(rendered) if rendered else "(no reviewable files)"

    shared_prompt = "\n\n".join(
        [
            _block("PR METADATA", metadata, nonce),
            _block("PR DIFF", diff_body, nonce),
            _render_references(refs, changed_paths, nonce),
        ]
    )
    return ReviewContext(
        repo=repo,
        pr_number=pr_number,
        head_sha=head_sha,
        files=reviewable,
        skipped=skipped,
        reference_paths=[r.file_path for r in refs],
        shared_prompt=shared_prompt,
        nonce=nonce,
    )