# Portfolio Risk Thesis — Day 1

This example is the deterministic data and replay foundation for the
four-day thesis experiment. Every instrument, issuer, market observation and
event is fictional and explicitly synthetic. Outputs are research evidence,
require human review, and are not investment advice.

The implementation is local, read-only and point-in-time. A record is visible
only when `available_at <= as_of`. Portfolio quantities and cash are fixed:
there is no order, trade, broker, rebalance, optimization, network provider,
external LLM, scheduler or portfolio mutation effect.

With the repository Thesis environment and package paths configured:

```bash
python -m portfolio_risk_thesis.cli validate-data
python -m portfolio_risk_thesis.cli list-portfolios
python -m portfolio_risk_thesis.cli replay-day1
python -m portfolio_risk_thesis.cli inspect-step --portfolio-id diversified --ordinal 2
```

Commands print compact summaries. `replay-day1 --output-root /absolute/path`
writes one summary only when that path is equal to or beneath the configured
absolute `THESIS_DATA_ROOT`, which must itself remain outside Git. The
repository demo configures this boundary through `make demo-thesis-day1`.

`data/dataset_manifest.yaml` supplies all fixture paths and canonical SHA-256
digests; adapters do not hard-code repository fixture paths. Recreate the
reviewed fixture in a temporary directory with
`scripts/generate_fixture.py --output /absolute/path`, then compare the
Parquet and fixture-manifest digests before replacing any reviewed fixture.
Every market and event row also carries and validates its fixture revision,
canonical content digest, units, quality state, limitations, synthetic
disclosure, source, and evidence reference.

## Day 2 licensed local-export bridge

Day 2 adds a separate `licensed_local` path in `risk_data`; it does not alter
the Day 1 synthetic replay. The bridge accepts only a human-reviewed private
manifest and the seven explicit CRSP/Compustat Parquet identities. It uses
DuckDB for scans, transformations, partitioned ZSTD Parquet output, fixed
date-effective joins, and the local catalogue at
`catalog/crsp-compustat.duckdb`. It accepts no SQL, expression, formula,
network provider, ticker join, or repository output path.
That exact catalogue is the latest local pointer; every admission also retains
an immutable digest-bound copy under `catalog/snapshots/<snapshot_id>/`, which
is the copy used for snapshot verification and candidate-universe queries.

The checked-in
`data/real_dataset_manifest.example.yaml` contains the reviewed schema profile
and explicit mappings but deliberately unusable placeholder paths, digests,
revision, and retrieval time. Initialize a private manifest outside Git, review
and change its `reviewed` flag, then use the commands below.

When running from an uninstalled source checkout, `risk_data` requires both its
own source directory and its declared `risk_domain` dependency on `PYTHONPATH`:

```bash
export PYTHONPATH="$SF_THESIS_DAY2_WT/packages/risk_domain/src:$SF_THESIS_DAY2_WT/packages/risk_data/src:$SF_THESIS_DAY2_WT/examples/portfolio-risk-thesis/src"

"$SF_THESIS_VENV/bin/python" -m risk_data.cli \
  init-crsp-compustat-manifest \
  --schema-profile "$SF_REAL_PROFILE_ROOT/source-schemas.json" \
  --source-root "$SF_REAL_RAW_ROOT" \
  --manifest "$THESIS_REAL_SOURCE_MANIFEST" \
  --revision "$THESIS_REAL_SOURCE_REVISION" \
  --retrieved-at "$THESIS_REAL_RETRIEVED_AT"

"$SF_THESIS_VENV/bin/python" -m risk_data.cli \
  profile-crsp-compustat \
  --source-manifest "$THESIS_REAL_SOURCE_MANIFEST" \
  --output "$SF_REAL_PROFILE_ROOT/validated-profile.json"

"$SF_THESIS_VENV/bin/python" -m risk_data.cli \
  build-crsp-compustat \
  --source-manifest "$THESIS_REAL_SOURCE_MANIFEST" \
  --output-root "$SF_REAL_OUTPUT_ROOT" \
  --mode daily-primary

"$SF_THESIS_VENV/bin/python" -m risk_data.cli verify-crsp-compustat ...
"$SF_THESIS_VENV/bin/python" -m risk_data.cli list-crsp-compustat-snapshots ...
"$SF_THESIS_VENV/bin/python" -m risk_data.cli candidate-crsp-universe \
  --data-root "$SF_REAL_OUTPUT_ROOT" \
  --as-of "$THESIS_REAL_AS_OF" \
  --minimum-observations 260 \
  --output "$THESIS_REAL_CANDIDATE_UNIVERSE"
```

`THESIS_REAL_SOURCE_REVISION` and `THESIS_REAL_RETRIEVED_AT` must be set to the
reviewed source revision and its timezone-aware retrieval timestamp. The
initializer consumes the shareable schema-only `source-schemas.json`; the
private `source-inventory.private.json` is not a schema profile and remains
outside Codex and Git.

Market availability is explicitly a research timing model: the source market
date becomes visible at the reviewed time on the next distinct observed market
date, never at the same-day close; the final date remains unavailable. Annual
and quarterly fundamentals remain separate, rows without explicit publication
availability do not enter primary point-in-time joins, RET/RETX and RET/DLRET
remain distinct, and no MetricPack or combined-return policy is included.

## Day 2 human-governed real portfolios

The version 2 candidate artifact is private eligibility evidence, ordered only
by private PERMNO for deterministic output. It is not a portfolio and contains
no candidate rank or automatically chosen security, quantity, cash balance, or
benchmark.

Copy
`selections/real_portfolio_selection.synthetic-placeholder.example.yaml` to an
absolute private path beneath `THESIS_DATA_ROOT`. A human must replace every
placeholder, verify the candidate-artifact SHA-256, content-derived ID, source
snapshot, and UTC `as_of`, supply five to eight explicit candidate IDs and
fixed positive integer quantities per portfolio, record explicit cash,
rationale and warning acknowledgement, and set `reviewed: true` with reviewer
and UTC timestamps. Candidate `as_of` must not be later than the portfolio
effective time. The example itself is deliberately invalid and makes no
security or quantity recommendation.

Materialization validates that completed review; despite its name,
`init-real-portfolios` never initializes or proposes choices:

```bash
python -m portfolio_risk_thesis.cli init-real-portfolios \
  --candidate-artifact "$THESIS_REAL_CANDIDATE_UNIVERSE" \
  --selection "$THESIS_REAL_SELECTION_YAML" \
  --output-directory "$THESIS_REAL_PORTFOLIO_OUTPUT"

python -m portfolio_risk_thesis.cli validate-real-portfolios \
  --portfolios-directory \
    "$THESIS_REAL_PORTFOLIO_OUTPUT/portfolio-definitions/$SELECTION_ID" \
  --receipt \
    "$THESIS_REAL_PORTFOLIO_OUTPUT/portfolio-definitions/$SELECTION_ID/portfolio-selection-receipt.json"
```

The generated portfolio YAML contains only private-neutral instrument aliases.
The candidate-to-PERMNO map, receipt, and evidence manifest remain private,
external, immutable, content-bound, and effect-free beneath
`THESIS_DATA_ROOT`.

For the interactive thesis workflow, use the local wizard. It repairs the
candidate metadata automatically, displays the private candidate evidence, and
asks the reviewer to enter candidate numbers, cash, and positive integer
quantities. It writes nothing until the reviewer types `REVIEWED`:

```bash
python -m portfolio_risk_thesis.cli prepare-real-selection \
  --candidate-artifact "$THESIS_REAL_CANDIDATE_UNIVERSE" \
  --selection "$THESIS_REAL_SELECTION_YAML"
```
