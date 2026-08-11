---
name: review-servicefabric-agent
description: Review a ServiceFabric AgentBlueprint, its generated LangGraph, and its version evidence against user requirements, system policy, temporal correctness, typed contracts, capability bindings, authority, and testability. Use before refining, implementing, saving, admitting, or promoting an agent to an Agent Graph.
---

# Review ServiceFabric Agent

## Review sequence

1. Read the nearest `AGENTS.md` and active workplan before inspecting implementation.
2. Treat `AgentBlueprint` as the source definition. Do not add a parallel agent model for review state.
3. Compare the candidate with its baseline by named sections. Report material semantic changes, not formatting noise.
4. Inspect the compiled LangGraph Python and graph specification. Verify state bindings, routing, stop conditions, retry bounds, human interrupts, and output assembly.
5. Trace each user or system requirement to direct configuration or test evidence. Mark it satisfied, partial, conflicting, unproven, or not applicable.
6. Check the agent-class boundary:
   - Static System Agents produce proposals only and cannot mutate code, Registry state, or experimental objects.
   - Experimental Specialists consume point-in-time risk context and remain effect-free unless a future policy explicitly says otherwise.
7. Check that capability inputs, outputs, evidence receipts, failure policies, and semantic bindings are explicit.
8. Inspect version-matched tests and runs through summaries first. Open full artifacts only when a finding requires them.
9. Recommend the smallest correction. Do not implement, admit, activate, merge, or promote automatically.

## Output

Return:

- an outcome-led assessment;
- a requirement ledger with evidence;
- material findings and exact correction targets;
- a complexity interpretation;
- whether a read-only Codex review, repository implementation, or Agent Graph consideration is justified;
- missing tests and unresolved human decisions.

Do not expose private chain-of-thought. Retain concise rationale, evidence references, diffs, receipts, and validation outcomes.
