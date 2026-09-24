"""ARQ background worker process."""

import asyncio
import logging

from arq.connections import RedisSettings

from backend.database.session import AsyncSessionLocal
from backend.integrations.github_client import get_pr_files, publish_pr_review_comments
from backend.services.ingestion_service import ingest_changed_files
from backend.services.review_service import run_security_review
from backend.settings import settings

logging.basicConfig(level=settings.LOG_LEVEL)
logger = logging.getLogger(__name__)


async def process_pull_request(ctx: dict, payload: dict) -> None:
    """Background task: fetch PR diffs, chunk, embed, and store in code_chunks."""
    pr_number = payload.get("number")
    repo_full_name = payload.get("repository", {}).get("full_name")
    action = payload.get("action")
    installation_id = payload.get("installation", {}).get("id")

    logger.info("Worker picked up job: PR #%s (%s) in %s", pr_number, action, repo_full_name)

    if not repo_full_name or not installation_id or not pr_number:
        logger.error(
            "Incomplete pull request payload: number=%s repository=%s installation.id=%s",
            pr_number,
            repo_full_name,
            installation_id,
        )
        return

    changed_files = get_pr_files(installation_id, repo_full_name, pr_number)

    for f in changed_files:
        logger.info(
            "  %s (%s) +%d/-%d",
            f.file_path, f.status, f.additions, f.deletions,
        )

    async with AsyncSessionLocal() as session:
        try:
            await ingest_changed_files(session, repo_full_name, pr_number, changed_files)
        except Exception:  # noqa: BLE001 - review can proceed without retrieval context
            logger.exception(
                "Embedding/indexing failed for %s PR #%s; continuing with diff-only security review",
                repo_full_name,
                pr_number,
            )
            await session.rollback()
        pull_request = payload.get("pull_request", {})
        findings = await run_security_review(
            session,
            repo_name=repo_full_name,
            pr_number=pr_number,
            title=pull_request.get("title", "Untitled pull request"),
            description=pull_request.get("body"),
            head_sha=pull_request.get("head", {}).get("sha", "unknown"),
            author=pull_request.get("user", {}).get("login", "unknown"),
            changed_files=changed_files,
        )
    published_count = await asyncio.to_thread(
        publish_pr_review_comments,
        installation_id,
        repo_full_name,
        pr_number,
        pull_request.get("head", {}).get("sha", "unknown"),
        findings,
    )
    logger.info(
        "Security review completed for %s PR #%s: %d finding(s), %d published",
        repo_full_name,
        pr_number,
        len(findings),
        published_count,
    )


class WorkerSettings:
    """ARQ Worker configuration settings."""
    functions = [process_pull_request]
    redis_settings = RedisSettings.from_dsn(settings.REDIS_URL)
    job_timeout = 900
