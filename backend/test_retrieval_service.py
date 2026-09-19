"""Run from the repository root with:  python -m unittest backend.test_retrieval_service -v

Covers the pure logic only. The SQL in _nearest/_load_query_vectors needs a real
Postgres+pgvector; see the integration checklist in the chat reply.
"""
"""Real-database test of the SQL in retrieval_service.

Skipped unless RETRIEVAL_TEST_DATABASE_URL is set. Use your DEV database (the
docker-compose one). It writes a few rows under random repo names
("itest/retrieval-xxxx") and deletes them afterwards, so real data is untouched.

    RETRIEVAL_TEST_DATABASE_URL="postgresql+asyncpg://user:pass@localhost:5432/db" \\
        python -m unittest tests.services.test_retrieval_integration -v

Vectors are hand-made (unit vectors), so the expected cosine similarities are
exact and don't depend on any embedding model:
    query (pr_diff of app/db.py)   = e0
    app/views.py  (full_file)      = e0                -> similarity 1.0
    app/models.py (full_file)      = 0.8*e0 + 0.6*e1   -> similarity 0.8
    app/old_pr.py (pr_diff)        = e0   TRAP: wrong source, must be excluded
    secret/x.py   (other repo)     = e0   TRAP: wrong tenant, must be excluded
"""
import logging
import os
import unittest
import uuid
from dataclasses import dataclass

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.agents.context_builder import PatchFile, build_review_context
from backend.models import CodeChunk
from backend.services.retrieval_service import RetrievalConfig, retrieve_context

DB_URL = os.environ.get("RETRIEVAL_TEST_DATABASE_URL")
DIM = 768


def unit(i: int) -> list[float]:
    return [1.0 if j == i else 0.0 for j in range(DIM)]


MIX = [0.8, 0.6] + [0.0] * (DIM - 2)


@dataclass
class FakeChangedFile:
    file_path: str
    file_sha: str


@unittest.skipUnless(DB_URL, "set RETRIEVAL_TEST_DATABASE_URL to run against a real database")
class RetrievalAgainstRealDB(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.assertTrue(
            hasattr(CodeChunk, "source"),
            "CodeChunk has no `source` column: add it (model + Alembic migration) before retrieval can work",
        )
        run = uuid.uuid4().hex[:8]
        self.repo = f"itest/retrieval-{run}"
        self.other_repo = f"itest/other-{run}"

        self.engine = create_async_engine(DB_URL)
        self.Session = async_sessionmaker(self.engine, expire_on_commit=False)
        # cleanups run last-in-first-out: delete rows first, then dispose the engine
        self.addAsyncCleanup(self.engine.dispose)
        self.addAsyncCleanup(self._delete_rows)

        def chunk(repo, path, sha, source, vec, text):
            return CodeChunk(
                repo_name=repo, file_path=path, chunk_index=0, file_sha=sha,
                source=source, chunk_text=text, embedding=vec,
            )

        async with self.Session() as s:
            s.add_all(
                [
                    chunk(self.repo, "app/db.py", "sha1", "pr_diff", unit(0), "the PR's diff chunk"),
                    chunk(self.repo, "app/views.py", "v1", "full_file", unit(0), "VIEWS baseline"),
                    chunk(self.repo, "app/models.py", "m1", "full_file", MIX, "MODELS baseline"),
                    chunk(self.repo, "app/old_pr.py", "o1", "pr_diff", unit(0), "OTHER PR HISTORY"),
                    chunk(self.other_repo, "secret/x.py", "s1", "full_file", unit(0), "OTHER TENANT"),
                ]
            )
            await s.commit()

    async def _delete_rows(self):
        async with self.Session() as s:
            await s.execute(delete(CodeChunk).where(CodeChunk.repo_name.in_([self.repo, self.other_repo])))
            await s.commit()

    async def _retrieve(self, files):
        """retrieve_context swallows errors by design; surface them as test failures."""
        async with self.Session() as s:
            with self.assertLogs("backend.services.retrieval_service", level="INFO") as logs:
                got = await retrieve_context(
                    s, repo_name=self.repo, changed_files=files, config=RetrievalConfig(neighbors_per_query=5)
                )
        errors = [line for line in logs.output if line.startswith("ERROR")]
        self.assertFalse(errors, f"retrieval swallowed an error (run check_retrieval.py for the traceback): {errors}")
        return got

    async def test_returns_nearest_baseline_in_similarity_order(self):
        got = await self._retrieve([FakeChangedFile("app/db.py", "sha1")])
        self.assertEqual([c.file_path for c in got][:2], ["app/views.py", "app/models.py"])
        self.assertAlmostEqual(got[0].similarity, 1.0, places=4)
        self.assertAlmostEqual(got[1].similarity, 0.8, places=4)
        self.assertEqual(got[0].content, "VIEWS baseline")

    async def test_excludes_other_sources_and_other_repos(self):
        got = await self._retrieve([FakeChangedFile("app/db.py", "sha1")])
        paths = {c.file_path for c in got}
        self.assertNotIn("app/old_pr.py", paths, "pr_diff rows must never be returned as context")
        self.assertNotIn("secret/x.py", paths, "rows from another repo leaked (tenant boundary broken)")
        self.assertTrue(all(c.source == "full_file" for c in got))

    async def test_file_without_stored_embeddings_returns_empty(self):
        self.assertEqual(await self._retrieve([FakeChangedFile("nope.py", "zzz")]), [])

    async def test_stale_file_sha_returns_empty(self):
        # the query must use the exact version of the file that is in this PR
        self.assertEqual(await self._retrieve([FakeChangedFile("app/db.py", "OLDSHA")]), [])

    async def test_database_to_prompt_end_to_end(self):
        got = await self._retrieve([FakeChangedFile("app/db.py", "sha1")])
        ctx = build_review_context(
            repo=self.repo, pr_number=1, head_sha="abc", title="t", description=None,
            files=[PatchFile("app/db.py", "@@ -1,1 +1,2 @@\n context\n+x = 1")],
            retrieved=got, nonce="deadbeef",
        )
        self.assertIn("Reference only - do NOT review this code.", ctx.shared_prompt)
        self.assertIn("app/views.py (not modified by this PR)", ctx.shared_prompt)
        self.assertIn("VIEWS baseline", ctx.shared_prompt)
        self.assertNotIn("OTHER TENANT", ctx.shared_prompt)
        self.assertNotIn("OTHER PR HISTORY", ctx.shared_prompt)


if __name__ == "__main__":
    unittest.main()