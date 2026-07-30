# Thesis model provider v0.1

`FixtureStructuredModelProvider` is deterministic and CI-only.
`OpenAIResponsesProvider` is local-only, selected explicitly, uses an explicit
model snapshot, `store=false`, strict JSON schema, no tools, and no fallback.
Credentials come only from `OPENAI_API_KEY` and are never serialized, logged,
hashed, or included in evidence. Receipts retain semantic digests, token
usage, latency, response ID, warnings, and limitations, while semantic output
identity excludes latency and response ID.
