# Current Workplan

- ID: PLATFORM-P3
- Title: Experiment workspace and bounded queue
- Status: in progress
- Namespace: platform-development
- Integration branch: integration/platform-experiment-workspace
- Workplan: docs/workplans/platform-development/phase-3-experiment-workspace.md
- Baseline commit: 5426cacee004817c17215ec8bff3747d5d00c2c2
- Phase 1 accepted candidate: a68ef6fce9d39f5341fa8675c093db2eba95aed6
- Verification: make verify-platform-phase3

Phase 3 adds immutable ExperimentDefinition and ExperimentSet contracts,
external restart-safe lifecycle and queue metadata, explicit foreground,
headless, and evaluation-only modes, budgets, idempotent admission, and an
Experiment Workspace over canonical source and registry references.

The visible increment creates and reviews isolated experiments, advances their
lifecycle, admits ready work to a bounded queue, pauses and resumes explicit
local controller state, and groups experiments for comparison. Admission does
not start a worker or model call.

The earlier Thesis Sprint is closed as `THESIS-DEFERRED` in
`docs/workplans/thesis-sprint/deferred.md`. Days 1–3 remain accepted and the Day
4 public fixture remains verified. The paid real panel and human scientific QA
were not run. This programme does not reopen or reinterpret that lifecycle.

All work remains research/development-only. Synthetic information must be
labelled, licensed data remains outside Git, consequential external effects are
disabled, and no live order, broker, trade, hedge, rebalance, optimization, or
portfolio mutation authority is introduced.

Phase 0 is accepted and was merged by PR #20 as commit
`21339db19357277ca9a9a1ca50107f1a884d7aeb`; all required workflows passed.
Phase 1 was accepted after independent adversarial R10 review of exact candidate
`a68ef6fce9d39f5341fa8675c093db2eba95aed6` and squash-merged by PR #21 as
`9440bbaeb3f43f04ff259dbde0eb2824b7f9c6f1`. Phase 2 starts from that immutable
baseline. It does not introduce experiment scheduling, production publication,
Studio–Codex execution, or any financial effect.

Phase 2 remains accepted locally at exact candidate
`b8eacc67ca9344944631c425e133c639395df9cf` after clean-worktree acceptance
review `3d1617a033104a91d8da48e5a50664dcb9f8ba09`. The governed repository,
explicit legacy-run admission, lifecycle APIs, Artifact Repository workspace,
and safety regressions passed. GitHub publication remains blocked by local
authentication, so Phase 3 is deliberately stacked on the recorded Phase 2
closure head rather than an unreviewed branch state.

Testing uses fast focused suites during each phase and a bounded phase gate at
candidate time. The exhaustive cross-phase clean-room suite runs every three
phases or immediately when a high-risk execution, financial-effect, data-rights,
or compatibility boundary changes.
