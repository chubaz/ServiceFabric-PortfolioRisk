# PLATFORM-P0 — programme activation, baseline, and terminology

- Status: in progress
- Integration branch: `integration/platform-development`
- Baseline: `81660bd3d4be9c8fb6725e5836e7821f9947eb17`
- Roadmap: `apps/portfolio-risk-workbench/labs/DEVELOPMENT_ROADMAP.md`
- Lane manifest: `config/agent/platform-development/lanes.json`

## Outcome

Create a trustworthy starting point for the multi-phase platform programme.
Phase 0 ends with agreed vocabulary, an evidence-backed map of what already
exists, explicit lifecycle and storage boundaries, visible operating-profile
rules, a preserved working vertical slice, and a bounded Phase 1 backlog.

This phase has wider responsibility than the roadmap's five bullets. It also
owns Git/CI hygiene, decision normalization, regression safety, developer
operability, public/private data boundaries, and the consistency of the Agent,
Capability, Dataset, Workflow Cycle, Decision, Context, Mandate, and future
Studio–Codex directions.

## Inputs and authority

1. Repository contracts, registries, runtime paths, tests, and Labs UI.
2. `DEVELOPMENT_ROADMAP.md` and `EXTERNAL_ADAPTERS_DISCUSSION_BRIEF.md`.
3. The user-reviewed `servicefabric_architecture_decision_register_v3.xlsx`.
4. The deferred Thesis Sprint record and accepted Day 1–3 baselines.

The decision workbook is an input, not an executable policy. Phase 0 must
normalize accepted and modified P0/Before-v1 answers into reviewable text before
they can govern implementation. Where a modified answer is ambiguous, the
handoff records the ambiguity rather than inventing a resolution.

## Visible, testable increment

By the end of Phase 0 the running Labs application must clearly disclose:

- development, experimental, and persistent-research profiles;
- real, synthetic, fixture, simulated, missing, and unavailable data states;
- whether an action is a finding, proposal, decision, simulated effect, or
  prohibited external effect;
- where a run and its artifacts are stored and what may be retained or deleted.

The existing agent run review, DuckDB query utility, and workflow-cycle
prototype must continue to pass focused smoke tests. Phase 0 does not redesign
their complete UX or implement the registry kernel.

## Execution waves

### Wave A — activation (integration, serial)

- merge and verify the prior lifecycle;
- create the clean branch/worktree and control-plane namespace;
- freeze lane ownership and write every task brief;
- add a deterministic Phase 0 verification target.

### Wave B — evidence audits (three tasks in parallel)

1. Canonical contracts, registries, and normalized decisions.
2. Run, storage, artifact, retention, and runtime behavior.
3. UI terminology, data-state disclosure, and profile/policy leakage.

These tasks are read-only except for their exact handoff files. They may not
create new canonical objects or modify application code.

### Wave C — synthesis and bounded implementation (integration)

- reconcile the three audits into one terminology and reuse map;
- record unresolved decisions and Phase 1 prerequisites;
- implement only the minimum profile/data-state disclosure needed for the
  visible increment;
- add architecture and application regression tests;
- preserve all existing strict contracts and ignored run-artifact boundaries.

### Wave D — independent QA and acceptance

- independently review scope, safety, truthfulness, and test evidence;
- run the Phase 0 gate from a clean candidate;
- either close Phase 0 or record explicit blockers without partial acceptance.

## Task index

| Task | Wave | Can run in parallel | Instruction |
|---|---|---:|---|
| P0-00 Integration activation | A | No | `TASK-00-INTEGRATION-ACTIVATION.md` |
| P0-01 Canonical and decisions audit | B | Yes | `TASK-01-CANONICAL-DECISIONS.md` |
| P0-02 Storage and runtime audit | B | Yes | `TASK-02-STORAGE-RUNTIME.md` |
| P0-03 UI profiles and policy audit | B | Yes | `TASK-03-UI-PROFILES-POLICY.md` |
| P0-04 Integration synthesis | C | No | `TASK-04-INTEGRATION-SYNTHESIS.md` |
| P0-05 Independent QA | D | After synthesis | `TASK-05-INDEPENDENT-QA.md` |

All paths above are relative to
`docs/workplans/platform-development/phase-0/`.

## Non-goals

- no Registry Kernel implementation;
- no new monolithic context, mandate, decision, run, or artifact object;
- no Studio–Codex execution gateway;
- no RavenPack, MCP, broker, or production integration;
- no autonomous decision or simulated portfolio mutation;
- no paid LLM experiment and no claim that fixture behavior is real evidence.

## Exit gates

1. All three audit handoffs are complete and identify evidence by path.
2. Every reused, missing, duplicated, provisional, and obsolete object is named.
3. Lifecycle/profile/data-state vocabulary has one meaning in contracts and UI.
4. P0/Before-v1 decisions are normalized with unresolved items made explicit.
5. Development-only controls cannot appear in non-development profiles.
6. The existing vertical slice and public fixture gates remain green.
7. Independent QA records a pass or explicit blockers.
8. Phase 1 starts only from an immutable accepted Phase 0 commit.
