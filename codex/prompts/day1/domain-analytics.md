# Domain-analytics lane prompt template

Lane: domain-analytics; branch: `feature/day1-domain-analytics`. Own only
declared domain/analytics/schema/test directories and the exact handoff.

Acceptance: immutable contracts cover all seven approved methods and include
confidence, horizon, sample period, observation count, methodology,
assumptions, warnings, limitations, and evidence; inadequate tail samples
warn. Exclude optimization, advice, trades, hedges, rebalances, orders,
providers, notebooks, and app edits. Run focused contract/domain/analytics
tests and `git diff --check`, document evidence and limitations, commit a
focused candidate, validate the current lifecycle gate, and stop without merge.
