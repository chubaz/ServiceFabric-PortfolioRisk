# KP-05: Supervisor Demo Pack and Day 1–3 Backlog

Status: draft. Deadlines: draft T+20h; review T+24h.

## Day 0 demonstration

The reviewable demonstration is deliberately modest: load deterministic YAML knowledge-product seeds; validate unique IDs, permitted review states, dependencies, source links, and deadline ordering; and show that a review decision creates a revised immutable record. The demonstration has no market feed, portfolio account, broker connection, order flow, or investment recommendation.

## Verified behavior

The planning contracts are Pydantic v2 immutable models. YAML is loaded with `safe_load`; seeds use `T0` plus minute offsets rather than personal timestamps. The catalogue sorts draft deadlines deterministically by offset and ID. The domain kernel supplies immutable UTC and missingness conventions consumed by the documentation, but this product does not execute domain calculations.

## Day 1–3 backlog

1. Integrate the approved planning catalogue into a canonical ServiceFabric-hosted application path.
2. Add provider-bound data contracts and only reviewed synthetic test fixtures.
3. Add capability and agent catalogues with evidence, warning, limitation, and human-review surfaces.
4. Build a supervisor-facing display that labels data quality, provenance, and planned versus implemented behavior.

## Review gate

Each backlog item requires architecture and safety review. No item authorizes trading, rebalancing, broker connectivity, publication of licensed data, or a claim that an alert is investment advice.
