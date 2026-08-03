# Thesis Sprint Day 2 specialist handoff

## Lane and branch

- Lane: `day2`
- Branch: `feature/thesis-day2`
- Base and working-tree HEAD: `1e9583c`
  (`chore(thesis): activate Day 2 metrics stage`)
- Candidate state: uncommitted working-tree changes; no commit, push, merge,
  lifecycle transition, network call, or consequential effect was created.
  Private portfolio definitions and evidence were materialized externally only
  after explicit human review.

## Changed paths

- `packages/risk_data/**`: upgrades `candidate-crsp-universe` to private,
  deterministic artifact version 2; adds optional absolute external `--output`
  confined beneath the governed data root, compact row-free console output,
  non-mutating parent-permission handling, and StockNames-optional catalogue
  support.
- `examples/portfolio-risk-thesis/**`: adds the five immutable reviewed
  selection/materialization contracts, human-review validation, private
  immutable output materialization and verification, the two requested CLI
  commands, documentation, and an invalid synthetic-placeholder selection
  example.
- `examples/portfolio-risk-thesis/**`: adds the reviewed Day 2 experiment
  binding, deterministic Morning MetricPack, canonical capability invocations,
  findings, review items, decision points, immutable private outputs, CLI
  prepare/validate/run commands, and a placeholder-only public example.
- `data/schemas/thesis-real-data/**`: adds the reviewed Day 2 experiment
  manifest schema.
- `tests/data/**` and `tests/thesis/**`: adds candidate-artifact and adversarial
  real-portfolio contract, CLI, immutability, idempotency, privacy, loader,
  network/effect, and Day 1 byte-regression coverage.
- `docs/handoffs/thesis-sprint/day2.md`: this exact handoff.

No root dependency, Makefile, CI, lifecycle, shared contract/workplan,
Day 1 portfolio YAML, other package, application, schema, or
`vendor/servicefabric/**` path was changed.

## Tests executed

- `make preflight` — PASS.
- `make test-thesis-real-data` — `31 passed`.
- Focused real-portfolio suite — `35 passed`.
- `make test-thesis-day1` — `57 passed`.
- All four requested CLI help surfaces — PASS.
- `git diff --check` — PASS.
- Metrics/kernel focused suite — `9 passed`.
- Full thesis suite after metrics implementation — `66 passed`.
- Private `prepare-day2-experiment` — PASS; inherited the already reviewed
  portfolio receipt metadata and emitted no private rows or paths.
- Private V1 `validate-day2` — correctly FAILED CLOSED because the original
  reviewed portfolios did not have 60 synchronized daily observations.
- Private V2 `validate-day2` — PASS with daily-primary and three portfolios.
- Private V2 `run-day2` — PASS and idempotent; run
  `day2_e77ee99b473419653d828dc0`, three output artifact digests verified,
  `effects = 0`.

## Evidence produced

- Candidate artifact v2 tests bind `artifact_id`, snapshot, `as_of`,
  minimum observations, dataset receipt, catalogue digest, deterministic
  candidate IDs, private PERMNO, missing-value counts, date-effective
  StockNames/SIC evidence, eligible CCM-link count, point-in-time fundamental
  coverage, and quality warnings.
- Candidate console evidence contains only `artifact_id`, `candidate_count`,
  `snapshot_id`, and `rows_printed = 0`; candidate files are external,
  immutable, mode `0600`, and confined beneath the supplied governed data
  root without changing pre-existing parent directory permissions.
- Candidate artifact identities are recomputed from the canonical version 2
  body. Edited rows cannot retain a stale ID, and catalogues without
  StockNames produce missing SIC/coverage warnings instead of a binder error.
- The real daily-primary acceptance snapshot produced a private version 2
  candidate artifact containing 250 deterministically ordered candidates,
  mode `0600`, with `rows_printed = 0`. The first full-view query attempt was
  stopped after exposing a multi-hour plan; the bounded implementation applies
  the deterministic candidate limit before point-in-time coverage evaluation
  and completed locally without emitting licensed rows or identifiers.
- Reviewed selections require and bind the source snapshot, UTC `as_of`,
  rationale, and warning acknowledgement. Candidate evidence later than the
  effective time is rejected before any output is written.
- Materialization tests produce only the explicitly reviewed portfolio YAML
  plus `private-instrument-map.json`, `portfolio-selection-receipt.json`, and
  `evidence-manifest.json` beneath
  `portfolio-definitions/<selection_id>/`.
- The generated test portfolio loads through the existing
  `load_portfolio` path, contains aliases rather than PERMNO/GVKEY/candidate
  IDs, and has no effects. Directories and files are mode `0700` and `0600`.
- Repeated identical execution yields byte-identical receipts; changed
  reviewed content with a new selection ID creates a distinct selection
  directory, digest, and receipt; changed existing output fails closed.
- Receipt validation rechecks the candidate artifact and requires the complete
  canonical evidence manifest, including version, publication state,
  limitations, artifact digests, and empty effects.
- The human-reviewed private acceptance selection materialized three
  fixed-quantity portfolio definitions with receipt
  `portfolio_receipt_38fae77d7b5c702a0559b0b4`; independent receipt
  validation passed with `effects = 0`. No private row, identifier map, reviewed
  YAML, generated portfolio, or receipt entered the repository.
- The local interactive wizard restores artifact metadata, displays private
  candidates by local index, requires explicit reviewer inputs and fixed
  positive integer quantities, and writes nothing until `REVIEWED` is typed.
- The three accepted Day 1 synthetic portfolio YAML files retain their exact
  pre-Day-2 SHA-256 digests.
- Metric calculations dispatch through the canonical capability registry for
  simple returns, annualized volatility, maximum drawdown, and historical
  tail risk. Fixed quantities and cash are preserved, point-in-time eligibility
  uses `available_at <= as_of`, missing values are never converted to zero, and
  every capability result must be succeeded and effect-free.
- The deterministic kernel covers `NO_ISSUE`, `REVIEW`, `URGENT_REVIEW`, and
  `ABSTAIN`; undefined required metrics force `BLOCKED / ABSTAIN`. Every
  outcome produces a human-review item and a decision point with empty effects.
- The private experiment validator rechecks reviewed source and portfolio
  receipts, source and output digests, daily-primary mode, snapshot binding,
  join quality, required prices, and the 60-observation portfolio gate.
- The selection wizard now exposes `latest_eligible_date` and an explicit
  latest-data cohort marker and rejects candidates outside that cohort for the
  Day 2 acceptance flow. It shows only that cohort by default and accepts
  optional reviewer-supplied uniform quantity and cash values to reduce manual
  entry. It still performs no ranking or automatic selection.

## Deviations

- Reviewed quantities are parsed without binary floating-point coercion and
  must be fixed positive integers, matching the authoritative integration-owned
  selection contract. Fractional, non-finite, floating-point, and non-positive
  values fail closed.
- Integration-owned Make targets for real-portfolio work remain deliberate
  failure placeholders and were not modified because the specialist lane does
  not own the root Makefile. The focused real-portfolio suite was run directly.

## Blockers

None. The original V1 selection correctly failed the frozen 60-observation
gate. A human reviewer then created `thesis-real-portfolios-v2` using only
explicit latest-data-cohort choices. The immutable V2 portfolio receipt
`portfolio_receipt_b32ae22d02471da4e6c5d966` validates with three portfolios
and zero effects. The bound private experiment validates and its deterministic
Day 2 run is complete and idempotent.

## Limitations

- Any revised selection must receive a new identity and explicit human review;
  immutable output is never overwritten.
- Candidate evidence is deterministically ordered by private PERMNO and may be
  explicitly bounded by `--limit`; it is not ranked and is never converted
  into choices.
- The accepted source profile carries SIC when available but no separate
  sector field; artifact `sector` therefore remains missing rather than being
  inferred.
- This scope contains no agent, optimizer, network provider, broker, order,
  trade, rebalance, recommendation, or portfolio mutation effect.

## Rollback

Restore the metric-stage files to `1e9583c` and restore this handoff. Any
external content-addressed test or human-run output must be reviewed and
removed separately by its exact selection or run directory; never delete a
broad data root.

## Recommended next action

Create a focused specialist candidate commit, run the exact Day 2 lane check,
and submit the candidate to integration. Integration must rerun the synthetic
suite and private V2 validation/run before advancing to Day 2 closeout.
