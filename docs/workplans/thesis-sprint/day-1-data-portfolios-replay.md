# THESIS-D1 — Data, portfolios, and deterministic replay

- Status: complete
- Namespace: `thesis-sprint`
- Experiment: `portfolio-risk-architecture-comparison-v1`
- Base: `day23-complete`
- Specialist branch point: reviewed Thesis Sprint control-plane commit
- Integration branch: `integration/thesis-experiment`
- Specialist branch: `feature/thesis-day1`
- Integration order: `day1` -> `integration`

## Objective

Establish the reproducible data and replay foundation for the four-day thesis
experiment. This activation creates the control plane, CI, locked environment,
ownership rules, frozen contract, and verification harness. Adapter, portfolio,
fixture, replay, and experiment behavior belongs to the Day 1 specialist and
is not implemented by this activation.

## Frozen Day 1 boundary

The specialist may change only:

- `examples/portfolio-risk-thesis/**`;
- `data/fixtures/synthetic/thesis-day1/**`;
- `tests/thesis/**`; and
- the exact file `docs/handoffs/thesis-sprint/day1.md`.

The specialist stops without merge. Integration remains the only acceptance
authority. Historical Day 0, Day 1, and Day 2–3 lifecycle records remain
complete and unchanged.

## Required implementation

Day 1 will provide a minimal example package, explicitly synthetic reviewed
fixtures, fixed-quantity portfolio inputs, and deterministic in-process
historical replay. Every observation must retain a timezone-aware UTC
`observed_at`, `available_at`, and replay `as_of`; a replay may consume an
observation only when `available_at <= as_of`. Missing availability blocks or
warns and is never guessed. Parquet may store records but is not the replay
mechanism.

The specialist must add:

- focused tests beneath `tests/thesis/**`;
- a fixture digest validator at
  `examples/portfolio-risk-thesis/scripts/validate_fixture_digests.py`;
- a local demo at
  `examples/portfolio-risk-thesis/scripts/run_day1_demo.py`; and
- a complete Day 1 handoff.

All mutable demo and replay artifacts must be written beneath
`THESIS_DATA_ROOT`, outside Git.

## Explicit exclusions

Day 1 implements no LLM, agent architecture, metric decision kernel, trading,
portfolio mutation, external provider, network call, Kafka, Redis, WebSocket,
scheduler, or ServiceFabric process-host smoke. It does not implement or
compare B0, B1, and A1; those architecture treatments are introduced later.

## Acceptance gates

- `make verify-d23-current`;
- `make test-thesis-control`;
- `make test-thesis-day1`;
- `make test-thesis-integration`;
- `make test-thesis-journeys`;
- fixture digest validation;
- the Day 1 lane path check from the control-plane addition commit through the
  exact specialist candidate head;
- `git diff --check`; and
- a clean `vendor/servicefabric` submodule.

`make verify-thesis-day1` is the accepted completion gate. It preserves the
completed D23 baseline, runs all Thesis Day 1 suites and fixture validation,
and checks the exact specialist candidate range. `make verify-thesis-current`
delegates to that completed gate while Day 2 remains queued.

## Specialist entry point

Create `feature/thesis-day1` from the reviewed integration commit that first
adds `config/agent/thesis-sprint/status.json`. That commit descends from the
`day23-complete` experiment baseline and contains this workplan, environment,
and lane checker. Read this workplan and
`docs/contracts/thesis-experiment-v0.1.md`, run `make thesis-env`, and change
only the frozen Day 1 lane paths.

Before handoff, resolve the immutable branch point and validate through the
specialist candidate head:

```bash
thesis_control_plane_base="$(
  git log --diff-filter=A --format=%H -1 -- \
    config/agent/thesis-sprint/status.json
)"
python scripts/thesis/check_lane_paths.py \
  --lane day1 \
  --base "$thesis_control_plane_base" \
  --head HEAD \
  --manifest config/agent/thesis-sprint/lanes.json
```

Record both resolved commit IDs in `docs/handoffs/thesis-sprint/day1.md`.
Integration runs the full acceptance gate against its checkout while keeping
the lane range restricted to the recorded candidate:

```bash
make verify-thesis-day1 THESIS_DAY1_LANE_HEAD=<specialist-candidate-head>
```
