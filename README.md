# ServiceFabric Portfolio Risk

ServiceFabric Portfolio Risk is a public application overlay for deterministic,
explainable portfolio-risk research and monitoring. It uses ServiceFabric's
canonical runtime and invocation contracts; the pinned dependency under
`vendor/servicefabric` remains read-only at commit
`7632b61d94a966346f95eb6c5bb2a5ea27f3bc14`.

Day 0 is complete and its evidence remains unchanged. Day 1 is complete at
`D1-COMPLETE`; deterministic verification and explicit identified human soft QA
have passed.

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
disabled and unavailable. Credentials are opaque local references. The Day 1
workspace retains four reviewed local query manifests. The completed Day 2–3
Phase 1 data plane adds five fixed research query manifests; arbitrary SQL is
not an interface.

## Day 2–3 Part 1 local research data plane

Part 1 is complete. It previews and explicitly confirms three fictional,
synthetic local exports: CRSP-like daily market data, Compustat-like annual
fundamentals, and a date-effective CRSP-Compustat-like identifier link. It
writes immutable normalized Parquet and curated DuckDB snapshots only beneath
the external `PORTFOLIO_RISK_DATA_ROOT`. Curated reads use reviewed fixed
manifests, and point-in-time eligibility requires `available_at <= as_of`.
Ticker-based guessed joins, missing-availability inference, arbitrary SQL, and
external provider network access remain unavailable.

`make demo-d23-phase1` writes the following deterministic evidence siblings
beneath `PORTFOLIO_RISK_DATA_ROOT/day23-phase1`:

```text
provider-register.json
import-previews.json
import-confirmations.json
dataset-snapshots.json
quality-reports.json
identifier-crosswalk.json
fixed-query-results.json
point-in-time-proof.json
evidence-manifest.json
```

The evidence manifest records the SHA-256 digest of every other sibling
artifact. The same directory contains the external mutable data-plane zones;
Parquet, DuckDB, quality, manifest, and evidence state remain outside Git.
Reviewable JSON Schema snapshots for all Part 1 data-plane contracts are
tracked under `data/schemas/day23/` and checked against fresh generation.

## Day 2–3 Part 2 monitoring and replay

Part 2 integration is complete. Compliant ephemeral staging of the four
allow-listed canonical fixtures is accepted, and deterministic local and
process-host gates passed. The identified final human QA passed; Day 2–3 is
complete. The deterministic journey and headless demo remain reviewable.

Portfolio-data contexts bind an immutable portfolio snapshot to exact Part 1
market, fundamental, and date-effective crosswalk revisions. Mapping uses
stable identifiers only: there is no ticker, name, fuzzy, or heuristic
fallback. Point-in-time selection uses `available_at <= as_of`; a missing
availability time stays missing, and an unavailable required market
observation causes abstention instead of being represented as zero.

Fictional RavenPack-like CSV and Accern-like Parquet exports can be previewed
and explicitly confirmed into immutable local event snapshots. Event queries
return only records available at the monitoring time and preserve amendments,
retractions, rights, publication state, and evidence digests. These fixtures
are synthetic and are not real provider observations.

Monitoring policies are immutable fixed-field revisions. Cadence is metadata
only and creates no scheduler. Explicit foreground runs use the existing four
agents—market data, portfolio exposure, news and sentiment, and alert and
recommendation—through registered capabilities. Runs produce evidence-bearing
findings and an analytical draft alert with empty effects and pending human
review.

Historical replay pins the portfolio, market, fundamental, crosswalk, event,
and policy revisions at every deterministic step. It preserves abstentions and
does not substitute current or future data. Evaluation uses deterministic
one-to-one alert/outcome matching and reports true positives, false positives,
false negatives, precision, recall, lead time, detection delay, coverage, and
sample warnings. Undefined metrics are `null` with an explicit warning, never
silently zero. Results are descriptive for the disclosed synthetic sample and
make no predictive claim.

`make demo-d23-part2` writes these deterministic evidence siblings beneath
`PORTFOLIO_RISK_DATA_ROOT/day23-part2`:

```text
data-context.json
event-import-preview.json
event-snapshot.json
monitoring-policy.json
monitoring-run.json
findings.json
alert-draft.json
agent-timeline.json
replay-specification.json
replay-runs.json
monitoring-evaluation.json
monitoring-report.md
monitoring-report.html
evidence-manifest.json
```

The manifest digests every other sibling artifact and records both operating
profiles, selected dataset and crosswalk revisions, the policy revision,
point-in-time rule, synthetic disclosure, pending human review, empty and
prohibited effects, evaluation methodology, retained evidence digests, and
accepted limitations. HTML and Markdown reports remain local review artifacts.

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
make verify-d23-phase1
make demo-d23-phase1
make servicefabric-d23-phase1-smoke
make verify-d23-part2
make demo-d23-part2
make servicefabric-d23-part2-smoke
make verify-d23-current
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

For a custom Day 2–3 data location, use `DAY23_PORTFOLIO_RISK_DATA_ROOT`.
The shorter `D23_PORTFOLIO_RISK_DATA_ROOT` spelling is also accepted:

```bash
make demo-d23-part2 \
  D23_PORTFOLIO_RISK_DATA_ROOT=/absolute/path/to/day23-data
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

The Day 2–3 Phase 1 smoke is also deliberately local-only. It installs, builds,
starts, calls, and stops the Workbench through ServiceFabric. It calls
`data.provider.catalog`, `data.import.preview`, `data.dataset.list`, and
`data.query.fixed`, requires empty effects, proves external providers remain
network-disabled, verifies a post-stop call fails, and checks that the hosted
process is cleaned up. CI runs the deterministic Phase 1 journey and demo but
does not run or claim the local process-host smoke.

The Part 2 smoke first validates the pinned upstream Text Utility baseline. It
then installs, builds, starts, and calls the Workbench through ServiceFabric
for `portfolio.data_context.create`, `events.query.as_of`,
`monitoring.policy.evaluate`, `monitoring.run.contextual`,
`monitoring.replay`, `monitoring.evaluate`, and
`monitoring.report.render`. Every result must have empty effects. The smoke
stops the Workbench, proves a post-stop call fails, verifies process cleanup,
and confirms that the pinned `vendor/servicefabric` tree was not edited. CI
runs the deterministic Part 1 and Part 2 tests, Part 2 headless demo, Day 0 and
Day 1 regressions, application-manifest check, and whitespace check. CI does
not run or claim Part 2 process-host smoke evidence.

## Limitations and safety boundary

The checked-in observations, news, and portfolio examples are fictional and
explicitly synthetic. Missing, failed, or incomplete observations remain
missing or carry a quality warning; they are never represented as zero.
Historical analytics are descriptive and do not predict future loss. Fixed
scenarios use a linear shock without pricing, optimization, or hedging models.
The base portfolio workflow performs no FX conversion.

There is no provider network access, external LLM call, notebook execution,
arbitrary SQL, broker connectivity, live account effect, order, trade, hedge,
optimization, automatic rebalance, PDF export, or investment advice. Reports
are local HTML and Markdown only. Monitoring and replay are explicit foreground
operations; there is no background scheduler. The deterministic evaluation
sample is deliberately small, fictional, synthetic, and unsuitable for a
predictive or investment-performance claim.

Browser, keyboard, accessibility, visual, evidence, methodology, and
user-workflow soft QA for Day 1 were completed by an identified human reviewer
and recorded in `docs/workplans/day-1/soft-qa-result.md`. Day 2–3 Part 3 human
QA, evidence review, release decision, and merge remain queued. The Part 2
package-staging blocker must be resolved without tracking duplicate fixtures,
and all integration gates must be rerun before Part 2 can be marked complete.
