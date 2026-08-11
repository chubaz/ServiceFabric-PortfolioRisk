# STUDIO-S5 — experiment object model and readiness gate

- Status: implementation complete and locally verified; candidate review pending
- Parent boundary: locally verified STUDIO-S4 and accepted PLATFORM-P6
- Successor: PLATFORM-P7 Fixture Context
- External financial effects: disabled

## Outcome

Define the smallest complete set of versioned objects required to create a
reproducible but dynamically explored portfolio-risk environment. Classify each
object as information, processing, policy, presentation, evaluation or runtime
evidence; identify its authoritative owner; and assess whether its current
implementation is absent, draft, threshold-ready or definitive.

This cycle defines and assesses objects. It does not build Fixture Context,
attach an experiment worker, execute a supra-agent decision or add another
general-purpose Studio.

The initial evidence-backed assessment is maintained in
`docs/thesis/experiment-object-readiness.md`.

The first bounded implementation batch is
`docs/workplans/platform-development/studio-foundation-5-1-scientific-identity-pack.md`.

Verification: `make verify-studio-foundation-s5`

Engineering qualification and the human methodology checklist are recorded in
`docs/handoffs/platform-development/studio-foundation-s5-qualification.md`.
The repeatable aggregate gate is
`make verify-studio-foundation-s5-qualification`. Engineering qualification
does not satisfy exit gate 10: one exact candidate still needs human review and
an immutable acceptance record before PLATFORM-P7.

## Implementation record — 2026-08-10

The complete S5 contract surface is implemented in
`packages/risk_experiments/src/risk_experiments/experiment_objects.py`:

- S5.2: independently digest-bound portfolio, mandate and executable risk-policy
  definitions composed into `PortfolioGovernancePack`;
- S5.3: point-in-time data manifest, portfolio-independent market environment,
  scenario, portfolio-applied view and closed context graph composed into
  `WorldContextPack`;
- S5.4: capability pack, dataset grants, connector descriptions and model route
  composed into a finite `ResourceEnvelope` that denies undeclared resources;
- S5.5: exact agent/graph/workflow processing identity, autonomy, supra-agent and
  effect policies composed into `AuthorityEnvelope`; the teaching candidate is
  human-only, supra-agent-disabled and effect-free;
- S5.6: evaluation suite, report template and dashboard package composed into
  `OutputEvaluationPack`, with hidden calculations structurally denied.

`ExperimentObjectSet` validates all cross-pack references and calculates the
four component digests plus `fixture_context_digest`. `ExperimentDefinition`
can pin the set through one saved `experiment_object_set` Registry identity.
Legacy records remain readable. The application still has no Fixture resolver
or experiment worker.

Seven read-only tutorials are indexed at `docs/tutorials/s5/README.md` and use a
deterministic reviewed-synthetic teaching fixture. Tutorial output is explicitly
not thesis evidence.

The full `make verify-studio-foundation-s5` gate passed 63 focused contract,
Registry, comparison, API, architecture and tutorial tests, followed by Python
compilation, execution of all tutorial sections, manifest-integrity and diff
checks. This is a local working-candidate result, not an immutable or merged
candidate.

## Reproducibility rule

An agent may choose dynamically only from resources that were reachable at the
start of the run. Runtime reasoning can select capabilities, issue bounded
queries, combine evidence, create interpretations and propose decisions. It
cannot silently add a dataset, connector, capability, model, policy or authority
that was outside the resolved resource envelope.

The apparatus therefore separates four immutable starting digests:

1. `world_context_digest` — portfolio, market/environment, scenario and
   point-in-time data state;
2. `resource_envelope_digest` — reachable capabilities, data access grants,
   connectors, knowledge/context graph and model routes;
3. `authority_envelope_digest` — mandate, risk policies, autonomy, decision,
   supra-agent and effect permissions;
4. `evaluation_envelope_digest` — research question, hypothesis, baseline,
   information regime, risk outcome, metric and evaluation plan.

`fixture_context_digest` is the canonical digest of those four components plus
the resolver version. Repeats of the same experimental arm must begin with the
same composite digest. A counterfactual may change one or more component
digests only when those changes were declared before execution. The unchanged
component digests establish the common experimental world.

Capability choices, query parameters, returned evidence, interpretations,
decisions and simulated consequences do not rewrite the Fixture Context. They
form the unique, append-only `ExperimentRunTrace`.

## Object classes

An object receives exactly one primary class:

| Class | Meaning | Required contract property |
|---|---|---|
| Information | Immutable state available for interpretation | observation time, availability time, revision, truth class and digest |
| Processing | Invocable transformation or retrieval unit | typed input/output, method version, effects, cost and deterministic failure semantics |
| Policy | Constraint on eligibility, authority or behaviour | precedence, scope, effective interval, decision rule and conflict semantics |
| Presentation | View over evidence; never a new source of truth | source bindings, rendering version and no hidden calculations |
| Evaluation | Predeclared scientific meaning and scoring | estimand, unit, population, baseline, outcome window and metric definition |
| Runtime evidence | What one execution selected, produced or decided | run identity, sequence, provenance, receipt and parent digests |

## Canonical pre-run objects

### World and information objects

| Object | Exact responsibility | Must not own |
|---|---|---|
| `PortfolioVersion` | Positions, cash, identifiers, valuation currency and effective time | mandate rules or market state |
| `DataSnapshotManifest` | Dataset revisions, schemas, rights, temporal eligibility and content digests | interpretations or missing-data substitution |
| `MarketEnvironmentSnapshot` | Point-in-time observable market, macro, liquidity, event and data-quality state | portfolio-specific exposures or agent conclusions |
| `ScenarioDefinition` | Declared historical, synthetic or simulated transformation of an environment | undeclared empirical observations |
| `PortfolioEnvironmentView` | Deterministic application of the environment to one portfolio | agent reasoning or mutable decisions |
| `ContextGraphSnapshot` | Versioned typed relations among eligible entities, evidence and policies | facts absent from its bound source revisions |

`MarketEnvironmentSnapshot` is independent of a portfolio.
`PortfolioEnvironmentView` is the reproducible join that expresses how that
environment applies to a particular `PortfolioVersion`.

### Mandate and risk-governance objects

| Object | Exact responsibility | Must not own |
|---|---|---|
| `MandateVersion` | Investor objective, horizon, eligible universe, strategic constraints and authority | computed breach state or run-specific decisions |
| `RiskPolicySet` | Executable limits, thresholds, aggregation, escalation and exception rules | investor narrative or portfolio observations |
| `AutonomyPolicy` | Which actors may propose, resolve, defer or escalate each decision class | analytical facts |
| `SupraAgentPolicy` | Eligibility, evidence threshold, allowed resolution classes, abstention and budget for a non-human resolver | unrestricted human authority or external effects |
| `EffectPolicy` | Allowed simulated mutations and structurally prohibited external effects | decision rationale |

A mandate states what the portfolio is for. A risk policy states how compliance
and escalation are calculated. They are related by exact versioned references
but remain different objects so policies can be tested without rewriting the
mandate.

### Reachable processing and resource objects

| Object | Exact responsibility | Must not own |
|---|---|---|
| `CapabilityDefinition` | One typed calculation, retrieval or transformation | orchestration or unrestricted connector access |
| `CapabilityPack` | Closed set of capability versions offered to an agent | runtime selection history |
| `ConnectorDefinition` / `ProviderAdapter` | Typed access to a pinned source with rights, secrets and effect boundaries | business logic or silent fallback data |
| `DatasetAccessGrant` | Dataset/revision/query scope reachable through a capability | raw credentials or interpretation |
| `AgentBlueprint` | Role, instructions, evidence duties, budgets and output contract | hidden capabilities or mutable fixture state |
| `AgentGraphDefinition` | Nodes, routing, stopping, review and failure policies | undeclared runtime branches |
| `WorkflowDefinition` | Composition of agents, graphs and human/supra-agent checkpoints | reusable object mutation |
| `ModelRoutePolicy` | Allowed model/provider versions, parameters, fallback and cost policy | provider credentials or scientific result |

The `resource_envelope_digest` covers the complete reachable index and exact
versions, not merely the subset ultimately selected. This permits agent choice
while keeping repeats equivalent.

### Evaluation and presentation objects

| Object | Exact responsibility |
|---|---|
| `ResearchQuestionDefinition` | Population, unit of analysis, treatment concept and intended inference |
| `HypothesisDefinition` | Directional or non-directional falsifiable claim linked to the question |
| `BaselineDefinition` | Exact baseline-ladder position and comparator behaviour |
| `InformationRegimeDefinition` | Evidence categories made reachable and disclosure rules |
| `RiskOutcomeDefinition` | Good/bad outcome semantics, horizon, censoring and breach/mitigation rules |
| `MetricDefinition` | Formula, inputs, aggregation, direction, missingness and uncertainty treatment |
| `EvaluationSuite` | Cases, labels, sampling, repetitions, estimands and acceptance thresholds |
| `ReportTemplate` | Evidence-grounded narrative projection with required provenance slots |
| `DashboardPackage` | Interactive projection of retained evidence with no hidden metric authority |

The five thesis identities required by S4 — research question, baseline step,
information regime, risk outcome and metric — must be first-class immutable
references rather than strings recovered from run prose.

## Runtime-only objects

These objects are created after the Fixture Context is frozen and never become
part of its starting digest:

- `ExperimentRun` and ordered `ExperimentRunTrace`;
- `CapabilityInvocationReceipt` and connector/data-access receipt;
- `EvidenceItem`, `Finding`, `Interpretation` and uncertainty statement;
- `DecisionProposal`, human or supra-agent `DecisionResolution`, and abstention;
- `SimulatedEffectReceipt` and later `ObservedRiskOutcome`;
- report, dashboard, evaluation and comparison artifacts;
- cyclical `AcceptanceRecord` and next-revision requirement.

A runtime object can be promoted into a new reusable definition only through
its owning Studio, validation and a new Registry version. It never mutates the
definition used by the run that produced it.

## Object readiness assessment

Every canonical object receives one status supported by evidence:

- `absent` — no authoritative contract or lifecycle;
- `draft` — contract or UI exists but cannot yet enter a reproducible fixture;
- `threshold_ready` — sufficient for the first thesis pilot, with named limits;
- `definitive` — passes its full target behaviour and cross-object gates.

Each assessment records contract path, Registry support, fixture test, runtime
receipt, persistence, UI, thesis role, blockers, acceptance evidence and next
revision. Acceptance is cyclical: a later assessment supersedes rather than
overwrites the previous record.

## Development order before PLATFORM-P7

1. Freeze thesis-design identities: research question, baseline, information
   regime, risk outcome and metric.
2. Make `PortfolioVersion`, `MandateVersion` and `RiskPolicySet` independently
   versioned and cross-validatable.
3. Define `DataSnapshotManifest`, `MarketEnvironmentSnapshot`,
   `ScenarioDefinition` and deterministic `PortfolioEnvironmentView`.
4. Define the closed capability/data/connector resource envelope and its
   reachability graph.
5. Define agent, graph, workflow, model-route, autonomy and supra-agent policies.
6. Bind evaluation, report and dashboard definitions without giving views
   hidden calculation authority.
7. Run the readiness assessment and admit only `threshold_ready` versions into
   the first Fixture Context cycle.

## Exit gates

1. Every required experiment object has one authoritative definition, owner and
   primary class.
2. Information, processing, policy, presentation, evaluation and runtime
   evidence are not conflated.
3. Mandate and risk-policy responsibilities and precedence are explicit.
4. The reachable resource envelope is finite, versioned and digestible before
   agent execution.
5. Dynamic capability use creates receipts but cannot alter the starting
   envelope or obtain an undeclared source.
6. Human and supra-agent proposal, resolution, abstention and effect authority
   are separately versioned and testable.
7. The four component digests permit exact repeat checks and declared
   counterfactual differences.
8. All five thesis-design identities are first-class references.
9. Each object has an evidenced readiness status and next-revision record.
10. A minimal threshold-ready object set is approved before PLATFORM-P7 begins.

## Non-goals

- no Fixture Context implementation or resolver;
- no worker, scheduler, model call or large experiment batch;
- no arbitrary runtime discovery or installation of capabilities/connectors;
- no automatic supra-agent authority or external financial effect;
- no claim that a dashboard, report or interpretation is source evidence;
- no opening of a sealed historical out-of-sample evaluation panel.
