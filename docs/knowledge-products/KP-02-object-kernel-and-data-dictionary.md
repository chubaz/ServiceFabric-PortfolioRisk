# KP-02: Object Kernel and Data Dictionary

Status: draft; implementation status: implemented for the Day 0 kernel. Deadlines: draft T+6h; review T+8h.

## Object definitions and identifiers

The implemented kernel distinguishes `Instrument`, `InstrumentIdentifier`, `Position`, `CashBalance`, `MarketObservation`, `FundamentalObservation`, `PortfolioSnapshot`, `QualityFlag`, and `SourceReference`. An instrument has a stable overlay `instrument_id`, a display name, and one or more typed identifiers. Identifier types are limited to ticker, PERMNO, GVKEY, CUSIP, and CIK; an instrument cannot repeat an identifier type. These are identifiers, not a claim that a corresponding provider record was retrieved.

Package, capability, tool, application, agent, finding, and alert identities remain separate from these domain objects. A `snapshot_id` identifies a submitted portfolio snapshot; its digest identifies the canonical contents of that immutable value.

## Time and Decimal conventions

All observation and snapshot times are timezone-aware and normalized to UTC. Naive timestamps are rejected. Persisted monetary values, quantities, prices, and market values use `Decimal`; binary floating point is not a persisted financial representation. Currency values use supported ISO 4217 alphabetic codes. Positions validate quantity × price against market value within the documented cent-level tolerance.

## Provenance, quality, and digest policy

Every observation may carry `SourceReference` entries containing source ID, source type, reference, and UTC retrieval time. A missing market or fundamental value remains `None` and requires the `missing` quality flag; it is never converted to zero. Synthetic observations carry `synthetic: true` and are not presented as real data.

Snapshots derive a deterministic SHA-256 digest from canonical JSON: model values are normalized, keys are ordered, decimals retain decimal text, and timestamps are rendered in UTC. A supplied mismatching digest is rejected. This is a content-addressing policy, not an assertion that input observations are complete or correct.

## Snapshot relationships

A portfolio snapshot contains sorted, unique positions; unique cash balances by currency; optional market and fundamental observations; and snapshot-level source references. Positions reference `instrument_id`; observations reference the same identifier. Corrected or newly observed data creates a new snapshot or revision value—existing snapshots are never overwritten in place.

## Planning and remaining work

The planning catalogue adds immutable review history, artifact links, thesis traceability, implementation status, and T0-relative deadlines around these artifacts. Additional risk measures, provider mappings, and finding schemas are planned work. They must preserve the same identity, provenance, missingness, and immutable-revision rules.
