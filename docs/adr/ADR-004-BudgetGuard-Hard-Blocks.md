# ADR-004: BudgetGuard Pattern for Hard Cost Blocking

## Status
ACCEPTED

## Context
LLM costs can spiral if a bug causes loops, for example an infinite retry loop
that spends hundreds or thousands of dollars per hour.

We need cost control that is:
- **Hard blocking**: Refuse LLM calls over a daily limit.
- **Visible**: Show spend in real time.
- **Actionable**: Route work to cheaper models when appropriate.

## Decision
Implement BudgetGuard with:
1. A daily hard cap, such as $100/day.
2. A per-PR soft limit that warns without blocking.
3. Cost-aware routing that chooses cheaper models when available.
4. Real-time tracking via continuous aggregates.

## Rationale
1. **Risk mitigation**: The system cannot accidentally spend $10k.
2. **Transparency**: Every token is visible.
3. **ROI**: Cost becomes an input to the agent autonomy decision.

## Consequences
- **Positive**: Bounded risk and cost-aware behavior.
- **Negative**: Adds complexity to orchestration.
- **Mitigation**: Keep BudgetGuard logic in one module, `economics/budget.py`.

## Implementation
Read cost from the `agent_health_1m` aggregate before each LLM call.

Block when:

```text
(today_cost + estimated_call_cost) > daily_cap
```

