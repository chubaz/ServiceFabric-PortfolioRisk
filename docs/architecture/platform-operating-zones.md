# ServiceFabric operating zones and object movement

- Status: Phase 6 structural correction; maintained architecture boundary
- Profile: local development and experimental research only
- External effects: disabled

## 1. Decision

The unified application has two operating areas with different responsibilities:

1. **System Development** has a Build phase that authors, isolate-tests and saves reusable definitions, followed by an Apply phase that loads saved definitions into a labelled Fixture Context and shows how an agent uses them.
2. **Experimental Research** composes saved definition versions and immutable source bindings into reproducible experiments and comparisons.

The zones share canonical contracts and storage services. They do not share authority implicitly.

```text
SYSTEM DEVELOPMENT
BUILD                                            APPLY
draft -> isolated object test                    fixture + saved definitions
  -> Registry candidate -> saved version ----------> isolated agent/object work
                                                     -> temporary run work products
                         |                                      |
                         +---------- saved versions ------------+-----> EXPERIMENTAL RESEARCH
                                                                 immutable bindings + saved definitions
                                                                   -> run / pause / compare
                                                                   -> experiment work products
                         +------------- explicit retention review -------------+
                                        |
                                        v
                              ARTIFACT REPOSITORY
                       retained, provenance-bound work products
```

## 2. Terms

| Term | Exact meaning |
|---|---|
| Reusable definition | A system-level object with stable identity, version, source pointer and lifecycle. |
| Saved definition | A definition explicitly indexed in the Registry. Source discovery alone is not saving. |
| Fixture Context | A labelled, point-in-time input environment used to exercise an object or agent. |
| Application scenario | A System Development Apply-phase test containing a saved agent, selected saved definitions and one Fixture Context. |
| Companion capability | A typed operation needed to create, validate, lifecycle, modify or apply a reusable definition. |
| Experiment | A reproducible composition of immutable source bindings, saved definitions, execution policy and evaluation intent. |
| Run work product | Any output created by one application or experiment execution. It is temporary by default. |
| Artifact | A run work product deliberately retained in content-addressed storage with provenance, truth and lifecycle policy. |
| Promotion | A separate reviewed process that turns an approved proposal or declarative work product into a new reusable definition version. |

An Artifact is therefore important, but it is not a synonym for every system object. Reports, dashboards and scenarios may exist both as reusable **definitions** and as rendered run **artifacts**. The identity tells which role the object is playing.

## 3. System Development

### 3.1 Responsibility

System Development owns singular object construction and its controlled application test:

- AgentBlueprint and agent role;
- CapabilityDefinition;
- ReportTemplate;
- DashboardPackage;
- ScenarioDefinition;
- future WorkflowDefinition;
- future ProviderAdapter;
- future PortfolioVersion and MandateVersion.

Each Studio treats the reusable definition and its necessary companion capabilities as one development concern. A Dashboard Studio may therefore build both a `DashboardPackage` and the typed capabilities that validate, render or update it. This does not fuse their identities: each remains separately versioned, reviewable and least-privileged. Agent and Capability Studios add companion capabilities only for lifecycle or native framework gaps.

The current Registry remains an index over canonical sources rather than their replacement. Git remains authoritative for reviewed code and declarative definitions. Registry metadata adds discovery, immutable identity, lifecycle, compatibility, provenance and relationships. Evaluation authoring is deliberately deferred until the thesis evaluation methodology is agreed.

### 3.2 Save gate

A draft may be tested locally without being reusable. It becomes loadable only after explicit Registry indexing creates a candidate lifecycle receipt. Validation and local publication add review strength; they do not deploy the object or grant financial effects.

Candidate, validated and locally published definitions may enter development experiments. Deprecated, retired, archived and merely discovered definitions may not enter new experiments. Existing experiment records retain their exact historical identities.

## 4. System Development: Apply

The Apply phase is not another authoring form. It is an object-behaviour workbench reached from every Studio after a version has been saved.

An Application Scenario declares:

- one saved agent definition;
- a real, reviewed-synthetic or real-anchored-simulated Fixture Context;
- one reviewed portfolio source;
- zero or more saved capability, report, dashboard and scenario definitions;
- an effect-free authority boundary;
- the expected work record and output review.

The agent receives the fixture boundary and may exercise only the definitions admitted to the scenario. The interface exposes frozen inputs, capability calls, concise rationale, validation/review events, files and outputs. It does not expose private chain-of-thought.

The current Phase 6 correction reuses the existing Agent Run Review and Workflow Cycle. PLATFORM-P8 must bind every selected definition into one end-to-end executable vertical slice. Until then, selections not consumed by the existing runner are shown as declared test intent, never as executed work.

## 5. Experimental Research

Experimental Research is the thesis apparatus. It owns:

- immutable ExperimentDefinitions;
- interactive foreground, background/headless and evaluation-only presentation;
- explicit queue admission and restart-safe lifecycle;
- saved ExperimentSets for comparisons;
- run and evaluation lineage;
- retained experiment artifacts.

Only saved Registry identities may be selected for new experiments. Source discovery is insufficient. This is enforced by the API, not only the interface.

The thesis comparison unit is an ExperimentSet whose controlled and variable factors can include agent framework, agent/graph/workflow version, Context Pack, Capability Pack, mandate, decision policy, model route, fixture/data revision and seed. Each experiment remains independently reproducible.

## 6. Existing backend reuse

| Need | Reused infrastructure |
|---|---|
| Reusable definitions | `risk_registry.LocalRegistryStore` and existing source adapters |
| Agent design and isolated work | Agent Studio blueprint compiler and Agent Run Review |
| Fixture data | read-only DuckDB data plane, synthetic behavior samples and Workflow Cycle simulation |
| Experiments and sets | `risk_experiments` contracts and `LocalExperimentStore` |
| Run files | temporary per-run Agent Studio folders |
| Retained work products | `risk_artifacts.LocalArtifactStore` |
| Decisions and investigation | `risk_decisions` and the external Decision Repository |
| Report outputs | `risk_reports` Markdown-first contracts and rendering |

The `GET /api/platform/workspaces` endpoint is a projection across these services. It introduces no new authoritative persistence object.

## 7. Phase dependency reminders

| Phase | Required follow-through from this boundary |
|---|---|
| PLATFORM-P7 | Create portable Fixture Context contracts; separate portfolio, environment and portfolio-applied environment layers; preserve point-in-time eligibility and context revisions. |
| PLATFORM-P8 | Execute one saved agent with selected saved capabilities and presentation definitions in the System Development Apply phase; retain complete work receipts and compare output revisions. |
| PLATFORM-P9 | Make PortfolioVersion and MandateVersion first-class registered definitions; build Mandate Lab and mandate knowledge-graph mappings. |
| PLATFORM-P11 | Route agent-authored change proposals to System Development without permitting runtime code mutation or self-promotion. |
| PLATFORM-P12 | Implement the development-only Studio-Codex gateway, worktree lifecycle and candidate definition registration. |
| PLATFORM-P14 | Register executable agent graphs and workflows; add human-fractioned, supra-agent and parallel-headless experimental policies. |
| PLATFORM-P15 | Register ProviderAdapters for MCPs, APIs and other integrations with rights, secrets and effect boundaries. |
| Experimental apparatus phase | Add branch-from-version, factor matrices, bounded workers for hundreds of runs, framework-comparison metrics and thesis result exports. |

Placeholders in the interface must name the phase that unlocks them. A placeholder must not claim execution, persistence or authority that the current backend does not provide.

## 8. Invariants

1. A discovered source is not a saved definition.
2. A run work product is not a reusable definition.
3. Artifact retention is explicit and does not promote an object.
4. New experiments reference only saved, versioned Registry identities.
5. Fixtures always disclose real, synthetic, simulated or mixed truth.
6. Application testing cannot mutate the canonical definition under test.
7. Experimental overlays remain local and digest-bound.
8. Build, Apply and Experimental Research authority is visible in the interface and in API validation.
9. External financial effects remain disabled.
10. Future controls remain honest placeholders until their contracts and tests exist.
