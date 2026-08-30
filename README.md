# AI PR Review Agent

A production-grade, first-principles AI pull request review system using
multiple specialist LLM agents grounded in codebase context.

## Architecture Highlights

- **Multi-Agent**: Four specialist agents for security, quality, tests, and docs.
- **Grounded**: RAG with hybrid vector and full-text search for codebase context.
- **Observable**: Complete event spine with audit trail and cost tracking.
- **Cost-Aware**: Hard budget controls prevent runaway LLM spending.
- **Reliable**: Failure catalog, retries, circuit breakers, and graceful degradation.
- **Human-Centered**: Confidence-weighted HITL gate routes uncertain reviews to humans.

## Quick Start

```bash
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install -r requirements.txt

cp .env.example .env
# Edit .env with Tiger Cloud, OpenAI, and GitHub credentials.

python -m backend.main
```

## 18-Day Build Plan

This project follows an 18-day intensive plan:

- Days 1-2: Foundation and architecture.
- Days 3-5: Backend infrastructure.
- Days 6-8: Data layer and retrieval.
- Days 9-11: Agent system.
- Days 12-14: Frontend and integration.
- Days 15-17: Reliability and observability.
- Day 18: Evaluation and deployment.

See `docs/BUILD_PLAN.md` for the detailed phase breakdown once it is added.

## Architecture Decision Records

- [ADR-001: LangGraph vs Temporal](docs/adr/ADR-001-LangGraph-vs-Temporal.md)
- [ADR-002: Modular Monolith](docs/adr/ADR-002-Modular-Monolith.md)
- [ADR-003: Tiger Cloud Single Spine](docs/adr/ADR-003-Tiger-Cloud-Single-Spine.md)
- [ADR-004: BudgetGuard Hard Blocks](docs/adr/ADR-004-BudgetGuard-Hard-Blocks.md)

## Module Structure

See [ARCHITECTURE.md](docs/ARCHITECTURE.md) for complete module
responsibilities and dependency rules.

## Testing

```bash
pytest
pytest --cov
```

## Production Deployment

The intended production target is Railway with:

- Docker containerization.
- Environment-based configuration.
- Database migrations on startup.
- Health checks and monitoring.

```bash
docker build -t ai-pr-review .
railway deploy
```

# Test
"# Test" 
