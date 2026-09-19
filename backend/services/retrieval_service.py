"""backend/services/retrieval_service.py

Per-hunk semantic retrieval: for every embedded diff chunk of this PR, find the
nearest *baseline* code (source="full_file") in the SAME repo, then merge.

Design notes (the reasoning is in the chat reply; short version here):
* Query vectors are the pr_diff embeddings ALREADY in code_chunks -> zero new
  embedding API calls.
* Only full_file rows are returned as context. Other PRs' diff chunks are
  history, not the codebase.
* repo_name is ALWAYS in the WHERE clause. It is a tenant boundary: without it,
  another repo's code could be sent to the LLM and quoted in a public comment.
* Similarity thresholds and token budgets are applied later by
  context_builder.select_references, so there is one place to tune them.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from itertools import zip_longest
from typing import Iterable, Protocol, Sequence

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.agents.context_builder import RetrievedChunk
from backend.models import CodeChunk

logger = logging.getLogger(__name__)


class ChangedFileLike(Protocol):
    """Matches the ChangedFile objects github_client.py already returns."""
    file_path: str
    file_sha: str


@dataclass(frozen=True)
class RetrievalConfig:
    neighbors_per_query: int = 5  # candidates per diff chunk
    max_queries: int = 20  # cap on diff chunks used as queries (cost/latency)
    max_results: int = 20  # candidates handed to the context builder
    ef_search: int = 100  # HNSW candidate list size; see _nearest()
    query_source: str = "pr_diff"
    baseline_source: str = "full_file"


# --- pure helpers (unit-tested without a database) ---------------------------
def interleave_round_robin(groups: Sequence[Sequence], limit: int) -> list:
    """Take one item from each group in turn, so one huge file cannot use up
    the whole query budget and starve the other files in the PR."""
    merged = [item for row in zip_longest(*groups) for item in row if item is not None]
    return merged[:limit]


def merge_hits(hits: Iterable[RetrievedChunk], max_results: int) -> list[RetrievedChunk]:
    """Same chunk found by several queries -> keep its best similarity."""
    best: dict[tuple[str, int], RetrievedChunk] = {}
    for h in hits:
        key = (h.file_path, h.chunk_index)
        if key not in best or h.similarity > best[key].similarity:
            best[key] = h
    return sorted(best.values(), key=lambda h: h.similarity, reverse=True)[:max_results]


# --- database access ---------------------------------------------------------
async def _load_query_vectors(
    session: AsyncSession, repo_name: str, changed_files: Sequence[ChangedFileLike], cfg: RetrievalConfig
) -> list:
    per_file = []
    for f in changed_files:
        rows = await session.execute(
            select(CodeChunk.embedding)
            .where(
                CodeChunk.repo_name == repo_name,
                CodeChunk.file_path == f.file_path,
                CodeChunk.file_sha == f.file_sha,  # this exact version of the file
                CodeChunk.source == cfg.query_source,
                CodeChunk.embedding.is_not(None),
            )
            .order_by(CodeChunk.chunk_index)
        )
        per_file.append(list(rows.scalars().all()))
    return interleave_round_robin(per_file, cfg.max_queries)


async def _nearest(session: AsyncSession, repo_name: str, vector, cfg: RetrievalConfig) -> list[RetrievedChunk]:
    distance = CodeChunk.embedding.cosine_distance(vector).label("distance")
    stmt = (
        select(CodeChunk.file_path, CodeChunk.chunk_index, CodeChunk.chunk_text, distance)
        .where(
            CodeChunk.repo_name == repo_name,  # tenant boundary: never remove
            CodeChunk.source == cfg.baseline_source,
            CodeChunk.embedding.is_not(None),
        )
        .order_by(distance)
        .limit(cfg.neighbors_per_query)
    )
    rows = (await session.execute(stmt)).all()
    return [
        RetrievedChunk(
            file_path=r.file_path,
            content=r.chunk_text,
            source=cfg.baseline_source,  # type: ignore[arg-type]
            similarity=1.0 - float(r.distance),
            chunk_index=r.chunk_index,
        )
        for r in rows
    ]


async def retrieve_context(
    session: AsyncSession,
    *,
    repo_name: str,
    changed_files: Sequence[ChangedFileLike],
    config: RetrievalConfig | None = None,
) -> list[RetrievedChunk]:
    """Never raises: on any failure the review proceeds with no reference
    context (a weaker review beats no review)."""
    cfg = config or RetrievalConfig()
    try:
        # SAVEPOINT: if a query fails, only this block rolls back, not the
        # caller's transaction (Postgres aborts the whole txn on any error).
        async with session.begin_nested():
            vectors = await _load_query_vectors(session, repo_name, changed_files, cfg)
            if not vectors:
                logger.info("No stored diff embeddings for %s; skipping retrieval", repo_name)
                return []

            # HNSW returns its ef_search nearest rows of the WHOLE table, and only
            # then applies WHERE. Filtering by repo/source can therefore leave fewer
            # than `neighbors_per_query` rows. A larger candidate list compensates.
            # (int() because SET cannot take bind parameters.)
            await session.execute(text(f"SET LOCAL hnsw.ef_search = {int(cfg.ef_search)}"))

            hits: list[RetrievedChunk] = []
            for vec in vectors:  # sequential: one AsyncSession cannot run queries concurrently
                hits.extend(await _nearest(session, repo_name, vec, cfg))
            merged = merge_hits(hits, cfg.max_results)
            logger.info("Retrieval: %d quer(ies) -> %d candidate chunk(s)", len(vectors), len(merged))
            return merged
    except Exception:  # noqa: BLE001
        logger.exception("Retrieval failed for %s; continuing without reference context", repo_name)
        return []