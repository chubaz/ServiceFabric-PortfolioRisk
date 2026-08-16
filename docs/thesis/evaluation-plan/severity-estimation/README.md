# Severity Estimation evaluation plan

- Status: consultation complete; implementation not authorised
- Evaluation priority: 2
- Scope: multi-day portfolio-risk architecture experiments
- Last reviewed: 12 August 2026

## Evaluation question

> Once an architecture has identified a risk episode, how accurately does it
> estimate the episode's adverse portfolio impact using only information
> eligible at the prediction time?

This dimension is deliberately narrower than the earlier label **Severity and
Risk Understanding**. The primary quantitative subject is Severity Estimation.
Causal and portfolio reasoning remain inspectable structured by-products, but
they are not assigned a ground-truth score until a credible and affordable
independent labelling method exists.

Detection Quality and Severity Estimation answer different questions:

```text
Detection Quality    = did the architecture identify the correct episode?
Severity Estimation  = how large was the predicted adverse portfolio effect?
```

## Primary severity target

The primary target is:

> Expected adverse portfolio impact, expressed in portfolio basis points over
> five trading sessions.

One- and twenty-session outcomes are retained as diagnostics. They do not
become additional evaluation dimensions.

The preferred forecast decomposes severity into:

```text
probability that the episode becomes material
        x
conditional adverse impact if it materialises
        =
expected adverse portfolio impact
```

A two-stage statistical implementation can therefore use:

1. a classification model for materialisation probability; and
2. a regression model for conditional adverse impact.

Logistic regression is appropriate for a binary probability, and ordinal
logistic regression is appropriate only if severity is intentionally reduced
to ordered bands. A regularised linear, robust, quantile or gradient-boosting
regression can estimate continuous impact. Model selection belongs to a later,
versioned capability qualification step.

## Labels and the statistical model

The Severity Model is not the label oracle. Using the model to create the
reference label and then scoring architectures against that prediction would
be circular.

```text
subsequent historical outcomes
        -> deterministic label construction
        -> realised portfolio impact in basis points
        -> train the Severity Model on an earlier period
        -> test architecture forecasts out of sample
```

Post-episode observations may be used to construct the hidden evaluation label.
They must never enter the point-in-time context supplied to the architecture.

## Label populations

### Event-conditioned episodes

For an eligible news or corporate episode, the labelling pipeline must:

- use the first eligible `available_at` as the episode start;
- resolve the affected instrument and point-in-time portfolio exposure;
- calculate benchmark- or factor-adjusted instrument returns;
- calculate portfolio contribution over one, five and twenty sessions;
- retain maximum adverse excursion and recovery time;
- cluster overlapping evidence so one episode is not counted repeatedly.

### Dense portfolio timeline

The evaluation cannot rely only on spoon-fed news. Every eligible portfolio-day
must be capable of becoming an evaluation observation using point-in-time:

- market state, volatility and liquidity;
- concentration and factor exposure;
- available fundamentals;
- scenarios and mandate indicators;
- events known by that time.

Subsequent portfolio outcomes determine whether an endogenous portfolio episode
materialised. This population covers risks emerging from market and portfolio
calculations even when no news record announces them.

## Required architecture output

For every detected episode that receives a severity judgement,
`ArchitectureOutput` must retain a forecast equivalent to:

```yaml
episode_id: string
severity_forecast:
  horizon_sessions: 5
  materialisation_probability: decimal
  conditional_adverse_impact_bps: decimal
  expected_adverse_impact_bps: decimal
  lower_bound_bps: decimal | null
  upper_bound_bps: decimal | null
  baseline_prediction_bps: decimal | null
  architecture_adjustment_bps: decimal | null
  source: rules | severity_model | architecture_adjustment
  confidence: decimal
  abstained: boolean
  evidence_ids: [string]
```

The hidden evaluation state must retain an outcome equivalent to:

```yaml
episode_id: string
realised_adverse_impact_bps: decimal
instrument_abnormal_return: decimal | null
portfolio_contribution_bps: decimal | null
maximum_adverse_excursion_bps: decimal | null
recovery_sessions: integer | null
label_horizon_sessions: 5
benchmark_id: string
label_status: resolved | censored | unresolved
```

`ArchitectureOutput` contains the architecture's ex-ante prediction. Realised
outcomes remain inaccessible evaluation state and are joined only after the
declared horizon has matured.

## Deterministic and statistical treatments

The current deterministic reference assigns severity 2 to a review-level rule
and severity 3 to an urgent rule, then takes the maximum finding severity. This
is **policy urgency**, not empirical economic severity. The two concepts must be
stored and evaluated separately:

```text
Policy urgency      = how quickly governance should respond
Economic severity   = expected adverse portfolio impact
```

A frozen Severity Model may be exposed as a common capability to all
architectures. Its inference is operationally repeatable, but its estimate is
statistical rather than a deterministic rule label.

The recommended experimental design is:

- the deterministic reference adopts the frozen model estimate without an LLM
  interpretation;
- the single-agent and graph treatments may accept, adjust or abstain from the
  estimate;
- the raw baseline, adjustment and final estimate are all retained;
- the evaluator measures whether each architecture improves, preserves or
  damages the shared statistical baseline out of sample.

If a pure rule-only treatment is required, it must report policy urgency and a
separately named rule-derived impact proxy. It must not present urgency tiers as
historically validated economic severity.

## Multidimensional inputs, scalar target

Multidimensional information should principally be used as model features,
rather than expanded into many weakly justified evaluation scores. Candidate
features include:

- event relevance, taxonomy, novelty and sentiment;
- pre-event volatility and liquidity;
- issuer fundamentals;
- portfolio weight, concentration and factor sensitivity;
- mandate thresholds and risk budget;
- scenario exposure;
- recent related episodes;
- prevailing market regime.

These dimensions help predict one economically interpretable target in
portfolio basis points. Risk channels and causal explanations remain available
for research inspection but are not part of the primary score.

## Evaluation measures

### Primary

**Mean absolute error in portfolio basis points** measures the average distance
between expected and realised adverse impact.

### Secondary

- **Severity rank correlation** measures whether episodes are ordered correctly
  from least to most severe.
- **Material-episode recall** measures whether episodes exceeding a predeclared
  portfolio-impact threshold were recognised as severe.

### Diagnostics

- systematic overestimation or underestimation;
- prediction-interval coverage;
- error by episode family, risk channel and severity band;
- incremental error relative to the frozen Severity Model;
- value added or destroyed by architecture adjustments;
- performance at one- and twenty-session horizons.

Exact severity match is not meaningful for a continuous target and must not be
used as the principal measure.

## Causal and portfolio reasoning boundary

Correct causal explanation is valuable but cannot yet be labelled reliably at
the scale required by the thesis. It must therefore remain:

- structured and inspectable in the architecture output;
- supported by evidence and explicit uncertainty;
- available for a small, blinded human audit if resources permit;
- excluded from the primary quantitative Severity Estimation score.

An LLM judge must not be called for every episode. A later exploratory appendix
may review a small stratified sample of material, immaterial and ambiguous
episodes, but it must be reported separately from outcome-based severity.

## Point-in-time and out-of-sample rules

- Use `available_at`, not the economic event date, as the information boundary.
- Use the next eligible market close when the event arrives after the applicable
  close.
- Construct labels with fixed one-, five- and twenty-session horizons, with five
  sessions primary.
- Split training, validation and test periods chronologically.
- Where feasible, group issuers across splits to reduce issuer memorisation.
- Use subsequent outcomes only for hidden labels.
- Keep synthetic challenge cases separate from real out-of-sample results.
- Retain benchmark, factor model, portfolio snapshot and label-pipeline versions.

## Advantages

- Feasible with point-in-time CRSP, Compustat, RavenPack and portfolio holdings.
- Scales without an LLM judge for every episode.
- Produces an interpretable result in portfolio basis points.
- Supports event-conditioned and endogenous portfolio episodes.
- Gives all architectures the same hidden evaluation target.
- Measures whether agent reasoning adds value beyond a statistical baseline.

## Limitations

- Market outcomes are noisy and do not establish causality.
- The evaluation horizon may contain unrelated information.
- Severe episodes are rare and require adequate historical coverage.
- Benchmark and factor-model choices affect labels.
- Portfolio labels depend on accurate point-in-time holdings.
- A reasonable ex-ante warning may not subsequently materialise.
- Overlapping episodes require governed clustering.
- Expected-impact estimation requires enough independent observations for
  calibration and out-of-sample testing.

## Implementation placeholders

Status: **planned; not implemented**.

Future work must add:

1. a versioned outcome-label construction capability;
2. an event and endogenous-episode clustering policy;
3. a qualified two-stage Severity Model capability;
4. the minimal `ArchitectureOutput` severity-forecast extension;
5. hidden outcome contracts and horizon-maturity handling;
6. out-of-sample split and leakage checks;
7. severity evaluation calculations and baseline-increment diagnostics.

Until those components exist and independently constructed outcomes have
matured, Severity Estimation must be reported as `not_measurable` rather than
filled with rule-urgency proxies.
