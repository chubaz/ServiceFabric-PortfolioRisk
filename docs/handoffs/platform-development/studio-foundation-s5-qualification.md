# STUDIO-S5 engineering qualification

- Date: 2026-08-10
- Scope: Studio foundations S1-S5 and the existing PLATFORM-P6 application boundary
- Engineering result: qualified locally
- Methodological result: human acceptance pending
- External effects: disabled
- Candidate commit: pending; the working tree contains the complete uncommitted Studio programme

## What is qualified

The implemented S5 contracts can represent one closed scientific design and one
closed experiment-object set. Their identities are digest-bound, cross-pack
references are validated, undeclared capabilities and datasets are denied, the
teaching authority is human-only, supra-agent resolution is disabled, and no
external financial effect is available.

The following gates passed:

| Gate | Result |
|---|---:|
| repository preflight | pass |
| STUDIO-S1 Risk Analysis Package | 67 tests passed |
| STUDIO-S2 Capability Studio | 17 tests passed |
| STUDIO-S3 Agent Studio | 30 tests passed |
| STUDIO-S4 Experiment Run Audit | 35 tests passed |
| STUDIO-S5 Experiment Object Model | 63 tests passed |
| PLATFORM-P6 compatibility | 54 tests passed |
| combined Registry, artifact, experiment, application, architecture and tutorial suite | 112 tests passed |
| Python and JavaScript syntax checks | pass |
| S5 tutorial execution | pass |
| package-manifest integrity | pass |
| whitespace/diff integrity | pass |

The repeatable machine gate is:

```bash
make verify-studio-foundation-s5-qualification
```

The gate deliberately excludes network calls, model calls, worker execution,
metric estimation and external effects.

## Live application qualification

The Experiment Kernel was reloaded at
`http://localhost:8779/?zone=research&workspace=experiments` and reached
`Ready`. The built-in tutorial opened and closed correctly. The worker surface
displayed `Not implemented`, exposed no queue-action controls, and stated that
prepared experiments stop at the worker boundary. The browser console contained
no errors.

This check did not save, modify, prepare, archive or execute an experiment. It
used existing local records only.

## Compatibility corrections made during qualification

Two historical architecture assertions had become stale without indicating a
product defect:

1. the S4 readiness test expected mandate contracts to be absent even though S5
   now supplies `MandateVersion`; it now verifies the contract while preserving
   portfolio-owner and methodological review gates;
2. the Phase 3 UI test depended on retired labels such as `System assets`; it
   now checks stable experiment controls and the explicit separation of saved
   definitions, data truth, worker boundary and retained artifacts.

No runtime behaviour or safety boundary was relaxed to make these tests pass.

## Human methodology acceptance required before PLATFORM-P7

Automated tests cannot legitimately decide whether the thesis design is valid.
One reviewer-approved candidate must answer every item below before its exact
Registry identities and `fixture_context_digest` are admitted:

| Object | Acceptance question |
|---|---|
| Research question | Are population, unit of analysis, treatment, comparator, estimand and inference scope unambiguous? |
| Hypothesis | Is the direction explicit, falsifiable and linked to one research question? |
| Baseline ladder | Does every comparator have reproducible behaviour and the same permitted resources except for the declared treatment? |
| Information regimes | Are evidence categories, disclosure, missingness and access rights predeclared and fair across arms? |
| Risk outcome | Are horizon, ordered states, breach, mitigation, avoidance, censoring and labelling rules operational? |
| Metrics | Are formula, inputs, aggregation, direction, missingness, uncertainty and decision thresholds fixed before evaluation? |
| Portfolio and mandate | Is the portfolio suitable for the pilot and is the mandate reviewed by its owner? |
| Risk policy | Are threshold precedence, exceptions, escalation and missing-data behaviour complete enough for the pilot? |
| Cases and scenarios | Are synthetic labels reviewed, historical snapshots point-in-time safe and the sealed out-of-sample boundary recorded? |
| Repetition plan | Are experimental unit, allocation, seeds, repetitions, sample-size rationale and stopping rules predeclared? |
| Authority | Is human-only resolution retained for the first pilot, with supra-agent and external effects disabled? |
| Interpretation | Are confirmatory, exploratory and diagnostic findings separated, including multiple-comparison treatment? |

## Acceptance record

Complete this record without editing the candidate definitions:

| Field | Value |
|---|---|
| decision | pending |
| reviewer | pending |
| review date | pending |
| scientific-design Registry identity | pending |
| experiment-object-set Registry identity | pending |
| fixture context digest | pending |
| accepted limitations | pending |
| required next revision | pending |
| rationale/evidence reference | pending |

Approval creates a new acceptance record. Rejection or qualification creates a
next-revision requirement; it does not overwrite the reviewed candidate.

## Development decision

This gate was satisfied on 2026-08-10 by the delegated, calibration-only review
recorded in `docs/thesis/methodology-acceptance-calibration-pilot.md`. The two
top-level identities are validated and the first P7 Fixture Context is retained.
This does not convert calibration evidence into thesis evidence. An experiment
worker, progress checkpoints, automatic
result retention, factor-matrix generation, metric estimation and causal
inference remain later work and are not implied by this qualification.
