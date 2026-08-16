# Risk-Episode Case Framework: Integration Feasibility at HEAD

**Assessment date:** 2026-08-14

**Repository:** ServiceFabric PortfolioRisk

**Assessed committed HEAD:** `23f99f536d0889669091a194abf8e88bf63cdfd6`

**Documented comparison baseline:** `6ea08f6b7b88f5759808f2b30466ccdcd106919f`

**Recommendation:** proceed with a reduced P0 scope

**Implementation status:** assessment only; this document does not implement the framework

## A. Executive verdict

| Verdict | Assessment |
|---|---:|
| Overall integration likelihood | **84%** |
| Confidence | **Medium-high** |
| Thesis-scale likelihood | **88%** |
| Product-scale likelihood | **58%** |

The thesis-scale likelihood is higher because the repository already contains most of the difficult experimental infrastructure: immutable portfolio state, point-in-time event selection, bounded capability invocation, experiment hierarchy, replay scheduling, agent wrappers, an `ArchitectureOutput`, evaluation records, local artifact persistence, and a research-facing Workbench. A selected historical-case corpus can therefore be built by extending existing objects.

Product-scale likelihood is lower because the current research application remains a local development plane, the licensed-data bridges are not yet complete provider-neutral production adapters, the detector and model lifecycle is immature, and the Workbench server and JavaScript application have accumulated substantial orchestration logic. None of those limitations blocks a defensible thesis slice.

The decisive recommendation is **proceed with reduced P0 scope**:

1. discover statistical manifestations across a bounded historical universe;
2. construct selected, versioned Silver cases and a small governed Gold subset;
3. replay the existing B0, B1, and A1 architectures under identical point-in-time conditions;
4. evaluate their trajectories using the existing nine dimensions;
5. expose this through one simple `Find cases -> Review case -> Run comparison -> Compare` interface.

Do not attempt a market-wide RiskEpisode truth system, general causal inference, exhaustive near-miss discovery, or a new parallel experiment platform in this scope.

### Important repository-state qualification

This assessment distinguishes committed HEAD from the current dirty worktree. The worktree contains valuable later additions, including a three-arm experimental program, counterfactual work, evaluation plans, and demo material, but those changes are provisional until committed and reconciled. A focused test run over the affected experimental surfaces completed with **45 passing and one failing test**: the failure expects 30 projections while the provisional three-arm program now produces 45. This is a bounded integration mismatch to resolve before Session 1, not evidence that the committed architecture is unusable.

## B. Current repository reuse map

| Proposed component | Existing repository evidence | Reuse | Extend | Build new | Defer |
|---|---|:---:|:---:|:---:|:---:|
| Point-in-time portfolio state | `PortfolioSnapshot` in `packages/risk_domain/.../models.py`; `PortfolioDataContext` in `monitoring.py` | Yes | Minor | No | No |
| Event eligibility and revisions | `EventDatasetSnapshot`, `EventQueryRequest`, and `query_event_snapshot` in `packages/risk_data/.../events.py`; `available_at <= as_of` contracts | Yes | RavenPack adapter | No | No |
| Statistical anomaly detection | `market.anomaly.detect`; `AnomalyDetectionRequest`; `AnomalyReport` in `risk_capabilities/registry.py` | Partial | Yes | Detector registry and additional algorithms | No |
| Typed capability execution | `CapabilityRegistry`, monitoring request types, receipts, and canonical ServiceFabric capability packages | Yes | Scanner capabilities | No | No |
| Deterministic monitoring baseline | `DeterministicContextualMonitoringOrchestrator` and monitoring roles | Yes | Case-aware treatment | No | No |
| Agent roles | News, market, exposure, and alert role cards in `risk_agents/roles.py` | Yes | Experimental configurations | No | No |
| Agent evaluation payload | `AgentStructuredOutput` and evaluation by-products in `risk_agents/artifacts.py` | Yes | Severity forecast fields | No | No |
| Experimental wrapper | `AgentExecutionEnvelope` and telemetry in `risk_agents/experimental_wrapper.py` | Yes | Graph aggregation | No | No |
| Architecture comparison output | `ArchitectureOutput`, `ArchitectureBehaviorSummary`, findings and decisions in `risk_experiments/hierarchy.py` | Yes | Risk-outlook trajectory fields | No | No |
| Experiment hierarchy | `StudyDefinition`, `ExperimentalCase`, `RunInput`, `ArchitectureConfig`, `ExperimentalRun`, `EvaluationRecord` | Yes | Case label references | No | No |
| Replay clock | `ReplaySpecification`, `ReplayRun`, and `BlockingReplayScheduler` | Yes | Historical case stream | No | No |
| Experiment composition | `ExperimentDefinition`, `ExperimentSet`, scientific-design and experiment-object contracts | Yes | Compiler rules | No | No |
| Experiment persistence | `LocalExperimentStore` | Yes | Indexing | No | No |
| Output persistence | `ArtifactManifest` and `LocalArtifactRepository` | Yes | Case bundle kinds/renderers | No | No |
| Registry | `RegistryIdentity`, `AssetKind`, `LocalRegistryStore` | Yes | Registry projections | Avoid a second registry | No |
| CRSP/Compustat access | Read-only DuckDB adapter in `risk_data/licensed_crsp_compustat.py` | Yes | Point-in-time derived series | No | No |
| RavenPack access | Licensed local curated data and private integration surfaces | Partial | Provider-neutral adapter | Small adapter | No |
| Anomaly signal contract | Existing anomaly report is too coarse for a detector sweep | No | Existing evidence conventions | Research payload | No |
| Candidate construction | No committed canonical implementation | No | Experiment/case composition | Candidate graph service | No |
| Silver label | No committed label contract for manifestation intervals | No | `ExperimentalCase` and artifact envelope | Research payload | No |
| Gold case | Existing evidence, artifact, review, and lifecycle primitives | Partial | Governed case bundle | Thin composition | No |
| Risk forecasting | Existing historical metrics and scenario calculations | Partial | Versioned forecast capability | Initial auditable models | Deep challengers |
| Case Design UI | Existing experiments routes and Labs shell | Partial | One focused workflow | Small UI module | Rich studios |
| Model lifecycle | Version fields and receipts exist, but no complete training/promotion system | Partial | Frozen experimental model manifests | Minimal manifest | Online retraining/MLOps |
| Causal inference | Evidence and competing explanations can be stored | Minimal | Descriptive attribution only | No | General causal graph inference |

### What changed since the documented baseline

The baseline commit did not contain the current `risk_experiments`, `risk_artifacts`, `risk_registry`, experimental Workbench Labs application, experimental agent wrapper, or licensed CRSP/Compustat bridge. Those additions materially improve integration feasibility. The principal gap has moved: it is no longer “build an experiment system”; it is now “add disciplined detector, case-label, and case-review layers to the experiment system already present.”

### Concrete repository evidence ledger

The assessment used the following committed implementation surfaces rather than treating the proposal as evidence of its own feasibility:

- **Schemas and domain contracts:** `packages/risk_domain/src/risk_domain/models.py`, `monitoring.py`, and `schema_export.py` define and export immutable portfolio, context, finding, decision, replay, outcome-label, and evaluation contracts.
- **Capabilities:** `packages/risk_capabilities/src/risk_capabilities/catalog.py` registers `market.anomaly.detect`, return/volatility/drawdown/VaR/expected-shortfall/scenario/contribution calculations, `portfolio.data_context.create`, `events.query.as_of`, policy evaluation, contextual monitoring, reporting, replay, and evaluation. `registry.py` contains the current simple anomaly calculation and the typed local capability registry.
- **Agents:** `packages/risk_agents/src/risk_agents/roles.py`, `monitoring.py`, `artifacts.py`, `experimental_wrapper.py`, and `provider.py` provide the four original risk roles, deterministic orchestration, effect-free structured output, execution envelopes, and the explicit rule that ServiceFabric's canonical runtime owns invocation/results.
- **Experiments:** `packages/risk_experiments/src/risk_experiments/hierarchy.py`, `models.py`, `scientific_design.py`, `experiment_objects.py`, `execution_kernel.py`, `replay_scheduler.py`, and `store.py` provide the existing Study-to-Run hierarchy, nine dimensions, object composition, safe output mapping, blocked replay clock, and persistence.
- **Persistence:** `packages/risk_artifacts/src/risk_artifacts/models.py` and `store.py`, plus `packages/risk_registry/src/risk_registry/models.py` and `store.py`, provide content-addressed artifacts, lifecycle state, immutable registry projections, integrity anchors, and local catalogues.
- **Data:** `packages/risk_data/src/risk_data/events.py` and `licensed_crsp_compustat.py` provide event revision/availability logic and a read-only structured DuckDB bridge. The external RavenPack directory proves local data availability but is not yet a committed public adapter.
- **Workbench routes:** `apps/portfolio-risk-workbench/labs/duckdb_server.py` exposes registry, artifact, experiment, replay, trace, architecture-output mapping, fixture-context, and experimental-program routes. This is evidence of a working research integration plane, but also a maintainability reason to keep the new UI small.
- **ServiceFabric adapter:** `apps/portfolio-risk-workbench/servicefabric-package.json` declares the reviewed FastAPI adapter and provider/catalog tools. `vendor/servicefabric` remains read-only. The Labs development server is not itself a complete production ServiceFabric package.
- **Architectural decisions:** ADR-0001 fixes the overlay and read-only ServiceFabric boundary; ADR-0006 fixes point-in-time deterministic replay; ADR-0007 fixes matched B0/B1/A1 inputs and strict outputs; ADR-0008 fixes label isolation, resumability, receipts, and the historical evaluation boundary; ADR-0009 defers presentation-heavy user-facing objects from thesis execution.
- **Current workplan:** `docs/workplans/current.md` states that development samples are not research runs, the interface should use plain terms, licensed data stays outside Git, effects are disabled, P9 execution is blocked by unbound market observations and an unqualified A1 chain, P10 awaits independently reviewed labels, and P11 inherits those blockers. The proposed sessions directly address those active gaps rather than restarting the platform roadmap.

Existing reproducible command surfaces include:

```bash
python -m risk_data.cli run-fixed-query ...
python -m risk_data.cli create-data-context ...
python -m risk_data.cli run-monitoring ...
python -m risk_data.cli run-replay ...
python -m risk_data.cli evaluate-replay ...
portfolio-risk-thesis validate-data ...
portfolio-risk-thesis prepare-day3-experiment ...
portfolio-risk-thesis run-day3 ...
portfolio-risk-thesis validate-day4 ...
portfolio-risk-thesis run-day4 ...
make verify-thesis-day3
make verify-thesis-day4
make verify-platform-phase7
make verify-platform-phase8
make verify-platform-phase11
```

The ellipses denote required local manifest/path arguments; the exact flags must come from each command's `--help` and may not be guessed by an agent contract.

## C. Architectural compatibility

| Area | Compatibility | Judgment |
|---|---:|---|
| Domain model | High | Immutable records, evidence references, portfolio snapshots, findings, decisions, replay records, and evaluation outputs already use the required discipline. New case concepts should be typed research payloads composed into existing envelopes. |
| Capability boundary | High | Typed, bounded operations and invocation receipts fit detector scans, interval construction, event association, forecasts, and evaluation. Arbitrary SQL/Python is unnecessary. |
| Replay | High | The explicit clock and blocking scheduler support point-in-time release and real processing latency without advancing simulated time. |
| Data plane | Medium-high | CRSP and Compustat are already queryable read-only through DuckDB. RavenPack needs a committed provider-neutral adapter and stricter availability tests. |
| Agent orchestration | High for thesis | B0/B1/A1, structured outputs, wrappers, graph behavior summaries, and execution-kernel mapping already exist. A general crew framework can wait. |
| Evidence | High | Evidence references, event revisions, artifact manifests, capability receipts, and Gold packet isolation can be composed without inventing another evidence object. |
| Workbench | Medium | Routes and components exist, but the application is large and terminology-heavy. The case journey must hide internal contracts behind four plain actions. |
| ServiceFabric runtime | Medium | Reviewed capability models are used, but the Labs development server is not yet a fully packaged ServiceFabric production application. This is acceptable for research and should be made explicit. |

### Compatibility with SF-PR invariants

The proposal is compatible only if these rules remain non-negotiable:

- Hindsight case construction is physically and logically separate from ex-ante replay.
- Gold packets and future outcomes are never granted to the evaluated architecture.
- Licensed records remain outside Git; committed manifests point to externally managed snapshots.
- Every detector, feature set, label definition, model, prompt, architecture, capability package, and seed is versioned.
- All portfolio effects are hypothetical; consequential actions remain denied.
- RavenPack supplies event evidence, not the canonical truth of a RiskEpisode.
- Statistical association is never relabelled as a causal or supply-chain relationship without the required evidence.

## D. Consolidation conflicts

The largest design risk is semantic duplication, not missing classes.

| Proposed term | Canonical ownership recommendation |
|---|---|
| `AnomalySignal` | Research analytics payload produced by a versioned detector run; do not replace the existing general `Finding`. |
| `RiskEpisodeCandidate` | Case-lab working record stored as an experiment artifact; it is not an alert or a decision. |
| `SilverCaseLabel` | Versioned label payload referenced by `ExperimentalCase`; keep programmatic label provenance. |
| `GoldCaseFile` | Governed artifact bundle composed of existing evidence references, label, reviewer state, decision checkpoints, and notes. |
| `RiskOutlookSnapshot` | Architecture-cycle projection mapped through `AgentStructuredOutput` into `ArchitectureOutput`; do not add a second output hierarchy. |
| `DecisionBaseline` | Research rubric attached to a case checkpoint; use existing decision vocabulary and `DecisionPoint` semantics. |
| `RunDefinition` | Use existing experiment definition/composition records rather than a new store. |
| `ReplayRun` | Reuse the existing replay and experimental-run records. |
| `RunEvaluation` | Reuse `EvaluationRecord`; attach case-reference metadata. |
| Provider identity | Reuse canonical provider identity and dataset manifests; RavenPack remains an adapter. |
| Model definition | Use a frozen experimental model manifest first; do not build a general MLOps catalogue in P0. |

The existing nine dimensions in `risk_experiments/hierarchy.py` are:

1. confidence and calibration;
2. decision quality;
3. detection quality;
4. efficiency;
5. evidence quality;
6. robustness;
7. severity understanding;
8. stability;
9. timeliness.

`Coverage/Abstention` should be retained as a cross-cutting diagnostic supporting those dimensions, not silently introduced as a tenth headline dimension. A future methodology decision may promote it.

The architecture names also need one explicit mapping. The current product uses **B0 deterministic, B1 single-agent, A1 graph**. The external brief uses A0/A1/A2/A3. P0 should keep the product names and document this equivalence rather than rename working contracts:

| Brief | Current product |
|---|---|
| A0 deterministic | B0 |
| A1 single synthesizer | B1 |
| A2 multi-agent | A1 |
| A3 graph plus critic | Future A1 critic variant |

## E. Minimal thesis-scale vertical slice

### User journey

Add one simple research journey, not another technical studio:

```text
Find cases -> Review case -> Run comparison -> Compare results
```

1. **Find cases** — choose period and bounded universe; run reviewed detectors in the background; show ranked candidate cards and a compact price/signal/event timeline.
2. **Review case** — show scope, manifestation interval, detector support, relevant events, data quality, and label status. Silver is programmatic; Gold requires explicit human acceptance.
3. **Run comparison** — choose cases, portfolio/mandate, B0/B1/A1, capability package, repeats, and budget. Display the data truth and holdout seal before execution.
4. **Compare results** — show architecture trajectories, nine dimension scores, uncertainty, runtime warnings, evidence, and saved reproducible results.

Technical schemas, receipts, hashes, and manifests are not rendered in the research interface. They remain inspectable through persisted machine-readable outputs and Codex handoffs.

### Exact integration surface

| Work | Placement |
|---|---|
| Detector contracts and algorithms | `packages/risk_analytics/src/risk_analytics/` |
| Bounded detector and case capabilities | `packages/risk_capabilities/src/risk_capabilities/` |
| Licensed point-in-time series and RavenPack adapter | `packages/risk_data/src/risk_data/` |
| Case labels and compiler composition | `packages/risk_experiments/src/risk_experiments/` |
| Architecture-cycle structured output additions | `packages/risk_agents/src/risk_agents/artifacts.py` |
| Safe mapping and graph aggregation | `packages/risk_experiments/src/risk_experiments/execution_kernel.py` |
| Case routes | `apps/portfolio-risk-workbench/labs/duckdb_server.py`, initially; later split into a route module |
| Four-stage UI | Existing Workbench experiments area, with a focused module rather than more top-level navigation |
| Persistence | Existing `LocalArtifactRepository`, `LocalExperimentStore`, and registry projections |
| Tests | `tests/analytics`, `tests/capabilities`, `tests/data`, `tests/experiments`, `tests/agents`, `tests/application`, `tests/journeys` |

### Objects to reuse

- `PortfolioSnapshot` and `PortfolioDataContext`
- `EventDatasetSnapshot` and point-in-time event query
- `EvidenceReference`, capability receipts, data-quality warnings
- `StudyDefinition`, `ExperimentalCase`, experiment definitions and object sets
- `AgentStructuredOutput`, experimental wrapper, `ArchitectureOutput`
- `ReplaySpecification`, `BlockingReplayScheduler`, `ExperimentalRun`
- `EvaluationRecord`, `ArtifactManifest`, and registry identity

### Thin research payloads to add

- `DetectorDefinition` and `DetectorRun`
- `AnomalySignal`
- `RiskEpisodeCandidate`
- `SilverCaseLabel`
- Gold case bundle schema composed from existing evidence/review objects
- Case-label bundle reference on an `ExperimentalCase`
- Frozen forecast/model manifest

These do not all require top-level public domain classes. Prefer package-local Pydantic payloads and artifact schemas until reuse demonstrates canonical value.

### Initial algorithms

P0 includes:

- robust factor- or sector-adjusted residual z-score;
- CUSUM for cumulative deterioration;
- one deterministic change-point method;
- group breadth/correlation detector;
- morphology-specific interval construction;
- candidate grouping by overlapping time, canonical entity/group scope, and reviewed event association.

A multivariate unsupervised detector is useful but can be a Session 3 challenger. Deep temporal models, diffusion models, and causal discovery are deferred.

### Bounded capability additions

Illustrative IDs, to be finalized against the registry before implementation:

- `market.anomaly.scan`
- `market.regime.detect`
- `case.interval.construct`
- `case.candidate.group`
- `case.events.associate`
- `risk_metric.forecast`
- `experiment.case.compile`

Do not expose raw SQL, unrestricted Python, future outcomes, or Gold packets to evaluated agents.

### Data required

- Read-only CRSP daily prices, returns, volume, identifiers, delistings, and corporate-action treatment.
- Point-in-time Compustat annual/quarterly facts and CCM links.
- RavenPack records with event time, availability time, entity, taxonomy, relevance, novelty, sentiment/intensity, amendments, and retractions.
- Market/sector returns and a small factor set; supplement only where rights and point-in-time semantics are clear.
- Selected portfolios and mandates already represented by versioned experiment objects.

The local DuckDB snapshot contains approximately 107.7 million CRSP daily rows, 5.15 million monthly rows, 0.91 million Compustat annual rows, 2.05 million quarterly rows, and 3.55 million curated RavenPack records for 2013–2017. That is sufficient for a bounded case sweep without committing licensed bytes.

### Minimum proof corpus

For the first end-to-end proof:

- 3 governed Gold cases with different morphologies;
- 3–6 additional Silver cases;
- at least 2 ordinary/negative-control intervals;
- at least 1 incomplete-data or abstention case;
- B0, B1, and A1 under the same information and capability conditions;
- at least 2 repeats for LLM treatments.

After the journey is reliable, expand toward 20–40 Silver cases, 5–10 near misses, and 10–20 ordinary/negative controls. Do not make that larger corpus a prerequisite for proving the software path.

## F. Ten-session implementation plan

The executable development contract is stored in:

`config/agent/thesis-risk-episodes/ten-session-development-contract.yaml`

| Session | Outcome | Visible proof |
|---|---|---|
| 1 | Reconcile baseline, terminology, contracts, and current worktree | Clean focused gate and contract inventory |
| 2 | Detector contracts plus robust residual z-score and CUSUM | A real-data signal preview with detector receipts |
| 3 | Change-point, breadth/correlation, interval construction, candidate grouping | Ranked candidate timeline |
| 4 | Silver/Gold case composition, review lifecycle, and leakage boundary | Reviewable saved case bundle |
| 5 | RavenPack association, Compustat context, controls, and data-quality paths | Evidence panel with eligible/retrospective separation |
| 6 | Minimal four-stage Case Design UI | Find and review a case without reading internal schemas |
| 7 | Case compiler, B0/B1/A1 qualification, packages, budgets, and repeats | Valid run matrix before execution |
| 8 | Point-in-time replay and architecture risk-outlook trajectories | Cycle-by-cycle comparison with blocked simulated clock |
| 9 | Nine-dimension evaluation and diagnostic coverage/abstention | Reproducible evaluation record and warnings |
| 10 | Comparison UI, artifact retention, journey tests, and release handoff | One accepted end-to-end historical comparison |

Sessions are sequential contracts, not permission to execute all work in one turn. Each session must preserve the previous acceptance gates and stop on a genuine safety, leakage, data-rights, or methodology blocker.

## G. Methodological feasibility

| Component | Feasibility | Position |
|---|---|---|
| Robust residual, CUSUM, breadth, change-point detectors | Standard engineering | Implement P0 with frozen parameters and versions. |
| Morphology-specific intervals | High | Deterministic and directly testable. |
| Candidate grouping | High with constraints | Association graph, not causal truth. |
| Selected Silver cases | High | Programmatic, reproducible, confidence-qualified. |
| Small governed Gold corpus | High with human review | Case agents may prepare; cannot approve their own Gold labels. |
| RavenPack association | High with data conditions | Requires point-in-time adapter, entity linkage, amendments, and rights discipline. |
| Severity forecast | Research-feasible | Use the agreed adverse portfolio impact target and simple walk-forward models. |
| Near-miss cases | Methodologically uncertain | Use a curated operational definition; do not claim exhaustiveness. |
| Calibration | Conditional | Stratified case sampling produces confidence scores unless recalibrated to representative base rates. |
| Decision quality | Research-feasible | Separate ex-ante appropriateness from ex-post branch regret. |
| General causal claims | Inappropriate for P0 | Permit descriptive attribution and competing explanations only. |
| Market-wide Gold ontology | Inappropriate for thesis window | Future research. |

### Detection and severity methodology already agreed

The existing plans under `docs/thesis/evaluation-plan/` define two important constraints:

- Detection quality requires labelled risk episodes and purposeful negative, ambiguous, immaterial, and no-event intervals; population recall must not be claimed from a selected corpus.
- Severity should primarily estimate expected adverse portfolio impact in basis points over five sessions, with one- and twenty-session diagnostics. A shared deterministic/statistical baseline may be used by all architectures; agents are evaluated on justified adjustments rather than receiving a different scale.

The `ArchitectureOutput` and agent by-products should be extended only enough to carry those structured estimates and their evidence. Narrative quality is not a substitute for evaluable fields.

## H. Data and compute feasibility

### Relative requirements

- **Storage:** licensed source data already dominates storage. Detector outputs should be sparse, columnar, and content-addressed. Selected case bundles are small. No duplicate copies of CRSP, Compustat, or RavenPack should be stored per experiment.
- **Query volume:** a broad 2013–2017 feature pass may scan tens of millions of daily rows. Compute normalized features once per versioned data snapshot, partition by date/scope, and reuse them across cases.
- **Detector runtime:** robust rolling detectors and group aggregation are practical on local DuckDB/Polars. Change-point and unsupervised challengers should run on selected series or cached feature panels, not every series on every request.
- **Replay volume:** the full Cartesian matrix will explode. Compile an explicit bounded matrix and reject accidental unbounded combinations.
- **LLM volume:** use no LLM calls for statistical sweeping or Silver interval construction. Invoke LLMs only for selected evidence review and evaluated architectures.

### Initial budget envelope

An initial proof of 8 case/control intervals x 3 architectures x 2 repeats creates 48 runs. Depending on the graph, this is approximately tens to low hundreds of model calls, not thousands. Cache deterministic context and capability results by content digest. A larger 30-case study should be staged only after the proof path passes leakage, stability, and data-quality gates.

Cost and latency must be recorded per run, but no fixed monetary estimate should be embedded in the contract because model routes and prices change. The runtime profile supplies the current budget at execution time.

### Scaling effects

Scaling can improve evidence coverage and specialist reasoning, but it also increases latency, tokens, coordination overhead, nondeterminism, and false-positive opportunities. Architecture and capability package must therefore remain independent experimental factors. More agents or more tools are not automatically a stronger treatment.

## I. Test and acceptance strategy

### Unit and schema tests

- Detector input/output schema validation.
- Robust residual and CUSUM known-path tests.
- Change-point and interval hysteresis tests.
- Candidate graph association and separation tests.
- Silver/Gold bundle validation.
- Forecast horizon and severity-unit validation.
- `AgentStructuredOutput -> ArchitectureOutput` mapping tests.

### Data and leakage tests

- CRSP corporate action, delisting, and survivorship treatment.
- Compustat point-in-time availability.
- RavenPack event availability, amendments, retractions, and entity mapping.
- Every ex-ante query enforces `available_at <= replay_time`.
- Gold packet and future outcome fields are absent from architecture inputs.
- Feature transformations do not use future windows.
- Train/validation/test intervals are purged and embargoed where outcomes overlap.

### Replay and architecture tests

- Deterministic replay reproduces identical outputs.
- Simulated clock freezes from trigger through final capability/agent output.
- Capability grants differ only when the compiled experimental factor says so.
- B0 cannot invoke generative capabilities.
- B1 and A1 use the same sealed input packet and capability package for matched runs.
- Graph contribution, critic correction, disagreement, and coordination telemetry aggregate without overwriting node outputs.
- All effects remain denied.

### Evaluation tests

- Detection denominators are derived from the selected label bundle, not architecture outputs.
- Severity units and horizons match the case labels.
- Timeliness compares architecture warning trajectories with manifestation intervals.
- Evidence is temporally eligible and source-supported.
- Confidence/calibration distinguishes representative from stratified sampling.
- Robustness perturbations preserve the reference label and vary only declared inputs.
- Stability uses repeated matched runs.
- Efficiency includes all model, capability, query, retry, and human-review costs.
- Coverage/abstention diagnostics are calculated without silently changing the nine headline dimensions.

### Journey acceptance

One selected historical case must execute:

```text
licensed external snapshots
  -> versioned detector signals
  -> candidate and Silver interval
  -> governed Gold evidence bundle
  -> saved Case Design
  -> matched B0/B1/A1 Run Definitions
  -> point-in-time replay trajectories
  -> hypothetical decisions
  -> nine-dimension Evaluation Records
  -> persisted comparison report
```

The journey fails if future information is visible, Gold evidence leaks, a capability receipt is missing, a run is not reproducible where expected, an LLM output is not structurally valid, or the user cannot tell what data and method produced a result.

## J. Blockers and open decisions

### Critical

1. **Case-label independence:** the evaluated architecture must not create or approve its own reference labels.
2. **Point-in-time leakage:** Compustat and RavenPack availability semantics must be proven for every field used.
3. **Current worktree reconciliation:** the provisional three-arm output-count mismatch and any related uncommitted changes must be resolved before building on them.

### High

1. Select the bounded initial universe and 3–8 proof cases/controls.
2. Freeze the manifestation and interval thresholds before comparing architectures.
3. Decide who accepts Gold cases and record reviewer confidence/agreement.
4. Finalize the severity target and unit in the structured outputs.
5. Establish a committed, provider-neutral RavenPack adapter without licensed bytes in Git.

### Medium

1. Select a small factor/sector benchmark set for residual returns.
2. Decide whether the first change-point implementation is PELT or a dependency-light deterministic alternative.
3. Select the first robustness perturbations and repeat count.
4. Decide whether critic treatment is part of the initial study or a later A1 variant.

### Low

1. Final visual styling of case timelines.
2. Additional unsupervised challengers.
3. Rich causal-case presentation.

No decision is required now about a universal RiskEpisode ontology, supply-chain modelling, live actions, online retraining, deep learning, or production MLOps.

## K. Final recommendation

**Proceed with reduced P0 scope.**

The repository is substantially more prepared than the documented baseline. Its core experiment, replay, structured-output, evidence, capability, and persistence systems should be extended, not replaced. The remaining work is achievable over ten bounded development sessions if the scope stays centered on selected cases and a simple user journey.

The concept should be redesigned only in these respects:

- make `RiskEpisodeCandidate`, Silver, and Gold case records research compositions rather than a new universal domain hierarchy;
- use one four-stage Case Design journey instead of more studios and categories;
- keep B0/B1/A1 naming and treat capability packages as independent factors;
- make evaluation trajectories and structured by-products primary, with narrative reports as renderings;
- delay product-scale provider/runtime hardening until the thesis vertical slice is reproducible.

Success is not a perfect market oracle. Success is a defensible, reproducible answer to this narrower question:

> Under identical historical information, case, portfolio, mandate, capability, and budget conditions, do bounded agentic architectures improve risk detection, interpretation, and decision support relative to a deterministic baseline?
