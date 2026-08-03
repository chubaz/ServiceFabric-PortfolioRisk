# P1-04 — registry kernel integration implementation

## Objective

Reconcile the three audits and deliver the complete Phase 1 visible increment:
registry package, source adapters, persistent API, catalogue UI, migration, and
verification.

## Integration work

1. Reuse canonical identity and lifecycle semantics before creating fields.
2. Implement an index/projection; never copy full canonical definitions.
3. Persist metadata atomically outside Git with explicit test overrides.
4. Discover all seven initial asset kinds from existing sources.
5. Expose preview, bootstrap, catalogue, detail, compare, and transition APIs.
6. Add the Registry workspace using the existing Labs design system.
7. Add unit, application, architecture, and browser verification.
8. Preserve the existing vertical slice and all Phase 0 truth boundaries.

## Completion evidence

Write `docs/handoffs/platform-development/phase1-integration.md` with exact
base/head, changed paths, tests, limitations, deviations, rollback, and the
candidate commit for independent QA.
