# P1-01 — registry contracts and persistence audit

## Objective

Identify the smallest registry projection contract and durable local storage
design by reusing existing ServiceFabric identity, lifecycle, provenance,
compatibility, and atomic-registry behavior.

## Read scope

- `vendor/servicefabric/**` (read-only)
- `packages/**`, `schemas/**`, `config/**`
- Phase 0 handoffs and Phase 1 workplan

## Only writable path

`docs/handoffs/platform-development/phase1-contracts-persistence.md`

## Required output

- exact reusable contracts and semantics by path;
- required projection fields versus prohibited duplicated definition fields;
- lifecycle transition matrix and validation invariants;
- path-safe, atomic, restart-safe local persistence recommendation;
- compatibility, provenance, lineage, and version-comparison semantics;
- risks, tests, unresolved questions, and rollback.

## Non-goals and checks

Do not implement code or edit canonical contracts. Run `git diff --check`; the
handoff must be the only changed path. Stop without merging.
