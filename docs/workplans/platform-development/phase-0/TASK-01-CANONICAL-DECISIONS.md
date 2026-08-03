# P0-01 — canonical contracts and decisions audit

## Objective

Map existing canonical objects and registries to the roadmap concepts, then
normalize the user-reviewed P0/Before-v1 decisions without creating duplicate
objects or silently resolving modified answers.

## Read scope

- `vendor/servicefabric/**` (read-only)
- `packages/**`, `schemas/**`, `data/schemas/**`
- `config/**`, `docs/contracts/**`, `docs/architecture/adr/**`
- the roadmap, connector brief, and supplied decision workbook

## Only writable path

`docs/handoffs/platform-development/phase0-canonical-decisions.md`

## Required output

- canonical-object inventory: existing, reusable with adapter, provisional,
  missing, duplicated, obsolete;
- registry inventory and identity/version/lifecycle semantics;
- P0/Before-v1 accepted and modified decision summary with source row/ID;
- exact recommendations for reuse before any new contract is considered;
- conflicts, ambiguities, and questions requiring the user.

## Non-goals and checks

Do not edit contracts, schemas, tests, manifests, or the workbook. Do not infer
acceptance from blank cells. Run `git diff --check`; the exact handoff must be
the only changed path. Stop without merging.
