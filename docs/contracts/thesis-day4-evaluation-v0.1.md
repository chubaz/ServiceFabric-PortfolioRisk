# Thesis Day 4 evaluation v0.1

## Scope

This contract governs the preliminary historical evaluation of the accepted
Day 3 B0, B1, and A1 treatments. It reuses the accepted Day 2 deterministic
metrics and decision kernel and the accepted Day 3 architecture runner. It
does not define a new architecture, provider abstraction, calculation path,
effect, application, or trading authority.

The implementation uses strict immutable contracts with extra fields
forbidden:

- `HistoricalWindow`;
- `PortfolioDayKey`;
- `Day4WindowSet`;
- `EventWindowLabel`;
- `OutcomeLabel`;
- `PortfolioDayLabel`;
- `Day4LabelPolicy`;
- `ProviderPricingSnapshot`;
- `Day4RepeatabilityPolicy`;
- `Day4ExperimentManifest`;
- `Day4ExecutionPlan`;
- `Day4Task`;
- `Day4TaskReceipt`;
- `ArchitectureObservation`;
- `PortfolioDayResult`;
- `AlertOutcomeMatch`;
- `ArchitectureEvaluation`;
- `RepeatabilityEvaluation`;
- `WorkedExample`;
- `Day4RunManifest`.

## Reviewed experiment manifest

The immutable reviewed experiment manifest identifies exactly three
private-neutral portfolio aliases and exactly three non-overlapping historical
windows: `stress_a`, `stress_b`, and `control`. Each window has exactly five
distinct reviewed daily-close timestamps in timezone-aware UTC. The manifest
therefore defines exactly 45 `PortfolioDayKey` contexts.

B0, B1, and A1 execute on every primary context, producing exactly 135 primary
architecture results. The context digest for a portfolio-day is identical
across architectures.

The manifest also defines exactly nine repeatability anchors, one per
portfolio-window pair. B1 and A1 each receive one additional observation on
every anchor. B0 is deterministic and is not recalled. The repeatability panel
therefore produces exactly 18 additional architecture results.

The authorized model-call budget is exactly 270:

- primary B1: 45 calls;
- primary A1: 180 calls;
- repeated B1: nine calls;
- repeated A1: 36 calls.

An authorization value must equal the reviewed plan. A missing, lower, higher,
or mutable authorization is rejected. The runner has no implicit provider and
no provider fallback.

An initialized manifest has `reviewed=false`. A human supplies the reviewer,
window rationales and dates, stress-window trigger availability, per-window
portfolio relevance, future-outcome thresholds, matching lookback, primary
label view, anchors, model configuration, pricing manifest, authorization,
and worked-example rules. Validation requires date coverage, required prior
and future sessions, no overlap, explicit control designation, B0/B1/A1,
`human_review_required=true`, and empty effects. No command selects a window,
threshold, anchor, or case.

## Execution and immutability

One manifest-driven runner creates an immutable `Day4ExecutionPlan` and stable
`Day4Task` identities before provider execution. Every attempted task produces
a `Day4TaskReceipt`. Completed receipts are preserved and skipped on resume;
the same semantic task cannot produce a duplicate call. A resume cannot
change the manifest, pricing snapshot, context, labels, provider, model
configuration, task identity, or call authorization.

The deterministic task identity covers the experiment digest, window,
portfolio, `as_of`, architecture, repetition, context digest, model snapshot,
and prompt-manifest digest. The runner phases are fixed:

1. validate the manifest and build the immutable task plan;
2. execute all primary architecture treatments;
3. execute only the additional anchor repetitions;
4. seal architecture output and the model-call ledger;
5. construct labels in the separate label module;
6. evaluate;
7. render results and the dashboard;
8. write manifests.

Provider and context modules do not import the label module.

Architecture observations preserve architecture identity, context digest,
semantic output digest, status, severity, critic result, evidence references,
provider receipt, latency, token counts, warnings, limitations, and empty
effects. Provider and schema failures are terminal execution failures and are
not evaluated as abstentions. The accepted Day 3 boundary may preserve such a
failure as `ABSTAINED_AGENT_OUTPUT` plus a `provider_error` or
`invalid_structured_output` receipt warning; Day 4 inspects the receipt first
and classifies that observation as `execution_failure`. An accepted real run
has zero provider errors.

All generated manifests, inputs, receipts, observations, labels, evaluations,
reports, charts, worked examples, and dashboard files are immutable external
artifacts. The evidence manifest digests every sibling evidence artifact.

## Label firewall

Labels are unavailable until all architecture execution is complete. No label
file path, label policy value, event-window label, future-outcome value,
composite value, or label-derived feature may enter an
`ArchitectureInputBundle`, role slice, provider request, prompt, or model
payload.

Exactly 45 `PortfolioDayLabel` records are loaded in the evaluation phase.
Every record contains:

- an event-window label;
- a five-business-day future outcome label;
- a composite OR label.

The event-window view is primary. The outcome and composite views are
secondary sensitivity views. Future outcomes are used only after architecture
execution and never become point-in-time evidence for an agent.

The event-window label is positive only for predeclared relevant
portfolio-window pairs and uses the reviewed stress-window
`trigger_available_at`. The control is negative unless an explicit outcome is
positive. The outcome label covers five future business sessions and uses
reviewed external thresholds for portfolio drawdown, realized volatility,
worst reviewed position loss, and an optional explicit material event.
Thresholds have no code defaults. The composite label is
`event_window OR outcome`.

## Classification

The architecture status mapping is fixed:

| Architecture status | Evaluation class |
| --- | --- |
| `REVIEW` | `alert` |
| `URGENT_REVIEW` | `alert` |
| `NO_ISSUE` | `no_alert` |
| `ABSTAIN` | `abstention` |
| `ABSTAINED_AGENT_OUTPUT` | `abstention` |

A positive-label abstention counts as a false negative. A negative-label
abstention is uncovered and reduces evaluated coverage; it is not a false
positive. A provider error is an execution failure, not an abstention.

## Alert and outcome matching

Matching is performed within one portfolio only. An alert is eligible only
when it is no later than the outcome and falls within the reviewed lookback.
Each alert and each outcome may be matched at most once. For an outcome, use
the closest eligible prior unmatched alert. Every `AlertOutcomeMatch`
preserves the rule, alert and outcome identities, timestamps, delay or lead
time, lookback, and supporting evidence.

## Descriptive measures

For each architecture, label view, portfolio, and window,
`ArchitectureEvaluation` reports:

- total portfolio-days;
- alerts, abstentions, and execution failures;
- TP, FP, TN, and FN;
- precision and recall;
- alerts per 100 portfolio-days;
- abstention rate;
- evaluated coverage;
- evidence-reference coverage;
- unsupported-claim rate;
- critic-pass rate;
- event detection delay;
- outcome lead time;
- median and deterministic p95 latency;
- input and output tokens;
- provider cost and pricing warnings.

Precision or recall with a zero denominator is `null` plus an explicit
warning, never zero. Missing observations remain missing.

`RepeatabilityEvaluation` reports semantic-status agreement, severity
agreement, exact semantic-output-digest agreement, affected-position Jaccard
agreement, and evidence-reference Jaccard agreement over the nine anchors.
B0 is evaluated through deterministic reuse and remains exact. Two
observations per B1/A1 anchor are a preliminary agreement check, not a complete
characterization of model-output variance.

Provider cost is derived only from an explicit, immutable, reviewed external
`ProviderPricingSnapshot`. It records provider, exact model snapshot, currency,
input and output prices per million tokens, `effective_at`, source reference,
reviewer, and digest. No price is hard-coded in source or fetched from the web
at runtime. If the reviewed snapshot lacks an applicable price, input and
output tokens remain reportable while cost is `null` and the warning is
`pricing_unavailable`.

## Required artifacts and acceptance

A complete run has 45 contexts, 135 primary observations, 18 repeat
observations, 153 total architecture observations, 45 labels, 270 model-call
receipts, zero provider errors, and empty effects. It contains an architecture
summary, repeatability summary, model-call ledger, run manifest, evidence
manifest, preliminary-results Markdown, one offline static HTML dashboard, and
exactly these charts: `alert-quality.svg`, `grounding-abstention.svg`, and
`latency-cost.svg`.

The immutable run layout is:

- `execution-plan.json`;
- `windows.json`;
- `architecture-input-index.parquet`;
- `raw-runs/**`;
- `architecture-results.parquet`;
- `labels.parquet`;
- `portfolio-day-results.parquet`;
- `architecture-summary.csv`;
- `repeatability-results.parquet`;
- `repeatability-summary.csv`;
- `model-call-ledger.parquet`;
- `worked-examples/**`;
- `charts/alert-quality.svg`;
- `charts/grounding-abstention.svg`;
- `charts/latency-cost.svg`;
- `preliminary-results.md`;
- `dashboard/index.html`;
- `dashboard/dashboard-data.json`;
- `run-manifest.json`;
- `evidence-manifest.json`.

The evidence manifest covers every file or tree digest.

Worked-example rules are fixed in the reviewed manifest before execution. The
run contains at least three alert cases, at least one false-positive or
failure case, and at least one abstention case.

The deterministic rules select the earliest true positive in `stress_a`, the
earliest true positive in `stress_b`, the highest-severity true positive from
a different portfolio where available, the earliest false positive or
otherwise earliest execution or critic failure, and the earliest abstention.
If fewer than three alert cases exist, acceptance fails; labels and thresholds
remain unchanged.

The static dashboard uses semantic HTML, embedded CSS, small local JavaScript,
and inline or local SVG. It has no CDN, frontend framework, application route,
or mandatory server. It exposes portfolio, window, review-date, and
architecture controls and presents NAV and drawdown context, the MetricPack,
eligible events, deterministic findings, architecture comparison, critic and
evidence detail, token/latency/cost data, human decision options, and a
Markdown export link.

All outputs distinguish observations, methodology, assumptions, warnings, and
limitations. They contain no significance test, winner field, architecture
recommendation, predictive claim, investment-performance claim, or
consequential effect. Automated acceptance cannot approve Day 4, the pull
request, or a release; explicit human QA is required.
