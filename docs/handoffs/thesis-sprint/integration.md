# Thesis Sprint integration handoff — Day 1 closure

## Lane and branch

- Lane: `integration`
- Branch: `integration/thesis-experiment`
- Experiment baseline: `day23-complete`
  (`6ea08f6b7b88f5759808f2b30466ccdcd106919f`)
- Control-plane base:
  `aaad2c5fb6f13286c9c1478f39c6e10a5a567cf6`
- Accepted specialist candidate:
  `433ee994998afd3c7e79cd1169ddcdd24e19960f`
- Merge commit: `8280a63`
- Integration head: uncommitted working tree by explicit instruction
- Lifecycle: Day 1 complete; `THESIS-D2-PORTFOLIOS` in progress at
  `portfolio_definition`

## Files

The accepted candidate added the reviewed synthetic fixture and Day 1 package
beneath `data/fixtures/synthetic/thesis-day1/**`,
`examples/portfolio-risk-thesis/**`, and `tests/thesis/**`, plus the exact
specialist handoff `docs/handoffs/thesis-sprint/day1.md`.

Day 1 closure changes are limited to these integration-owned paths:

- `.github/workflows/thesis-sprint.yml`
- `Makefile`
- `README.md`
- `config/agent/thesis-sprint/status.json`
- `docs/handoffs/thesis-sprint/integration.md`
- `docs/workplans/current.md`
- `docs/workplans/thesis-sprint/day-1-data-portfolios-replay.md`
- `scripts/thesis/run_day1_demo.py`
- `tests/architecture/test_day23_control_plane.py`
- `tests/architecture/test_overlay_boundaries.py`
- `tests/architecture/test_thesis_sprint_control_plane.py`
- `tests/data/test_day23_research_data_plane.py`
- `tests/journeys/test_thesis_day1_vertical_slice.py`

The pre-existing integration edits in
`tests/architecture/test_day1_preparation.py` and
`tests/architecture/test_day23_control_plane.py` were preserved; only the
active Thesis pointer assertion in the latter advanced from `THESIS-D1` to
`THESIS-D2`.

The historical data-suite fixture assertion is a repository-wide binary-data
boundary despite its older `tests/data` location. Its exact allowlist now
includes only the accepted Thesis Day 1 Parquet fixtures; no data package or
fixture changed during closure.

Historical journey targets now select non-Thesis journey files explicitly,
while `test-thesis-journeys` owns `test_thesis*.py`. This prevents cross-
environment collection without skipping any journey.

The completed D23 lane check now ends at immutable tag `day23-complete`
instead of the later Thesis branch head, preserving its historical evidence
range and excluding Thesis-owned paths.

## Tests

- `make preflight`: PASS.
- `make test-thesis-control`: PASS (`16 passed`).
- `make test-thesis-journeys`: PASS (`1 passed`).
- `make verify-thesis-day1`: PASS, including the complete D23 baseline,
  `16` Thesis control tests, `20` specialist tests, `2` vertical-slice tests,
  fixture digests, the exact specialist range, and whitespace checks.
- `make demo-thesis-day1`: PASS; wrote the content-addressed external bundle
  for run `sha256:f9b855df8c7b016e32c16fd11e3de71623802469922c7aaaef6cc3037ec27e81`.
- `git diff --check`: PASS.
- `git -C vendor/servicefabric status --short`: clean.

The completion gate preserves the completed D23 baseline, runs all Thesis
control, specialist, integration, and journey tests, validates fixture
digests, checks the exact specialist lane range, and validates whitespace.

## Evidence

The vertical-slice journey runs all three fixed-quantity portfolios through
all five configured daily replay steps. Every step verifies deterministic run
identity and order, market and event point-in-time eligibility, latest-price
selection, canonical `portfolio.snapshot.create` and
`portfolio.exposure.summarize` invocation, immutable snapshot creation,
positive and reconciled NAV, reconciled position and cash weights, empty
effects, and absence of broker, order, trade, and rebalance objects.

The integration demo writes these immutable siblings beneath
`THESIS_DATA_ROOT/day1/<run_id>`:

- `dataset-metadata.json`
- `instrument-map.json`
- `portfolio-definitions.json`
- `replay-specification.json`
- `replay-steps.json`
- `portfolio-snapshots.json`
- `exposure-snapshots.json`
- `nav-and-weights.json`
- `run-manifest.json`
- `evidence-manifest.json`

The journey executes the complete demo in two separate temporary roots and
requires byte-identical semantic artifacts, IDs, and digests. The evidence
manifest digests every other sibling artifact, and Git status must remain
unchanged. Standard runs derive and record a canonical software revision from
the execution sources, canonical dependencies, package metadata, and locked
environment; an explicitly supplied non-empty revision remains authoritative.

## Deviations

The specialist demo remains available as its focused compact example. The
required acceptance evidence bundle is produced by the integration-owned
`scripts/thesis/run_day1_demo.py`. The Thesis package path now explicitly
includes `packages/risk_planning/src`, removing reliance on the package-local
import fallback for the canonical capability registry.

## Limitations

All inputs and outputs are fictional and synthetic and are not investment
advice. Day 1 provides only fixed-quantity replay, canonical portfolio
snapshots, exposure summaries, NAV, and weights. It contains no metrics,
findings, decision kernel, agents, B0/B1/A1 treatments, architecture
comparison, evaluation, external provider, external LLM, broker, order, trade,
rebalance, optimization, or portfolio mutation effect. Soft QA remains queued.

## Blockers

None.

## Rollback

Revert only the integration closure paths listed above, restore
`config/agent/thesis-sprint/status.json` and `docs/workplans/current.md` to
`THESIS-D1` in progress, and leave the accepted specialist merge and completed
historical lifecycle records intact. Generated demo evidence is external and
may be removed by deleting its exact `THESIS_DATA_ROOT/day1/<run_id>`
directory; no Git path is involved.

## Accepted Day 2 bridge checkpoint

The accepted `feature/thesis-day2` checkpoint implements the local licensed
CRSP/Compustat bridge and CLI. Its daily-primary and monthly-smoke builds were
completed locally under human authorization; licensed data and generated
snapshots remain external. The candidate-universe artifact is the final
currently implemented artifact. Metrics remain queued.

## Exact specialist entry point

The Day 2 specialist must read
`docs/workplans/thesis-sprint/day-2-portfolio-definition.md` and
`docs/contracts/thesis-real-portfolio-selection-v0.1.md`. Start from the
candidate-universe artifact and implement only the human-reviewed selection
YAML to fixed-quantity `PortfolioDefinition` YAML validation flow. The system
must never choose securities or quantities. Run:

```bash
make verify-thesis-day1
```

No metrics, selection algorithm, optimizer, broker, order, trade, rebalance,
or portfolio mutation is part of this entry point.
