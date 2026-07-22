# D23-PHASE-1 — Governed local research data plane

- Status: in progress
- Base: `day1-complete`
- Lanes: integration, data-platform, experience

## Objective

Establish a reproducible, local-only research data plane with immutable
snapshots, explicit provenance, point-in-time semantics, quality reporting,
fixed query manifests, and a reviewed provider/rights boundary. This phase
freezes contracts and harnesses; it does not implement provider-data product
code.

## Contract freeze

Every imported dataset records provider identity, dataset identity and
revision, rights state, access state, local source digest, source schema, field
mapping, source units, transformations, observed_at, available_at,
retrieved_at, point-in-time `as_of`, quality report, immutable snapshot
identity, date-effective identifier crosswalk, fixed query manifest, and
publication restriction.

## Operating boundary

The landing, normalized, curated, manifests, quality, and evidence zones are
external to Git when mutable. Reviewed synthetic local sources may be
available. Licensed local exports require an explicit rights state and
confirmation before import. WRDS, CRSP, Compustat network, RavenPack, Accern,
and Bloomberg remain network-disabled. No credentials or provider calls are
allowed. Secrets, if referenced by future local tooling, are opaque local
references only.

Queries use fixed manifests only, always carry `as_of`, filter point-in-time
records using `available_at`, and never fall back to look-ahead or silently
guess missing availability. User SQL is not a contract.

## Acceptance gates

- control-plane records and lane ownership validate;
- Day 0 and Day 1 regression gates remain green;
- fixed manifests and contract vocabulary are reviewable;
- mutable data zones are excluded from Git;
- no external network, broker, order, trade, or rebalance effect is present.
