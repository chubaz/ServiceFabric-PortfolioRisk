# Day 1 risk analysis contract v0.1

Supported methods: simple returns, log returns, annualized volatility,
maximum drawdown, historical VaR, historical expected shortfall,
deterministic scenario shocks, and portfolio contribution summaries.

Each analysis result includes `analysis_id`, `snapshot_id`, `confidence_level`
(when applicable), `horizon`, `sample_period`, `observation_count`,
`methodology`, `assumptions`, `warnings`, `limitations`, `evidence`, and an
immutable output digest. Historical VaR/expected-shortfall results carry an
inadequate-sample warning below the reviewed minimum and preserve missing
quality states. Scenario shocks are deterministic and descriptive.

Outputs are reports or findings for review. They cannot invoke optimization,
trade, hedge, rebalance, order, or other live effect paths. HTML and Markdown
are in scope; PDF export and notebook execution are deferred.
