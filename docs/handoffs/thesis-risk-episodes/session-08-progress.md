# Session 8 Progress — Point-in-Time Trajectory Kernel

**State:** accepted; superseded by `session-08.md`

The first Session 8 slice adds a reusable `RunTrajectory` kernel over one
compiled matched-run cell. It is not a second replay or output model.

Implemented:

- typed market, fundamental, event, portfolio, mandate and derived observations;
- `available_at <= replay_at` release at every workflow cycle;
- deterministic chronological trigger ordering;
- frozen simulated time through capability, model and validation processing;
- explicit `ArchitectureOutput`, abstention or error result for every cycle;
- exact Run, Case, architecture, cycle and input-context binding;
- previous-output identity carried to the next cycle without copying prose;
- capability/model calls, token use, processing components and cost per cycle;
- reconciled trajectory totals and immutable external persistence;
- fail-closed termination after an explicit cycle error.
- Case compilation now separates the complete eligible replay stream from the
  retrospectively retained Gold evidence set. Rejected controls remain visible
  to the architecture when historically eligible; Gold selection never becomes
  an input shortcut;
- a licensed-source adapter resolves every declared Case observation to its
  exact detector unit or context candidate, verifies exact set equality, and
  creates chronological availability triggers;
- a compact Run-comparison preflight reports observation counts, types, cycle
  count and time range without rendering internal contracts.

Controlled tests prove a late observation is absent from the first cycle and
present in the next, abstentions remain evaluable, successful cycles retain one
valid `ArchitectureOutput`, an error stops the trajectory, the full ex-ante
stream includes non-Gold controls, and unresolved identities fail closed. The
retained licensed repository was then used under explicit research-lead
authority to create one bounded ADX Case. It now retains an agent-authored
label, distinct label review, evidence review, independently reviewed Gold
reference, compiled `ExperimentalCase`, matched B0/B1/A1 plan and B0 trajectory.

The Case contains 16 architecture-visible observations: 15 historically
eligible event records and one CRSP detector record. The three admitted adapters
then completed the same 16-cycle stream after explicit research-lead authority
to transmit the bounded derived licensed context to OpenAI:

| Architecture | Substantive cycles | Abstentions | Model calls | Cost | Highest state |
|---|---:|---:|---:|---:|---|
| B0 deterministic | 16 | 0 | 0 | $0 | alert |
| B1 single agent | 4 | 12 | 4 | $0.010899 | watch |
| A1 agent graph | 4 | 12 | 16 | $0.028659 | watch |

B1 used 23,181 input and 5,219 output tokens. A1 used 70,153 input and
12,190 output tokens. Raw licensed news text was not sent; the adapters exposed
only bounded structured event and market context. Neither model architecture
received the Gold reference. Repeated execution requests return the retained
trajectory instead of invoking capabilities or models twice.

This is an apparatus result, not evidence that A1 is superior. A1 retained a
usable narrative on three of four active cycles and hit one deterministic critic
abstention. B1 retained one usable narrative and hit three critic abstentions.
Both remained at `watch` when B0 reached a final `alert`, so the comparison has
already identified a severity/escalation disagreement that the evaluation
session must measure rather than hide.

Session 8 closure subsequently added governed human-readable trajectory
artifacts outside evaluation fields, a compact expandable workflow-cycle
timeline, explicit warning/actionable/high-confidence/persistence/decay
projections, graph contribution/disagreement/coordination projections, and a
mixed-frequency clock-blocking proof. Session 9 now owns evaluation of the
observed detection, severity, evidence and timeliness differences.

The Case is valid for apparatus development, but its Gold record states that
Codex performed separate review passes under explicit research-lead authority.
It is not represented as external expert adjudication.

## Verification

- 173 focused experiment, detector, data-adapter, application and UI-contract
  tests passed.
- JavaScript syntax, Python compilation and `git diff --check` passed.
- The final Session 1–8 focused regression gate passed 177 tests;
  retained B1 and A1 endpoint checks returned `idempotent: true` without new
  model calls.
- The live Workbench resolved the new Case to 16 exact licensed observations,
  exposed the compact planner, compiled and completed three matched cells, and
  now projects only concise retained Run summaries. Contracts and technical
  receipts remain available to Codex and tests rather than cluttering the page.
