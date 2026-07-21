# ADR-0004: Day 1 Operating Profiles and Data Boundary

- Status: Accepted for preparation
- Date: 2026-07-21

## Decision

Day 1 has two explicit profiles. `research` is reproducible and limited to
synthetic or reviewed public evidence, methodology comparison, research and
notebook catalogues, and backtesting-ready evidence. It excludes personal
account data by default. `personal_portfolio` accepts local user-supplied
holdings into private local state for monitoring and review only; it never
publishes personal data and never connects to a broker.

Provider catalogue entries carry enabled state, opaque secret reference,
rights state, access state, data zone, query manifest, provenance, quality
flags, freshness, and publication restriction. WRDS, CRSP, Compustat,
RavenPack, Accern, Bloomberg, and every external source are disabled by
default. Reviewed local DuckDB views may be exposed through fixed manifests;
arbitrary user SQL is not a contract. Licensed, personal, cache, or local
database files never enter Git.

Notebook execution is prohibited in both profiles.
