# P1-03 — existing-definition source and migration audit

## Objective

Map existing agent, capability, evaluation, report, dashboard, scenario, and
workflow definitions into truthful registry projections without creating new
canonical objects or importing generated runtime artifacts.

## Read scope

- `apps/portfolio-risk-workbench/labs/**`
- `packages/**`, `examples/**`, `schemas/**`
- relevant tests and Phase 0 canonical inventory

## Only writable path

`docs/handoffs/platform-development/phase1-source-migration.md`

## Required output

- source-of-truth mapping for every initial asset kind;
- deterministic identity/version/digest rules;
- display projection and provenance mapping;
- duplicate/collision and unavailable-version handling;
- explicit bootstrap/import behavior and repeatability;
- migration tests, limitations, risks, and rollback.

## Non-goals and checks

Do not modify definitions, registries, UI, or tests. Do not manufacture missing
assets to satisfy a count. Run `git diff --check`; the handoff must be the only
changed path. Stop without merging.
