# Day 2–3 integration handoff — Part 2 accepted; Part 3 queued

## Lane and branch

- Lane: `integration`
- Branch: `integration/day2-3`
- Base: `day1-complete` (`627a08b`)
- Committed integration base: `560d069`
- Head: working tree includes the integration changes below; no merge or push
- Lifecycle: Part 1 complete; Part 2 complete; Part 3 queued; soft QA queued
- QA result: no human QA-pass, release, or merge claim

## Accepted resolution

Experience candidate `4403c37` is accepted. It removes the rejected tracked
fixture duplicates and adds `stage_package.py`, which copies only the four
allow-listed canonical files from `data/fixtures/synthetic/day23/**` into an
ephemeral package and regenerates its complete source digest manifest.

Integration added the staged-manifest host bootstrap adapter. It runs the
normal pinned Day 1 runtime bootstrap, rebuilds the application host from the
read-only `vendor/servicefabric/**` source, applies the staged manifest through
the existing strict host patcher, and reinstalls only that copied host package.
The smoke installs the staged package; it does not copy fixtures ad hoc or
weaken ServiceFabric validation.

## Changed paths

- `apps/portfolio-risk-workbench/**`: accepted staging/runtime corrections
- `scripts/day23/bootstrap_staged_servicefabric_runtime.py`
- `scripts/day23/servicefabric_part2_smoke.sh`
- Part 2 demo, journey, Makefile, CI, architecture tests, lifecycle records,
  README, active workplans, and this handoff
- No `vendor/servicefabric/**` path changed

## Tests executed

- Application suite: `89 passed`.
- Focused experience suite: `7 passed`.
- Integration and architecture closure suite: `47 passed`.
- Part 2 deterministic demo: PASS.
- `make verify-d23-current`: PASS, including Day 0, Day 1, Part 1, Part 2,
  application manifest, lane, journey, and whitespace gates.
- `make servicefabric-d23-part2-smoke`: PASS with the configured external
  runtime venv and local state root.
- `git diff --check`: PASS.
- Application manifest hash check: PASS.

## Evidence produced

The deterministic Part 2 evidence bundle remains beneath the configured local
`PORTFOLIO_RISK_DATA_ROOT/day23-part2` state root. It includes the evidence
manifest and thirteen digested siblings for context, event import/snapshot,
policy, monitoring run, findings, alert draft, agent timeline, replay,
evaluation, and Markdown/HTML reports.

The hosted smoke independently staged and checked the generated manifest,
validated the pinned Text Utility baseline, installed and built the staged
Workbench, exercised all seven Part 2 capabilities, verified empty effects and
explicit human review, verified stop/post-stop rejection and process cleanup,
and confirmed pinned-upstream immutability.

## Deviations

- The initial accepted Workbench merge omitted hosted monitoring resources.
- Rejected correction `ba6aa12` used duplicate tracked fixtures and was not
  accepted.
- The compliant correction stages canonical fixtures ephemerally and embeds
  the staged manifest in a copied host package at bootstrap time.
- Lifecycle advanced to `D23-PART-3` only after the complete Part 2 gate passed.

## Blockers

None for Part 2 integration. Part 3 remains a deliberate human-review gate;
it must inspect the evidence manifest and make the release/merge decision.

## Limitations

- All observations and outcome labels are fictional synthetic local data.
- Evaluation is descriptive for a small labelled sample and makes no
  predictive or investment-performance claim.
- Cadence remains metadata only; monitoring and replay are foreground actions.
- Human review remains required, and no alert authorizes a transaction or
  portfolio effect.

## Rollback

Revert the uncommitted integration changes and omit candidate `4403c37` if the
release review rejects this integration. Preserve canonical fixtures under
`data/fixtures/synthetic/**` and the pinned ServiceFabric tree. Ephemeral
staged packages and external evidence/runtime state can be discarded separately.

## Recommended next action

Begin `docs/workplans/day-2-3/part-3-final-qa-release.md`: review the local
evidence manifest and reports, perform final human QA, and make the explicit
release and merge decision. Do not claim Part 3 complete from these automated
gates alone.
