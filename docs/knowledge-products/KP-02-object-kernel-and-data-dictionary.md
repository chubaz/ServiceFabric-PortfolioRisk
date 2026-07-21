# KP-02: Object Kernel and Data Dictionary

Status: draft. Deadlines: draft T+6h; review T+8h.

## Identity and value boundaries

Day 0 keeps package, capability, tool, application, agent, finding, and alert identities distinct. The implemented domain kernel defines instruments, identifiers, positions, cash balances, market observations, fundamental observations, portfolio snapshots, quality flags, and source references. Snapshot IDs identify snapshots; content digests make their persisted contents addressable.

## Implemented behavior

Persisted financial values use `Decimal`, timestamps are timezone-aware and normalized to UTC, and snapshot construction enforces immutable values. A missing observation has no fabricated value and must carry a missing quality flag. Synthetic observations carry `synthetic: true`. Source references retain source ID, type, reference, and retrieval time.

## Planning vocabulary

This catalogue adds knowledge-product IDs (`KP-00` through `KP-05`), work items, T0-relative deadlines, review decisions, and source-reference links. Review decisions are append-only values; recording one returns a revised knowledge-product record rather than mutating the original.

## Planned behavior

Additional risk measures, provider mappings, and finding schemas are not implemented by this product. Their data dictionaries must retain the same missingness, source, and immutable-revision semantics.
