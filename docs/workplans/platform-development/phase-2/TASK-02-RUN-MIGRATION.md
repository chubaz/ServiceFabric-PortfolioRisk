# P2-02 — existing-run migration audit

## Objective

Map current Agent Lab run folders and generated outputs into a truthful retained
run projection without silently promoting one-off files or licensed material.

## Read scope

- `apps/portfolio-risk-workbench/labs/**`
- relevant run, agent, capability, report, and application tests
- Phase 0 storage audit and Phase 2 workplan

## Only writable path

`docs/handoffs/platform-development/phase2-run-migration.md`

## Required output

- exact current run-folder producer/consumer map;
- deterministic import/admission rules and required rejection cases;
- mapping for inputs, provenance, activity, capability/model receipts, outputs,
  review, transcript, and rendered files;
- licensed/private/synthetic disclosure and publication restrictions;
- idempotence, partial/corrupt run handling, rollback, and tests.

Do not read the user's private run contents, alter runtime code, or manufacture
missing metadata. Run `git diff --check`; stop without merging.
