# PLATFORM-P3 — experiment workspace and bounded queue

- Status: accepted
- Accepted candidate: `63530a08040f0976e68d310072a27a809943f15d`
- Integration branch: `integration/platform-experiment-workspace`
- Baseline: `5426cacee004817c17215ec8bff3747d5d00c2c2`
- Roadmap: `apps/portfolio-risk-workbench/labs/DEVELOPMENT_ROADMAP.md`
- Verification: `make verify-platform-phase3`

## Outcome

Make an experiment a first-class isolated research workspace without copying or
redefining portfolios, mandates, datasets, agents, workflows, evaluations, or
artifacts. An experiment binds exact canonical references, a temporal and
eligibility boundary, a presentation mode, explicit budgets, and an effect-free
policy. Lifecycle and queue state remain independently reviewable and
restart-safe.

## Visible increment

The Labs application gains an **Experiment Workspace** where a user can:

1. choose interactive foreground, background/headless, or evaluation-only mode;
2. bind a portfolio, snapshot policy, mandate, data revision, and discovered
   workflow or evaluation definition;
3. review the immutable compiled definition and data-truth declaration;
4. validate and mark the experiment ready through explicit receipts;
5. admit it to a bounded local queue without implicitly starting execution;
6. start, pause, resume, complete, fail, or cancel controller state using a
   restart-safe token;
7. group independent experiments into a comparison set.

## Architecture boundary

- `ExperimentDefinition` owns experiment meaning; its canonical digest is
  immutable after creation.
- `ExperimentRecord` owns append-only lifecycle receipts and optimistic
  revisions. It does not modify the definition.
- `QueueEntry` is an operational projection with an idempotency key and resume
  token. It is not evidence that a workflow or model call occurred.
- `ExperimentSet` owns bounded comparison planning; every member remains an
  independent experiment.
- Mutable metadata lives beneath `PORTFOLIO_RISK_EXPERIMENT_ROOT`, outside Git.
- Registered definitions use `risk_registry.RegistryIdentity` directly. Source
  bindings are digest-bound references, not duplicate domain objects.
- Evaluation-only mode compiles only to `evaluate_existing_outputs`; it cannot
  request workflow replay.
- No scheduler daemon, network worker, LLM call, SQL call, artifact promotion,
  portfolio mutation, order, broker, or external effect is introduced.

## Development tasks

### A — contracts and persistence

Implement strict source bindings, immutable definitions and sets, lifecycle
receipts, external atomic storage, optimistic revisions, and idempotency.

### B — bounded execution control

Implement queue admission and restart-safe state control. Keep actual workflow
execution explicitly outside this phase.

### C — application experience

Add creation, review, lifecycle, queue, and set-comparison views while clearly
separating system assets, overlays, run outputs, and promotion.

### D — focused qualification

Run contract, persistence, API, architecture, and browser checks. Defer the next
exhaustive cross-phase clean-room qualification until the three-phase cadence,
unless focused evidence reveals a high-risk boundary defect.

## Exit gates

1. Definitions and sets are strict, immutable, digest-bound, and reference
   existing canonical contracts rather than replacing them.
2. Storage is outside Git, atomic, path-safe, symlink-safe, restart-safe, and
   concurrency guarded.
3. Lifecycle transitions are append-only, optimistic, idempotent, and bounded.
4. Queue admission is explicit, resumable, and visibly distinct from execution.
5. Evaluation-only jobs cannot become workflow replay jobs.
6. Modes, data truth, source bindings, budgets, state, receipts, and queue truth
   are understandable in the application.
7. Experiment sets remain bounded and expose comparison readiness.
8. Focused Phase 3 tests and browser review pass with external effects disabled.

## Non-goals

- no actual agent, workflow, model, capability, SQL, or scheduler execution;
- no report-composer or decision-card lifecycle;
- no simulated portfolio mutation or order ledger;
- no automatic artifact promotion or cleanup;
- no Studio–Codex execution, RavenPack, MCP, or provider integration;
- no Phase 4 work.
