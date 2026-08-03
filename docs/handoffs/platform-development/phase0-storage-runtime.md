# Phase 0 specialist handoff — storage and runtime audit

- Lane: storage/runtime audit (`P0-02`)
- Branch: `feature/platform-p0-storage-runtime`
- Audit base: `b815cabeb7fde93a75ba4c9a221f2183f40f81b8`
- Programme baseline: `81660bd3d4be9c8fb6725e5836e7821f9947eb17`
- Scope: read-only inspection; this handoff is the only repository change

## Executive finding

The current vertical slice works, but it has five different state models rather
than one governed persistence path:

1. canonical immutable portfolio/data contracts and external data zones;
2. ignored filesystem folders for generated agents, agent runs, and capability
   memory;
3. browser `localStorage` for authored portfolios and agents;
4. process memory for workflow-cycle sessions, graph composition, output passes,
   and the full experiment prototype;
5. immutable thesis evidence bundles with stronger manifests and digest
   verification than the Labs run repository.

Phase 1 should therefore create a lightweight index over existing definitions
and records. It must not make the Labs `manifest.json`, browser state, or a new
generic run object authoritative. Phase 2 should move governed artifacts and
caches behind the existing ServiceFabric workspace boundary and add retention,
reference, integrity, and recovery policy.

## Endpoint-to-runtime call map

All endpoints are defined in
`apps/portfolio-risk-workbench/labs/duckdb_server.py`. The module creates one
global in-memory DuckDB data plane and one global in-memory workflow-cycle
manager at process import.

| Endpoint | Runtime path | Calls / data boundary | Persistence |
|---|---|---|---|
| `GET /api/health` | `health` | Reads process state, dataset catalogue counts, reviewed-portfolio count, and whether a local OpenAI credential exists. | None. It currently returns the absolute raw-data root. |
| `GET /api/catalog` | `catalog` | Returns the schema and statistics built by `ReadOnlyDataPlane._build_catalog` from allow-listed Parquet files. | None; rebuilt at server start. |
| `GET /api/portfolios` | `portfolios` | Projects reviewed YAML portfolio selections and private-neutral instrument aliases. | None. |
| `POST /api/query/portfolio` | `ReadOnlyDataPlane.query_portfolio` | Runs bounded, position-filtered, as-of DuckDB queries across allow-listed local CRSP/Compustat sources. | Response only. |
| `POST /api/query/ask` | `plan_sql` then `validate_generated_sql` and `execute_generated_sql` | One OpenAI Responses call receives the question-specific schema projection but no licensed rows; one validated `SELECT` runs locally, capped at 10,000 rows, 200 columns, and 20 seconds. | Response only; the browser may download a CSV outside ServiceFabric governance. |
| `GET /api/agents/runtime` | `runtime_status` | Reports compiler, LangGraph/OpenAI package, model-menu, credential-presence, and Lab capability metadata. | None. |
| `POST /api/workflow-cycle/sessions` | `prepare_workflow_cycle_configuration` then `WorkflowCycleManager.create` | Reads real daily close anchors, creates a seeded synthetic intraday bridge, and registers a session object. | Process memory only. |
| `GET /api/workflow-cycle/sessions/{id}` | `SyntheticWorkflowSession.snapshot` | Returns current clock, candles, dashboard, report, events, decisions, and data-truth disclosure. | Process memory only. |
| `POST /api/workflow-cycle/sessions/{id}/control` | `start`, `pause`, or `set_speed` | Starts one daemon thread per active session and advances deterministic synthetic seconds. | Process memory only. |
| `POST /api/workflow-cycle/sessions/{id}/decisions/{decision}` | `resolve_decision` | Mutates an in-memory review record; no financial effect. | Process memory only. |
| `POST /api/workflow-cycle/sessions/{id}/agents` | `attach_agent` | Changes an in-memory dashboard-page latch and adds a declarative dashboard patch. | Process memory only. |
| `DELETE /api/workflow-cycle/sessions/{id}` | `WorkflowCycleManager.delete` | Removes the session from the manager and signals its daemon thread to stop. | Irrecoverable; no run artifact or deletion receipt. |
| `GET /api/agents/capability-platform` | `capability_platform_manifest` | Returns a static Lab meta-capability list plus the filesystem capability-memory policy. | None. This is not the canonical capability registry. |
| `GET /api/agents/templates` | `risk_agent_templates` | Builds templates from Python source and validates them as Lab `AgentBlueprint` values. | None. |
| `POST /api/agents/blueprint/validate` | `compile_blueprint(..., persist=False)` | Pydantic validation plus Python source compilation and graph-spec generation. | None. |
| `POST /api/agents/blueprint/plan` | `plan_blueprint` | One schema-constrained OpenAI drafting call. | Response/browser state only. |
| `POST /api/agents/blueprint/plan-section` | `plan_blueprint_section` | One schema-constrained OpenAI call for a selected section. | Response/browser state only. |
| `POST /api/agents/advisor` | `advise_blueprint` | One schema-constrained OpenAI critique call. | Response/browser chat state only. |
| `POST /api/agents/compile` | `compile_blueprint` | Writes generated `blueprint.json` and `agent.py` when `persist=true`. | Ignored `.agent-runs/generated-agents/<blueprint-digest>/`. |
| `POST /api/agents/input-preview` | `prepare_agent_input` | Selects a code-defined synthetic scenario or assembles real point-in-time DuckDB inputs and provenance. | Response only. |
| `POST /api/agents/run` | `prepare_agent_input` then `run_blueprint` | Compiles and imports a generated LangGraph module, invokes the local graph, runs the partially connected PortfolioRisk capability chain, optionally calls OpenAI, and optionally releases the review interrupt as an isolated auto-approval. | Optional ignored run directory plus generated agent. |
| `GET /api/agents/runs` | `list_agent_runs` | Lists readable run manifests. | Reads ignored filesystem state. |
| `GET /api/agents/runs/{id}` | `load_agent_run` | Reads manifest-listed files up to 2 MB after path containment checks. | Reads ignored filesystem state. |
| `DELETE /api/agents/runs/{id}` | `delete_agent_run` | Validates the run-ID pattern and parent, then calls `shutil.rmtree`. | Immediate physical deletion; no tombstone, dependency check, receipt, or recovery. |
| `POST /api/agents/output-pass` | `run_output_pass` | Builds one structured-output patch from a code-defined synthetic scenario, optionally with OpenAI. | Response/browser state only; no server-side pass ledger. |

The Portfolio workspace additionally stores up to 12 authored portfolios and
16 authored agents in browser `localStorage`. Same-name saves replace prior
entries without version lineage. The Agent Graph workspace is an in-browser
composition and validation preview. The Full Experiment workspace in
`apps/portfolio-risk-workbench/labs/app.js` is an in-browser synthetic
prototype; refresh loses its workflow state. Dataset query CSV export is a
browser download, not a registered artifact.

## Storage inventory

| Class | Existing storage and contract | Current status |
|---|---|---|
| System assets | Reviewed code and declarations in Git; `CapabilityDescriptor` and `CapabilityRegistry` under `packages/risk_capabilities`; `AgentRole` under `packages/risk_agents`; immutable domain records under `packages/risk_domain`. | Reusable but split across code catalogues; no unified lifecycle index. |
| Data assets | `PORTFOLIO_RISK_DATA_ROOT` external zones and the governed `ResearchDataPlane`; the local Lab separately discovers `private-data/crsp-compustat/raw` and reviewed portfolio-definition files. | External/private boundary is sound in package code, but the Lab does not bind queries to one registered dataset-snapshot revision. |
| Experiment overlay | Reviewed thesis YAML manifests under `examples/portfolio-risk-thesis/experiments`; current Full Experiment and graph state are browser-only. | Reusable thesis manifests exist; the new Lab composition is one-off and not a governed overlay. |
| Generated agent | `.agent-runs/generated-agents/<artifact_id>/blueprint.json` and `agent.py`, where `artifact_id` includes the blueprint digest. | Rebuildable ignored output. There is no lifecycle state, registry reference, atomic publish, or cleanup API. |
| Agent run artifact | `.agent-runs/agent-lab/<run_id>/` containing input, provenance, blueprint, activity, research plan, capability/model executions, output, review, Markdown brief/transcript, and `manifest.json`. | Reviewable local folder, not a canonical evidence bundle. Manifest entries have sizes but no content digests, rights, retention, parent experiment, definition revisions, or deletion policy. |
| Capability cache | `.agent-runs/capability-memory/<namespace>/<input-key>.json`; writes only successful, effect-free calls taking at least five seconds. | Non-authoritative intent is correct, but no TTL, tool/code revision, explicit rights, atomic write, concurrency lock, invalidation, or cleanup exists. |
| Graph memory | Generated LangGraph uses `InMemorySaver` for configured memory; output-pass and advisor history remain browser/process state. | Ephemeral and lost on process/browser restart despite user-selectable memory scopes named `workflow_cycle`, `experiment`, and `session`. |
| Workflow-cycle state | `WorkflowCycleManager.sessions` plus one `SyntheticWorkflowSession` object and optional daemon thread per session. | Explicitly synthetic and bounded per session, but entirely ephemeral and unindexed. |
| Fixture | Reviewed committed material under `data/fixtures/synthetic/**`; additional `_scenario_context` and JavaScript-generated scenarios are source-code samples. | The committed fixtures are reusable. Code-generated samples lack fixture manifest identity and should not be labelled as reviewed fixtures. |
| Evidence | PortfolioRisk `ArtifactReference`, `AgentRun`, evidence references, immutable data snapshots, and thesis `run-manifest.json` / `evidence-manifest.json`; ServiceFabric `EvidenceRecord`, `ToolResult`, and durable-operation event records. | Strong reusable contracts already exist. Labs run persistence does not currently use them. |
| Platform runtime state | ServiceFabric's `application-workspace-v0.1` contract separates editable `SERVICEFABRIC_WORKSPACE` from runtime-owned `SERVICEFABRIC_HOME`, including `registry`, `artifacts`, `operations`, `cache`, `tmp`, locks, backups, and explicit lifecycle verbs. | Best existing seam for Phase 1/2; the Lab's repository-local ignored root is not equivalent to platform-managed state. |

The clean specialist worktree contained no `.agent-runs` or `.servicefabric`
state. The paths above are therefore code-level storage behavior, not a claim
about a specific user's retained run contents. No licensed row, credential, or
private manifest content was read.

## Reusable versus one-off behavior

### Reuse as-is or through a thin projection

- immutable `DatasetSnapshot`, `PortfolioSnapshot`, `ExposureSnapshot`,
  `ArtifactReference`, `RiskFinding`, `DecisionPoint`, and deterministic
  `AgentRun` domain contracts;
- `CapabilityDescriptor`, capability allow-lists, invocation history, and
  registered deterministic handlers;
- `AgentRole` grants and denied effects;
- governed research dataset revisions, snapshot catalogues, fixed-query
  manifests, point-in-time rules, evidence, and quality records;
- ServiceFabric `ToolInvocationRequest`, `ToolResult`, `EvidenceRecord`,
  immutable artifact references, `ServiceFabricOperation`, operation events,
  execution attempts, and idempotency records;
- immutable Day 3/4 evidence-manifest patterns and digest verification;
- the working Lab input preview, query validator, run review, and synthetic
  cycle disclosure as behavior to preserve.

### Keep explicitly provisional or one-off

- Lab `AgentBlueprint`, context/capability packs, and meta-capability tuple are
  authoring/runtime prototypes, not registry authority;
- browser-saved portfolios and agents are drafts, not published definitions;
- graph compilation and Full Experiment execution are UI simulations;
- workflow-cycle decisions, dashboards, reports, and agent latches disappear
  on restart;
- output assembly passes have no durable pass ledger;
- generated agents are rebuildable compiler output;
- Lab run folders are review conveniences, not evidence-locked thesis runs;
- the direct LangGraph execution and direct PortfolioRisk registry calls are
  not yet projected through canonical ServiceFabric invocation/result
  envelopes.

## Retention, deletion, recovery, and concurrency risks

1. **Run deletion is irreversible and ungoverned.** It physically removes the
   folder without checking references, retention class, publication/evidence
   lock, or parent experiment. There is no tombstone or deletion receipt.
2. **Worktree-local defaults are fragile.** `.agent-runs` sits under the Git
   worktree (although ignored), so a worktree cleanup can orphan or remove
   assets that the UI presents as saved.
3. **Generated writes are not atomic.** Concurrent compilation of an identical
   blueprint targets the same files without a lock or atomic replacement.
   Capability-memory writes have the same race, and cache readers do not
   handle a partially written JSON file.
4. **The cache key is incomplete for safe long-term reuse.** It binds namespace
   and input but not capability revision, code revision, calculation method
   revision, or policy version. It has no expiry or data-rights boundary.
5. **Run listing, loading, and deletion can race.** There is no repository lock,
   and malformed folders are silently omitted rather than recorded as damaged.
6. **Workflow-cycle scaling is unbounded.** Each active session can create a
   daemon thread; the manager has no quota, TTL, durable checkpoint, startup
   recovery, or joined shutdown. Deletion signals stop but does not wait for
   thread termination.
7. **Browser persistence has last-writer-wins behavior.** Multiple tabs can
   overwrite authoring state. Clearing site data has no recovery path.
8. **Auto-approval is the default isolated-run behavior.** It is disclosed in
   the saved review record but must remain an explicit experimental test
   release, not be confused with a human decision or persistent-research
   approval.
9. **Rights-sensitive inputs can enter ignored run files.** Real input preview
   preserves local licensed-derived source records inside the run folder, but
   the manifest does not record rights, publication restriction, or retention.
10. **Cache and run roots are reported by APIs.** The capability-platform
    response and health response expose absolute local paths. Developer-only
    diagnostics may need them, but persistent/product projections should use
    opaque references.

## Data-truth and disclosure gaps

- `live` currently means both “localhost API connected” and “historical local
  licensed data”; it does not mean a live market feed. The API uses
  `real_duckdb`, while some UI labels use `live_duckdb` or “live data.”
- `/api/catalog` and `/api/portfolios` do not return a consistent operating
  profile, data-truth class, rights state, snapshot revision, or retention
  disclosure.
- `/api/query/ask` correctly prevents licensed rows from reaching Luna, but its
  result envelope is not a canonical `ToolResult` and lacks a registered
  dataset-snapshot reference.
- The synthetic cycle correctly states that daily anchors are real and
  intraday candles are a seeded synthetic Brownian bridge. Preserve this
  mixed-source disclosure.
- The browser-generated dataset path and `_scenario_context` are called
  “fixtures” without a reviewed fixture manifest/digest. They are synthetic
  samples unless bound to a committed fixture revision.
- The Full Experiment fixture uses `real-*` private-neutral aliases inside a
  synthetic browser path. The synthetic status is explained in prose, but
  identity labels make the state easier to misread.
- `POST /api/agents/output-pass` always uses code-defined synthetic context but
  has no explicit `data_mode` field in its request/result contract.
- Some capabilities shown as runnable are only frozen-context bindings; the
  execution receipt does disclose this, but catalogue status and actual
  runtime binding are separate concepts in the UI.
- The Lab has data modes but no enforced development, experimental, or
  persistent-research operating profile. The existing Workbench
  `research`/`personal_portfolio` profile is a data/workspace policy and must
  not be silently repurposed as the new execution-profile axis.

## Recommended seams for Phase 1 — Registry Kernel

1. Use the ServiceFabric `$SERVICEFABRIC_HOME/registry` responsibility as the
   lightweight local index. Store identity, version/revision, lifecycle state,
   source pointer, digest, ownership, compatibility, and provenance—not large
   payloads or licensed records.
2. Index existing `CapabilityDescriptor`, `AgentRole`, immutable domain
   definitions, reviewed thesis manifests, and generated Lab candidates by
   reference. Do not copy them into a second authoritative model.
3. Treat Lab blueprints and browser drafts as `draft`/`candidate` projections.
   A generated Python module remains a rebuildable artifact until validation
   and publication explicitly bind it to approved definitions.
4. Use immutable revision references; never resolve a run against mutable
   `latest`, `current`, or `production` aliases. Preserve parent definition,
   dataset snapshot, prompt/model, policy, capability, and code revisions.
5. Adapt Lab execution to canonical ServiceFabric `ToolInvocationRequest` and
   `ToolResult`/`EvidenceRecord` receipts. Use `ServiceFabricOperation` and its
   event/attempt/idempotency records for work that must survive a request or
   pause, rather than inventing another durable-run envelope.
6. Keep the canonical registry and artifact repository separate. Registry
   removal must not silently delete source, persistent data, or published
   artifacts, matching the ServiceFabric workspace lifecycle contract.
7. Make operating profile, data-truth class, rights/publication state, and
   artifact lifecycle/retention four distinct fields. They answer different
   questions and must not be inferred from one another.

## Recommended seams for Phase 2 — Artifact Repository

1. Place runtime-owned artifacts, operations, cache, locks, temporary state,
   and backups beneath an explicit external `SERVICEFABRIC_HOME` (or a reviewed
   application resource bound through it), not a disposable Git worktree.
2. Reuse PortfolioRisk `ArtifactReference` and ServiceFabric
   `EvidenceRecord`/artifact references. Add repository metadata as a
   projection around them rather than changing their business meaning.
3. Give retained runs a complete digest manifest and opaque repository
   locator. Record source revisions, real/synthetic/simulated state, rights,
   experiment/run association, retention class, approvals, and supersession.
4. Separate cache from evidence. Cache loss must be safe and recomputable;
   evidence and published artifacts must be immutable and verified.
5. Use atomic writes and per-artifact/per-operation locks. Content-addressed
   duplicate writes should converge on identical bytes or fail closed.
6. Replace immediate delete with eligibility validation, reference checks,
   explicit confirmation, a deletion receipt/tombstone, and a bounded recovery
   path. Published and evidence-locked artifacts must deny ordinary deletion.
7. Define quotas and TTLs for ephemeral sessions, output-pass intermediates,
   logs, previews, and caches. Do not apply TTL deletion to experiment evidence
   without its reviewed retention policy.
8. Decide explicitly whether a workflow cycle is ephemeral or durable. If
   durable, checkpoint only bounded state and preserve an operation event log;
   do not serialize daemon-thread implementation state.

## Bounded acceptance tests for the next phases

### Phase 0 integration tests

- preserve `tests/application/test_labs_runtime.py`, including generated-agent
  output outside application source and deterministic mixed-source cycle
  disclosure;
- every Lab screen/API exposes operating profile separately from data-truth
  class and says whether persistence is browser, process, run-retained, or
  evidence-locked;
- development-only compile/Codex controls are absent outside development;
- “fixture” requires a reviewed fixture ID/revision/digest; code-generated
  values are labelled synthetic samples;
- the query utility still shares no licensed rows with Luna and enforces one
  read-only statement, 10,000 rows, 200 columns, and timeout;
- existing Agent Run Review, DuckDB query, and Workflow Cycle smoke paths remain
  green.

### Phase 1 registry tests

- importing current capabilities, roles, manifests, and candidates creates
  pointers without duplicating authoritative payloads;
- registry versions are immutable, lineage is preserved, and mutable aliases
  cannot be invocation targets;
- lifecycle changes do not delete source, data, runs, or artifacts;
- incompatible or missing referenced revisions fail closed;
- non-development profiles cannot publish or mutate candidate code.

### Phase 2 repository tests

- path traversal, absolute client paths, symlink escape, oversize previews, and
  cross-root references are rejected;
- concurrent same-digest writes are atomic and idempotent; different bytes for
  the same identity fail closed;
- run manifests cover every retained file and verification detects added,
  missing, or modified artifacts;
- cache keys include capability/tool, code/method/policy revision, input digest,
  and point-in-time boundary; cache deletion causes safe recomputation;
- deletion checks active references and retention state, writes a receipt, and
  supports the declared recovery window;
- evidence-locked and published artifacts cannot use ordinary deletion;
- workflow-cycle restart behavior matches its declared ephemeral or durable
  contract, and session quotas prevent unbounded threads/state.

## Evidence and tests executed

- `python3 -m pytest tests/application/test_labs_runtime.py -q`: **PASS**, 2
  tests.
- `make preflight`: environment check passed, then repository check stopped
  because this specialist worktree's uninitialized `vendor/servicefabric`
  directory resolved to superproject commit
  `b815cabeb7fde93a75ba4c9a221f2183f40f81b8`, not the pinned gitlink
  `7632b61d94a966346f95eb6c5bb2a5ea27f3bc14`.
- Vendor inspection used the task-authorized initialized read-only source at
  `/Users/lorenzocc/Developer/servicefabric-lab/worktrees/platform-development/integration/vendor/servicefabric`,
  verified at `7632b61d94a966346f95eb6c5bb2a5ea27f3bc14`.
- Inspected application endpoints/runtime, package contracts, focused tests,
  `.gitignore`, committed fixture boundaries, and ServiceFabric workspace,
  invocation, result, artifact, evidence, and durable-operation contracts.

## Deviations, blockers, and limitations

No runtime behavior was executed against licensed data, no provider call was
made, and no user run directory was inspected. Consequently this audit proves
code paths and contract boundaries, not the integrity of any particular local
run folder. The preflight vendor-state failure is an environment limitation for
this specialist worktree; integration must run the full gate with its
initialized pinned vendor source.

The Lab currently invokes generated LangGraph code directly. This audit does
not approve that path as canonical ServiceFabric execution; it records the
adapter seam required before persistent publication. No new contract, runtime
path, storage root, registry, deletion operation, or authority was created.

## Rollback

Revert the single handoff commit. There are no runtime, data, artifact, fixture,
configuration, or dependency changes to undo.

## Recommended next action

Integration should reconcile this inventory with P0-01 and P0-03, normalize
the four orthogonal axes (operating profile, data truth, lifecycle, retention),
and implement only the minimum truthful disclosure and regression tests in
Phase 0. Registry and artifact persistence work should begin only after that
accepted synthesis.
