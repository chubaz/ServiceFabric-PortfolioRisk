# ServiceFabric Portfolio Risk

ServiceFabric Portfolio Risk is a public application overlay for deterministic,
explainable portfolio-risk research and monitoring. It uses ServiceFabric's
canonical runtime and invocation contracts; the pinned dependency under
`vendor/servicefabric` remains read-only at commit
`7632b61d94a966346f95eb6c5bb2a5ea27f3bc14`.

Day 0 is complete and its evidence remains unchanged. Day 1 implementation is
complete at `D1-QA`; human soft QA is pending and is not implied by automated
verification or the local process-host smoke.

## Readable Workbench

The Workbench is a loopback-only FastAPI application whose primary interface is
server-rendered semantic HTML with local CSS. Dashboard, portfolio, risk,
findings, alerts, data, providers, research, notebook catalogue, agents, plan,
and settings pages retain visible profile, data-state, evidence, limitation,
and human-review disclosures. JSON APIs remain available for development and
evidence inspection. Notebook pages are catalogue-only.

Two explicit profiles are supported:

- `research` uses reproducible reviewed synthetic or reviewed-public metadata.
- `personal_portfolio` accepts user-supplied local holdings into an external
  private data root for monitoring and review only. It cannot publish personal
  data or connect to a broker.

## Portfolio input and provider boundary

The personal profile accepts bounded local CSV or YAML uploads. Raw bytes are
parsed in memory and are not persisted. A readable preview exposes normalized
content, input and preview digests, validation issues, and quality flags.
Explicit confirmation of the exact digest creates a content-addressed immutable
snapshot. Corrections create a new revision; comparison is read-only and never
overwrites either snapshot.

The provider catalogue exposes rights, access, data-zone, provenance,
freshness, quality, credential-reference, and publication states. WRDS, CRSP,
Compustat, RavenPack, Accern, Bloomberg, and every other external provider are
disabled and unavailable. Credentials are opaque local references. Only four
reviewed fixed local query manifests are available; arbitrary SQL is not an
interface.

## Analytics, evidence, and reports

Reviewed Day 1 methodologies are:

- adjacent simple and logarithmic returns;
- annualized sample volatility using `n - 1` and an explicit periods-per-year
  assumption;
- maximum drawdown from the cumulative wealth path;
- nearest-rank historical value at risk and historical tail-mean expected
  shortfall, with an explicit inadequate-sample warning;
- fixed deterministic linear scenarios; and
- weighted constituent contribution summaries with reconciliation.

Every result carries its method, horizon, sample period, observation count,
assumptions, warnings, limitations, evidence references, and output digest.
Reports are deterministic semantic HTML and Markdown. The four-agent timeline
records the market-data, portfolio-exposure, news-and-sentiment, and
alert-and-recommendation receipts in order. Reports and timelines require
explicit human review and have empty effects.

`make demo-day1-headless` writes these deterministic artifacts beneath
`PORTFOLIO_RISK_DATA_ROOT/day1-workbench` (using the Makefile's external Day 1
data root by default):

```text
input-preview.json
confirmed-portfolio-snapshot.json
snapshot-comparison.json
provider-catalogue.json
risk-analysis.json
scenario-analysis.json
agent-timeline.json
report.md
report.html
evidence-manifest.json
```

The evidence manifest records the SHA-256 digest of every sibling evidence
artifact.

## Exact local commands

Python 3.11 is required. Run the complete deterministic release checks with:

```bash
make preflight
make verify-day1
make demo-day1-headless
make servicefabric-day1-smoke
make verify-day0
git diff --check
```

To choose other external Day 1 locations without writing generated data into
the repository:

```bash
make demo-day1-headless \
  DAY1_PORTFOLIO_RISK_DATA_ROOT=/absolute/path/to/portfolio-risk-data

make servicefabric-day1-smoke \
  DAY1_PORTFOLIO_RISK_DATA_ROOT=/absolute/path/to/portfolio-risk-data \
  DAY1_SERVICEFABRIC_RUNTIME_VENV=/absolute/path/to/servicefabric-runtime \
  DAY1_SERVICEFABRIC_HOME=/absolute/path/to/servicefabric-home
```

The Day 1 smoke first validates the original pinned Text Utility baseline. It
then installs, builds, starts, inspects, calls, and stops the Workbench through
ServiceFabric, verifies packaged semantic HTML/CSS resources, checks
representative Day 1 capabilities and empty effects, and proves a capability
fails after stop. The bounded bootstrap copies host/client sources only into an
external runtime, checks the pinned upstream commit and local risk-package
source digests, and installs ordinary non-editable distributions. It never
edits `vendor/servicefabric`.

The Linux process-host smoke is deliberately local-only. CI runs every
deterministic Day 0 and Day 1 test, the Day 1 headless demo, manifest checks,
and whitespace checks; CI does not claim process-host smoke evidence.

## Limitations and safety boundary

The checked-in observations, news, and portfolio examples are fictional and
explicitly synthetic. Missing, failed, or incomplete observations remain
missing or carry a quality warning; they are never represented as zero.
Historical analytics are descriptive and do not predict future loss. Fixed
scenarios use a linear shock without pricing, optimization, or hedging models.
The base portfolio workflow performs no FX conversion.

There is no external provider or LLM call, notebook execution, arbitrary SQL,
broker connectivity, live account effect, order, trade, hedge, optimization,
automatic rebalance, PDF export, or investment advice. HTML and Markdown
reports are local review artifacts. Browser, keyboard, screen-reader, and
visual soft QA require a separate identified human reviewer and remain pending.
