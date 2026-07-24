# Day 2–3 Part 2 monitoring-core handoff

- Lane: `monitoring-core`
- Branch: `feature/day23-monitoring-core`
- Base: Part 2 activation revision `d031002`
- Head: uncommitted working tree based on `d031002`; no commit or push was
  requested or created

## Changed paths

- `packages/risk_domain/**`
- `packages/risk_data/**`
- `packages/risk_analytics/**`
- `packages/risk_capabilities/**`
- `packages/risk_agents/**`
- `schemas/risk/**`
- `data/schemas/day23/**`
- `data/fixtures/synthetic/**`
- `tests/contracts/**`
- `tests/domain/**`
- `tests/data/**`
- `tests/analytics/**`
- `tests/capabilities/**`
- `tests/agents/**`
- `docs/handoffs/day-2-3/monitoring-core.md`

No Workbench, root dependency, Makefile, CI, shared control-plane,
integration-test, journey-test, or `vendor/servicefabric/**` path was changed.

## Delivered

- Immutable portfolio data-context contracts and construction with exact
  date-effective crosswalk matching, explicit reviewed-primary overlap
  resolution, truthful mapping coverage, and no ticker, name, fuzzy, or
  heuristic fallback.
- Point-in-time dataset selection using `available_at <= as_of`, with no
  substitution of `observed_at`, retrieval time retained as lineage rather
  than eligibility, no unpinned revision fallback, explicit missing-
  availability and stale warnings, and blocking missing required market
  observations.
- Governed local CSV and Parquet event preview/confirm/snapshot/query support,
  including reviewed Decimal ranges, deterministic duplicate versioning,
  amendment and retraction lineage, private licensed text redaction, and
  point-in-time event filtering.
- Fixed-field immutable monitoring-policy versions. Arbitrary expressions,
  Python, SQL, shell, formula, DSL input, and scheduling behavior are absent;
  cadence is descriptive metadata and human review is always required.
- Registered `portfolio.data_context.create`, `events.query.as_of`,
  `monitoring.policy.evaluate`, the internal effect-free
  `monitoring.alert.synthesize`, `monitoring.run.contextual`,
  `monitoring.report.render`, `monitoring.replay`, and `monitoring.evaluate`
  capabilities.
- Deterministic contextual monitoring through the existing Market Data,
  Portfolio Exposure, News & Sentiment, and Alert & Recommendation roles.
  Each role invokes its registered capability, and runs preserve only receipts
  derived from those completed invocations plus revisions, the four-agent
  timeline, evidence, warnings, limitations, an analytical draft alert, and
  empty effects.
- Deterministic historical replay with a new point-in-time data context at
  every step, explicit abstentions, and no current/future fallback.
- One-to-one same-instrument outcome matching, reviewed lookback and evaluation
  horizon behavior, null-and-warning undefined metrics, lead time, detection
  delay validation, coverage, sample/method disclosures, and no predictive
  claim.
- Deterministic Markdown and semantic HTML monitoring/replay reports covering
  context, policy, findings, alerts, metrics, methodology, samples,
  assumptions, warnings, limitations, evidence, human review, and empty
  effects.
- CLI commands `preview-event-export`, `confirm-event-export`,
  `create-data-context`, `validate-monitoring-policy`, `run-monitoring`,
  `run-replay`, `evaluate-replay`, and `render-monitoring-report`, all
  local-only.
- Fictional synthetic RavenPack-like CSV, Accern-like Parquet, and outcome
  fixtures. They contain no real entity, headline, or provider row.

## Tests executed

- `make preflight` — PASS after an approved network-enabled dependency
  bootstrap retry; subsequent runs are offline from the installed environment.
- `make test-d23-monitoring-core` — PASS, 143 tests.
- Existing core package tests:
  - Day 0 domain/contracts — PASS, 29 tests.
  - Data — PASS, 60 tests.
  - Capabilities — PASS, 18 tests.
  - Agents — PASS, 15 tests.
  - Day 1 data — PASS, 60 tests.
  - Analytics — PASS, 21 tests.
  - Day 1 capabilities/agents — PASS, 33 tests.
- `make verify-d23-phase1` — PASS, including architecture, Day 0, Day 1,
  application, integration, journey, Part 1 control-plane, data, experience,
  integration, and journey gates.
- `git diff --check` — PASS.

## Evidence produced

- Generated domain schemas under `schemas/risk/v0.1/**`, analytics report
  schemas under `schemas/risk/analytics/v0.1/**`, and event schemas under
  `data/schemas/day23/**`.
- Focused tests cover exact mapping and overlap rejection, missing mappings and
  coverage, no-look-ahead selection, stale/missing data, CSV/Parquet event
  preview, availability filtering, duplicates, amendments, retractions,
  licensed-text redaction, immutable fixed policies, the four-agent run,
  evidence enforcement, effect-free alerts, replay discipline and abstention,
  one-to-one evaluation, null undefined metrics, lead/detection timing,
  deterministic reports/digests, and prohibited network, external-LLM, broker,
  order, trade, rebalance, and optimization paths.
- Capability receipts, context digests, immutable policy revisions, replay
  step digests, evaluation digests, and report digests provide deterministic
  review anchors.

## Review defects resolved

- Four-agent receipts now come from completed registered invocations. Registry
  history records context creation, event query, policy evaluation, alert
  synthesis, and contextual-run assembly; replay uses the same registered
  workflow at every step.
- Policy evaluation computes observation age against the immutable policy
  version's stale-data maximum rather than reusing the context warning limit.
- Point-in-time observation eligibility uses `available_at` only.
  `retrieved_at` remains auditable local lineage and may follow a historical
  replay timestamp.
- Supplied observations with missing `available_at` produce an explicit
  quality issue even when an older eligible observation remains usable.
- Replay specifications pin market, crosswalk, optional fundamental, and
  optional event revisions, and every step must match those exact identities.
- `create-data-context`, `run-monitoring`, `run-replay`, `evaluate-replay`, and
  `render-monitoring-report` CLI execution routes through registered
  capabilities and their evidence/status/effect boundaries.
- Every date-effective mapping identifies its exact crosswalk snapshot and
  revision; mismatched records are rejected before context construction.
- The event record and generated schema expose the frozen `local_event_id`
  field. `event_id` remains only a non-serialized compatibility accessor.

## Deviations

- None from monitoring-core scope. No new agent role, dependency, network
  provider, background scheduler, arbitrary-expression surface, external LLM,
  consequential effect, PDF, publication path, or notebook execution was
  added.

## Blockers

- None within the monitoring-core lane.

## Limitations

- The required reviewed synthetic Parquet fixture conflicts with the legacy
  integration-owned architecture assertion that prohibits every tracked
  `*.parquet` path. The current regression gate passes because this work is
  intentionally uncommitted. Before accepting the fixture into Git,
  integration must narrow that assertion to allow exactly
  `data/fixtures/synthetic/day23/accern-like-events.parquet`; monitoring-core
  cannot edit `tests/architecture/**`.
- The integration-owned root ignore rules cover `data/*`. The generated event
  schemas were marked intent-to-add only so they are visible for review; the
  accepting authority must force-add the reviewed `data/schemas/day23/**`
  files.
- Monitoring and replay are explicit foreground invocations. Cadence remains
  metadata and no scheduler is provided.
- Evaluation is descriptive for the supplied labelled sample and methodology;
  it makes no predictive or investment-performance claim.

## Rollback

Restore the modified public exports, registries, CLI, role grants, schema
indexes, focused tests, and synthetic README, then remove the new monitoring,
event, portfolio-context, report, generated-schema, fixture, test, and handoff
files listed above. No external provider, broker, order, trade, or mutable
remote state requires rollback.

## Recommended next action

Integration should review the immutable contracts and deterministic digests,
narrow the tracked-Parquet architecture guard to this one reviewed synthetic
fixture, force-add the reviewed ignored schemas, and rerun
`make test-d23-monitoring-core` plus the Part 2 integration gate before
accepting the candidate changes.
