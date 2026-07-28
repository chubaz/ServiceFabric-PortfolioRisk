# Thesis experiment contract v0.1

## Status and identity

This frozen control-plane contract governs experiment
`portfolio-risk-architecture-comparison-v1` in the `thesis-sprint` namespace.
It begins at immutable tag `day23-complete`. Historical Day 0, Day 1, and
Day 2–3 lifecycle records remain authoritative for their completed programmes.

## Day 1 data and replay contract

All committed observations are explicitly labelled synthetic and live only
beneath `data/fixtures/synthetic/thesis-day1/**`. Each record preserves a
stable identity, source and fixture revision, content digest, units, quality
state, `observed_at`, `available_at`, and any limitations. All timestamps are
timezone-aware UTC.

Portfolio quantities are fixed inputs. Replay cannot trade, rebalance, optimize,
or otherwise mutate a portfolio. For replay step `as_of`, every selected
observation must satisfy:

```text
available_at <= as_of
```

Missing `available_at` blocks the record or produces an explicit warning; it
is never inferred. A missing or failed observation remains missing and is
never represented as zero.

Historical streaming is a deterministic in-process replay ordered by the
frozen timestamp and identity rules. Parquet is an allowed storage format, not
the replay mechanism. No Kafka, Redis, WebSocket, background scheduler, or
network provider participates.

## Artifact and effect boundary

Generated mutable artifacts, including Parquet, databases, replay state,
reports, and caches, remain outside Git beneath the configured
`THESIS_DATA_ROOT`. Only explicitly synthetic, reviewed fixtures may be
committed. Credentials are opaque local references and never experiment data.

Day 1 implements no LLM and no agent architecture. There is no external
provider, external LLM, broker connectivity, order, trade, hedge, rebalance,
optimization, or portfolio mutation effect. Consequential actions require
explicit human review.

## Four-day comparison boundary

The experiment will compare B0, B1, and A1 only after their treatment
definitions and common metric decision kernel are frozen in later workplans.
Day 1 creates shared replay inputs; it produces no architecture comparison,
ranking, or result claim.

Every later output must identify its treatment, input and output digests,
evidence, assumptions, warnings, limitations, synthetic disclosure, and human
review state.
