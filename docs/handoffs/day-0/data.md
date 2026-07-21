# Day 0 Handoff

- Lane: Data
- Branch: `feature/day0-data`
- Base: `day0-prepared`
- Head: `c05e48c` (working tree changes are intentionally uncommitted)
- Status: Wave 0C data scope complete pending integration review

## Objective

Materialize the deterministic, explicitly synthetic Day 0 data flow from
schema-validated provider rows through normalized records into local-only
Parquet, DuckDB views, immutable domain snapshot manifests, and a deterministic
ingestion/anomaly evidence bundle.

## Changed paths

- `packages/risk_data/**`
- `connectors/**`
- `tests/data/**`
- `docs/handoffs/day-0/data.md`

## Contracts consumed

- `risk_domain.MarketObservation` and `risk_domain.FundamentalObservation`
- `risk_domain.InstrumentIdentifier`, `QualityFlag`, and `SourceReference`
- `risk_domain.DatasetFile`, `DatasetProvenance`, and canonical
  `DatasetSnapshot`
- canonical digest helpers from `risk_domain.digests`

## Commands executed

- `make preflight` (environment check attempted)
- `make test-data`
- `git diff --check`

## Tests and results

Focused data tests cover deterministic output, disabled WRDS stubs, explicit
missing observations (including empty query coverage), duplicate detection,
stale flags, identifier and ISO 4217 currency validation, synthetic provenance
enforcement, domain mapping, actual Parquet output, DuckDB views, immutable
artifact manifests, CLI execution, and the external temporary-directory write
boundary. `make test-data` passed: 15 tests in 1.58s.

Wave 0C adds a caller-timestamped, immutable evidence bundle containing the
anomaly query digest, the ingestion run and dataset snapshot manifests,
verified artifact digests, validation evidence, ALPHA anomaly observations and
quality flags, plus a clearly fictional seeded ALPHA news event. The bundle
contains no provider credentials or endpoints.

## Evidence

- Fixed fixture seed `20260721`; persisted fixtures use fictional `ALPHA`,
  `BETA`, and `GAMMA` symbols with UTC timestamps and explicit synthetic
  metadata.
- Five daily prices per instrument support return calculations. The final
  `ALPHA` daily return is exactly -12%; `BETA` and `GAMMA` retain normal-range
  movements.
- Validation evidence records 25 input rows, 21 accepted rows, 4 rejected
  candidates, and one each of duplicate, missing identifier, stale observation,
  and missing value. Manifests retain source and artifact SHA-256 digests.
- The pipeline writes only beneath `PORTFOLIO_RISK_DATA_ROOT` (or the explicit
  `--output` root) and rejects repository-local output and pre-existing target
  artifacts.
- `python -m risk_data.cli export-evidence --output ROOT --generated-at
  TIMESTAMP` writes `manifests/evidence-bundle.json` only after the required
  ingestion artifacts have been verified.
- WRDS adapters immediately raise `ConnectorDisabledError`; they contain no
  network client or provider credential handling.

## Deviations

The Day 0 synthetic provider is intentionally in-memory. Its deliberate invalid
candidates are rejected before Parquet materialization solely to demonstrate
quality evidence.

The repository still records Wave 0B as active and has no checked-in Wave 0C
workplan; this Wave 0C data work follows the explicit task direction.

## Blockers

`make preflight` remains unavailable because `gh` reports the configured GitHub
token has expired during `env-check`. This is unrelated to the data
implementation.

## Limitations

No real network access, provider authentication, licensed data, cache, broker
connectivity, or mutable-update path exists. Artifacts are immutable at their
target paths; a new root or revision is needed for a subsequent ingestion.
The CLI uses the fixed fixture timestamp only when `--generated-at` is omitted;
callers should supply it for reviewable evidence generation.

## Rollback

Delete the explicitly selected external data root if it was created for a local
run, then remove the listed uncommitted data-lane paths or revert the future
focused integration commit.

## Recommended next action

Run `make test-data` and `git diff --check` in integration, then exercise
`python -m risk_data.cli ingest-synthetic --output ROOT` with an external data
root before accepting the focused data-lane change.
