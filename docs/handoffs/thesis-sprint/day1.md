# Thesis Sprint Day 1 specialist handoff

## Lane and branch

- Lane: `day1`
- Branch: `feature/thesis-day1`
- Experiment baseline tag: `day23-complete`
- Lane base: reviewed control-plane addition commit
  `aaad2c5fb6f13286c9c1478f39c6e10a5a567cf6`
- Working-tree HEAD: `aaad2c5fb6f13286c9c1478f39c6e10a5a567cf6`
- Candidate state: uncommitted by explicit instruction; integration must
  record the exact lane base and candidate head before running the commit-range
  lane gate.

## Changed paths

- `examples/portfolio-risk-thesis/**`: package metadata, documentation,
  reviewed manifests, three fixed-quantity portfolios, immutable Pydantic
  contracts, read-only Parquet adapters, deterministic replay clock/channel,
  canonical snapshot/exposure builder, CLI, fixture generator, digest
  validator, and external-root demo.
- `data/fixtures/synthetic/thesis-day1/**`: deterministic `market.parquet`,
  `events.parquet`, and `fixture-manifest.json`.
- `tests/thesis/**`: focused contract, adapter, replay, portfolio, snapshot
  builder, reproducibility, safety, and output-boundary tests.
- `docs/handoffs/thesis-sprint/day1.md`: this handoff.

## Tests executed

- `make preflight`: PASS.
- `make thesis-env`: PASS.
- `make test-thesis-day1`: PASS (`20 passed`).
- Thesis Sprint control-plane suite: PASS (`16 passed`).
- Existing canonical capability tests for snapshot creation and exposure
  summary: PASS (`2 passed`, `2 deselected`).
- Fixture digest validator: PASS.
- All four CLI command help surfaces: PASS.
- End-to-end CLI validation, portfolio listing, five-day replay, and step
  inspection: PASS.
- `make demo-thesis-day1` with an explicit external Day 1 state root: PASS.
- Uncommitted Day 1 allowlist audit: PASS (`34` files, all within lane).
- Added text whitespace and nondeterministic/network API audits: PASS.
- `git diff --check`: PASS.
- Pinned `vendor/servicefabric` status: clean.

## Evidence produced

- Canonical SHA-256 fixture digests in `fixture-manifest.json` and
  `data/dataset_manifest.yaml`.
- Fixture revision `2026-07-28.2`; every market and event record carries and
  validates its own canonical content digest, revision, units, quality state,
  limitations, source, synthetic disclosure, and evidence reference.
- `1040` deterministic market rows: exactly `130` ordered business-day
  observations for each of eight fictional instruments.
- `24` deterministic fictional events, including a delayed-availability event
  excluded until the following reviewed replay step.
- Five deterministic daily steps for each of three fixed-quantity portfolios,
  with stable run IDs, point-in-time evidence, immutable canonical
  `PortfolioSnapshot` and `ExposureSnapshot` outputs, and reconciled NAV and
  weights.
- All generated demo/replay output is constrained to an explicit absolute
  path equal to or beneath the configured external `THESIS_DATA_ROOT`.

## Deviations

The integration-owned Thesis `PYTHONPATH` omits `packages/risk_planning/src`,
although importing the canonical `risk_capabilities` registry requires it.
The example adds only that repository-local import dependency before importing
the canonical registry; snapshot and exposure calculations still use the
registered canonical invocation path without an alternate implementation.

Review corrections incorporated: output containment now uses
`THESIS_DATA_ROOT`; row provenance is immutable and content-addressed;
`review_time` is parsed from the experiment manifest and contributes to replay
identity; and partial-day specifications emit only ticks satisfying
`start <= as_of <= end`, with incompatible intervals rejected.

## Blockers

There is no candidate commit SHA because the specialist was explicitly told
not to commit. The commit-range lane checker therefore cannot validate the
uncommitted candidate. The current modified/untracked path set has been
reviewed against the Day 1 allowlist; integration must create or identify the
candidate commit and run the authoritative lane gate.

## Limitations

The data and results are entirely synthetic and are not investment advice.
Day 1 provides only NAV, position/cash weights, and exposure from the existing
canonical capabilities. It intentionally provides no returns, volatility,
drawdown, tail risk, findings, agents, LLMs, architecture comparison,
historical evaluation, external provider, streaming infrastructure, trading,
rebalancing, or portfolio mutation effect. Replay is deterministic,
in-process, daily, and bounded to a five-day smoke interval.

## Rollback

Remove only the added paths under `examples/portfolio-risk-thesis/**`,
`data/fixtures/synthetic/thesis-day1/**`, and `tests/thesis/**`, and restore
this exact handoff from the lane base. Do not alter completed lifecycle
records or the pinned ServiceFabric submodule.

## Recommended next action

Review the uncommitted specialist diff, create the focused candidate commit,
record its SHA as the candidate head, run the authoritative lane check from
`aaad2c5fb6f13286c9c1478f39c6e10a5a567cf6` through that exact head, then run
`make verify-thesis-day1 THESIS_DAY1_LANE_HEAD=<candidate-head>` on the
integration checkout. Stop for explicit human acceptance without merging
specialist work directly.
