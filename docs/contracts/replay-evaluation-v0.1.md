# Replay and evaluation contract v0.1

An immutable replay specification records start and end, cadence, selected
data revisions, policy revision, and the explicit point-in-time rule. Replay
uses `available_at`, has no look-ahead, and makes no predictive claim.

Outcome labels use one-to-one deterministic alert/outcome matching. A match is
eligible only when alert and outcome refer to the same instrument, the alert is
no later than the labelled outcome, and the alert lies inside the reviewed
lookback window. Each alert and outcome may be matched once; choose the closest
eligible prior unmatched alert.

The evaluation records outcome labels, true positives, false positives, false
negatives, precision, recall, lead time, detection delay, evaluated coverage,
abstentions, sample-size warnings, methodology, evidence, and limitations.
`precision = TP / (TP + FP)` and `recall = TP / (TP + FN)`. Undefined
denominators are `null` plus a warning, never zero. `lead_time` is
`outcome_time - alert_time`; `detection_delay` is
`alert_time - trigger_available_at`.
