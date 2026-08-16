# Session 3 Handoff — Selective Label Production

**Contract:** `thesis-risk-episode-case-framework-v1`
**Session:** S03 — Build selective label production
**State:** completed locally; awaiting user acceptance before S04

## Outcome

Session 3 implements the labelling production system that sits between broad
statistical detection and selective Gold preparation. It does not produce a
Gold case, Silver case corpus, or experimental Case.

The working path is:

```text
all admitted detector signals
  -> duplicate detector hits grouped into one review unit
  -> deterministic stratified sample
  -> immutable annotation revision
  -> independent review
  -> reference-ready eligibility
  -> stop
```

`reference-ready` means that a label may later be selected for an expensive
Gold-preparation workflow immediately before an experiment is compiled. It is
not Gold acceptance and it creates no Case.

## Scientific design

The versioned labelling protocol covers ten field families:

1. manifestation outcome;
2. instrument relevance;
3. defensible scope;
4. direction;
5. temporal morphology;
6. manifestation interval;
7. severity;
8. supporting and conflicting evidence;
9. data quality;
10. retrospective label confidence.

These fields support detection quality, severity understanding, timeliness,
evidence quality, and confidence/calibration. Decision quality requires a
separate checkpoint reference. Robustness, stability, and efficiency come from
experimental perturbations and runtime behaviour. The labelling system does
not fabricate those dimensions.

The protocol maps its fields to the existing `ArchitectureOutput` evaluation
surface without changing `ArchitectureOutput`. In particular:

- outcome can be compared with assessment state;
- reviewed severity can be compared with output severity;
- scope and direction can be compared with structured findings;
- retained evidence can be compared with finding citations;
- manifestation and availability times support detection and timeliness;
- reference confidence supports later calibration analysis;
- `case_id` remains absent until a separately governed Gold reference is bound
  to an experimental Case.

## Efficient sampling

The system first groups signals that share the same scope, date, and direction.
This retains every detector's support while preventing the same market move
from being labelled twice merely because two methods crossed a threshold.

It then rotates deterministically across:

- upside and downside;
- boundary, elevated, and extreme scores;
- single-detector and multi-detector support.

Only after each represented stratum receives an opportunity does the sampler
fill remaining capacity. The plan records all selected and excluded review
units, the exact source detector outputs, period, portfolio, dataset revision,
seed, and protocol version. Input order does not change the sample.

## Annotation and review lifecycle

- Every saved annotation is immutable.
- Corrections create a new revision that names the exact revision superseded.
- Materialised risk requires an interval, positive severity, evidence, and a
  resolved morphology.
- A non-material move requires severity zero and no manifestation interval.
- A data-quality error requires an explicit quality flag and data-artifact
  morphology.
- Ambiguous labels may remain incomplete and therefore cannot silently become
  reference truth.
- An independent review checks detection/scope, severity, evidence, and timing.
- The annotator cannot review their own annotation.
- Acceptance requires all four checks and sufficient reviewer confidence.
- A reviewer can request changes or exclude an item.
- A requested change returns the item to an immutable next annotation revision.

No lifecycle operation creates Gold.

## Persistence and safety

`LocalLabellingStore` provides:

- restart-safe local batches;
- atomic writes and directory fsync;
- symlink and path-containment checks;
- optimistic revision checks;
- idempotent creation, annotation, and review requests;
- append-only annotation, review, and event history;
- exact reconciliation between selected units, annotations, reviews, and
  source detector outputs.

Licensed data remains read-only and outside Git. The persisted batches contain
derived references and labels, not copied CRSP rows. The evaluated architecture
cannot access the label store through its experimental input contract.

## User experience

Route: `?zone=research&workspace=experiments`

The workflow uses the existing four-stage page:

```text
Find cases -> Review case -> Run comparison -> Compare results
```

In **Find cases**, **Prepare review sample** appears only after a successful
scan. It creates or reopens the same reproducible sample and moves to **Review
case**.

The Review case stage contains:

- a saved-sample selector;
- progress counts for selected, unlabelled, awaiting review, and ready items;
- a compact list of named companies and dates;
- one clear annotation form;
- an independent-review form only after an annotation exists;
- an explicit explanation that no Gold or experimental Case was created.

Technical schemas, hashes, evidence identifiers, detector run IDs, receipts,
cache records, and storage paths do not appear in the interface. They remain
available in persisted machine records and Codex handoffs.

## Real-data proof

The live system executed two reproducible licensed-data batches:

```text
diversified portfolio · 2015-08-01 to 2015-10-31
12 detector signals -> 9 review units -> 9 selected

diversified portfolio · 2015-01-01 to 2015-12-31
22 detector signals -> 17 review units -> 12 selected
```

The one-year sample includes upside and downside moves, boundary/elevated/
extreme bands, and single-/multi-detector support across named securities such
as Microsoft, Oracle, Honeywell, T. Rowe Price, and Adams Diversified Equity
Fund.

The browser successfully loaded the retained one-year sample and all twelve
annotation forms. Browser error/warning log: empty. No live annotation was
invented during software verification.

## Verification

```text
full focused S03 gate: PASS · 251 tests
new label-contract/runtime tests: PASS · 11
Python compilation: PASS
JavaScript syntax: PASS
real licensed-data batch API: PASS
idempotent batch reload: PASS
live browser journey: PASS
browser console warnings/errors: 0
```

The tests cover protocol completeness, ArchitectureOutput alignment,
de-duplication, deterministic sampling, time-window filtering, material/
non-material/ambiguous/data-quality semantics, immutable revisions, restart
safety, stale-write rejection, idempotent retries, self-review rejection,
changes-requested workflow, user-payload redaction, API routing, and the
no-Gold UI boundary.

## Files added or materially changed by S03

- `packages/risk_experiments/src/risk_experiments/labelling.py`
- `packages/risk_experiments/src/risk_experiments/__init__.py`
- `packages/risk_experiments/pyproject.toml`
- `apps/portfolio-risk-workbench/labs/case_discovery_runtime.py`
- `apps/portfolio-risk-workbench/labs/case_labelling_runtime.py`
- `apps/portfolio-risk-workbench/labs/duckdb_server.py`
- `apps/portfolio-risk-workbench/labs/index.html`
- `apps/portfolio-risk-workbench/labs/labs.js`
- `apps/portfolio-risk-workbench/labs/styles.css`
- `tests/experiments/test_labelling.py`
- `tests/application/test_case_labelling_runtime.py`
- `tests/application/test_labs_runtime.py`
- `docs/thesis/evaluation-plan/detection-quality/README.md`
- `docs/thesis/risk-episode-case-framework-language.md`
- `config/agent/thesis-risk-episodes/ten-session-development-contract.yaml`
- `docs/workplans/current.md`

## Next-session boundary

S04 will improve what the labeller can study, not create Gold cases. It will
add reproducible interval and severity proposals, change-point and group-level
context, and explicit candidate association edges. Automated proposals remain
separate from accepted annotation revisions and cannot establish truth.

Gold preparation is now scheduled only after event/fundamental enrichment and
only for reference-ready labels selected for an imminent experiment.
