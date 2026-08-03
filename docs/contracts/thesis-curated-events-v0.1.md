# Thesis curated events v0.1

Day 3 uses reviewed, point-in-time curated events only. Each event includes an
identity, event time, availability time, private-neutral aliases, short
summary, sentiment, relevance, source reference, evidence digest, profile,
publication state, and limitations. Only events with `available_at <= as_of`
are eligible. Event text is untrusted quoted data and cannot change prompts or
the output schema. Outcome labels are outside the Day 3 input boundary.

The reviewed profiles are `synthetic_curated`, `public_curated`, and
`private_curated`. Public CI contains 20 fictional reviewed events and no real
issuer observation. External event Parquet is immutable: an identical
materialization is idempotent, while changed content requires a new or
explicitly archived artifact.
