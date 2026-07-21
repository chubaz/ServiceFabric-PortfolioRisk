# Day 1 preparation

Day 0 is complete at tag `day0-complete`; this preparation is complete on
`chore/day1-preparation`. Day 1 implementation has not started.

## Entry and gates

The entry point is `D1-WAVE-1A`. Review this file, the current workplan, ADRs
0003–0005, the lane manifest, and the knowledge-product schedule. Before each
specialist starts: verify branch, run `make preflight`, inspect status, and
work only in manifest-owned paths. Each lane runs focused tests, `git diff
--check`, writes its exact handoff, creates a focused candidate commit, and
stops without merge. Integration accepts commits in the declared order.

## Safety

Synthetic/reviewed-public research and local-private personal portfolio data
are distinct profiles. Providers remain disabled, secrets opaque, and no
licensed/personal files enter Git. No broker, order, rebalance, trade, external
LLM, arbitrary SQL, or notebook execution is permitted.

## Exit

Each wave needs its acceptance gates in `config/agent/day1/waves.json`, focused
tests, evidence, rights/safety review where applicable, and an immutable
handoff. Soft QA is a separate queued gate and cannot be inferred from tests.
