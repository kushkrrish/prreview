"""backend/services/full_repo_ingestion.py"""

import logging

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from backend.integrations.github_client import get_all_repo_files
from backend.models import CodeChunk
from backend.services.chunking_strategies import AdaptiveChunkerFactory
from backend.services.embedding_strategies import embedding_service

logger = logging.getLogger(__name__)


async def _is_already_indexed_full_file(session: AsyncSession, repo_name: str, file_path: str, file_sha: str) -> bool:
    """Same cache-check idea as the PR-diff path, but scoped to source='full_file'."""
    result = await session.execute(
        select(CodeChunk.id)
        .where(
            CodeChunk.repo_name == repo_name,
            CodeChunk.file_path == file_path,
            CodeChunk.file_sha == file_sha,
            CodeChunk.source == "full_file",
        )
        .limit(1)
    )
    return result.scalar_one_or_none() is not None


async def ingest_full_repo(session: AsyncSession, installation_id: int, repo_full_name: str) -> None:
    """
    One-time (or periodic) baseline scan: embeds the FULL content of every
    file in the repo's default branch, tagged source="full_file". This is
    what lets vector search find related files that a PR diff never
    touches directly.

    Reuses the same AdaptiveChunkerFactory as PR diffs -- it works fine on
    plain source text since only HunkBoundaryStrategy assumes "@@" diff
    markers, and it falls back gracefully to whole-block handling when
    none are found.
    """
    files = get_all_repo_files(installation_id, repo_full_name)
    hits = 0
    misses = 0

    for f in files:
        if await _is_already_indexed_full_file(session, repo_full_name, f.file_path, f.file_sha):
            hits += 1
            continue

        misses += 1
        strategy = AdaptiveChunkerFactory.get_strategy(f.content)
        # pr_number=0 is a placeholder here -- full-repo scans aren't tied
        # to any specific PR, so the chunk header will just say "PR #0".
        chunks = strategy.chunk(f.file_path, 0, f.content)

        for idx, chunk_text in enumerate(chunks):
            vector = await embedding_service.get_embedding(chunk_text)

            stmt = pg_insert(CodeChunk).values(
                repo_name=repo_full_name,
                file_path=f.file_path,
                source="full_file",
                chunk_index=idx,
                file_sha=f.file_sha,
                chunk_text=chunk_text,
                embedding=vector,
            ).on_conflict_do_nothing(
                constraint="uq_repo_file_source_chunk_sha",
            )
            await session.execute(stmt)

        await session.commit()
        logger.info("Full-repo scan: indexed %d chunk(s) for %s", len(chunks), f.file_path)

    logger.info(
        "Full-repo scan summary for %s: %d file(s) cached, %d file(s) newly indexed",
        repo_full_name, hits, misses,
    )
