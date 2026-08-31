# ADR-003: Tiger Cloud as the Single Data Spine

## Status
ACCEPTED

## Context
We need three data shapes:
1. **Memory**: Semantic vectors for code chunks.
2. **Truth**: Relational records for reviews, findings, and feedback.
3. **Time**: Time-series events for traces, audit, and cost.

A naive design would split these into Qdrant, Postgres, and ClickHouse. A
simpler approach uses managed Postgres with the right extensions.

## Decision
Use Tiger Cloud, a managed Postgres platform with pgvector and TimescaleDB.

One durable data spine provides three lanes:
- Lane 1: `code_chunks` with pgvector and DiskANN for memory.
- Lane 2: `pr_reviews`, `findings`, and `hitl_reviews` for truth.
- Lane 3: `agent_events` hypertables and aggregates for time.

## Rationale
1. **Operational**: One backup, one connection string, one disaster recovery plan.
2. **Queries**: Findings, events, and cost can be joined in the same transaction.
3. **Cost**: Consolidation beats specialized stores during early scale.
4. **Simplicity**: One product and one mental model.

## Consequences
- **Positive**: Simpler operations, cheaper deployment, and easier joins.
- **Negative**: Specialized systems may outperform Postgres in narrow workloads.
- **Mitigation**: DiskANN makes vector search viable at meaningful scale.

## Implementation
The initial schema will live in `migrations/2026-06-tiger-init.sql`.

