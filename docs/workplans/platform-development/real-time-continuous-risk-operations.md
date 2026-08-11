# Parked slice: continuous real-time risk operations

Status: parked; not part of the current compressed-replay implementation.

## Purpose

Build a second execution regime that represents a risk-management system
running continuously through a trading day. It is a comparator for the thesis
apparatus, not a replacement for inexpensive large-scale replay.

## Required design

1. Event-time scheduler with durable queues and replay-safe ordering.
2. Concurrent agent and graph workers with declared per-workflow priorities.
3. Real-time context updates and point-in-time data admission.
4. Backpressure, cancellation, deadlines, retries and failure isolation.
5. A daily resource envelope covering wall time, model calls, tokens and cost.
6. Trigger-to-output, queueing, critical-path and utilization telemetry.
7. End-of-day execution treatment compatible with daily-price experiments.
8. Identical headless structured outputs and ArchitectureOutput mapping used by
   compressed replay so evaluation remains comparable.

## Experimental comparison

Run identical Cases under `compressed_replay_v1` and
`continuous_operations`. Treat execution regime, concurrency, event-arrival
rate, portfolio count, agent-graph width, model route and resource budget as
controlled factors. Compare analytical quality, timeliness, stability,
throughput, deadline success and efficiency without combining them into an
unexplained composite score.

## Admission boundary

Do not call a test `continuous` merely because it sleeps between workflow
cycles. Admission requires real concurrent workers, queue telemetry, explicit
resource budgets, reproducible event ordering and the same retained output
contract used by the thesis evaluator.
