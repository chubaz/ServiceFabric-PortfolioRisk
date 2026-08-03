# ServiceFabric Labs — architecture and phased development roadmap

- Status: maintained architecture and development skeleton
- Updated: 2026-08-03
- Scope: ServiceFabric PortfolioRisk research and development application
- Current authority: planning only; this file does not enable live orders, broker connectivity, or portfolio effects

## 1. Purpose

This document consolidates the direction for the ServiceFabric Labs application after the Agent Studio, Dataset Lab, Workflow Cycle, live run review, and early dashboard prototypes.

The objective is to build a system in which users can:

1. create and publish reusable agents, capabilities, evaluations, reports, dashboards, scenarios, mandates, theses, and workflows;
2. assemble isolated portfolio experiments from immutable versions of those objects;
3. run experiments interactively or headlessly, including large experiment sets;
4. inspect agent work, evidence, decisions, consequences, and persistent outputs;
5. use a development-only Studio–Codex bridge to turn approved proposals into tested code or declarative artifacts;
6. progressively build a financial risk-environment view that exists independently of the portfolio and can later be mapped onto it;
7. preserve thesis-grade lineage across inputs, calculations, prompts, capabilities, decisions, outputs, and later outcomes.

The system is not a collection of one-off agent demos. It is a governed authoring, experiment, persistence, and evaluation environment.

### 1.1 Unified application operating zones

The application now projects the existing services into three explicit zones:

- **System Development** creates and fixture-tests reusable definitions, then saves them in the Registry;
- **Agent Application** loads saved definitions into a labelled fixture context and exposes the agent/object work record;
- **Experimental Research** composes only saved definition versions into persistent experiments and comparisons.

The normative terminology, movement rules, backend reuse and later-phase dependency reminders are maintained in [`docs/architecture/platform-operating-zones.md`](../../../docs/architecture/platform-operating-zones.md). Every later phase must preserve the distinction among reusable definitions, Fixture Contexts, temporary run work products, retained artifacts and experiments.

## 2. Product principles

### 2.1 Separate meaning, execution, and persistence

The system must not flatten these concepts:

- **Definition**: what an agent, capability, mandate, workflow, scenario, dashboard, or evaluation is.
- **Assignment**: the portfolio, dates, question, event, and parameters for one invocation.
- **Experiment**: the isolated environment in which definitions and assignments are composed and executed.
- **Run**: one execution attempt with immutable receipts.
- **Artifact**: a report, table, chart, dashboard page, decision proposal, context patch, or other output produced by a run.
- **Published asset**: an approved reusable version available to later experiments.
- **Persistent workspace object**: a mandate, thesis, dashboard, report, or monitoring package intentionally carried forward over time.

### 2.2 Findings, decisions, and actions remain distinct

```text
Evidence
  → Finding
  → Decision Proposal
  → Decision
  → Workflow or simulated action
  → Observed outcome
```

Accepting a proposal does not imply an undeclared action. Every effect must be previewed, policy-compatible, and represented by a separate receipt.

### 2.3 Runtime agents propose; the development harness builds

Normal analytical agents may identify a missing capability, weak dashboard, unsuitable report structure, or useful specialist agent. They should create a typed `ArtifactChangeProposal`; they should not edit the codebase directly.

The development-only Studio–Codex bridge may turn an approved proposal into code, tests, documentation, and a candidate registry entry.

### 2.4 Rich agent outputs are narrative and structured

Agent reports should communicate a financial message. Machine-readable schemas remain underneath, but the primary text is concise Markdown with meaningful hierarchy, evidence, uncertainty, and decision implications.

### 2.5 Real, synthetic, and simulated states are always visible

Every run and artifact must state whether it uses:

- licensed real data;
- public real data;
- reviewed synthetic fixtures;
- simulated intraday evolution anchored to real observations;
- mixed inputs.

No failed or absent observation is represented as zero, and no synthetic observation is presented as real.

## 3. Operating profiles and lifecycle boundaries

The term “persistent” describes an artifact lifecycle. It is not the same as a deployment environment. The application should expose three primary operating profiles and one future product profile.

### 3.1 Development profile

Purpose: create, change, test, and load ServiceFabric definitions and code.

Characteristics:

- localhost or explicitly controlled development environment;
- Studio–Codex gateway enabled;
- candidate registry visible;
- source code and declarative definitions may change through approved tasks;
- code-mutating tasks run in isolated Git worktrees;
- tests, diffs, validation receipts, and merge approval are mandatory;
- no live portfolio or external market effects;
- unpublished definitions cannot be mistaken for system assets.

Only this profile should expose Studio–Codex code-authoring controls.

### 3.2 Experimental profile

Purpose: run reproducible research on fictitious or historically replayed portfolios.

Characteristics:

- experiment references immutable registry versions;
- an experiment may add experiment-local configuration overlays without modifying the system registry;
- runtime agents cannot edit application code;
- a policy-bound deciding agent may resolve selected decisions;
- a supra-agent may substitute for the user only inside an explicitly labelled experiment;
- simulated portfolio mutation and simulated orders may be allowed only against a fictitious portfolio and a simulation ledger;
- external communication, brokers, venues, and live portfolio effects remain denied;
- results preserve policy, context, model, prompt, tool, and decision lineage.

The current Thesis Sprint workplan prohibits portfolio mutation. Enabling simulated mutation therefore requires a later, explicit architecture decision, contract, safety test, and new workplan. It is not enabled by this roadmap.

### 3.3 Persistent research profile

Purpose: retain approved definitions, mandates, theses, monitoring packages, dashboards, reports, and experiment evidence for reuse.

Characteristics:

- published registry versions are immutable;
- persistent portfolio workspaces may carry forward approved dashboards, reports, mandates, theses, subscriptions, and monitoring strategies;
- users can archive, supersede, clone, or retire assets;
- code changes still occur only through the development profile;
- all loaded assets disclose version, provenance, status, and compatibility.

### 3.4 Future front-facing product profile

Purpose: demonstrate or operate approved product workflows without exposing development machinery.

Characteristics:

- published definitions only;
- Studio–Codex disabled;
- human review remains explicit;
- raw manifests and receipts remain inspectable under developer/audit views;
- production policy is narrower than experimental policy;
- no simulated state is confused with live state.

## 4. Registry and archive architecture

### 4.1 One registry, several lifecycle views

The application should present a unified catalogue while retaining separate lifecycle states:

```text
Draft
  → Candidate
  → Validated
  → Published
  → Deprecated
  → Retired

Any non-published version may also be archived.
```

The catalogue contains at least:

- CapabilityDefinition;
- AgentBlueprint;
- AgentGraphDefinition;
- WorkflowDefinition;
- EvaluationSuite;
- ReportTemplate;
- DashboardPackage;
- VisualisationDefinition;
- ScenarioDefinition;
- MandateVersion;
- RiskThesis / InvestmentThesis;
- MonitoringStrategy and SubscriptionPack;
- ContextPack, CapabilityPack, OutputContract, AutonomyProfile, and RuntimeProfile.

### 4.2 Storage responsibilities

Use the smallest storage surface appropriate to each type:

| Surface | Stores | Does not store |
|---|---|---|
| Git | reviewed code, schemas, declarative definitions, skills, tests, documentation | licensed data, run outputs, secrets |
| Registry metadata database | identity, version, state, compatibility, ownership, lineage, tags, provenance | large files and raw datasets |
| Graph relations | typed links among mandates, rules, theses, evidence, portfolios, capabilities, decisions, and workflows | duplicated authoritative payloads |
| Artifact repository | reports, charts, dashboards, run files, evidence bundles, rendered Markdown/HTML | registry meaning without metadata |
| Experiment data plane | snapshots, Parquet results, capability receipts, model-call ledgers, evaluation records | reusable definitions unless explicitly promoted |

For the local prototype, registry metadata and graph edges can live in explicit relational tables while large artifacts remain in governed filesystem directories. A specialist graph database is not required before graph queries and scale justify it.

### 4.3 Artifact identity and deduplication

Every stored artifact should carry:

- artifact ID and type;
- semantic version or immutable revision;
- content digest;
- creator and creation method;
- source definition versions;
- experiment/run association, if any;
- data and evidence boundary;
- real/synthetic/simulated state;
- retention class;
- publication state;
- parent and supersession links;
- human approvals.

Content-addressed storage or digest-based deduplication prevents repeated experiments from storing identical large artifacts multiple times.

### 4.4 Retention classes

| Class | Intended use | Default treatment |
|---|---|---|
| Ephemeral | temporary logs, previews, intermediate renderings | delete after run or short TTL |
| Run-retained | artifacts needed to inspect one saved run | retain with run; deletable through governed cleanup |
| Experiment evidence | inputs, outputs, decisions, and evaluations required for reproducibility | retain until experiment/archive policy permits deletion |
| Published | reusable approved definition or artifact | immutable; supersede rather than overwrite |
| Evidence-locked | thesis or release evidence required for audit | deletion requires explicit policy and receipt |

Deletion should remove eligible files and mark the metadata record deleted or tombstoned. It must not leave active registry references pointing to absent artifacts.

## 5. Experiment architecture

### 5.1 Experiment as a first-class isolated workspace

An `ExperimentDefinition` should bind:

- name, purpose, hypothesis, and owner;
- start/end dates and replay schedule;
- portfolio and snapshot-selection policy;
- effective mandate version;
- data revisions and eligibility boundary;
- agent, graph, workflow, capability, scenario, dashboard, and evaluation versions;
- model/runtime/pricing policy;
- decision and autonomy policy;
- real/synthetic/simulated configuration;
- retention and publication policy;
- cost, concurrency, and storage budgets.

An experiment references system assets by immutable version. Experiment-local overrides are explicit overlays, not silent copies.

### 5.2 Experiment lifecycle

```text
Draft
  → Validated
  → Ready
  → Running
  ↔ Paused for decision
  → Completed / Failed / Cancelled
  → Reviewed
  → Archived
  → Eligible for governed deletion
```

### 5.3 Interactive and headless modes

An experiment can use one of three presentation modes:

- **Interactive foreground**: live clock, dashboards, agent work, capability calls, and decision pauses.
- **Background/headless**: no dashboard rendering, minimal narrative, structured outputs and receipts only.
- **Evaluation-only**: consumes already completed outputs to rerun labels, metrics, or comparisons without agent calls.

The computational workflow remains the same. Presentation and meta-capability availability vary by mode.

### 5.4 Experiment sets

An `ExperimentSet` groups independent experiments or a parameter matrix:

- shared research question;
- controlled factors;
- variable factors;
- random seeds;
- repeat counts;
- budget and concurrency limits;
- shared evaluation suite;
- aggregation and comparison rules.

This is the correct unit for hundreds of experiments. A set owns scheduling and comparison, while each experiment retains its own immutable state and outputs.

### 5.5 Concurrent execution and storage

Hundreds of experiments should not imply hundreds of open browser sessions or dashboards.

Use:

- a queue and bounded worker pool;
- per-experiment resource and model-call budgets;
- headless mode by default for batch runs;
- deterministic resumability and idempotent task keys;
- shared immutable input snapshots;
- digest-based artifact deduplication;
- columnar result tables for cross-run analysis;
- explicit quotas and retention policies;
- a single experiment-set status view.

The front-facing development experiment is only a pointer to one selected foreground experiment. Background experiments continue without visual rendering.

## 6. Markdown-first analytical reports

### 6.1 Output contract

Reports should be stored as a structured envelope with Markdown sections:

```yaml
report_id: ...
report_type: DailyPortfolioRiskReview
as_of: ...
outcome_sought: ...
sections:
  - section_id: executive_message
    title: Executive message
    markdown: |
      **Primary conclusion:** ...
    evidence_ids: [...]
    severity: material
artifacts: [...]
warnings: [...]
limitations: [...]
```

The structured envelope supports validation and reuse. Markdown provides readable hierarchy.

### 6.2 Recommended report language

Use Markdown intentionally:

- headings for distinct conclusions;
- bold text for the principal message, not every noun;
- short bullets for evidence or actions;
- tables for comparisons and thresholds;
- blockquotes for explicit warnings or decision implications;
- inline evidence links or stable evidence IDs;
- compact paragraphs that state what changed, why it matters, and what follows.

Avoid:

- repeated explanations of how the software works;
- long generic introductions;
- redundant restatement of metrics;
- raw JSON or codes as the primary presentation;
- arbitrary HTML, JavaScript, or unsanitized model-produced markup.

### 6.3 Default financial report structure

1. **Outcome sought**
2. **Executive message**
3. **What changed**
4. **Risk mechanisms and non-trivial findings**
5. **Portfolio and mandate relevance**
6. **Evidence, models, and scenario results**
7. **Counter-evidence, uncertainty, and limitations**
8. **Decision implications**
9. **Recommended monitoring or next work**

The user or agent may replace this structure through an Output Contract. Iterative runs may fill separate sections, but each section is validated and assembled into one artifact rather than appended as uncontrolled prose.

### 6.4 Report meta-capabilities

Initial report meta-capabilities should include:

- `report.plan_sections`;
- `report.compose_markdown`;
- `report.check_evidence_coverage`;
- `report.check_repetition_and_length`;
- `report.render_sanitized_html`;
- `report.attach_table_or_chart`;
- `report.publish_candidate`.

Charts and dashboards enter reports through registered artifact references. The model does not directly execute arbitrary HTML or JavaScript.

## 7. Meta-capability proposals and Studio–Codex

### 7.1 Runtime proposal contract

An agent that needs a new or modified capability, visualisation, dashboard, report, scenario, workflow, or specialist agent should produce an `ArtifactChangeProposal` containing:

- target artifact type and current version;
- problem and desired outcome;
- evidence from the run;
- proposed behavior and user value;
- required inputs and expected outputs;
- affected interfaces and dependencies;
- safety, rights, temporal, and authority constraints;
- acceptance tests;
- suggested ServiceFabric authoring skill;
- urgency and expected reuse;
- whether a declarative change may be sufficient.

The proposal appears in a user-owned queue. It does not mutate the registry or codebase.

### 7.2 When a Git worktree is necessary

Use a worktree when the approved task:

- edits application or package code;
- changes schemas or contracts;
- changes tests or dependencies;
- creates a new executable capability;
- may run in parallel with other development work.

A worktree is optional when the change is purely:

- a draft description;
- a registry tag or non-executable metadata edit;
- an experiment-local configuration;
- a report/dashboard parameter change already supported by a published definition.

Codex worktrees isolate parallel chats and share Git metadata with the main checkout. The official Codex documentation also notes that branches can be checked out in only one worktree at a time and that managed worktrees may be cleaned up after their associated chat is archived. ServiceFabric should therefore manage candidate branches and cleanup explicitly rather than assume every proposal requires a permanent worktree.

### 7.3 Development-only gateway

```text
Agent or user proposal
  → human approves authoring request
  → Studio compiles a bounded CodexAssignment
  → backend gateway chooses declarative path or code-worktree path
  → Codex thread runs with repository skill + AGENTS.md + narrow sandbox
  → tests and validation run
  → diff, receipts, candidate manifest, and preview return to Studio
  → human accepts, revises, or rejects
  → accepted candidate merges to the working integration branch
  → development registry reloads
  → localhost smoke test
  → optional commit/push/PR
  → task archived and worktree becomes eligible for cleanup
```

The browser must not post arbitrary terminal commands. The backend owns a narrow command allowlist and the Git lifecycle.

### 7.4 Worktree and merge lifecycle

1. Resolve the exact base/integration branch and confirm its state.
2. Create a unique candidate task and worktree for code-mutating work.
3. Start the Codex thread with the worktree as `cwd`.
4. Invoke the relevant repository skill explicitly.
5. Run required tests and produce a bounded diff.
6. Present the diff, artifacts, limitations, and validation results.
7. Require human approval before promotion.
8. Commit the candidate so the work is reachable before cleanup.
9. Merge through an integration authority; do not merge directly to `main`.
10. Reload the development registry and run a localhost smoke test.
11. On success, mark the candidate published in development or prepare a PR.
12. On failure, deactivate/revert the candidate and retain the worktree for diagnosis.
13. Remove the worktree only when the commit is reachable, no task is active, and cleanup is approved by policy.

Worktree deletion should use governed Git worktree operations, never a broad recursive filesystem deletion.

### 7.5 Codex integration surface

The recommended integration is server-side:

- the Codex SDK can start, continue, and resume local coding threads;
- Codex app-server supports authentication, thread history, approvals, per-turn working directories and sandbox policies, streamed messages, tool events, file changes, and unified diffs;
- repository `AGENTS.md` supplies durable repository constraints;
- repository skills under `.agents/skills` supply reusable ServiceFabric authoring procedures;
- the Studio stores Codex thread/task IDs and displays streamed progress without exposing an unrestricted shell.

Official Codex sources:

- [Codex SDK](https://learn.chatgpt.com/docs/codex-sdk.md)
- [Codex app-server](https://learn.chatgpt.com/docs/app-server.md)
- [Codex worktrees](https://learn.chatgpt.com/docs/environments/git-worktrees.md)
- [Build skills](https://learn.chatgpt.com/docs/build-skills.md)
- [Custom instructions with AGENTS.md](https://learn.chatgpt.com/docs/agent-configuration/agents-md.md)
- [Subagent operations](https://learn.chatgpt.com/docs/agent-configuration/subagents.md)

## 8. Decision Cards and due-diligence workspaces

### 8.1 Decision Card

A Decision Card should lead with the financial question and its consequence:

- decision question;
- why it exists now;
- proposing agent and workflow;
- recommendation and alternatives;
- mandate and policy relevance;
- portfolio relevance;
- risk-environment relevance;
- expected consequence of every outcome;
- evidence and source coverage;
- models, scenarios, and capability receipts;
- counter-evidence and specialist disagreement;
- uncertainty, missing information, and expiry;
- authority level and eligible resolvers;
- downstream workflow preview;
- current lifecycle state and notifications.

### 8.2 Due-diligence page

Opening a card creates a human-owned `DecisionDueDiligenceWorkspace` anchored to the immutable proposal context.

The user can:

- inspect every input, evidence item, capability call, and artifact used by the proposer;
- ask questions without changing the original proposal;
- run ad-hoc registered capabilities;
- assemble a temporary investigation workflow;
- attach specialist agents chosen by the human;
- compare alternative scenarios or theses;
- request a counter-thesis or independent validation;
- save useful results as supplemental evidence;
- revise the decision proposal while preserving prior versions;
- resolve, defer, reject, escalate, or request further investigation.

The due-diligence workspace is not automatically promoted into a reusable system asset. The user may explicitly save a workflow, report, scenario, or dashboard candidate to the registry.

### 8.3 Deciding agent and supra-agent

Two roles are required:

- **Deciding agent**: may resolve defined decision classes according to a human-authored policy. It must notify the user and preserve its decision rationale, evidence, policy version, and consequence.
- **Supra-agent**: substitutes for the human only in an explicitly isolated experiment. It may coordinate agents, choose workflows, resolve decisions, and—if a future policy permits—create simulated portfolio mutations or simulated orders against a fictitious ledger.

Neither role can define or expand its own authority.

A future simulated-effect permission should require all of:

```text
environment = experiment
portfolio_kind = fictitious
execution_adapter = simulation_ledger
external_communication = denied
broker_connectivity = denied
policy_version = human_approved
full_receipts = required
user_notification = required
```

## 9. Risk-context architecture — revised boundary

The earlier EnvironmentRiskContext concept conflated the general financial environment with the portfolio-specific application of that environment. The attached risk-environment analysis requires a stronger separation.

### 9.1 Provisional context family

#### A. RiskEnvironmentContext

An independent, point-in-time, versioned belief about global macro, meso, and micro risk mechanisms.

It contains:

- regime hypotheses;
- risk drivers and mechanisms;
- causal and transmission graph;
- macro, meso, and micro risk theses;
- indicators and observations;
- eligible evidence;
- supporting and contradicting findings;
- direction, velocity, propagation, proximity, and uncertainty;
- subscriptions and monitoring strategy;
- unresolved questions and alternative theses.

It exists even when no current portfolio is exposed.

#### B. PortfolioContext

The point-in-time portfolio state and its governing constraints:

- positions, quantities, cash, valuations, and mappings;
- exact data revisions and quality state;
- effective Portfolio Mandate and covenants;
- deterministic portfolio metrics and findings;
- portfolio-specific theses and persistent objects.

#### C. PortfolioEnvironmentOverlay

A provisional third context that maps selected environment mechanisms onto the portfolio:

- relevant drivers and transmission channels;
- position, issuer, sector, country, factor, duration, credit, and liquidity sensitivities;
- plausible propagation paths;
- affected mandate objectives and covenants;
- model/scenario evidence;
- portfolio materiality;
- unanswered transmission questions.

This is the refined environment as applied to the portfolio. It should not overwrite the independent RiskEnvironmentContext.

#### D. OverallDefaultContext

A reproducible composition for a specific workflow cycle:

```text
PortfolioContext
  + effective MandateContext
  + relevant PortfolioEnvironmentOverlay
  + eligible event/news context
  + current decisions and outcomes
  + persistent dashboard/report/thesis pointers
  = OverallDefaultContext
```

#### E. DecisionContext

A task-specific, immutable narrowing of the OverallDefaultContext plus the current proposal, deadline, evidence, and unresolved questions.

### 9.2 Open architecture placeholder

The names, precise composition rules, and graph ownership are not final. Before implementation, decide:

- whether `PortfolioEnvironmentOverlay` is an independent versioned context or a layer attached to PortfolioContext;
- whether OverallDefaultContext is persisted or compiled on demand from immutable pointers;
- which context owns portfolio-specific risk theses;
- how changes in the independent environment invalidate or refresh overlays;
- how a user and specialist council propose, challenge, and approve environment theses;
- how RiskEnvironmentContext subscriptions interact with RavenPack and future external adapters;
- how task-specific ContextViews remain token-efficient.

No new monolithic context object should be created until these decisions are settled against existing canonical objects.

## 10. Labs and user workspaces

### 10.1 Mandate Lab

Create, import, distil, test, approve, version, and inspect portfolio mandates and graph-backed covenants. The first slice is already defined in the decision register.

### 10.2 Theses Lab

Maintain investment and risk theses with mechanisms, assumptions, evidence, counter-evidence, indicators, invalidation conditions, horizons, confidence, and review cadence.

### 10.3 Risk Environment Lab

Maintain the independent macro/meso/micro environment view, causal graph, risk theses, monitoring strategies, subscriptions, specialist discussions, and historical snapshots.

### 10.4 Decision Lab

Search and compare Decision Cards, open due-diligence workspaces, inspect policy and consequences, and review later outcomes.

### 10.5 Registry and Experiment Lab

Browse reusable assets, compare versions, create experiments and experiment sets, configure foreground/headless mode, monitor budgets, and control retention.

These Labs share components with Agent Studio and the future Agent Graph Studio. They do not collapse every object into one page.

## 11. Phased implementation plan

Each phase must produce a visible, testable increment. Parallel Codex tasks should be used only for bounded, non-overlapping work. One integration task owns shared contracts and merges.

### Phase 0 — Baseline and terminology freeze

- approve operating profiles and lifecycle vocabulary;
- inventory existing canonical objects and registries;
- mark current one-off fixture/run behavior explicitly;
- freeze the context architecture questions that remain open;
- add architecture tests that prevent development controls in non-development profiles.

Parallel tasks:

- read-only canonical-object inventory;
- storage/run-directory inventory;
- UI terminology audit;
- current policy and lifecycle audit.

### Phase 1 — Registry kernel

- introduce a unified registry index over existing definitions;
- implement candidate, validated, published, deprecated, retired, and archived states;
- add version comparison, lineage, compatibility, and provenance;
- surface agents, capabilities, evaluations, reports, dashboards, scenarios, and workflows first.

Parallel tasks:

- registry contracts and persistence;
- registry catalogue UI;
- import/migration of existing definitions;
- validation and architecture tests.

### Phase 2 — Artifact repository and run persistence

- create typed artifact manifests and retention classes;
- give every isolated run a stable folder/repository identity;
- support browse, download, save, archive, and governed deletion;
- distinguish intermediate, run-retained, published, and evidence-locked files.

### Phase 3 — Experiment workspace

- create ExperimentDefinition and ExperimentSet views over existing canonical contracts;
- separate system assets, experiment-local overlays, run outputs, and promoted artifacts;
- implement foreground, headless, and evaluation-only modes;
- add budgets, queue state, resumability, and experiment-set comparison.

Parallel tasks:

- experiment contracts and validation;
- scheduler/worker prototype;
- experiment UI;
- storage/retention tests.

### Phase 4 — Markdown report composer

- make Markdown sections the default narrative report surface;
- add section planning, repetition checks, evidence checks, and safe HTML rendering;
- support iterative section completion and registered chart/table attachments;
- update Agent Run Review and Daily Portfolio Risk Review.

### Phase 5 — Decision Review v1

- implement structured Decision Proposals and lifecycle;
- pause the Workflow Cycle at material decisions;
- render concise Decision Cards;
- support human investigate, accept-and-monitor, defer, reject, and escalate outcomes;
- create one effect-free follow-up workflow and an updated context revision.

### Phase 6 — Decision due-diligence workspace

- open a dedicated page from any Decision Card;
- expose evidence, artifacts, capability receipts, mandate/policy, and alternatives;
- let the user assemble a temporary investigation workflow;
- preserve supplemental evidence and proposal revisions.

### Phase 7 — Context boundary prototype

- implement read-only panels for RiskEnvironmentContext, PortfolioContext, provisional PortfolioEnvironmentOverlay, OverallDefaultContext, and DecisionContext;
- show provenance and differences without creating a new monolithic store;
- measure token-efficient task-specific ContextViews;
- return unresolved graph-ownership questions for human decision.

### Phase 8 — Complete the Daily Portfolio Risk Review vertical slice

- deterministic context assembly;
- capability input preparation and reuse ledger;
- genuine LLM agent work record;
- Markdown report and live dashboard artifacts;
- decision point, investigation, and multi-day carry-forward;
- synthetic and real-data isolated tests.

### Phase 9 — Mandate Lab

- build describe/import, AI candidate extraction, structured review, rule preview, tests, and immutable draft version;
- add mandate graph relations by reusing canonical nodes;
- compile task-specific MandateContext;
- evaluate eligibility and concentration rules in replay.

### Phase 10 — Theses and Risk Environment Labs

- create structured risk theses and monitored indicators;
- add causal/transmission graph views;
- add Risk Strategist sessions and specialist challenge;
- compile monitoring subscriptions;
- create PortfolioEnvironmentOverlay proposals.

### Phase 11 — Meta-capability proposal queue

- let agents propose new or modified artifacts;
- show proposals in Agent Studio, Capability Studio, Dashboard workspace, and Decision due diligence;
- add human approval, rejection, amendment, and prioritization;
- route declarative proposals without code to the candidate registry.

### Phase 12 — Studio–Codex gateway

- development profile only;
- server-side SDK/app-server integration;
- streamed task work and approvals;
- worktree lifecycle and integration-branch promotion;
- development registry reload and smoke test;
- audit and cleanup.

Parallel tasks:

- gateway and thread persistence;
- Git/worktree controller;
- Studio task/review UI;
- security and sandbox tests.

### Phase 13 — Repository authoring skills

- capability author;
- agent author;
- visualisation author;
- dashboard package author;
- report author;
- scenario author;
- workflow author;
- mandate author;
- thesis/risk-environment author;
- evaluation author.

Each skill must encode canonical object reuse, lane ownership, tests, documentation, rights, temporal integrity, and registry publication.

### Phase 14 — Agent Graph and workflow composition

- create modular agent-graph definitions;
- validate state, routes, tools, authority, outputs, and human checkpoints;
- compose multiple graphs within one workflow cycle and date;
- support framework-specific runtime adapters without changing business contracts.

### Phase 15 — External adapters and RavenPack

- complete the separate [connectors, adapters, and integrations discussion](EXTERNAL_ADAPTERS_DISCUSSION_BRIEF.md);
- implement governed MCP/API/database/event adapters;
- add RavenPack under temporal, rights, and licensing controls;
- evaluate selected third-party LangGraph integrations only after compatibility and provenance review.

### Phase 16 — Experimental deciding and supra-agent profiles

- implement human-authored resolver policy;
- compare human and deciding-agent resolutions;
- add a supra-agent only in isolated experiments;
- introduce simulated effects only after a new safety contract and workplan;
- notify the user and retain full receipts for every autonomous decision.

### Phase 17 — Batch experimental apparatus

- execute hundreds of headless experiments through ExperimentSets;
- support framework, prompt, model, capability, policy, and workflow comparisons;
- add human review sampling and outcome labels;
- report cost, latency, reliability, grounding, decision quality, and artifacts.

### Phase 18 — UX/UI consolidation and front-facing demonstration

- polish each Lab after its workflow is stable;
- create coherent navigation from portfolio and mandate to environment, workflow, decisions, and outputs;
- keep developer/audit detail progressively disclosed;
- produce a front-facing demonstration without Studio–Codex controls.

### Phase 19 — Thesis evaluation, hardening, and release decisions

- freeze experiment protocols;
- run descriptive and later statistically justified evaluations;
- compare agentic frameworks without overclaiming;
- document limitations, security boundaries, and product implications;
- make explicit human release decisions.

## 12. Parallel Codex task discipline

Use separate Codex tasks when work is independent and has a clear ownership boundary. Recommended task lanes per phase:

- contracts and architecture;
- persistence and migrations;
- backend/runtime;
- frontend/interaction;
- evaluation and fixtures;
- independent QA/review.

Rules:

1. One task owns each shared contract or migration.
2. Parallel write tasks use separate worktrees and branches.
3. Read-heavy exploration and test review can run in parallel more freely.
4. Every task has explicit allowed paths, required tests, and an output manifest.
5. A single integration task resolves conflicts and promotes candidates.
6. Tasks stop without merging unless they hold integration authority.
7. The main planning task retains decisions and final summaries; raw logs remain in specialist tasks.
8. Parallelism is bounded by dependency order, cost, and merge risk—not by the maximum available number of chats.

## 13. Immediate next decisions

Before programming the registry/experiment skeleton, settle:

1. the exact names of the three operating profiles;
2. whether the registry initially stores only metadata/pointers or also declarative payloads;
3. the local artifact repository root and retention defaults;
4. whether experiment-local overrides may be promoted directly or must become candidates;
5. the minimal Markdown report contract;
6. the Decision Card and due-diligence v1 scope;
7. the provisional context-family names and which context is compiled versus persisted;
8. the development integration branch used by Studio–Codex;
9. who can approve Codex authoring, merge, development loading, and cleanup;
10. whether simulated portfolio mutation is in thesis scope or a later research extension.

The renewed decision register records these questions in structured form.
