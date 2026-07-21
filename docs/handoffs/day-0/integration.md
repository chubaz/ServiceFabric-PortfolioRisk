# Day 0 Integration Handoff

- Lane and branch: integration / `integration/day0`
- Base: `day0-prepared` (`eedde4b2e6ed69c91f21bedb91d183b5b859af58`)
- Head: `4bd61739ebf1fa67ddc5cb73b47ffc96681daa2c` plus the intentionally uncommitted final integration diff
- Status: Waves 0A, 0B, and 0C integrated; ready to enter D0-QA; soft QA has not passed

## Merged candidates

- Domain candidate `64b1c26`, accepted by merge `cbacd7d`.
- Data candidate `e474f56`, accepted by merge `e93d660`.
- Planning candidate `7633278`, accepted by merge `da7b8fe`.
- Capabilities and agents candidate `d47c6c8`, accepted in integration history culminating at `2011caf`.
- Application candidate `e591de3`, accepted by merge `4bd6173`.

Every canonical specialist handoff was inspected before the final integration
changes. The historical application handoff's upstream dirty-tree exception
was not accepted: the pinned submodule is clean and unchanged.

## Changed paths

- Cross-package capability and application adapter fixes for effect-free draft
  status and the required hosted exposure/anomaly endpoints.
- `tests/journeys/test_day0_monitoring_journey.py` and
  `scripts/day0/run_monitoring_demo.py` for the complete synthetic monitoring
  journey, verified dataset-file lineage, bounded-as-of portfolio observations,
  and six external JSON artifacts.
- Pin-checked external ServiceFabric runtime bootstrap and lifecycle smoke
  scripts under `scripts/day0/`; local risk packages are installed as immutable
  distributions rather than editable imports.
- `Makefile`, Day 0 CI, manifest hashes, README, workplan/status records, and
  this handoff.

## Tests and commands

- `make preflight` — PASS. Repository boundary checks and the pinned upstream
  doctor passed. GitHub auth is optional for offline checks and can be required
  with `DAY0_REQUIRE_GITHUB_AUTH=1`.
- Baseline focused suites before integration: 20 domain, 15 planning, 15 data,
  10 capabilities, 9 agents, 14 application, and 8 integration tests passed.
- Post-integration focused checks: 10 capabilities, 15 application, and 1
  journey test passed.
- `make verify-day0` — PASS: 102 tests total (8 architecture, 20
  contracts/domain, 15 planning, 15 data, 10 capabilities, 9 agents, 15
  application, 8 integration, and 2 journey), followed by manifest and
  whitespace checks.
- `make demo-day0-headless` — PASS; all six required JSON artifacts were
  written beneath the external data root.
- `make servicefabric-smoke` — PASS; Text Utility and Workbench lifecycles,
  four required calls, cleanup, and post-stop rejection all passed.
- `git diff --check` — PASS.

## Evidence

- Synthetic ingestion creates a canonical `DatasetSnapshot`; the journey then
  creates a `PortfolioSnapshot` and `ExposureSnapshot` with NAV `40000.00`,
  largest position weight `0.50`, and concentration limit `0.40`.
- The retained observations produce the ALPHA anomaly; exposure produces the
  concentration finding; fictional news remains explicitly synthetic.
- Exactly four `AgentRun` records identify the Market Data, Portfolio Exposure,
  News & Sentiment, and Alert & Recommendation roles.
- The alert begins in `draft`, requires human review, has no effects, and the
  review creates a `DecisionPoint`. No order or broker object exists.
- The headless demo writes all six required JSON artifacts beneath the external
  data root with a content-digested evidence manifest. The agent receipt records
  assumptions, warnings, limitations, and output digests; the manifest retains
  the human `DecisionPoint` and review result.
- The runtime smoke validates Text Utility first and uses canonical governed
  ServiceFabric calls for `risk.workbench.status`,
  `portfolio.exposure.summarize`, `market.anomaly.detect`, and
  `alert.draft.synthesize`, followed by stop and a required failed call.

## Deviations and blockers

- The checked-out AP-01A host reviews only Text Utility. The smoke bootstrap
  copies that exact pinned host into an external venv and applies a source-hash
  checked Workbench allowlist there. No file under `vendor/servicefabric` is
  edited. General multi-application hosting remains upstream work.
- The Workbench artifact packages the reviewed knowledge-product YAML catalogue,
  so hosted `/plan` and `/research` do not depend on the repository checkout.
- A pre-existing untracked `scripts/day0/lane_helpers.sh` was present before
  this pass. It was preserved, not modified, and is outside this handoff's
  proposed changes.
- No known repository blocker remains. The local GitHub CLI credential is
  expired, so remote-only checks require reauthentication; all requested local
  gates pass without it.

## Limitations

- Synthetic-only, local-only, Python 3.11, and Linux process-host scope.
- Runtime dependency changes require a deliberate bootstrap because non-editable
  local risk distributions are frozen into the external runtime input set.
- No real providers, external LLMs, licensed data, FX conversion, broker
  connectivity, orders, trading, rebalancing, or investment advice.
- GitHub Actions runs every deterministic suite and headless journey. The full
  process-host smoke remains a documented local-only check.
- D0-QA is an entry point. This handoff does not claim soft QA passed.

## Rollback

Revert only the uncommitted integration diff, remove the external runtime venv,
`SERVICEFABRIC_HOME`, and generated portfolio-risk data root if desired, then
restore `docs/workplans/current.md` and `config/agent/day0/status.json` to the
prior Wave 0B state. Retain the pinned ServiceFabric commit and merged candidate
history.

## Soft-QA entry point and recommended next action

Begin Part 3/6 at `docs/workplans/day-0/soft-qa.md`. Review the generated
evidence and record an explicit human soft-QA decision; do not infer a pass from
automation alone.
