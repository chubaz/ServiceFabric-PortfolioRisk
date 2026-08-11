---
name: build-servicefabric-agent
description: Build or revise a governed ServiceFabric Agent candidate from an approved AgentBlueprint. Use when Studio-Codex is asked to implement, correct, test, or prepare a candidate version of a Static System Agent or Experimental Specialist Agent in the ServiceFabric PortfolioRisk repository.
---

# Build a ServiceFabric Agent

Turn an approved Studio blueprint into a bounded, tested candidate. The result is never silently registered, activated, merged, or published.

## Required inputs

Require an approved blueprint containing:

- agent class and semantic version;
- observable outcome and typed input/output contracts;
- capability grants, authority, routing, state, memory, prompts, and governance;
- evaluation fixtures and acceptance thresholds;
- for Static System Agents: owning Studio, repository-relative codebase scope, knowledge sources, and skill IDs.

If a material field is missing, return a concise blocking question. Do not infer new authority.

## Workflow

1. Read `AGENTS.md`, `docs/workplans/current.md`, the active workplan, and `references/agent-contract.md`.
2. Confirm the requested class. Never mix Static System and Experimental Specialist contracts, capabilities, or runners.
   Every Experimental Specialist must declare whether it is a `final_decision_agent`
   or `specialist_node` and must compile with the mandatory headless experimental
   wrapper. Final decision agents produce the architecture-final decision;
   specialist decisions are advisory and never become the graph decision merely
   because they were emitted by a node.
3. Search the Agent Registry, existing templates, contracts, tests, and skills. Prefer configuration or reuse over new implementation.
4. Classify the change as configuration-only, adapter work, compiler/runtime work, or UI work. State the smallest coherent change.
5. Work only inside the approved repository-relative paths. Preserve the canonical ServiceFabric runtime and package boundaries.
6. Implement the candidate with existing objects and abstractions. Do not add a new domain object merely to support the Studio UI.
7. Run contract validation plus representative, failure-boundary, and adversarial fixtures. Run focused repository tests proportional to the change.
8. Return a candidate handoff containing changed files, tests, unresolved limitations, version impact, and the explicit human decision required next.

## Hard boundaries

- Do not edit vendor code.
- Do not enable portfolio, broker, order, hedge, rebalance, or external communication effects.
- Do not register, activate, publish, merge, delete a worktree, or change an experiment without explicit approval.
- Do not hide missing capabilities or contracts; record them as dependencies.
- Do not claim a simulated fixture used real data, real capabilities, or a real LLM call.
- Do not store secrets in prompts, manifests, receipts, or artifacts.
- Do not build an interactive experiment runner. Experimental agents execute
  headlessly. Label human-facing files as presentation-only and exclude their
  content from scientific evaluation.
- Do not derive evaluation claims by parsing Markdown, HTML, charts, or reports.
  Emit the declared evaluation by-products beside the useful structured output.

## Done when

The candidate validates, its class and experimental-role boundaries are tested,
its headless wrapper contract passes, declared fixtures pass, the diff remains
within scope, and the handoff states honestly what is executable now versus deferred.
