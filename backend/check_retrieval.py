"""Read-only smoke test of retrieval against YOUR real database.

    python -m backend.check_retrieval <owner/repo> [--max-files 5]

Reads DATABASE_URL from the environment (or .env). Writes nothing.

What it tells you:
  1. what is in code_chunks for this repo (rows per source, how many have embeddings)
  2. which pr_diff file versions it uses as queries (the most recently embedded)
  3. what retrieve_context returns, with similarity scores
  4. how many survive the min_similarity threshold  -> use this to tune the 0.5 guess
  5. the exact REFERENCE CONTEXT block the model would be shown
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
import statistics
import sys
from dataclasses import dataclass

from sqlalchemy import desc, func, select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.agents.context_builder import ContextLimits, _render_references, select_references
from backend.models import CodeChunk
from backend.services.retrieval_service import retrieve_context


@dataclass
class DbChangedFile:
    file_path: str
    file_sha: str


def _database_url() -> str:
    try:
        from dotenv import load_dotenv

        load_dotenv()
    except ImportError:
        pass
    url = os.environ.get("DATABASE_URL")
    if not url:
        sys.exit("DATABASE_URL is not set (export it or put it in .env)")
    return url


async def main(repo: str, max_files: int) -> None:
    if not hasattr(CodeChunk, "source"):
        sys.exit("CodeChunk has no `source` column. Add it (model + Alembic migration) first.")

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    engine = create_async_engine(_database_url())
    Session = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with Session() as session:
            ver = (await session.execute(text("SELECT extversion FROM pg_extension WHERE extname='vector'"))).scalar()
            print(f"pgvector version: {ver}")

            # 1. inventory
            rows = (
                await session.execute(
                    select(CodeChunk.source, func.count(), func.count(CodeChunk.embedding))
                    .where(CodeChunk.repo_name == repo)
                    .group_by(CodeChunk.source)
                )
            ).all()
            if not rows:
                names = (await session.execute(select(CodeChunk.repo_name).distinct().limit(10))).scalars().all()
                sys.exit(f"No chunks for repo_name={repo!r}. repo_name values in the table: {names}")
            print(f"\n== code_chunks for {repo} ==")
            for source, total, embedded in rows:
                print(f"  {source:<10} rows={total:<6} with_embedding={embedded}")

            # 2. queries: most recently embedded pr_diff file versions
            ts = func.max(CodeChunk.updated_at).label("ts")
            latest = (
                await session.execute(
                    select(CodeChunk.file_path, CodeChunk.file_sha, ts)
                    .where(
                        CodeChunk.repo_name == repo,
                        CodeChunk.source == "pr_diff",
                        CodeChunk.embedding.is_not(None),
                    )
                    .group_by(CodeChunk.file_path, CodeChunk.file_sha)
                    .order_by(desc(ts))
                    .limit(max_files)
                )
            ).all()
            if not latest:
                sys.exit("No embedded pr_diff rows for this repo: nothing to use as a query.")
            files = [DbChangedFile(p, sha) for p, sha, _ in latest]
            print("\n== query files (pr_diff, newest first) ==")
            for f in files:
                print(f"  {f.file_path}  sha={f.file_sha[:8]}")

            # 3. retrieval
            chunks = await retrieve_context(session, repo_name=repo, changed_files=files)
            print(f"\n== retrieve_context -> {len(chunks)} candidate chunk(s) ==")
            for c in chunks:
                preview = c.content[:70].replace("\n", " ")
                print(f"  {c.similarity:6.3f}  {c.file_path} (chunk {c.chunk_index})  {preview!r}")
            if not chunks:
                sys.exit("Nothing retrieved. If the log above says 'Retrieval failed', that is the cause.")

            # 4. threshold tuning
            sims = [c.similarity for c in chunks]
            print(
                f"\nsimilarity: min={min(sims):.3f} median={statistics.median(sims):.3f} max={max(sims):.3f}; "
                + ", ".join(f">={t}: {sum(s >= t for s in sims)}" for t in (0.5, 0.6, 0.7, 0.8))
            )
            limits = ContextLimits()
            kept = select_references(chunks, limits)
            print(f"kept after min_similarity={limits.min_similarity} and budgets: {len(kept)}")

            # 5. exactly what the model would see
            block = _render_references(kept, {f.file_path for f in files}, nonce="check")
            print("\n== REFERENCE CONTEXT the model would receive (first 1500 chars) ==")
            print(block[:1500])
    finally:
        await engine.dispose()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("repo", help="repo_name exactly as stored, e.g. owner/repo")
    ap.add_argument("--max-files", type=int, default=5)
    args = ap.parse_args()
    asyncio.run(main(args.repo, args.max_files))