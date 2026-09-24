"""Run a safe, synthetic command-injection evaluation against the security LLM.

This is intentionally not application code: it never creates or executes the
vulnerable command; it only supplies a unified diff to the reviewer.
"""
from __future__ import annotations

import asyncio
from pathlib import Path

from backend.agents.context_builder import PatchFile, build_review_context
from backend.agents.security_agent import review_security


async def main() -> None:
    fixture_path = Path(__file__).parents[2] / "tests" / "fixtures" / "vulnerable_command_runner.py"
    fixture_lines = fixture_path.read_text(encoding="utf-8").splitlines()
    fixture_diff = "@@ -0,0 +1,%d @@\n%s" % (
        len(fixture_lines),
        "\n".join(f"+{line}" for line in fixture_lines),
    )
    print(f"Starting security evaluation for {fixture_path.name}...", flush=True)
    context = build_review_context(
        repo="eval/security-fixtures",
        pr_number=1,
        head_sha="synthetic",
        title="Add command runner",
        description="Evaluate a newly added command runner before merging.",
        files=[PatchFile(
            "tests/fixtures/vulnerable_command_runner.py",
            fixture_diff,
            "added",
        )],
        nonce="security-eval",
    )
    print("Sending synthetic command-injection diff through the configured review providers...", flush=True)
    findings = await review_security(context)
    print(f"findings={len(findings)}")
    if not findings:
        raise RuntimeError(
            "Gemini returned no valid finding for the synthetic command-injection fixture"
        )
    for finding in findings:
        print(f"{finding.severity} {finding.category} {finding.file_path}:{finding.line_start}")
        print(finding.summary)


if __name__ == "__main__":
    asyncio.run(main())
