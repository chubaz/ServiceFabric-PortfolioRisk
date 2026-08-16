# Experiment evaluation framework

For the treatment taxonomy, paired-comparison rules, standalone Experiment
boundary and financial-counterfactual progression, read
`docs/thesis/counterfactual-experiment-design.md` with this framework.

## Experimental hierarchy

Every retained result belongs to one unambiguous scientific hierarchy:

```text
Study
└── Experiment
    └── Case
        └── Run
```

- A **Study** states the research programme.
- An **Experiment** states one question and hypothesis, fixing controlled factors
  and declaring what varies.
- A **Case** fixes the portfolio, mandate, point-in-time data and evidence that an
  architecture is allowed to observe.
- A **Run** executes one architecture on one Case and retains its input,
  configuration, output, trace, observations and evaluation.

Market **Regimes** classify Cases across experiments; they are not an additional
parent in the hierarchy. Regime and outcome labels live in `CaseEvaluationState`,
which is explicitly unavailable to the architecture under test. This prevents a
method from receiving its own answer key.

## Output and evaluation separation

`ArchitectureOutput` is the immutable result produced by the method under test. It
contains its assessment, findings, evidence, risk interpretation, expectations,
confidence, uncertainty and proposed monitoring or review decision. A separate
evaluator later produces `EvaluationRecord`, bound to the exact output identifier.
The human-readable Markdown report is compiled from these records; it is a
presentation and is never the object being scored.

An architecture now produces one immutable `ArchitectureOutput` for every
workflow cycle, not one conclusion after the full period has been revealed. The
run retains the ordered output sequence. Consecutive breaches of the same rule
are consolidated into a `FindingEpisode` with first detection, last detection,
maximum severity, maximum threshold distance and resolution state.

Every cycle decision creates a selected branch and a counterfactual branch. Both
remain `awaiting_outcome` until the declared horizon. Decision regret is therefore
computable later without inventing a favourable outcome during execution.

## Architecture-specific interpretation

All architectures receive the same versioned cycle context, metric contracts and
classified event/fundamental context. Their interpretation policy differs:

- the deterministic reference uses fixed mandate rules;
- a single-agent architecture may choose evidence and capabilities within its
  registered contract and must return the same typed cycle output;
- an agent graph may delegate and validate work, but must return the same typed
  cycle output and trace every specialist contribution.

The event classification interface is currently a deterministic provider-score
baseline. It is deliberately replaceable by a fast, versioned inference model for
relevance or severity without changing the execution-kernel context contract.

Every model-based architecture is born wrapper-compatible in Agent Studio and
runs headlessly in an experiment. A single-agent method has one final decision
agent. A graph retains all specialist-node outputs but maps only its one declared
final decision contribution. Specialist decisions are explicitly advisory.
User-facing reports, charts and dashboards are presentation artifacts and are
labelled outside the experiment rather than scored as architecture outputs.

The wrapper captures observed runtime behavior. For graphs this includes agent
contributions, finding and decision disagreement, severity and confidence
dispersion, accepted critic corrections, handoffs, synthesis time and
coordination overhead. The wrapper does not rewrite the financial conclusion.

The experiment page evaluates every method on nine dimensions:

1. detection quality;
2. severity and risk understanding;
3. timeliness;
4. evidence quality;
5. confidence and calibration;
6. decision quality;
7. robustness;
8. stability;
9. efficiency.

An evaluation field is never replaced by a convenient proxy. It is reported as
`measured`, `partial`, `not_measurable`, or `not_applicable`. Precision, recall,
severity error, warning lead time, calibration, decision regret, and cross-regime
robustness require independently reviewed labels or comparison cases. The first
deterministic replay therefore preserves those fields but does not invent scores.

| Dimension | Produced during the run | Joined only after the run |
|---|---|---|
| Detection quality | typed findings and affected assets | hidden finding labels |
| Severity and understanding | severity, materiality, risk channel and interpretation | reviewed severity labels |
| Timeliness | trigger, observation, first-finding and output timestamps | eligible event time |
| Evidence quality | citations, conflicts and capability receipts | evidence-quality review |
| Confidence and calibration | value, kind and method | labels or realised outcomes |
| Decision quality | action, rationale, alternatives and branch IDs | matured branch outcomes |
| Robustness | case, context digest and perturbation ID | matched perturbation set |
| Stability | repetition ID, output digest and structured claims | repeated identical cases |
| Efficiency | wall time, critical path, calls, tokens, cost, retries and errors | declared budget |

This separation prevents the architecture from seeing its own answer key while
ensuring `ArchitectureOutput` contains every architecture-side observation the
evaluator needs.

## Deterministic reference treatment

The reference method performs no model calls. It:

- reads point-in-time CRSP prices, eligible RavenPack events, and available
  Compustat observations from the licensed local DuckDB database;
- calculates daily return, annualised volatility, drawdown, cash weight, largest
  issuer weight, and—where the mandate requires it—largest sector weight;
- applies the exact versioned research mandate selected with the portfolio;
- records pass, breach, and unable-to-assess counts for every clause;
- creates a classified event state and a small fundamental state for every cycle
  before the fixed rules execute;
- attaches metric and mandate references to each warning;
- records latency, database queries, model calls, cost, missing observations, and
  deterministic stability;
- produces a structured architecture output, including a bounded monitoring or
  human-review decision, but never mutates the portfolio or causes an external
effect.

## Metric computation

Each metric is governed by a retained `MetricSpecification` defining formula,
unit, history policy, adjustment policy, required observations and missing-data
treatment. The selected experiment start date no longer resets its history:

- daily portfolio performance prefers CRSP total returns and uses a disclosed
  price-return fallback only when a curated constituent total return is missing;
- volatility uses every available portfolio return from common constituent
  inception through the cycle as-of date;
- drawdown uses the total-return high-water mark from that same inception;
- concentration and cash metrics remain point-in-time calculations over accepted
  fixed quantities and cash.

Incomplete constituent valuation is retained as partial data quality and reduces
calculation confidence. It is never silently converted to zero. Fixed quantities,
constant cash, and any price-return fallback remain explicit counterfactual
limitations.

## Functional evaluator

The selected-case evaluator is now implemented as
`risk_experiments.evaluate_selected_case_trajectory`. It joins an immutable
`RunTrajectory` to an independently accepted `GoldCaseRecord` only after the Run
has terminated. Every nested `EvaluationMetricResult` retains its status, value,
numerator, denominator, unit, method, reference identities and limitations. An
unavailable metric cannot carry a value and an unavailable dimension cannot carry
a score.

For the first retained ADX Case, the available references support five bounded
measurements:

- selected-case detection and downside direction, without population precision
  or recall;
- daily-session timeliness and separate real processing latency;
- reviewed supporting/alternative evidence roles and point-in-time source
  eligibility;
- ex-ante monitoring-action appropriateness at one sealed checkpoint, kept
  separate from unavailable economic branch regret;
- runtime, model calls, tokens, cost and abstention without an arbitrary
  efficiency composite.

Economic severity is not scored because the current outputs carry ordinal
urgency, not comparable basis-point forecasts. Confidence calibration is not
scored from one selected positive Case. Session 10 adds two identical
repetitions and a predeclared one-cycle adverse-event delay for every method.
Stability now compares normalized structured behavior across repetitions;
robustness compares detection and evidence retention against the matched delay.
Both remain bounded selected-Case measurements, not population claims. Missing
severity and calibration evidence stays explicitly `not_measurable`, never zero
or perfect.

The evaluator is versioned and bound to the ordered cycle-output identifiers,
trajectory digest and Gold digest. Evaluation records are immutable under the
external `run-evaluations` repository. Later label admission, branch maturity,
repeat Runs or perturbations create new versioned evaluation evidence; they never
rewrite architecture output.

Completed comparisons can be saved as a content-addressed reproducibility
bundle containing the exact Case, developer-only Gold reference, matrix,
trajectories, evaluations, human report and Codex diagnostics. File digests are
verified on load; reproduction recomputes the comparison from immutable source
records and must match the manifest digest. Archive is reversible and removal
is a recoverable tombstone that never deletes the source Runs.

The current named portfolios retain the accepted quantities and resolve current
company names from the licensed security master. Applying these fixed holdings to
2013–2017 remains a technical counterfactual rather than a thesis-valid historical
portfolio-construction rule.

## Persistence

When **Save this run** is selected, the governed Artifact Repository retains the
complete `result.json` plus separately inspectable `case.json`, `run-input.json`,
`architecture-output.json`, `run-trace.json`, `evaluation-record.json`, and the
ordered `architecture-outputs.json`, `finding-episodes.json`,
`decision-branches.json`, `metric-specifications.json`, and downstream `report.md`.
The files are licensed, publication-restricted experiment
evidence. Reloading reads those saved bytes and does not repeat the calculation.
Future evaluator versions must create a new evaluation record rather than
overwrite the original architecture output.

Isolated Agent Studio tests are not experiment runs. They persist
`agent-output.json` with `not_admitted_to_experiment`; only a wrapper execution
bound to a registered Case, Run and workflow cycle may create
`ArchitectureOutput`.
