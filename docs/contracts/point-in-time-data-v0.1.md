# Point-in-time data contract v0.1

## Semantics

`observed_at` is when the source says the fact was observed. `available_at` is
when that fact became available to the research process. `retrieved_at` is
when the local source was retrieved or imported. `as_of` is the evaluation
cutoff carried by every fixed query manifest.

For a query with cutoff `as_of`, a record is eligible only when its
`available_at <= as_of`. A record with missing `available_at` is not eligible
without an explicit quality decision; implementations must block or warn,
never silently infer availability. There is no look-ahead fallback.

## Immutable evidence

Point-in-time results identify provider, dataset revision, source digest,
schema, mapping, units, transformations, quality report, immutable snapshot,
date-effective identifier crosswalk, fixed query manifest, and publication
restriction. New imports create new revisions; snapshots are not overwritten.

Fixed manifests are the only query interface in Phase 1. Arbitrary SQL and
user SQL, notebook
execution, external providers, broker connectivity, orders, trades, and
rebalancing are outside this contract.
