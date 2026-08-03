# Phase 0 handoff — canonical contracts and normalized decisions

- Lane: P0-01 canonical contracts and decisions audit
- Branch: `feature/platform-p0-canonical-decisions`
- Activation parent: `b815cabeb7fde93a75ba4c9a221f2183f40f81b8`
- Programme baseline: `81660bd3d4be9c8fb6725e5836e7821f9947eb17`
- Status: audit complete; no contract or runtime change

## Audit boundary and method

This is a read-only evidence audit of the overlay packages, schemas, contract
notes, application-local registries, the initialized ServiceFabric vendor
source, the development roadmap and connector brief, and the supplied decision
workbook. The workbook was read directly from
`servicefabric_architecture_decision_register_v3.xlsx`; no workbook content was
modified.

The decision workbook is an architectural input, not executable policy. Its
`Your choice` cells are normalized below, but the corresponding `Status` cells
remain `Open`. Consequently, this handoff does not activate authority, change a
state machine, or authorize a new canonical object.

## Executive reuse decision

Do not create a new registry kernel, invocation envelope, result envelope,
evidence record, effect contract, application artifact model, or generic
agent-run plan in the overlay. ServiceFabric already owns those general
contracts. The overlay should retain ownership of portfolio-risk semantics and
adapt them to ServiceFabric at an explicit boundary.

Phase 1 should first define identity mappings and projections. It should not
replace upstream ServiceFabric code, collapse domain-specific records into a
single generic object, or promote a Labs or thesis fixture model to canonical
status merely because its name matches a roadmap concept.

## Canonical-object inventory

### Existing and directly reusable

| Concern | Existing owner and evidence | Reuse decision |
|---|---|---|
| Portfolio state and findings | `packages/risk_domain/src/risk_domain/models.py`: `PortfolioSnapshot`, `ExposureSnapshot`, `RiskFinding`, `AlertDraft`, `DecisionPoint`, `AgentRun`, `RiskLimit`, positions and observations | Keep as portfolio-risk domain records. Reuse immutable snapshot and finding semantics; do not copy them into a future ERC. |
| Point-in-time monitoring context | `packages/risk_domain/src/risk_domain/monitoring.py`: `PortfolioDataContext`, `PortfolioDataContextRequest`, `MonitoringPolicyVersion`, `PolicyEvaluationResult`, `ContextualMonitoringRun`, `ReplaySpecification`, `ReplayRun`, `MonitoringEvaluation` | Reuse as the current deterministic monitoring slice and as source records referenced by a future composed context view. |
| Agent role and run context | `packages/risk_agents/src/risk_agents/contracts.py`: `AgentRole`, `AgentRunContext`, `AgentProvider`; `roles.py`: `AGENT_ROLES`, `ROLE_BY_ID`, `ACTIVE_AGENT_ROLE_IDS`; `timeline.py`: review, receipt, step and timeline records | Preserve as current risk-agent contracts. Use timelines and receipts as evidence, not as a general registry lifecycle. |
| Risk capability calls | `packages/risk_capabilities/src/risk_capabilities/contracts.py`: `CapabilityDescriptor`, `CapabilityInvocation`, `CapabilityOutcome`, `EvidenceReference`; `registry.py`: request map, result, invocation record and local dispatcher | Preserve the reviewed portfolio-risk request/result semantics. Adapt registration and invocation to ServiceFabric rather than creating a second platform registry. |
| Analytics, scenarios and reports | `packages/risk_analytics/src/risk_analytics/contracts.py`: `AnalysisResult` hierarchy, `ScenarioShock`, `ScenarioResult`, `RiskReport`; `monitoring_reports.py`: `MonitoringReportRequest`, `MonitoringReport` | Reuse typed analytical outputs and report records. They do not yet constitute a reusable scenario-definition or report-template registry. |
| Data identity, rights and eligibility | `packages/risk_data/src/risk_data/research_contracts.py`, `licensed_contracts.py`, `events.py`, and `catalogue.py` | Reuse provider/dataset/revision, availability, link, quality, event and point-in-time rules. These are authoritative inputs to temporal eligibility, not an ERC substitute. |
| Planning and knowledge products | `packages/risk_planning/src/risk_planning/models.py`: `KnowledgeProduct`, `ReviewDecision`, `ArtifactLink`, `ThesisTraceabilityEntry`, `PlanningCatalog` | Reuse traceability and reviewed-knowledge patterns. They are not yet a general thesis graph, mandate, or decision-proposal contract. |
| General capability definition and registry | `vendor/servicefabric/packages/servicefabric_capability_model/src/servicefabric_capability_model/models.py`: `CapabilityDefinition`; `vendor/servicefabric/packages/servicefabric_capability_registry/src/servicefabric_capability_registry/registry.py`: `CapabilityRecord`, `CapabilityRegistry` | ServiceFabric is the platform owner. Reuse the persisted definition registry; do not fork or replace it in the overlay. |
| General invocation and output | `vendor/servicefabric/packages/servicefabric_capability_invocation/servicefabric_capability_invocation/models.py` and `service.py`; `vendor/servicefabric/packages/servicefabric_contracts/src/servicefabric_contracts/{invocation,results,evidence,effects}.py` | Reuse request resolution, transport invocation, result, evidence and effect declarations. Portfolio-risk models should project to and from them. |
| Versioned tool/application semantics | `vendor/servicefabric/packages/servicefabric_contracts/src/servicefabric_contracts/{tool_revision,lifecycle,applications}.py`; `vendor/servicefabric/packages/servicefabric_artifacts/servicefabric_artifacts/store.py` | Reuse tool revision, compatibility, provenance, lifecycle, application manifest and immutable artifact-store semantics. |
| General agentic plan/context | `vendor/servicefabric/packages/servicefabric_agentic_contracts/src/servicefabric_agentic_contracts/contracts.py`; `vendor/servicefabric/packages/servicefabric_agentic_context/src/servicefabric_agentic_context/context.py` | Reuse `AgentTask`, `AgentRunPlan`, task result/handoff/tool result and `ApplicationContextPack` as platform envelopes. Preserve risk-specific policy and context semantics in the overlay. |

### Reusable only through an explicit adapter or projection

| Overlay concept | Required adaptation |
|---|---|
| `risk_capabilities.CapabilityDescriptor` and the in-process `CapabilityRegistry` | Map each reviewed descriptor to a ServiceFabric `CapabilityDefinition`/revision and each local invocation to the canonical invocation service. Keep the local dispatcher as an implementation adapter until migration is proven; do not call it the platform registry. |
| Overlay evidence references | Map domain, capability, analytics, monitoring and thesis references into ServiceFabric `EvidenceRecord` identities while retaining their richer domain payloads and temporal fields. |
| Agent Lab `AgentBlueprint` | Treat as a Labs authoring/compiler projection. Later separate stable blueprint meaning from assignment and runtime profile before registration; never persist the current combined form as a new platform truth without migration. |
| Thesis experiment manifests | Use Day 2/3/4 manifests as bounded, immutable examples for a future experiment projection. Do not generalize their thesis-specific fields into a platform contract in Phase 0. |
| Application-local scenario catalogue | Project reviewed definitions from `apps/portfolio-risk-workbench/analysis_service.py` into a future versioned scenario registry only after identity and compatibility rules are decided. `ScenarioResult` remains the output contract. |
| Planning knowledge products and thesis traceability | Adapt to a future thesis/knowledge graph while retaining current IDs and review history. A graph index must reference, not duplicate, the authoritative records. |

### Provisional and bounded models

- `apps/portfolio-risk-workbench/labs/agent_studio.py` contains an
  application-local `AgentBlueprint`, its identity/prompt/state/routing/memory/
  governance/capability/output sections, a `META_CAPABILITY_REGISTRY`, and local
  persistence and compilation behavior. These are valuable prototype inputs,
  not canonical platform contracts.
- `examples/portfolio-risk-thesis/src/portfolio_risk_thesis/contracts.py` and
  its Day 3/4 contract modules contain thesis-bound portfolio, replay,
  experiment, metric-pack, finding, review and kernel-decision records. Their
  completed-programme meaning must be preserved.
- `schemas/risk/v0.1/**`, `schemas/risk/analytics/v0.1/**`, and the Day 2–4
  schema trees are generated or bounded schema snapshots. They are not a
  unified heterogeneous-asset registry.
- The roadmap's proposed Context Packs, Capability Packs, Autonomy Profiles,
  Runtime Profiles and Evaluation Suites are design vocabulary until mapped to
  existing contracts and given explicit identity/lifecycle ownership.

### Missing canonical ownership

The audit found no single canonical, general contract for:

- a heterogeneous registry index spanning capabilities, agents, workflows,
  scenarios, reports, dashboards, evaluations and experiments;
- a stable `AgentBlueprint` separated from per-run assignment and runtime
  profile;
- `MandateVersion` and machine-testable mandate rules/covenants;
- an Environment Risk Context manifest/view, immutable revisions, typed context
  patches, task-specific context views, or the unresolved portfolio-applied
  environmental overlay;
- `DecisionProposal`, resolved decision, decision card/due-diligence workspace,
  consequence preview, and observed outcome as an end-to-end lifecycle;
- general `ExperimentDefinition`, `ExperimentSet`, comparison grouping and
  concurrent-run policy;
- `WorkflowDefinition`, `AgentGraphDefinition`, reusable evaluation suite,
  report template, dashboard package or visualisation definition;
- cross-kind lineage, compatibility, provenance, retention, tombstone and
  archive policy.

These are gaps, not authorization to add all of these objects. Phase 1 must
first test whether each can be expressed as a ServiceFabric application,
artifact, operation or projection plus a small portfolio-risk contract.

### Duplicated or conflicting concepts

1. **Capability registries.** ServiceFabric has a persisted definition registry;
   the overlay has a local in-process request/handler dispatcher. They serve
   different functions but share the same name. Introduce an adapter and name
   the runtime dispatcher explicitly; never replace the vendor registry.
2. **Capability identifiers.** `CapabilityInvocation` and `CapabilityOutcome`
   constrain IDs to `risk.capability.*`, while the live overlay catalogue uses
   IDs including `risk.returns.simple`, `portfolio.exposure.summarize`, and
   `events.query.as_of`. Identity normalization is a prerequisite to platform
   registration.
3. **Decision-like records.** `AlertDraft` and `DecisionPoint` occur in both
   `risk_domain.models` and `risk_capabilities.registry`; monitoring adds
   `MonitoringAlertDraft`, and the thesis slice adds `KernelDecisionPoint`.
   None implements the workbook's four-stage decision system completely.
4. **Evidence references.** `SourceReference`, `ArtifactReference`, capability
   `EvidenceReference`, analytics `AnalysisEvidence`, monitoring evidence, and
   thesis candidate/external artifact references overlap. Preserve their
   specialized fields and map identities to ServiceFabric evidence rather than
   deleting them wholesale.
5. **Dataset snapshots.** Domain, research-data and event modules use snapshot
   names for different bounded meanings. Require typed namespace and relation
   mappings; do not merge on class name.
6. **Replay and outcome labels.** Monitoring-domain and thesis-specific forms
   overlap but carry programme-specific contracts. Keep completed thesis forms
   immutable and use an adapter for future general experiments.
7. **Reports and scenarios.** Canonical result contracts exist, while report
   layout and scenario definitions remain application- or programme-local.
8. **Operating profiles.** `risk_planning.research.OperatingProfile` currently
   represents research/personal-portfolio modes, not the proposed development,
   experimental and persistent-research runtime boundary. Resolve by an
   explicit mapping or a separately named concept, not a silent rename.

### Obsolete objects

None is safe to declare obsolete in Phase 0. Duplicate names are legacy or
bounded records until an identity map, compatibility policy, migration test and
rollback path exist. Deprecation must use the existing ServiceFabric lifecycle
semantics rather than deletion.

## Registry, identity, version and lifecycle inventory

| Registry or catalogue | Identity | Version/immutability | Lifecycle and present limitation |
|---|---|---|---|
| ServiceFabric capability registry | Capability definition/record identity and revision metadata | Persisted atomically; separates definition from app links | Static registration and availability; it does not make a capability executable by itself. Invocation service performs resolution and validation. |
| ServiceFabric tool/application contracts | Tool/application IDs, revisions and artifact manifests | Explicit revision, compatibility, provenance, schema/effect/dependency/evidence/idempotency metadata; content-addressed artifact storage | Tool maturity: experimental/alpha/beta/stable/deprecated; deprecation: active/deprecated/retired; support: supported/best-effort/unsupported. These semantics should anchor future registry lifecycle. |
| Overlay capability catalogue | String capability ID in `CAPABILITY_DESCRIPTORS`/`CAPABILITY_BY_ID`; request types in `CAPABILITY_REQUEST_TYPES` | Code-versioned, not independently persisted/versioned | Local availability is the presence of a registered handler; no general draft/canary/active/retired lifecycle or compatibility record. |
| Overlay agent-role catalogue | `role_id` in `AGENT_ROLES`/`ROLE_BY_ID` and an active-ID set | Code-versioned | Active membership only; no persisted blueprint revision, provenance, migration or lifecycle history. |
| Data provider/query catalogues | Provider, dataset, revision, query, policy and snapshot IDs/digests | Strong immutable revision/content digest and point-in-time rules | Domain-specific admission/eligibility/quality state; not a general asset lifecycle. |
| Monitoring policies/runs | Policy ID plus integer revision and digest; immutable snapshots and run IDs | Canonical digest validation and explicit as-of semantics | Strong for monitoring/replay, but does not govern heterogeneous asset publication. |
| Planning catalogue | Knowledge product, decision and traceability IDs | Serialized catalogue records | Review-oriented but not a versioned knowledge graph or platform publication registry. |
| Labs Agent Studio registries | Local blueprint/capability/meta-capability IDs | Application-local JSON/compiler versions | Development prototype; no canonical compatibility, promotion, retirement or cross-experiment ownership. |
| Thesis schema/manifests | Programme-specific IDs, versions and digests | Immutable experiment/run records and exported schema versions | Authoritative only within completed thesis programmes; not a reusable registry kernel. |

Minimum future registry semantics should be additive around the upstream
contracts: namespaced stable ID; immutable revision; kind; owner; source and
provenance; compatibility; lifecycle state; availability/profile policy;
schema/effect/evidence declarations; dependency graph; artifact links; creation
and supersession times; and retention/tombstone policy. Run artifacts must
reference an exact registered revision, never an unversioned display name.

## Normalized P0 / Before-v1 decisions

There are 20 workbook rows at the exact intersection `Priority = P0` and
`Timing = Before v1`. Sixteen accept the recommendation and four modify it.
Blank cells were not treated as acceptance.

### Accepted without modification

| Workbook row / ID | Normalized decision |
|---|---|
| 5 / `DEC-001` | Use and visibly label four distinct stages: Finding, Decision Proposal, resolved Decision, and executed Action. Acceptance never implies an undeclared effect. |
| 16 / `DEC-012` | Use a visible D0–D4 authority ladder: explain, recommend, invoke effect-free workflows, resolve reversible analytical choices, and portfolio effects. Every blueprint and proposal shows its level and denied effects. |
| 21 / `DEC-017` | Decision policy is human-owned and versioned. Agents may propose changes but cannot activate them. The note further bars a supra-agent from changing system permissions outside experiments; human approval is required. |
| 22 / `DEC-018` | Use the proposal lifecycle: proposed → policy-validated → awaiting review → resolved → workflow scheduled → completed → outcome observed, with rejected, deferred and escalated branches. Invalid transitions must fail. |
| 24 / `DEC-020` | Reviewer outcomes are Investigate, Accept & monitor, Defer, Reject and Escalate. Each maps to a defined transition and consequence preview. |
| 25 / `DEC-021` | Acceptance records a decision and may schedule only the explicitly previewed registered workflow. It never performs an undeclared action; decision and scheduled workflow are separate receipts. |
| 28 / `DEC-024` | Agents may recommend only registered workflows compatible with the input contract, authority and current ERC state. Incompatible choices are hidden or visibly blocked with a reason. |
| 33 / `ERC-001` | Define ERC(t) as a cohesive view of verified portfolio facts, deterministic risk evidence, eligible external evidence, mandate, theses, decisions/outcomes, and uncertainties/questions, with named layer and time eligibility. |
| 34 / `ERC-002` | Build ERC as a view/manifest over existing canonical records and add only missing relation metadata. It must be rebuildable from canonical IDs and must not copy authoritative facts into a competing record. |
| 35 / `ERC-003` | Use eight initial conceptual layers: portfolio/mandate, market/risk, fundamentals/issuer, events/evidence, models/scenarios, theses/knowledge, decisions/outcomes, gaps/questions. The user note explicitly includes external analysis, metrics, indicators and capability results curated by the Risk Analyst. |
| 37 / `ERC-005` | ERC revisions are immutable and record parent, change set, producer, trigger, as-of, available-at and validation status. The user requires continuity across different instances of the same experiment for quality comparison. |
| 39 / `ERC-007` | Create revisions only for registered triggers: clock advance, portfolio/mandate change, accepted capability result, eligible event, validated context patch, thesis state change, resolved decision, and qualifying analyst research. Unchanged runs do not create revisions. |
| 40 / `ERC-008` | Enforce as-of, available-at, dataset revision and eligibility checks for every ERC item and custom SQL. External searches/API results must have publication availability no later than the as-of boundary. |
| 41 / `ERC-009` | Every context item has canonical ID/type, layer, summary, as-of, available-at, evidence, producer, confidence/quality, lifecycle, refresh/expiry and dependencies. Preserve the user's distinction between evidence items and thesis data primarily used through a knowledge graph. |
| 44 / `ERC-012` | Context-item states are proposed, validated, active, challenged, superseded, expired and rejected. Only validated active items enter the default run context; challenged history remains visible. |
| 52 / `ERC-020` | Agents and specialists propose typed, auditable Context Patches—add, update-link, challenge, supersede, expire or resolve-gap. Silent direct writes are prohibited. |

### Modified answers: accepted direction and unresolved boundary

| Workbook row / ID | User modification | Safe normalization now | Unresolved before implementation |
|---|---|---|---|
| 6 / `DEC-002` | “Small mandatory core” instead of the full proposal contract | A proposal must remain schema-valid, comparable, reviewable and routable, but only a small core is mandatory across all recipes. | The user has not selected the actual mandatory fields. Integration must not silently retain all ten recommended fields or invent a smaller set. |
| 17 / `DEC-013` | Permit experimental D4 only for supra-agents in an experimental setting | No external or real portfolio effect is authorized. Any future D4 path is limited to an explicitly experimental, fictitious portfolio and a supra-agent operating under a human-owned policy. | This conflicts with the original v1 D2 ceiling and with accepted `IMP-008`, which defers D3/D4. Clarify whether D4 is a post-v1 experiment or an isolated research-only branch. Define the simulated-effect boundary and emergency stop before code. |
| 18 / `DEC-014` | Accept material-proposal pauses, but allow supra-agents to substitute for humans experimentally | Default v1 pauses on every material proposal. A supra-agent may substitute only in an explicitly experimental profile if policy permits and must emit the same immutable resolution/notification receipt. | Define which proposal classes permit substitution, the policy version and approver, whether a human can override before the downstream workflow, and how the UI distinguishes human from supra-agent resolution. |
| 59 / `ERC-027` | Evaluate typed/compiled ContextView against agent-built context | Preserve both as experimental strategies. Neither is the sole accepted production default yet; both must obey the same temporal/evidence boundary and be compared on token use and quality. | Define experiment arms, retrieval budget, quality threshold, leakage tests and whether a hybrid arm is allowed. Do not let “agent-built” mean unrestricted data access. |

### Adjacent P0 / Now implementation constraints

These five answered rows are not part of the `Before v1` decision set, but they
materially bound the next increment:

- row 163 / `IMP-001` modifies the first slice: build only basic ERC hosting
  infrastructure now; use an inspectable synthetic-data experiment; defer
  shipping ERC until sufficient MCP/API/connector integration exists;
- row 164 / `IMP-002` accepts initial visible layers for Portfolio, Mandate,
  deterministic risk evidence, data quality, and gaps/questions, with future
  layers shown empty;
- row 166 / `IMP-004` places reusable ERC/Decision Review panels first in the
  Workflow Cycle Console, embeddable by Agent Studio and future Graph Studio;
- row 168 / `IMP-006` accepts temporal/provenance/readability/pause/no-effect/
  traceability/deterministic-revision gates only insofar as they conform to the
  other answers;
- row 170 / `IMP-008` defers D3/D4 authority, live effects, RavenPack, the full
  thesis graph UI, arbitrary capability creation and general multi-agent
  councils from the first increment.

## Exact recommendations before any new contract

1. Create a reviewed identity-map document and adapter tests before changing a
   contract. It must map overlay capability IDs, evidence identities, agent
   roles and run/artifact references to exact ServiceFabric revisions.
2. Use ServiceFabric as the owner of generic capability definition,
   registration, invocation, result, evidence, effect, tool lifecycle and
   application-artifact semantics. Add portfolio-risk fields by typed adapter,
   not by vendor modification or parallel kernel.
3. Preserve overlay portfolio, monitoring, data-eligibility, analytics and
   policy models as domain authorities. A future ERC references these immutable
   objects and stores only relations, lifecycle metadata and revision lineage.
4. Resolve the duplicated decision types by first documenting their current
   callers and serialization compatibility. Introduce the four-stage decision
   contract only after `DEC-002`, `DEC-013` and `DEC-014` are resolved.
5. Treat the Agent Lab blueprint as an authoring input. Compile it into existing
   role/task/application/runtime contracts; do not register the entire current
   Pydantic object as a permanent platform record.
6. Keep thesis experiment manifests immutable. Derive a general experiment
   shape through projection and comparative tests rather than modifying the
   completed schemas.
7. Establish one lifecycle vocabulary per kind with an explicit mapping to the
   ServiceFabric tool lifecycle. Do not reuse `active` across context items,
   tools, agents and experiments without recording its kind-specific meaning.
8. Before a registry kernel is proposed, inventory storage/retention and UI
   profile findings from P0-02/P0-03 and decide whether a lightweight index over
   immutable manifests is sufficient.

## Conflicts, ambiguities and user questions

1. What exact fields form the “small mandatory core” for every Decision
   Proposal (`DEC-002`)? A safe candidate can be proposed later, but is not
   accepted here.
2. Is experimental D4 (`DEC-013`) deferred beyond v1 as `IMP-008` says, or must
   an isolated fictitious-portfolio path exist in the first vertical slice?
3. Which decision classes may a supra-agent resolve, under which policy, and is
   there a human veto window (`DEC-014`)?
4. For ERC token efficiency (`ERC-027`), are the required comparison arms
   compiled typed view versus bounded agent-built retrieval, or should a hybrid
   be included?
5. Is the portfolio-applied interpretation of the environment a named ERC view,
   a Portfolio Context extension, or a third context? The roadmap explicitly
   leaves this unresolved and no canonical owner exists.
6. Does ERC continuity “across different instances of the same experiment” mean
   shared immutable ancestry only, or may experiments share an active mutable
   branch? The latter would weaken isolation and reproducibility.
7. Should `OperatingProfile` be extended/migrated or should runtime isolation
   use a separately named profile concept to avoid changing its current
   research/personal-portfolio meaning?

## Evidence and checks

- Inspected all eight Phase 0 ADRs, the active workplan, Phase 0 baseline/task,
  development roadmap and external-adapters brief.
- Inspected the overlay package, schema, configuration and contract-note scope.
- Inspected initialized ServiceFabric source read-only from the integration
  worktree at `vendor/servicefabric` commit `7632b61d94a966346f95eb6c5bb2a5ea27f3bc14`.
- Parsed all workbook sheets with read-only XLSX/XML access. The Decision
  Register has 170 data rows; the exact P0/Before-v1 intersection has 20
  answered rows: 16 accepted recommendations and 4 modifications.
- No blank answer was inferred as acceptance. No `Open` workbook status was
  changed or treated as a published policy.

## Deviations, limitations and blockers

- No implementation blocker affected the audit.
- The bundled workspace-dependency discovery call did not return and was
  terminated. Because the workbook required read-only inspection, the audit
  used Python standard-library ZIP/XML parsing and made no spreadsheet writes.
- This audit establishes ownership and gaps; it does not prove runtime
  compatibility between overlay and ServiceFabric types. Adapter contract tests
  are required before implementation.
- Modified workbook choices remain unresolved where the note does not define an
  exact contract or conflicts with an accepted deferral.

## Rollback

Revert this documentation-only commit. No contract, schema, workbook, vendor
source, application, manifest, test, runtime artifact or data was changed.

## Next action

Integration should reconcile this inventory with the storage/runtime and UI/
profile audits, publish the unresolved decision questions, and implement only
the minimum Phase 0 disclosure slice. Phase 1 should begin with the identity map
and adapter contract tests, not a new registry or monolithic ERC model.
