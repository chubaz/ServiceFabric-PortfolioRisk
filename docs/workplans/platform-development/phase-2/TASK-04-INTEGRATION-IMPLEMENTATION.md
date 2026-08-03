# P2-04 — artifact repository integration implementation

## Objective

Reconcile the three audits and deliver the complete Phase 2 visible increment:
artifact package, external repository, retained-run adapter, API, UI, governed
retention operations, and verification.

## Integration work

1. Reuse canonical artifact identity and immutable storage semantics.
2. Store content-addressed bytes outside Git and metadata atomically.
3. Implement strict artifact, run, reference, lifecycle, and receipt models.
4. Add admission for compatible Agent Lab runs with fail-closed migration.
5. Expose browse, detail, file preview/download, verify, archive, tombstone,
   restore, deletion preview, and eligible purge APIs.
6. Add the Artifact Repository workspace using the existing Labs design system.
7. Add focused, application, architecture, migration, and browser tests.
8. Preserve Phase 1 registry truth and all no-effect/data-rights boundaries.

## Completion evidence

Write `docs/handoffs/platform-development/phase2-integration.md` with exact
base/head, paths, tests, limitations, deviations, rollback, and candidate.
