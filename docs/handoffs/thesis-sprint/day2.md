# Thesis Sprint Day 2 specialist handoff

## Lane and branch

- Lane: `day2`
- Branch: `feature/thesis-day2`
- Base and working-tree HEAD: `5815e81`
  (`chore(thesis): align Day 2 with accepted data bridge`)
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

## Deviations

- Reviewed quantities are parsed without binary floating-point coercion and
  must be fixed positive integers, matching the authoritative integration-owned
  selection contract. Fractional, non-finite, floating-point, and non-positive
  values fail closed.
- Integration-owned Make targets for real-portfolio work remain deliberate
  failure placeholders and were not modified because the specialist lane does
  not own the root Makefile. The focused real-portfolio suite was run directly.

## Blockers

None. The private reviewed selection, three generated definitions, immutable
receipt, and receipt validation are complete.

## Limitations

- Any revised selection must receive a new identity and explicit human review;
  immutable output is never overwritten.
- Candidate evidence is deterministically ordered by private PERMNO and may be
  explicitly bounded by `--limit`; it is not ranked and is never converted
  into choices.
- The accepted source profile carries SIC when available but no separate
  sector field; artifact `sector` therefore remains missing rather than being
  inferred.
- This scope contains no metric, finding, decision kernel, agent, optimizer,
  network provider, broker, order, trade, rebalance, recommendation, or
  portfolio mutation effect.

## Rollback

Restore the modified `risk_data` and thesis example files to `5815e81`, remove
only the newly added selection example, materialization module and focused
test file, and restore this handoff. Any external content-addressed test or
human-run output must be reviewed and removed separately by its exact
selection directory; never delete a broad data root.

## Recommended next action

Create a focused candidate commit, run the lane allowlist gate for that exact
head, and submit it to integration for acceptance. Stop before metrics or
decision-kernel work.
