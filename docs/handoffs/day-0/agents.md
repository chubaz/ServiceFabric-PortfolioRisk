# Day 0 agents handoff

- Lane and branch: capabilities and agents / `feature/day0-agents`
- Base: `day0-prepared` (`5d4bb78a2c4126c7a04c0244e50ef6662cd3e0b8`)
- Head: `c05e48c` (no candidate commit created)
- Status: Wave 0A implementation complete; focused verification passed

## Objective

Provide bounded role cards, capability contracts, provider interface, and a deterministic no-LLM provider without portfolio analytics, provider access, or executable financial actions.

## Changed paths

- `packages/risk_capabilities/`: immutable capability descriptor, invocation, outcome, evidence contracts, and finite catalog.
- `packages/risk_agents/`: immutable role/run contracts, four mandatory role cards, provider protocol, and deterministic non-executable draft provider.
- `tests/capabilities/` and `tests/agents/`: focused contract and provider safety coverage.
- `docs/handoffs/day-0/agents.md`: this handoff.

## Contracts consumed

- Day 0 ADR-0002 deterministic and human-review requirements.
- Capability outcomes preserve supplied opaque evidence references; provider credentials are not contract fields or supported input names.

## Commands executed

- `make preflight` — attempted; stopped in `env-check` because the local GitHub CLI authentication is expired.
- `DAY0_VENV=/home/lorenzoccasoni/servicefabric-lab/state/venvs/day0 make test-capabilities` — PASS (`5 passed`).
- `DAY0_VENV=/home/lorenzoccasoni/servicefabric-lab/state/venvs/day0 make test-agents` — PASS (`4 passed`).
- Isolated package smoke test (`pip install --no-deps packages/risk_capabilities packages/risk_agents`, then `python -I -c 'import risk_agents, risk_capabilities'`) — PASS.
- `git diff --check` — PASS.

## Tests and results

- Capability contracts: `5 passed`.
- Agent role and provider tests: `4 passed`.
- Installed-package import without repository path injection: PASS.

## Evidence

- The deterministic provider prepares only immutable, evidence-preserving drafts; it has no direct execution method. Invocation and results remain the canonical ServiceFabric runtime's responsibility.

## Deviations

- Post-review remediation removed the direct `run` path, rejects credential-like input names, restricts input values to immutable scalars, and declares `risk-capabilities` as an install dependency.

## Blockers

- `make preflight` cannot complete until the local GitHub CLI authentication is repaired; this is an environment issue.

## Limitations

- The provider produces only stable review drafts. It does not retrieve data, calculate exposure, make investment recommendations, connect to brokers, or execute trades.

## Rollback

- Remove the uncommitted lane-owned additions, or revert a future focused candidate commit. No shared configuration or vendor path changed.

## Recommended next action

- Run the focused tests, review the finite capability grants and safety disclosures, then allow integration to assess a focused candidate commit.
