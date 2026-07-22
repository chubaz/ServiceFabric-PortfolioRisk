# Day 1 domain-analytics handoff

## Lane, branch, base, and head

- Lane: `domain-analytics`
- Branch: `feature/day1-domain-analytics`
- Base: accepted Wave 1B integration commit `066bb8f3421174810f07961a009942530742a851`
- Head: `066bb8f3421174810f07961a009942530742a851` with the candidate changes left uncommitted as requested

## Changed paths

- `packages/risk_analytics/**`: new bounded Python 3.11 package containing immutable analysis contracts, fixed Decimal policies, return, volatility, drawdown, historical tail-risk, scenario, contribution, deterministic report, and schema-export implementations.
- `schemas/risk/analytics/v0.1/**`: reviewed analytics JSON Schemas and content-digested schema index generated exclusively by `risk_analytics.schema_export`.
- `tests/analytics/**`: focused known-value, missing-data, determinism, safety-boundary, and stable-rendering tests.
- `tests/contracts/test_analytics_schema_export.py`: reproducible schema-export and prohibited-field tests.
- `docs/handoffs/day-1/domain-analytics.md`: this handoff.

No `risk_domain` change was required. Day 0 contract and schema files remain unchanged.

## Tests executed

- `make preflight` — PASS.
- `make test-day1-analytics` — PASS: 22 contract/domain tests and 14 analytics tests.
- `make verify-day0` — PASS: 37 architecture, 22 contract/domain, 22 planning, 27 data, 10 capability, 9 agent, 51 application, 13 integration, and 4 journey tests; manifest hashes and `git diff --check` also passed.
- Analytics schemas were regenerated with `risk_analytics.schema_export` before the focused target.
- Final `git diff --check` — recorded after this handoff update.

## Evidence produced

- Known simple and log return fixtures prove the reviewed formulas with positive, ordered prices.
- Mixed-currency price-series coverage proves that prices cannot be divided without an explicit common currency.
- Sample volatility proves denominator `n - 1` and the explicit default annualization assumption of 252 periods.
- Drawdown fixtures prove cumulative-wealth peak/trough selection and non-negative loss magnitude.
- Historical tail fixtures prove deterministic nearest-rank VaR, signed losses, expected-shortfall tail mean, reviewed confidence bounds, and the inadequate-sample warning calculated from `ceil(10 / (1 - confidence))`.
- Scenario fixtures prove linear position and portfolio P&L with no transaction effect.
- Contribution fixtures prove deterministic ordering, weighted-return reconciliation, and explicit missing-constituent warnings without zero filling.
- Reconstructed results and reports prove stable output digests, Markdown, and semantic HTML; every analytical result family exposes its calculated outcome in both report formats.
- Persisted specialized-result coverage proves that volatility, drawdown, tail-risk, scenario, contribution, and report contracts reject contradictory methodology labels; generated schemas expose the same constants.
- Generated schemas prove the absence of advice, optimization, recommendation, effect, order, trade, rebalance, and hedge fields.

All observations used by the focused analytics tests are explicitly synthetic reviewed fixtures.

## Deviations

- The accepted Wave 1B integration handoff explicitly made this package the next action while the integration-owned lifecycle files still record Wave 1C as queued. This lane did not edit or advance those control-plane files.
- Analytics schemas use the additive `schemas/risk/analytics/v0.1` namespace and their own exporter so the Day 0 `schemas/risk/v0.1` snapshot remains byte-compatible.
- No shared evidence or report reference had to be added to `risk_domain`; the analytics evidence contract references immutable evidence identifiers, locations, and digests directly.

## Blockers

No domain-analytics implementation blocker remains. Integration must review this uncommitted candidate and advance the Wave 1C lifecycle only after its acceptance process.

## Limitations

- Historical methods are descriptive and do not predict future losses.
- Scenario analysis is a reviewed linear market-value shock only; it has no pricing model, optimization, hedge recommendation, or transaction effect.
- Reports are deterministic Markdown and semantic HTML only. PDF and notebook execution are not implemented.
- This lane did not run the complete Wave 1C gate because agent and experience Wave 1C work remains outside its ownership.

## Rollback

Discard only the uncommitted paths listed above. No immutable snapshot, Day 0 schema, root dependency, application, provider, ServiceFabric submodule, or lifecycle control file needs rollback.

## Recommended next action

Integration should review the generated schema snapshot and focused test evidence, then accept a focused domain-analytics candidate before allowing the agents and experience Wave 1C lanes to consume these contracts. No merge, commit, or push was performed by this lane.
