# Detection Quality evaluation plan

- Status: selective labelling and retrospective path/interval/severity study implemented; event/fundamental enrichment and Gold adjudication remain gated
- Evaluation priority: 1
- Scope: multi-day portfolio-risk architecture experiments
- Last reviewed: 12 August 2026

## Evaluation question

> Does the architecture identify independently labelled, portfolio-relevant
> risk developments that it should detect, without producing excessive false
> alerts, duplicates or unsupported episode hypotheses?

The present deterministic mandate-finding comparison does not answer this
question. It tests whether an architecture preserves calculated mandate
findings already supplied in its context. That result belongs to apparatus
integrity and must not be presented as independent Detection Quality.

## Detection output

A detection is a structured episode hypothesis linking:

- eligible evidence or an observed portfolio-state change;
- an affected instrument, exposure or portfolio scope;
- a risk channel;
- a detection time;
- an ex-ante materiality judgement;
- evidence references and uncertainty.

A deterministic mandate breach is an observation, not an agent discovery. It
may enter the architecture context or be evaluated as rule recognition, but it
must remain separate from independent episode detection.

## Two reference-episode families

### Instrument Risk Episode

An Instrument Risk Episode affects an issuer or instrument independently of
whether a particular portfolio currently holds it. Examples include earnings
deterioration, guidance reduction, refinancing difficulty, regulatory action,
litigation, product failure, management disruption, abnormal price behaviour
and liquidity deterioration.

Instrument episodes can be labelled once and projected onto any point-in-time
portfolio holding the instrument.

### Portfolio Risk Episode

A Portfolio Risk Episode arises from the interaction of holdings, exposures,
market conditions, scenarios and mandate constraints. Examples include
concentration, correlation convergence, simultaneous liquidity deterioration,
factor accumulation, combined immaterial issuer developments becoming
portfolio-material, and macro shocks transmitted through the current
portfolio composition.

Portfolio episodes cannot be labelled from a news feed alone. They require a
point-in-time portfolio state and may require subsequent outcomes.

Detection Quality must report these separately:

```text
Instrument episode detection
        +
Portfolio episode detection
        +
Instrument-to-portfolio relevance
        =
Detection Quality evidence
```

They must not be pooled into one unexplained F1 score.

## Risk Episode definition

A Risk Episode is a bounded period during which evidence supports the
existence of a particular risk mechanism affecting an instrument or portfolio,
with a defined onset, scope, risk channel, evidential basis and outcome state.

Each admitted episode distinguishes:

- **cause** — the development initiating or intensifying risk;
- **clues** — information available to the tested architecture;
- **risk mechanism** — how the development could transmit into loss or
  instability;
- **affected scope** — instrument, factor, portfolio segment or portfolio;
- **ex-ante materiality** — importance using only eligible information;
- **ex-post materiality** — the subsequently observed consequence;
- **outcome horizon** — when the consequence is evaluated;
- **resolution** — materialised, latent, reversed, expired or unresolved.

A credible risk may exist without subsequently producing a loss. The label
must preserve both ex-ante risk and realised consequence instead of defining
all non-materialised risks as false.

## Existing dataset signals

### RavenPack

The current licensed integration supplies:

- instrument and entity identifiers;
- event and availability timestamps;
- taxonomy topic, group, type, subtype, property, category and description;
- provider relevance, sentiment and novelty;
- story and similarity identifiers;
- source and news type;
- date-effective PERMNO and GVKEY linkage.

The local scope contains approximately 3.55 million records, 104,554
taxonomy-classified event records, 16 linked provider entities and 2,064
category definitions.

These are features and provisional weak labels, not ground truth:

- provider relevance concerns the named entity, not portfolio materiality;
- sentiment is not severity;
- novelty is not materiality;
- category describes an event, not its risk consequence;
- similarity supports clustering but does not prove economic episode identity.

### CRSP

CRSP can support ex-post outcome construction through returns, prices, volume,
trade counts, bid/ask observations, intraday range, shares outstanding and
delisting records. Potential derived outcomes include abnormal return,
drawdown, volatility escalation, liquidity deterioration, unusual volume and
terminal loss. Horizons, benchmarks and thresholds must be fixed before the
test period.

### Compustat

Compustat can provide later fundamental confirmation through earnings,
revenues, operating performance, leverage, liquidity, working capital,
impairments and financing changes. Point-in-time logic must use the information
publication date, not the accounting period end.

### Curated Day 3 and Day 4 events

The repository contains 20 reviewed public events with event and availability
times, entity, sentiment and relevance, including deliberately irrelevant
examples. They are suitable for fixtures and interface tests, but not as thesis
ground truth: they cover late 2024, do not overlap the licensed 2013–2017
RavenPack period, and their relevance was curated rather than independently
validated against outcomes.

### Mandate breaches

Mandate breaches provide valid labels for mandate-rule recognition only. They
must not be reused as general event or portfolio-risk detection labels.

## Risk Episode Labelling System

Status: **selective signal labelling and deterministic study support implemented through Session 4**.

The current implementation deliberately covers the first governed layer only:

```text
versioned detector runs
    -> same-scope/date/direction review units
    -> stratified bounded sample
    -> immutable annotation revisions
    -> independent review
    -> reference-ready gate
```

It does not create Gold cases, experimental Cases, causal narratives or an
oracle over the full market. Duplicate detector hits are reviewed once while
retaining method support. Sampling rotates across direction, score strength
and single- versus multi-detector support so the labelling burden is
concentrated on an informative subset rather than every signal.

For one selected review unit at a time, the label study now reconstructs a
bounded real CRSP path and proposes four alternative temporal readings:
punctual, drawdown, slow deterioration and regime transition. It also records
a deterministic mean/variance change-point check, maximum adverse excursion
within 1/5/20-session horizons, portfolio breadth, pre/post average
correlation, missingness, and only explicitly allowed non-causal association
edges. These results are retained as proposal revisions. They do not approve,
overwrite or silently revise an annotation. A reviewer may copy one proposal
into the unsaved form, edit it, or ignore it.

Each annotation records outcome, relevance, scope, direction, temporal
morphology, manifestation interval, severity, evidence, data quality and label
confidence. Those fields are explicitly mapped to detection, severity,
timeliness, evidence and calibration evaluation. Robustness, stability,
efficiency and decision quality continue to come from run behaviour, telemetry
and separate decision references rather than being invented by the label.

An annotation becomes **reference-ready** only after a different reviewer has
checked detection/scope, severity, evidence and temporal fields. This state
means eligible for a later Gold-preparation workflow. It does not create or
admit Gold truth.

This is one governed labelling system with two coordinated components. It must
remain independent of every tested architecture.

### Instrument Episode Oracle

Inputs:

- RavenPack event and news metadata;
- issuer mappings;
- CRSP market behaviour;
- Compustat fundamentals;
- category definitions;
- optionally admitted external evidence.

Outputs:

- instrument-level episode clusters;
- risk channels;
- ex-ante materiality;
- ex-post outcome;
- ambiguity and label confidence;
- full provenance and review state.

A model may propose labels but cannot automatically establish ground truth.
Admission requires deterministic outcome validation, human review or both.

### Portfolio Episode Oracle

Inputs:

- point-in-time holdings and exposures;
- portfolio metrics and mandate;
- instrument episodes;
- market, factor and scenario data;
- subsequent instrument and portfolio outcomes.

Outputs:

- portfolio-specific episodes;
- affected holdings and exposures;
- causal or contributory mechanisms;
- ex-ante and ex-post materiality;
- outcome horizon and unresolved uncertainty.

The Oracle may inspect subsequent outcomes when creating ex-post labels. Those
outcomes must never be admitted into the tested architecture's context.

## Future system placeholder B — Case Challenge-Set Generator

Status: **planned; not implemented**.

Synthetic enrichment must be a versioned, Case-specific overlay. It must never
mutate or masquerade as the licensed source dataset.

The generator first audits the real Case, then adds only missing challenge
classes:

- relevant and material episodes;
- relevant but immaterial episodes;
- irrelevant records;
- ambiguous or conflicting evidence;
- duplicates;
- delayed information;
- missing data;
- quiet periods without material episodes.

Every generated record declares:

- `synthetic = true`;
- method, seed and generator version;
- intended challenge class and expected label;
- availability time and affected or deliberately unrelated instruments;
- difficulty level and provenance;
- confirmation that future real information was not used.

Real and synthetic performance is reported separately. A combined figure may
only be a secondary, explicitly weighted summary.

## Unsupervised discovery beyond the event feed

Unsupervised methods are needed to propose endogenous portfolio episodes that
do not originate in RavenPack. Candidate approaches include:

- return, volatility, volume and liquidity change-point detection;
- abnormal residual returns after market and sector controls;
- correlation, covariance and factor-exposure regime shifts;
- clustering breakdowns;
- Bayesian online change-point detection;
- hidden Markov and regime-switching models;
- isolation forests and autoencoder reconstruction errors;
- graph anomalies across issuers and exposures;
- extreme-value and multivariate portfolio-state anomaly detection.

An anomaly is a candidate episode, not a reference label:

```text
Market and portfolio state
        -> unsupervised anomaly
        -> candidate endogenous episode
        -> outcome analysis and independent review
        -> admitted RiskEpisodeLabel
```

Unsupervised detection alone cannot determine cause, economic materiality,
risk direction or the appropriate action.

## Required data contracts

### RiskEpisodeLabel

```text
episode_id
episode_scope                 instrument | portfolio
instrument_ids
portfolio_id                  nullable for instrument episodes
episode_start
first_evidence_available_at
confirmation_time
episode_end
risk_channels
cause_type
reference_materiality         material | immaterial | ambiguous
ex_ante_probability
ex_ante_impact
ex_post_state                 materialised | latent | reversed | expired | unresolved
outcome_horizon
outcome_measures
evidence_ids
label_method                  human | deterministic | supervised | weakly_supervised
label_created_at
labeler_version
review_state
label_confidence
synthetic
```

### ArchitectureDetection

```text
detection_id
run_id
cycle_id
detected_at
episode_hypothesis
predicted_scope
predicted_instrument_ids
predicted_portfolio_id
predicted_risk_channels
predicted_materiality
confidence
evidence_ids
abstained
abstention_reason
```

### EpisodeMatch

```text
reference_episode_id
detection_id
match_state                   matched | false_positive | false_negative | duplicate
entity_match
temporal_overlap
risk_channel_match
scope_match
match_method
match_score
review_state
```

### CaseObservationCalendar

```text
case_id
portfolio_id
observation_date
eligible_episode_ids
material_episode_ids
ambiguous_episode_ids
quiet_period
eligible_data_digest
synthetic_overlay_digest
```

## Metrics and required data

### Primary metrics

| Metric | Required data |
|---|---|
| Precision | All `ArchitectureDetection` and corresponding `EpisodeMatch` records |
| Recall | All material `RiskEpisodeLabel` and corresponding matches |
| F1 | Precision and recall for the same declared episode population |
| High-materiality recall | Reference materiality and matched detections |
| False alerts per portfolio-day | Unmatched detections and eligible portfolio-days |

Primary metrics are always separated by:

- real instrument episodes;
- synthetic instrument episodes;
- real portfolio episodes;
- synthetic portfolio episodes.

### Diagnostic metrics

| Metric | Required data |
|---|---|
| Duplicate-detection rate | Multiple detections matched to one episode |
| Instrument-mapping accuracy | Predicted and reference instrument identifiers |
| Portfolio-scope accuracy | Predicted and reference portfolio scope |
| Risk-channel accuracy | Predicted and reference risk channels |
| Ambiguous-case abstention rate | Ambiguous labels and architecture abstentions |
| Incorrect abstention rate | Material episodes on which the architecture abstained |
| Quiet-period false-alert rate | Observation calendar and unmatched detections |
| Episode-fragmentation rate | Detections created for one continuing episode |
| Episode-merging error | One detection matched to unrelated episodes |

Risk-channel accuracy remains a Detection Quality diagnostic, while the
quality of the causal and portfolio interpretation is evaluated under Severity
and Risk Understanding.

## Multi-day evaluation

Detection Quality is calculated over the full experimental period:

1. admit only information available in the current workflow cycle;
2. create or update eligible reference episodes;
3. execute the architecture;
4. retain its episode hypotheses;
5. match hypotheses with independent reference episodes;
6. carry unresolved episodes into later cycles;
7. prevent repeated discussion from becoming repeated detections;
8. compute final metrics over the complete period.

The evaluation must include positive, negative, ambiguous and quiet cycles.
One positive day is insufficient.

## Current-system assessment

The current `Detection F1` compares architecture findings with deterministic
mandate findings derived from the same input. B0 constructs the reference,
while B1 and A1 are given those calculations. The score therefore measures
**Mandate-finding reproduction**, not independent Detection Quality.

Until the two planned systems and their admitted labels exist:

- independent Detection Quality is `not_measurable`;
- mandate-finding reproduction remains an apparatus-integrity check;
- structural citation presence remains an integrity check;
- no 100% integrity value may be described as architecture-quality evidence.

## Decisions still required before implementation

1. Define reference materiality levels and outcome horizons.
2. Define matching tolerances for time, entity, scope and risk channel.
3. Choose the human-review and adjudication process for Oracle proposals.
4. Choose which outcome constructions can establish ex-post materiality.
5. Define challenge-set difficulty and the required balance of negative,
   ambiguous and quiet cycles.
6. Define train, validation and out-of-sample separation for the labelling
   models and tested architectures.
