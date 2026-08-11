# P2-01 — artifact contracts and persistence audit

## Objective

Identify the smallest repository projection around existing PortfolioRisk
artifact references and ServiceFabric immutable artifact-store contracts.

## Read scope

- `vendor/servicefabric/**` (read-only)
- `packages/risk_domain/**`, `packages/risk_registry/**`
- Phase 0 storage audit, Phase 1 handoffs, and the Phase 2 workplan

## Only writable path

`docs/handoffs/platform-development/phase2-contracts-persistence.md`

## Required output

- exact reused contracts and adapter boundary;
- artifact/run manifest fields, retention and lifecycle matrices;
- content-addressing, concurrency, locking, recovery, and integrity invariants;
- path/symlink/size/reference/deletion threat model;
- opaque locator, data-truth, rights, approval, and provenance semantics;
- focused adversarial tests, risks, rollback, and unresolved questions.

Do not implement code or edit vendor/canonical contracts. Run
`git diff --check`; stop without merging.
