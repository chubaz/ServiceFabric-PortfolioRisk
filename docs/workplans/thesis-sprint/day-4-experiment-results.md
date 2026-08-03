# THESIS-D4 — Experiment execution and results

- Status: deferred after public fixture verification; real panel and human QA not run
- Depends on: `THESIS-D3` complete and accepted
- Experiment: `portfolio-risk-architecture-comparison-v1`

## Objective

Execute a reviewed, manifest-driven historical comparison of B0, B1, and A1,
produce reproducible descriptive evidence and one offline static dashboard,
and prepare an explicit human QA decision without overstating the preliminary
experiment.

## Lifecycle closeout

The public synthetic 45-context fixture, 153 architecture observations, 45
labels, 270 deterministic call receipts, descriptive evaluation, report, and
offline dashboard passed their automated gates. The user elected not to run
the full paid real-data experiment at this stage. Consequently:

- the real 270-call panel is not claimed as executed;
- human scientific QA is not claimed as passed;
- no architecture ranking, predictive result, or release decision exists;
- the implementation and immutable fixture evidence are retained for later
  resumption under an explicit workplan.

## Accepted entry evidence

Day 1 through Day 3 are complete. The accepted entry evidence includes exactly
three explicitly reviewed fixed-quantity portfolios, Day 2 Morning
MetricPacks and deterministic decision-kernel outputs, reviewed point-in-time
events, and one validated B0/B1/A1 provider run. It contains no historical
ranking or outcome evaluation.

Day 4 reuses the Day 2 calculation path and Day 3 architecture runner. It adds
no dependency, frontend framework, provider abstraction, application change,
generic experiment framework, second architecture runner, or large
interactive shell script.

## Frozen primary panel

- Exactly three reviewed private-neutral portfolios participate.
- Exactly three predeclared, non-overlapping historical windows participate:
  two stress or event windows and one quiet control window.
- Each window contains exactly five distinct reviewed daily-close timestamps
  in timezone-aware UTC.
- The panel therefore contains exactly 45 authoritative portfolio-day
  contexts.
- B0, B1, and A1 run on the same authoritative context for every portfolio-day.
- The panel therefore contains exactly 135 primary architecture results.

The system may profile eligible coverage, but it must never select a window
automatically. Every window and review timestamp is frozen in a reviewed
experiment manifest before execution.

The experiment initializer writes `reviewed=false`. A human must explicitly
provide the reviewer, three window rationales, five dates per window,
`trigger_available_at` for each stress window, portfolio relevance per window,
future-outcome thresholds, matching lookback, primary label view, one anchor
date per portfolio-window, model configuration, pricing manifest, maximum
authorized calls, and worked-example selection rules. The system does not
choose windows, dates, thresholds, anchors, or worked cases.

Validation requires non-overlapping windows; coverage for all dates; required
prior and future sessions; an explicitly designated control; exactly
B0/B1/A1; `human_review_required=true`; and empty effects.

## Frozen repeatability panel and budget

Nine anchors are predeclared, one for every portfolio-window pair. B1 and A1
have two total observations on each anchor: the primary observation and one
additional repeat. B0 is deterministic and is not recalled. The repeatability
panel therefore contains exactly 18 additional model-assisted architecture
results.

The primary matrix authorizes 225 model calls: 45 B1 calls and 180 A1 role
calls. The anchor repeats authorize another 45 calls: nine B1 calls and 36 A1
role calls. The maximum authorized provider-call budget is exactly 270. A
budget mismatch is rejected; the run may not silently override the reviewed
manifest.

Two observations per anchor support only a preliminary agreement measure. They
do not characterize the full variance of model output.

## Execution and label separation

One manifest-driven Python runner builds and freezes the execution plan,
materializes all Day 2 and Day 3 inputs, executes the complete primary and
repeatability panels, and writes immutable task receipts. It is resumable:
completed tasks are skipped without duplicate calls, semantic task identity is
stable, and a resumed run cannot exceed the authorized budget.

Architecture execution completes before labels are loaded. No label path,
event-window label, future-outcome value, composite value, or derived label
feature may enter `ArchitectureInputBundle`, a provider request, or a model
payload.

There are exactly 45 label records. Each record contains:

- an event-window label;
- a five-business-day future outcome label;
- a composite OR label.

The event-window label is the primary preliminary view. Outcome and composite
labels are secondary sensitivity views and are used only in the evaluation
phase.

An event-window label is positive only for a predeclared relevant
portfolio-window pair and uses that stress window's `trigger_available_at`.
The control is negative unless an explicit outcome label is positive. The
outcome view covers five future business sessions and applies reviewed
external thresholds for future portfolio drawdown, future realized
volatility, worst reviewed position loss, and an optional explicit material
event. Thresholds have no source-code defaults.

## Classification and abstention

- `REVIEW` and `URGENT_REVIEW` classify as `alert`.
- `NO_ISSUE` classifies as `no_alert`.
- `ABSTAIN` and `ABSTAINED_AGENT_OUTPUT` classify as `abstention`.
- An abstention on a positive label counts as a false negative.
- An abstention on a negative label is uncovered. It affects evaluated
  coverage and does not count as a false positive.
- A provider error is an execution failure, not an abstention.
- An accepted real run requires zero provider errors.

## Descriptive evaluation

For every architecture, label view, portfolio, and window, report total
portfolio-days, alerts, abstentions, execution failures, TP, FP, TN, FN,
precision, recall, alert count per 100 portfolio-days, abstention rate,
evaluated coverage, evidence-reference coverage, unsupported-claim rate,
critic-pass rate, median event detection delay, and median outcome lead time.
Undefined precision or recall is `null` with an explicit warning; it is never
coerced to zero.

Report semantic-status agreement, severity agreement, exact-output-digest
agreement, affected-position Jaccard agreement, evidence-reference Jaccard
agreement, median latency, deterministic p95 latency, input tokens, output
tokens, and provider cost. B0 agreement is calculated from deterministic reuse
and remains exact. Cost is calculated only from an explicit reviewed external
pricing manifest. No price is hard-coded in source and no runtime price is
fetched from the web. When pricing is unavailable, tokens remain reportable,
cost is `null`, and the warning is `pricing_unavailable`.

Alerts and outcomes match only within the same portfolio. An alert must be no
later than the outcome and within the reviewed lookback. Each alert and each
outcome is matched at most once, using the closest eligible prior unmatched
alert. The matching rule and the evidence for every match are preserved.

## Required external evidence

The completed evidence bundle contains:

- the reviewed experiment manifest;
- 45 portfolio-day contexts;
- 135 primary architecture results;
- 18 additional B1/A1 repeat results;
- 153 total architecture observations;
- 45 label records;
- an architecture summary table;
- a repeatability summary;
- a 270-entry model-call ledger;
- `alert-quality.svg`, `grounding-abstention.svg`, and `latency-cost.svg`;
- at least three worked alert cases;
- at least one false-positive or failure case;
- at least one abstention case;
- `preliminary-results.md`;
- one offline static HTML dashboard;
- a run manifest;
- an evidence manifest.

The immutable run directory contains `execution-plan.json`, `windows.json`,
`architecture-input-index.parquet`, `raw-runs/**`,
`architecture-results.parquet`, `labels.parquet`,
`portfolio-day-results.parquet`, `architecture-summary.csv`,
`repeatability-results.parquet`, `repeatability-summary.csv`,
`model-call-ledger.parquet`, `worked-examples/**`, the three charts,
`preliminary-results.md`, `dashboard/index.html`,
`dashboard/dashboard-data.json`, `run-manifest.json`, and
`evidence-manifest.json`. The evidence manifest covers every file or tree
digest.

Worked cases are selected by rules frozen in the experiment manifest, not
chosen after reviewing architecture results. The dashboard is self-contained
HTML, CSS, JavaScript, and SVG, uses no remote asset, requires no application
change, exposes portfolio/window/date/architecture selection, and retains
critic failures, abstentions, evidence references, costs, latency, and the
human-review boundary.

The deterministic worked-case rules select the earliest true positive from
each stress window, the highest-severity true positive from a different
portfolio where available, the earliest false positive or otherwise earliest
execution or critic failure, and the earliest abstention. Fewer than three
alert examples fails the exit criterion; labels and thresholds are not changed
to manufacture a pass.

## Claims and completion boundary

Results are descriptive research observations. There is no significance test,
no winner field, no architecture recommendation, no predictive claim, no
investment-performance claim, no loss-prevention claim, no
production-readiness claim, and no regulatory-compliance claim. No result
authorizes a broker action, order, trade, rebalance, optimization, or
portfolio mutation.

Generated mutable artifacts remain outside Git. Committed material may contain
only reviewed public-safe summaries and explicitly synthetic fixtures allowed
by the repository boundary. Licensed rows, identifiers, private portfolio
details, provider payloads, raw responses, credentials, local paths, and
private pricing do not enter Git.

Results must distinguish evidence from assumptions, warnings, and limitations.
They are research observations, not investment advice, and authorize no
trading or portfolio mutation effect.

Day 4 is complete only after explicit human QA. A successful automated run
does not approve the experiment, the pull request, or a release.
