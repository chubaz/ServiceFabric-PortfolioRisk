# Thesis model provider v0.1

`FixtureStructuredModelProvider` is deterministic and CI-only.
`OpenAIResponsesProvider` is local-only, selected explicitly, uses an explicit
model snapshot, `store=false`, strict JSON schema, no tools, and no fallback.
Credentials come only from `OPENAI_API_KEY` and are never serialized, logged,
hashed, or included in evidence. Receipts retain semantic digests, token
usage, latency, response ID, provider-reported model, raw-response digest,
warnings, and limitations, while semantic output identity excludes latency
and response ID.

`ModelConfiguration` freezes model ID and snapshot, prompt-manifest digest,
explicit temperature support state, maximum output tokens, timeout, at most
one transient retry, `store=false`, empty tools, and response-schema version.
B1 and all four A1 requests share that configuration. Provider errors and
invalid structured output become deterministic abstentions, are recorded in
receipts, and cause the formal local gate to fail. No fixture fallback is
permitted.
