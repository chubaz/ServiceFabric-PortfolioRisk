# ServiceFabric Portfolio Risk

ServiceFabric Portfolio Risk is a public, synthetic-only application overlay
for deterministic portfolio-risk research, monitoring, evidence, reviewable
alerts, and four-role agent orchestration. The pinned ServiceFabric repository
under `vendor/servicefabric` remains a read-only dependency at commit
`7632b61d94a966346f95eb6c5bb2a5ea27f3bc14`.

## Day 0 complete; Day 1 prepared

Day 0 is complete and its reviewed soft-QA handoff passed. Day 1 is prepared
but not implemented: `D1-WAVE-1A` is the queued entry point.

The Day 1 waves are:

- 1A — human-readable, profile-aware Workbench and information architecture;
- 1B — local portfolio input, immutable snapshots, data catalogue, and rights;
- 1C — explainable risk analytics, reports, agent timelines, and human review.

The Day 1 plan preserves JSON APIs for developers and evidence inspection, but
the primary user surface will be semantic server-rendered HTML. Research uses
synthetic/reviewed public evidence; `personal_portfolio` uses local private
holdings only. No external provider is enabled by default, no licensed or
personal data enters Git, and no broker, order, trade, hedge, optimization, or
automatic rebalance effect exists. Alerts and analyses remain non-advice
drafts requiring explicit human review.

## Implemented Day 0 modules

- `risk_domain`: immutable dataset, portfolio, exposure, finding, alert,
  decision, and agent-run contracts with Decimal financial values.
- `risk_planning`: six knowledge-product records, review state, traceability,
  and the draft supervisor one-page renderer.
- `risk_data`: deterministic synthetic CRSP-like and Compustat-like ingestion,
  validation evidence, Parquet artifacts, DuckDB views, and dataset manifests.
- `risk_capabilities`: portfolio snapshot and exposure calculations, market
  anomaly detection, synthetic-news classification, alert drafting, and review.
- `risk_agents`: four bounded deterministic roles that invoke only registered
  capabilities and produce no effects.
- `portfolio-risk-workbench`: a loopback-only FastAPI dashboard and reviewed
  ServiceFabric capability adapter.

## Exact local commands

Python 3.11 is required. These commands keep environments and generated data
outside Git:

```bash
export DAY0_VENV=/home/lorenzoccasoni/servicefabric-lab/state/venvs/day0
make preflight
make verify-day0
make demo-day0-headless
make servicefabric-smoke
git diff --check
```

`make demo-day0-headless` writes the portfolio snapshot, exposure snapshot,
findings, four agent runs, alert draft, and evidence manifest beneath
`/home/lorenzoccasoni/servicefabric-lab/state/day0/integration/portfolio-risk-data`
by default. Override `PORTFOLIO_RISK_DATA_ROOT` on the Make command line when a
different external root is needed.

`make servicefabric-smoke` creates or reuses its runtime venv beneath
`state/venvs/day0`, uses a dedicated `SERVICEFABRIC_HOME`, validates the pinned
upstream Text Utility journey first, then installs, builds, starts, inspects,
calls, and stops the Workbench through the canonical ServiceFabric CLI. It also
proves that a capability is unavailable after stop. The process-host smoke is
Linux-local because GitHub Actions cannot guarantee the same deterministic
process-host conditions; CI runs all unit, architecture, integration, and
journey tests plus the headless demo.

The smoke bootstrap records a digest of the reviewed local risk-package sources
and installs them as ordinary, non-editable distributions in the external
runtime. A running hosted application therefore cannot import later working-tree
edits. Changing those sources deliberately creates a new bootstrap input set.
The hosted artifact also packages the reviewed knowledge-product catalogue used
by `/plan` and `/research`.

## Boundaries and limitations

All observations, news events, portfolios, and outputs are fictional synthetic
fixtures. Missing or failed observations are never represented as zero. Day 0
and prepared Day 1 do not connect to market-data providers, licensed datasets,
external LLMs, brokers, or accounts.

There is no live trading, order object, broker object, automatic rebalancing,
or investment advice. Alerts begin as drafts, have empty effects, and require a
recorded human DecisionPoint. The exposure calculation supports one base
currency and performs no FX conversion.

The pinned AP-01A host natively reviews only Text Utility. The local smoke
bootstrap therefore applies a digest-checked Portfolio Risk allowlist to a
copied host installed in the external runtime venv; it does not edit the pinned
submodule. Broader multi-application hosting remains an upstream limitation.
