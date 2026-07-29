# Thesis real portfolio selection contract v0.1

Portfolio selection is a human-governed definition stage. The frozen flow is:

```text
candidate-universe artifact + human-reviewed selection YAML
    -> validated fixed-quantity PortfolioDefinition YAML files
```

The candidate universe is evidence produced by the accepted licensed bridge,
with point-in-time eligibility and immutable snapshot identity. A human must
select instruments by stable identifiers from that artifact and record the
review decision, source snapshot, `as_of`, rationale, and warnings in the
selection YAML.

Validation may reject unknown, duplicate, unavailable, or out-of-universe
identifiers. It may not select securities, infer tickers, optimize, rebalance,
or fill missing values. Quantities must be explicitly supplied by the human in
the reviewed YAML and must be fixed positive integers. The system never
chooses securities or quantities and creates no orders or portfolio effects.

Licensed sources, manifests, snapshots, and generated outputs remain outside
Git beneath `THESIS_DATA_ROOT`. Metrics and decision-kernel work remain
queued.
