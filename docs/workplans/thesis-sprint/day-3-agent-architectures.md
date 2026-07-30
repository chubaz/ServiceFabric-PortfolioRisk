# THESIS-D3 — Agent architecture treatments

- Status: complete and accepted
- Depends on: `THESIS-D2` complete and accepted
- Experiment: `portfolio-risk-architecture-comparison-v1`

## Objective

Implement the later architecture comparison for treatments B0, B1, and A1
against the same accepted replay inputs and metric decision kernel. Treatment
identities, prompts or deterministic policies, capability access, evidence,
and stopping conditions must remain distinct and reviewable.

## Accepted boundary

B0, B1, and A1 are implemented for fixture verification and explicitly
authorized local OpenAI Responses runs. Comparisons use identical immutable
inputs, fixed quantities, point-in-time availability, frozen prompt and model
configuration, strict structured outputs, and effect-free human-review
results. The deterministic critic converts invalid output to abstention.

Public CI remains fixture-only and network-free. The local provider gate passed
against human-reviewed external events and exposures, an explicit dated model
snapshot, typed authorization, a Keychain-backed API key, and an immutable
external artifact bundle. The accepted run retained the frozen treatment call
counts and empty effects; unsupported claims were converted to deterministic
abstentions.

Day 3 acceptance does not rank architectures or claim precision, recall,
timeliness, outcome performance, cost superiority, or a QA result. Those
questions remain within queued Day 4.
