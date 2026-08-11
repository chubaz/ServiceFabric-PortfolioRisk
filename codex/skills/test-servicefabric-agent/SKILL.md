---
name: test-servicefabric-agent
description: Design, execute, and review bounded tests for a versioned ServiceFabric agent or compiled LangGraph using representative, failure-boundary, adversarial, replay, and semantic-consistency cases. Use before saving or admitting an agent and when comparing revisions under an explicit LLM budget.
---

# Test ServiceFabric Agent

## Test sequence

1. Read the blueprint, compiled graph, output contract, capability contracts, authority profile, and exact version history.
2. Establish three mandatory fixture classes: representative, failure boundary, and adversarial.
3. Add historical replay or historically calibrated synthetic cases only when their provenance and as-of eligibility are explicit.
4. Verify deterministic structure before spending on LLM calls:
   - schema and semantic bindings;
   - graph reachability and bounded termination;
   - capability arguments, receipts, and failure routes;
   - denied effects and human checkpoints;
   - output completeness, evidence coverage, and abstention coherence.
   - mandatory headless wrapper compatibility for every Experimental Specialist;
   - final-decision versus specialist-node scope;
   - exclusion labels on every human-facing presentation artifact;
   - availability of findings, confidence, decision and execution observations
     required by ArchitectureOutput mapping.
5. Allocate LLM calls to claims deterministic checks cannot decide. State model, call ceiling, token ceiling, estimated cost, and stopping rule.
6. Evaluate the work product for decision value, unsupported claims, contradictions, repetitions, temporal leakage, and reviewer usability.
7. Compare against the previous version using the same fixtures and evaluation definitions.
8. Save compact metrics and findings with the agent version. Keep complete transcripts and artifacts reference-only.

## Release result

Return pass/fail by fixture, material regressions, confidence limits, cost and latency, reviewer overrides, and one of: revise, repeat, save candidate, or eligible for separate Registry admission review.

Never equate one plausible output with a passed agent. Never mutate a portfolio or external system during an agent test.
