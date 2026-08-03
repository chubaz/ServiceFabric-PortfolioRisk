# PLATFORM-P1 — unified registry kernel and catalogue

- Status: in progress
- Integration branch: `integration/platform-registry-kernel`
- Baseline: `21339db19357277ca9a9a1ca50107f1a884d7aeb`
- Roadmap: `apps/portfolio-risk-workbench/labs/DEVELOPMENT_ROADMAP.md`
- Lane manifest: `config/agent/platform-development/phase1-lanes.json`

## Outcome

Create one searchable index over existing ServiceFabric PortfolioRisk
definitions without replacing their canonical contracts. An indexed record is
a projection and source pointer, not another copy of the agent, capability,
evaluation, report, dashboard, scenario, or workflow definition.

## Visible, testable increment

The Labs application gains a Registry workspace where a user can:

1. preview definitions discovered from existing source registries;
2. explicitly index them into persistent local development storage;
3. search and filter by kind and lifecycle state;
4. inspect identity, source, digest, provenance, compatibility, and lineage;
5. compare two versions and apply validated lifecycle transitions.

The UI must say whether an item is merely discovered or persistently indexed.
It must identify its canonical source and make clear that this is not production
publication. The registry introduces no financial effects.

## Contract boundary

- Canonical definitions stay at their existing source paths and registries.
- The kernel stores immutable identity and source observations plus append-only
  lifecycle receipts.
- Mutable registry data defaults outside Git and may be redirected in tests.
- Phase 1 stores no report files, run outputs, datasets, or copied manifests;
  those belong to later artifact and experiment phases.
- Publication means registry publication in the local development profile, not
  product deployment or external distribution.

## Execution waves

### Wave A — activation

Freeze the exact baseline, lanes, task briefs, verification target, and current
programme pointer.

### Wave B — bounded parallel audits

1. Registry contracts and persistence reuse.
2. Catalogue UI integration and truthful user language.
3. Existing source discovery and migration mapping.

Each specialist is read-only except for one handoff. Integration owns every
shared contract and code change.

### Wave C — integration implementation

Implement the reusable registry package, Labs source adapters, API, catalogue
UI, focused tests, and migration/bootstrap behavior. Reconcile specialist
evidence before choosing an adapter or creating a field.

### Wave D — independent QA and acceptance

Review the exact candidate in a clean worktree, run focused and regression
gates, preserve any failure evidence, then either repair and repeat or accept
Phase 1. No Phase 2 work starts in this workstream.

## Task index

| Task | Wave | Parallel | Instruction |
|---|---|---:|---|
| P1-00 activation | A | No | `TASK-00-INTEGRATION-ACTIVATION.md` |
| P1-01 contracts/persistence audit | B | Yes | `TASK-01-CONTRACTS-PERSISTENCE.md` |
| P1-02 catalogue UI audit | B | Yes | `TASK-02-CATALOGUE-UI.md` |
| P1-03 source migration audit | B | Yes | `TASK-03-SOURCE-MIGRATION.md` |
| P1-04 integration implementation | C | No | `TASK-04-INTEGRATION-IMPLEMENTATION.md` |
| P1-05 independent QA | D | After implementation | `TASK-05-INDEPENDENT-QA.md` |

All task paths are relative to
`docs/workplans/platform-development/phase-1/`.

## Exit gates

1. All seven initial asset kinds are surfaced from real existing definitions.
2. No indexed record embeds or becomes authoritative for its source definition.
3. Lifecycle transitions are validated and append-only receipts are retained.
4. Version comparison, lineage, compatibility, and provenance are inspectable.
5. Local persistence survives restart and is path-safe, atomic, and testable.
6. The existing Agent, Dataset, and Workflow Cycle workspaces regress cleanly.
7. Focused tests, application tests, architecture tests, and independent QA pass.
8. The accepted exact commit is recorded before Phase 1 closes.

## Non-goals

- no artifact repository or governed deletion;
- no experiment workspace or multi-run scheduler;
- no production registry publication;
- no Studio–Codex process execution;
- no RavenPack/MCP/external adapter;
- no live or simulated financial effect.
