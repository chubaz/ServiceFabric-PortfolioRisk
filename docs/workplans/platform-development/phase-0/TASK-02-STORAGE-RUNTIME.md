# P0-02 — storage, runs, artifacts, and runtime audit

## Objective

Trace how current agent tests, LLM calls, DuckDB queries, synthetic workflow
cycles, dashboards, reports, and generated files execute and persist. Define
the smallest safe boundary needed before Registry and Artifact Repository work.

## Read scope

- `apps/portfolio-risk-workbench/labs/**`
- runtime, capability, agent, data, and application packages
- `.gitignore`, package manifests, scripts, tests, and fixture paths
- ServiceFabric persistence/runtime contracts in `vendor/servicefabric/**`

## Only writable path

`docs/handoffs/platform-development/phase0-storage-runtime.md`

## Required output

- endpoint-to-runtime call map for every current Lab;
- system asset, experiment overlay, run artifact, cache, fixture, and evidence
  storage inventory;
- current one-off versus reusable behavior;
- retention/deletion/recovery and concurrency risks;
- real/synthetic/fixture disclosure gaps;
- recommended Phase 1/2 seams using existing contracts first.

## Non-goals and checks

Do not move files, delete runs, create storage contracts, or change runtime
code. Never read licensed rows or secrets. Run `git diff --check`; the exact
handoff must be the only changed path. Stop without merging.
