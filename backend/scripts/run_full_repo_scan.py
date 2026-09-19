"""
Manual trigger for a full-repo baseline scan. Run this once per repo, e.g.
right now for your test repo, instead of waiting for a real GitHub App
"installation" webhook event.

Usage:
    python -m backend.scripts.run_full_repo_scan <installation_id> <owner/repo>

Find your installation_id from a previous worker log line, e.g. the
installation.id value logged when a PR event was processed, or from
your GitHub App's Advanced -> Recent Deliveries -> any payload's
installation.id field.
"""

import asyncio
import logging
import sys

from backend.database.session import AsyncSessionLocal
from backend.services.full_repo_ingestion import ingest_full_repo
from backend.settings import settings

logging.basicConfig(level=settings.LOG_LEVEL)


async def main(installation_id: int, repo_full_name: str) -> None:
    async with AsyncSessionLocal() as session:
        await ingest_full_repo(session, installation_id, repo_full_name)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python -m backend.scripts.run_full_repo_scan <installation_id> <owner/repo>")
        sys.exit(1)

    asyncio.run(main(int(sys.argv[1]), sys.argv[2]))
