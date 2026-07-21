# Day 0 domain handoff

- Lane and branch: domain / `feature/day0-domain`
- Base and head: `e561d6dfb28451de39df4fe037cf91f15ace4bfb` (no candidate commit created)

## Changed paths

- `packages/risk_domain/`: added immutable dataset manifest/provenance and
  portfolio exposure contracts, validation, exports, and schema resources.
- `schemas/risk/v0.1/`: generated snapshots for dataset files, provenance,
  datasets, position exposures, concentration measures, and exposure snapshots.
- `tests/domain/test_models.py`: added synthetic dataset lineage, fixed
  demonstration-portfolio, cash-only, and Decimal-context regression coverage.

## Evidence and validation

- Generated schemas with `risk_domain.schema_export.write_schema_snapshot`.
- `make test-domain` — PASS (`14 passed`).
- The fixed demonstration portfolio verifies NAV `40000`, ALPHA `0.50` largest
  position weight, and cash weight `0.125`.
- `git diff --check` — PASS.

## Deviations, blockers, and limitations

- No contract-scope deviations.
- `make preflight` was previously blocked in `env-check` by an expired local
  GitHub CLI token; the synced Wave 0B plan and lane manifest were re-read
  before this change. This is an environment-only limitation.
- Exposure calculation currently rejects portfolios needing currency conversion;
  all source market values and cash must be in the portfolio base currency.
- Exposure ratios use a fixed 34-digit, half-even Decimal context so repeating
  weights and content digests are independent of the caller's Decimal context.

## Rollback and next action

- Roll back by removing these uncommitted lane-owned changes, or by reverting a
  future focused candidate commit. No shared configuration or vendor files were
  changed.
- Integration should review the domain field names and generated schemas, then
  accept a focused candidate commit after its lane-path check.
