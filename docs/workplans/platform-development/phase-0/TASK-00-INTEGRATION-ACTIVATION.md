# P0-00 — integration activation

## Objective

Create the clean programme branch, authoritative status and lane manifests,
task briefs, CI-compatible lifecycle pointer, and deterministic verification
gate from the merged baseline.

## Owner and paths

- Owner: integration authority.
- Branch: `integration/platform-development`.
- Allowed paths: the integration lane in
  `config/agent/platform-development/lanes.json`.

## Required work

1. Verify PR #18 and all required checks before branching.
2. Preserve the deferred Thesis Sprint record without making it current.
3. Create the `platform-development` namespace and exact specialist lanes.
4. Add architecture tests for status, tasks, ownership, and safety boundaries.
5. Run `make verify-platform-phase0` and record the evidence.

## Completion evidence

Commit, check results, clean status, changed paths, deviations, and rollback are
recorded in the integration handoff. No specialist may merge this task.
