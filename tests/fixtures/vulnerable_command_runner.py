"""Intentionally vulnerable fixture used to exercise PR security detection.

This file is test data only. It is not imported by the application and must not
be used as an implementation example. The reviewer should identify that an
untrusted command is passed to a shell with shell=True. The surrounding helper
text keeps the fixture large enough to pass the review chunk-size threshold.
"""

import subprocess


def execute_user_input(user_input: str) -> str:
    """Execute a supplied command for the security-agent evaluation fixture."""
    result = subprocess.run(
        user_input,
        shell=True,
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout


def fixture_metadata() -> dict[str, str]:
    """Return metadata so this file remains a realistic changed module."""
    return {
        "purpose": "security review evaluation",
        "owner": "test suite",
        "warning": "do not copy this command execution pattern",
    }