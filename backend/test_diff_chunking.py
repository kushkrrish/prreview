import unittest

from backend.agents.context_builder import PatchFile, split_diff_by_file


class DiffChunkingTests(unittest.TestCase):
    def test_splits_files_and_skips_trivial_patches(self):
        files = [
            PatchFile("small.py", "@@ -1 +1 @@\n+x"),
            PatchFile("large.py", "@@ -1 +1 @@\n+" + "a" * 600),
            PatchFile("second.py", "@@ -1 +1 @@\n+" + "b" * 600),
        ]

        chunks = split_diff_by_file(files)

        self.assertEqual([chunk.path for chunk in chunks], ["large.py", "second.py"])

    def test_splits_oversized_file_by_hunk(self):
        patch = "\n".join([
            "@@ -1,1 +1,1 @@",
            "+" + "a" * 2_600,
            "@@ -20,1 +20,1 @@",
            "+" + "b" * 2_600,
        ])

        chunks = split_diff_by_file([PatchFile("large.py", patch)])

        self.assertEqual([chunk.path for chunk in chunks], ["large.py", "large.py"])
        self.assertTrue(all(len(chunk.patch or "") >= 500 for chunk in chunks))


if __name__ == "__main__":
    unittest.main()