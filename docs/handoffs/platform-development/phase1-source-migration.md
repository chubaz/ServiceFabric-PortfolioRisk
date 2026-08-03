# Phase 1 source and migration audit

- Lane: existing-definition source and migration audit (`P1-03`)
- Branch: `feature/platform-p1-registry-sources`
- Activation parent: `535c427ad7880582db07a9fa5b1ac9e6409c7230`
- Accepted Phase 0 baseline: `21339db19357277ca9a9a1ca50107f1a884d7aeb`
- Scope: read-only source inspection; this handoff is the only repository change

## Executive answer

The seven requested catalogue kinds can be populated from real definitions
already in the repository, but they do not all have the same maturity or
canonical owner. A truthful initial bootstrap can discover **44 projections**:

| Kind | Initial count | Actual source type | Truthful catalogue label |
|---|---:|---|---|
| Agent | 4 | immutable `AgentRole` values | PortfolioRisk agent role |
| Capability | 29 | immutable `CapabilityDescriptor` values | PortfolioRisk capability descriptor |
| Evaluation | 1 | reviewed, validated Day 4 experiment/evaluation manifest | Thesis-scoped evaluation definition |
| Report | 3 | deterministic Python renderer entry points and typed outputs | Report renderer, not a saved report |
| Dashboard | 1 | accepted offline Day 4 dashboard renderer | Dashboard renderer, not a dashboard package |
| Scenario | 3 | application-local scenario catalogue entries | Workbench scenario definition |
| Workflow | 3 | immutable Day 3 architecture treatment definitions | Thesis-scoped workflow treatment |

This set satisfies the seven-kind catalogue increment without manufacturing
generic `EvaluationSuite`, `ReportTemplate`, `DashboardPackage`,
`ScenarioDefinition`, or `WorkflowDefinition` objects that do not yet exist.
The registry should store only an immutable source observation, display
projection, provenance, lifecycle receipts, and a pointer back to the source.
It must not copy source payloads as a new authority or import generated runtime
artifacts.

The six rich Agent Studio recipes, browser-saved agents and portfolios, graph
composer state, synthetic workflow-cycle dashboard, and Full Experiment
JavaScript workflows are useful development candidates but are not in the
initial bootstrap. They are provisional/browser/runtime objects and lack the
stable source/version contract required for automatic indexing.

## Exact initial source map

### 1. Agents — four reviewed role cards

**Authority and locator**

- value contract:
  `packages/risk_agents/src/risk_agents/contracts.py::AgentRole`;
- source catalogue:
  `packages/risk_agents/src/risk_agents/roles.py::AGENT_ROLES`;
- lookup and active projection:
  `ROLE_BY_ID` and `ACTIVE_AGENT_ROLE_IDS`;
- invariant tests:
  `tests/agents/test_roles_and_provider.py`.

**Native identities**

1. `risk.agent.news_sentiment`;
2. `risk.agent.market_data`;
3. `risk.agent.portfolio_exposure`;
4. `risk.agent.alert_recommendation`.

The source provides no explicit semantic version. Each role is code-versioned
and immutable once imported. The projection must therefore display
`Unversioned source revision` plus the short definition digest; it must not
invent `v1`.

**Display projection**

| Catalogue field | Source |
|---|---|
| native ID | `role_id` |
| name | deterministic title case of the final ID segment; projection-only |
| purpose | `objective` |
| inputs / outputs | `input_contracts` / `output_contracts` |
| dependencies | `allowed_capability_ids` |
| authority | `denied_effects`, `human_review_required` |
| evidence and escalation | `evidence_requirements`, `escalation_policy` |
| current availability | membership in `ACTIVE_AGENT_ROLE_IDS` |

These are role cards, not executable LangGraph blueprints. The registry must
not claim that indexing one compiles it, chooses a provider, or makes it
runnable.

### 2. Capabilities — 29 reviewed descriptors

**Authority and locator**

- value contract:
  `packages/risk_capabilities/src/risk_capabilities/contracts.py::CapabilityDescriptor`;
- source catalogue:
  `packages/risk_capabilities/src/risk_capabilities/catalog.py::CAPABILITY_DESCRIPTORS`;
- lookup:
  `CAPABILITY_BY_ID`;
- local runtime adapter and request map:
  `packages/risk_capabilities/src/risk_capabilities/registry.py`;
- invariant tests:
  `tests/capabilities/test_contracts.py` and
  `tests/capabilities/test_registry.py`.

Every descriptor is discovered, even when it lacks a local execution handler.
At this baseline 25 IDs are present in `CapabilityRegistry.capability_ids`.
These four are descriptor-only provider-draft capabilities:

- `risk.capability.alert_recommendation`;
- `risk.capability.market_data`;
- `risk.capability.news_sentiment`;
- `risk.capability.portfolio_exposure`.

Runtime availability is therefore a compatibility observation, not lifecycle
or publication state. An indexed descriptor without a handler is not
`runnable`, `broken`, or absent; it is `defined · local handler unavailable`.

**Display projection**

| Catalogue field | Source |
|---|---|
| native ID | `capability_id` |
| name | deterministic title case of dot-separated ID; projection-only |
| purpose | `objective` |
| inputs / outputs | `input_contract`, `output_contract` |
| authority | `allowed_effects`, `denied_effects` |
| controls | `requires_evidence`, `requires_human_review` |
| local compatibility | exact membership in `CapabilityRegistry.capability_ids` |

No descriptor has a semantic version. Use a digest revision and retain the Git
source observation. Do not conflate this overlay descriptor catalogue with the
ServiceFabric capability-definition registry identified in Phase 0.

### 3. Evaluation — one reviewed thesis evaluation definition

**Authority and locator**

- declarative source:
  `examples/portfolio-risk-thesis/experiments/day4_fixture.yaml`;
- strict contract:
  `examples/portfolio-risk-thesis/src/portfolio_risk_thesis/day4/contracts.py::Day4ExperimentManifest`;
- validated loader and binding verification:
  `examples/portfolio-risk-thesis/src/portfolio_risk_thesis/day4/manifest.py::load_day4_manifest`;
- accepted meaning:
  `docs/contracts/thesis-day4-evaluation-v0.1.md` and
  `docs/architecture/adr/0008-thesis-day4-evaluation.md`;
- invariant tests:
  `tests/thesis/test_day4_manifest.py`,
  `tests/thesis/test_day4_evaluation.py`, and
  `tests/architecture/test_thesis_day4_boundaries.py`.

**Native identity and version**

- ID: `portfolio-risk-day4-synthetic-fixture-v1` from `experiment_id`;
- native version: `1` from `version`;
- semantic manifest digest at this audit baseline:
  `sha256:b7c46cbec914c59676c658c443e498c5de04b5faaa0a4b56e8bff8809d6186cc`;
- truth state: `synthetic_fixture`, reviewed, human review required, effects
  empty, no real provider call.

The item is a thesis-scoped experiment/evaluation definition. It is not a
general evaluation suite and must retain its exact 45-context, B0/B1/A1,
label-firewall, repeatability, pricing, and 270-call authorization semantics.
The registry must never import its generated observations, labels, reports,
dashboard files, or run/evidence manifests as part of this definition.

**Display projection**

- name: deterministic humanization of `experiment_id`;
- purpose: the fixed architecture comparison described by the accepted
  evaluation contract;
- scope: portfolios, windows and architectures from the validated manifest;
- evaluation policy: `label_policy`, `repeatability`, worked-example rules;
- runtime boundary: profile/model metadata and maximum authorized calls;
- governance: `reviewed`, reviewer, `human_review_required`, effects,
  limitations;
- dependencies: exact named input bindings and their declared digests, exposed
  as references rather than embedded files.

### 4. Reports — three deterministic renderer definitions

There is no reusable `ReportTemplate` contract. The real reusable source is
three code-defined renderer entry points with typed result contracts:

| Native symbol | Typed output / meaning | Test evidence |
|---|---|---|
| `risk_analytics.reports.render_report` | `RiskReport`; deterministic Markdown and semantic HTML for one reviewed analytics result | `tests/analytics/test_analytics.py` |
| `risk_analytics.monitoring_reports.render_monitoring_report` | `MonitoringReport`; deterministic monitoring or monitoring-and-replay review | `tests/analytics/test_monitoring_policy_replay_reports.py` |
| `portfolio_risk_thesis.day4.report.render_preliminary_results` | cautious aggregate Day 4 preliminary-results Markdown | `tests/thesis/test_day4_report.py` |

The source locator is the importable symbol plus repository-relative file.
The stable native ID is the importable symbol itself. Version is unavailable,
so revision is content-derived. Display name comes from deterministic symbol
humanization; summary comes from the function docstring and its output contract
description. Input/output contract names come from the function signature and
typed models, not from a copied sample report.

`RiskReport` and `MonitoringReport` instances are outputs, not definitions.
`write_day4_reports` is orchestration over report, chart and dashboard
renderers and should appear as lineage/compatibility for the Day 4 renderer,
not as an extra template. Generated Markdown and HTML are Phase 2 artifacts and
must not be bootstrapped into Phase 1.

### 5. Dashboard — one accepted offline renderer

**Authority and locator**

- implementation:
  `examples/portfolio-risk-thesis/src/portfolio_risk_thesis/day4/report.py::render_dashboard`;
- required content and static/offline boundary:
  `docs/contracts/thesis-day4-evaluation-v0.1.md`;
- acceptance tests:
  `tests/thesis/test_day4_report.py` and
  `tests/architecture/test_thesis_day4_boundaries.py`.

The native ID is the importable symbol
`portfolio_risk_thesis.day4.report.render_dashboard`. It has no semantic
version and receives a digest revision. Its display should say
`Day 4 offline dashboard renderer · thesis-scoped · synthetic fixture support`
and disclose that it generates self-contained local HTML from already
completed evaluation data.

This is not a `DashboardPackage`, not the browser's current live dashboard,
and not an artifact. The workflow-cycle `dashboard_pages` list in
`labs/workflow_cycle_runtime.py` is constructed per ephemeral synthetic
session. Its version counter and agent latches are runtime state, so it is
explicitly excluded from bootstrap until a stable definition is separated
from a session instance.

### 6. Scenarios — three application-local definitions

**Authority and locator**

- source catalogue:
  `apps/portfolio-risk-workbench/analysis_service.py::SCENARIO_CATALOGUE`;
- lookup:
  `SCENARIO_BY_ID`;
- execution request:
  `ReviewedRiskAnalysisService._scenario_request`;
- deterministic analytical contract and implementation:
  `risk_analytics.contracts.ScenarioShock` / `ScenarioResult` and
  `risk_analytics.scenarios.apply_scenario`;
- tests:
  `tests/analytics/test_analytics.py` and application tests that exercise the
  reviewed analysis service.

**Native identities**

1. `broad_market_minus_10`;
2. `concentrated_holding_minus_20`;
3. `rates_sensitive_assets_minus_5`.

The display projection uses `label`, `shocks`, and
`all_snapshot_positions`. The definitions have no explicit version, horizon,
owner, approval receipt, or compatibility declaration. They must be labelled
`Workbench application-local scenario` and use digest revisions. The
projection must not turn a `ScenarioResult` from a run into a reusable scenario
definition.

### 7. Workflows — three accepted Day 3 treatments

**Authority and locator**

- immutable definition contract:
  `portfolio_risk_thesis.day3.contracts.ArchitectureTreatmentDefinition`;
- source factory:
  `portfolio_risk_thesis.day3.treatments.definitions`;
- execution topology:
  `b0`, `b1`, `a1` and `role_payload` in the same module;
- composition invariants:
  `ArchitectureRun` and `ArchitectureComparison`;
- tests:
  `tests/thesis/test_day3_treatments.py`,
  `tests/thesis/test_day3_runner.py`, and
  `tests/architecture/test_thesis_day3_boundaries.py`.

**Native identities and display**

| ID | Roles | Model calls | Truthful label |
|---|---|---:|---|
| `B0` | none | 0 | Deterministic reference treatment |
| `B1` | `risk.agent.alert_recommendation` | 1 | Single structured-agent treatment |
| `A1` | four ordered risk-agent roles | 4 | Ordered specialist-team treatment |

These are accepted thesis treatment definitions, not general Workflow Studio
graphs. They have no semantic version, so use digest revisions. Preserve role
order, fixed call counts, common-context digest, critic boundary, and empty
effects as compatibility/provenance. The three browser `defaultWorkflows` in
`labs/app.js` and the graph composer in `labs/labs.js` remain excluded because
they are browser-state prototypes rather than independently versioned source
definitions.

## Deterministic identity and revision rules

### Stable registry identity

Use a kind-qualified, source-qualified tuple as the logical identity:

```text
(kind, source_namespace, native_id)
```

The serialized key may be
`<kind>::<source_namespace>::<native_id>`, but the tuple fields should remain
separate in storage. Recommended source namespaces are:

| Kind | Source namespace |
|---|---|
| Agent | `portfolio-risk.agent-role` |
| Capability | `portfolio-risk.capability-descriptor` |
| Evaluation | `portfolio-risk.thesis-day4-evaluation` |
| Report | `portfolio-risk.report-renderer` |
| Dashboard | `portfolio-risk.thesis-day4-dashboard-renderer` |
| Scenario | `portfolio-risk.workbench-scenario` |
| Workflow | `portfolio-risk.thesis-day3-treatment` |

Do not globally merge equal display names or equal native IDs. For example,
`A1` outside the thesis treatment namespace is not this workflow. Kind and
source namespace prevent accidental cross-kind and cross-programme aliasing.

### Two digests, one immutable revision

Record two different digests:

1. **Source digest** — SHA-256 of the exact repository file bytes at discovery.
   This proves which source file was observed.
2. **Definition digest** — SHA-256 of canonical JSON containing `kind`, source
   namespace, native ID, explicit native version or `null`, validated semantic
   payload, contract schema/signature, source locator, and an implementation
   digest only when executable code is itself the definition. This identifies
   the meaning indexed for that item. The raw digest of a declarative source is
   provenance and is deliberately not folded into its semantic digest.

Canonical JSON uses UTF-8, sorted object keys, compact separators, JSON-native
Pydantic serialization, explicit `null`, and preserves semantically ordered
arrays such as role order, workflow order, shocks, and output sections. It
must reject NaN/infinity and must not contain absolute paths, timestamps from
the import run, local environment values, credentials, or runtime availability.

For Pydantic values, the semantic payload is `model_dump(mode="json")` plus a
canonical `model_json_schema()` digest. For YAML, validate first and digest the
validated model payload; retain the raw file digest separately. For renderer
functions, use the importable symbol, normalized signature/output contract,
and source-file digest. For application tuples/dicts, validate required keys,
normalize tuples to JSON arrays, and preserve declared order.

The immutable registry revision key is:

```text
(registry_identity, definition_digest)
```

If the source has a native version, record it as `native_version`. It is a
label and collision guard, not a substitute for the digest. If it does not,
display `Unversioned source revision <first 12 digest characters>`; never
invent a semantic version or use mutable `latest` as a run reference.

### Provenance fields

Every discovery observation should include:

- repository identifier and Git commit;
- repository-relative source path and importable symbol/key;
- source and definition digests;
- adapter ID and adapter version;
- native ID and native version, if present;
- contract/schema locator;
- discovery time as receipt metadata only, excluded from the digest;
- source authority classification: canonical overlay, application-local,
  thesis-scoped accepted, or provisional;
- real/synthetic boundary and effect/human-review disclosures where present;
- dependency IDs and compatibility observations;
- lifecycle provenance: discovered by bootstrap, indexed by whom/when, and
  later transition receipts.

The projection may cache small display fields for search, but the source
pointer and digest remain the authority. An inspect action should re-resolve
the source and report `verified`, `changed`, or `unavailable`; it must not
silently fall back to the cached projection as if it were the definition.

## Bootstrap and import behavior

### Network-free discovery

Bootstrap must be explicit and network-free. It should:

1. require the Development operating profile;
2. resolve the repository root and exact Git commit;
3. invoke only allow-listed read-only adapters for the seven sources above;
4. validate every source into its existing contract where one exists;
5. build all observations in memory;
6. sort by kind, source namespace, native ID, then definition digest;
7. reject duplicate IDs, version collisions, invalid definitions, missing
   source files, and any generated/runtime path before writing;
8. show a preview with counts, truth labels, source paths, and errors;
9. on explicit index, persist the batch atomically and append one bootstrap
   receipt containing adapter versions and the complete accepted identity set.

The fixed initial expected counts are 4, 29, 1, 3, 1, 3, and 3 by the table
above. A mismatch fails the accepted-baseline bootstrap and reports the actual
count; it must not manufacture placeholders. A later source revision should
update its reviewed expected-count fixture deliberately.

Bootstrap is repeatable:

- same repository commit and source bytes produce the same ordered identities,
  digests, lineage, and compatibility projection;
- re-indexing an already indexed exact revision is a no-op plus an idempotent
  receipt, not a duplicate version;
- a changed definition under the same logical identity creates a new immutable
  revision and `supersedes` link after preview/confirmation;
- source disappearance never deletes or rewrites an indexed revision.

Discovery should not import `labs/agent_studio.py` or execute generated agents,
open DuckDB, read licensed data, start a workflow clock, call a model/provider,
render a report/dashboard, or load run folders. Importing a source adapter must
have no runtime effect.

### Duplicate and collision rules

| Condition | Required behavior |
|---|---|
| same identity + same definition digest | idempotent no-op |
| same identity + new digest + no native version | preview new source revision; retain prior and link lineage |
| same identity + same native version + different digest | fail closed as a version collision |
| same native ID in another kind/namespace | distinct record; no implicit alias |
| two adapters claim same identity and digest but different locators | report duplicate-source ambiguity; require an explicit alias/authority decision |
| two entries in one source have same native ID | reject the entire source batch |
| display-name collision | allow with visible kind/source badges; never use display name for lookup |
| referenced capability/agent revision absent | record incompatible/unresolved; do not substitute a mutable active version |

### Source unavailable or invalid

An unavailable source produces an adapter error containing the relative source
locator and reason. Counts are `unknown`, not zero. Preview may show other
successful adapters, but the accepted seven-kind baseline bootstrap should not
write a partial batch. Previously indexed revisions remain inspectable with a
visible `source currently unavailable` observation; their lifecycle state is
not silently changed.

An invalid source or digest mismatch also fails closed. For the Day 4 manifest,
use its real loader so bound fixture digests and strict manifest invariants are
verified. Do not downgrade to unvalidated YAML merely to populate the page.

## Provisional sources deliberately excluded

| Source | Why not automatically bootstrapped | Future safe path |
|---|---|---|
| `labs.agent_studio.risk_agent_templates()` | rich compiler blueprints but application-local, model/runtime fields mixed with role meaning, no independently accepted lifecycle | preview as development candidates after an adapter separates authoring blueprint, assignment and runtime |
| browser `localStorage` agents/portfolios | mutable same-name replacement, browser-specific, no immutable source revision | explicit user export/import into a validated draft source |
| generated `.agent-runs/generated-agents/**` | rebuildable compiler output | reference from a later artifact repository, never use as definition authority |
| saved `.agent-runs/agent-lab/**` | run inputs, outputs and evidence, not definitions | later run/artifact index with retention and rights policy |
| workflow-cycle sessions and dashboard pages | per-process synthetic runtime instances | define a stable package/workflow contract first; retain sessions as runs |
| Agent Graph Studio composition | browser-memory preview with no persistent graph definition | explicit validated graph manifest in a later phase |
| Labs Full Experiment `defaultWorkflows` | JavaScript prototype coupled to mutable browser state and synthetic calculation path | migrate only after comparison against accepted workflow contracts |
| `META_CAPABILITY_REGISTRY` | foundation/proposal entries mixed with one available Lab tool; explicitly not canonical capability registry | candidate view with status and adapter provenance, not baseline capability import |
| generated Day 4 reports/dashboard | immutable run artifacts, not reusable definitions | Phase 2 artifact repository references |

The catalogue may later expose these under a separate `Development candidates`
source with strong provisional labels. It must not silently combine them with
the initial accepted-source bootstrap or advertise them as published.

## Migration and acceptance tests

### Source adapter tests

1. Discover exactly four unique `AgentRole` IDs and preserve capability order,
   denied effects and human-review state.
2. Discover exactly 29 unique capability descriptors; show exactly 25 local
   handlers and four descriptor-only capabilities at this baseline.
3. Load the Day 4 fixture through `load_day4_manifest`, verify its bound input
   digests, exact native version and semantic manifest digest, and mark it
   synthetic/effect-free.
4. Resolve all three report symbols and their expected typed output or contract
   surface without calling the renderers.
5. Resolve the Day 4 dashboard symbol without rendering a file and preserve the
   accepted offline/static boundary.
6. Discover the three scenario IDs with exact shock order and values.
7. Discover B0, B1 and A1 in stable order with model-call counts 0, 1 and 4 and
   the exact ordered role IDs.
8. Assert that no adapter reads `.agent-runs`, browser storage, licensed data,
   external absolute paths, credentials, provider clients, or network state.

### Identity, digest and repeatability tests

1. Two clean discoveries at the same commit produce byte-identical canonical
   projections and definition digests.
2. Reordered dictionary keys and YAML formatting/comments do not alter the
   semantic definition digest; source digest may change and remains visible.
3. Reordering semantic arrays such as A1 roles or scenario shocks changes the
   definition digest and, where validated, fails the source contract.
4. Same identity/version with changed payload fails as a collision.
5. Same identity/digest imports idempotently and does not add a version.
6. A changed unversioned definition creates one immutable successor and leaves
   the prior revision resolvable.
7. All source locators are repository-relative and path traversal, symlink
   escape and absolute client paths are rejected.
8. Definition digest excludes discovery time, machine paths and local runtime
   availability; compatibility observations can change without rewriting the
   definition revision.

### Bootstrap and failure tests

1. Preview performs no write; index requires explicit action in Development.
2. A complete bootstrap atomically records all 44 projections and one batch
   receipt; a forced write failure leaves no partial baseline.
3. Repeating the bootstrap yields the same records and an idempotent receipt.
4. Missing or invalid source reports `unknown/unavailable`, never an empty
   catalogue, and leaves existing indexed versions intact.
5. Removing an indexed source from discovery does not delete, retire or archive
   it; lifecycle changes require their own validated receipt.
6. No bootstrap record embeds a full source manifest, report/dashboard output,
   run file, dataset row, prompt response, or generated code.
7. Search and inspect clearly distinguish source authority, lifecycle,
   availability, data truth and human-review/effect boundaries.

### Compatibility and lineage tests

- every agent dependency resolves to an exact capability definition revision
  or displays an unresolved compatibility reason;
- B1/A1 workflow roles resolve to exact agent-role revisions, never to mutable
  active IDs at execution time;
- the Day 4 evaluation links to B0/B1/A1 workflow revisions, report and
  dashboard renderer revisions, and manifest input references without copying
  them;
- scenario render/execution compatibility identifies the deterministic
  `risk.scenario.evaluate` capability and `ScenarioShock`/`ScenarioResult`
  contracts;
- report renderer compatibility names accepted input/output contracts and
  refuses an unknown output schema;
- changing compatibility adds an observation/receipt; it does not rewrite the
  source definition digest.

## Baseline evidence

- Imported the existing immutable catalogues in a network-free Python process:
  four `AGENT_ROLES`, 29 `CAPABILITY_DESCRIPTORS`, and three Day 3 treatment
  definitions.
- Compared descriptors with the local dispatcher: 25 exact local handlers,
  four descriptor-only definitions, and no runtime-only IDs.
- Loaded `day4_fixture.yaml` through the strict Day 4 loader and verified the
  semantic manifest digest shown above.
- Imported the application scenario catalogue: three exact IDs and shock
  definitions.
- Ran the focused existing source-contract suite:
  `python3 -m pytest tests/agents/test_roles_and_provider.py`
  `tests/capabilities/test_registry.py tests/analytics/test_analytics.py`
  `tests/thesis/test_day3_treatments.py tests/thesis/test_day4_manifest.py`
  `tests/thesis/test_day4_report.py -q`: **46 passed**.
- Inspected report and dashboard renderer source, accepted Day 3/4 contracts,
  focused tests, Phase 0 canonical/storage handoffs, the Phase 1 workplan and
  Phase 1 architecture control-plane test.
- Relevant raw source-file SHA-256 values at this branch baseline include:
  `roles.py` `50cfe1eda7136bbfc4ea82fde589275893846ab6c43e9a442802ada7761fcd36`,
  `catalog.py` `4fee0af0418c37125a71959831b911b38ae3d15d2fe86c4e76540fc9d7828dbc`,
  `analysis_service.py` `f8244d347b19d44845c88b8f6f2cc7c4afe84eef9e55827165c8c0c8707b2fa0`,
  `day3/treatments.py` `e15d33a1908b25253520639beed67233bb3cd62ba9eba640492a2a69e95a58d6`,
  and `day4/report.py`
  `36805e4259a21f3340009b1b05946874155e0d778544c27de132e7a0a5a7acf9`.

## Limitations and risks

1. Six of seven kinds lack explicit semantic versions. Digest revisions are
   honest and deterministic but cannot infer author intent such as breaking or
   compatible change.
2. Report and dashboard assets are source symbols, not declarative templates.
   Conservatively including their complete source-file digest can create a new
   revision after an unrelated edit in the same file. A future extracted
   manifest can narrow this without rewriting old observations.
3. The only accepted evaluation and workflow definitions are thesis-scoped.
   Showing them as generic platform defaults would be misleading.
4. The scenario catalogue is application-local and uses private-neutral
   instrument aliases for two targeted shocks. Compatibility with another
   portfolio is not implied.
5. Import-based discovery trusts that allow-listed modules remain side-effect
   free. Tests should enforce no network, provider, data-plane, renderer, or
   runtime initialization during discovery.
6. Registry lifecycle cannot repair incomplete source semantics. A
   `Published` registry projection still means local Development registry
   publication, not product deployment, external distribution, or execution
   readiness.
7. This audit does not define a new canonical cross-kind contract; integration
   owns the smallest projection and storage decision after reconciling P1-01
   and P1-02.

## Preflight deviation

`make preflight` passed the environment check but the repository check stopped
because this specialist worktree's `vendor/servicefabric` directory is
uninitialized and resolves to the superproject commit
`535c427ad7880582db07a9fa5b1ac9e6409c7230`, rather than the pinned gitlink
`7632b61d94a966346f95eb6c5bb2a5ea27f3bc14`. No vendor source was modified or
initialized for this audit. The source mapping above uses overlay definitions
only and relies on the accepted Phase 0 vendor ownership decision.

## Rollback

Revert this single documentation commit. No source definition, registry,
runtime, generated asset, data file, test, configuration, or dependency was
changed.

## Recommended integration action

Implement one adapter interface and these seven allow-listed adapters, first as
a read-only preview. Freeze the 44-item baseline in tests, reconcile the
projection fields and persistence transaction with P1-01, and reconcile source
truth/lifecycle language with P1-02. Only after the preview proves stable
identity, digest, collision, and unavailable-source behavior should the
explicit Development-profile `Index` action persist the batch.
