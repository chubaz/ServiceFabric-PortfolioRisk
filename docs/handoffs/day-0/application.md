# Day 0 application handoff

- Lane and branch: application / `feature/day0-application`
- Base: `day0-prepared` (`5d4bb78a2c4126c7a04c0244e50ef6662cd3e0b8`)
- Head: `c05e48ce1dac06f2f5211e2f05eedd30a883f1b9` (no candidate commit created)
- Status: Wave 0C review-bound dashboard and monitoring adapter implemented; no candidate commit created.

## Objective

Provide a reviewed, loopback-only FastAPI Portfolio Risk Workbench shell for
local synthetic-prototype navigation and the read-only
`risk.workbench.status` capability.

## Changed paths

- `apps/portfolio-risk-workbench/app.py`
- `apps/portfolio-risk-workbench/pyproject.toml`
- `apps/portfolio-risk-workbench/servicefabric-package.json`
- `tests/application/test_workbench.py`
- `docs/handoffs/day-0/application.md`
- `vendor/servicefabric/services/application_host/servicefabric_application_host/service.py`

## Contracts consumed

- Pinned ServiceFabric Text Utility FastAPI example: reviewed adapter manifest
  structure and FastAPI/Uvicorn pins.
- ADR-0002: Python 3.11, synthetic-mode disclosure, and human-review boundary.

## Commands executed

- `make preflight` (attempted before edits)
- `make test-application` — PASS (`13 passed`)
- `scripts/day0/update_manifest_hashes.py apps/portfolio-risk-workbench/servicefabric-package.json --check` — PASS
- `git diff --check` — PASS
- Canonical ServiceFabric lifecycle test (`install`, `build`, loopback `start`,
  `risk.workbench.status` invocation, `stop`) — PASS (`1 passed`) outside the
  sandbox because the host must bind its reviewed loopback health port.

## Evidence

- Every page identifies Wave 0A as a local synthetic prototype and explicitly
  rules out live data, live trading, broker connectivity, and investment advice.
- The manifest declares only the read-only status capability and loopback-only,
  non-public hosting through `reviewed-fastapi-v1`.

## Deviations, blockers, and limitations

- Application source and tests remain within lane scope; the upstream-host
  exception below was explicitly authorized to resolve the runtime defect.
- The pinned ServiceFabric host hard-coded the Text Utility package and could
  not install this reviewed manifest. With explicit user authorization, its
  reviewed package and capability allowlists were extended only for this
  workbench; the ServiceFabric submodule is therefore intentionally dirty and
  must be reviewed as an upstream candidate rather than accepted as a normal
  application-lane change.
- `make preflight` is blocked in `env-check` by an expired local GitHub CLI
  token; this is an environment issue, not an application change.
- This wave provides no portfolio calculations, providers, or actionable tools.

## Rollback

Remove the uncommitted lane-owned files, or revert a future focused candidate
commit. No shared configuration or ServiceFabric vendor files changed.

## Recommended next action

Run the focused application tests and manifest-hash check, then let integration
review the lane-scoped diff and accept a focused candidate commit.

## Wave 0C update

- Added local synthetic dashboard cards, catalogue-only research and notebook
  pages, alert and agent-run APIs, and review-bound monitoring actions.
- Alert reviews require a reviewer and one explicit decision; each stores an
  immutable `DecisionPoint` below `PORTFOLIO_RISK_DATA_ROOT` and has no effects.
- The adapter delegates news classification, alert synthesis, review, and
  monitoring orchestration to integrated capability and agent packages.
- Focused tests cover all pages, monitoring, alert detail, every review outcome,
  missing-reviewer rejection, empty effects, synthetic disclosure, route safety,
  and manifest hashes.
