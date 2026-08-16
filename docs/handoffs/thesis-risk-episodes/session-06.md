# Session 6 Handoff — Governed Gold References and Experimental Cases

**Contract:** `thesis-risk-episode-case-framework-v1`
**Session:** S06
**State:** implementation complete; real reference production remains human-gated

## Outcome

Session 6 adds the selective bridge between reviewed retrospective work and the
existing experiment hierarchy.

```text
accepted label review
  + accepted evidence review
  + explicit planned experiment selection
  -> immutable Gold reference draft
  -> different human Gold reviewer
  -> accepted retrospective reference
  -> existing ExperimentalCase
       observable_state  = replay-eligible evidence only
       evaluation_state  = admitted Gold reference, architecture_access=false
```

The implementation does not create another Case type. `GoldCaseBundle` is a
research-only reference payload. `ExperimentalCase` remains the canonical Case
used by replay and evaluation.

## Scientific gates

Gold preparation fails unless all of the following are true:

1. the exact signal label has an accepted independent review;
2. the exact context execution has an accepted human evidence review;
3. at least one evidence candidate was explicitly retained;
4. a researcher names the planned Study, Experiment and research use;
5. a decision checkpoint and acceptable action set are declared;
6. the preparation identity is different from the Gold reviewer;
7. the Gold reviewer reconciles label, evidence, temporal isolation and limits;
8. at least one retained evidence item was available ex ante before compiling a
   replayable Experimental Case.

No broad Gold production, automatic approval, causal narrative generation or
market-wide case construction is present.

## Gold reference contract

The immutable reference binds exact retained content:

- label and label-review identities;
- context execution and evidence-review identities;
- manifestation interval, direction, morphology and observed severity;
- retained evidence with supporting, contradicting, alternative or unresolved
  position;
- ex-ante versus retrospective-only visibility;
- explicit provider/data-quality limitations;
- decision checkpoints and acceptable action sets;
- data truth (`licensed_historical`, `public_historical`,
  `reviewed_synthetic`, or `mixed`);
- planned Study and Experiment.

The user interface does not render hashes, schema names, query receipts,
provider revisions or internal record IDs. Those remain in the external local
record for Codex and reproducibility work.

## Architecture firewall

Compilation uses the existing `ExperimentalCase` split:

```text
observable_state
  portfolio / mandate / risk policy references
  data references
  replay-eligible observation IDs
  ex-ante as-of time

evaluation_state
  admitted Gold-reference ID
  outcome observations
  evaluation horizon
  architecture_access = false
```

`RunInput` is unchanged and contains no Gold, manifestation, severity or future
outcome fields. A domain test serializes the observable state and verifies that
those retrospective fields are absent.

## Persistence

`LocalGoldCaseStore` provides:

- content-addressed, idempotent Gold draft creation;
- append-only independent reviews with optimistic concurrency;
- immutable review supersession;
- one persisted canonical `ExperimentalCase` bound to the accepted reference;
- symlink and path-containment checks;
- storage outside Git under the existing label-production root.

Licensed source bytes are not copied into the repository.

## User journey

The work remains inside **Experiment Lab → Review case**.

Each selected move shows one compact **Experimental reference** state:

- **Not ready:** plain-language missing scientific checks;
- **Ready to prepare:** planned experiment and checkpoint form;
- **Independent review:** four required reconciliation checks;
- **Accepted:** one action to create the Experimental Case;
- **Ready:** compact confirmation that observable evidence and hidden truth are
  separated.

Only one primary action appears at each state. There is no new top-level page,
object catalogue or developer-record panel.

## Licensed-history status

The existing ADX proposal remains unchanged:

```text
label review       not accepted
evidence review    not accepted
Gold reference     not created
Experimental Case not created
```

The live interface correctly displays both blockers. This is a scientific
gate, not an implementation defect. Controlled reviewed records were used only
to test the complete software lifecycle.

## Additional defect fixed

The bounded DuckDB query previously depended implicitly on the optional
`pytz` adapter when fetching timezone-aware timestamps. It now returns ISO
timestamp strings and validates them explicitly. This removes an undeclared
runtime dependency without weakening temporal checks.

## Verification

```text
Gold lifecycle domain tests                PASS
context/data/application focused suite     PASS · 36 tests
broad experiment and case-framework suite PASS · 109 tests
Python compilation                         PASS
JavaScript syntax                          PASS
live licensed-data gate                    PASS
rendered desktop workflow                  PASS
real Gold creation                         NOT RUN · human gate preserved
```

## Material files

- `packages/risk_experiments/src/risk_experiments/gold_cases.py`
- `packages/risk_experiments/src/risk_experiments/__init__.py`
- `packages/risk_data/src/risk_data/context_inputs.py`
- `apps/portfolio-risk-workbench/labs/gold_case_runtime.py`
- `apps/portfolio-risk-workbench/labs/duckdb_server.py`
- `apps/portfolio-risk-workbench/labs/labs.js`
- `apps/portfolio-risk-workbench/labs/professional.css`
- `apps/portfolio-risk-workbench/labs/index.html`
- `tests/experiments/test_gold_cases.py`
- `tests/application/test_case_labelling_runtime.py`
- `tests/application/test_labs_runtime.py`

## Direction to completion

Session 7 can compile the matched B0/B1/A1 run matrix after one real reference
passes the four human decisions above. Its implementation should:

1. accept only saved `ExperimentalCase` identities;
2. seal one architecture-neutral observable input;
3. keep architecture and capability package as separate factors;
4. reject generative or adaptive capabilities from B0;
5. show cost, repetition, budget and information conditions before execution;
6. never expose the Gold packet to any architecture process.
