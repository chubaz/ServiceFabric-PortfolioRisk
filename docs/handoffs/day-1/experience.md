# Day 1 Experience Handoff

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
- Kept Wave 1B portfolio import and Wave 1C analytics explicitly unavailable without implying a zero or completed result.
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
- Portfolio upload/validation/confirmation remains Wave 1B work.
- VaR, expected shortfall, stress, scenario, correlation, contribution, and other risk analytics remain Wave 1C work; the Risk screen makes no methodology claim for them.
- External providers and notebook execution remain disabled in every profile.
- Browser-specific visual and assistive-technology QA remains an integration/soft-QA activity; focused tests validate the rendered contracts and accessibility primitives.
- Hosted catalogue copies must continue to be synchronized from the reviewed knowledge sources when those source records change.

## Rollback

Restore the modified Workbench app files and `tests/application/test_workbench.py` to the accepted integration base, remove the added app-local catalogue, template, stylesheet, presentation, and Day 1 seed files, and remove this handoff. No data migration or external rollback is required; persisted Day 0 evidence contracts were not changed.

## Recommended next action

Integration should first install Jinja2 and python-multipart through the canonical runtime/verification lock, then run clean runtime bootstrap, `verify-wave-1a`, and browser/keyboard/assistive-technology soft QA before accepting or rejecting the candidate. Do not begin Wave 1B portfolio import or Wave 1C analytics through this lane.
