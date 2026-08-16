# Session 5B Handoff — Dormant Context Work Planner

**Contract:** `thesis-risk-episode-case-framework-v1`
**Session:** S05B — Design dormant context work
**State:** completed locally; retrieval and association execution deferred

## Outcome

The system now supports the complete design lifecycle for later evidence work
without performing that work.

```text
selected review item
  -> choose purpose and sources
  -> bound event/fundamental windows
  -> require competing evidence
  -> specify optional controls
  -> check source blockers and limitations
  -> save immutable plan revision
  -> reload or revise
  -> stop
```

Every retained plan proves:

```text
execution_status          not_started
retrieval_count           0
association_count         0
controls_generated_count  0
label_modified            false
gold_case_created         false
```

## Canonical design

The new `ContextWorkPlan` is separate from `LabellingBatch`, annotations,
Gold references and experimental Cases. It binds to one exact batch and review
unit and contains:

- a plain-language purpose;
- selected event and/or fundamental channels;
- bounded event lookback/follow-through and fundamental history;
- exact canonical-identifier matching;
- point-in-time `available_at <= replay_time` eligibility;
- ranked features for later entity/time/relevance/novelty/taxonomy/intensity work;
- a no-causal-claim policy;
- required supporting, contradicting, alternative, unresolved and quality-limit outputs;
- optional control specifications that remain ungenerated;
- source-readiness blockers and non-blocking coverage limitations.

`ContextEvidenceCandidate` and `ContextAssociationProposal` define the future
typed output boundary. No current runtime constructs either object. Candidates
will be provider-neutral, temporally explicit, proposal-only and human-reviewed.

## Lifecycle and persistence

Plans use a dedicated local append-only store under label production. Revisions
are contiguous, bind to one review unit, retain supersession, reject stale
updates and use atomic file replacement. The store contains specifications only;
it never stores provider rows or event text.

The UI and API omit plan IDs, digests, provider revisions and storage paths.
Those remain available to developers and coding assistants in the retained
machine-readable record.

## User experience

No page or navigation item was added. A compact, collapsible **Context work**
panel appears inside the selected item in **Review case**. It supports:

- three purposes;
- event/fundamental source selection;
- bounded history fields;
- competing-evidence requirement;
- four initial optional control specifications;
- **Check plan** without persistence;
- **Save plan / Save revision**;
- clear blockers versus limitations;
- explicit retrieved/associated/generated counts.

## Real-history qualification

A revision-1 plan was saved for the retained 24 August 2015 ADX downside move:

```text
purpose              test competing explanations
sources              RavenPack + Compustat
event window         30 days before / 10 days after
fundamental history  8 quarters
controls specified   ambiguous event / no-material-event period
execution            not started
retrieved             0
associated            0
controls generated    0
```

The system correctly retained two blockers:

- RavenPack amendment/retraction/supersession semantics are not mapped;
- eight Compustat rows lack qualified availability time.

It separately retained portfolio coverage and retrospective-cutoff limitations.
The plan reloaded with the same settings and zero execution counts. A second
Microsoft event-only design was validated without being saved or executed.

## Verification

```text
context contract/store gate                 PASS · 4 tests
focused context/data/application gate       PASS · 30 tests
broader label/application/API gate          PASS · 70 tests
repository preflight                        PASS
Python compilation                          PASS
JavaScript syntax                           PASS
real-history validate/save/reload            PASS
browser plan check                           PASS
```

## Material files

- `packages/risk_experiments/src/risk_experiments/context_work.py`
- `packages/risk_experiments/src/risk_experiments/__init__.py`
- `apps/portfolio-risk-workbench/labs/case_labelling_runtime.py`
- `apps/portfolio-risk-workbench/labs/duckdb_server.py`
- `apps/portfolio-risk-workbench/labs/labs.js`
- `apps/portfolio-risk-workbench/labs/professional.css`
- `tests/experiments/test_context_work.py`
- `tests/application/test_case_labelling_runtime.py`
- `tests/application/test_labs_runtime.py`

## Deferred boundary

The large-scale association, control-generation and experiment integration
strategy remains deferred. The next execution slice requires explicit user
authority plus resolution or acceptance of the recorded blockers. It must start
from these saved plans rather than improvising an unbounded query.
