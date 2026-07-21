# Day 0 domain handoff

- Lane and branch: domain / `feature/day0-domain`
- Base: `day0-prepared` (`5d4bb78a2c4126c7a04c0244e50ef6662cd3e0b8`)
- Head: `cc62a33a5775c715e2457154e7eeacc74455dcd2` (no candidate commit created)

## Changed paths

- `packages/risk_domain/`: immutable Pydantic v2 domain contracts, canonical
  digest helpers, and deterministic schema exporter.
- `schemas/risk/v0.1/`: generated JSON Schema snapshots and schema index.
- `tests/contracts/` and `tests/domain/`: focused construction, immutability,
  validation, digest, Decimal, ordering, missing-value, and reproducibility
  coverage.

## Evidence and validation

- Generated schemas with `risk_domain.schema_export.write_schema_snapshot`.
- `make test-domain` — PASS (`9 passed`).
- `git diff --check` — PASS.
- `make preflight` was attempted but stopped in `env-check` because the local
  GitHub CLI token is expired. No repository change is needed to resolve it.

## Deviations, blockers, and limitations

- No contract-scope deviations.
- The preflight authentication failure is an environment blocker only.
- Day 0 market-value validation uses the declared cent-level (`0.01`)
  quantization tolerance; later policy changes require an ADR and schema
  revision.

## Rollback and next action

- Roll back by deleting the uncommitted lane-owned additions, or by reverting a
  future focused candidate commit; no shared configuration or vendor files were
  changed.
- Integration should review the contract field names and generated snapshots,
  then accept a focused candidate commit after its normal lane-path check.
