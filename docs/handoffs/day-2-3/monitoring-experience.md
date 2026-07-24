# Day 2–3 Part 2 monitoring-experience handoff

## Lane and branch

- Lane: `experience`
- Branch: `feature/day23-monitoring-experience`
- Merge authority: none; this specialist stops without merge

## Base and head

- Base: `16238339c82324fb455f9eac8293db48d7aa1ad5`
- Original candidate: `5f159c7ed61223e44b7331fcdfb56f78e1db9489`
- Rejected diagnostic base: `ba6aa12`
- HEAD: correction candidate commit follows this handoff update
- Delivery state: compliant hosted-package staging candidate ready for a fresh
  integration decision

## Changed paths

- `apps/portfolio-risk-workbench/app.py`
- `apps/portfolio-risk-workbench/monitoring_service.py`
- `apps/portfolio-risk-workbench/stage_package.py`
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

The correction removes the rejected tracked duplicates. The staging utility
reads only the four allow-listed canonical files under
`data/fixtures/synthetic/day23/**`, writes them to an ephemeral package tree,
and regenerates a complete digest-locked manifest there. No staged resource is
written back into the repository.

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
- Corrected the hosted application boundary so context setup and replay outcome
  loading resolve only package-relative resources in the staged tree. Neither
  path depends on repository-relative `data/fixtures/**` at runtime.
- Added `stage_package.py`, which rejects symlinks, path escape, missing
  canonical inputs, existing output trees, and undeclared staged files.

## Tests executed

- `make preflight` — PASS for the correction. The original candidate's first
  sandboxed attempt could not reach the pinned package index; its approved
  rerun also completed successfully.
- `DAY23_VENV=/home/lorenzoccasoni/servicefabric-lab/state/venvs/day23 make test-d23-monitoring-experience`
  — PASS, `89 passed`.
- Focused `tests/application/test_monitoring_experience.py` — PASS, `7 passed`.
- Staged-package host-shaped regression — PASS. It stages from the canonical
  fixture root, verifies staged digests, imports the Workbench from a temporary
  `hosted-applications/.../runtime` tree, and exercises all seven Part 2
  actions without a repository data tree.
- `stage_package.py` smoke check — PASS. The generated manifest passes
  `update_manifest_hashes.py --check` and includes exactly the four staged
  monitoring resources.
- The integration-owned ServiceFabric process-host smoke was not rerun here;
  it still requires integration to invoke this staging contract before
  `apps install`.
- Python compile check for `app.py`, `monitoring_service.py`,
  `presentation.py`, and `stage_package.py` — PASS.
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

- Original candidate application test output: `88 passed`.
- Staged-package application test output: `89 passed`.
- Staged-package focused Part 2 experience test output: `7 passed`.
- Manifest hash verification: PASS.
- Generated staged manifest verification: PASS.
- Application package lock matches the integrated local package trees.
- Review-remediation evidence covers rejection of future portfolio snapshots,
  unknown market/crosswalk revisions, runs predating context, bounded replay,
  actual revision-derived replay values, and non-circular immutable outcomes.
- All hosted Part 2 action results are human-review-required and effect-free.

## Deviations

- No functional deviation from the Part 2 workplan or frozen contracts.
- Integration review found that the original hosted context action resolved
  repository-relative fixtures outside the built package. The rejected
  diagnostic correction proved the runtime fix but violated the sole canonical
  synthetic-fixture boundary. This candidate moves the copy operation to an
  explicit ephemeral staging step and preserves the boundary in Git.
- Hosted smoke actions import the reviewed synthetic Part 1 fixtures through
  the governed local data plane; portfolio prices, context observations,
  mappings, replay returns, and outcome labels are resolved from those
  immutable records rather than manufactured by route functions.
- Browser event uploads are bridged to the core path-based local data-plane
  contract through private content-digested local staging. No server path is
  accepted from or returned to the user.

## Blockers

- Integration must wire the staging command into its package-install path and
  feed the generated manifest into the reviewed ServiceFabric host bootstrap
  or equivalent approved package allowlist before `apps install`. A staged
  package installed into a runtime bootstrapped against the source manifest is
  correctly rejected as an unapproved package. The experience lane cannot
  modify the integration-owned Makefile, smoke script, or runtime bootstrap.

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

Revert only the staging candidate on top of `ba6aa12` (or omit the rejected
diagnostic commit when selecting the net diff). No migration is required;
staged package trees are ephemeral and no canonical repository data fixture was
changed.

## Recommended next action

Integration authority should invoke the staging contract before installing the
Workbench. The intended shape is:

```bash
stage_dir="$(mktemp -d)"
trap 'rm -rf "$stage_dir"' EXIT
"$DAY23_PYTHON" apps/portfolio-risk-workbench/stage_package.py \
  --source apps/portfolio-risk-workbench \
  --output "$stage_dir/portfolio-risk-workbench"
# Bootstrap/review the host against the staged manifest before installing it.
"$servicefabric" apps install "$stage_dir/portfolio-risk-workbench"
```

Then rerun the exact Part 2 verification sequence. Part 3 must not start until
integration independently confirms every Part 2 gate. Do not merge or advance
lifecycle state based on this specialist handoff alone.
