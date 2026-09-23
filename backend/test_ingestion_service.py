import unittest
from unittest.mock import AsyncMock, patch

from backend.integrations.github_client import ChangedFile
from backend.services.ingestion_service import ingest_changed_files


class IngestionCacheTests(unittest.IsolatedAsyncioTestCase):
    async def test_cached_file_skips_embedding(self):
        session = AsyncMock()
        cached_row = type("CachedRow", (), {"scalar_one_or_none": lambda self: "cached-id"})()
        session.execute.return_value = cached_row
        changed_file = ChangedFile(
            file_path="app.py",
            status="modified",
            file_sha="a" * 40,
            patch="@@ -1,1 +1,1 @@\n+cached content",
            additions=1,
            deletions=0,
        )

        with patch(
            "backend.services.ingestion_service.embedding_service.get_embedding",
            new_callable=AsyncMock,
        ) as get_embedding:
            await ingest_changed_files(session, "acme/api", 7, [changed_file])

        get_embedding.assert_not_awaited()
        session.commit.assert_not_awaited()
        session.execute.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()