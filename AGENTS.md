# ServiceFabric Portfolio Risk — Agent Instructions

## Repository purpose

This repository is a bounded application overlay for portfolio-risk research,
monitoring, data ingestion, explainable findings, and agentic workflows built
against ServiceFabric's canonical contracts and runtime.

## Source-of-truth order

Read these sources in order before editing:

1. `AGENTS.md`
2. `docs/workplans/current.md`
3. the active workplan referenced there
4. `docs/architecture/adr/`
5. `config/agent/day0/lanes.json`
6. package-local contracts and tests

## Stable architecture rules

- `vendor/servicefabric/**` is a read-only pinned dependency.
- Never edit, format, commit inside, or advance the ServiceFabric submodule.
- Application adapters do not own risk calculations or tool business logic.
- ServiceFabric canonical invocation and result contracts remain authoritative.
- New execution paths must not bypass the canonical ServiceFabric runtime.
- Package, capability, tool, application, agent, finding, and alert identities
  remain distinct.
- Immutable snapshots and revisions are not overwritten in place.
- Provider credentials are opaque local references, never contract values.
- Agent output must identify evidence, assumptions, warnings, and limitations.
- Consequential actions require explicit human review.

## Financial safety boundary

- No live orders.
- No broker connectivity during Day 0 or Day 1.
- No automatic rebalancing.
- No representation that an alert is investment advice.
- No fabricated market, fundamental, news, or portfolio observations.
- Synthetic observations must be labelled synthetic.
- A failed or incomplete data query must never be represented as zero.
- Missing observations must remain missing or carry an explicit quality flag.

## Public-repository data boundary

Never commit:

- API keys, passwords, tokens, cookies, SSH material, or private endpoints;
- CRSP, Compustat, Bloomberg, RavenPack, Accern, or other licensed extracts;
- private portfolio statements or personal account data;
- local DuckDB, SQLite, Parquet, Arrow, Feather, or provider cache files;
- copyrighted PDFs without explicit redistribution rights.

Reviewed synthetic fixtures are allowed only under
`data/fixtures/synthetic/**`.

## Day 0 lane ownership

### Integration

Owns:

- root configuration;
- CI;
- dependency locks;
- shared architecture records;
- cross-module tests;
- wave state;
- merge decisions.

Branch: `integration/day0`

### Planning

Owns:

- `packages/risk_planning/**`
- `seed/knowledge-products/**`
- `docs/knowledge-products/**`
- focused tests for those paths

Branch: `feature/day0-planning`

### Data

Owns:

- `packages/risk_data/**`
- `connectors/**`
- `data/schemas/**`
- focused data tests

Branch: `feature/day0-data`

### Domain

Owns:

- `packages/risk_domain/**`
- `schemas/risk/**`
- contract tests

Branch: `feature/day0-domain`

### Application

Owns:

- `apps/portfolio-risk-workbench/**`
- focused application tests

Branch: `feature/day0-application`

### Capabilities and agents

Owns:

- `packages/risk_capabilities/**`
- `packages/risk_agents/**`
- focused capability and agent tests

Branch: `feature/day0-agents`

## Prohibited overlap

Specialist lanes must not modify:

- root dependency files;
- root Makefile;
- CI workflows;
- shared wave manifests;
- another lane's package;
- `vendor/servicefabric/**`;
- generated schema snapshots by hand.

Only the integration authority may accept or reject candidate commits.

## Standard workflow

1. Verify the current branch and worktree.
2. Read the active workplan.
3. Run `make preflight`.
4. Modify only lane-owned paths.
5. Run focused tests.
6. Run `git diff --check`.
7. Write or update the lane handoff.
8. Create focused candidate commits.
9. Stop without merging.

## Git safety

- Never work directly on `main`.
- Never force-push `main`.
- Never use `git clean -fdx`.
- Never reset or discard user changes.
- Do not merge specialist branches.
- Do not stage broad changes until `git status` has been reviewed.
- Report unexpected dirty files as a blocker.

## Codex safety

Use:

- `--sandbox workspace-write`
- `--ask-for-approval on-request`

Do not use:

- `--dangerously-bypass-approvals-and-sandbox`
- `--yolo`
- unrestricted filesystem access

No secret directory is granted to Codex.

## Completion report

Every handoff must record:

- lane and branch;
- base and head;
- changed paths;
- tests executed;
- evidence produced;
- deviations;
- blockers;
- limitations;
- rollback;
- recommended next action.
