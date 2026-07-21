# D0-WAVE-0A: Foundation Freeze and Executable Skeleton

- Status: active
- Integration branch: `integration/day0`
- Base: `day0-prepared`

## Objective

Freeze the shared Day 0 execution conventions and create the minimal,
reproducible harness required for bounded parallel implementation. This wave
establishes contracts and package skeletons only; it does not implement
portfolio-risk behavior, provider integrations, or executable agent actions.

## Lane scopes

| Lane | Owned implementation scope | Canonical handoff |
| --- | --- | --- |
| Domain | `packages/risk_domain/**`, `schemas/risk/**`, `tests/contracts/**`, `tests/domain/**` | `docs/handoffs/day-0/domain.md` |
| Planning | `packages/risk_planning/**`, `seed/knowledge-products/**`, `docs/knowledge-products/**`, `tests/planning/**` | `docs/handoffs/day-0/planning.md` |
| Data | `packages/risk_data/**`, `connectors/**`, `data/schemas/**`, `tests/data/**` | `docs/handoffs/day-0/data.md` |
| Agents | `packages/risk_capabilities/**`, `packages/risk_agents/**`, `tests/capabilities/**`, `tests/agents/**` | `docs/handoffs/day-0/agents.md` |
| Application | `apps/portfolio-risk-workbench/**`, `tests/application/**` | `docs/handoffs/day-0/application.md` |
| Integration | shared configuration, CI, architecture, cross-module tests, wave state, and merges | `docs/handoffs/day-0/integration.md` |

Each specialist lane may modify exactly its listed canonical handoff in
addition to its owned implementation paths. The lane manifest is authoritative
for enforcement.

## Dependency graph

```text
domain -> planning -> data -> agents -> application -> integration
```

Domain contracts define shared identities and value semantics. Planning uses
those contracts to describe research work. Data implements only contract-bound
observations. Agents consume the prior contracts and must retain evidence and
human-review boundaries. The application hosts reviewed adapters only after
the capability surface is fixed. Integration validates candidate branches in
that order.

## Acceptance tests

- `make test-architecture` verifies overlay boundaries, the ServiceFabric pin,
  ownership rules, data restrictions, and prohibited execution surfaces.
- `scripts/day0/check_lane_paths.py` rejects candidate changes outside the
  corresponding lane manifest.
- `scripts/day0/update_manifest_hashes.py --check` validates declared source
  files and their content hashes for an application manifest.
- `make verify-wave-0a` completes once the shared harness is present and all
  Wave 0A architecture checks pass.
- Specialist candidates must provide focused tests and their canonical handoff
  before integration accepts them.

## Exclusions

- provider API access, credentials, and licensed or real portfolio data;
- broker connectivity, order placement, rebalancing, or investment advice;
- external LLM calls or LLM API keys;
- changes under `vendor/servicefabric/**`;
- mutable snapshots, non-deterministic synthetic fixtures, and bypasses of
  ServiceFabric canonical invocation and result contracts.

## Integration order

`domain`, `planning`, `data`, `agents`, `application`, `integration`.

Integration validates each candidate against `integration/day0`, checks lane
ownership before accepting it, and does not merge specialist branches.

## Rollback

Revert the focused integration commits that activated this wave and restore
`config/agent/day0/status.json` and `docs/workplans/current.md` to the
preparation state. Do not alter the ServiceFabric submodule pin. Candidate
branches remain unmerged and may be corrected independently.
