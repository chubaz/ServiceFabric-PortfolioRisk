# Thesis Sprint Day 4 specialist handoff

## Lane and branch

- Lane: `day4`
- Branch: `feature/thesis-day4`
- Lane base: `696c9f19c763d33bfde5c290f0049eefc2f9100a`.
- Candidate head: the implementation commit containing this handoff on
  `feature/thesis-day4`.
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

The specialist implementation changes only the declared Day 4 lane:

- the Day 2 historical-as-of adapter and Day 4 CLI surface;
- reviewed fixture and real-example manifests plus synthetic labels/pricing;
- contracts, manifest validation, coverage, post-seal labels, descriptive
  evaluation, the resumable runner, reporting, dashboard, and schemas;
- focused Day 4 contract, manifest, label, evaluation, runner, and report tests.

Validation completed:

- 44 focused Day 4 tests passed;
- 57 Day 2–4 and Day 3 vertical-slice regression tests passed;
- the complete fixture matrix ran twice, with the second pass resuming all
  immutable task evidence without duplicate calls;
- the accepted fixture bundle contains 45 contexts, 135 primary observations,
  18 repeats, 45 labels, 270 receipts, five rule-selected cases, three SVGs,
  the offline dashboard, and public-safe Markdown;
- `validate-day4-run --require-successful-provider --require-exit-criteria`
  passed;
- fixture evidence-manifest file digest:
  `sha256:096ed3b593d8e3983afd1d3d43c4de446e99085929bba5efb23e532c2222280a`;
- `git diff --check` passed.

## Current deviations

The synthetic fixture uses zero-token deterministic receipts and deliberately
includes one control-window false-positive pattern and one critic-created
abstention pattern so every frozen acceptance rule is exercised. No actual
provider is called.

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

Validate lane ownership, push `feature/thesis-day4`, merge it with a merge
commit into `integration/thesis-experiment`, replace the activation Make
stubs, and run the integrated fixture and preserved Day 3 gates. Then prepare
the external real manifest for explicit human review before any provider call.
