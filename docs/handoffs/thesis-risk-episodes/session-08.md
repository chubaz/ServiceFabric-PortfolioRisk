# Session 8 Handoff — Point-in-Time Risk-Outlook Trajectories

**State:** accepted
**Next:** S09 — Complete truthful evaluation

## Completed

- Reused the accepted licensed ADX Case and one sealed matched matrix for B0,
  B1 and A1.
- Released all 16 observations chronologically under
  `available_at <= replay_at`; the Gold reference remained inaccessible.
- Produced a valid `ArchitectureOutput`, explicit abstention or explicit error
  at every workflow cycle.
- Retained simulated-time freeze and real-processing-time receipts across the
  entire capability, model, validation and mapping path.
- Reused the existing agent execution wrappers and deterministic mapper.
- Retained A1's four node contributions, handoffs, finding disagreement,
  confidence/severity dispersion, synthesis time and coordination overhead in
  `ArchitectureOutput.architecture_behavior`.
- Added a human-readable trajectory projection with incoming evidence types,
  outlook, confidence, hypothetical monitoring decision, capability/model
  calls, processing time and graph diagnostics.
- Added first-warning, first-actionable, first-alert, first-high-confidence,
  active-streak and confidence-decay projections without treating these
  presentation values as evaluation scores.
- Admitted one immutable Markdown presentation artifact per Run to the existing
  external Artifact Repository. All three are `licensed_real`,
  `licensed_restricted`, publication-restricted and explicitly
  `excluded_from_evaluation`.
- Proved event-time, intraday and daily-close triggers remain chronological and
  simulated time stays frozen while real wall-clock processing advances.
- Kept the research UI compact: the existing Run comparison shows three result
  cards and loads one expandable timeline only on request.

## First retained comparison

| Architecture | Cycles with output | Abstentions | Model calls | Tokens in / out | Cost | Highest state |
|---|---:|---:|---:|---:|---:|---|
| B0 deterministic | 16 | 0 | 0 | 0 / 0 | $0 | alert |
| B1 single agent | 4 | 12 | 4 | 23,181 / 5,219 | $0.010899 | watch |
| A1 agent graph | 4 | 12 | 16 | 70,153 / 12,190 | $0.028659 | watch |

No paid calls were made during Session 8 closure. The existing B1/A1
trajectories were retrieved idempotently while presentation artifacts were
admitted.

The apparatus exposes meaningful disagreement rather than a trivial perfect
result. B0 reached an alert at the market manifestation. B1 and A1 remained at
watch. B1 retained a usable narrative in one of four active cycles and had
three critic abstentions; A1 retained three and had one. All A1 active cycles
show specialist finding disagreement of 1.0 because the specialist nodes
produced non-overlapping finding clusters. Session 9 must interpret that value
carefully: specialization disagreement is not automatically an error.

## Safety and data boundary

- User authority covered bounded transmission of derived licensed context to
  OpenAI for B1/A1.
- Raw licensed RavenPack text was never supplied to the model or stored in Git.
- Gold labels and retrospective selection state were not supplied.
- No web, broker, order, hedge, rebalance or portfolio-mutation effect existed.
- Presentation artifacts are renderings; structured trajectory records and
  receipts remain the future evaluation source.

## Files changed in the closure slice

- `packages/risk_experiments/src/risk_experiments/trajectories.py`
- `apps/portfolio-risk-workbench/labs/trajectory_execution_runtime.py`
- `apps/portfolio-risk-workbench/labs/duckdb_server.py`
- `apps/portfolio-risk-workbench/labs/labs.js`
- `apps/portfolio-risk-workbench/labs/professional.css`
- `tests/experiments/test_trajectories.py`
- `tests/application/test_trajectory_execution_runtime.py`
- `tests/application/test_matched_run_runtime.py`
- `config/agent/thesis-risk-episodes/ten-session-development-contract.yaml`
- `docs/workplans/current.md`

## Verification

- 177 focused detector, data, capability, Case, Gold, matched-run, execution
  kernel, trajectory, application, Registry and Day 3 treatment tests passed.
- JavaScript syntax, Python compilation and `git diff --check` passed.
- Live localhost APIs returned three retained Runs, three active governed
  presentation artifacts and a 16-cycle A1 timeline.
- Every A1 active-cycle receipt reported frozen simulated time and positive real
  processing latency.
- The local browser automation surface blocked localhost navigation under its
  URL policy, so final visual inspection remains a manual page reload; API and
  UI contract qualification succeeded.

## Session 9 entry conditions

The detection and severity methodology files exist and the first Gold-backed
matched set is retained. S09 should now:

1. compile versioned evaluation records from trajectory data and declared Gold
   references;
2. return `not_evaluable` whenever a denominator or required label is absent;
3. separate policy urgency from economic severity;
4. separate decision appropriateness from realised branch outcome;
5. expose run validity, limitations and principal shortcomings before scores;
6. make no new model call merely to calculate deterministic evaluation metrics.
