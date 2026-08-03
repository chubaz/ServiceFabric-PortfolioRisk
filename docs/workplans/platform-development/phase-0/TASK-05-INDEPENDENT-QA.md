# P0-05 — independent Phase 0 QA

## Objective

Independently determine whether the Phase 0 candidate is truthful, internally
consistent, safe, testable, and ready to become the Phase 1 baseline.

## Read scope

The complete Phase 0 candidate, all three specialist handoffs, decision source,
CI results, current workplan, roadmap, and deferred thesis record.

## Only writable path

`docs/handoffs/platform-development/phase0-independent-qa.md`

## Review requirements

- reproduce `make verify-platform-phase0` from a clean worktree;
- verify exact lane ownership and no vendor/private/generated-data changes;
- check that UI words match contract and policy meanings;
- ensure fixture/synthetic/simulated/real states cannot be confused;
- ensure development-only controls do not appear enabled elsewhere;
- verify all unresolved decisions remain visible;
- record pass, fail, or blocked with evidence and residual risk.

The reviewer does not fix the candidate and does not merge. Any defect returns
to integration as a new bounded task.
