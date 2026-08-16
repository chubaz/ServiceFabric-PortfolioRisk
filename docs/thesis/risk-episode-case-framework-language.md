# Risk-Episode Case Framework Language and Ownership

This is the Session 1 language boundary for the historical case framework. It keeps the research interface simple while assigning every technical record to one existing package.

## The four user actions

The Experiment page has one research journey:

```text
Find cases -> Review case -> Run comparison -> Compare results
```

No other object is required as a primary navigation concept. Technical identities, schemas, hashes, receipts, and lifecycle records are not rendered in the research interface. They remain in persisted machine-readable outputs and Codex handoffs for software inspection.

## Shared language

| Term | Plain meaning | Not the same as | Owning package or existing object |
|---|---|---|---|
| Signal | A versioned statistical observation that something unusual occurred in one series or group. | Finding, alert, case, or cause. | `risk_analytics`; typed research payload stored through the artifact repository. |
| Review unit | Signals sharing the same scope, date, and direction, presented once so duplicate detector hits do not create duplicate labelling work. | Candidate, episode, or accepted label. | `risk_experiments.SignalReviewUnit`; retained inside a labelling batch. |
| Labelling batch | A reproducible, bounded sample of review units selected across direction, score strength, and detector support. | Case corpus or experiment. | `risk_experiments.LabellingBatch`; restart-safe local label-production store. |
| Study proposal | A reproducible retrospective calculation that helps a reviewer interpret one selected move: price path, alternative intervals, severity horizons, breadth, correlation, limitations and explicit associations. | Label, truth, finding, causal claim, or Gold case. | `risk_analytics.LabelStudyProposal`, retained as an immutable proposal revision inside the labelling batch. |
| Reference-ready | An annotation revision independently checked for detection/scope, severity, evidence, and timing. | Gold acceptance or an experimental Case. | Computed `GoldPreparationReadiness`; it always records that no Gold case was created. |
| Candidate | One or more related signals worth reviewing together. | Accepted risk episode, alert, or causal conclusion. | `risk_experiments`; working case-lab artifact. |
| Silver label | A reproducible programmatic description of a manifestation, including scope, direction, morphology, interval, severity measures, and detector support. | Expert truth or Gold acceptance. | `risk_experiments`; label payload referenced by `ExperimentalCase`. |
| Gold case | A governed retrospective case bundle whose evidence, alternatives, checkpoints, and limitations have been accepted by an independent human reviewer. | An architecture input or universal causal truth. | Existing `ExperimentalCase`, evidence references, review state, and `ArtifactManifest` composed by `risk_experiments`. |
| Case | The frozen portfolio, mandate, time boundary, eligible information policy, and case-label reference shared by matched Runs. | A Run, a market regime, or a mutable dashboard. | Existing `risk_experiments.ExperimentalCase`. |
| Run | One architecture executing once against one frozen Case and configuration. | An Experiment or a software test. | Existing `risk_experiments.ExperimentalRun` and replay records. |
| Architecture output | The structured, effect-free result retained from one workflow cycle or Run. | A report, private reasoning, or raw agent text. | Existing `risk_experiments.ArchitectureOutput`, mapped from `risk_agents.AgentStructuredOutput`. |
| Evaluation | A versioned comparison between retained architecture output/behavior and an independent Case reference. | The architecture's self-assessment. | Existing `risk_experiments.EvaluationRecord`. |
| Experiment | A bounded matrix of matched Runs answering one research question. | A single Run or an application fixture. | Existing `ExperimentDefinition`, `ExperimentSet`, and scientific-design objects. |
| Evidence | A temporally qualified source reference supporting or contradicting a structured claim. | A narrative assertion or provider row copied into Git. | Existing evidence contracts, capability receipts, and artifact manifests. |
| Reference label | Information used only by evaluation after output is fixed. | Architecture context. | Case-label bundle with a mandatory label firewall. |
| Development fixture | Controlled data used to test software behavior. | Historical research evidence. | Existing fixture context and synthetic fixture stores. |

## Data language

The interface must always distinguish these states:

| Label | Meaning |
|---|---|
| Licensed · read only | Local CRSP, Compustat, or RavenPack records. Source bytes remain outside Git and cannot be written by the experiment. |
| Point-in-time · ex ante | Only information with `available_at <= replay_time` is available to the architecture. |
| Retrospective reference | Hindsight information available only to Case Design and evaluation. It is never sent to the evaluated architecture. |
| Reviewed synthetic | A governed fixture with a declared generation method and accepted scope. |
| Development-only sample | A code-generated software-test sample that cannot appear as a research result. |
| Synthetic augmentation | A deliberately generated negative, ambiguous, immaterial, or missing-information observation attached to one Case Design and visibly identified. |
| Not evaluable | Required independent labels or outcomes are absent. It never means zero risk, zero error, or a perfect score. |

## Architecture language

The existing product identifiers remain authoritative:

| ID | Meaning |
|---|---|
| B0 | Deterministic reference treatment using only admitted deterministic/statistical capabilities. |
| B1 | One final decision agent using the common experimental wrapper. |
| A1 | A graph of specialist agents and a final synthesizer using the common graph wrapper. |

Architecture and capability package are separate experimental factors. More agents or capabilities do not imply a stronger method.

## Canonical ownership decision

No new general finding, alert, evidence, decision, run, evaluation, provider, or registry hierarchy will be introduced.

| Proposed payload | Initial owner | Storage/transport | Promotion rule |
|---|---|---|---|
| `DetectorDefinition` | `risk_analytics` | Typed immutable payload | Promote only if used outside the case framework. |
| `DetectorRun` | `risk_analytics` | Artifact manifest plus receipts | Remains research analytics unless reused broadly. |
| `AnomalySignal` | `risk_analytics` | Sparse columnar result plus typed preview | Must never become a general `Finding` automatically. |
| `SignalReviewUnit`, `SignalSelectionPlan`, `LabellingBatch` | `risk_experiments` | Immutable label-production records | Reduce and review detector output; never create Gold automatically. |
| `LabelStudyProposal` | `risk_analytics`, retained by `risk_experiments` | Immutable proposal revision with retrospective-only path and method outputs | May prefill an unsaved label form but can never approve or revise a label. |
| `RiskEpisodeCandidate` | `risk_experiments` | Case-lab artifact | Never becomes an alert automatically. |
| `SilverCaseLabel` | `risk_experiments` | Versioned label artifact | Referenced by `ExperimentalCase`; immutable after publication. |
| `GoldCaseBundle` | `risk_experiments` | Composition of existing evidence, review, checkpoint, and artifact records | Gold acceptance requires independent human review. |
| `CaseLabelBundleReference` | `risk_experiments` | Field/reference on the existing Case composition | No separate registry category in P0. |
| `FrozenForecastModelManifest` | `risk_analytics` | Versioned experiment artifact | General model lifecycle is deferred. |

## Evaluation boundary

The existing nine dimensions remain unchanged:

1. confidence and calibration;
2. decision quality;
3. detection quality;
4. efficiency;
5. evidence quality;
6. robustness;
7. severity understanding;
8. stability;
9. timeliness.

Coverage and abstention remain diagnostics. Reports and user-facing prose are renderings of structured outputs and are never used as hidden evaluation inputs.

## Non-negotiable separations

- A statistical anomaly is not automatically a risk episode.
- A candidate is not automatically Silver or Gold.
- A Gold case is not available to the architecture under evaluation.
- A market regime classifies a Case; it is not silently supplied as architecture context.
- A user-facing report is not the `ArchitectureOutput`.
- A deterministic mandate breach reference is not an event-relevance oracle.
- A development fixture is not a research result.
- RavenPack event metadata is evidence, not ground truth for market materiality or causality.
