# P1-00 — integration activation

## Objective

Activate Phase 1 from the exact accepted Phase 0 merge, freeze non-overlapping
lanes, and provide a deterministic verification target before implementation.

## Owner and paths

- Owner: integration authority.
- Branch: `integration/platform-registry-kernel`.
- Allowed paths: integration lane in `phase1-lanes.json`.

## Required work

1. Verify PR #20 and its required checks.
2. Create the Phase 1 branch/worktree from merge `21339db19357277ca9a9a1ca50107f1a884d7aeb`.
3. Activate status, workplan, tasks, lane manifest, and gate.
4. Run the control-plane test and record exact evidence.

## Completion evidence

Record base/head, changed paths, tests, deviations, rollback, and next action in
the integration handoff. No specialist merges this task.
