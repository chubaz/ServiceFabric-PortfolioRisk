# Day 1 integration lane prompt template

Lane: integration; branch: `integration/day1`. Own only the integration
allowances in `config/agent/day1/lanes.json`. Integrate in the declared order
after acceptance gates and review focused diffs. Preserve ServiceFabric
canonical runtime ownership, immutable evidence, profile separation, provider
rights, and human review.

Acceptance: manifests, current workplan, cross-lane tests, repository/manifest
checks, and the lifecycle-appropriate completed-wave gates pass. Wave 1A is
active; do not require the historical queued preparation state after activation.
Exclude product implementation outside owned
paths, dependency additions, provider access, broker/order/rebalance effects,
notebook execution, and upstream edits. Run focused tests plus `make
verify-day1-current`; record evidence and exact handoff. Stop without merge.
