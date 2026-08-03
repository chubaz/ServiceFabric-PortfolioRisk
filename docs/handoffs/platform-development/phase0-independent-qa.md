# Phase 0 independent QA handoff

- Lane: P0-05 independent QA
- Branch: `review/platform-p0-qa`
- Candidate: `b5616a795dc5d480202e5e767dfa7a7828c8bf46`
- Programme baseline: `81660bd3d4be9c8fb6725e5836e7821f9947eb17`
- Verdict: **FAIL**
- Scope: independent review only; no candidate defect was repaired and nothing
  was merged

## Verdict

The amended candidate is locally reproducible, preserves the financial-effect
boundary, contains the required audit evidence, and fixes the obsolete Thesis
Day 1 specialist-ancestry CI assertion correctly. It is not yet ready to become
the Phase 1 baseline because two user-visible Phase 0 truth contracts remain
internally inconsistent and the synthesis commit exceeds the path ownership
declared by the programme manifest:

1. Workflow Cycle still represents an unresolved threshold finding as a
   decision before an identified resolver acts.
2. Generated synthetic Agent scenarios are presented and persisted as named
   fixtures without the fixture identity/version/digest required to distinguish
   a reviewed fixture from a synthetic behavior sample.
3. The integration lane changed the Labs application although its own lane
   record does not grant that directory.

The first defect directly contradicts accepted `DEC-001`, the integration
synthesis, and the truth strip's findings/proposals-only authority statement.
The second makes the new truth strip disagree with the saved run and input
provenance. Both are within Phase 0's stated terminology and data-truth scope;
neither requires a registry kernel or new canonical object to correct. The path
finding is a control-plane inconsistency: the workplan assigns the visible
increment to integration, but the machine-readable lane grant omits its path.

## Blocking findings

### QA-01 — an unresolved proposal is still called and stored as a decision

**Expected**

The accepted vocabulary is evidence → finding → decision proposal → decision
by an identified resolver → effect. The active truth strip says Workflow Cycle
has “Findings and decision proposals only · effects none.” `DEC-001` requires
Finding, Decision Proposal, resolved Decision and Action to remain distinct.

**Observed**

- `apps/portfolio-risk-workbench/labs/workflow_cycle_runtime.py:283` creates a
  dictionary named `decision` immediately when a loss threshold is crossed.
  It gives that unresolved object a `decision_id`, appends it to `decisions`,
  records an event of kind `decision`, and calls it an intraday-loss decision
  before any resolver acts (`:290-314`).
- `apps/portfolio-risk-workbench/labs/index.html:723-725` labels the pending
  object “Human decision” and offers “Accept and resume”, “Open investigation”
  and “Reject finding”. “Open investigation” does not open an investigation
  workspace.
- `apps/portfolio-risk-workbench/labs/labs.js:2803-2806` presents a “Decision
  queue” and says a threshold “created a decision”.
- `apps/portfolio-risk-workbench/labs/workflow_cycle_runtime.py:482-497`
  resolves by mutating the same dictionary in memory. It records no resolver
  identity, consequence preview, separate immutable resolution receipt or
  distinction between the proposal and the resulting decision.

**Impact**

The page can make an analytical threshold crossing look authoritative before
resolution. This violates the Phase 0 exit gate requiring lifecycle vocabulary
to have one meaning in contracts and UI, and it undermines the central decision
boundary the user asked Phase 0 to establish.

**Required bounded return task**

Without introducing the unresolved Decision v1 contract, rename the current
ephemeral object and API/UI projection to a decision proposal/review proposal,
keep the finding distinct, identify the resolver on resolution, render the
consequence of each allowed outcome, and record a separate resolution receipt.
“Investigate” must either schedule/open the declared investigation or say that
it only marks the proposal for later investigation. Add runtime assertions, not
only string-presence tests.

### QA-02 — generated behavior samples are persisted as reviewed-sounding fixtures

**Expected**

The Phase 0 vocabulary reserves “Reviewed synthetic fixture” for a governed
fixture identifier, version and digest. Generated/code-defined scenarios are
“Synthetic behavior fixtures” or synthetic samples. That distinction must
remain consistent in input provenance and retained run manifests, not only in
the global truth strip.

**Observed**

- The server truth strip correctly calls the Agent source “Synthetic behavior
  fixture” in `apps/portfolio-risk-workbench/labs/duckdb_server.py:80-83`.
- The actual input preview instead returns `data_mode: synthetic_fixture`,
  `SYNTHETIC FIXTURE`, and only a scenario name at
  `duckdb_server.py:1180-1192`; it has no fixture version or digest.
- The generated source context calls itself a named fixture and uses a
  `fixture://` reference at
  `apps/portfolio-risk-workbench/labs/agent_studio.py:3267-3283`, again without
  a reviewed fixture version/digest.
- The retained run manifest persists that conflicting `data_mode` and
  `data_label` at `agent_studio.py:4147-4166`; the run result supplies
  `SYNTHETIC FIXTURE` at `:4296-4300`.

**Impact**

The same run is described as an ungoverned synthetic behavior fixture in the
truth strip and as a named synthetic fixture in its durable review material.
Reviewers cannot tell from the saved manifest whether it references a reviewed
Git fixture or a code-generated sample, which fails the requested
fixture/synthetic provenance boundary.

**Required bounded return task**

Classify these existing code-defined scenarios consistently as
`synthetic_behavior_fixture` (or synthetic sample) throughout request,
provenance, result, UI and manifest. Alternatively, bind each to a reviewed
fixture ID, immutable version and digest. Add a test that exercises the actual
preview and saved-manifest values; the current test checks only truth-strip
source strings.

### QA-03 — the integration synthesis exceeds its declared lane paths

**Expected**

`config/agent/platform-development/lanes.json` is the exact ownership record.
The Phase 0 task and AGENTS instructions say lane ownership must be verified,
and the lane record should grant every path required by P0-04 before work begins.

**Observed**

The integration lane grants `.github`, control-plane docs/config, scripts and
tests plus a small allowed-file list. It does not grant
`apps/portfolio-risk-workbench/**`. Integration commit `a0a4fb9` changes six
Labs source files and `apps/portfolio-risk-workbench/servicefabric-package.json`.
The workplan did assign the visible increment to integration, so this appears
to be a manifest omission rather than cross-agent code ownership; nevertheless
the committed change does not satisfy the exact machine-readable grant.

**Impact and required bounded return task**

The programme cannot claim exact lane validation while its principal synthesis
change lies outside the declared paths. Reconcile the manifest with the already
documented integration responsibility, add a regression that validates the
actual integration commit range against the grant, and re-run the gate. Do not
retroactively broaden specialist ownership.

## Non-blocking terminology residue

These do not add another reason for the FAIL verdict, but should be included in
the same bounded truth-language correction where practical:

- `apps/portfolio-risk-workbench/labs/index.html:719`,
  `labs.js:2800,2818`, and `workflow_cycle_runtime.py:72,114,363` still say
  “Live market tape” or “Live portfolio risk review” for a seeded simulated
  intraday stream. The truth strip is correct, but the primary content can still
  imply a live market feed.
- Agent run headings say “Keep every output” although the disclosed class is a
  temporary, deletable local run, and the repository item still says
  “Synthetic fixture”.
- `OverallDefaultContext` remains visible as if settled in the Agent forms and
  lifecycle. The accepted audit classifies it as a provisional compiled view
  pending the context-family decision.
- Development authoring controls are not tagged or server-rejected as a group.
  This is not current leakage because the candidate exposes only the fixed
  Development profile, but enforcement is required before any Experimental or
  Persistent research profile becomes executable.

## Evidence that passed

### Required and focused local verification

- `PIP_NO_INDEX=1 make BOOTSTRAP_VENV=.venv-bootstrap-qa
  DAY0_VENV=.venv-day0-qa verify-platform-phase0`: **PASS**, 24 tests.
  Repository check and ServiceFabric doctor passed at pinned vendor commit
  `7632b61d94a966346f95eb6c5bb2a5ea27f3bc14`.
- `PIP_NO_INDEX=1 make DAY0_VENV=.venv-day0-qa test-application
  test-architecture`: **PASS**, 93 application tests and 99 architecture tests.
- `node --check apps/portfolio-risk-workbench/labs/labs.js`: **PASS**.
- Python compilation of `agent_studio.py`, `duckdb_server.py`, and
  `workflow_cycle_runtime.py`: **PASS**.
- ServiceFabric application-package manifest hash check: **PASS**.
- `git diff --check`: **PASS**.

The QA environments were copied from the integration lane's pinned local
environments and run with `PIP_NO_INDEX=1`; no dependency network access or
model/provider call was used.

### Control-plane and scope integrity

- All three specialist audit commits change only their exact handoff files:
  `e3acab1`, `29e2147`, and `6883427`.
- Integration commit `b5616a7` is within the recorded integration grant. Commit
  `a0a4fb9` contains the Labs changes required by P0-04, but those application
  paths are missing from the lane manifest; this is QA-03 above.
- The complete baseline-to-candidate range has no change under
  `vendor/servicefabric`, `private-data`, `.agent-runs`, `state`, or committed
  data/fixture paths.
- The ServiceFabric gitlink remains pinned at `7632b61d94a966346f95eb6c5bb2a5ea27f3bc14`.
- No external-effect endpoint, broker connection, order, trade, hedge,
  rebalance or portfolio-mutation operation was introduced.

### Truth strip, checkpoint and decision-source evidence

- The server provides a four-part Development/data/authority/persistence
  boundary for every workspace in
  `apps/portfolio-risk-workbench/labs/duckdb_server.py:57-106`.
- The strip is outside the workspace panels and remains visible as a two-by-two
  mobile grid; connection failure falls back to “origin not verified” rather
  than synthetic data.
- Licensed historical, synthetic behavior and mixed licensed-anchor/simulated-
  intraday meanings are stated explicitly in the strip; Workflow Cycle exposes
  its sealed-future-anchor rule in the runtime snapshot.
- Agent isolated-run checkpoint release now defaults off. When deliberately
  enabled, the receipt records `actor_type: test_harness`,
  `human_approval: false`, `review_checkpoint_released_for_test`, findings/
  proposals-only authority, no effects, and temporary-run persistence. No
  canonical `DecisionPoint` is created by this path.
- The integration handoff keeps all seven unresolved decisions visible with a
  latest safe decision point: `DEC-002`, `DEC-013`, `DEC-014`, `ERC-027`, the
  portfolio-applied environment placement, cross-experiment ERC ancestry, and
  final `OperatingProfile` naming.

## CI evidence and caveat

GitHub PR #20 is open, mergeable and still draft at the reviewed head. At the
last independent connector read for `b5616a7`:

- `preparation` run 53: **success**;
- `Day 0` run 57: **success**;
- `Day 1 lifecycle` run 55: **success**;
- `thesis-sprint` run 46: **success**;
- `day23` run 42: **still in progress**.

The amendment is a coherent fix: `verify-thesis-day1` continues to run the
historical tests and fixture checks, while the old specialist-ancestry/path
range assertion runs only when the active workplan ID is `THESIS-*`. The new
architecture test confirms that both branches of this gate remain present.

An additional independent `make verify-thesis-current` attempt did not complete
because the clean QA worktree lacked a prebuilt Day 2–3 environment and
networking was disabled; it stopped during dependency bootstrap before tests.
This is an environment limitation, not a candidate failure. The amended
GitHub `thesis-sprint` workflow subsequently completed successfully. The
remaining `day23` run must be green before integration makes any merge decision.

The PR description still reports the pre-amendment counts (23 Phase 0 tests and
98 architecture tests); the amended candidate has 24 and 99 respectively.
Update the evidence text before marking the PR ready.

## Deviations, blockers and limitations

- No browser automation or visual screenshot was used in this independent
  lane. Layout behavior is covered by committed source/tests and the integration
  handoff's desktop/740px evidence; visual/a11y behavior beyond those assertions
  remains residual risk.
- No licensed query, paid model call, private run folder or user data was read.
- The candidate remains development-profile-only. This QA therefore verifies
  that no non-development profile is enabled, not that future server-side
  profile enforcement already exists.
- The FAIL verdict is caused by the two semantic defects and one lane-manifest
  inconsistency above, not by the still-running `day23` CI check.

## Changed paths

- `docs/handoffs/platform-development/phase0-independent-qa.md` only.

## Rollback

Revert this documentation-only QA commit. No candidate implementation, vendor
source, private data, generated artifact, workbook, runtime session or external
system was modified.

## Recommended next action

Return the candidate to integration for one bounded correction task covering
QA-01, QA-02 and QA-03, with focused runtime and lane-range tests. Re-run `make
verify-platform-phase0`, application and architecture tests, verify all GitHub
workflows are green, then dispatch a fresh independent QA review. Do not mark
Phase 0 complete or make PR #20 ready while this FAIL handoff remains current.

---

## Re-review — 2026-08-03 — candidate `7bcf9a7d99969586e55a2d186a0b603b755cd1ca`

- Lane: P0-05 independent QA, second review
- Branch: `review/platform-p0-qa-r2`
- Candidate: `7bcf9a7d99969586e55a2d186a0b603b755cd1ca`
- Prior FAIL above: preserved verbatim
- Verdict: **FAIL**
- Scope: independent review only; no candidate defect was repaired and nothing
  was merged

### Re-review verdict

The bounded correction closes QA-02 and QA-03 and materially improves QA-01.
It now keeps the decision proposal immutable during resolution, creates a
separate decision and consequence receipt, previews all outcomes, describes
investigation honestly, and preserves empty portfolio and external effects.
The candidate nevertheless cannot become the Phase 1 baseline because the
corrected decision path still does not implement the lifecycle it claims in
three related places:

1. the finding is not a separately retained immutable artifact;
2. the UI records a generic hard-coded role as an identified human resolver;
3. acceptance auto-starts the workflow although the immutable receipt records
   only that manual resume is permitted.

These are not requests for the unresolved Decision v1 design. They are
truthfulness defects in the current in-memory Phase 0 demonstration and can be
fixed within the existing bounded runtime.

### QA-01-R2 — finding, resolver, and consequence remain internally inconsistent

**Separate finding artifact**

`workflow_cycle_runtime.py:292-324` creates only a `decision_proposal`. The
threshold observation is embedded in that object as `finding` with a
`finding_id`; the session has no `findings` collection and the snapshot exposes
only `decision_proposals`, `decisions`, and `consequence_receipts`. The focused
runtime probe confirmed those are the only lifecycle collections. Therefore
the visible chain starts with a proposal containing prose rather than the
declared `evidence -> finding -> decision proposal` sequence. The new test is
named as if all four artifacts are distinct, but it asserts no standalone
finding artifact.

**Resolver identity**

`duckdb_server.py:358-361` defaults every resolution to
`local-human-reviewer`, and `labs.js:2924-2930` sends that same constant while
declaring `resolver_type: human`. There is no authenticated identity, explicit
reviewer field, or per-session actor identity behind that value. A button click
does demonstrate interactive resolution, but the retained decision cannot
truthfully identify which human resolved it. The risk dashboard then renders
the constant as `Resolver local-human-reviewer` (`labs.js:2803-2808`), making a
generic role look like an identified person.

**Recorded versus actual consequence**

The accepted option says “The workflow may be resumed manually”
(`workflow_cycle_runtime.py:304-309`) and its consequence receipt records
`manual_resume_permitted` (`:550-564`). The UI instead labels the action
“Accept proposal and resume” (`index.html:723-725`) and immediately posts a
second `start` command after recording the decision (`labs.js:2931-2933`). The
focused runtime probe reproduced the resulting transition from `paused` to
`running`. The receipt therefore does not record the actual workflow
consequence of the interaction shown to the user.

The financial authority boundary itself remains intact: the proposal and
decision contain `effects: []`, while the receipt contains
`portfolio_effects: []` and `external_effects: []`. No broker, order, trade,
hedge, rebalance, or portfolio-mutation action was introduced.

**Required bounded return task**

1. Retain a separate immutable finding record and have the proposal reference
   it by ID; expose and test the finding independently of the proposal.
2. Require a truthful resolver identity supplied by an explicit local-review
   interaction or authenticated/session actor. Do not default an API caller to
   a generic identifier while asserting that it is a human identity.
3. Make the accepted consequence and behavior identical: either leave the
   cycle paused and require a separate manual Resume action, or record the
   automatic resume as the actual consequence and receipt. The former matches
   the present preview and keeps resolution separate from execution.
4. Add runtime/API assertions for all three boundaries, including that the
   browser path cannot create a human-labelled decision without an identified
   resolver and that the receipt matches the resulting workflow state.

### QA-02-R2 — closed

Code-generated Agent scenarios are consistently classified as
`synthetic_behavior_sample`. Their provenance includes the selected scenario,
`reviewed_fixture: false`, a `synthetic://agent-studio/<scenario>` reference,
and an explicit warning that the values are neither a reviewed fixture nor a
historical observation. The same data mode and label are persisted in the run
manifest, while `input-provenance.json` retains `reviewed_fixture: false`.

The new application test exercises the generated input and an actual temporary
saved-run package, rather than checking only source strings. No licensed-data
or empirical claim is made for this path.

### QA-03-R2 — closed

The integration lane now grants both `apps/portfolio-risk-workbench` and
`tests/application`. The committed architecture test validates the visible
synthesis range
`e3acab1252269066fa6818b24a84047d4ac38847..a0a4fb920291cf1f4fe52e651632bf75d0968a9b`
against that grant. An independent invocation returned ten changed-path
records and zero violations, including the Labs application, package manifest,
application test, architecture test, status, and integration handoff.

This is a reconciliation of the integration responsibility already assigned
by P0-04; no specialist lane was broadened.

### Other Phase 0 truth checks

- The four-part Development/data/authority/persistence strip remains
  server-defined and visible for every workspace.
- Agent isolated-run checkpoint release defaults off. An intentional test-
  harness release remains labelled `test_harness`, `human_approval: false`,
  findings/proposals-only, effect-free, and temporary.
- Agent code-generated samples and licensed DuckDB inputs remain distinct in
  request types, provenance, UI labels, and persistence.
- Workflow Cycle continues to disclose licensed daily anchors plus simulated
  seeded intraday observations, sealed future anchors, in-memory persistence,
  and no financial effects.
- The prior ambiguous “Live” Agent and simulated-cycle labels covered by the
  focused application test are absent. `OverallDefaultContext` remains visibly
  provisional/assembled-after-calculation; its final canonical placement is
  still an explicit downstream decision.
- All seven unresolved downstream decisions listed in the integration handoff
  remain visible and were not silently resolved by this correction.

### Reproduced verification

- `PIP_NO_INDEX=1 make BOOTSTRAP_VENV=.venv-bootstrap-qa
  DAY0_VENV=.venv-day0-qa verify-platform-phase0`: **PASS**, 25 tests.
- `PIP_NO_INDEX=1 make DAY0_VENV=.venv-day0-qa test-application
  test-architecture`: **PASS**, 95 application tests and 100 architecture
  tests.
- ServiceFabric application-package manifest hash check: **PASS**.
- `node --check apps/portfolio-risk-workbench/labs/labs.js`: **PASS**.
- Python compilation of `agent_studio.py`, `duckdb_server.py`, and
  `workflow_cycle_runtime.py`: **PASS**.
- `git diff --check`: **PASS**.
- Independent synthesis-range lane validation: **PASS**, ten records and zero
  violations.
- Focused decision-runtime probe: **PASS as evidence of the blocker**; it
  showed no separate `findings` collection, a decision resolved by the literal
  `local-human-reviewer`, a receipt of `manual_resume_permitted`, and the
  follow-up UI-equivalent start transition to `running`.

The QA virtual environments were copied from the integration worktree's pinned
local environments and executed with `PIP_NO_INDEX=1`. No dependency network,
licensed query, paid model call, private run folder, or external-effect system
was used. GitHub status was not independently refreshed because GitHub CLI
authentication is unavailable in this QA environment; this does not change the
local semantic FAIL.

### Scope integrity and residual risk

- The complete programme-baseline-to-candidate range contains no change under
  `private-data`, `.agent-runs`, `state`, or committed fixture/data paths.
- `vendor/servicefabric` remains pinned at
  `7632b61d94a966346f95eb6c5bb2a5ea27f3bc14`.
- No browser automation or visual screenshot was used in this re-review. The
  decision mismatch is established by the actual UI handler, rendered copy,
  runtime objects, focused application tests, and a direct runtime probe.
- Passing tests do not override QA-01-R2 because the new lifecycle test does
  not assert a separate finding, a non-default truthful resolver, or agreement
  between the receipt and browser-driven workflow state.

### Changed path and rollback

This re-review changes only
`docs/handoffs/platform-development/phase0-independent-qa.md`. Revert the
documentation-only QA commit to roll it back. No implementation, vendor source,
private data, generated artifact, workbook, runtime service, or external system
was modified.

### Re-review recommendation

Return only QA-01-R2 to integration as one bounded correction. QA-02 and QA-03
are closed and should not be reopened. After the corrected finding/resolver/
consequence path has focused runtime and UI-handler coverage, dispatch a third
independent review. Do not mark Phase 0 complete, move the active wave to an
accepted baseline, or make PR #20 ready while this second **FAIL** remains the
latest QA verdict.
