# Day 1 provider access boundary

All provider catalogue entries start with `enabled: false` and
`access_state: unavailable` unless a separately reviewed local synthetic or
public source is explicitly approved. WRDS, CRSP, Compustat, RavenPack,
Accern, Bloomberg, brokers, and other external sources are disabled by
default. Credentials are represented only by opaque references such as
`secret-ref:provider/example`; secret values, endpoints, cookies, and tokens
are never contract data.

Each query manifest records source identity, rights state, access state, data
zone, requested fields, provenance, freshness, quality flags, and publication
restriction. Only reviewed fixed DuckDB views may be read; arbitrary SQL is
not accepted. Licensed and personal data stays in an external local zone and
must not enter Git, reports marked public, or synthetic fixtures.

Provider access cannot create broker, order, trade, or rebalance effects.
