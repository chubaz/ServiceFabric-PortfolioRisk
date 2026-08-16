# Phase 12: Single-run research registry

## Purpose

Make every individual run scientifically locatable before the concurrent
Experiment Lab is introduced. This phase owns classification, immutable context
supersession, rerun obligations, coverage and analysis identity. It does not
own job scheduling, worker allocation or concurrent execution.

## Required initial comparison

Every accepted fixed context starts with three vertical baseline cells:

1. **B0** — deterministic, pre-parameterised workflow;
2. **B1** — single agent with a bounded capability catalogue and budget;
3. **A1** — agent graph with the same bounded reachable environment.

All three begin from the same portfolio, mandate, scenario, point-in-time data
boundary and assigned information regime. A new architecture is a
cross-sectional variant, not a replacement baseline.

## Run classification

The immutable run classification is:

```text
study → experiment → fixed context → case → baseline/architecture
     → portfolio+mandate → information regime → scenario → evaluation → repetition
```

Market-regime labels are applied to cases for stratified analysis. They do not
enter an agent prompt unless the assigned information regime declares them as
available. Actual capability use is retained as a run observation and does not
change the assigned information-regime bin after execution.

## Context revision and reruns

Contexts are append-only. A changed portfolio/mandate, scenario, data boundary,
information regime or reachable capability environment produces a successor
digest. Old runs remain reproducible evidence for their original context, but
are `stale_for_active_program`; every affected old cell creates a rerun
obligation under the successor context.

Changing an architecture reruns that architecture’s cells. Changing an
evaluation method or admitting later labels creates a new evaluation. Changing
an analysis specification creates a new analysis snapshot. None of these
operations overwrites the historical run.

## Later development

- Persist classification receipts, context successors and rerun obligations in
  the Registry.
- Show program coverage: required, complete, failed, stale and missing cells.
- Register architecture, portfolio/mandate, information regime and scenario
  variants from System Development.
- Add declared contrasts and analysis snapshots for paired comparison,
  counterfactual analysis and regression datasets.
- Let the Experiment Lab schedule the same planned cells concurrently; it must
  consume this registry rather than define another taxonomy.
