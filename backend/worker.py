"""ARQ background worker process."""

import logging

from arq.connections import RedisSettings

from backend.database.session import AsyncSessionLocal
from backend.integrations.github_client import get_pr_files
from backend.services.ingestion_service import ingest_changed_files
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
        await ingest_changed_files(session, repo_full_name, pr_number, changed_files)

    # Next step: feed the now-indexed code_chunks into the LLM review step,
    # and post results back to the PR as a GitHub comment/review.


class WorkerSettings:
    """ARQ Worker configuration settings."""
    functions = [process_pull_request]
    redis_settings = RedisSettings.from_dsn(settings.REDIS_URL)
