"""Parse GitHub unified-diff patches and render them with explicit line numbers.

Why this exists: LLMs cannot reliably count lines inside a raw diff, and wrong
line numbers are the most common way PR bots break (GitHub rejects inline
comments on lines outside the diff). So *we* compute the numbers and print
them on every line; the model only has to copy them.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from functools import cached_property
from typing import Literal

# "@@ -10,5 +10,6 @@ optional function context". Counts are optional in git output.
_HUNK_RE = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@")

LineKind = Literal["add", "context", "remove"]
_MARKER = {"add": "+", "context": " ", "remove": "-"}


@dataclass(frozen=True)
class DiffLine:
    kind: LineKind
    text: str
    new_lineno: int | None  # None for removed lines: they don't exist in the new file


@dataclass
class Hunk:
    header: str
    lines: list[DiffLine] = field(default_factory=list)


@dataclass
class FileDiff:
    path: str
    status: str
    hunks: list[Hunk]

    @cached_property
    def visible_lines(self) -> dict[int, DiffLine]:
        """New-side lines GitHub lets us comment on (added + context)."""
        return {
            ln.new_lineno: ln
            for h in self.hunks
            for ln in h.lines
            if ln.new_lineno is not None
        }

    @cached_property
    def added_linenos(self) -> frozenset[int]:
        return frozenset(n for n, ln in self.visible_lines.items() if ln.kind == "add")


def parse_patch(path: str, patch: str, status: str = "modified") -> FileDiff:
    """Parse the ``patch`` string PyGithub returns for a changed file."""
    hunks: list[Hunk] = []
    current: Hunk | None = None
    new_no = 0

    for raw in patch.splitlines():
        m = _HUNK_RE.match(raw)
        if m:
            current = Hunk(header=raw)
            hunks.append(current)
            new_no = int(m.group(1))
            continue
        # Ignore anything before the first hunk and "\ No newline at end of file".
        if current is None or raw.startswith("\\"):
            continue

        marker, text = raw[:1], raw[1:]
        if marker == "+":
            current.lines.append(DiffLine("add", text, new_no))
            new_no += 1
        elif marker == "-":
            current.lines.append(DiffLine("remove", text, None))
        else:  # " " (context). A truly empty raw line is also a blank context line.
            current.lines.append(DiffLine("context", text, new_no))
            new_no += 1

    return FileDiff(path=path, status=status, hunks=hunks)


def render_file_diff(fd: FileDiff) -> str:
    """Render as ``<line number>|<marker><code>``; removed lines get no number."""
    out = [f"FILE: {fd.path} ({fd.status})"]
    for hunk in fd.hunks:
        out.append(hunk.header)
        for ln in hunk.lines:
            num = f"{ln.new_lineno:>5}" if ln.new_lineno is not None else "     "
            out.append(f"{num}|{_MARKER[ln.kind]}{ln.text}")
    return "\n".join(out)