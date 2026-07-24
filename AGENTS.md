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
- `docs/handoffs/day-0/planning.md`

Branch: `feature/day0-planning`

### Data

Owns:

- `packages/risk_data/**`
- `connectors/**`
- `data/schemas/**`
- focused data tests
- `docs/handoffs/day-0/data.md`

Branch: `feature/day0-data`

### Domain

Owns:

- `packages/risk_domain/**`
- `schemas/risk/**`
- contract tests
- `docs/handoffs/day-0/domain.md`

Branch: `feature/day0-domain`

### Application

Owns:

- `apps/portfolio-risk-workbench/**`
- focused application tests
- `docs/handoffs/day-0/application.md`

Branch: `feature/day0-application`

### Capabilities and agents

Owns:

- `packages/risk_capabilities/**`
- `packages/risk_agents/**`
- focused capability and agent tests
- `docs/handoffs/day-0/agents.md`

Branch: `feature/day0-agents`

## Day 1 preparation and lanes

Day 1 preparation is integration-owned on `chore/day1-preparation`. Before
any Day 1 implementation, review `docs/workplans/current.md` and the active
workplan it names. The Day 1 integration order is:

`domain-analytics` -> `knowledge` -> `data` -> `agents` -> `experience` -> `integration`.

Day 1 lanes are recorded in `config/agent/day1/lanes.json`. Specialist lanes
must change only their explicit directories and their one exact handoff file;
they stop without merge. The three Day 1 waves are human-readable workbench
(1A), portfolio/data workspace (1B), and risk analysis/explainability (1C).

During Day 1, raw JSON remains available as developer/evidence APIs but is
prohibited as the primary user presentation. Server-rendered semantic HTML,
local CSS, progressive enhancement, keyboard access, and visible
synthetic/profile/human-review disclosures are required. Arbitrary SQL,
notebook execution, remote UI assets, external providers, external LLMs,
broker connectivity, live portfolio effects, orders, trades, and rebalancing
are prohibited. Notebook pages are catalogue-only and any provider secret is
an opaque local reference.

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

## Day 2–3 three-part programme

The completed Part 1 workplan is
`docs/workplans/day-2-3/phase-1-local-research-data-plane.md`. The active
workplan is `docs/workplans/day-2-3/part-2-portfolio-event-monitoring-replay.md`
and lifecycle state is authoritative in `config/agent/day23/status.json`.
The former four-phase plan is superseded. The programme has exactly three
parts: Part 1, the complete governed local research data plane; Part 2, in
progress, for portfolio-linked datasets, local event intelligence, monitoring
policies, four-agent monitoring, historical replay, evaluation, reports, and
Workbench workflows; and Part 3, queued, for final human QA, evidence review,
release decision, and merge.

Day 2–3 has exactly three lanes: `integration/day2-3`,
`feature/day23-monitoring-core`, and `feature/day23-monitoring-experience`.
Ownership and exact handoff allowances are frozen in
`config/agent/day23/lanes.json`. Specialist lanes stop without merge. The
integration order is `monitoring-core` -> `experience` -> `integration`.

Phase 1 is a governed local research data plane, not provider-data product
implementation. Its landing, normalized, curated, manifests, quality, and
evidence zones are mutable outside Git. Fixed query manifests are required;
user SQL, notebook execution, external API calls, provider network access,
broker connectivity, orders, trades, and automatic rebalancing are prohibited.
Every record preserves provider/dataset identity and revision, rights and
access state, source digest/schema/mapping/units/transformations,
`observed_at`, `available_at`, `retrieved_at`, point-in-time `as_of`, quality,
immutable snapshot, date-effective crosswalk, manifest, and publication
restriction. Point-in-time filtering uses `available_at`; missing availability
blocks or warns and is never guessed. Credentials remain opaque references.

Part 2 additionally prohibits a background scheduler, arbitrary policy
expressions, fuzzy or ticker-based entity matching, look-ahead, external
providers, external LLMs, broker connectivity, orders, trades, and automatic
rebalancing. Cadence is metadata only; all consequential actions require
explicit human review.

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
