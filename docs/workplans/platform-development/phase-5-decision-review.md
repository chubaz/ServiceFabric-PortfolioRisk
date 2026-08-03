# PLATFORM-P5 — Decision Review v1

- Status: accepted
- Accepted candidate: `57e6a397231c8a1327fba4c6856edd2373f45e80`
- Integration branch: `integration/platform-decision-review`
- Baseline: `8ec4ed5501d5a322439237be4207068c96347fca`
- Roadmap: `apps/portfolio-risk-workbench/labs/DEVELOPMENT_ROADMAP.md`
- Verification: `make verify-platform-phase5`
- Cross-phase checkpoint: `make verify-platform-phase5-cross-phase`

## Outcome

Turn the existing synthetic-cycle pause into a strict, restart-safe human
decision lifecycle. Keep Finding, Decision Proposal, human resolution and any
later action visibly separate. Every reviewer choice must have a readable
consequence preview and an immutable receipt; none may create a portfolio or
external effect.

## Visible increment

1. The Workflow Cycle pauses on a material proposal and exposes five outcomes:
   Investigate, Accept & monitor, Defer, Reject and Escalate.
2. A concise Decision Review page leads with the question, why it exists now,
   recommendation, relevance, consequences, evidence and uncertainty.
3. The reviewer supplies an identity and rationale; stale concurrent reviews
   fail closed and retries are idempotent.
4. Investigate runs the one registered
   `decision.investigate.effect-free.v1` follow-up, creates a supplemental
   context revision, and returns the immutable proposal to review.
5. Accept and Reject permit only a later, separate manual clock resume. Defer
   and Escalate keep the clock paused.

## Architecture boundary

- Reuse canonical portfolio-risk Finding identity; do not define another
  finding record.
- `risk_decisions` owns only decision proposal, lifecycle, resolution,
  consequence and supplemental decision-context contracts.
- Proposal content is immutable and digest-bound. Lifecycle changes are an
  append-only receipt chain stored outside Git beneath
  `PORTFOLIO_RISK_DECISION_ROOT`.
- Phase 5 authority is D1 and human-only. Supra-agent resolution, simulated
  portfolio mutation, live effects and policy self-modification remain
  prohibited.
- The investigation is a fixed effect-free workflow over already eligible
  references. It does not query new data, call an LLM, open a due-diligence
  workspace or rewrite the original proposal.

## Tasks

### A — contracts and lifecycle

Implement the five standard options, proposal digest, point-in-time checks,
human resolution, explicit consequence receipts, valid transitions and final
state protection.

### B — repository and cycle integration

Persist records atomically outside Git with symlink protection, optimistic
revisions and idempotency. Pause/resume the cycle from the persisted state.

### C — Decision Review interface

Render concise cards and a readable detail view. Keep evidence and lifecycle
expandable, require identity and rationale, and expose the supplemental context
revision after investigation.

### D — qualification

Run focused contract, persistence, lifecycle, API, cycle and UI checks. Then run
the scheduled cross-phase clean-room checkpoint for Phases 3–5.

## Exit gates

1. All five accepted human outcomes are available in canonical order.
2. A material proposal always pauses the cycle and cannot resume implicitly.
3. Proposal content remains unchanged across every lifecycle transition.
4. Every resolution has reviewer identity, rationale, policy reference and an
   effect-free consequence receipt.
5. Investigation produces one persisted supplemental context revision and
   returns the proposal to human review.
6. Stale or duplicate review requests fail closed or return the prior result.
7. Decision records survive process restart and reject unsafe storage paths.
8. The Decision Review page is usable at desktop and narrow widths and reports
   no browser console errors.
9. Focused and post-Phase-5 cross-phase gates pass.

## Non-goals

- no Phase 6 due-diligence workspace or ad-hoc investigation workflow builder;
- no deciding agent, supra-agent or non-human resolver;
- no automatic clock resume, workflow scheduling or notification integration;
- no portfolio, order, broker, trade, hedge, rebalance or mutation effect;
- no new data connector, LLM call, metric calculation or risk model.

## Acceptance evidence

- Focused gate: 28 tests passed after final idempotency and lifecycle-chain
  hardening.
- Cross-phase checkpoint: Day 0 architecture (124), domain/contracts (29),
  planning (22), data (83), capabilities (18), agents (15), application (115),
  integration (15), and historical journeys (8) passed; Phase 3 (15), Phase 4
  (14), and the then-current Phase 5 gate (27) also passed.
- Browser: a real-daily-anchor/synthetic-intraday cycle paused at a 1.02% loss;
  all five choices were visible; Investigate created one supplemental context
  revision; Accept & monitor finalized the proposal while leaving clock resume
  manual and effects empty.
- UI: no error/warning console messages; 705px viewport had one-column layout,
  no horizontal overflow, and a visible Decision detail panel.
- Deviation: the cross-phase suite exposed stale earlier-phase pointer tests;
  they now preserve historical acceptance while allowing a later active phase.
- Adjacent defect fixed: legacy Agent Run persistence now composes its required
  Phase 4 report envelope when an older caller does not supply one.
