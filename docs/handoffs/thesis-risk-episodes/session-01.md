# Session 1 Handoff — Experimental Foundation

**Contract:** `thesis-risk-episode-case-framework-v1`
**Session:** S01 — Reconcile the experimental foundation
**State:** accepted by continuation to S02

## Completed

- Reconciled the experimental programme around exactly three ordered arms: B0 deterministic, B1 single agent, and A1 agent graph.
- Corrected the application projection expectations from the former two-arm counts to 45 outputs and 90 repeated observations for 15 cases and two repetitions.
- Updated qualification messages so both B1 and A1 must satisfy the common wrapper and the pricing boundary refers to an exact read-only point-in-time snapshot.
- Froze the common language and canonical ownership of signals, candidates, Silver labels, Gold cases, Runs, architecture outputs, and evaluations.
- Froze the initial 2013–2017 proof universe to the 18 reviewed portfolio-linked securities, including the disclosed 16/18 RavenPack linkage boundary.
- Recorded exact external dataset, mapping, provider, portfolio, and integration digests without committing licensed data or local paths.
- Kept the Experiment interface in one page and aligned its existing four tabs to Find cases, Review case, Run comparison, and Compare results.
- Added a compact data-truth line to the existing readiness panel rather than another view or object catalogue.

## Canonical ownership

- Detector definitions, runs, signals, and frozen forecast manifests: `risk_analytics`.
- Candidates, Silver labels, Gold case composition, and label references: `risk_experiments`.
- Primary architecture payload: existing `risk_agents.AgentStructuredOutput`.
- Evaluation projection: existing `risk_experiments.ArchitectureOutput` and `EvaluationRecord`.
- Persistence: existing experiment, artifact, and registry stores.

No new general finding, alert, evidence, decision, provider, run, evaluation, or registry hierarchy was introduced.

## Data boundary

- CRSP/Compustat snapshot: `crsp_compustat_01322048b75d7ac69e858b1e`.
- Portfolio selection: `thesis-real-portfolios-day4-v1`.
- RavenPack: integration version 1.0, portfolio-scoped, 2013–2017, 3,545,638 admitted records, 16/18 securities linked.
- All source bytes remain external, licensed, read-only, and unavailable for publication.
- Retrospective case labels remain separate from point-in-time architecture context.
- Development fixtures and synthetic augmentations cannot be presented as licensed research observations.

## Files changed by S01

- `packages/risk_experiments/src/risk_experiments/experimental_program.py`
- `apps/portfolio-risk-workbench/labs/experimental_program_runtime.py`
- `apps/portfolio-risk-workbench/labs/historical_replay_runtime.py`
- `apps/portfolio-risk-workbench/labs/index.html`
- `apps/portfolio-risk-workbench/labs/labs.js`
- `apps/portfolio-risk-workbench/labs/styles.css`
- `tests/application/test_experimental_program_runtime.py`
- `tests/application/test_labs_runtime.py`
- `tests/experiments/test_case_sampling_manifest.py`
- `docs/thesis/risk-episode-case-framework-language.md`
- `config/agent/thesis-risk-episodes/initial-case-sampling-manifest.yaml`
- `config/agent/thesis-risk-episodes/ten-session-development-contract.yaml`
- `docs/workplans/current.md`
- `docs/handoffs/thesis-risk-episodes/session-01.md`

## Verification

```text
make preflight: PASS
focused S01 tests: PASS · 45 tests
Python compilation: PASS
JavaScript syntax: PASS
YAML validation: PASS · contract and sampling manifest
git diff --check: PASS
live API contract: PASS · B0/B1/A1 · licensed read only · no synthetic additions
live HTML contract: PASS · four actions · no Technical details disclosure
```

## User-interface proof

Route: `?zone=research&workspace=experiments`

Expected result:

- one Experiment page;
- no new top-level studio or object view;
- the four research actions are visible in the existing navigation;
- the readiness panel clearly says licensed/read-only, point-in-time/ex-ante, mandate-rule reference labels, and no synthetic additions;
- advanced programme objects and technical receipts are not rendered in the research interface; they remain in developer outputs and Codex handoffs.

## Unresolved, intentionally deferred

- Detector implementation begins in S02.
- Candidate ranking and interval construction begin in S03.
- Silver/Gold persistence begins in S04.
- RavenPack's committed provider-neutral adapter is hardened in S05.
- Detector-backed case discovery replaces the initial saved-case selector during S06.

## Next-session readiness

S02 may start only after the focused S01 gate passes and the user accepts this handoff.
