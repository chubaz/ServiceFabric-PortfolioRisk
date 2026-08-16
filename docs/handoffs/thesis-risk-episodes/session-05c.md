# Session 5C Handoff — Selected Context Preparation and Review

**Contract:** `thesis-risk-episode-case-framework-v1`
**Session:** S05 association execution
**State:** implementation complete; one licensed-history proposal awaits human review

## Outcome

The saved Context Work Plan is now executable for one explicitly selected
review item. Execution remains bounded, read-only and proposal-only.

```text
saved plan revision
  -> exact security mapping
  -> fixed event/fundamental queries
  -> exclude unqualified time records
  -> prepare provider-neutral candidates
  -> separate replay-eligible / retrospective-only
  -> human retain / reject / request more work
  -> stop before label or Gold
```

The user remains in **Review case**. No page or top-level object catalogue was
added.

## What was built

### Bounded data preparation

`query_selected_case_context` reads only:

- one exact portfolio security;
- one saved event window;
- one saved fundamental lookback;
- rows with qualified `available_at`;
- rows available by the retrospective cutoff;
- date-effective Compustat links.

Rows with missing availability, invalid time ordering or availability after the
cutoff are counted and excluded. Availability is never inferred.

RavenPack amendments, retractions and supersession remain unavailable in the
current linked view. The system therefore marks every event candidate
`provider_lifecycle_unverified`; it does not treat this provider limitation as
causal or reference truth.

### Proposal boundary

The preparation kernel produces immutable `ContextEvidenceCandidate` records
inside one `ContextAssociationProposal`. The deterministic score is a review
ordering aid based only on exact entity match, temporal distance, provider
relevance and novelty. It is not rendered as a probability and does not choose
the evidential role.

Every candidate begins as:

```text
role      unresolved
position  unresolved
status    needs human review
```

The reviewer may retain, reject or request more work and assign a role and
position. An accepted context requires at least one retained candidate and an
explicit acknowledgement of limitations.

### Persistence and firewall

Preparation results are immutable and idempotent per exact plan revision.
Human reviews are append-only and use optimistic concurrency. Technical
receipts and provider revisions remain in the local machine-readable record,
not in the research interface.

At every state:

```text
label_modified            false
gold_case_created         false
controls_generated_count  0
```

## Licensed-history qualification

The revised ADX plan for 24 August 2015 was prepared from local licensed
history:

```text
bounded candidates       18
replay-eligible          15
retrospective-only        3
missing-time exclusions   8
invalid-time exclusions   0
after-cutoff exclusions   0
synthetic controls        0
label changes             0
Gold/Case creation        0
```

The candidate set contains RavenPack event material. Compustat rows for this
specific security were not admitted because their availability time was
unqualified. The proposal is retained as **Awaiting review**; no evidential role
was accepted on the user's behalf.

## User workflow

Inside the selected review item:

1. Save or revise the evidence plan.
2. Select **Prepare evidence**.
3. Review the replay-eligible and retrospective-only counts.
4. Expand excluded-row limitations when needed.
5. For every candidate choose **Retain**, **Reject** or **Needs review**.
6. Assign an evidential role and position only when justified.
7. Acknowledge the limitations and save the review.

Candidate IDs, query receipts, provider revisions and storage paths are not
shown to the researcher.

## Verification

```text
focused context/data/application gate  PASS · 36 tests
broader case-framework gate             PASS · 96 tests
repository preflight                    PASS
Python compilation                      PASS
JavaScript syntax                       PASS
licensed-history preparation            PASS
live browser workflow                   PASS
browser warnings/errors                 0
```

## Material files

- `packages/risk_data/src/risk_data/context_inputs.py`
- `packages/risk_data/src/risk_data/__init__.py`
- `packages/risk_experiments/src/risk_experiments/context_work.py`
- `packages/risk_experiments/src/risk_experiments/__init__.py`
- `apps/portfolio-risk-workbench/labs/case_labelling_runtime.py`
- `apps/portfolio-risk-workbench/labs/duckdb_server.py`
- `apps/portfolio-risk-workbench/labs/labs.js`
- `apps/portfolio-risk-workbench/labs/professional.css`
- `tests/data/test_context_inputs.py`
- `tests/experiments/test_context_work.py`
- `tests/application/test_case_labelling_runtime.py`
- `tests/application/test_labs_runtime.py`

## Direction to completion

The remaining contract now has four coherent steps:

1. **Human context review, then Session 6:** accept one bounded evidence set and
   use only independently reviewed labels selected for an imminent experiment
   to prepare Gold references and saved experimental Cases.
2. **Session 7:** compile a matched B0/B1/A1 matrix with exact capability,
   budget, repeat and anonymisation conditions visible before execution.
3. **Sessions 8–9:** execute point-in-time ArchitectureOutput trajectories and
   compute truthful evaluation records, including explicit not-evaluable states.
4. **Session 10:** save, reload, reproduce and present one complete comparison.

Session 6 must not begin Gold preparation for the ADX item until its evidence
candidates and label have both received the required human review. Large-scale
association, automatic control generation and market-wide case production
remain deferred.
