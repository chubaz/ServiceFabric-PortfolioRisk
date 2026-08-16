---
name: design-servicefabric-experiment
description: Design and review governed ServiceFabric PortfolioRisk experiments and evaluation plans. Use whenever Codex discusses experiment design, evaluation methodology, counterfactual comparisons, comparison dimensions, treatment matrices, standalone experiment definitions, concurrent experiment batches, terminal counterfactual analysis, robustness or repetition plans, portfolio-action counterfactuals, or an Experiment Lab/Studio. Do not use for post-run retained-evidence integrity audits or to execute a research run.
---

# Design ServiceFabric Experiment

Ground every design in the repository methodology rather than inventing a new
comparison taxonomy.

Before proposing or changing an experiment:

1. Read the repository `AGENTS.md` and `docs/workplans/current.md`.
2. Read `docs/thesis/counterfactual-experiment-design.md` completely.
3. Read `docs/thesis/experiment-evaluation-framework.md` when defining outputs,
   evaluator states or measurement timing.
4. Read `docs/thesis/experimental-object-operating-model.md` when binding the
   design to registered objects, Fixture Context or Experiment Kernel.

## Design rules

- Use Study → Experiment → Case → Run as the scientific hierarchy.
- Treat Regime as a cross-cutting classification on Cases, not as another
  parent. Treat it as an intervention only when an explicit synthetic scenario
  changes the market path.
- Start with one research question, hypothesis and standalone Experiment
  definition.
- Freeze the Case and point-in-time evidence boundary before varying a system.
- Classify every proposed dimension as a system intervention, conditioning
  variable or financial counterfactual.
- Predeclare the baseline, treatment, changed dimensions, fixed controls,
  repetitions, outcomes and evaluator before execution.
- Prefer paired within-Case comparisons and bounded sequential Experiments.
- Add interaction cells only for an explicit interaction question.
- Preserve the common architecture output contract across treatments.
- Keep hidden labels and matured outcomes unavailable until post-Run evaluation.
- Preserve risk quality, decision quality, realised profit and loss, and
  opportunity cost separately.
- Represent unavailable results as `partial`, `not_measurable` or
  `not_applicable`; never invent a proxy score.
- Keep the Studio a composer and reader of standalone Experiments. Do not create
  a Studio-only execution or evaluation path.
- Keep single-Run validation and counterfactual Experiment composition as two
  visible, connected work areas. Default apparatus validation to B0 and reuse
  its exact setup when composing the matched matrix.

## Concurrent batch rule

Allow independent Run cells to execute concurrently without altering their
scientific identities or controls. Require the Experiment to produce a terminal,
versioned counterfactual analysis after all eligible Runs finish.

The analysis must bind to exact Run IDs and report matrix coverage, paired
within-Case effects, declared interactions, repeated-Run stability,
Regime-conditioned results, separate outcome dimensions, confounds, failed
treatment manipulations, missing cells and not-yet-measurable outcomes. A failed
or missing required cell produces partial analysis with affected contrasts; it
is never silently excluded. The analysis never rewrites source Run outputs.

## Design handoff

Return or write a design containing:

- Study, Experiment, Case, Run and Regime identities;
- research question and hypothesis;
- standalone Experiment boundary;
- Case definition and information boundary;
- baseline and treatment cells;
- intervention, conditioning and financial-counterfactual dimensions;
- fixed controls and confound checks;
- outcome and evaluation definitions;
- concurrency and terminal-analysis semantics;
- repetition and robustness plan;
- retained outputs and missingness states;
- bounded first slice and explicitly deferred dimensions.

State the expected Run count before recommending a matrix. If a proposed
Cartesian product is large, split it into the sequential programme from the
counterfactual design reference.

## Boundaries

- Do not claim causality, prediction, mitigation or thesis readiness from an
  unexecuted design or calibration fixture.
- Do not choose treatments, metrics or loss weights after observing results.
- Do not add live orders, broker connectivity, portfolio mutation authority or
  automatic rebalancing.
- Do not build or execute the experiment unless the user explicitly requests
  implementation or execution.
- For retained Run integrity and pair comparability after execution, switch to
  `$audit-servicefabric-experiment-run`; do not duplicate its evidence gate.
