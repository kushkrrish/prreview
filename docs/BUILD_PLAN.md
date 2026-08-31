# Build Plan

## Days 1-2: Foundation and Architecture

- Create the modular monolith structure.
- Define core contracts, settings, exceptions, and orchestration boundaries.
- Document architectural decisions with ADRs.
- Prepare the database lifecycle hooks for Tiger Cloud integration.

## Days 3-5: Backend Infrastructure

- Add async database engine and migrations.
- Implement GitHub App authentication and webhook verification.
- Configure ARQ workers and Redis-backed job dispatch.

## Days 6-8: Data Layer and Retrieval

- Create review, finding, code chunk, and event schemas.
- Implement code ingestion and embedding generation.
- Add hybrid retrieval over pgvector and full-text search.

## Days 9-11: Agent System

- Implement security, quality, tests, and docs agents.
- Add prompt registry and structured finding validation.
- Merge, deduplicate, and rank findings across agents.

## Days 12-14: Frontend and Integration

- Build review status and findings views.
- Add GitHub status updates and PR comments.
- Wire the full webhook-to-review workflow.

## Days 15-17: Reliability and Observability

- Add retries, timeouts, circuit breakers, and graceful degradation.
- Implement audit events, traces, and cost telemetry.
- Enforce BudgetGuard limits before LLM calls.

## Day 18: Evaluation and Deployment

- Run evaluation against representative pull requests.
- Tune severity thresholds and HITL routing.
- Package and deploy the production service.

