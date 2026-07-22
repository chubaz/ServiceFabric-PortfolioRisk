# Day 1 agents lane prompt template

Lane: agents; branch: `feature/day1-agents`. Own only declared capability,
agent, and test directories and exact handoff.

Acceptance: timelines identify role, capability, evidence, assumptions,
warnings, limitations, and output digest; canonical invocation remains the
only execution path and human review is explicit. Exclude external LLMs,
provider calls, broker/order/trade/rebalance effects, and app edits. Run
focused capability/agent tests and `git diff --check`, record evidence, commit
a focused candidate, validate the current lifecycle gate, and stop without merge.
