# System Architecture

## Module Dependency Rules

**Golden Rule**: Depend inward only.

```text
           outer, volatile
                  |
                  v
            feature modules
                  |
                  v
     integrations, tools, reliability
                  |
                  v
          database and memory
                  |
                  v
                core
        depends on no application code
```

## Module Map

### Core

`backend/core/exceptions.py`: Exception hierarchy.

`backend/core/contracts.py`: Shared data contracts such as `Finding`.

`backend/core/workflow_engine.py`: Abstract orchestration interface.

### Data and Integration

`backend/database/`: Async Postgres access for Tiger Cloud.

`backend/memory/`: Embeddings, retrieval, and Tiger Cloud vector integration.

`backend/integrations/`: GitHub, Redis, and other external service clients.

### Business Logic

`backend/agents/`: Specialist agent implementations for security, quality,
tests, and documentation.

`backend/orchestrator/`: Workflow execution, including the LangGraph
implementation of the core workflow interface.

`backend/api/`: FastAPI routes and API schemas.

`backend/webhook_receiver/`: GitHub webhook verification and dispatch.

`backend/job_queue/`: ARQ workers and background jobs.

### Cross-Cutting

`backend/observability/`: Events, tracing, cost telemetry, and audit logs.

`backend/reliability/`: Retries, circuit breakers, timeouts, and graceful
degradation.

`backend/security/`: Authentication, authorization, input validation, and
injection guards.

`backend/tools/`: LLM clients, model routing, and reusable tool adapters.

### Configuration

`backend/models/`: Pydantic schemas, enums, and base models.

`backend/prompts/`: Prompt registry and templates.

`backend/settings.py`: Global environment-based configuration.

## Module Responsibilities

### `core/workflow_engine.py`

Single responsibility: define the workflow orchestration contract.

Depends on: nothing outside the Python standard library.

Imported by: `orchestrator/langgraph_engine.py`, API handlers, and job workers.

### `database/`

Single responsibility: async Postgres access for Tiger Cloud.

Depends on: `core/exceptions.py` and `models/`.

Imported by: `agents/`, `api/`, `memory/`, and `orchestrator/`.

### `memory/`

Single responsibility: code embeddings, indexing, RAG, and retrieval.

Depends on: `database/` and `core/`.

Imported by: `agents/` and `orchestrator/`.

### `agents/`

Single responsibility: specialist review agent implementations.

Depends on: `core/`, `database/`, `memory/`, `models/`, and `prompts/`.

Imported by: `orchestrator/`.

### `orchestrator/`

Single responsibility: workflow execution and agent coordination.

Depends on: `core/`, `agents/`, `memory/`, `observability/`, and `reliability/`.

Imported by: `job_queue/` and `api/`.

## Forbidden Dependencies

- Never import LangGraph outside `backend/orchestrator/`.
- Never put SQL in `backend/agents/`.
- Never import `backend/agents/` from `backend/core/`.
- Never create circular dependencies.
- Never import `backend/agents/` from `backend/database/`.

## Communication Patterns

Intra-module communication uses direct calls.

Cross-module communication uses stable contracts such as `Finding`.

External communication goes through clients, such as
`backend/integrations/github_client.py`.

## Testing Strategy

Unit tests cover a single module with dependencies mocked.

Integration tests cover two or three modules with a real test database.

End-to-end tests run the full review workflow against a small test repository.

