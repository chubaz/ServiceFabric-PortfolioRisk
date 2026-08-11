# Work needed before the first research experiment

## Important distinction

The repository contains automated software tests and development-only sample
data. They help developers find broken code. They are not research experiments,
historical evidence or thesis results, and the main research interface must not
present them as such.

## Required for the first real run

- [ ] Select one historical dataset and test period.
- [ ] Check that each record was available on the date when the method receives
  it.
- [ ] Select one portfolio.
- [ ] Record its mandate, risk limits and allowed recommendations.
- [ ] Define which historical events or outcomes count as relevant risks.
- [ ] Review the first set of labels manually.
- [ ] Connect the rules-based method to these cases.
- [ ] Connect the fixed-workflow method to the same cases.
- [ ] Connect the LLM method to the same cases.
- [ ] Run all three methods without changing the input data between them.
- [ ] Measure warning accuracy, timing, missed risks, failures and cost.
- [ ] Save the report, case details and run files together.

## Required before thesis-scale experiments

- [ ] Repeat the run and measure whether each method gives stable results.
- [ ] Add more portfolios, periods and event types.
- [ ] Test how results change when information is added or removed.
- [ ] Record uncertainty and human disagreements in the labels.
- [ ] Review a sample of results with the supervisor.
- [ ] Freeze the final experiment plan before running the thesis evidence set.

## Presentation work

- [ ] Choose two clear historical cases for the demonstration.
- [ ] Prepare one comparison table and one timing chart.
- [ ] Create the 10-minute supervisor presentation.
- [ ] State clearly what is working, what is not working and which decisions are
  needed from the supervisor.

This is the active development list. A new page, category or studio should be
added only when it directly completes one of these items.
