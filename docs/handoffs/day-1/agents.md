# Day 1 capabilities and agents handoff

## Lane, branch, base, and head

- Lane: capabilities and agents
- Branch: `feature/day1-agents`
- Base: accepted domain-analytics integration commit `72a878764b1f721a1c2c9b5c3a172e42d339d1b2`
- Head: `72a878764b1f721a1c2c9b5c3a172e42d339d1b2` with the requested candidate changes left uncommitted

## Changed paths

- `packages/risk_capabilities/**`: typed immutable requests and effect-free registered handlers for simple/log returns, annualized volatility, maximum drawdown, historical VaR, historical expected shortfall, deterministic scenarios, contribution summaries, and Markdown/HTML report rendering. Capability envelopes preserve evidence digests, exact methodology, assumptions, warnings, limitations, human-review state, and analytics output digests.
- `packages/risk_agents/**`: the same four role cards with reviewed Day 1 grants, immutable `AgentTimeline`, `AgentTimelineStep`, `CapabilityReceipt`, and `ReviewCheckpoint` contracts, and deterministic four-role orchestration through `RegisteredCapabilityAgent` and `CapabilityRegistry` only.
- `tests/capabilities/**`: unique-ID, typed-validation, exact-methodology, tail-warning, descriptive-scenario, contribution-reconciliation, report-review, evidence, digest, and prohibited-effect coverage.
- `tests/agents/**`: deterministic sequence/digest/receipt/review timeline coverage, failed-step preservation, exact four-role coverage, no execution surface, role safety grants, and existing monitoring regression coverage.
- `docs/handoffs/day-1/agents.md`: this handoff.

No application, root dependency, CI, shared lifecycle, schema snapshot, provider, or ServiceFabric submodule path was changed.

## Tests executed

- `make preflight` — PASS: environment, repository, ServiceFabric doctor, and diff checks passed.
- `PIP_NO_INDEX=1 DAY1_VENV=/home/lorenzoccasoni/servicefabric-lab/state/venvs/day1 make test-day1-agents` — PASS initially; final focused rerun passes 28 capability and agent tests after review fixes.
- `PIP_NO_INDEX=1 DAY0_VENV=/home/lorenzoccasoni/servicefabric-lab/state/venvs/day0 make test-agents` — PASS initially; final regression rerun passes 14 agent tests, including the existing Day 0 deterministic monitoring workflow.
- `git diff --check` — PASS before the handoff update and required again as the final check.

## Evidence produced

- The finite registry exposes the nine requested analytics capability IDs exactly once and validates each request against its immutable Pydantic contract before dispatch.
- Known synthetic observations prove exact analytics methodology propagation and show that capability output digests equal the immutable `risk_analytics` result digests.
- Historical VaR and expected-shortfall receipts preserve the `inadequate-tail-sample` warning instead of treating an incomplete sample as zero or success without qualification.
- Scenario evidence remains a linear descriptive shock with no pricing model, optimization, hedge recommendation, or transaction effect.
- Contribution evidence reconciles weighted constituent returns, contribution sum, and supplied portfolio return.
- Report evidence proves deterministic Markdown and semantic HTML come from `risk_analytics.render_report`, retain the source digest, and require human review. PDF and notebook execution are absent.
- The four-agent timeline proves caller-supplied UTC timestamps, contiguous deterministic sequence, stable input/output digests, retained evidence and disclosures, empty effects, and explicit pending review checkpoints.
- Serialized run requests round-trip through JSON into capability-specific immutable request models and execute successfully; the plan contract rejects a fifth step and rejects duplicate role identities.
- Role cards retain the input contracts for every legacy grant alongside the new analytics request contracts.
- Injected capability failures remain failed timeline steps with their warning and a deterministic receipt digest; they are not converted to success or zero.
- Source and role-boundary checks show no external LLM, provider call, broker, order, trade, rebalance, optimization, or hedge execution surface.

All analytical and news observations used by focused tests are explicitly labelled reviewed synthetic fixtures.

## Deviations

- Integration-owned lifecycle files still identify Wave 1B as current and Wave 1C as queued. The user explicitly authorized this agents-lane work after the accepted domain-analytics merge; this lane did not edit the lifecycle control plane.
- The user explicitly requested no commit or push, overriding the standard candidate-commit step. All changes remain uncommitted for review.
- Historical VaR and expected shortfall use the approved shared `HistoricalTailRiskResult`; the two registered IDs expose the same reviewed nearest-rank/tail-mean calculation without duplicating it.

## Blockers

No implementation blocker remains. Integration still owns lifecycle advancement, candidate acceptance, cross-lane Wave 1C verification, and merge decisions.

## Limitations

- The orchestration consumes only caller-supplied immutable requests and timestamps. It does not fetch data, call providers, invoke an external LLM, or construct missing observations.
- The News & Sentiment Agent retains the existing explicitly synthetic event classification as context only.
- Analytics are descriptive and evidence-bound. The Alert & Recommendation Agent may render review material and suggest investigation, scenario analysis, or monitoring, but cannot optimize, trade, hedge, rebalance, submit an order, or create any external effect.
- Human review checkpoints are pending until an explicit reviewer decision is recorded. Report creation is not approval for a consequential action.
- PDF generation and notebook execution are not implemented.

## Rollback

Discard only the uncommitted agents-lane paths listed above. No data migration, immutable snapshot, generated schema, application state, provider state, root dependency, ServiceFabric pin, or lifecycle record requires rollback.

## Recommended next action

Integration should review the nine capability registrations, four unchanged role identities, canonical invocation history, timeline failure semantics, report review boundary, focused test evidence, and final diff check; then accept or reject the uncommitted candidate without merging from this specialist lane.
