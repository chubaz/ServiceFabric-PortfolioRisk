# Day 2–3 integration handoff — Part 2 activation

- Lane: `integration`
- Branch: `integration/day2-3`
- Base: `day1-complete` (`627a08b`)
- Completed Part 1 head: `0b12e198abc1713f0a286aee817491ffbfe15b17`
- Part 2 migration head: uncommitted by instruction
- Status: Part 1 complete; Part 2 in progress; Part 3 queued; no final QA claim

## Three-part migration

The former four-phase programme is superseded by `3-part-v1`. Lifecycle state
now activates `D23-PART-2`, while the completed Part 1 workplan, immutable
evidence, deterministic demo, and local process-host smoke record remain
preserved. The retired future Phase 2–4 workplans are marked superseded and
contain no completed evidence.

The active manifest now has only `integration`, `monitoring-core`, and
`experience`, in the order `monitoring-core` -> `experience` -> `integration`.
It uses only explicit `allowed_directories` and `allowed_files`; the existing
strict lane checker now validates that shape and rejects ambiguous or
overlapping allowances. The former lane manifest is archived only to verify
the completed Part 1 diff at its pinned head.

Part 2 contract records freeze portfolio data context, explicit-identity local
events, typed immutable monitoring policies, and deterministic point-in-time
replay evaluation. No product behavior, dependency, provider, LLM, scheduler,
policy expression language, fuzzy matching, look-ahead, broker, order, trade,
or rebalance effect is activated by this migration.

## Changed paths

- Part 2 migration control plane: `AGENTS.md`, `Makefile`,
  `.github/workflows/day23.yml`, `config/agent/day23/**`,
  `docs/workplans/current.md`, the Day 2–3 workplans, the four Part 2 contract
  records, the existing lane checker, and its architecture tests.
- No application, package, connector, fixture, dependency, or
  `vendor/servicefabric/**` path changed.
- Historical Part 1 record follows.
- Root integration surfaces: `Makefile` and `README.md`.
- Lifecycle and CI: `.github/workflows/day23.yml`,
  `config/agent/day23/status.json`, `config/agent/day23/phases.json`,
  `docs/workplans/current.md`, and the Phase 1 workplan status.
- Integration evidence and tests:
  `scripts/day23/run_phase1_demo.py`,
  `scripts/day23/servicefabric_phase1_smoke.sh`,
  `tests/journeys/test_d23_phase1_data_plane.py`, and the Day 2–3
  control-plane tests.
- Generated contract evidence: all canonical JSON Schema snapshots beneath
  `data/schemas/day23/**`.
- Hosted interface closure:
  `apps/portfolio-risk-workbench/app.py` and its reviewed source hash in
  `apps/portfolio-risk-workbench/servicefabric-package.json`.
- CI repair:
  `scripts/day1/check_preparation.py`,
  `tests/application/test_workbench.py`, and all 26 explicitly added generated
  `data/schemas/day23/**` snapshots.
- This exact handoff file.

The CI repair preserves Day 1 as a regression baseline while allowing a
reviewed `D23-*` workplan to own the current lifecycle pointer. It also restores
the generated schema evidence hidden by the broad root data-ignore rule and
keeps the hosted JSON preview adapter aligned with its reviewed application
hash.

## Specialist handoffs reviewed

- `data-platform`: accepted. The package supplies immutable local CSV/Parquet
  preview and confirmation, normalized Parquet, curated DuckDB views, quality
  reports, explicit crosswalks, fixed manifests, and point-in-time filtering.
  Integration generated and included all 26 canonical
  `data/schemas/day23/**` review snapshots by explicitly adding the reviewed
  outputs under the existing broad data-ignore rule; a closure test regenerates
  and compares them byte-for-byte.
- `experience`: accepted. The Workbench keeps human-readable import, dataset,
  quality, crosswalk, and fixed-query screens plus effect-free action routes.
  Integration corrected the hosted `data.import.preview` interface from a
  browser-only multipart signature to a bounded typed JSON action signature;
  browser upload routes and package-owned data behavior are unchanged.

## Tests executed

- `make preflight` — PASS.
- Focused data and application baseline — PASS, 106 tests.
- Focused closure coverage — PASS, 100 tests.
- `tests/journeys/test_d23_phase1_data_plane.py` — PASS.
- `make verify-d23-phase1` — PASS.
- `make demo-d23-phase1` — PASS.
- `make servicefabric-d23-phase1-smoke` — PASS.
- `make verify-day1` — PASS.
- `make verify-day0` — PASS.
- Application manifest hash check — PASS.
- Exact PR-head reproduction — FAIL as expected with three failures: stale
  application source hash, Day 1 current-workplan mismatch, and zero committed
  Day 2–3 schema snapshots.
- Focused CI repair regression — PASS, 4 tests.
- `make demo-day0-headless` with
  `PORTFOLIO_RISK_DATA_ROOT=/tmp/servicefabric-pr17-ci-day0` — PASS against a
  fresh CI-equivalent data root.
- `make demo-day1-headless` — PASS.
- `git diff --check` — PASS.

## Evidence produced

The deterministic demo writes these siblings beneath
`PORTFOLIO_RISK_DATA_ROOT/day23-phase1`:

- `provider-register.json`
- `import-previews.json`
- `import-confirmations.json`
- `dataset-snapshots.json`
- `quality-reports.json`
- `identifier-crosswalk.json`
- `fixed-query-results.json`
- `point-in-time-proof.json`
- `evidence-manifest.json`

The evidence manifest digests every other sibling artifact. Mutable landing,
normalized, curated, manifest, quality, and evidence zones remain outside Git.
The journey proves all three explicit synthetic previews and confirmations,
immutable normalized Parquet, curated DuckDB views, non-blocking quality
reports, a date-effective PERMNO/GVKEY crosswalk, every fixed manifest,
`available_at <= as_of` exclusion, no ticker guess, no arbitrary SQL, disabled
external providers, and empty effects.

The local ServiceFabric smoke calls `data.provider.catalog`,
`data.import.preview`, `data.dataset.list`, and `data.query.fixed`; each returns
empty effects. It also verifies external providers remain disabled, the
post-stop call fails, and the hosted process record and operating-system
process are cleaned up. CI deliberately runs deterministic verification and
the demo only; it does not run or claim local process-host smoke evidence.

## Deviations

One cross-lane interface correction was required after specialist integration:
the declared `data.import.preview` ServiceFabric capability pointed at a
multipart-only browser action that the canonical JSON invocation gateway could
not call. The narrow typed JSON adapter change is recorded above and delegates
to the accepted `ResearchDataWorkspace`; it adds no risk calculation, provider
logic, or Phase 2 behavior. Review follow-up narrowed that text-based JSON
adapter to CSV filenames; binary-safe Parquet preview remains available only
through the existing browser multipart and CLI paths.

Review follow-up also generated and included the 26 contract snapshots that
the data-platform handoff had produced but the broad root data-ignore rule hid.
The rule remains unchanged in the candidate commit because `.gitignore` has no
Day 2–3 lane owner; the reviewed schema files are tracked explicitly.
The Day 1 lifecycle checker now validates all Day 1 status and boundary
requirements while deferring only the obsolete Day 1 current-pointer
comparison after a reviewed Day 2–3 workplan is active.

No provider was enabled or contacted. No arbitrary SQL, notebook execution,
broker connection, order, trade, rebalance, live portfolio effect, dependency,
vendor edit, or Phase 2 implementation was added.

## Blockers

None for Phase 1 closure.

## Limitations

- Phase 1 remains local-only, synthetic in the deterministic journey, and
  single-writer.
- The hosted JSON preview action accepts bounded text CSV content; browser
  multipart upload remains the reviewed path for bounded CSV/Parquet bytes,
  and the CLI remains the large-file path.
- Licensed local exports still require explicit rights and publication review.
- Contract snapshots are generated review evidence; edits must be made in the
  Pydantic contracts and regenerated, not changed by hand.
- The repository's saved GitHub CLI token was expired during CI diagnosis.
  Public GitHub check metadata and an exact local clone of PR head `225eb6a`
  were used to identify and reproduce the failures.
- The default persistent Day 0 demo root contained a conflicting immutable
  artifact from an earlier local run. It was preserved; the demo passed against
  the fresh temporary root shown in the test record.
- A proposed local `.gitignore` exception is intentionally excluded from the
  candidate commit after the lane-path audit identified that file as unowned in
  the frozen Day 2–3 lane manifest.

## Rollback

Revert only the Part 2 activation edits to restore the prior Phase 2 queued
pointer and lane manifest. Preserve the completed Part 1 commit, archived
verification manifest, immutable snapshots, and external `day23-phase1`
evidence. Rollback requires no application, package, connector, fixture, or
`vendor/servicefabric/**` edit.

## Recommended next action

Issue the two fresh specialist handoffs. Integrate `monitoring-core`, then
`experience`, then run the integration, journey, deterministic demo, and local
process-host smoke gates before considering Part 2 complete. Part 3 remains
queued until a separate human QA and release decision.
