# Phase 1 registry contracts and persistence audit

## Scope and conclusion

This audit is for the Phase 1 local-development registry projection only. It
does not define a second ServiceFabric registry, alter any canonical contract,
or authorize publication outside the local development profile.

The smallest safe design is an **append-only observation and lifecycle index**
over exact source revisions. It should reuse ServiceFabric's identifier,
digest, owner, provenance, compatibility, lifecycle, and durable-event
semantics, while retaining PortfolioRisk's point-in-time and evidence meaning
at the source. The index must never embed a source definition in order to make
an otherwise unversioned object look registered.

The recommended persistence kernel combines two existing patterns:

1. the symlink rejection, process lock, strict state validation, canonical
   digest, and atomic replacement used by the capability registry; and
2. the immutable, sequenced, digest-chained event history, optimistic version
   check, directory `fsync`, replay, and snapshot reconciliation used by the
   durable operation store.

Neither implementation can be reused unchanged. The capability registry owns
full capability definitions rather than heterogeneous projections, while the
operation store's states describe execution rather than asset publication.

The ServiceFabric submodule was unavailable in this task worktree because a
network checkout was not possible. The audit therefore read the clean,
detached checkout already present in the integration worktree at the exact
pinned submodule commit `7632b61d94a966346f95eb6c5bb2a5ea27f3bc14`.

## Canonical contracts and implementation semantics to reuse

Paths below are relative to the repository root unless prefixed with
`vendor/servicefabric`.

| Concern | Exact source | Reusable semantics | Boundary for Phase 1 |
|---|---|---|---|
| Strict models, identity and digests | `vendor/servicefabric/packages/servicefabric_contracts/src/servicefabric_contracts/common.py`: `ContractModel`, `ImmutableContractModel`, `Identifier`, `Digest`, `SEMVER_PATTERN` | Reject extra fields; immutable revision values; bounded normalized identifiers; `sha256:` digests; semantic versions. | Use these primitives or behaviorally identical validation. Do not relax them for display names or source paths. |
| Ownership and display metadata | `vendor/servicefabric/packages/servicefabric_contracts/src/servicefabric_contracts/metadata.py`: `OwnerReference`, `ResourceMetadata` | Typed owner; bounded name/description; normalized, sorted, credential-safe labels and annotations. | A small derived display projection is allowed, but it remains non-authoritative and must be bound to the exact source observation and adapter revision. |
| Capability meaning | `vendor/servicefabric/packages/servicefabric_capability_model/src/servicefabric_capability_model/models.py`: `CapabilityDefinition`, `CapabilityDefinitionSpec`, `CapabilityMetadata` | Stable semantic declaration, explicitly distinct from invocation and implementation. | Point to this definition. Do not copy its objective, concepts, schemas, effects or suitability lists into registry-owned truth. |
| Persisted capability registration | `vendor/servicefabric/packages/servicefabric_capability_registry/src/servicefabric_capability_registry/registry.py`: `CapabilityRecord`, `RegistrationResult`, `capability_content_digest`, `CapabilityRegistry` | Canonical JSON digest; idempotent same-ID/same-content registration; same-ID/different-content conflict; deterministic list; state/root/lock symlink rejection; mode `0700`; `fcntl` process lock; temp file, file `fsync`, and `os.replace`; strict reciprocal-index validation. | Reuse conflict, locking and filesystem rules. Do not reuse its state shape because it stores the complete capability definition and lacks append-only lifecycle receipts and directory `fsync`. Do not replace this canonical capability registry. |
| Tool revision | `vendor/servicefabric/packages/servicefabric_contracts/src/servicefabric_contracts/tool_revision.py`: `ToolRevision`, `ToolRevisionSpec`, `CompatibilityDeclaration`, `RevisionProvenance`, `SchemaReference` | Exact semantic revision; canonical content digest; source/build provenance; contract-version and compatible-definition declarations; explicit schema/effect/dependency/evidence/idempotency relationships; mutable aliases rejected. | A capability/tool projection should retain exact references and digests, not re-express these nested contracts. The registry must reject `latest`, `current`, `active`, and `production` as revisions or invocation targets. |
| Tool lifecycle | `vendor/servicefabric/packages/servicefabric_contracts/src/servicefabric_contracts/lifecycle.py`: `ToolLifecycleDeclaration` | Maturity, deprecation, and support are three separate axes. Deprecated tools require a replacement, and replacement references are invalid for other deprecation states. | Preserve these source declarations as source facts. Do not flatten them into the local registry publication state. |
| Application definitions and revisions | `vendor/servicefabric/packages/servicefabric_contracts/src/servicefabric_contracts/applications.py`: `ApplicationDefinition`, `ApplicationRevision`, `SourceBundleManifest`, `ArtifactProvenance` | Definition versus immutable revision; exact source digest; deterministic safe relative paths; reviewed revision state; versioned builder provenance; reproducible file manifests. | Reuse definition/revision separation, safe relative path validation and provenance shape. Phase 1 stores neither source bundles nor artifact manifests. |
| Dependency relationships | `vendor/servicefabric/packages/servicefabric_contracts/src/servicefabric_contracts/dependencies.py`: `DependencyContract` and discriminated dependency declarations | Typed dependency kinds, exact tool constraints, URI-like data/graph refs, bounded unique declarations. | Registry compatibility and lineage edges must remain typed. Do not copy the dependency contract; store exact edge references or a source-computed summary. |
| Effects | `vendor/servicefabric/packages/servicefabric_contracts/src/servicefabric_contracts/effects.py`: `EffectDeclaration`, `EffectContract` | Non-mutating effects have no reversibility; mutations require explicit reversibility; `none` cannot coexist with effects. | The registry operation itself is a local state write. Indexing or publication must not imply that the indexed definition can execute effects. |
| Evidence | `vendor/servicefabric/packages/servicefabric_contracts/src/servicefabric_contracts/evidence.py`: `EvidenceRecord` | Bounded evidence identity, source, locator, digest, aware collection time, trust, claims, summary and provenance references; credential-like locators rejected. | Store evidence references only. Evidence bodies, licensed rows and provider responses belong outside the registry. |
| Durable state transitions | `vendor/servicefabric/packages/servicefabric_contracts/src/servicefabric_contracts/durable_operations.py`: `OperationTransitionSpec`, `OperationEventSpec` | Expected/resulting version increments exactly once; aware timestamps; actor and reason; contiguous sequence; prior-event digest chain. | Reuse these invariants for registry receipts, but define registry-specific states and receipts. An asset lifecycle is not a `ServiceFabricOperation`. |
| Durable local event store | `vendor/servicefabric/packages/servicefabric_operations/src/servicefabric_operations/store.py`: `DurableOperationStore`, `StoreLimits`, `canonical_json`, `digest_bytes` | Hashed filesystem key; bounded record/count limits; root/path symlink rejection; same-directory temp write, file `fsync`, atomic replace, directory `fsync`; immutable event files; optimistic concurrency; replay and snapshot verification; corruption fails closed. | Best implementation pattern for receipt log plus derived snapshot. Add a cross-process lock; its `RLock` protects only one process. |
| Idempotent local review records | `vendor/servicefabric/packages/servicefabric_application_factory_state/src/servicefabric_application_factory_state/store.py`: `FileFactoryLifecycleStore` | Safe ID validation; per-run `fcntl` lock; atomic file and directory sync; same record ID/same content converges; different content conflicts; strict identity-bound reload. | Useful supplementary pattern for cross-process locking and idempotent append semantics. Its rewritten aggregate state is not an append-only registry history. |
| Workspace/state root | `vendor/servicefabric/packages/servicefabric_workspace/servicefabric_workspace/models.py`: `WorkspaceLayout`; `resolution.py`: `resolve_workspace` | Mutable runtime state is separate from editable source; `registry`, `artifacts`, `operations`, `locks`, `cache`, `tmp`, and `backups` have separate responsibilities; explicit paths and `SERVICEFABRIC_HOME` are supported. | Put registry state under `WorkspaceLayout.registry`, outside Git when `SERVICEFABRIC_HOME` is configured. Do not expose host absolute paths through the API. Do not use the workspace application registry's silent malformed-record skipping as the kernel behavior. |
| Artifact storage | `vendor/servicefabric/packages/servicefabric_artifacts/servicefabric_artifacts/store.py` | Content-addressed immutable artifact bytes, safe member names, digest verification and convergent writes. | Explicitly out of Phase 1. Registry records may point to an artifact identity but cannot retain artifact files or act as an artifact repository. |
| Agentic task/run envelopes | `vendor/servicefabric/packages/servicefabric_agentic_contracts/src/servicefabric_agentic_contracts/contracts.py`: `AgentTask`, `AgentRunPlan`, `AgentTaskResult`, `AgentHandoff` | Strict, bounded task graphs and results; coding path boundaries are assignment fields, not general agent identity. | Do not copy task/run state into an agent registry projection. Coding paths and verification commands remain run/assignment concerns. |
| PortfolioRisk capability definition | `packages/risk_capabilities/src/risk_capabilities/contracts.py`: `CapabilityDescriptor`; `registry.py`: `CapabilityResult`, `CapabilityInvocationRecord`, in-process `CapabilityRegistry` | Effect-free, evidence-aware risk semantics; finite code-defined handlers; typed requests; invocation history. | Adapt descriptors to canonical ServiceFabric capability definitions/revisions. The in-process dispatcher is not the platform registry, and invocation history is run evidence, not lifecycle history. |
| PortfolioRisk agent role | `packages/risk_agents/src/risk_agents/contracts.py`: `AgentRole`; `roles.py`: `AGENT_ROLES`, `ROLE_BY_ID`; `timeline.py`: `CapabilityReceipt`, `AgentTimelineStep`, `AgentTimeline` | Review-bound allowlist, denied effects, inputs, outputs, evidence and escalation; immutable effect-free receipts and contiguous reviewed timelines. | Index the role by exact source observation. Do not copy prompts, allowlists or policies. Timelines are run evidence and cannot be used as asset lifecycle receipts. |
| PortfolioRisk data revision/provenance | `packages/risk_domain/src/risk_domain/models.py`: `DatasetSnapshot`, `DatasetProvenance`; `packages/risk_data/src/risk_data/research_contracts.py`: `DatasetRevision`, `ResearchDatasetSnapshot`, `PointInTimePolicy` | Immutable content digests; real/synthetic lineage is explicit; source query/revision identity; aware retrieval; rights and publication restrictions; point-in-time rule. | Dataset records are not one of the seven Phase 1 asset kinds and licensed data must not enter the registry. Definition adapters may retain only bounded source/provenance and rights references. |
| Policy and evaluation result | `packages/risk_domain/src/risk_domain/monitoring.py`: `MonitoringPolicyVersion`, `ReplaySpecification`, `ReplayRun`, `MonitoringEvaluation` | Content-addressed policy revision; exact datasets/as-of boundary; deterministic replay; reconciled evaluation metrics and evidence. | These are policy, run and result contracts, not a reusable `EvaluationSuite` definition. Never index a run result as if it were an evaluation definition. |
| Analytical/report results | `packages/risk_analytics/src/risk_analytics/contracts.py`: `AnalysisResult`, `ScenarioResult`, `RiskReport`; `monitoring_reports.py`: `MonitoringReport` | Immutable evidence-rich result digest; scenario reconciliation; report source digest and human-review boundary. | These are output instances. Phase 1 cannot store Markdown/HTML, scenarios' calculated results, or report files. A report asset must be a source-defined template/specification, not a `RiskReport` instance. |
| Current Lab authoring candidate | `apps/portfolio-risk-workbench/labs/agent_studio.py`: `AgentBlueprint`, nested authoring models, `COMPILER_VERSION`, `META_CAPABILITY_REGISTRY` | Strict validation of state, routing, memory, governance, capability latches, structured output, output passes and compiler version. | This is an application-local candidate source, not canonical platform authority. Index only a pointer/digest/adapter projection. Generated `agent.py` and blueprint copies are rebuildable artifacts, not registry definitions. |
| Current app-local scenario candidate | `apps/portfolio-risk-workbench/analysis_service.py`: `SCENARIO_CATALOGUE`, `SCENARIO_BY_ID` | Finite reviewed scenario IDs and shocks in source code. | May be surfaced as a candidate source observation. `ScenarioResult` remains a result. The projection cannot silently upgrade the catalogue into a canonical scenario-definition contract. |

## Definition coverage warning for the seven Phase 1 kinds

The current codebase has strong canonical definitions for capabilities and
application/tool revisions, a risk-specific `AgentRole`, and an app-local
`AgentBlueprint` candidate. It does **not** yet have canonical, reusable
definitions named `EvaluationSuite`, `ReportTemplate`, `DashboardPackage`,
`ScenarioDefinition`, or `WorkflowDefinition`. Existing nearby records are a
mix of app-local catalogues, code templates, transient cycle state, or run
outputs.

Therefore:

- adapters may truthfully expose existing app-local source declarations as
  `candidate` observations, with exact source and adapter provenance;
- `MonitoringEvaluation`, `RiskReport`, `MonitoringReport`, `ScenarioResult`,
  cycle dashboard state, and agent timelines must not be indexed as reusable
  definitions;
- absence of a reusable definition must remain visible as a source gap. The
  registry projection is not permission to invent or duplicate a missing
  canonical contract; and
- a candidate cannot advance to `published` merely because it is indexed. The
  source adapter must declare that the kind is versionable and provide an exact
  immutable revision and digest.

This is the main contract risk against the exit gate requiring all seven kinds.
The integration lane should satisfy the visible catalogue with truthful
candidate sources where they actually exist, and block publication for kinds
whose source lacks an immutable reusable definition.

## Minimum registry projection

### Authoritative projection fields

One record represents one observation of one exact source revision. The
recommended logical key is `(asset_kind, asset_id, source_revision)`. The
serialized contract should contain only:

| Field | Requirement and invariant |
|---|---|
| `api_version` / `kind` | Version the projection schema independently; kind is `RegistryProjection`, not the source asset's kind. |
| `record_id` | Deterministically derived from kind, stable source ID and immutable source revision; bounded ServiceFabric `Identifier`. Never use a display name. |
| `asset_kind` | Closed Phase 1 enum: `agent`, `capability`, `evaluation`, `report`, `dashboard`, `scenario`, `workflow`. |
| `asset_id` | Stable, namespaced source identity. Source adapter validates the source contract and identity match. |
| `source_revision` | Exact immutable semantic revision or content-addressed revision supplied by the adapter. Mutable aliases are rejected. |
| `source_ref` | Opaque bounded source locator such as a `source://` reference or adapter-owned logical locator. It is not a client-supplied host path. |
| `source_digest` | Canonical `sha256:` digest of the exact source definition. Same key/different digest is a conflict, never an update. |
| `source_contract_ref` | Exact contract/schema identity and version used to validate the source. |
| `source_adapter_ref` | Adapter ID and immutable adapter revision/digest. This records how the projection was derived. |
| `owner_ref` | Reuse `OwnerReference`; the adapter may map a canonical owner but cannot synthesize authority silently. |
| `observed_at` / `indexed_at` | Timezone-aware UTC source observation and explicit index times. `observed_at` is not an as-of claim about financial data. |
| `display_projection` | Optional bounded title, short description and normalized labels for search. Mark derived/non-authoritative and bind it to source and adapter digests. |
| `lifecycle_snapshot` | Derived current local registry lifecycle state, receipt sequence and last receipt digest. History remains in immutable receipts. |
| `provenance_refs` | Bounded exact references to provenance/evidence records; no evidence bodies. |
| `compatibility_refs` | Bounded typed references to compatibility assertions/evaluations. Do not copy full nested source contracts. |
| `lineage_refs` | Bounded typed edges between exact registry revisions. |
| `availability` | Explicit discovery/index-source availability observation, separate from lifecycle, maturity, support, operating profile, data truth and rights. |
| `record_digest` | Canonical digest of the immutable projection content, excluding only the digest itself and the replaceable derived snapshot pointer if implementation requires it. |

The stored projection should be immutable. A changed display projection,
adapter revision, source location, owner mapping, or compatibility evaluation
creates a new observation/event or exact source revision according to the
adapter contract; it is never an in-place silent rewrite.

### Fields that must not be duplicated

The registry must not own or embed:

- agent objectives, prompts, prompt messages/templates, instructions, routing
  conditions, graph topology, memory/state schemas, governance text, tool
  latches, output assembly plans, model/runtime settings, or coding paths;
- capability objectives, input/output schemas, request payloads, implementation
  bindings, effects, dependency contracts, policies, code, SQL, or credentials;
- evaluation cases, replay datasets, labels, model responses, metric results,
  reviewer answers or evaluation outputs;
- report Markdown/HTML, report sections, tables, charts, templates, renderer
  files or generated documents;
- dashboard pages, widgets, chart data, HTML/JavaScript, live patches, latched
  agents or cycle state;
- scenario shocks, models, simulated/real time series, calculated results or
  data rows;
- workflow tasks, nodes, edges, assignments, checkpoints, run plans, run state
  or execution receipts;
- full source manifests/definition JSON, source bundles, artifacts, run outputs,
  evidence bodies, licensed/private data, caches, logs, secrets, absolute host
  paths, worktree paths or mutable aliases.

Search title, short description and labels are acceptable only as bounded,
derived display projections with source/adapter provenance. They can always be
rebuilt and never override the canonical source.

## Identity, indexing and immutability rules

1. `discovered` is an API/UI observation, not a persisted lifecycle state.
   Discovery is read-only and may disappear when a source is unavailable.
2. Indexing is explicit. It validates the canonical source, computes the exact
   source digest, assigns an immutable revision, writes an `indexed` receipt,
   and then exposes the persistent projection.
3. Re-indexing the same logical key, source digest and adapter revision is
   idempotent and returns the existing record/receipt outcome.
4. The same logical key with a different source digest is a hard conflict. A
   source change must have a new immutable source revision.
5. A stable ID cannot change kind. A revision cannot change source identity.
6. Runs and dependencies may bind only exact indexed revisions, never a search
   result, display name or mutable alias.
7. Source disappearance changes availability and may block operations, but it
   does not delete the record or rewrite lifecycle history.
8. Lifecycle transitions affect the local registry projection only. They never
   mutate, deploy, delete, activate or execute the canonical source.

## Registry lifecycle

Use one small local-publication axis, separate from the source's maturity,
support, deprecation, review state and runtime availability:

`indexed -> reviewed -> published -> deprecated -> retired`

`published` means visible as a reusable entry in this local development
registry. It is not deployment, production activation, external publication,
runtime availability, safety approval, or authority to execute.

### Transition matrix

| From | To | Allowed? | Required validation |
|---|---|---:|---|
| discovery preview | `indexed` | yes, explicit index command | Source exists and validates; stable ID/kind; exact immutable revision; digest and adapter provenance; owner; no mutable alias; no conflicting key. |
| `indexed` | `reviewed` | yes | Expected receipt sequence; source still resolves to recorded digest; review actor, reason and evidence references; kind adapter reports definition completeness. |
| `reviewed` | `published` | yes | Expected sequence; local development profile; exact source available; compatibility checks pass; required dependencies/lineage targets resolve; no policy block; source kind is a reusable definition rather than a run/output instance. |
| `published` | `deprecated` | yes | Expected sequence; reason; replacement exact revision when one exists. A tool whose source uses `ToolLifecycleDeclaration` must obey its stricter replacement rule. |
| `deprecated` | `retired` | yes | Expected sequence; reason; inbound references are reported; retirement does not delete source or artifacts. |
| `indexed` | `retired` | yes, withdrawal | Expected sequence; reason such as invalid candidate/source withdrawal; must never claim prior publication. |
| `reviewed` | `retired` | yes, withdrawal | Expected sequence; reason and reviewer; must never claim publication. |
| any state | same state | no new transition | Return an idempotent prior result only when the transition command has the same idempotency key and exact intent digest; otherwise reject no-op transitions. |
| `published` | `reviewed`/`indexed` | no | Publish a corrected new source revision, or deprecate this one. History cannot move backward. |
| `deprecated` | `published` | no | Publish a new reviewed revision. Do not resurrect a deprecated exact revision. |
| `retired` | any state | no | Terminal. A replacement must be a new exact revision. |
| any state | deleted | no | Deletion/tombstones and artifact retention are outside Phase 1. |

### Lifecycle receipt

Each transition, including initial indexing, needs an immutable receipt with:

- receipt and record identity;
- `from_state` (`null` only for initial indexing) and `to_state`;
- expected and resulting sequence, incrementing exactly once;
- reason code and bounded safe rationale;
- timezone-aware transition time;
- actor reference and actor type (`human`, `system_adapter`); no anonymous actor;
- exact source revision and digest at transition time;
- source-adapter revision/digest;
- optional approval/evidence/replacement references;
- prior receipt digest (`null` only for sequence one);
- canonical receipt digest and command idempotency key/intent digest;
- operating profile fixed to local development and empty financial effects.

Validation must reject stale sequence/state, broken digest chains, missing
actors/reasons, source drift, unknown internal targets, terminal-state changes,
or transition rules not in the matrix. A source availability observation may
be appended without changing lifecycle, like the durable operation store's
observation event.

## Persistence recommendation

### Root and layout

Resolve the root from the ServiceFabric workspace context, then place this
application projection under a fixed platform-owned child such as:

```text
<WorkspaceLayout.registry>/portfolio-risk/
  registry.lock
  events/
    <sha256(record_id)>/
      00000001.json
      00000002.json
  snapshots/
    <sha256(record_id)>.json
  catalogue.json
```

Tests inject a temporary root. Production-like source code must not default to
a disposable Git worktree or repository-local `.agent-runs` path. User input
never selects filenames. Hash a validated record ID for directory/file keys,
and return opaque record IDs rather than host paths.

Reject an existing symlink at the configured root, lock file, event directory,
record directory, snapshot directory, snapshot file or event file. Create the
root with owner-only permissions (`0700`) and files with owner-only permissions
where supported. Resolve and verify every internal path remains below the root.
Reject absolute/traversing client paths, NULs, drive syntax, empty components,
oversize IDs and oversize records. Apply explicit limits to records, assets,
events per asset, labels, edges and catalogue response size.

### Write protocol

1. Acquire an in-process reentrant lock and a cross-process exclusive lock
   (`fcntl.flock` for the current POSIX development environment) on the fixed
   registry lock file.
2. Reload and strictly validate the current event chain and snapshot. Never
   trust a caller's prior read.
3. Check command idempotency, expected sequence, expected state, source key,
   source digest, adapter revision and transition invariants.
4. Serialize canonical UTF-8 JSON with sorted keys and a final newline. Wrap
   each record in an envelope containing the payload digest.
5. Write the next immutable event to a same-directory temporary file, flush,
   file-`fsync`, atomically install it with exclusive-create semantics, and
   `fsync` the event directory.
6. Rebuild the record snapshot from the authoritative events. Write the
   snapshot through a same-directory temporary file, flush, file-`fsync`,
   `os.replace`, and directory-`fsync`.
7. Rebuild the bounded catalogue projection in the same way. The catalogue and
   snapshots are accelerators; immutable events are the recovery authority.
8. Release locks and remove any uninstalled temporary file in `finally`.

Always commit the event before its derived snapshots. A crash after the event
but before a snapshot update is recoverable by replay. The reverse order would
allow a snapshot to claim a transition for which no immutable receipt exists.

### Startup and corruption behavior

On startup, validate schema versions, record envelopes, event filenames,
contiguous sequence, record identity, source key, prior digest chain,
transition matrix, receipt digest, and snapshot equality with replay. Rebuild a
missing or stale snapshot/catalogue from valid events. Do not silently skip a
malformed record (the workspace application registry's fast-list behavior is
not suitable here). Unknown schema versions, altered immutable events, broken
chains, conflicting source digests, duplicate non-identical events or path
violations fail closed and expose a diagnostic state. Automatic deletion or
silent repair is prohibited.

`fcntl` is POSIX-specific. Hide locking behind a small store interface so a
future platform-supported lock can replace it without changing contracts.

## Provenance, lineage, compatibility and comparison

### Provenance

Keep three layers distinct:

1. **source provenance**: exact source ref, source contract version, immutable
   source revision and digest;
2. **projection provenance**: adapter ID/revision/digest, observation time,
   indexing time, actor and derived-display fields; and
3. **evidence provenance**: references to `EvidenceRecord` or PortfolioRisk
   evidence identities, never copied evidence content.

For data-derived definitions, retain references to data truth, rights and
point-in-time policy, but do not store datasets or infer one field from the
other. Synthetic/real, rights/publication restriction, operating profile,
availability and registry lifecycle remain separate dimensions.

### Lineage

Represent lineage as typed directed edges between exact revision keys. Initial
types should be narrowly bounded to `derived_from`, `supersedes`, `replaces`,
and `composed_from`. A lineage edge contains source and target record keys,
edge type, source/adapter provenance and an optional evidence reference. It
contains no embedded target definition.

Internal edge targets must exist and be the expected kind. Reject self-edges,
duplicates, mutable aliases and cycles for `derived_from`/`supersedes` chains.
An external source URI belongs in provenance, not as a fake internal asset.
Retirement preserves edges. New source revisions explicitly supersede older
ones; indexing order does not imply lineage.

### Compatibility

Compatibility is not a free-text boolean. Use typed assertions/evaluations
bound to exact source digests:

- subject and target exact record keys;
- relationship (`requires`, `compatible_with`, `renders`, `evaluates`,
  `produces`, or source-contract-specific relation);
- exact or semantic-version constraint and relevant schema/contract digest;
- status (`compatible`, `incompatible`, `unknown`, `unavailable`);
- safe reason, checked time, evaluator ID/revision/digest, and evidence refs;
- subject and target source digests observed during the check.

For tool revisions, adapt `CompatibilityDeclaration` rather than weakening it.
For heterogeneous assets, kind adapters compute compatibility against their
canonical contracts. Derived status becomes stale as soon as either digest or
the evaluator revision changes and must be recomputed. `unknown` and
`unavailable` fail closed for publication and invocation.

Examples of relevant compatibility checks are agent capability grants against
exact capability revisions and authority/effect policy, report/dashboard
renderers against exact output schema revisions, workflows against exact agent
and assignment contracts, scenarios against required portfolio/data schemas,
and evaluation definitions against the definition revisions they evaluate.

### Version comparison

The registry provides a stable comparison envelope, not a generic deep diff of
copied definitions. It always compares two exact records of the same kind and
stable asset ID and reports:

- source revision/digest and source-contract change;
- derived display metadata change;
- local lifecycle history difference;
- lineage edges added/removed;
- compatibility assertions and their freshness/status change;
- owner/source/adapter provenance change; and
- a kind-adapter comparison summary with adapter revision and explicit
  `unavailable` when either source cannot be read.

Kind-specific comparison reads canonical source definitions at request time.
Examples include effect/schema/dependency changes for capabilities, authority
or capability-grant changes for agents, and shock/model changes for scenario
definitions. The comparison result may be cached as a derived response, but it
must not become source truth and must be invalidated by either source digest or
adapter revision.

## Required tests

### Projection and adapter tests

- every supported adapter validates its canonical source before producing a
  projection and provides exact source contract, revision, digest and adapter
  provenance;
- all seven kinds share the same small projection shape; no serialized record
  contains prohibited definition or run-output fields;
- source title/description/labels are explicitly derived and rebuildable;
- same key/same source digest is idempotent; same key/different digest fails;
- stable ID cannot change kind and mutable revision aliases are rejected;
- run results (`MonitoringEvaluation`, `RiskReport`, `ScenarioResult`, timeline
  or dashboard session state) cannot be admitted as reusable definitions;
- unavailable or non-versionable app-local candidates cannot be published.

### Lifecycle tests

- every allowed matrix transition succeeds with exact sequence increment and
  digest linkage; every other transition fails;
- stale expected sequence/state loses the race without writing;
- identical idempotency key and intent converges; changed intent conflicts;
- `retired` is terminal; rollback is a new revision, not a backward transition;
- local publication cannot occur outside development and never changes source,
  runtime deployment or artifact state;
- deprecation applies the stricter source contract when required and preserves
  replacement lineage;
- source disappearance adds availability history without deleting or rewriting
  the asset.

### Filesystem and recovery tests

- reject root, lock, event, record and snapshot symlinks; absolute paths,
  traversal, malformed IDs and path escape never reach filesystem names;
- same-process and multi-process concurrent appends preserve exactly one
  sequence; losing writers receive a conflict;
- injected crashes before event install leave no transition; after event
  install but before snapshot/catalogue replacement recover by replay;
- event, snapshot and catalogue writes use file and directory `fsync` and clean
  temporary files;
- altered bytes, malformed JSON/envelopes, oversized records, missing events,
  sequence gaps, duplicate event names, broken chains and snapshot mismatch
  fail closed;
- restart reproduces the same list/search/detail/lifecycle state from events;
- quota exhaustion returns a bounded error and never evicts published records.

### Provenance, compatibility and comparison tests

- provenance identifies exact source and adapter revisions without exposing
  credentials or host paths;
- internal lineage targets exist, kind constraints hold, and cycles/self-edges
  fail;
- compatibility becomes stale after any involved digest/evaluator change;
- missing/incompatible/unknown requirements block publication and invocation;
- version comparison rejects different stable IDs/kinds, uses exact revisions,
  and clearly reports unavailable source detail without fabricating a diff;
- lifecycle changes do not appear as canonical source-definition changes.

### Regression tests

- the existing ServiceFabric capability registry and PortfolioRisk local
  dispatcher remain unchanged and keep their current conflict/invocation
  behavior;
- existing Agent, Dataset and Workflow Cycle tests remain green;
- registry operations create no report files, run artifacts, datasets,
  generated modules, model calls or financial effects.

## Risks and mitigations

| Risk | Consequence | Mitigation |
|---|---|---|
| Projection becomes a second canonical definition | Drift and ambiguous authority | Enforce a field allowlist, source digest binding and adapter contract tests; prohibit raw manifest/definition payloads. |
| Result instance is mislabeled as reusable definition | Registry appears complete but cannot reproduce work | Admission adapters distinguish definition/candidate/result. Block result contracts and publish only versionable definitions. |
| Local `published` is mistaken for deployed/production | Unsafe user expectations | Name it “published to local development registry” in contracts/API/UI; keep deployment and runtime availability separate. |
| App-local code lists have no immutable revision | Silent source drift | Derive a content-addressed source revision plus repository revision; same key/different digest conflicts; block publication where adapter cannot guarantee immutability. |
| Snapshot is treated as authoritative | Crash loses or fabricates transitions | Events are authoritative; event-first write; verify/rebuild snapshots at startup. |
| Cross-process lost update | Broken lifecycle history | Combine `RLock`, fixed `fcntl` lock and expected-sequence compare-and-swap. |
| Symlink/path escape | Registry writes outside the state root | Fixed hashed keys, containment checks and symlink rejection at every component. |
| Compatibility status silently stales | Invalid compositions appear valid | Bind assertions to both source digests and evaluator revision; stale means unknown and blocks publication/use. |
| Event log grows without bound | Disk/latency exhaustion | Explicit Phase 1 quotas and bounded response pagination. No automatic history deletion; retention design belongs to a later governed phase. |
| POSIX-only lock | Portability failure | Isolate store lock interface and test contention; replace with platform lock before non-POSIX support. |

## Unresolved decisions for integration

1. Which existing source declarations will truthfully represent the
   `evaluation`, `report`, `dashboard`, and `workflow` kinds? Nearby current
   objects are mostly result/session instances, not reusable definitions.
2. Is content-addressed revision plus repository commit acceptable for every
   app-local candidate, or must candidates remain unpublishable until they gain
   a canonical semantic revision?
3. Should `deprecated` require a replacement for all asset kinds, or only when
   the source contract requires one? This audit recommends reason plus optional
   replacement generally, while preserving the stricter tool rule.
4. What exact organization owner mapping may an adapter apply when a source
   lacks `OwnerReference`? Missing ownership should block review rather than be
   silently assigned.
5. Which compatibility relations and kind-pair constraints are required for
   the first UI? Start narrowly; do not make an unconstrained general graph.
6. What bounded quotas are appropriate for assets, events per asset and local
   state bytes? Limits must be explicit before publication is enabled.
7. Should initial indexing create only an index receipt, or an index receipt
   plus a separate source-observation event? One event can safely contain both
   for Phase 1 if it preserves both timestamps and meanings.

None of these questions permits copying a definition, accepting a mutable
alias, or weakening local-only publication and effect-free boundaries.

## Rollback

Phase 1 rollback is operationally simple because canonical sources are never
modified:

1. disable the Registry workspace/API and stop new writes;
2. preserve the external registry directory as diagnostic data or move it as a
   single reviewed backup operation; do not delete source definitions or
   artifact repositories;
3. revert the overlay integration commit and restore the prior programme
   pointer;
4. continue using the existing ServiceFabric capability registry,
   PortfolioRisk code catalogues and Labs workflows unchanged; and
5. if a later implementation version is incompatible, use a new registry
   schema/root and an explicit read/validate/migrate command. Never rewrite
   immutable old events in place.

Because publication is local registry metadata only, rollback has no financial,
deployment, source-code-definition or external distribution consequence.
