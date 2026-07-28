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
