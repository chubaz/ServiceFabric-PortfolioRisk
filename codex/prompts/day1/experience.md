# Day 1 experience lane prompt template

Lane: experience; branch: `feature/day1-experience`. Own only the declared app
and application-test directories and exact handoff.

Acceptance: semantic server-rendered HTML is primary, JSON APIs remain, all
navigation/screens/disclosures/review forms exist, keyboard and responsive
states are readable, and notebook screens are catalogue-only. Exclude Node,
remote assets, frontend framework migration, arbitrary SQL/notebook execution,
broker/order/rebalance effects, and domain business logic. Run focused app
tests and `git diff --check`, record evidence, commit a focused candidate, and
validate the current lifecycle gate, and stop without merge.
