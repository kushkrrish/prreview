# ADR-002: Modular Monolith Architecture

## Status
ACCEPTED

## Context
As a startup building an AI agent, we need to:
- Deploy quickly.
- Keep operational complexity low.
- Iterate rapidly on agent reasoning.
- Stay within a constrained operations budget.

## Decision
Build a modular monolith, not microservices.

The system runs as a single Python application with:
- Internal modules with clear boundaries.
- A dependency rule of core inward, feature modules outward.
- The option to extract services later when pressure justifies it.

## Rationale
1. **Operational**: One database, one app process, one CI/CD pipeline.
2. **Development**: No RPC latency and easier debugging.
3. **Cost**: No load balancers, service mesh, or multi-service observability burden.
4. **Reversibility**: Workers and services can be extracted when actually needed.

## Consequences
- **Positive**: Simple deployment and fast iteration.
- **Negative**: A single process can become a bottleneck.
- **Mitigation**: Extract ARQ workers into separately scaled processes early.

## Implementation
See `docs/ARCHITECTURE.md` for module dependency rules.

