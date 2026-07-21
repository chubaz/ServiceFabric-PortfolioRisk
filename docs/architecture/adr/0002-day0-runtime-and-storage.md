# ADR-0002: Freeze Day 0 Runtime and Storage Conventions

- Status: Accepted
- Date: 2026-07-21

## Context

Day 0 contributors need stable, explicit conventions before independently
implemented risk-domain, data, capability, and application components can be
integrated. Financial values, observation time, snapshot identity, and action
approval require stricter semantics than framework defaults provide.

## Decision

- Day 0 runs on Python 3.11 only.
- Timestamps are timezone-aware and normalized to UTC.
- Money and quantities use `Decimal`; binary floating-point is not a persisted
  financial value representation.
- Currency values use ISO 4217 alphabetic currency codes.
- Snapshots are immutable and content-addressed. New observations or
  corrections create a new snapshot or revision rather than overwriting one.
- Mutable data, provider caches, and local analytical databases reside beneath
  an external local data root, never the repository.
- Synthetic data uses a recorded deterministic seed and is labelled synthetic.
- Consequential actions require explicit human approval.
- No external LLM provider is configured or called by default.

## Consequences

All Day 0 schemas, packages, fixtures, and tests must preserve these rules.
Adapters may format values for display but cannot weaken canonical value,
snapshot, or approval semantics. A future change needs a reviewed ADR and
migration plan.
