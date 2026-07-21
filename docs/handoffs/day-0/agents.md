# Day 0 agents handoff

- Lane and branch: capabilities and agents / `feature/day0-agents`
- Base: `day0-prepared` (`5d4bb78a2c4126c7a04c0244e50ef6662cd3e0b8`)
- Head: `e6f39a5` (current branch head; no commit created in this Wave 0B task)
- Status: Wave 0B capability registry and bounded agent activation complete; focused verification passed

## Objective

Provide bounded role cards, capability contracts, a deterministic no-LLM draft provider, and the Wave 0B deterministic capability registry without provider access or executable financial actions.

## Changed paths

- `packages/risk_capabilities/`: immutable contracts, finite catalog, and deterministic registry for planning due-listing, synthetic-ingestion handoff, snapshot creation, exposure summaries, and anomaly detection.
- `packages/risk_agents/`: immutable role/run contracts, four role cards, deterministic non-executable draft provider, and registry-delegating active agents.
- `tests/capabilities/` and `tests/agents/`: focused contract, registry, activation, and safety coverage.
- `docs/handoffs/day-0/agents.md`: this handoff.

## Contracts consumed

- Day 0 ADR-0002 deterministic and human-review requirements.
- Immutable `risk_domain` PortfolioSnapshot and ExposureSnapshot contracts.
- Normalized synthetic `risk_data` observations; capability outcomes preserve supplied opaque evidence references.

## Commands executed

- `make preflight` — attempted; stopped in `env-check` because the local GitHub CLI authentication is expired.
- `DAY0_VENV=/home/lorenzoccasoni/servicefabric-lab/state/venvs/day0 make test-capabilities` — PASS (`9 passed`).
- `DAY0_VENV=/home/lorenzoccasoni/servicefabric-lab/state/venvs/day0 make test-agents` — PASS (`5 passed`).
- Isolated package smoke test from Wave 0A (`pip install --no-deps packages/risk_capabilities packages/risk_agents`, then `python -I -c 'import risk_agents, risk_capabilities'`) — PASS.
- `git diff --check` — PASS.

## Tests and results

- Capability contracts and registry: `9 passed`.
- Agent role, provider, and active-agent tests: `5 passed`.
- Installed-package import without repository path injection: PASS.

## Evidence

- `portfolio.snapshot.create` uses only supplied normalized observations, positions, and explicit timestamps; it never infers current time.
- `portfolio.exposure.summarize` delegates to the immutable domain ExposureSnapshot calculation and returns NAV, position/cash weights, gross/net exposure, and largest position weight.
- `market.anomaly.detect` reports simple-return threshold breaches (including the seeded ALPHA move), preserves evidence, warns about missing observations, and never imputes zero returns.
- The deterministic provider prepares only immutable, evidence-preserving drafts; it has no direct execution method. Invocation and results remain the canonical ServiceFabric runtime's responsibility.

## Deviations

- The Market Data and Portfolio Exposure agents are active and invoke only their registered capability grants. News & Sentiment and Alert & Recommendation remain inactive.
- No orchestration framework, external provider, API material, broker connectivity, order submission, or automatic rebalancing was added.

## Blockers

- `make preflight` cannot complete until the local GitHub CLI authentication is repaired; this is an environment issue.

## Limitations

- The registry is local-only and deterministic; integration must still bind registered capabilities through the canonical ServiceFabric runtime before any hosted invocation.
- The provider produces only stable review drafts. It does not retrieve data, make investment recommendations, connect to brokers, or execute trades.

## Rollback

- Remove the uncommitted lane-owned additions, or revert a future focused candidate commit. No shared configuration or vendor path changed.

## Recommended next action

- Integration should bind the finite registry to the canonical ServiceFabric runtime, review its dependency metadata, and assess a focused candidate commit.
