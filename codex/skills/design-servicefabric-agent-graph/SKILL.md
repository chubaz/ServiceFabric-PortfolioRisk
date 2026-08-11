---
name: design-servicefabric-agent-graph
description: Decide whether a ServiceFabric agent should remain a single bounded LangGraph agent or be composed into an Agent Graph, then design the smallest governed composition. Use when responsibilities, contexts, capability grants, authority, evaluation, failure isolation, or independent challenge differ materially.
---

# Design ServiceFabric Agent Graph

## Decision rule

Keep one agent by default. Propose a graph only when separation creates measurable value through at least one of:

- different context or data rights;
- different capability grants or runtime profiles;
- independent validation or professional challenge;
- different authority or human-review boundaries;
- separately measurable quality criteria;
- failure isolation, latency, or cost control.

Do not split agents to imitate an organization or merely because the task has sections.

## Design sequence

1. State the overall work product and acceptance condition.
2. Identify responsibilities that genuinely require separate contracts.
3. Define each node's input, output, state contribution, capability surface, evidence duty, authority, abstention rule, and evaluation.
4. Define typed edges, merge/reducer rules, routing conditions, bounded loops, failure paths, and human interrupts.
5. Preserve point-in-time eligibility and provenance across every edge.
6. Prevent hidden shared memory; pass only declared state or artifact references.
7. Compare the proposed graph with the single-agent baseline for quality, cost, latency, and operational complexity.
8. Return a non-executing graph proposal. Human approval is required before implementation or Registry admission.

Prefer specialist → independent critic → synthesizer → human when independent challenge is the reason for composition. A graph must not grant any node authority absent from the approved overall boundary.
