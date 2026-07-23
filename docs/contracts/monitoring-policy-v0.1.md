# Monitoring policy contract v0.1

A monitoring policy is an immutable version with a profile and typed threshold
fields: percentage-move, concentration, event-relevance, negative-sentiment,
and stale-data thresholds, plus optional tail-risk and scenario-loss
thresholds. It includes a review requirement and cadence metadata only.

Cadence metadata does not create a background scheduler. Policies contain no
arbitrary or executable expression language; evaluation is a bounded,
reviewable contract operation. Policy revisions are never overwritten.
Alerts and findings preserve evidence, assumptions, warnings, limitations, and
human-review state. No policy can authorize an order, trade, rebalance, or live
portfolio effect.
