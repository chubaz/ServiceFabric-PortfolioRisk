# Event dataset contract v0.1

Each immutable local event record preserves `provider`, `source_event_id`,
`local_event_id`, an explicit stable `entity_id`, `event_time`, `available_at`,
and `retrieved_at`. It also records `event_type`, `relevance`, `sentiment`,
`novelty`, amendment or retraction state, publication restriction, evidence,
`synthetic_state`, and `private_state`.

Entity identity is explicit and crosswalk-backed; fuzzy and ticker-based
matching are not permitted. Point-in-time consumers filter on `available_at`
and retain missing-availability warnings. Events are local-only, immutable,
and effect-free. External event providers, external LLMs, credentials, and
publication of restricted evidence remain disabled.
