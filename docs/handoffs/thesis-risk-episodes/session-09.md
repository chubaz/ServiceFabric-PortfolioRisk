# Session 9 Handoff — Truthful Selected-Case Evaluation

**State:** accepted
**Next:** S10 — Finish comparison, reproducibility, and release gate

## Completed

- Extended the existing `EvaluationRecord` rather than creating a parallel
  evaluation object.
- Added nested `EvaluationMetricResult` records with explicit status, value,
  numerator, denominator, unit, method, references and limitations.
- Made unavailable values structurally safe: an unavailable metric cannot carry
  a numeric result and an unavailable dimension cannot carry a score.
- Added the deterministic `selected-case-evaluator-v1`, joining one retained
  `RunTrajectory` to its accepted `GoldCaseRecord` only after execution.
- Persisted immutable evaluation JSON beneath the existing external research
  repository in `run-evaluations`; no licensed source bytes entered Git.
- Added six runtime-validity checks per Run: terminal state, matched clock,
  point-in-time eligibility, trigger-to-output clock blocking, Gold firewall and
  cycle errors.
- Added a compact post-run comparison API and changed the existing **Compare
  results** page to lead with validity, observed findings, measurement coverage,
  unavailable evidence and shortcomings.
- Kept technical receipts behind one collapsed disclosure. Internal contracts,
  hashes, capability IDs and raw objects are not primary user content.
- Removed unexplained perfect-score presentation. Detection reads `Hit · 1/1`,
  timeliness reads `Same session`, and decision appropriateness reads
  `Accepted · 1/1`; only the evidence composite uses a percentage.

## First retained evaluation

All three matched Runs are valid with limitations and are archivable. All 18
runtime checks passed. Five dimensions are usable and four are explicitly not
measurable for each method.

| Dimension | B0 | B1 | A1 | Interpretation |
|---|---:|---:|---:|---|
| Detection | hit 1/1 | hit 1/1 | hit 1/1 | Selected Case only; no population recall |
| Timeliness | same session | same session | same session | Daily-price unit; real processing reported separately |
| Evidence | 1.00 | 0.67 | 0.67 | B0 kept the reviewed alternative distinct; B1/A1 did not |
| Decision | accepted 1/1 | accepted 1/1 | accepted 1/1 | Ex-ante checkpoint only; no branch regret |
| Efficiency | measured | measured | measured | Raw time/calls/tokens/cost; no arbitrary composite |
| Severity | unavailable | unavailable | unavailable | No economic impact forecast in basis points |
| Confidence | unavailable | unavailable | unavailable | One selected positive Case cannot calibrate |
| Robustness | unavailable | unavailable | unavailable | No matched perturbation retained yet |
| Stability | unavailable | unavailable | unavailable | One repetition retained |

The agent methods used 20 model calls and $0.039558 in total. This one Case
shows no detection-timing gain over B0. It does show a material evidence-role
difference: B0 retained the reviewed positive precursor as conflicting evidence,
while B1 and A1 included it in supporting context. No architecture winner is
declared.

## Files changed in Session 9

- `packages/risk_experiments/src/risk_experiments/hierarchy.py`
- `packages/risk_experiments/src/risk_experiments/evaluations.py`
- `packages/risk_experiments/src/risk_experiments/__init__.py`
- `apps/portfolio-risk-workbench/labs/trajectory_evaluation_runtime.py`
- `apps/portfolio-risk-workbench/labs/duckdb_server.py`
- `apps/portfolio-risk-workbench/labs/index.html`
- `apps/portfolio-risk-workbench/labs/labs.js`
- `apps/portfolio-risk-workbench/labs/styles.css`
- `apps/portfolio-risk-workbench/labs/professional.css`
- `tests/experiments/test_trajectory_evaluations.py`
- `tests/application/test_experiment_api.py`
- `tests/application/test_labs_runtime.py`
- `docs/thesis/experiment-evaluation-framework.md`
- `config/agent/thesis-risk-episodes/ten-session-development-contract.yaml`
- `docs/workplans/current.md`

## Verification

- 163 experiment, Case, Gold, matrix, trajectory and application tests passed.
- JavaScript syntax, Python compilation and `git diff --check` passed.
- The evaluator ran against the actual retained B0/B1/A1 licensed-derived
  trajectories and saved three immutable EvaluationRecords.
- Actual result: 3/3 Runs, `valid_with_limitations`, archivable, 18/18 runtime
  checks passed.
- The application was restarted on port 8776 and the retained comparison was
  reloaded through the live HTTP API and the in-app browser.
- The **Compare results** view was visually verified at a 937 px viewport with
  no horizontal overflow, no browser warnings, distinct validity labels and
  precise sub-dollar model costs (`$0.0109` and `$0.0287`).
- The final API/UI regression pass completed with 31 focused tests; the broader
  Session 9 suite remains at 163 passing tests.

## Session 10 entry conditions

S10 can now focus on the release-quality reproducibility bundle rather than
inventing more evaluation concepts. It should:

1. add at least two identical B1/A1 repetitions and one bounded perturbation so
   stability and robustness become measurable;
2. retain/reload the matrix, trajectories, evaluations and human comparison as
   one reproducibility bundle;
3. prove B0 deterministic rerun identity and Gold leakage prevention;
4. complete one supervisor-facing result and a concise technical diagnostics
   package;
5. run the full planned journey and packaging gate.
