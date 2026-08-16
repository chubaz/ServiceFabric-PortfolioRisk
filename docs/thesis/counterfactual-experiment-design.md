# Counterfactual experiment design

## Purpose

The Experiment Lab should answer one disciplined question:

> Given the same Case and the information available at decision time, what would
> have happened under another permitted system configuration or financial
> choice?

Counterfactual reasoning applies to every manipulable comparison dimension, not
only to portfolio actions. A comparison is credible only when its changed
dimension is declared before execution and the other relevant dimensions remain
fixed.

## Scientific object split

Use this hierarchy throughout the Experiment Lab:

```text
Study
└── Experiment
    └── Case
        └── Run
```

- A **Study** states the research programme and groups related Experiments.
- An **Experiment** states one research question and hypothesis, declares its
  baseline, treatments, controls, outcomes and evaluation protocol, and owns one
  concurrent batch of Runs.
- A **Case** freezes the portfolio, mandate, point-in-time information, evidence
  boundary and Case characteristics.
- A **Run** executes one configuration on one Case and retains its inputs,
  configuration, outputs, trace, observations and evaluation.
- A **Regime** classifies Cases across Experiments. It is cross-cutting metadata,
  not another parent in the hierarchy and not normally an intervention.

The Runs for a Case are cells in a predeclared configuration grid. This permits
paired comparisons within the same Case instead of comparisons between
unrelated Cases.

A compact potential-outcome notation is:

```text
Y_case(architecture, information, capabilities, parameterisation,
       event_selection, model_configuration, decision_policy)
```

A counterfactual effect changes one declared argument while holding the others
fixed. An interaction changes two dimensions deliberately, for example to ask
whether event information helps an agent graph more than a single agent.

## Comparison dimensions

| Dimension | Counterfactual question |
|---|---|
| Architecture | What would the same Case produce under deterministic, single-agent or agent-graph execution? |
| Information regime | What changes when the method receives portfolio-only, market, event, or mandate/thesis context? |
| Capability pack | What is the marginal value of basic metrics, monitoring, scenario, factor or decision capabilities? |
| Parameterisation | What changes when parameters are fixed, mechanically derived or selected/constructed by an agent? |
| Event selection | What changes with no filtering, basic/provider filtering, ex-ante ML relevance or a retrospective oracle upper bound? |
| Agent/model configuration | What changes with another model, prompt, budget, temperature or coordinator configuration? |
| Repetition | How stable is the same configuration across identical repeated Runs? |
| Decision policy | What changes when the method may only alert, may recommend, or may select a simulated action? |
| Portfolio action | What would the subsequent outcome have been under no action, reduction, hedge or exit branches? |

Architecture, information, capabilities, parameterisation, event selection,
model configuration and decision policy are **system interventions**. Portfolio
action, execution assumptions and simulated market paths are **financial
counterfactuals**.

Market/economic Regime, event type, risk type, severity and portfolio
characteristics are normally **conditioning or stratification variables**. A
historical Case cannot simply be reassigned to another Regime. Changing the
Regime requires an explicit synthetic scenario and must be presented as a
scenario counterfactual.

## Outcomes

Measure outcomes separately across:

1. detection quality;
2. severity and risk understanding;
3. timeliness;
4. evidence quality;
5. decision quality;
6. robustness;
7. stability;
8. latency and cost.

Do not collapse risk quality, decision quality, realised profit and loss, and
opportunity cost into one convenient result. Each answers a different question.
The common architecture output contract and post-Run evaluator remain the
authorities defined in `docs/thesis/experiment-evaluation-framework.md`.

## Standalone Experiment contract

An Experiment must be executable without the Studio and must retain enough
information for the Studio to reconstruct its design, progress and results. It
should declare:

- one research question and hypothesis;
- the Cases and their point-in-time evidence boundaries;
- the baseline cell and treatment cells;
- the intentionally varied dimensions;
- the controls that must remain identical;
- repetitions and random/model configuration;
- outcome definitions and evaluation metrics;
- required labels or matured outcomes;
- its complete Run outputs, traces, evaluation records, latency and cost;
- missing, partial, not-measurable and not-applicable results without invented
  substitutes.

The Studio is a composer of standalone Experiment definitions and a reader of
their retained outputs, not a second execution or evaluation path.

## Lab interaction model

Keep two visible, connected work areas:

1. **Single-Run validation** executes one method on one frozen Case through the
   canonical runtime, evaluator and retention path. It is the default starting
   point for confirming that data access, processing, output mapping,
   evaluation and persistence work end to end. A successful Run validates that
   apparatus cell; it is not comparative evidence.
2. **Counterfactual Experiment** reuses validated Case, method, window and
   evaluator selections to compose a predeclared matched-Run matrix. It owns the
   Study and Experiment intent, controls, concurrency and terminal analysis.

The Experiment Studio must not replace or duplicate the single-Run executor.
The interface should provide an explicit handoff in both directions: promote a
single-Run setup into an Experiment design, and validate the B0 cell from an
Experiment before executing its matrix. The single-Run route should default to
the deterministic B0 treatment so apparatus validation does not require a model
call or external-context authorization.

## Concurrent execution and terminal analysis

An Experiment may execute its independent Run cells concurrently. Concurrency
changes scheduling only; it must not change the scientific identities, inputs,
controls, output contract or evaluation protocol of a cell.

When all eligible Runs reach a terminal state, the Experiment must produce a
separate counterfactual analysis bound to the exact Run outputs. The analysis
must include:

- completion, failure and missing-cell coverage for the declared matrix;
- paired baseline-versus-treatment effects within each Case;
- declared interaction effects where the matrix supports them;
- stability across identical repetitions;
- results conditioned on Regime and Case characteristics;
- detection, severity, timeliness, evidence, decision, robustness, latency and
  cost outcomes without collapsing them into one score;
- confounds, failed treatment manipulations, unavailable labels, censoring and
  outcomes that are not yet measurable;
- the evaluation version and the exact Run identifiers used.

The analysis is produced after the concurrent batch; it does not rewrite any
Run output. If a required cell fails or is missing, report partial analysis and
the affected contrasts rather than silently dropping the cell. Re-evaluation
after labels or financial outcomes mature creates a new analysis version.

## Paired comparison rule

For each comparison:

1. Freeze one Case and its available-at information boundary.
2. Declare the baseline, treatment and changed dimension before running.
3. Hold the remaining dimensions and evaluation protocol fixed.
4. Execute both cells through the same canonical runtime and output contract.
5. Repeat identical cells when stability is an outcome.
6. Join hidden labels or matured financial outcomes only after execution.
7. Calculate paired effects within the Case, then condition aggregate results on
   Regime and Case characteristics.

An undeclared difference is a confound. A declared dimension that did not
actually change is a failed treatment manipulation.

## Portfolio-action counterfactuals

At decision time, freeze the actual portfolio and branch over a finite permitted
action set. Begin with:

```text
NO_ACTION
REDUCE_POSITION_25%
REDUCE_POSITION_50%
```

All branches initially experience the same subsequent historical market path.
Predeclare the decision time, execution delay, transaction costs, evaluation
horizons, mandate constraints, benchmark and objective function. The initial
apparatus may assume the portfolio is a price taker, but must state that
assumption.

For each branch preserve return, drawdown, volatility, VaR/ES where available,
risk-limit breaches, concentration, benchmark-relative return, factor exposure,
scenario loss and transaction cost. Judge actions through a fixed,
mandate-derived loss function rather than realised return alone:

```text
regret(action) = loss(action) - minimum loss among permitted actions
mitigation(action) = loss(NO_ACTION) - loss(action)
```

Describe mitigation as a retrospective association under the declared path, not
as risk that the system definitively avoided.

Alternative market paths may be added later. They create a second layer that
tests whether an action remains reasonable across plausible futures rather than
being lucky under realised history.

## Sequential programme

Do not begin with the full Cartesian product. Use bounded, sequential
Experiments:

1. architecture comparison;
2. architecture × information;
3. architecture × capability pack;
4. fixed versus mechanically or agent-derived parameterisation;
5. event-context selection methods;
6. decision policy and portfolio-action branches;
7. robustness analysis conditioned on Regime and Case characteristics.

Start portfolio-action evaluation with historical paths and the three bounded
actions above. Add mandate-derived loss, costs and regret next; hedging and more
sophisticated actions after that; alternative market scenarios last.

This sequence keeps each causal question legible, limits Run volume and makes
interaction tests deliberate.

## Experiment-page visual contract

The Design view presents the comparison space in four connected parts:

1. **Change the system** — manipulable architecture, information, capability,
   parameterisation, event-selection, model-configuration, repetition and
   decision-policy dimensions.
2. **Simulate financial outcomes** — portfolio-action and explicit
   market-scenario branches. These are not confused with system treatments.
3. **Group the results** — observed Regime and Case characteristics used for
   stratification rather than reassigned as treatments.
4. **Measure outcomes** — the post-Run evaluation dimensions, displayed
   separately from everything the experiment varies.

The page also displays the sequential programme and identifies the currently
executable slice. This prevents the catalogue from implying that all dimensions
should be combined into one Cartesian-product experiment.
