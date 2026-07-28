# THESIS-D2 — Metrics and decision kernel

- Status: queued
- Depends on: `THESIS-D1` complete and accepted
- Experiment: `portfolio-risk-architecture-comparison-v1`

## Objective

Freeze and implement the experiment metrics and one deterministic decision
kernel over the accepted Day 1 point-in-time replay. The kernel will consume
the same immutable inputs for every later architecture treatment and preserve
evidence, assumptions, warnings, limitations, and human-review boundaries.

## Queued boundary

No Day 2 behavior is active. Metric definitions, missing-value rules,
comparison tolerances, treatment-independent inputs, and output digests must be
accepted before implementation. Undefined values remain undefined with an
explicit warning; they are never converted to zero.

There is no provider network, LLM, broker, order, trade, rebalance, scheduler,
or portfolio mutation effect.
