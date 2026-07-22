# Provider dataset contract v0.1

This contract freezes the metadata required for a Phase 1 local research
dataset. It is a metadata contract, not a provider integration.

## Required identity and rights

- `provider_id`: stable provider identity, distinct from package, capability,
  tool, application, agent, finding, and alert identities;
- `dataset_id` and immutable `dataset_revision`;
- explicit `rights_state`, `access_state`, and `publication_restriction`;
- `local_source_digest` over the imported source bytes or canonical source;
- opaque `secret_ref` only when a future local process needs one; never the
  secret, endpoint, token, or credential value.

## Required data description

The record includes `source_schema`, `field_mapping`, `source_units`, and an
ordered `transformations` list. Each observation carries `observed_at`,
`available_at`, `retrieved_at`, and point-in-time `as_of`. Missing availability
is missing: it must block or warn and must never be guessed or replaced by a
look-ahead value.

## Evidence and publication

The dataset includes a `quality_report`, an immutable `snapshot_id`, a
date-effective `identifier_crosswalk`, and a `fixed_query_manifest` reference.
Publication restrictions travel with snapshots and evidence. Mutable landing,
normalized, curated, manifests, quality, and evidence storage is external to
Git.

Phase 1 permits reviewed synthetic local sources and explicitly confirmed
licensed local exports only. It makes no external API call and leaves WRDS,
CRSP, Compustat network, RavenPack, Accern, and Bloomberg network-disabled.
