# ServiceFabric connectors, adapters, MCP, and third-party integrations — discussion brief

- Status: conversation starter; implementation deliberately deferred
- Updated: 2026-08-03
- Scope: RavenPack, MCP servers, APIs, databases, event streams, third-party LangGraph services, and ChatGPT/Codex plugin surfaces

## 1. Purpose of the future discussion

Define how external systems become governed ServiceFabric capabilities without giving agents unrestricted credentials, arbitrary network access, raw provider SDKs, or temporally invalid data.

The discussion should decide:

1. what an adapter is;
2. what a capability owns versus what the adapter owns;
3. how authentication, licensing, rights, temporal eligibility, schemas, and receipts are enforced;
4. how MCP, APIs, databases, streams, and third-party agent services share one integration contract;
5. which integrations belong in development, experimental, persistent research, or future product profiles;
6. how integrations are tested, versioned, observed, suspended, and retired.

## 2. Starting architecture

```text
Agent
  → registered CapabilityDefinition
  → typed request and policy check
  → AdapterDefinition
  → MCP / API / database / event stream / third-party service
  → normalized canonical result
  → temporal, rights, quality, and provenance validation
  → capability receipt
  → context or artifact proposal
```

Agents do not receive raw credentials or unrestricted provider clients.

## 3. Candidate adapter families

- MCP server adapters;
- REST/GraphQL API adapters;
- local DuckDB/Parquet query adapters;
- governed SQL database adapters;
- event-stream and pub/sub adapters;
- document/retrieval adapters;
- RavenPack event/news adapter;
- market/fundamental provider adapters;
- third-party LangGraph execution adapters;
- ChatGPT/Codex plugin-backed tools where the deployment surface supports them.

## 4. Required adapter contract

Every adapter should declare:

- adapter ID, version, owner, and environment availability;
- integration family and endpoint identity;
- credential reference and authentication method;
- allowed operations and denied effects;
- input/output schemas;
- temporal fields and point-in-time filtering;
- data rights, redistribution, prompt, cache, and storage policy;
- rate limits, latency, timeout, retry, and circuit-breaker policy;
- pagination, row/column, token, and cost limits;
- normalization and canonical mapping rules;
- data-quality and missing-data behavior;
- provenance and capability receipt format;
- observability, health, suspension, and deprecation rules;
- synthetic fixture and contract-test strategy.

## 5. RavenPack questions

1. Which RavenPack products, entities, taxonomies, relevance/novelty fields, and event timestamps are available?
2. Which fields can be stored, displayed, summarized, sent to an LLM, or retained in experiment evidence?
3. Which time represents `observed_at`, `available_at`, provider revision, and retrieval?
4. How are updates, retractions, duplicates, and entity mappings represented?
5. Does the first slice use a pull query, historical file, or streaming interface?
6. How are event candidates routed into RiskEnvironmentContext theses and PortfolioEnvironmentOverlay relevance?
7. Which synthetic/public fixture can reproduce the contract in CI?

## 6. MCP questions

1. Is the MCP server local, remote, first-party, third-party, or user-installed?
2. Which tools/resources are safe for analytical agents?
3. Which calls require user approval?
4. How are tool schemas, annotations, authentication state, and server health discovered?
5. How are prompt-injection and untrusted-content boundaries enforced?
6. Can results enter the ERC/portfolio context directly, or only through a validated ContextPatch?
7. How are MCP server versions and changed tool schemas detected?

## 7. Third-party LangGraph and agent services

Evaluate an integration only if it provides a measurable advantage in orchestration, persistence, observability, deployment, or evaluation.

Review:

- state and checkpoint compatibility;
- event/trace export;
- tool and capability contracts;
- human checkpoints;
- policy enforcement;
- model/provider portability;
- data location and privacy;
- cost and operational dependency;
- deterministic replay and version pinning;
- ability to map outputs back to ServiceFabric canonical artifacts.

ServiceFabric business contracts should remain authoritative even when execution is delegated to a framework provider.

## 8. ChatGPT plugins and Codex extensions

Clarify whether the integration is:

- a ServiceFabric capability exposed to ChatGPT through MCP/plugin packaging;
- a third-party connector used by a development Codex task;
- a user-facing ChatGPT app;
- a repository skill used only for authoring;
- an external data connector used by analytical workflows.

These have different authentication, UI, approval, and deployment boundaries and should not share one generic “plugin” flag.

## 9. Capability Studio implications

The future Capability Studio should support:

- attach an existing AdapterDefinition;
- inspect authentication and health without exposing secrets;
- select operations and schemas;
- define input preparation and normalization;
- generate synthetic examples and tests;
- document rights and temporal behavior;
- run an isolated capability test;
- publish a candidate CapabilityDefinition;
- compare versions and usage receipts;
- list proposed, in-progress, validated, published, deprecated, and retired capabilities.

## 10. Proposed phased conversation

### Conversation A — common adapter contract

Freeze identity, schemas, credentials, rights, time, receipts, health, and environment profiles.

### Conversation B — local DuckDB/database adapter

Use the working query facility as the reference implementation for read-only, temporally bounded local data access.

### Conversation C — MCP adapter

Implement discovery, tool selection, authentication status, approval, normalization, and receipt handling.

### Conversation D — RavenPack

Map licensing, timestamps, entities, events, revisions, and CI fixtures before UI or agent work.

### Conversation E — third-party LangGraph/services

Compare operational value and contract compatibility; integrate only a bounded execution adapter if justified.

### Conversation F — plugin/application surfaces

Decide whether any capability should also be distributed through a ChatGPT/Codex plugin or external app surface.

## 11. Exit criteria for the discussion

The adapter architecture is ready for implementation only when:

- one common adapter contract is approved;
- rights and temporal rules are testable;
- secrets remain opaque references;
- agents cannot bypass registered capabilities;
- normalized results and receipts are defined;
- failure and missing-data behavior is explicit;
- development, experiment, and future product availability are separated;
- a local synthetic fixture can test every adapter family;
- RavenPack-specific questions have documented answers;
- ServiceFabric retains canonical ownership of business objects and decisions.
