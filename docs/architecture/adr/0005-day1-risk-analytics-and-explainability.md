# ADR-0005: Explainable Day 1 Risk Analytics

- Status: Accepted for preparation
- Date: 2026-07-21

## Decision

Analytics contracts cover simple and log returns, annualized volatility,
maximum drawdown, historical VaR, historical expected shortfall,
deterministic scenario shocks, and portfolio contribution summaries. Every
result records confidence level where applicable, horizon, sample period,
observation count, methodology, assumptions, warnings, limitations, and
evidence references. Tail-risk results warn when the sample is inadequate.

Reports are human-readable HTML/Markdown. Agent timelines identify role,
capability, evidence, assumptions, warnings, limitations, and an output digest.
No result is an executable optimization, trade, hedge, rebalance, or order
recommendation; consequential actions remain explicit human review points.
PDF export and notebook execution are deferred.
