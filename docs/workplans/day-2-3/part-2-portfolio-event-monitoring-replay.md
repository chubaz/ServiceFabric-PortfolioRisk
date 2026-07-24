# D23-PART-2 — Portfolio, event monitoring, replay, and Workbench workflows

- Status: complete through integration gates; Part 3 human QA pending
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

## Integration resolution

The original hosted Workbench package omitted required monitoring resources.
Correction candidate `ba6aa12` made the hosted actions pass by tracking four
duplicate CSV fixtures beneath the application. That violates the repository
boundary permitting reviewed synthetic fixtures only beneath
`data/fixtures/synthetic/**` and creates a second source of truth, so
integration rejected the correction.

Experience candidate `4403c37` supplies the compliant staging contract. The
integration smoke stages only the four allow-listed files beneath
`data/fixtures/synthetic/day23/**`, regenerates and checks the complete staged
manifest, and rebuilds the copied pinned ServiceFabric host against that
manifest before installing the staged package. No tracked fixture duplicate is
present beneath the application, and the Workbench runs without repository-
relative runtime access.

The Part 2 application, regression, deterministic demo, lifecycle, and local
process-host smoke gates pass. Part 3 remains queued for human QA, evidence
review, release decision, and merge; no QA-pass or release claim is made here.
