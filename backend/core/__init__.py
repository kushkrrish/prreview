"""Core contracts, interfaces, and exceptions.

The core package is the innermost architectural layer. It must remain free of
framework, database, provider, and application-specific implementation imports.
"""

from backend.core.contracts import AgentType, Finding, Severity
from backend.core.exceptions import (
    AIReviewAgentException,
    ConfigurationError,
    DatabaseError,
    GitHubError,
    LLMError,
    RetrievalError,
    ValidationError,
    WorkflowError,
)
from backend.core.workflow_engine import WorkflowEngine

__all__ = [
    "AIReviewAgentException",
    "AgentType",
    "ConfigurationError",
    "DatabaseError",
    "Finding",
    "GitHubError",
    "LLMError",
    "RetrievalError",
    "Severity",
    "ValidationError",
    "WorkflowEngine",
    "WorkflowError",
]

