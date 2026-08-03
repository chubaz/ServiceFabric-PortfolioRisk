# Thesis Sprint Day 3 specialist handoff

## Lane and state

- Specialist lane: `feature/thesis-day3`, already merged into
  `integration/thesis-experiment`.
- Lifecycle: `THESIS-D3` complete and accepted; `THESIS-D4` queued.
- Treatments: B0 deterministic, B1 one model call, A1 four fixed role calls.
- Day 4 evaluation and soft QA remain queued.

## Implemented public evidence

The public implementation provides strict immutable contracts, generated JSON
Schemas, a reviewed prompt registry with byte digests, one common context
digest, role-sliced A1 inputs, 20 fictional point-in-time events, immutable
Parquet materialization, exact-digest fixture responses, a strict OpenAI
Responses boundary, deterministic critic abstention, compact comparison
metrics, and a complete immutable external artifact bundle.

B0 preserves the Day 2 kernel status with zero model calls. B1 receives the
complete governed context in exactly one call. A1 uses
`risk.agent.market_data`, `risk.agent.portfolio_exposure`,
`risk.agent.news_sentiment`, and `risk.agent.alert_recommendation` in order.
Specialists cannot see another role's context. Invalid structured output is
retained by semantic digest and converted to `ABSTAINED_AGENT_OUTPUT`.

The public tests cover prompt digests, label leakage, prompt-injection text,
private fields, event availability, strict schemas, provider request shape,
no tools, `store=false`, errors and invalid JSON, no fixture fallback, critic
violations, exact model-call counts, role order, semantic identity, immutable
artifacts, and a network-blocked vertical journey.

## Local acceptance

The explicitly authorized local OpenAI Responses run completed and the formal
`verify-thesis-day3-real` gate passed. Compact acceptance metadata confirmed
one common context digest, B0 with zero calls, B1 with one call, A1 with four
fixed role calls, and zero effects. The accepted external evidence retained
provider receipts and deterministic critic reports. B1 and A1 abstained after
critic violations; that is the governed fail-closed behavior, not a provider
failure.

The direct and interactive runners remain available for reproducibility, but
the accepted immutable run is not repeated during closeout. Private data,
credentials, raw responses, provider requests, local paths, and generated
experiment artifacts remain outside Git. No precision, recall, timeliness,
statistical, cost-comparison, architecture-ranking, or QA result is claimed by
this Day 3 handoff; those remain queued Day 4 work.

## Rollback

Revert the Day 3 implementation and integration harness changes without
touching accepted Day 1, Day 2, licensed local data, or external evidence.
External run directories are content-addressed and remain outside Git.
