# Thesis Sprint Day 4 specialist handoff

## Lane and branch

- Lane: `day4`
- Branch: `feature/thesis-day4`
- Lane base: reviewed Day 4 activation head on
  `integration/thesis-experiment`; record the exact commit before starting.
- Candidate head: pending specialist implementation.
- Lifecycle: `THESIS-D4` in progress; human soft QA queued.

## Allowed changes

The specialist may modify only:

- `examples/portfolio-risk-thesis/**`;
- `data/fixtures/synthetic/thesis-day4/**`;
- `data/schemas/thesis-experiment-results/**`;
- `tests/thesis/**`;
- the exact file `docs/handoffs/thesis-sprint/day4.md`.

The specialist stops without merge. It must not modify the root Makefile, CI,
control plane, shared contracts or ADRs, lifecycle state, Workbench
application, product packages, requirements, or `vendor/servicefabric/**`.

## Frozen implementation

Implement one manifest-driven, resumable Day 4 runner that reuses the Day 2
metrics kernel and Day 3 B0/B1/A1 treatments. Add no dependency, frontend
framework, provider abstraction, generic experiment framework, second
architecture runner, application change, or large interactive shell script.

The reviewed primary panel is exactly three portfolios by three predeclared
windows by five reviewed daily-close timestamps: 45 contexts and 135
B0/B1/A1 primary results. The repeatability panel has nine predeclared anchors
and 18 additional B1/A1 results. B0 is deterministic and is not recalled. The
maximum authorized provider-call budget is exactly 270.

Architecture execution must close before any of the 45 labels are loaded.
Label paths and values cannot enter an architecture input or model payload.
Use the event-window view as primary and the five-business-day future outcome
and composite OR views as secondary sensitivity views.

Preserve the fixed classification, abstention, provider-error, one-to-one
matching, null metric, pricing, repeatability, privacy, zero-effect, and
no-overclaim rules in
`docs/contracts/thesis-day4-evaluation-v0.1.md`. Provider errors are
execution failures, and an accepted real run requires zero provider errors.

## Required evidence

The immutable external bundle must contain the reviewed experiment manifest,
45 contexts, 135 primary results, 18 additional results, 45 labels, the
architecture and repeatability summaries, a 270-entry call ledger, three
required SVG charts, rule-selected worked examples, preliminary-results
Markdown, an offline static dashboard, a run manifest, and an evidence
manifest.

The public fixture is synthetic and network-free. Private portfolios,
licensed rows and identifiers, credentials, requests, raw responses, pricing,
local paths, and generated real evidence remain outside Git.

## Tests to execute

- `make test-thesis-day4`
- `make verify-thesis-day3`
- `make demo-thesis-day4-fixture`
- `git diff --check`

Validate the candidate range with `scripts/thesis/check_lane_paths.py` before
handoff. Do not commit a claim that one architecture wins.

## Completion report

Before handoff, replace the pending values and record:

- exact lane base and candidate head;
- changed paths;
- tests executed and their results;
- evidence produced and its manifest digest;
- deviations;
- blockers;
- limitations;
- rollback;
- recommended next action.

## Current deviations

None. Day 4 implementation has not yet been produced by this activation.

## Current blockers

None.

## Limitations

Two observations per repeatability anchor support only a preliminary agreement
measure. Results are descriptive research evidence, not investment advice,
and cannot establish significance, predictive superiority, investment
performance, or production readiness.

## Rollback

Discard only the unmerged `feature/thesis-day4` candidate. Do not alter the
accepted Day 1 through Day 3 evidence or completed historical lifecycle
records. Generated evidence is external and is removed, if authorized, only
by targeting its exact immutable run directory.

## Recommended next action

Create `feature/thesis-day4` from the reviewed activation head, implement only
the declared lane paths, run the focused and preserved Day 3 gates, record the
exact candidate head, and stop without merge.
