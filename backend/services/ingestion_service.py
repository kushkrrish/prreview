"""backend/services/ingestion_service.py"""

import logging

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import CodeChunk
from backend.services.chunking_strategies import AdaptiveChunkerFactory
from backend.services.embedding_strategies import embedding_service

logger = logging.getLogger(__name__)


async def _is_already_indexed(session: AsyncSession, repo_name: str, file_path: str, file_sha: str) -> bool:
    """
    Cache check: file_sha is Git's own content hash, so if a row already
    exists for this exact repo+path+sha, the file's content hasn't changed
    since it was last embedded -- no need to hash anything extra or
    recompute chunks/embeddings.
    """
    result = await session.execute(
        select(CodeChunk.id)
        .where(
            CodeChunk.repo_name == repo_name,
            CodeChunk.file_path == file_path,
            CodeChunk.file_sha == file_sha,
        )
        .limit(1)
    )
    return result.scalar_one_or_none() is not None


async def ingest_changed_files(
    session: AsyncSession,
    repo_name: str,
    pr_number: int,
    changed_files: list,  # list[ChangedFile] from github_client.py
) -> None:
    """
    For each changed file: skip entirely if already indexed (cache hit),
    otherwise chunk adaptively and embed each chunk (cache miss).
    """
    hits = 0
    misses = 0

    for f in changed_files:
        if not f.patch:
            logger.info("Skipping %s (no patch -- binary, removed, or too large)", f.file_path)
            continue

        if await _is_already_indexed(session, repo_name, f.file_path, f.file_sha):
            hits += 1
            logger.info("Cache HIT: %s (sha=%s) already indexed, skipping", f.file_path, f.file_sha[:8])
            continue

        misses += 1
        strategy = AdaptiveChunkerFactory.get_strategy(f.patch)
        chunks = strategy.chunk(f.file_path, pr_number, f.patch)
        logger.info(
            "Cache MISS: %s (sha=%s) -> %d chunk(s) via %s",
            f.file_path, f.file_sha[:8], len(chunks), type(strategy).__name__,
        )

        for idx, chunk_text in enumerate(chunks):
            vector = await embedding_service.get_embedding(chunk_text)

            stmt = pg_insert(CodeChunk).values(
                repo_name=repo_name,
                file_path=f.file_path,
                chunk_index=idx,
                file_sha=f.file_sha,
                chunk_text=chunk_text,
                embedding=vector,
            ).on_conflict_do_nothing(
                constraint="uq_repo_file_chunk_sha",
            )
            await session.execute(stmt)

        await session.commit()
        logger.info("Indexed %d chunk(s) for %s", len(chunks), f.file_path)

    logger.info(
        "Ingestion summary for PR #%d: %d file(s) cached (skipped), %d file(s) newly indexed",
        pr_number, hits, misses,
    )
