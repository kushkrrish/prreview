"""backend/services/chunking_strategies.py"""
from abc import ABC, abstractmethod
import re
from typing import Any, Dict, List


class ChunkingStrategy(ABC):
    """Abstract Strategy interface for diff chunking."""
    @abstractmethod
    def chunk(self, file_path: str, pr_number: int, diff_text: str) -> List[str]:
        """Splits diff text into structured chunks with contextual headers."""
        pass


class SingleChunkStrategy(ChunkingStrategy):
    """Strategy for Small Diffs (<= 50 lines): Keeps entire file diff intact."""
    def chunk(self, file_path: str, pr_number: int, diff_text: str) -> List[str]:
        return [
            f"File: {file_path} | PR #{pr_number} | Strategy: SingleChunk\n---\n{diff_text}"
        ]


class HunkBoundaryStrategy(ChunkingStrategy):
    """Strategy for Medium Diffs (51 - 200 lines): Splits along @@ git hunk boundaries."""
    def _parse_hunks(self, diff_text: str) -> List[Dict[str, Any]]:
        # Git omits ",count" when the hunk covers exactly 1 line, e.g.
        # "@@ -5 +5,2 @@" instead of "@@ -5,1 +5,2 @@". The count on
        # EITHER side must be optional, or these single-line hunks silently
        # fail to match and get merged into the previous hunk instead of
        # being recognized as their own boundary.
        hunk_pattern = re.compile(r"^@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@(.*)$", re.MULTILINE)
        matches = list(hunk_pattern.finditer(diff_text))
        if not matches:
            return [{"header": "@@ Full Diff @@", "lines": diff_text.splitlines()}]
        hunks = []
        for i in range(len(matches)):
            start = matches[i].start()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(diff_text)
            hunk_raw = diff_text[start:end].splitlines()
            hunks.append({
                "header": hunk_raw[0] if hunk_raw else "",
                "lines": hunk_raw[1:] if len(hunk_raw) > 1 else [],
            })
        return hunks

    def chunk(self, file_path: str, pr_number: int, diff_text: str) -> List[str]:
        hunks = self._parse_hunks(diff_text)
        chunks = []
        for idx, hunk in enumerate(hunks, start=1):
            chunks.append(
                f"File: {file_path} | PR #{pr_number} | Hunk #{idx}: {hunk['header']}\n---\n"
                + "\n".join(hunk["lines"])
            )
        return chunks


class SlidingWindowStrategy(ChunkingStrategy):
    """Strategy for Large Diffs (> 200 lines): Fixed token window with line overlap."""
    def __init__(self, window_size: int = 150, overlap: int = 15):
        if overlap >= window_size:
            raise ValueError("overlap must be smaller than window_size, or the window never advances")
        self.window_size = window_size
        self.step = window_size - overlap

    def chunk(self, file_path: str, pr_number: int, diff_text: str) -> List[str]:
        lines = diff_text.splitlines()
        chunks = []
        for start in range(0, len(lines), self.step):
            window = lines[start : start + self.window_size]
            chunks.append(
                f"File: {file_path} | PR #{pr_number} | Lines {start+1}-{start+len(window)}\n---\n"
                + "\n".join(window)
            )
        return chunks


class AdaptiveChunkerFactory:
    """Factory Context that selects the appropriate Chunking Strategy based on diff metrics."""
    @staticmethod
    def get_strategy(diff_text: str) -> ChunkingStrategy:
        line_count = len(diff_text.splitlines())
        if line_count <= 50:
            return SingleChunkStrategy()
        elif line_count <= 200:
            return HunkBoundaryStrategy()
        else:
            return SlidingWindowStrategy()