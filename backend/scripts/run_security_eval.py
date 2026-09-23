"""Run a safe, synthetic command-injection evaluation against the security LLM.

This is intentionally not application code: it never creates or executes the
vulnerable command; it only supplies a unified diff to the reviewer.
"""
from __future__ import annotations

import asyncio

from backend.agents.context_builder import PatchFile, build_review_context
from backend.agents.security_agent import review_security


async def main() -> None:
    print("Starting Gemini security evaluation...", flush=True)
    context = build_review_context(
        repo="eval/security-fixtures",
        pr_number=1,
        head_sha="synthetic",
        title="Add command execution endpoint",
        description="Synthetic security-agent evaluation only.",
        files=[PatchFile(
            "app/command_runner.py",
            "@@ -0,0 +1,6 @@\n+import subprocess\n+\n+def run(command: str) -> None:\n+    subprocess.run(command, shell=True, check=True)\n+\n+",
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
