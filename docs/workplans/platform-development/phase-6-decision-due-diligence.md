# PLATFORM-P6 — Decision due-diligence workspace

- Status: accepted
- Accepted candidate: `5669055bbc6aea205cf3e0eb4867a949daaa5154`
- Integration branch: `integration/platform-decision-due-diligence`
- Baseline: `b07c7f8a0abac713d5d50158d6bd3ce24421eca3`
- Roadmap: `apps/portfolio-risk-workbench/labs/DEVELOPMENT_ROADMAP.md`
- Verification: `make verify-platform-phase6`

## Outcome

Give a human reviewer a dedicated, restart-safe workspace for understanding a
Decision Proposal before resolving it. The workspace must make evidence,
retained artifact references, capability receipts, mandate/policy relevance,
uncertainty and every alternative consequence easy to inspect without changing
the original Finding or Decision Proposal.

## Visible increment

1. Every Decision Card opens a dedicated due-diligence workspace.
2. The workspace separates direct evidence, artifacts, capability receipts,
   mandate/policy and alternatives, including honest missing/unavailable states.
3. The user assembles a temporary investigation from up to five registered,
   deterministic, effect-free modules and states the question being tested.
4. Running the workflow persists its step receipts, supplemental evidence and an
   additive candidate Proposal Revision. It does not resolve the decision.
5. Repeated investigations remain comparable through immutable digests,
   sequence numbers, actor identity, point-in-time metadata and idempotency.

## Registered investigation modules

- `decision.evidence.coverage.inspect`
- `decision.capability.receipts.inspect`
- `decision.policy.alignment.inspect`
- `decision.alternatives.compare`
- `decision.artifacts.lineage.inspect`

These modules inspect already eligible references. They do not fetch new market
or fundamental data, execute arbitrary queries, call an LLM, publish a reusable
workflow, or create a portfolio/external effect.

## Architecture boundary

- The Phase 5 proposal remains immutable and digest-bound.
- A `DecisionProposalRevision` is an additive candidate interpretation linked to
  the base proposal, context digest, supplemental evidence and workflow run.
- A revision is not a human resolution and cannot resume the Workflow Cycle.
- Due-diligence records remain inside the existing external, symlink-safe
  Decision Repository; no second repository or monolithic context store is
  created.
- The workspace may inspect final decisions, but new investigation runs are
  admitted only while the proposal remains non-final.
- Authority remains D1 and human-only. Financial and external effects remain
  structurally empty.

## Tasks

### A — contracts and persistence

Add typed supplemental evidence, temporary workflow runs, step receipts and
candidate proposal revisions to the existing decision record. Enforce temporal
eligibility, unique ordered steps, immutable digests, idempotency, optimistic
revision checks and proposal-revision continuity.

### B — due-diligence execution

Implement the five registered inspection modules over references already bound
to the proposal. Produce concise findings that explicitly distinguish verified
content from reference-only coverage and unavailable payloads.

### C — application workspace

Add the dedicated page, Decision Card navigation, grouped evidence ledger,
temporary workflow builder, readable run trace, supplemental evidence and
proposal-revision comparison. Keep the base proposal and authority boundary
continuously visible.

### D — qualification

Run focused contract, persistence, idempotency, API and UI tests. Qualify a
synthetic workflow-cycle proposal in the browser at desktop and narrow widths.
The next exhaustive cross-phase suite remains scheduled after Phase 8 unless a
high-risk boundary changes.

## Exit gates

1. Any Decision Card can open its due-diligence workspace directly.
2. Evidence, artifacts, capability receipts, policy/mandate and alternatives are
   visible as distinct groups with availability and data-truth labels.
3. Only the five registered effect-free modules can enter a temporary workflow.
4. Every workflow step records inputs, result, outputs, timing and empty effects.
5. Supplemental evidence is point-in-time valid, digest-bound and persisted.
6. Proposal revisions are ordered, base-proposal-bound and never overwrite the
   original proposal or constitute a decision.
7. Stale and conflicting requests fail closed; exact retries are idempotent.
8. Final decisions remain inspectable but reject new investigation execution.
9. The workspace is usable at desktop and narrow widths with no browser errors.
10. The focused Phase 6 gate passes.

## Non-goals

- no deciding agent, supra-agent or non-human resolver;
- no arbitrary workflow graph, SQL, Python, shell, LLM or external connector;
- no new empirical data retrieval or claim that a referenced payload was read;
- no registry publication, reusable workflow creation or Studio–Codex gateway;
- no automatic clock resume, notification or scheduler;
- no portfolio, broker, order, trade, hedge, rebalance or mutation effect;
- no Phase 7 context-boundary model or Phase 8 vertical-slice expansion.

## Post-acceptance structural correction

Before Phase 7, the unified Labs shell was corrected to expose three operating
zones without replacing the accepted Phase 6 stores or decision contracts:

1. **System Development** for authoring, singular fixture tests and explicit
   Registry saving;
2. **Agent Application** for loading saved definitions into a labelled fixture
   and reviewing object/agent behaviour through the existing isolated runner;
3. **Experimental Research** for persistent experiment composition, queueing and
   comparison.

The correction also closes an experiment admission defect: source discovery is
no longer enough to enter a new experiment. Workflow and evaluation identities
must be explicitly indexed in the Registry and remain candidate, validated or
locally published. This gate is enforced by the API as well as the selection UI.

The terminology and future dependency reminders are normative in
`docs/architecture/platform-operating-zones.md`. PLATFORM-P7, P8, P9, P14 and
P15 placeholders remain non-executable and name the exact later capability that
will activate them. Artifacts are defined as deliberately retained run work
products; they do not become reusable definitions without a separate promotion.

## Acceptance evidence

- Focused gate: 39 tests passed across inherited Phase 5 boundaries, Phase 6
  architecture, decision contracts, persistence, idempotency, API and Workflow
  Cycle compatibility.
- Browser: a technology-concentrated portfolio with real daily anchors and a
  seeded synthetic intraday path paused at a 1.02% loss against a 1.00% review
  threshold on 2018-10-09 at 14:18 simulated time.
- Navigation: the Decision Card opened the dedicated due-diligence page with
  direct evidence, two artifact references, one capability receipt, one policy
  and all five alternatives visibly separated.
- Execution: one five-module and one four-module temporary workflow retained two
  run traces, nine supplemental evidence items and contiguous candidate Proposal
  Revisions 2 and 3. The immutable proposal remained version 1 and awaiting
  human review; no resolution or effect was created.
- Persistence: both runs and Proposal Revision 3 survived a complete application
  process restart from the same external Decision Repository.
- UI: no console warnings or errors after the notification defect was corrected;
  the 705px viewport used one main column with no horizontal overflow.
- Verification cadence: the next exhaustive cross-phase checkpoint remains due
  after Phase 8; Phase 6 changed no external-effect, data-rights or non-human
  authority boundary that would trigger it early.
