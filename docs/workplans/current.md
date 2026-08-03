# Current Workplan

- ID: PLATFORM-P1
- Title: Unified registry kernel and catalogue
- Status: accepted
- Namespace: platform-development
- Integration branch: integration/platform-registry-kernel
- Workplan: docs/workplans/platform-development/phase-1-registry-kernel.md
- Baseline commit: 21339db19357277ca9a9a1ca50107f1a884d7aeb
- Accepted candidate: a68ef6fce9d39f5341fa8675c093db2eba95aed6
- Independent QA: R10 PASS
- Verification: make verify-platform-phase1

Phase 1 builds a persistent, development-only index over the definitions that
already exist in ServiceFabric PortfolioRisk. It does not replace or copy
canonical objects. The first catalogue covers agents, capabilities,
evaluations, reports, dashboards, scenarios, and workflows, with lifecycle,
version comparison, lineage, compatibility, and provenance.

The visible increment is a searchable Registry workspace that can preview and
explicitly index existing definitions, inspect their source and provenance,
compare versions, and apply governed lifecycle transitions. Registry metadata
survives a server restart outside Git; indexed definitions remain authoritative
at their original sources.

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
`a68ef6fce9d39f5341fa8675c093db2eba95aed6`. It starts from that immutable
baseline. It does not introduce artifact
repository semantics, production publication, Studio–Codex execution, or any
financial effect.
