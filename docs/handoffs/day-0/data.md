# Day 0 Handoff

- Lane: Data
- Branch: `feature/day0-data`
- Base: `day0-prepared`
- Head: `c05e48c` (working tree changes are intentionally uncommitted)
- Status: complete pending integration review

## Objective

Provide provider-neutral ingestion contracts and deterministic in-memory,
explicitly synthetic fixtures without any real provider access or local data
storage.

## Changed paths

- `packages/risk_data/**`
- `connectors/**`
- `data/schemas/README.md`
- `tests/data/**`
- `docs/handoffs/day-0/data.md`

## Contracts consumed

- `risk_domain.MarketObservation` and `risk_domain.FundamentalObservation`
- `risk_domain.InstrumentIdentifier`, `QualityFlag`, and `SourceReference`
- canonical digest helpers from `risk_domain.digests`

## Commands executed

- `make preflight` (environment check attempted)
- `make test-data`
- `git diff --check`

## Tests and results

Focused data tests cover deterministic output, disabled WRDS stubs, explicit
missing observations (including empty query coverage), duplicate detection,
stale flags, identifier and ISO 4217 currency validation, synthetic provenance
enforcement, domain mapping, and the in-memory no-write boundary. `make
test-data` passed: 11 tests in 0.23s.

## Evidence

- Fixed fixture seed `20260721`; fixtures use fictional `NOVA`, `ORBIT`, and
  `QUASAR` symbols.
- Fixture timestamps are timezone-aware UTC values.
- Market fixture retains one missing value, one duplicate candidate, one stale
  value, and a final `NOVA` negative move from `101.25` to `57.00`.
- WRDS adapters immediately raise `ConnectorDisabledError`; they contain no
  network client or provider credential handling.

## Deviations

No persisted schema snapshot was generated: Wave 0A contracts are Python-first
and generated snapshots are integration-owned.

## Blockers

`make preflight` cannot complete locally because `gh` reports the configured
GitHub token has expired during `env-check`. This is unrelated to the data
implementation.

## Limitations

No real network access, provider authentication, Parquet, DuckDB, cache, or
other persistence exists. Duplicate candidates are retained for validation and
future rejection flow testing rather than silently overwritten.

## Rollback

Remove the listed uncommitted data-lane paths or revert the future focused
integration commit. No external state or data file is created.

## Recommended next action

Run `make test-data` and `git diff --check` in integration, then accept the
focused data-lane change after the preflight GitHub authentication is repaired.
