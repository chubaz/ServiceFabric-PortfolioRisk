# Portfolio data context contract v0.1

A portfolio data context is an immutable, evidence-bearing selection used by a
monitoring or report run. It contains:

- selected immutable portfolio snapshot;
- selected market dataset revision and optional fundamental dataset revision;
- selected date-effective crosswalk revision;
- optional event dataset revision;
- point-in-time `as_of`, using `available_at` for eligibility;
- mapping coverage, unmapped positions, ambiguous mappings, and stale
  observations;
- evidence references, warnings, limitations, and an immutable digest.

Mappings require explicit stable entity identifiers and the selected crosswalk
revision. Ticker-only or fuzzy entity matching is prohibited. Missing
availability remains missing and blocks or warns; it is never guessed. The
context does not contain credentials, provider endpoints, orders, trades, or
rebalancing instructions.
