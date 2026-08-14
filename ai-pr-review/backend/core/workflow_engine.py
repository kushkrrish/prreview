"""Workflow orchestration abstraction."""

from abc import ABC, abstractmethod
from typing import Any


class WorkflowEngine(ABC):
    """Abstract interface for workflow orchestration.

    This interface allows swapping implementations, for example from LangGraph
    to Temporal, without changing the rest of the codebase.
    """

    @abstractmethod
    async def run(self, workflow_id: str, input_state: dict[str, Any]) -> dict[str, Any]:
        """Execute a workflow from start to completion."""

    @abstractmethod
    async def resume(self, workflow_id: str) -> dict[str, Any]:
        """Resume an interrupted workflow from its last checkpoint."""

    @abstractmethod
    async def get_state(self, workflow_id: str) -> dict[str, Any]:
        """Fetch the current workflow state."""

    @abstractmethod
    async def list_running(self) -> list[str]:
        """List currently executing workflow identifiers."""

