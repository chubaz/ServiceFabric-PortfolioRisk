# Session 5 Handoff — Context Source Readiness

**Contract:** `thesis-risk-episode-case-framework-v1`
**Session:** S05 — Qualify event and fundamental context sources
**State:** completed locally; association execution is not authorised

## Outcome

The system is ready to begin selected context work later, but it has performed
none of that work now.

```text
saved review sample
  -> fixed read-only source profile
  -> schema, rights, coverage and time checks
  -> ordered preparation plan
  -> stop

event retrieval         not run
fundamental retrieval   not run
signal association      not run
event association       not run
synthetic controls      not run
Gold preparation        not run
```

## Systematic boundary

`ContextSourceReadiness` is a typed, content-addressed result. It records the
selected period and portfolio, retrospective cutoff, source qualifications,
ordered dependencies, and an invariant `association_execution=not_authorized`
with `association_count=0`.

The fixed DuckDB query returns only counts, schema presence, coverage and time
integrity. It does not return event text, event identities, fundamental values,
rankings or proposed relationships. Licensed data remains local and read-only.

The preparation plan makes later sequencing explicit:

1. qualify source contracts;
2. qualify point-in-time fields;
3. qualify entity coverage;
4. retrieve bounded context — deferred;
5. propose associations — deferred;
6. prepare controls and counter-evidence — deferred.

Missing amendment, retraction and supersession semantics are reported as a
provider-mapping limitation. They are not guessed from RavenPack fields.

## Correction to Session 4

The label-study runtime no longer creates same-security or synchronized-market
association edges. It always passes an empty association set. The analytics
contract remains available as a dormant boundary for a later authorised slice,
but no current runtime uses it.

## Interface

The existing **Review case** view gains one compact **Check sources** action.
Its result shows RavenPack and Compustat coverage, eligible row counts, and an
explicit **Associations — Not started · 0 created** state. No new page, object
catalogue, schema panel or evidence table was added.

## Licensed-data proof

The retained diversified 2015 review sample was profiled against the live local
catalogue:

```text
RavenPack       partial · 6/8 securities · 521,628 eligible rows
Compustat       partial · 7/8 securities · 16/28 rows eligible by cutoff
Associations    not started · 0 created
```

The system correctly stopped at `not_ready`: eight Compustat rows lack a
qualified availability timestamp and the current RavenPack integration has no
explicit amendment/retraction/supersession mapping. These are preparation
blockers, not failed associations, because association was never attempted.

## Verification

```text
focused analytics/data/experiment/application gate   PASS · 64 tests
Python compilation                                    PASS
JavaScript syntax                                     PASS
licensed read-only readiness API                      PASS
automatic signal association absence                 PASS
Gold/Case creation absence                            PASS
```

Material files:

- `packages/risk_data/src/risk_data/context_readiness.py`
- `apps/portfolio-risk-workbench/labs/case_labelling_runtime.py`
- `apps/portfolio-risk-workbench/labs/duckdb_server.py`
- `apps/portfolio-risk-workbench/labs/index.html`
- `apps/portfolio-risk-workbench/labs/labs.js`
- `apps/portfolio-risk-workbench/labs/professional.css`
- `tests/data/test_context_readiness.py`
- `tests/application/test_case_labelling_runtime.py`

## Next boundary

Context retrieval and association are a distinct sub-slice and require explicit
user authorisation. S06 Gold preparation cannot begin until that work has been
authorised, implemented, reviewed and accepted.
