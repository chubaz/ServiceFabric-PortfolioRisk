# Day 2–3 Phase 1 data-platform handoff

- Lane: `data-platform`
- Branch: `feature/day2-data-platform`
- Base: `day1-complete` (`627a08b`)
- Head: working tree based on `d29f085`; no candidate commit was requested or created

## Changed paths

- `packages/risk_data/**`
- `data/fixtures/synthetic/**`
- `data/schemas/day23/**`
- `tests/data/test_day23_research_data_plane.py`
- `docs/handoffs/day-2-3/data-platform.md`

No Workbench, root dependency, Makefile, CI, shared control-plane, or
`vendor/servicefabric/**` path was changed.

## Delivered

- Frozen Pydantic contracts and generated JSON Schemas for provider, rights,
  dataset/revision, source, mapping/transformation, point-in-time, preview and
  confirmation, quality, crosswalk, fixed query, and research snapshot state.
- Local-only CSV and Parquet preview/confirmation service with absolute-path,
  repository-boundary, digest, rights, publication, mapping, and explicit
  confirmation gates.
- Immutable external `landing`, `normalized`, `curated`, `manifests`,
  `quality`, and `evidence` zones beneath `PORTFOLIO_RISK_DATA_ROOT` or the
  explicit CLI data root.
- Normalized Parquet outputs for `security_master`, `daily_market`,
  `fundamentals_annual`, and `identifier_crosswalk`; immutable DuckDB snapshots
  exposing all required curated views.
- Fixed query manifests with structured parameters, required point-in-time
  cutoffs, `available_at <= as_of`, bounded limits, deterministic columns, and
  snapshot/evidence identifiers. No arbitrary SQL API is exposed.
- Explicitly disabled network posture: provider definitions cannot enable a
  network, and the workflow contains no network client or connection path.
- CLI commands: `preview-local-export`, `confirm-local-export`,
  `list-research-datasets`, `run-fixed-query`, and `show-data-quality`.
- Three fictional, explicitly synthetic text fixtures and configurable mapping
  manifests. Parquet is generated only in temporary test storage.

## Tests executed

- `make preflight` — PASS
- Baseline `make test-d23-data` — PASS, 27 tests
- Focused `pytest tests/data/test_day23_research_data_plane.py -q` — PASS,
  25 tests
- Final `make test-d23-data` — PASS, 52 tests
- Existing `make test-data` — PASS, 52 tests
- Contract/schema compile and generation check — PASS
- `git diff --check` — PASS

## Evidence produced

- Generated review schemas under `data/schemas/day23/**`.
- Focused acceptance tests cover CSV and Parquet; preview-only behavior; source
  digest and explicit confirmation; rights/publication/path gates; missing
  availability and no-look-ahead; duplicates/invalid dates/missing identifiers;
  unit and sign-normalization evidence; raw versus valuation prices;
  idempotent import and corrected revisions; date-effective/open-ended links;
  overlap rejection; fixed-only queries and limits; CLI workflows; no network;
  and the public-repository data boundary.
- Each confirmed external snapshot writes an immutable snapshot manifest,
  source/mapping/transformation evidence, quality report, and (when applicable)
  crosswalk snapshot.

## Review defects resolved

- Mapping, dataset, provider, revision, transformation, and report identifiers
  are path-safe; generated paths are resolved and checked beneath the external
  data root, and quality filenames are digest-derived.
- Quality-report identity includes dataset, revision, source, and mapping, so a
  new revision of identical source bytes creates a distinct immutable report.
- Non-nullable mappings now reject missing values, and invalid non-nullable
  values are blocking.
- Naive availability timestamps are rejected rather than assigned an inferred
  timezone.
- Provider numeric missing codes apply only to numeric mappings, preserving
  legitimate string attributes such as ticker `C`.
- The Day 1 `FixedQueryManifest` remains the package-level public contract; the
  Phase 1 model is exposed separately as `ResearchFixedQueryManifest`.
- Explicitly imported security-master rows are merged with derived identifiers
  and returned by the `security-master` fixed query.

## Deviations

- None from the Phase 1 scope. No provider network was accessed, no dependency
  was added, and no binary dataset or database was written to Git.

## Blockers

- The integration-owned root `.gitignore` currently ignores `data/*`. The
  generated `data/schemas/day23/**` files exist in this worktree but do not
  appear in ordinary `git status`; integration must either force-add those
  reviewed schemas or add an integration-owned allow rule before accepting a
  candidate commit.

## Limitations

- Phase 1 is local-only and intentionally accepts only CSV and Parquet.
- Imports are designed for one local writer at a time; cross-process locking is
  deferred.
- Provider-specific download, authentication, arbitrary SQL/expression input,
  notebooks, URLs, archives, spreadsheets, databases, and web filesystem paths
  remain prohibited.

## Rollback

Remove the new Phase 1 files under the changed paths and restore the modified
`risk_data` public exports, CLI, serialization helper, and synthetic fixture
README. External data-root snapshots are immutable local artifacts and can be
removed separately by their owner; rollback does not require editing them.

## Recommended next action

Integration should review the generated schemas and public contracts, resolve
their existing `data/*` ignore rule for `data/schemas/day23/**`, then run
`make verify-d23-phase1` before accepting a focused candidate commit.
