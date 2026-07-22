# Day 1 final integration handoff

## Lane, branch, base, and head

- Lane: integration authority.
- Branch: `integration/day1`.
- Day 1 prepared base: `day1-prepared` (`01ff31a3daa0db815da51da16ca19099005149e7`).
- Accepted merged head: `283e3a47d46111252fd3e228a3cf7d8b7908b98a`.
- Final integration state: the reviewed working tree above that head; no commit,
  push, merge to `main`, issue closure, or soft-QA decision was made.

## Accepted specialist candidate commits

- Knowledge: `f207c1e` — Day 1 research, planning, and catalogue records.
- Experience Wave 1A: `c54bf48` — semantic profile-aware Workbench.
- Data: `939ba92` — local portfolio preview/snapshot and provider contracts.
- Experience Wave 1B completion: `9ccca55` — human-readable portfolio and
  provider workspace bindings.
- Domain analytics: `d5888ef` — explainable typed risk methodologies.
- Capabilities and agents: `6793d2e` — registered analytics, reports, and
  deterministic four-agent timelines.
- Experience Wave 1C: `10e5df4` — risk, report, timeline, and review screens.

Integration accepted those candidates in the declared order and preserved the
Day 0 tag, status, schemas, tests, evidence workflow, and pinned ServiceFabric
commit.

## Final integration changes

- `tests/journeys/test_day1_workbench_journey.py` covers both profiles,
  semantic HTML, valid YAML and invalid CSV previews, visible issues, explicit
  confirmation, immutable revisions/comparison, disabled external providers,
  fixed query manifests, every reviewed analytics method, inadequate-sample
  warnings, scenario/contribution reconciliation, four roles, HTML/Markdown
  reports, pending explicit review, empty effects, and prohibited surfaces.
- `scripts/day1/run_day1_demo.py` produces the ten deterministic external
  artifacts and digests every sibling artifact in the evidence manifest.
- `scripts/day1/bootstrap_servicefabric_runtime.py` adds `risk_analytics` to
  the bounded, non-editable, source-digested Day 1 hosted package set while
  retaining the pinned upstream commit and external copied-host adaptation.
- `scripts/day1/servicefabric_smoke.sh` retains the original Text Utility gate,
  verifies built semantic resources by digest, calls the six representative
  Day 1 tools, checks empty effects, proves post-stop failure, and always cleans
  up hosted processes.
- `apps/portfolio-risk-workbench/app.py` and its manifest add only the missing
  hosted adapter bindings for `portfolio.input.preview` and
  `provider.catalog.list`; parsing, provider state, analytics, and business
  logic remain package-owned.
- The Makefile, Day 1 CI workflow, lifecycle status/current workplan, README,
  manifest digests, runtime-bootstrap tests, and preparation harness are aligned
  to the final deterministic gates.

## Tests executed

- `make preflight` — PASS before edits.
- Pre-edit `make verify-day1` — PASS, establishing the regression baseline.
- Focused final journey — PASS, 2 tests.
- Focused runtime/journey/architecture integration set — PASS, 35 tests.
- Workbench regression — PASS, 71 tests.
- `make verify-day1` — PASS: 37 Day 0 architecture, 22 contract/domain, 22
  planning, 27 data, 14 capability, 14 agent, 71 application, 15 integration,
  6 journey, 6 research, 29 Day 1 architecture, 14 analytics, and the combined
  28 Day 1 capability/agent tests passed; manifest and whitespace checks passed.
- `make demo-day1-headless` — PASS twice consecutively at the configured
  persistent external Day 1 data root. Confirmation `created` outcomes are
  canonicalized in evidence, and every artifact remained byte-for-byte stable.
- `make servicefabric-day1-smoke` — PASS using the exact default command after
  the pinned, hash-locked runtime bootstrap. Text Utility passed first; the
  Workbench packaged resources and all six representative calls passed with
  empty effects; the post-stop call failed as required; cleanup completed.
- `make verify-day0` — PASS after the integrated PYTHONPATH exposed the additive
  analytics package required by the accepted capability imports: 37
  architecture, 22 contract/domain, 22 planning, 27 data, 14 capability, 14
  agent, 71 application, 15 integration, and 6 journey tests passed; manifest
  and whitespace checks passed.
- `git diff --check` — PASS after this handoff update.

## Evidence produced

External deterministic evidence is beneath
`PORTFOLIO_RISK_DATA_ROOT/day1-workbench`: `input-preview.json`,
`confirmed-portfolio-snapshot.json`, `snapshot-comparison.json`,
`provider-catalogue.json`, `risk-analysis.json`, `scenario-analysis.json`,
`agent-timeline.json`, `report.md`, `report.html`, and
`evidence-manifest.json`. The manifest carries SHA-256 digests for every sibling
artifact, the two profiles, synthetic disclosure, pending human-review state,
empty effects, and the prohibited effect list.

Hosted evidence additionally proves the pinned Day 0/Text Utility baseline,
ordinary non-editable installation of all six reviewed local packages,
digest-matching packaged templates/CSS, disabled provider catalogue, fixed
query manifests, tail warning, effect-free analytics/report calls, and
capability unavailability after Workbench stop.

## Deviations

- The final authority added two thin Workbench action adapters after specialist
  merge because the required ServiceFabric smoke tool IDs had no hosted route.
  This is a cross-package interface/packaging correction only; it delegates to
  the accepted data services and adds no calculation or provider logic.
- The first isolated smoke bootstrap attempt was blocked by sandbox DNS. The
  same hash-locked command was rerun with approved network/process permission.
  During smoke development, resource verification and CLI-result parsing were
  corrected before the exact final command passed.
- The standard candidate-commit step is intentionally omitted because the
  assignment explicitly prohibited commits.
- The exact first `make verify-day0` run reached the integration suite and
  exposed that its legacy PYTHONPATH omitted `risk_analytics`. The shared test
  harness now exposes the accepted additive package to Day 0 regressions; no
  Day 0 contract, fixture, behavior, dependency lock, or evidence was changed.

## Blockers

No implementation or deterministic integration blocker remains. Day 1 human
soft QA is intentionally pending and is not an automated-test blocker or pass.

## Limitations

- Browser, keyboard, screen-reader, and visual review require an identified
  human reviewer under the queued soft-QA protocol.
- Historical analytics are descriptive and sample-bound; fixed scenarios are
  linear and do not price instruments or recommend actions.
- Reports are local Markdown/HTML review artifacts. PDF and publication are
  unavailable.
- External providers/LLMs, arbitrary SQL, notebook execution, broker/account
  connectivity, orders, trades, hedges, optimization, and rebalancing remain
  absent. Personal portfolio data remains only in the external local data root.

## Rollback

Revert only the final uncommitted integration-owned files and the two bounded
Workbench adapter/manifest changes to accepted head `283e3a4`. External demo
and hosted-runtime directories may be removed independently because they are
derived local evidence. Do not change immutable portfolio records in place,
the `day0-complete` evidence, or `vendor/servicefabric/**`. To roll back merged
Day 1 product work, revert accepted candidates in reverse integration order as
recorded in `config/agent/day1/waves.json`.

## Pull request 16 CI repair addendum

- Lane and branch: integration authority on `integration/day1`.
- Repair base: `1994a1a9f610bdb94e0bd2fceea35dacb62981fb`.
- Implementation head: `c7857ae` (`fix(ci): expose risk analytics to day0
  workflow`); this handoff update is the documentation-only successor.
- Changed paths: `.github/workflows/day0.yml` and
  `tests/architecture/test_day1_runtime_boundaries.py`, plus this exact handoff.
- Failure evidence: PR 16 run `29923176407`, job `88933506974`, passed 228
  tests and manifest validation before the Day 0 headless journey failed with
  `ModuleNotFoundError: No module named 'risk_analytics'`.
- Fix: both Day 0 workflow execution blocks now expose the additive
  `packages/risk_analytics/src` tree; an architecture test prevents either
  workflow path from silently dropping it.
- Tests executed: the exact failed headless journey — PASS with all six
  artifacts; focused runtime-boundary tests — PASS, 9 tests; `make verify-day0`
  — PASS; `make verify-day1-current` — PASS; `git diff --check` — PASS.
- Evidence produced: synthetic Day 0 repair-run artifacts under
  `/tmp/servicefabric-day0-ci-fix/day0-monitoring`; no repository data artifact
  was added.
- Deviations: the local `gh` credential was expired, so failure metadata and
  logs were read through the connected GitHub integration and public Actions
  API. This did not affect repository verification.
- Blockers: none for the implementation. Publishing and remote recheck remain
  the next actions.
- Limitations: local verification reproduces the failing command and all
  deterministic repository gates; GitHub-hosted runner success is confirmed
  only after the pushed commit completes CI.
- Rollback: revert `c7857ae` and its documentation-only successor; do not
  change `vendor/servicefabric/**` or delete immutable repository evidence.
- Recommended next action: push the two focused commits, watch all PR 16
  checks, and inspect any residual failure before declaring CI green.

## Exact Part 6/6 entry point

An identified human reviewer starts Part 6/6 at
`docs/workplans/day-1/soft-qa.md` on the exact reviewed working tree based on
`283e3a4`, after confirming `make verify-day1`, `make demo-day1-headless`,
`make servicefabric-day1-smoke`, `make verify-day0`, and `git diff --check`.
The reviewer must inspect both profiles and record independent browser,
keyboard, disclosure, invalid-input, snapshot, provider-rights, analytics-
limitation, report, timeline, and no-effect evidence. Only that separate human
decision may change `soft_qa` from `queued`; this handoff does not claim it
passed.
