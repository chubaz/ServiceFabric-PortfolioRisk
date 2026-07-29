# THESIS-D2 — Morning MetricPack and deterministic decision kernel

- Status: in progress
- Depends on: accepted human-reviewed real portfolio definitions
- Next state: `THESIS-D3` after integration acceptance and Day 2 closeout

Implement a deterministic, point-in-time Morning MetricPack and decision
kernel against the accepted fixed-quantity portfolio definitions. The kernel
must preserve evidence, assumptions, warnings, limitations, missing values,
data-readiness state, materiality, review items, decision points, and empty
effects.

The specialist must add explicit validation and run commands backed by real
implementations and synthetic tests. The private local gate must fail closed
for unavailable daily data, monthly-only selection, fewer than 60 eligible
daily observations, digest mismatch, unavailable required prices, ambiguous
CCM links, or unreviewed source mappings.

No agent architecture, LLM, provider network, broker, order, trade, rebalance,
optimization, recommendation, or portfolio mutation effect is in scope.
Licensed rows, identifiers, maps, portfolio selections, generated metrics, and
receipts remain external beneath `THESIS_DATA_ROOT`.
