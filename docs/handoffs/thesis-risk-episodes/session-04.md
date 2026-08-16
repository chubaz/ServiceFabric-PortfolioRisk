# Session 4 Handoff — Retrospective Label Study

**Contract:** `thesis-risk-episode-case-framework-v1`
**Session:** S04 — Enrich labels with intervals and candidate evidence
**State:** completed locally; awaiting user acceptance before S05

## Outcome

Session 4 makes one selected detector move genuinely investigable before a
human labels it. It does not create Silver or Gold cases, experimental Cases,
findings, alerts or causal narratives.

```text
selected review unit
  -> fixed read-only CRSP path
  -> deterministic study calculations
  -> immutable proposal revision
  -> reviewer chooses, edits or ignores
  -> unsaved annotation form
  -> explicit save remains separate
```

The study runs only on demand for a selected review unit. Broad discovery
therefore remains inexpensive and detailed work is concentrated where the
researcher is actually considering a reference label.

## Implemented calculations

The retrospective study contains:

- an indexed real-price path around the selected move;
- a bounded deterministic mean/variance split check near the signal;
- punctual, drawdown, slow-deterioration and regime-transition interval
  proposals;
- high-water/low-water onset, adverse peak, recovery hysteresis and explicit
  censoring;
- 1-, 5- and 20-session terminal returns;
- maximum adverse excursion within each declared horizon;
- maximum adverse excursion over the retained path;
- same-direction portfolio breadth at the signal date;
- pre/post average pairwise correlation and its change;
- missingness/insufficient-history flags;
- a typed association boundary reserved for later work.

The subsequent S05 boundary removed automatic association execution from the
runtime. The typed edge contract remains dormant for future, separately
authorised work. No current label study links signals or names an economic cause.

## Proposal and label firewall

`LabelStudyProposal` is immutable, content-addressed, retrospective-only and
always has `annotation_status=proposal_only` and `gold_case_created=false`.
The labelling batch retains proposal revisions append-only. Recalculation after
an admitted method correction creates a new proposal identity; it does not
rewrite the earlier calculation.

The interface projects no proposal IDs, hashes, receipts, evidence identifiers,
storage paths or schemas. Selecting an interval only copies its dates,
morphology and severity observation into the browser's unsaved form. The item
remains **To label** until the researcher explicitly saves an annotation.

Reference records remain outside all ex-ante architecture input contracts.

## Persistence and compatibility

The fixed data adapter accepts only dataset identity, a positive PERMNO set and
bounded dates. It executes a committed query against the read-only local
DuckDB catalogue. Rows reconcile to missing-return counts and are bounded by a
declared retrospective cutoff.

Session 3 batches remain loadable. Their empty pre-study digest is accepted as
a one-way legacy representation, upgraded in memory, and replaced with the
current digest at the next atomic write without changing annotations or
reviews.

## User experience

The existing **Review case** stage now shows, for a studied item:

- one compact indexed path;
- readable 1/5/20-session outcome cards;
- portfolio breadth, correlation change and worst adverse path;
- alternative interval interpretations as direct choice buttons;
- an explicit “Suggestion only” boundary;
- the existing annotation and independent-review forms below.

There is no new page, registry category or technical drawer. The workflow
remains:

```text
Find cases -> Review case -> Run comparison -> Compare results
```

## Licensed-data proof

The retained 2015 diversified-portfolio sample reopened after migration and
the system studied the 24 August 2015 ADX downside move:

```text
path                    2015-07-10 to 2015-10-08
selected daily return   -5.45%
change-point support    0.77 · supported
1-session excursion     63.1 bps
5-session excursion     63.1 bps
20-session excursion    63.1 bps
full-path excursion     126.3 bps
portfolio breadth       100.0% · 7/7 observed securities
average correlation     0.61 -> 0.52
```

Four interval alternatives were rendered. Choosing the drawdown interpretation
prefilled start `2015-07-31`, peak `2015-08-25`, unresolved/censored state and
the 20-session adverse excursion. The persisted item remained unlabelled and
no Gold or experimental Case was created.

## Verification

```text
focused cross-package gate       PASS · 236 tests
study-label contract gate        PASS · 20 tests
repository preflight             PASS
Python compilation               PASS
JavaScript syntax                PASS
legacy batch migration           PASS
licensed DuckDB study API        PASS
live browser interaction         PASS
visual layout inspection         PASS
```

Tests cover deterministic paths, upside/downside and censored cases,
change-point output, declared severity horizons, group breadth/correlation,
non-causal associations, retrospective cutoffs, fixed-query bounds and
reconciliation, digest tampering, proposal idempotency/revisions, proposal-to-
annotation isolation, legacy batch compatibility, payload redaction, API
delegation and the no-Gold UI boundary.

## Material files

- `packages/risk_analytics/src/risk_analytics/label_study.py`
- `packages/risk_data/src/risk_data/label_study_inputs.py`
- `packages/risk_experiments/src/risk_experiments/labelling.py`
- `apps/portfolio-risk-workbench/labs/case_labelling_runtime.py`
- `apps/portfolio-risk-workbench/labs/duckdb_server.py`
- `apps/portfolio-risk-workbench/labs/labs.js`
- `apps/portfolio-risk-workbench/labs/styles.css`
- `tests/analytics/test_label_study.py`
- `tests/data/test_label_study_inputs.py`
- `tests/experiments/test_labelling.py`
- `tests/application/test_case_labelling_runtime.py`
- `tests/application/test_labs_runtime.py`

## Next-session boundary

S05 qualifies RavenPack and Compustat source readiness only. Retrieval,
association, alternatives and synthetic controls require a separate explicit
authorisation before Gold preparation can be considered.
