"""ARQ background worker process."""

import logging

from arq.connections import RedisSettings

from backend.integrations.github_client import get_pr_files
from backend.settings import settings

logger = logging.getLogger(__name__)


async def process_pull_request(ctx: dict, payload: dict) -> None:
    """Background task: fetch PR diffs, compute embeddings, and post AI reviews."""
    pr_number = payload.get("number")
    repo_full_name = payload.get("repository", {}).get("full_name")
    action = payload.get("action")
    installation_id = payload.get("installation", {}).get("id")

    logger.info("Worker picked up job: PR #%s (%s) in %s", pr_number, action, repo_full_name)

    if not installation_id:
        logger.error(
            "No installation.id in webhook payload for PR #%s -- cannot authenticate to GitHub. "
            "Check that the GitHub App is actually installed on this repo.",
            pr_number,
        )
        return

    changed_files = get_pr_files(installation_id, repo_full_name, pr_number)

    for f in changed_files:
        logger.info(
            "  %s (%s) +%d/-%d",
            f.file_path, f.status, f.additions, f.deletions,
        )

    # Next step: feed `changed_files` into the adaptive chunking pipeline,
    # skip embedding for files whose file_sha already exists in code_chunks,
    # and embed only genuinely new/changed content.


class WorkerSettings:
    """ARQ Worker configuration settings."""
    functions = [process_pull_request]
    redis_settings = RedisSettings.from_dsn(settings.REDIS_URL)
