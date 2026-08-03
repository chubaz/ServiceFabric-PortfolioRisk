# ADR-0006: Thesis experiment runtime

- Status: Accepted for Thesis Sprint Day 1
- Date: 2026-07-28

## Context

The four-day thesis experiment requires reproducible historical inputs without
changing the completed Day 0, Day 1, or Day 2–3 programmes or weakening the
canonical ServiceFabric boundaries.

## Decision

Historical streaming is deterministic in-process replay. Parquet is storage,
not the replay mechanism. Point-in-time selection requires
`available_at <= as_of`, and all timestamps are timezone-aware UTC. Portfolio
quantities are fixed for replay.

Generated mutable artifacts remain outside Git beneath `THESIS_DATA_ROOT`.
Only explicitly synthetic reviewed fixtures may be committed. The later
four-day experiment compares B0, B1, and A1 against common accepted inputs;
Day 1 implements no LLM or agent architecture.

The runtime includes no Kafka, Redis, WebSocket, scheduler, network provider,
trading, or portfolio mutation effect. No broker, order, trade, rebalance, or
optimization path is authorized.

## Consequences

Day 1 is a small local deterministic foundation, not a production streaming
system. Missing availability cannot be guessed. Storage layout cannot become
an implicit execution engine. Later architecture results remain synthetic
research evidence subject to explicit human review and limitations.
