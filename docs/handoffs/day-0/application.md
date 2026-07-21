# Day 0 application handoff

- Lane and branch: application / `feature/day0-application`
- Base: `day0-prepared` (`5d4bb78a2c4126c7a04c0244e50ef6662cd3e0b8`)
- Head: `c05e48ce1dac06f2f5211e2f05eedd30a883f1b9` (no candidate commit created)
- Status: Wave 0B synthetic vertical-slice adapter implemented; no candidate commit created.

## Objective

Expose the integrated planning, data, domain, and capability APIs through a
reviewed, local-only FastAPI workbench without recreating their calculations.

## Changed paths

- `apps/portfolio-risk-workbench/app.py`
- `apps/portfolio-risk-workbench/pyproject.toml`
- `apps/portfolio-risk-workbench/servicefabric-package.json`
- `tests/application/test_workbench.py`
- `tests/application/conftest.py`
- `docs/handoffs/day-0/application.md`
- `vendor/servicefabric/services/application_host/servicefabric_application_host/service.py`

## Contracts consumed

- Pinned ServiceFabric Text Utility FastAPI example: reviewed adapter manifest
  structure and FastAPI/Uvicorn pins.
- ADR-0002: Python 3.11, synthetic-mode disclosure, and human-review boundary.
- `risk_planning`, `risk_data`, `risk_domain`, `risk_capabilities`, and
  `risk_agents`: immutable contracts and registered Wave 0B operations.

## Commands executed

- `make preflight` (attempted before edits)
- `make test-application` — PASS (`13 passed`)
- `scripts/day0/update_manifest_hashes.py apps/portfolio-risk-workbench/servicefabric-package.json --check` — PASS
- `git diff --check` — PASS
- Canonical ServiceFabric lifecycle test (`install`, `build`, loopback `start`,
  `risk.workbench.status` invocation, `stop`) — PASS (`1 passed`) outside the
  sandbox because the host must bind its reviewed loopback health port.

## Evidence

- All new API and action routes are covered with a temporary
  `PORTFOLIO_RISK_DATA_ROOT`; immutable ingestion, snapshot, exposure, and
  finding records are written only below that root.
- Pages expose synthetic planning, ingestion, portfolio, finding, and agent
  state while retaining the human-review and non-advisory disclosures.
- The manifest declares exactly the implemented read-only capabilities and
  remains loopback-only with non-public hosting.

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
- The application does not calculate risk itself: it adapts registered
  capability results. It provides no live providers, orders, brokers, public
  hosting, or actionable tools.

## Rollback

Remove the uncommitted lane-owned files, or revert a future focused candidate
commit. The separately authorized pre-existing ServiceFabric submodule change
must be reverted independently if its upstream review is rejected.

## Recommended next action

Review the temporary-root route coverage and manifest capability mapping, then
let integration review the lane-scoped diff and the separately dirty upstream
candidate.
