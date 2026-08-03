# P0-04 — integration synthesis and visible increment

## Objective

Accept or reject the three audit candidates, reconcile their evidence, and
implement the smallest coherent Phase 0 increment without inventing duplicate
canonical objects.

## Dependencies

P0-01, P0-02, and P0-03 handoffs must be present at reviewed candidate commits.

## Integration work

1. Validate candidate ancestry and exact allowed paths.
2. Build one canonical reuse/terminology/decision synthesis.
3. Record unresolved questions with impact and latest safe decision point.
4. Add compact profile, provenance, authority, and artifact-boundary disclosure
   to the current Labs shell where the audits show it is necessary.
5. Add architecture and application tests that prevent semantic drift.
6. Update status from audit to acceptance only after all gates pass.

## Required verification

- `make verify-platform-phase0`
- focused application tests for changed UI/runtime paths
- existing Labs smoke tests
- `git diff --check`

Integration owns shared contracts and resolves conflicts. It must reject rather
than repair an out-of-scope specialist candidate silently.
