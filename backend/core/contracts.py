"""Shared domain contracts used across modules."""

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class AgentType(str, Enum):
    """Specialist agent families that can raise findings."""

    SECURITY = "security"
    QUALITY = "quality"
    TESTS = "tests"
    DOCS = "docs"


class Severity(str, Enum):
    """Finding severity levels from blocking to informational."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class Finding(BaseModel):
    """Structured output from any specialist agent.

    This contract ensures all four agents produce consistent, composable output
    that can be merged, ranked, and deduplicated by downstream workflow steps.
    """

    agent_type: AgentType = Field(description="Which agent raised this finding.")
    severity: Severity = Field(description="How severe this issue is.")
    category: str = Field(
        description="Finding category, such as injection, missing_test, or undocumented_api."
    )
    file_path: str = Field(description="Path relative to the repository root.")
    line_start: int = Field(ge=1, description="Starting line number, 1-indexed.")
    line_end: int = Field(ge=1, description="Ending line number, inclusive.")
    summary: str = Field(description="One-line finding title.")
    suggestion: str = Field(description="Recommended remediation.")
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Confidence score from 0.0 to 1.0.",
    )
    rationale: str = Field(description="Evidence-backed explanation for the finding.")

    model_config = ConfigDict(use_enum_values=True)

    @model_validator(mode="after")
    def validate_line_range(self) -> "Finding":
        """Ensure the ending line does not precede the starting line."""
        if self.line_end < self.line_start:
            raise ValueError("line_end must be greater than or equal to line_start")
        return self
