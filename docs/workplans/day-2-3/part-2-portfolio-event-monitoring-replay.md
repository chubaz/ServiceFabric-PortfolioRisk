# D23-PART-2 — Portfolio, event monitoring, replay, and Workbench workflows

- Status: in progress
- Depends on: `D23-PART-1` (complete)
- Integration order: `monitoring-core` -> `experience` -> `integration`

## Objective

Define and implement, through the two specialist lanes, portfolio-linked local
datasets, local event intelligence, effect-free monitoring policies, the four
monitoring agents, deterministic historical replay, evaluation, reports, and
human-readable Workbench workflows. This activation does not authorize live
providers, external LLMs, broker connectivity, orders, trades, rebalancing, or
investment advice.

## Frozen boundaries

The contracts in `docs/contracts/portfolio-data-context-v0.1.md`,
`event-dataset-v0.1.md`, `monitoring-policy-v0.1.md`, and
`replay-evaluation-v0.1.md` are the Part 2 interface boundary. All observations
remain local, synthetic or explicitly private, provenance-bearing, immutable,
and point-in-time filtered by `available_at`. There is no background scheduler,
arbitrary policy expression language, fuzzy or ticker-based entity matching,
look-ahead, or consequential action.

## Acceptance gates

- specialist ownership and exact handoffs validate;
- Part 1, Day 1, and Day 0 regression gates remain green;
- portfolio context, events, policies, replay, and evaluation contracts are
  reviewable and preserve evidence, warnings, and limitations;
- monitoring and Workbench paths remain canonical-runtime, local-only, and
  effect-free;
- deterministic replay reports undefined metrics as null plus warnings and make
  no predictive claim.

Part 2 completion does not imply Part 3 QA or release approval.
