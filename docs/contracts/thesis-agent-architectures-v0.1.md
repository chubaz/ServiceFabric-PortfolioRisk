# Thesis agent architectures v0.1

The immutable Day 3 treatments are `B0`, `B1`, and `A1`. They consume one
identical governed input digest and emit one strict review schema. B0 is a
deterministic template with zero model calls; B1 makes one structured,
tool-free synthesis call; A1 makes four sequential, role-sliced calls using
the registered Market Data, Portfolio Exposure, News and Sentiment, and Alert
and Recommendation role IDs. No agent recalculates a metric or creates an
effect.

Final statuses are `NO_ISSUE`, `REVIEW`, `URGENT_REVIEW`, `ABSTAIN`, and
`ABSTAINED_AGENT_OUTPUT`. A deterministic critic verifies evidence, exact
metric values, eligible events, portfolio membership, allowed next steps,
human review, and empty effects. A failure becomes `ABSTAINED_AGENT_OUTPUT`.
