# Session 7 Handoff — Matched Architecture Run Compilation

**Contract:** `thesis-risk-episode-case-framework-v1`
**Session:** S07
**State:** implementation complete; real execution remains explicitly gated

## Outcome

Session 7 adds the non-executing bridge from one governed `ExperimentalCase`
to a matched B0/B1/A1 comparison plan.

```text
accepted Gold reference
  -> saved canonical ExperimentalCase
  -> choose capability package, repetitions and identity treatment
  -> compile immutable matched matrix
  -> review projected runs, calls, tokens, time and maximum cost
  -> no execution
```

No fixture Case, automatic Gold record, model response or capability result is
created by this workflow.

## Scientific invariants

The compiler enforces:

1. only a saved Case with an admitted reference can enter a plan;
2. Gold and future evaluation state remain inaccessible to every architecture;
3. every cell receives the same observation IDs and point-in-time information regime;
4. B0, B1 and A1 are all present with exact versioned configurations;
5. architecture, capability package, repetition and identity condition are explicit factors;
6. B0 rejects generative or adaptively parameterised capabilities;
7. every model arm has bounded calls, input tokens, output tokens, cost and processing time;
8. model authorization is recorded but never inferred;
9. plan compilation is idempotent and cannot mutate an existing semantic plan;
10. `execution_status` is always `not_started` in this session.

## Reuse and persistence

The implementation reuses `ExperimentalCase`, `RunInput`, `ArchitectureConfig`,
`ExperimentalCapabilityConfig`, the existing historical-replay capability
definitions and `LocalGoldCaseStore`. The Gold store now exposes safe catalogues
of its governed records and compiled Cases; no parallel Case registry was added.

`LocalMatchedRunPlanStore` retains plans beneath the same external label-production
root with path containment, symlink rejection, immutable writes and idempotent
recompilation. Runtime output and evaluation records remain separate future work.

## User journey

The existing **Experiment Lab → Run comparison** view now contains one compact
planner. It shows only:

- accepted Case;
- evidence/capability package;
- repetitions;
- named or anonymized identity;
- optional future model-call authorization;
- projected B0/B1/A1 resources.

If no accepted Case exists, the page states the exact human gate and disables
compilation. Internal hashes, schemas, provider receipts and raw contracts are
not rendered.

## Real-data status

The current licensed-data state still has no accepted real Gold reference and
therefore no real `ExperimentalCase`. The truthful UI state is **No accepted
Case yet**. Controlled records were used only for software tests.

## Verification

```text
matched-run domain and UI boundary tests     PASS · 10 tests
broad experiment/case-framework suite        PASS · 108 tests
Experiment API and application regression    PASS · 59 tests
Python compilation                           PASS
JavaScript syntax                            PASS
real model/capability execution               NOT RUN
```

## Material files

- `packages/risk_experiments/src/risk_experiments/matched_runs.py`
- `packages/risk_experiments/src/risk_experiments/gold_cases.py`
- `packages/risk_experiments/src/risk_experiments/__init__.py`
- `apps/portfolio-risk-workbench/labs/matched_run_runtime.py`
- `apps/portfolio-risk-workbench/labs/duckdb_server.py`
- `apps/portfolio-risk-workbench/labs/index.html`
- `apps/portfolio-risk-workbench/labs/labs.js`
- `apps/portfolio-risk-workbench/labs/professional.css`
- `tests/experiments/test_matched_runs.py`
- `tests/application/test_matched_run_runtime.py`

## Session 8 boundary

Session 8 may execute the saved plan only after a real accepted Case exists and
the user explicitly authorises model calls. It must freeze simulated time from
trigger through all capability and agent work, retain every cycle's structured
`ArchitectureOutput`, include full processing latency and cost, and keep user-facing
renderings outside evaluation fields.
