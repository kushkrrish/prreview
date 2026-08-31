"""Application-specific exception hierarchy."""


class AIReviewAgentException(Exception):
    """Base exception for all system errors."""


class ConfigurationError(AIReviewAgentException):
    """Configuration validation failed."""


class WorkflowError(AIReviewAgentException):
    """Workflow orchestration error."""


class RetrievalError(AIReviewAgentException):
    """Memory or retrieval layer error."""


class LLMError(AIReviewAgentException):
    """LLM provider error, such as rate limit, timeout, or invalid response."""


class ValidationError(AIReviewAgentException):
    """Input validation error."""


class GitHubError(AIReviewAgentException):
    """GitHub API or webhook processing error."""


class DatabaseError(AIReviewAgentException):
    """Database operation error."""

