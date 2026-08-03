# ADR 0008: Thesis Day 4 historical evaluation

- Status: Accepted for Thesis Sprint Day 4
- Date: 2026-07-30

## Context

Day 2 provides the accepted deterministic Morning MetricPack and decision
kernel. Day 3 provides the accepted B0, B1, and A1 treatments, common governed
context, strict provider boundary, and deterministic critic. Day 4 must
evaluate those treatments historically without introducing a second
calculation or architecture path, leaking future labels, or overstating a
small preliminary panel.

## Decision

Use one reviewed, manifest-driven, resumable Python runner to orchestrate the
existing Day 2 and Day 3 engines. Freeze three reviewed portfolios, two stress
windows, one quiet control window, and five reviewed daily-close timestamps
per window. Execute B0, B1, and A1 over the resulting 45 common contexts for
135 primary results.

Freeze nine repeatability anchors, one for each portfolio-window pair. Repeat
B1 and A1 once at every anchor, producing 18 additional results. Do not recall
deterministic B0. Enforce an exact maximum authorization of 270 provider calls
and preserve an immutable receipt for every attempted call.

Separate execution into governed phases: freeze and validate the manifest,
materialize point-in-time Day 2 and Day 3 context, execute architectures,
close architecture execution, load labels, evaluate, render reports and the
offline dashboard, then write the run and evidence manifests. Labels and label
paths are unavailable to architecture inputs and provider payloads.

Use event-window labels as the primary preliminary view. Use
five-business-day future outcomes and their composite OR label only as
secondary evaluation sensitivity views. Apply the frozen status,
abstention, provider-error, matching, coverage, grounding, timeliness,
repeatability, latency, token, and pricing rules in
`docs/contracts/thesis-day4-evaluation-v0.1.md`.

Pricing comes only from a reviewed external pricing manifest. The dashboard is
self-contained offline HTML, CSS, JavaScript, and SVG. It does not modify the
Workbench application or use a frontend framework or remote asset.

## Consequences

The public suite can run the complete matrix with synthetic labels and a
network-blocked fixture provider. Licensed data, private portfolios, provider
payloads, raw responses, pricing, and generated results remain external to
Git. Real execution has no fixture fallback and requires zero provider errors.

Results are descriptive and effect-free. There is no significance test,
winner field, architecture recommendation, predictive claim,
investment-performance claim, or release approval. Two observations per
anchor provide only a preliminary agreement measure and do not characterize
model-output variance.

The runner may resume from immutable completed receipts but may not mutate the
reviewed experiment, duplicate a call, or exceed the authorization. A
successful automated run does not complete Day 4; explicit human QA remains
required.
