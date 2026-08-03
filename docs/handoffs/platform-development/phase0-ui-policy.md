# Phase 0 UI, operating-profile, and policy audit

- Status: complete read-only audit
- Lane: P0-03 — UI, profiles, and policy
- Branch: `feature/platform-p0-ui-policy`
- Audited head: `b815cabeb7fde93a75ba4c9a221f2183f40f81b8`
- Implementation authority: none; this lane changes only this handoff

## Executive conclusion

The Labs application already has unusually good local disclosures in its most important demonstrations: the Database page distinguishes licensed DuckDB queries from synthetic samples, Agent Run Review distinguishes deterministic fixtures from model-backed execution, and Workflow Cycle identifies simulated intraday data anchored to real daily closes. The main Phase 0 problem is not an absence of disclosures. It is that they are local, inconsistently named, and not backed by one operating-profile contract.

The smallest safe visible increment is an always-visible **truth strip** shared by every Labs workspace. It should state four independent facts:

1. operating profile;
2. data origin and point-in-time qualification;
3. authority/effect boundary;
4. persistence/retention class.

This increment should be display-first in Phase 0. It must not add a profile selector, registry kernel, Studio–Codex gateway, new domain object, simulated portfolio mutation, or external effect. Existing canonical contracts remain authoritative. Where the UI currently calls a pending review item a decision, it must instead call it a decision proposal until an identified resolver records a decision.

## Required Phase 0 vocabulary

Use these terms as separate dimensions. Do not combine them into a generic `mode` badge.

### Operating profile

| Label | Meaning in Phase 0 | Controls |
|---|---|---|
| **Development** | Local authoring, compilation, and isolated testing of definitions. | Development controls may be visible. External effects are prohibited. A future Studio–Codex gateway may exist only here. |
| **Experimental** | Historical replay, synthetic-data simulation, and bounded research runs. | Runtime code authoring is unavailable. External effects are prohibited. Simulated effects remain disabled for the Phase 0 increment. |
| **Persistent research** | Approved, reusable research assets and evidence with immutable versions. | No code authoring. External effects are prohibited. This is a declared future-facing profile until registry and lifecycle contracts exist. |

Do not expose `Product` or `Production` as a selectable profile in Phase 0. Do not let users change profiles through an ungoverned browser control. The server, not query parameters or local storage, must be the eventual authority for the active profile.

### Data origin

Use one primary origin and explicit modifiers:

- **Licensed local historical data**
- **Public real data**
- **Reviewed synthetic fixture** — only when a governed fixture identifier, version, and digest exist
- **Synthetic behavior fixture** — generated or scenario-based test data without the governed fixture identity above
- **Simulated data anchored to licensed observations**
- **Mixed input** — enumerate every component

Relevant modifiers include:

- point-in-time eligible;
- point-in-time qualified;
- publication time unavailable;
- future anchor sealed;
- rights restricted;
- no synthetic fallback.

Avoid the unqualified labels `real data` and `live data`. They do not say whether data is licensed, historical, point-in-time safe, streaming, complete, or externally sourced.

### Data state

| State | Exact meaning |
|---|---|
| `eligible` | The observation is permitted at the run's as-of time. |
| `stale` | An observation exists but is outside the declared freshness rule. |
| `missing` | An expected field has no eligible observation. |
| `unavailable` | The source/capability is not configured, not reachable, or not present in the selected dataset. |
| `failed` | An attempted operation returned an error. |
| `blocked` | Policy or authority prevented the operation. |
| `not applicable` | The field is intentionally irrelevant to this task. |

Never turn `missing`, `unavailable`, or `failed` into zero.

### Execution

- **Deterministic local execution**
- **Model-backed execution**
- **Simulated stream**
- **No fallback**

Reserve `live` for wall-clock or streaming execution. Replace the current phrases as follows:

| Current phrase | Required replacement |
|---|---|
| Live cycle | Simulated intraday cycle |
| Live work record | Current work record |
| Live Agent Card | Agent Card preview |
| Live LLM | Model-backed execution |
| Live DuckDB / real data | Licensed local historical data |

### Analytical and authority states

The visible progression must be:

```text
Evidence
  -> Finding
  -> Decision proposal
  -> Decision by an identified resolver
  -> Simulated effect preview
  -> Simulated effect (future and disabled in Phase 0)
  -> Outcome observation
```

The terms are not interchangeable:

- **Finding**: an evidence-backed analytical observation;
- **Decision proposal**: reviewable options, recommendation, uncertainty, and proposed consequence; it has no authority;
- **Decision**: an immutable resolution by an identified human or policy-authorized experimental resolver;
- **Simulated effect**: an explicitly fictitious internal state change in an experimental boundary;
- **External effect prohibited**: no broker, order, hedge, rebalance, portfolio mutation, or external communication.

The current canonical `AlertDraft` remains a non-executing draft. The current canonical `DecisionPoint` remains the human resolution contract. Phase 0 should not create replacements for either.

### Persistence

Use one of these labels wherever an artifact is displayed:

- **Unsaved browser draft**
- **Temporary local run** — deletable test output; not published and not a registry asset
- **In-memory session** — lost when the service restarts
- **Experiment-retained** — future, after retention policy exists
- **Published persistent** — future, after registry/version contracts exist
- **Evidence-locked** — future, after evidence lifecycle policy exists

## Proposed visible increment

Add one shared truth strip immediately below the global Labs header. It remains visible on desktop and mobile and is refreshed when the workspace, selected data source, execution method, or persistence state changes.

```text
Profile       Development
Data          Licensed local historical · point-in-time qualified
Authority     Findings and proposals only · external effects prohibited
Persistence   Temporary local run · deletable · not published
```

The four cells are independent. A workspace name, connection status, or execution method cannot replace an operating profile. On narrow screens the strip may wrap to two rows or collapse into an accessible disclosure, but it must not be hidden.

Recommended page states:

| Workspace/state | Truth strip content |
|---|---|
| Database, connected | `Development` · `Licensed local historical data` · `Read-only; no synthetic fallback` · `Unsaved browser result` |
| Database, sample | `Development` · `Synthetic behavior fixture` · `Read-only` · `Unsaved browser result` |
| Agent, deterministic test | `Development` · `Synthetic behavior fixture` · `Deterministic local execution; effects none` · `Temporary local run` |
| Agent, DuckDB + model | `Development` · `Licensed local historical data; point-in-time qualified` · `Model-backed interpretation; effects none` · `Temporary local run` |
| Workflow Cycle | `Experimental prototype` · `Mixed: licensed daily anchors + simulated intraday` · `Findings and proposals only; effects none` · `In-memory session` |
| Full experiment | `Experimental prototype` · enumerate selected inputs · `Browser-only sandbox; external effects prohibited` · `Unsaved browser state` |

The truth strip should be fed from one server-provided runtime description. Phase 0 may render a fixed Development profile where necessary, but UI code must not infer authority from a route name or user-editable parameter.

## Screen-by-screen audit

### Global shell and navigation

Evidence:

- `apps/portfolio-risk-workbench/labs/index.html:32-37` defines Database, Portfolio, Agent, Agent graph, Live cycle, and Full experiment workspaces.
- `apps/portfolio-risk-workbench/labs/labs.js:282-299` changes the visible workspace and rewrites the current `.mode-badge`.
- `apps/portfolio-risk-workbench/labs/labs.js:3458-3459` reads `?workspace=` only at initialization.
- `apps/portfolio-risk-workbench/labs/styles.css:1564` hides the mode badge on mobile.

Findings:

1. There is no operating-profile contract in the Labs API or shell. The badge alternately means workspace, data source, connection state, or simulation state.
2. Switching tabs does not update browser history or the shareable URL. Back/forward navigation and copied links therefore do not reliably identify the visible workspace.
3. The brand link targets `#experiment`, while the primary navigation uses query-driven workspaces.
4. Hiding the only global status badge on mobile removes the most important disclosure precisely where screen space is constrained.

Required change:

- Introduce the truth strip above and keep the existing connection status as a separate, subordinate status.
- Give each workspace button an accessible current state, update `?workspace=` through the History API, and restore it on popstate.
- Make the brand link route to the default workspace rather than a legacy fragment.

### Database

Evidence:

- `apps/portfolio-risk-workbench/labs/index.html:85-96` exposes explicit licensed-data and synthetic query choices for positional queries.
- `apps/portfolio-risk-workbench/labs/labs.js:592-607` reports licensed-data query failure and does not silently substitute a synthetic result.
- `apps/portfolio-risk-workbench/labs/styles.css:705-708` includes visible quality states.

Strengths:

- The no-fallback behavior is correct.
- The natural-language SQL flow is constrained and visibly read-only.
- Result provenance is already available near the query result.

Risks and required change:

1. `Live` and `real` are too broad. Label the source `Licensed local historical data`; show rights, point-in-time status, and limitations.
2. The natural-language path is implicitly DuckDB-backed but the source truth is not prominent before a query is run.
3. Query and connection errors are plain text rather than announced status regions.
4. Formalize the data-state vocabulary above and preserve null/missing values.
5. Give scrollable result tables an accessible region name and keyboard focus where necessary.

### Portfolio

Findings:

1. The instrument chooser is presented as an available governed universe, but the page does not state whether the list came from DuckDB, static JavaScript, or a reviewed registry.
2. `Saved locally` and `Save reviewed draft` use browser local storage. They can be mistaken for published or persistent assets.
3. Simple maximum-position and minimum-cash checks are called a `Mandate check`. They are not yet a professional mandate contract or knowledge graph.

Required change:

- Display the instrument-universe origin next to the selector.
- Rename storage status to `Unsaved browser draft` / `Browser-local draft; not published`.
- Rename the current constraint surface `Prototype portfolio constraints` or `Monitoring policy preview` until the Mandate Lab and canonical mandate representation are decided.
- Do not add a new mandate object in Phase 0.

### Agent Studio and Agent Run Review

Evidence:

- `apps/portfolio-risk-workbench/labs/index.html:232-241` and `:402-415` visibly lock effect authority.
- `apps/portfolio-risk-workbench/labs/index.html:529-538` separates synthetic-fixture and real-DuckDB input.
- `apps/portfolio-risk-workbench/labs/labs.js:1897-1955` previews input and provenance before execution.
- `apps/portfolio-risk-workbench/labs/agent_studio.py:4095-4169` saves run artifacts in dedicated, deletable run folders.
- `apps/portfolio-risk-workbench/labs/index.html:551` defaults an `Auto-approve the human interrupt` option on.
- `apps/portfolio-risk-workbench/labs/agent_studio.py:782-797` also defaults `auto_approve_review` to true.

Strengths:

- The effect-free authority boundary is clear.
- Synthetic/deterministic and DuckDB/model-backed execution are separated.
- Exact input, capability activity, output, provenance, and generated files are reviewable.

Risks and required change:

1. Automatic test continuation must never be represented as human approval. Rename it `Release review checkpoint in the test harness (effect-free only)`, default it off, record actor `test_harness`, and use status `review_checkpoint_released_for_test`.
2. A test-harness release must not create a canonical human `DecisionPoint`.
3. Run folders need the label `Temporary local run · deletable · not published · not a registry asset` and a disclosed root/retention rule.
4. `Keep every output` overstates persistence. Saving is not publishing.
5. `OverallDefaultContext` is a provisional compiled view, not a settled canonical object. Label it `Prototype compiled context view` until the context-family decision is made.
6. Blueprint, advisor, compile, prompt, and output-pass controls are development authoring controls. Mark them Development-only now, then enforce the same rule at the server boundary when profiles become executable policy.
7. The current advisor drawer requires keyboard focus management, close behavior, an accessible name, and focus return.

### Agent graph

Findings:

1. The visual graph is a useful development abstraction, but its compilation result can look like a registered, executable workflow.
2. The agent list is browser-local, not a governed registry.
3. The graph controls are development authoring controls and are currently exposed without a profile contract.

Required change:

- Label the graph `Development draft` and its result `Compiled plan preview; not registered or published`.
- Label locally saved agents `Browser-local draft`.
- Add semantic tab roles and keyboard behavior to custom tabsets.
- Do not build registry publication or workflow execution in this phase.

### Workflow Cycle

Evidence:

- `apps/portfolio-risk-workbench/labs/index.html:653-669` explains simulated time and real close anchors.
- `apps/portfolio-risk-workbench/labs/workflow_cycle_runtime.py:532-537` exposes source truth and a sealed future anchor.
- `apps/portfolio-risk-workbench/labs/workflow_cycle_runtime.py:283-314` creates a pending object named `decision` when a threshold is crossed.
- `apps/portfolio-risk-workbench/labs/index.html:716-718` presents the pending object as a human decision.
- `apps/portfolio-risk-workbench/labs/labs.js:2893-2903` records `investigate` but does not open an investigation workspace.

Strengths:

- This is the clearest existing data-truth explanation.
- Future close anchors are sealed, preserving the intended look-ahead boundary.
- The clock pauses at review points.

Risks and required change:

1. Rename `Live cycle` to `Simulated intraday cycle`.
2. The threshold crossing is a finding and decision proposal, not a decision. It becomes a decision only when an identified resolver records an allowed outcome.
3. `Open investigation` is misleading because no workspace opens. Use `Mark for investigation`, or render a disabled `Investigation workspace not yet available` action.
4. Acceptance/rejection needs a concise consequence preview before resolution: what resumes, what is recorded, and what remains unchanged.
5. Agent latches currently behave as attachment metadata rather than demonstrated sub-agent execution. Label them `Prototype attachment metadata` unless an actual run receipt exists.
6. Cycle sessions are in memory and disappear on service restart; disclose this in the truth strip and session panel.
7. Cycle status and new review proposals need `aria-live` announcements that do not continually interrupt candle updates.

### Full experiment

Findings:

1. The legacy page mixes experiment configuration, fixtures, agent frameworks, context compilation, decision controls, and PortfolioEvents within a browser-only surface.
2. It permits human-controlled sandbox mutation while the Agent and Cycle pages explicitly promise effects none.
3. The local `production boundary` explanation is valuable but cannot replace an always-visible profile and effect boundary.
4. Terms such as `AUTO_CLEARED`, `RealPortfolioSelectionManifest`, and `Overall Default Context` can imply governed execution or canonical persistence that is not present.

Required change:

- Apply the strongest Phase 0 banner: `Experimental prototype · browser-only sandbox · simulated PortfolioEvents only · external effects prohibited · not persistent`.
- Prefer `no review checkpoint triggered` over `AUTO_CLEARED`; it is an analytical routing result, not an autonomous approval.
- State the data origin of the portfolio selection manifest.
- Label compiled context as a prototype view.
- Because simulated mutation is a Phase 0 non-goal, do not expand it. Either leave existing controls behind the explicit experimental banner or disable application actions pending the later authority policy decision.

### Dialogs, system map, and help

The explanatory copy and ASCII diagrams are useful, especially the production-boundary map. They should remain secondary explanations. No modal, tooltip, or diagram should carry the only disclosure of profile, data truth, authority, or persistence.

Help buttons and custom dialogs must have accessible names, keyboard entry/exit, Escape handling, focus containment where modal, and focus return. Native `dialog` behavior is preferable where it fits the current implementation.

## Development-control leakage audit

No current Studio–Codex terminal or code-edit gateway was found in the Labs markup or routes. That is the correct Phase 0 state.

The following existing controls are nevertheless development-only authoring surfaces and should be tagged and later gated as a unit:

- blueprint generation and planning;
- agent design advisor;
- agent compilation;
- prompt/output-pass generation;
- graph composition;
- natural-language SQL generation;
- raw manifest/configuration editing.

Recommended enforcement contract:

1. UI elements carry `data-development-only` for inspection and testing.
2. The server publishes the active operating profile.
3. Every authoring endpoint rejects requests outside Development, regardless of hidden controls or crafted HTTP requests.
4. Experimental and Persistent research profiles never receive a Studio–Codex gateway URL, command, session token, or terminal control.
5. External effects remain disabled in all Phase 0 profiles.

This is a policy boundary, not a CSS visibility feature.

## Accessibility and layout audit

### P0 requirements for the visible increment

- The truth strip must remain visible at mobile widths; do not repeat the current hidden-badge behavior.
- Workspace navigation uses `aria-current` or tab semantics consistently and supports keyboard navigation.
- Custom tab lists use `role=tab`, `aria-selected`, `aria-controls`, and associated `tabpanel` elements.
- All interactive elements, including generic buttons, links, summaries, workspace tabs, and run-mode controls, receive a visible `:focus-visible` state.
- Connection errors, query status, run status, paused review points, and completed outputs use appropriately scoped `aria-live` regions.
- Do not place critical provenance, decision, or report text at 6–8 px. Use the common body/label scale.
- Do not rely on teal/amber/red alone; retain text labels and status icons.
- Scrollable tables and work records need names and keyboard-reachable regions where nested scrolling is unavoidable.
- Opening and closing the advisor returns focus predictably.
- Avoid competing nested scroll containers in Agent Run Review on narrow screens; provenance and output must remain readable without horizontal overlap.

### Layout observations

The fixed-width run transcript, three-column review panes, and densely nested cards work at desktop width but can obscure source truth and output on smaller screens. Phase 0 should not redesign the Studio. It should ensure the four truth dimensions, run premise, principal output, and review action stack vertically before optional traces and files.

## Test plan for the integration lane

### Architecture/static tests

1. Every supported workspace route renders the truth strip with profile, data, authority, and persistence cells.
2. Workspace switching updates `?workspace=`, browser history, the accessible current state, and the visible panel.
3. Mobile CSS does not hide the truth strip or the external-effects prohibition.
4. Development-only controls are tagged consistently.
5. Non-development profiles do not render Studio–Codex controls and the matching server endpoints reject authoring requests.
6. Unqualified ambiguous copy is absent from primary UI: `Live cycle`, `Live work record`, `Live Agent Card`, `auto-approve the human interrupt`, `AUTO_CLEARED`, and bare `real data`.

### Application/backend tests

1. A runtime/health response includes the server-authoritative operating profile and `external_effects: disabled`.
2. Synthetic provenance may use `reviewed_synthetic_fixture` only with fixture ID, version, and digest; generated scenarios use `synthetic_behavior_fixture`.
3. DuckDB provenance records licensed-local origin, rights, point-in-time qualification, and source limitations.
4. Missing/unavailable/failed values remain explicit and never become numeric zero.
5. Every saved agent-run manifest records operating profile, data origin, execution method, authority boundary, persistence class, and effects.
6. A test-harness checkpoint release records actor `test_harness`, never `human`, and does not create a canonical `DecisionPoint`.
7. A Workflow Cycle snapshot records mixed input, sealed future anchor, in-memory persistence, and effects none.
8. Resolving a decision proposal records the identified resolver, allowed resolution, consequence summary, and immutable receipt.

### Interaction and accessibility tests

1. All workspace and Agent sub-tabs can be traversed and selected by keyboard.
2. Focus is visible and lands on the new page heading or panel after navigation.
3. Service unavailable, query failure, run paused, and decision-proposal creation are announced once.
4. Opening and closing the advisor preserves a coherent focus path.
5. `Mark for investigation` does not claim a workspace was opened.
6. Truth-strip values and principal Agent Run Review content remain visible and non-overlapping at narrow desktop and mobile breakpoints.

### Regression commands

Run at minimum:

```bash
pytest tests/application/test_labs_runtime.py
pytest tests/architecture/test_platform_development_control_plane.py
pytest tests/application/test_workbench.py
make verify-platform-phase0
```

Also perform focused local-service smoke checks for:

- Database licensed query and deliberate service failure with no synthetic fallback;
- Agent deterministic synthetic run;
- Agent licensed-data preview and model-backed execution with a stubbed provider where required;
- Workflow Cycle creation, start, pause, proposal review, and resume;
- Full experiment banner and disabled/prototype effect boundary.

## Evidence summary

Canonical contracts inspected:

- `docs/contracts/portfolio-data-context-v0.1.md`
- `docs/contracts/monitoring-policy-v0.1.md`
- `packages/risk_domain/src/risk_domain/models.py`
- `packages/risk_domain/src/risk_domain/monitoring.py`

Primary application surfaces inspected:

- `apps/portfolio-risk-workbench/labs/index.html`
- `apps/portfolio-risk-workbench/labs/labs.js`
- `apps/portfolio-risk-workbench/labs/styles.css`
- `apps/portfolio-risk-workbench/labs/duckdb_server.py`
- `apps/portfolio-risk-workbench/labs/agent_studio.py`
- `apps/portfolio-risk-workbench/labs/workflow_cycle_runtime.py`
- `apps/portfolio-risk-workbench/labs/README.md`
- `apps/portfolio-risk-workbench/labs/DEVELOPMENT_ROADMAP.md`
- `apps/portfolio-risk-workbench/presentation.py`

Existing test surfaces inspected:

- `tests/application/test_labs_runtime.py`
- `tests/application/test_workbench.py`
- `tests/architecture/test_platform_development_control_plane.py`

The persistent Workbench already has a `ProfileView` and tests for persistent profile/data/review badges. The integration lane should reuse its semantics where they are compatible, without coupling the Labs shell to a presentation implementation or inventing a second canonical profile object.

## Deviations, blockers, and limitations

- `make preflight` did not reach a green baseline. Environment validation passed, but the repository check reported a ServiceFabric pin mismatch: expected `7632b61d...`, actual audited head `b815cabeb...`. This lane did not change pins or repository state.
- This was a source and contract audit. Browser automation and visual screenshots were not required or authorized by the lane, and no running service state was treated as canonical evidence.
- Exact line numbers are references to the audited head and may shift when the integration lane edits the UI.
- The audit does not decide the future registry kernel, Mandate Lab object model, context-family projection, Studio–Codex protocol, or simulated-action authority. It marks UI claims that must remain provisional until those decisions are accepted.

## Rollback

This lane adds only this Markdown handoff. Rollback is deletion of `docs/handoffs/platform-development/phase0-ui-policy.md`; no application, runtime, fixture, or test state is affected.

## Recommended integration order

1. Add the server-authoritative, display-only operating-profile description and shared truth strip.
2. Normalize the primary labels and separate finding, proposal, decision, and effect terminology.
3. Correct test-harness review-release provenance.
4. Add route/history and accessibility semantics.
5. Add the focused tests above.
6. Run Phase 0 verification, capture browser evidence, and only then consider profile enforcement or later-phase controls.

The integration lane should keep this increment deliberately narrow. Its purpose is to make the current system truthful and reviewable before expanding what it can do.
