# ADR-001: LangGraph vs Temporal for Workflow Orchestration

## Status
ACCEPTED

## Context
We need a workflow orchestrator that can:
1. Run four specialist agents in parallel.
2. Checkpoint state to survive worker crashes.
3. Handle retries on transient LLM errors.
4. Integrate cleanly with LLM provider APIs.

Two main candidates are under consideration:
- **LangGraph**: Lightweight, LLM-native, and runs in process.
- **Temporal**: Heavy, battle-hardened, and runs as separate infrastructure.

## Decision
Choose LangGraph for Phases 1-12.

Revisit this decision if sustained concurrent workflows exceed 50/minute, or if
cross-service coordination becomes a core requirement.

## Rationale
1. **Cost now**: LangGraph requires no extra infrastructure.
2. **Speed to market**: It can deploy in the same process as FastAPI.
3. **LLM integration**: It is built for agents rather than generic workflows.
4. **Learning curve**: It is simpler for a small team.
5. **Migration path**: LangGraph is hidden behind `core/workflow_engine.py`.

## Consequences
- **Positive**: Fast iteration, no ops overhead, tighter LLM integration.
- **Negative**: It will not scale to thousands of concurrent workflows.
- **Mitigation**: If scale requires it, implement a Temporal-backed version of
  the `WorkflowEngine` interface.

## Implementation
All orchestration callers import from `backend.core.workflow_engine`, never
directly from LangGraph. Implementation details live in
`backend/orchestrator/langgraph_engine.py`.

