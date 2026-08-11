# Experiment object readiness inventory

- Assessment date: 2026-08-10
- Governing cycle: STUDIO-S5 experiment object model and readiness gate
- Purpose: determine what may enter the first Fixture Context development cycle
- Status meanings: `absent`, `draft`, `threshold_ready`, `definitive`

This is a provisional engineering assessment, not an acceptance record. Each
status must later be superseded by a tested, immutable assessment containing an
exact object version and evidence digest.

## Apparatus foundations

| Desired object | Current evidence | Status | Blocking gap |
|---|---|---:|---|
| `ExperimentDefinition` | persistent local store; exact workflow/evaluation, scientific-design and experiment-object-set Registry gates | `threshold_ready` | Legacy records may omit the new optional references |
| `ExperimentSet` | strict stored comparison membership and bounded planning | `threshold_ready` | No factor-matrix compiler or worker |
| `ArtifactManifest` / retained run | governed content-addressed repository and lifecycle | `threshold_ready` | Future worker must retain through the same authority boundary |
| retained-run audit and `AcceptanceRecord` | S4 complete-inventory comparison and immutable supersession | `threshold_ready` | Acceptance needs runs carrying explicit thesis-design identities |
| experiment worker | no workflow resolver, checkpoint contract or run/artifact linker | `absent` | Implement only after threshold-ready starting objects and P7/P8 |

## World and information

| Desired object | Current evidence | Status | Blocking gap |
|---|---|---:|---|
| `PortfolioVersion` | S5.2 immutable snapshot binding, as-of, currency and truth class | `threshold_ready` | Candidate portfolio content must be registered for the pilot |
| `DataSnapshotManifest` | S5.3 closed dataset/revision/rights manifest with point-in-time rejection | `threshold_ready` | P7 must materialize and verify the bound source bytes |
| `MarketEnvironmentSnapshot` | S5.3 portfolio-independent environment over an exact data manifest | `threshold_ready` | P7 must implement resolution from eligible source observations |
| `ScenarioDefinition` | S5.3 observed/historical/synthetic/simulated contract with calibration and seed rules | `threshold_ready` | Empirical calibration specifications remain future versions |
| `PortfolioEnvironmentView` | S5.3 deterministic portfolio/environment/scenario join identity | `threshold_ready` | P7 must implement the resolver named by the contract |
| `ContextGraphSnapshot` | S5.3 closed, point-in-time node and edge set | `threshold_ready` | The teaching graph is deliberately minimal |

## Mandate, risk and authority

| Desired object | Current evidence | Status | Blocking gap |
|---|---|---:|---|
| `MandateVersion` | S5.2 objective, horizon, universe, constraints and effective interval | `threshold_ready` | Candidate mandate content requires portfolio-owner review |
| `RiskPolicySet` | S5.2 exact mandate link, executable threshold rules, precedence and missingness policy | `threshold_ready` | Initial rule coverage is deliberately narrow |
| `AutonomyPolicy` | S5.5 explicit proposal and resolution actor matrix | `threshold_ready` | First candidate is human-only |
| `SupraAgentPolicy` | S5.5 bounded evidence, abstention, decision-class and resolution-budget contract | `draft` | Disabled until a later experimental treatment and safety evaluation |
| `EffectPolicy` | S5.5 versioned disabled external effects and simulated-effect allow-list | `threshold_ready` | Simulated effects remain empty in the first candidate |

## Reachable processing resources

| Desired object | Current evidence | Status | Blocking gap |
|---|---|---:|---|
| `CapabilityDefinition` | strict descriptors/invocations/outcomes, canonical ServiceFabric runtime and Capability Studio | `draft` | Studio review is open; no closed experiment-ready capability snapshot |
| `CapabilityPack` | S5.4 closed exact capability identities and agent-selection rule | `threshold_ready` | Underlying Capability Studio candidates still require review |
| `ConnectorDefinition` / `ProviderAdapter` | S5.4 rights, opaque credential reference, freshness, temporal semantics and empty effects | `draft` | No general connector is attached to the teaching envelope |
| `DatasetAccessGrant` | S5.4 capability/dataset/operation scope with fixture-as-of rule | `threshold_ready` | P7 must enforce grants during materialized access |
| `AgentBlueprint` | Agent Studio blueprint compiler and fixture runs | `draft` | S3 remains in progress; experiment identity does not resolve to a canonical executor |
| `AgentGraphDefinition` | generated LangGraph-like execution and routing configuration | `draft` | No separately registered graph identity or stable executor contract |
| `WorkflowDefinition` | thesis treatment workflows are discoverable and can be registered | `draft` | No Registry-to-runtime resolver using exact pinned object versions |
| `ModelRoutePolicy` | S5.4 exact routes, fail-closed fallback and call bound | `threshold_ready` | Pricing metadata belongs in a later route version |

## Evaluation and presentation

| Desired object | Current evidence | Status | Blocking gap |
|---|---|---:|---|
| `ResearchQuestionDefinition` | strict S5.1 identity with population, unit, intervention, comparator and estimand | `draft` | Candidate thesis content has not received methodological acceptance |
| `HypothesisDefinition` | strict S5.1 identity linked to an exact research question | `draft` | Candidate direction and falsification rule require methodological acceptance |
| `BaselineDefinition` | strict S5.1 comparator kind, behaviour and resource references | `draft` | B0/B1/A1 candidates are not yet registered design-pack versions |
| `InformationRegimeDefinition` | strict S5.1 evidence categories, reachable resources and missingness/disclosure rules | `draft` | The future CapabilityPack and DatasetAccessGrant identities are not available |
| `RiskOutcomeDefinition` | strict S5.1 horizon, ordered states, breach, mitigation and censoring semantics | `draft` | The actual portfolio-risk scale and labelling protocol require acceptance |
| `MetricDefinition` | strict S5.1 estimand, formula, aggregation, direction, missingness and uncertainty semantics | `draft` | No accepted formula implementation or evaluation fixture yet |
| `ScientificDesignPack` | six linked S5.1 definitions; exact Registry identity and S4 comparison projection | `draft` | No candidate pack content has been reviewed and registered |
| `EvaluationSuite` | S5.6 case set, seeds, repeats, metric thresholds and sealed-OOS rule | `threshold_ready` | Candidate cases and thresholds require methodological approval |
| `ReportTemplate` | S5.6 ordered sections, required evidence roles and hidden-calculation denial | `threshold_ready` | Candidate presentation content remains simple |
| `DashboardPackage` | S5.6 views, exact metric identities and hidden-calculation denial | `threshold_ready` | Candidate presentation content remains simple |
| `ExperimentObjectSet` | all six packs, cross-reference validation, four component digests and one Fixture digest | `draft` | The tutorial candidate must be reviewed and registered before P7 |

## Runtime evidence and decisions

| Desired object | Current evidence | Status | Blocking gap |
|---|---|---:|---|
| capability and agent receipts | immutable invocation records, timelines and retained run files | `threshold_ready` | Standardize them under the future run-trace envelope |
| `Finding` / evidence bundle | domain findings, report findings and evidence references | `threshold_ready` | Normalize identities across analytical packages |
| `DecisionProposal` and human resolution | accepted Phase 5/6 immutable decision lifecycle | `threshold_ready` | Fixture/run linkage and experimental authority reference are missing |
| supra-agent resolution | policy attachment point exists; teaching candidate is explicitly disabled | `draft` | Runtime resolution and safety evaluation remain outside S5 |
| simulated effect and observed outcome | outcome labels exist; external effects are empty | `draft` | No isolated simulation ledger linking decision, counterfactual and later risk outcome |

## Admission decision for PLATFORM-P7

P7 must not start with the entire desired catalogue. Its first admissible set is:

1. `ExperimentDefinition`, `ArtifactManifest` and retained-run audit as existing
   threshold foundations;
2. threshold versions of `PortfolioVersion`, `MandateVersion`, `RiskPolicySet`,
   `DataSnapshotManifest`, `MarketEnvironmentSnapshot`, `ScenarioDefinition`
   and `PortfolioEnvironmentView`;
3. a closed `CapabilityPack` plus its `DatasetAccessGrant` objects;
4. exact agent/workflow, model-route and human-only authority references;
5. the five explicit thesis-design identities.

All required contract shapes and digest rules now exist. Admission remains
blocked until the tutorial candidate's scientific content, mandate, risk rules
and evaluation thresholds are reviewed and the resulting exact object set is
saved in the Registry. Contract completion is not methodological approval.

Supra-agent resolution, simulated effects, general connectors, adaptive graph
topologies and definitive dashboards are later treatments. They must not block
the first human-reviewed Fixture Context, but their future attachment points
must be present in the contracts now.

## Immediate revision batches

| Batch | Objects | Result required before next batch |
|---|---|---|
| S5.1 Scientific identity | research question, baseline, information regime, risk outcome, metric | One immutable design pack that S4 can read without inference |
| S5.2 Governed portfolio | portfolio, mandate, risk policy, authority/effect placeholders | One cross-validatable portfolio-governance pack |
| S5.3 Reproducible world | data manifest, market environment, scenario, portfolio-environment view | Same world digest on repeated resolution and strict point-in-time tests |
| S5.4 Reachable resources | capability pack, dataset grants, connector/model-route references | Finite resource-envelope digest and denied undeclared access test |
| S5.5 Processing policy | agent, graph, workflow, autonomy and supra-agent policy | Exact resolver identities; supra-agent remains disabled initially |
| S5.6 Output/evaluation | evaluation suite, report and dashboard definitions | Views consume retained evidence without adding calculations |

All six implementation batches pass the S5 contract/tutorial gate. The table
above remains the revision sequence for candidate content and later definitive
versions rather than unfinished contract work.
