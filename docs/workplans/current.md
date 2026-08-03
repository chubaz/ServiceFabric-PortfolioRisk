# Current Workplan

- ID: PLATFORM-P2
- Title: Artifact repository and retained runs
- Status: in progress
- Namespace: platform-development
- Integration branch: integration/platform-artifact-repository
- Workplan: docs/workplans/platform-development/phase-2-artifact-repository.md
- Baseline commit: 9440bbaeb3f43f04ff259dbde0eb2824b7f9c6f1
- Phase 1 accepted candidate: a68ef6fce9d39f5341fa8675c093db2eba95aed6
- Verification: make verify-platform-phase2

Phase 2 adds a governed, development-only repository for generated artifacts
and retained runs. It reuses canonical artifact references and immutable
content-addressed storage, adds retention and deletion policy as metadata, and
keeps all mutable bytes outside Git.

The visible increment is an Artifact Repository workspace that can browse,
inspect, verify, download, archive, restore, and govern deletion of retained
run outputs. Every file belongs to an immutable digest manifest and discloses
its data-truth, rights, retention, run, provenance, and publication boundary.

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
