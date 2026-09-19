"""Enumerations and category registries used throughout the system."""

from enum import Enum


class AgentTypeEnum(str, Enum):
    """Specialist review agent types."""

    SECURITY = "security"
    QUALITY = "quality"
    TESTS = "tests"
    DOCS = "docs"


class SeverityEnum(str, Enum):
    """Finding severity levels."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


SECURITY_CATEGORIES: dict[str, str] = {
    "injection": "SQL/NoSQL/command injection",
    "auth_bypass": "Authentication/authorization bypass",
    "secrets": "Hardcoded secrets",
    "deserialization": "Unsafe deserialization",
    "crypto": "Cryptography mistake",
    "xxe": "XML external entity vulnerability",
}

QUALITY_CATEGORIES: dict[str, str] = {
    "logic_error": "Logic error or correctness bug",
    "complexity": "Unnecessary complexity",
    "design_pattern": "Violates design pattern",
    "error_handling": "Incomplete error handling",
    "resource_leak": "Resource leak such as file or connection leakage",
    "type_safety": "Type safety issue",
}

TEST_CATEGORIES: dict[str, str] = {
    "missing_test": "Missing test case",
    "edge_case": "Untested edge case",
    "test_quality": "Test quality issue such as brittle or non-deterministic tests",
    "coverage": "Coverage gap",
}

DOCS_CATEGORIES: dict[str, str] = {
    "missing_docstring": "Missing or incomplete docstring",
    "outdated_comment": "Outdated or misleading comment",
    "undocumented_api": "Public API not documented",
    "missing_adr": "Architectural decision not documented",
}


class ReviewStatus(str, Enum):
    """Lifecycle status for a pull request review."""

    PENDING = "pending"
    APPROVED = "approved"
    REVIEW_REQUESTED = "review_requested"
    BLOCKED_CRITICAL = "blocked_critical"


class HITLDecision(str, Enum):
    """Human-in-the-loop decision outcomes."""

    APPROVED = "approved"
    REJECTED = "rejected"
    DISPUTED = "disputed"

