import unittest

from backend.agents.context_builder import RetrievedChunk
from backend.services.retrieval_service import EmbeddedReference, rank_similar_references


class SimilarityRetrievalTests(unittest.TestCase):
    def test_returns_top_four_similar_references_in_order(self):
        references = [
            EmbeddedReference("auth.py", "auth" * 100, [1.0, 0.0]),
            EmbeddedReference("db.py", "db" * 100, [0.9, 0.1]),
            EmbeddedReference("api.py", "api" * 100, [0.0, 1.0]),
            EmbeddedReference("docs.md", "docs" * 100, [-1.0, 0.0]),
            EmbeddedReference("unrelated.py", "other" * 100, [0.0, -1.0]),
        ]

        result = rank_similar_references([1.0, 0.0], references, top_k=4, max_chars=2_000)

        self.assertEqual([item.file_path for item in result], ["auth.py", "db.py", "api.py", "unrelated.py"])
        self.assertLessEqual(sum(len(item.content) for item in result), 2_000)

    def test_caps_reference_code_at_two_thousand_characters(self):
        references = [EmbeddedReference("large.py", "x" * 5_000, [1.0, 0.0])]

        result = rank_similar_references([1.0, 0.0], references)

        self.assertEqual(len(result), 1)
        self.assertEqual(len(result[0].content), 2_000)


if __name__ == "__main__":
    unittest.main()