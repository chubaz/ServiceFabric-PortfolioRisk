# Day 2–3 Part 2 monitoring-experience handoff

## Lane and branch

- Lane: `experience`
- Branch: `feature/day23-monitoring-experience`
- Merge authority: none; this specialist stops without merge

## Base and head

- Base: `16238339c82324fb455f9eac8293db48d7aa1ad5`
- HEAD: `16238339c82324fb455f9eac8293db48d7aa1ad5`
- Delivery state: uncommitted working-tree changes, as requested

## Changed paths

- `apps/portfolio-risk-workbench/app.py`
- `apps/portfolio-risk-workbench/monitoring_service.py`
- `apps/portfolio-risk-workbench/presentation.py`
- `apps/portfolio-risk-workbench/risk-package-lock.json`
- `apps/portfolio-risk-workbench/servicefabric-package.json`
- `apps/portfolio-risk-workbench/static/workbench.css`
- `apps/portfolio-risk-workbench/templates/base.html`
- `apps/portfolio-risk-workbench/templates/monitoring_*.html`
- `tests/application/test_monitoring_experience.py`
- `docs/handoffs/day-2-3/monitoring-experience.md`

No root dependency, Makefile, CI, shared wave-state, monitoring-core package, or
`vendor/servicefabric/**` path was changed.

## Delivered behavior

- Added the visible Monitoring navigation section: Context, Events, Policies,
  Runs, Replay, and Evaluation.
- Added semantic context preview/confirmation/list/detail workflows. Blocking
  unmapped, ambiguous, and unavailable required market-data states cannot be
  confirmed.
- Context previews now resolve the selected Part 1 research snapshot, exact
  market/fundamental revisions, fixed-query observations, and immutable
  date-effective crosswalk. Unknown or mismatched revisions are rejected, and
  a portfolio snapshot newer than `as_of` is never backdated.
- Added bounded browser-byte CSV/Parquet event import, preview, explicit
  confirmation, immutable snapshot display, separate event/availability times,
  amendments/retractions, rights/publication disclosures, and private-text
  redaction.
- Added immutable fixed-field monitoring policy preview/confirmation. No
  expression, code, formula, SQL, or scheduler field exists.
- Added contextual runs through the registered four-role orchestrator, with
  capability receipts, findings, draft alert, evidence, limitations, pending
  human review, and empty effects. `run_at` cannot precede the confirmed
  context and policy metrics are derived from context observations rather than
  form-supplied smoke values.
- Added deterministic replay and evaluation with pinned contexts/revisions,
  reviewed cadence and outcome-label snapshots, no look-ahead, one-to-one
  matching, sample warnings, and `Not available` rendering for undefined
  metrics. Each step selects the latest eligible return from the pinned market
  revision, replay is capped at 366 steps before materialization, and outcomes
  are loaded from the immutable reviewed fixture before execution rather than
  synthesized from generated alerts.
- Added local semantic HTML and Markdown monitoring/replay reports. PDF and
  publication controls remain unavailable; personal-profile reports remain
  local-private.
- Added the requested typed APIs and seven manifest-declared ServiceFabric
  action paths. There is no generic capability invocation endpoint.
- Updated application source hashes and the package lock to the integrated
  monitoring-core package digests.

## Tests executed

- `make preflight` — PASS. The first sandboxed attempt could not reach the
  pinned package index; the approved rerun completed successfully.
- `DAY23_VENV=/home/lorenzoccasoni/servicefabric-lab/state/venvs/day23 make test-d23-monitoring-experience`
  — PASS, `88 passed`.
- Focused `tests/application/test_monitoring_experience.py` — PASS, `6 passed`.
- Python compile check for `app.py`, `monitoring_service.py`, and
  `presentation.py` — PASS.
- `scripts/day0/update_manifest_hashes.py
  apps/portfolio-risk-workbench/servicefabric-package.json --check` — PASS.
- `git diff --check` — PASS.

Coverage includes semantic context flow and blocking mappings; bounded event
upload, `available_at`, amendment/retraction, and network prohibition; fixed
policy fields and absent executable fields; contextual four-agent runs and
draft alerts; replay, defined and undefined metrics, sample warnings, matching
methodology, and reports; research and local-private personal profiles; empty
effects; absence of server paths, provider enablement, generic invocation,
network endpoints, SQL, notebook execution, broker/order/trade/rebalance, and
optimization paths; existing Day 0, Day 1, and Part 1 application regressions;
and manifest completeness/hashes.

## Evidence produced

- Application test output: `88 passed`.
- Focused Part 2 experience test output: `6 passed`.
- Manifest hash verification: PASS.
- Application package lock matches the integrated local package trees.
- Review-remediation evidence covers rejection of future portfolio snapshots,
  unknown market/crosswalk revisions, runs predating context, bounded replay,
  actual revision-derived replay values, and non-circular immutable outcomes.
- All hosted Part 2 action results are human-review-required and effect-free.

## Deviations

- No functional deviation from the Part 2 workplan or frozen contracts.
- Hosted smoke actions import the reviewed synthetic Part 1 fixtures through
  the governed local data plane; portfolio prices, context observations,
  mappings, replay returns, and outcome labels are resolved from those
  immutable records rather than manufactured by route functions.
- Browser event uploads are bridged to the core path-based local data-plane
  contract through private content-digested local staging. No server path is
  accepted from or returned to the user.

## Blockers

- None.

## Limitations

- Cadence remains metadata and replay is explicitly invoked; there is no
  background scheduler.
- Event provider access remains local-only and network-disabled.
- Reports are local HTML/Markdown review artifacts only.
- The current Part 1 fixed-query API queries the active research snapshot.
  Monitoring therefore rejects a selected historical aggregate snapshot when
  it is no longer the active fixed-query snapshot instead of substituting data
  from another revision.
- Alert review remains analytical human review and never authorizes a trade or
  portfolio effect.
- Part 3 human QA, release decision, merge, and publication are not claimed.

## Rollback

Discard only the uncommitted paths listed above. No migration is required;
runtime artifacts are immutable local files beneath the configured external
data root and no repository data fixture was changed.

## Recommended next action

Integration authority should review the working-tree diff and handoff, rerun
the Part 2 integration and journey gates, perform Part 3 human QA, and decide
whether to create and accept a candidate commit. Do not merge based on this
specialist handoff alone.
