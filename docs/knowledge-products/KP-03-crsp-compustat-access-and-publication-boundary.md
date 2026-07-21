# KP-03: CRSP/Compustat Access and Publication Boundary

Status: draft; implementation status: partial. Deadlines: draft T+7h; review T+10h.

## Licensed-data and publication boundary

CRSP, Compustat, Bloomberg, RavenPack, Accern, and similar licensed extracts must never be committed to this public repository. The same prohibition covers API keys, passwords, tokens, cookies, SSH material, private endpoints, portfolio statements, provider caches, and local DuckDB, SQLite, Parquet, Arrow, or Feather files. Approval to design a connector is not approval to publish an extract, a derived dataset, or query output; redistribution rights and provenance require separate review.

No real CRSP or Compustat access is implemented. This product contains neither provider credentials nor licensed observations, and it makes no claim that an account, entitlement, query, or dataset exists.

## Synthetic-data boundary

Only reviewed deterministic fixtures beneath `data/fixtures/synthetic/**` may be committed. They must be labelled synthetic, carry their deterministic seed or generation context, and retain missing or partial quality states. A failed or incomplete query may not become a zero observation. Synthetic data is a test aid, not a proxy for provider coverage, timeliness, or accuracy.

## Future WRDS secret-reference design

A future WRDS integration may accept an opaque local secret reference such as a deployment-specific key name or secret-manager handle. The reference is resolved only by local infrastructure and never serialized into a planning, domain, tool, or application contract. The connector configuration must not contain the credential value, and logs, manifests, test fixtures, and error messages must redact it. This is a design proposal only; secret resolution and WRDS connectivity are not implemented.

## Future local data zones and storage rationale

The planned local-only pipeline separates four zones outside the repository:

- Landing: an access-controlled immutable receipt of a provider response plus retrieval metadata.
- Normalized: schema-mapped, typed records with source and quality metadata retained.
- Curated: reviewed local analytical tables or datasets derived from normalized records.
- Snapshot: immutable, content-addressed inputs supplied to domain or application workflows.

Parquet is the proposed exchange and archival format because it is columnar, typed, and suited to reproducible batch partitions. DuckDB is the proposed local analytical engine because it can query local Parquet efficiently without a network service. Both remain local implementation choices; no Parquet file, DuckDB database, or provider cache is committed here.

## Future query-manifest requirements

Each future provider query must create a local, reviewable manifest recording provider and dataset identifiers, approved purpose, query template/version or checksum, parameter names and non-secret values, schema version, retrieval time in UTC, row-count/quality outcomes, destination zone, and rights classification. It must reference—not contain—the local secret reference. Query output remains unpublished unless a separate publication review confirms rights, provenance, and the absence of private or licensed content.
