# Day 1 Experience Handoff

## Wave 1C — risk analysis and explainability

### Lane, branch, base, and head

- Lane: `experience`; branch: `feature/day1-experience`.
- Base and current head: `1a4dd29d3663502fcc6e7bbe9adaf499b27bb42a` (`Merge branch 'feature/day1-agents' into integration/day1`).
- Candidate state: uncommitted and unstaged, with no push or specialist merge, as explicitly requested.
- Date: 2026-07-22.

### Changed paths

- `apps/portfolio-risk-workbench/{app.py,analysis_service.py,presentation.py,pyproject.toml,risk-package-lock.json,servicefabric-package.json}`
- `apps/portfolio-risk-workbench/static/workbench.css`
- `apps/portfolio-risk-workbench/templates/{risk,report,agents,agent_runs,components}.html`
- `tests/application/{conftest.py,test_workbench.py}`
- `docs/handoffs/day-1/experience.md`

No path outside the experience lane allowance and this exact handoff was changed. Root configuration, shared wave state, other lane packages/tests, and `vendor/servicefabric/**` remain untouched.

### Delivered behavior and evidence

- Replaced the Wave 1C placeholder with a semantic, server-rendered Risk screen. It provides an immutable portfolio-snapshot selector; a methodology selector containing only the eight reviewed registered analytics capabilities; reviewed confidence values `0.90`, `0.95`, and `0.99`; and the three fixed scenario examples `broad_market_minus_10`, `concentrated_holding_minus_20`, and `rates_sensitive_assets_minus_5`.
- Renders simple/log returns, annualized volatility, maximum drawdown, historical VaR, historical expected shortfall, contributions, and fixed scenarios as readable metrics with horizon, sample, observation count, methodology, assumptions, warnings, limitations, evidence, output digest, pending human review, and empty effects. The return path uses local CSS with signed text/pattern state plus an underlying accessible table; there is no remote chart dependency or color-only state.
- Displays the inadequate historical-tail sample warning as a prominent `role="alert"` result disclosure on both tail methods. It explicitly rejects prediction and certainty claims and is also preserved in the evidence drawer and generated report contract.
- Shows every fixed catalogue shock in a readable table and the selected scenario's exact shocks separately. No free-form scenario language or hedge, trade, rebalance, order, optimization, broker, or portfolio-effect surface was added.
- Added `analysis_service.py` as the presentation-facing coordination seam. It constructs typed requests and invokes only the integrated `CapabilityRegistry`, `DeterministicAnalysisOrchestrator`, and `risk.report.render` capability. Analytics arithmetic remains wholly in `risk_analytics`/registered capability handlers and is absent from route functions.
- Review remediation bounds both the analytics observation set and its evidence digest to the selected immutable snapshot's `as_of` timestamp, preventing look-ahead and later fixture additions from changing an older snapshot's inputs.
- Review remediation makes the fixed broad-market shock apply its reviewed `-10%` only to instruments actually present in the selected snapshot. Instrument-specific scenarios are intersected with the snapshot and return an explicit unavailable state when no reviewed shock applies; unknown scenario IDs are rejected and never substituted with a default. The one-position personal fixture now completes all four timeline receipts.
- Expanded the Agent screen with the integrated four-step `AgentTimeline`: ordered sequence, role, capability receipt, methodology, evidence, assumptions, warnings, limitations, output digest, status, pending review checkpoint, and explicit empty effects. Timeline history remains available alongside prior monitoring runs.
- Added human-readable `GET /reports/{method_id}` HTML and downloadable `GET /reports/{method_id}.md` Markdown. Both retain immutable report/source digests, evidence, profile state, synthetic/local state, and pending review disclosure. PDF and notebook execution are absent. Personal-profile reports show publication unavailable, and no publication action exists.
- Added typed `GET /api/risk/analyses`, `GET /api/risk/analyses/{method_id}`, `GET /api/agent-timelines`, and `GET /api/reports` response contracts while preserving every prior JSON endpoint.
- Collection APIs translate invalid methodology/confidence/scenario/snapshot queries and missing personal-snapshot states into deliberate HTTP 422 responses rather than server errors.
- Declared fixed ServiceFabric action paths for the eight reviewed analytics capabilities and report renderer; tests prove manifest tool IDs match routes and every result has empty effects. No arbitrary function-invocation endpoint exists.
- Updated the hosted app package lock with the reviewed `risk_analytics` digest and refreshed the accepted integrated `risk_agents`/`risk_capabilities` digests. Added `risk-analytics==0.1.0` to the app-local package metadata and refreshed every application source hash.

### Tests executed

- `make preflight` — PASS.
- `PIP_NO_INDEX=1 .venv-day1/bin/pytest -q tests/application/test_workbench.py` — PASS, 71 tests.
- Day 1 environment with all repository test directories — PASS, 244 tests.
- `PIP_NO_INDEX=1 make verify-wave-1c` — PASS, including Wave 1A, Wave 1B, Day 0 regressions, 71 application tests, 14 analytics tests, 28 capability/agent tests, integration, journeys, planning/research, data, contracts/domain, architecture, environment checks, manifest validation, and `git diff --check`.
- `.venv-day1/bin/python scripts/day0/update_manifest_hashes.py apps/portfolio-risk-workbench/servicefabric-package.json --check` — PASS.
- `git diff --check` — PASS.
- `PIP_NO_INDEX=1 make servicefabric-day1-smoke SERVICEFABRIC_RUNTIME_VENV=/tmp/servicefabric-wave1c-runtime SERVICEFABRIC_HOME=/tmp/servicefabric-wave1c-home PORTFOLIO_RISK_DATA_ROOT=/tmp/servicefabric-wave1c-data` — BLOCKED before startup as described below; no smoke assertion ran.

Application evidence covers every requested methodology, selected metadata, primary tail warning, exact scenario shocks, accessible visual/table parity, four roles and capability receipts, empty effects, HTML/Markdown reports, personal-profile publication denial, API preservation/typing, semantic HTML primacy, prohibited-route absence, package hashes, and capability path matching. Review regressions additionally cover snapshot as-of cutoffs, cutoff-bound evidence, one-position personal scenarios and four-step timelines, incompatible and unknown scenario rejection, and controlled collection-API validation/empty states.

### Deviations, blockers, and limitations

- `docs/workplans/current.md` is integration-owned and still identifies Wave 1B while describing Wave 1C as queued. The explicit assignment and integrated Wave 1C contracts were used without modifying that shared lifecycle pointer.
- Hosted smoke is integration-blocked: `scripts/day0/bootstrap_servicefabric_runtime.py` still computes an exact lock from the pre-Wave-1C package tuple and neither digests nor installs `packages/risk_analytics`. It therefore rejects the correctly expanded `risk-package-lock.json` with `risk-package-lock.json does not match reviewed local package sources`. Integration must add `risk_analytics` to that reviewed local-package tuple and rebuild the hosted runtime before smoke can start. The experience lane is prohibited from changing that script.
- Reports are local review artifacts only. No PDF, publishing, notebook execution, external provider/LLM, broker connectivity, order, trade, hedge, optimization, or rebalancing path exists.
- Historical metrics remain descriptive and sample-bound; the reviewed fixture intentionally produces an inadequate-tail warning. Scenario results are fixed linear shocks without a pricing model. Browser, keyboard, screen-reader, and visual soft QA remain integration activities beyond automated semantic/accessibility assertions.

### Rollback and recommended next action

Rollback is a focused restoration of the Wave 1C Workbench adapter/service, templates, CSS, app package metadata/lock/manifest, application tests, and this Wave 1C handoff section to `1a4dd29`. No schema, analytics package, immutable portfolio snapshot, or external state migration is required; generated local test records can be discarded with their temporary data roots.

Recommended next action: integration reviews the uncommitted candidate, updates the integration-owned hosted bootstrap to include the reviewed `risk_analytics` package, refreshes the hosted runtime, runs `servicefabric-day1-smoke`, and then performs browser/keyboard/screen-reader soft QA before accepting Wave 1C. Do not merge from this specialist lane.

## Wave 1B supplement — parallel presentation pass

### Lane, branch, base, and head

- Lane: `experience`; branch: `feature/day1-experience`.
- Base and current head: `8cf77e5` (`chore(day1): close Wave 1A gate`).
- Candidate state: uncommitted, with no push or specialist merge, as required.

### Changed paths

- `apps/portfolio-risk-workbench/app.py`
- `apps/portfolio-risk-workbench/workspace_service.py`
- `apps/portfolio-risk-workbench/servicefabric-package.json`
- `apps/portfolio-risk-workbench/templates/{portfolio,data,providers,settings,portfolio_import,portfolio_preview,portfolio_snapshots,portfolio_snapshot,portfolio_compare}.html`
- `tests/application/test_workbench.py`
- `docs/handoffs/day-1/experience.md`

### Delivered presentation and route boundary

- Added semantic Portfolio import, preview, immutable-snapshot history/detail, and explicit-ID comparison screens, plus all requested HTML and developer API route boundaries.
- Import uses `UploadFile`, accepts only CSV/YAML filename formats, rejects a declared upload larger than 1 MiB, accepts no filesystem path, and never reads, parses, stores, or displays raw input in the application.
- Preview presentation reserves format, digest, validation issues, quality flags, and a checkbox-plus-digest confirmation control. Invalid previews have no confirmation control; existing snapshots have no edit or delete control.
- Expanded Portfolio, Data, Providers, and Settings to show readable holdings/history, fixed query manifests, dataset/provenance/rights states, a disabled external-provider catalogue, and opaque secret-reference examples.
- Added `workspace_service.py` as the only Workbench-to-data-service adapter. It binds typed `PortfolioInputService`, `PortfolioSnapshot`, `SnapshotComparison`, `ProviderCatalogueEntry`, and `FixedQueryManifest` values without duplicating their business logic.
- Replaced temporary unavailable route stubs with end-to-end preview, typed reload, confirmation, immutable snapshot, idempotency, correction, comparison, provider catalogue, and fixed-manifest flows. Raw upload bytes remain in memory and are never persisted by the app.
- Browser confirmation and comparison fields bind from form bodies; import is forced to the `personal_portfolio` profile; provider and manifest metadata are rendered from reviewed typed catalogue records.
- Review remediation installs a request-level bounded multipart parser that rejects file bytes before they can be queued or spooled, rejects YAML documents whose embedded profile is not `personal_portfolio` before preview persistence, and renders comparison-storage failures through the semantic HTML error state.

### Tests and evidence

- `make preflight` — PASS.
- `.venv-day1/bin/pytest -q tests/application/test_workbench.py tests/integration/test_day1_wave1a.py tests/data` — PASS, 81 tests.
- Day 0 monitoring regression using the existing locked Day 1 environment and explicit package paths — PASS, 2 tests.
- `scripts/day0/update_manifest_hashes.py apps/portfolio-risk-workbench/servicefabric-package.json --check` — PASS.
- `git diff --check` — PASS.
- `make verify-day1-current` — preparation and preflight stages passed, then Wave 1A bootstrap was blocked by package-index DNS while attempting to fetch pinned `certifi`; no application test failure was observed.

### Deviations, blockers, limitations, rollback, next action

- This was intentionally a presentation-only parallel pass. Functional preview parsing, validation, immutable persistence, confirmation digest checks, comparison results, data catalogue binding, and provider records remain exclusively data-lane work.
- The user-requested functional test matrix cannot be claimed until the data candidate is integrated. The application tests cover route shape, semantic forms, safety disclosures, absence of arbitrary SQL, and the isolated seam only.
- No raw portfolio input, provider extract, local database, secret, or provider endpoint was added to Git.
- Rollback is a focused revert of the Wave 1B application adapter/templates/tests and manifest changes. Existing immutable data-root records are not mutated or deleted by rollback.
- Recommended next action: integration runs the complete Wave 1B functional matrix and clean hosted-runtime/browser/keyboard/assistive-technology soft QA.

## Lane and branch

- Lane: `experience`
- Branch: `feature/day1-experience`
- Scope: Wave 1A human-readable Workbench
- Date: 2026-07-22

## Base and head

- Accepted integration base: `c76c7daa83c99a4692001189afa1a74ee4554dac`
- Current Git HEAD: `c76c7daa83c99a4692001189afa1a74ee4554dac`
- Candidate state: uncommitted working tree, as explicitly requested; no commit, push, or specialist merge was created.
- Base update: the feature branch was fast-forwarded to the already-accepted knowledge merge before catalogue binding.

## Changed paths

- `apps/portfolio-risk-workbench/app.py`
- `apps/portfolio-risk-workbench/presentation.py`
- `apps/portfolio-risk-workbench/pyproject.toml`
- `apps/portfolio-risk-workbench/servicefabric-package.json`
- `apps/portfolio-risk-workbench/catalog/{research,notebooks}.yaml`
- `apps/portfolio-risk-workbench/seed/knowledge-products/day-1/*.yaml`
- `apps/portfolio-risk-workbench/static/workbench.css`
- `apps/portfolio-risk-workbench/templates/*.html`
- `tests/application/test_workbench.py`
- `docs/handoffs/day-1/experience.md`

No path outside the experience lane allowance and this exact handoff was changed by the candidate working tree. `vendor/servicefabric/**` was not modified.

## Delivered behavior

- Replaced generic JSON page rendering with Jinja2 semantic HTML and local responsive CSS.
- Added the complete global navigation, skip link, semantic landmarks, visible focus treatment, and persistent profile, data-state, freshness, and human-review badges.
- Added reusable metrics, badges, tables, finding and alert cards, disclosures, empty/error states, evidence drawers, review forms, and accessible CSS visual summaries.
- Added all required Dashboard, Portfolio, Risk, Findings, Alerts, Data, Providers, Research, Notebooks, Agents, Plan, and Settings screens while retaining the Agent Runs evidence view.
- Preserved every Day 0 `/api` and `/actions` route and the existing ServiceFabric capability declarations.
- Kept research as the default profile and implemented `personal_portfolio` as request-local presentation state with private/local/no-publication disclosures only.
- Bound Plan, Research, and Notebooks to the integrated immutable `risk_planning` contracts. Hosted catalogue copies exactly match the reviewed repository sources and are declared in the application manifest.
- Kept notebooks catalogue-only, providers disabled, and review decisions effect-free. Added no provider enablement, notebook execution, arbitrary SQL, broker, order, trade, or rebalance route.
- Bound Wave 1B portfolio/data workspace behavior to the integrated typed data service; Wave 1C analytics remain unavailable by design.
- Renders research and notebook evidence title, URI/reference, and relevance as explicit readable fields rather than falling back to a raw mapping representation.
- Distinguishes a missing alert (404) from unavailable local alert storage (for example, 409), preserving the original status without claiming absent evidence.
- Treats an empty observation result as unavailable evidence and never renders it as an established zero-row dataset summary.

## Tests executed

- `make preflight` — environment check PASS and repository check PASS; dependency bootstrap could not complete because sandbox network installation was denied.
- `PIP_NO_INDEX=1 DAY1_VENV=/tmp/day1-validation-venv make test-day1-experience` — PASS, 42 tests.
- `PIP_NO_INDEX=1 DAY0_VENV=/tmp/day1-validation-venv make test-application` — PASS, 42 tests, using the already provisioned locked Day 1 validation environment so Jinja2 and form parsing are present.
- `python3 scripts/day0/update_manifest_hashes.py apps/portfolio-risk-workbench/servicefabric-package.json --check` — PASS.
- `git diff --check` — PASS.

## Evidence produced

- Application tests cover semantic HTML and heading order on every page, full navigation and persistent badges, keyboard labels and focus CSS, responsive/local assets, both profiles, profile-filtered catalogues, empty and error states, and missing-value formatting.
- Regression tests verify readable catalogue evidence fields, distinct 404 and unavailable alert states, and explicit handling of an empty observation result.
- Tests cover Day 0 snapshot/exposure content, findings and alerts, effect-free review actions and form submission, all four agent roles, both planning epochs, and reviewed research/notebook catalogue metadata.
- Route inventory tests prove there is no notebook execution, provider enablement, broker, order, trade, or rebalance route.
- Manifest tests prove every template, stylesheet, presentation module, and hosted catalogue file is declared and every SHA-256 digest matches.
- Packaged catalogue tests prove byte-for-byte equality with `docs/research/catalog.yaml`, `notebooks/catalog/catalog.yaml`, and `seed/knowledge-products/day-1/*.yaml`.

## Deviations

- No progressive-enhancement JavaScript was added because every required interaction is usable with server-rendered HTML and standard form submission.
- The standard preflight dependency bootstrap was not rerun with network access after escalation was rejected. Required tests instead used an existing environment that satisfies the checked-in locked requirements with `PIP_NO_INDEX=1`.
- No candidate commit was created because the task explicitly prohibited commits.

## Blockers

- Canonical runtime dependency installation remains integration-blocked. `scripts/day0/bootstrap_servicefabric_runtime.py` and `verify-day0` install `requirements/day0.lock`, which does not contain Jinja2 or python-multipart and does not install the app-local `pyproject.toml`. A clean canonical runtime therefore cannot import this Wave 1A application.
- The required fix is integration-owned: add the reviewed UI dependencies to the lock used by the canonical runtime and Wave 1A verification (or update those integration paths to install `requirements/day1.lock`), regenerate hashes, and verify both clean runtime bootstrap and `verify-wave-1a`. The experience lane must not modify root requirement locks, the root Makefile, or shared bootstrap scripts.
- Full network-backed bootstrap evidence remains unavailable in this sandbox.

## Limitations

- Profile selection is query-string presentation state only and is intentionally not persisted.
- The Wave 1B data service is integrated and exercised end-to-end; no application-owned parsing, persistence, comparison, provider, SQL, broker, order, trade, or rebalance logic was added.
- VaR, expected shortfall, stress, scenario, correlation, contribution, and other risk analytics remain Wave 1C work; the Risk screen makes no methodology claim for them.
- External providers and notebook execution remain disabled in every profile.
- Browser-specific visual and assistive-technology QA remains an integration/soft-QA activity; focused tests validate the rendered contracts and accessibility primitives.
- Hosted catalogue copies must continue to be synchronized from the reviewed knowledge sources when those source records change.

## Rollback

Restore the modified Workbench app files and `tests/application/test_workbench.py` to the accepted integration base, remove the added app-local catalogue, template, stylesheet, presentation, and Day 1 seed files, and remove this handoff. No data migration or external rollback is required; persisted Day 0 evidence contracts were not changed.

## Recommended next action

Integration should run the complete Wave 1B functional matrix, clean runtime/bootstrap, and browser/keyboard/assistive-technology soft QA. Do not begin Wave 1C analytics through this lane.
