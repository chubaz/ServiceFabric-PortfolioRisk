# Central Experiment Manager

- Status: agreed direction; first live readiness view implemented
- Purpose: design, build, run and compare portfolio-risk agent setups from one place
- Main rule: the Library is read-only to agents

## Why this exists

The user should not have to move between several Studios and remember how every object connects. One central manager should take a research question, inspect what is already saved, identify what is missing, coordinate approved development, assemble the experiment, run it and explain the results.

Studios remain available for detailed building work. They are opened only when a required agent, tool, mandate, portfolio, scenario, report or workflow is missing or needs improvement.

## Five ordinary concepts

| Product term | Meaning |
|---|---|
| Library | Saved and versioned agents, tools, mandates, portfolios, workflows and data connections. The technical backend remains the Registry. |
| Build | Create or improve something that is missing. |
| Agent setup | The exact saved agents, tools, workflow, data and rules used by an experiment. |
| Run | Execute one agent setup over an exact historical period and portfolio. |
| Review and compare | Inspect inputs, calls, outputs, decisions, quality, time and cost across runs. |

Other contract names remain under Technical details and are not primary interface language.

## How it should work

```text
Describe the research question
  -> search the Library
  -> show reusable items and missing items
  -> send approved missing items to Build with Codex
  -> save tested versions in the Library
  -> assemble two or more agent setups
  -> confirm real data, dates, portfolio and mandate
  -> run the same historical cases
  -> review the work
  -> compare the results
```

The manager continues automatically through routine checks. It pauses only for decisions about development scope, data access, cost, Library admission, opening OOS data or accepting a research conclusion.

## The Library is protected

- Agents can search it and propose combinations.
- Agents cannot rewrite, delete or silently repair saved versions.
- Only saved versions may be used in a formal experiment.
- Missing work creates a Build Request; it does not create a fake saved item.
- A tested item enters the Library only after explicit approval.
- Completed runs continue to reference the exact versions they used.

## Shared actions

Builder.io's Agent-Native approach is useful here because the human interface and agents should use the same backend actions. The agent should not click through pages or receive a large dump of the Library.

The first shared actions are:

- search saved items;
- check whether an agent setup is complete;
- create a linked Build Request;
- resolve point-in-time data;
- prepare an experiment comparison;
- schedule and resume runs;
- calculate fixed evaluation measures;
- save selected outputs;
- request a human decision.

Deterministic work belongs in these actions. LLM calls are reserved for designing agent setups, resolving genuinely novel gaps and interpreting completed evidence. Repeated model work should become a tested tool.

Source examples:

- https://www.builder.io/blog/agent-native-architecture
- https://www.builder.io/blog/why-the-best-agent-native-apps-use-less-ai

## Central agent workflow

Begin with one graph containing four understandable roles:

| Role | Work |
|---|---|
| Planner | Turns the question into agent setups to compare and searches the Library. |
| Build coordinator | Tracks missing items and sends approved Build Requests to the correct builder and Codex. |
| Run manager | Checks real data and exact versions, applies budgets and runs approved experiments. |
| Reviewer | Calculates fixed measures, checks evidence and explains differences and limitations. |

Split these into separate agents only when their data access, authority or evaluation genuinely differs.

## What must be checked

| Item | Plain readiness check |
|---|---|
| Mandate | Can every rule be calculated using available tools and eligible data? |
| Portfolio | Can every holding be matched to point-in-time prices, identifiers and classifications? |
| Risk analysis | Do the requested models, measures and evidence outputs exist and reconcile? |
| Scenario | Are the shocks, calibration, starting state and interpretation explicit? |
| Agent | Does it have the required data, tools, output format and authority? |
| Workflow | Are the order, branches, stops, budgets and human decisions explicit? |
| Evaluation | Were measures, labels and OOS boundaries fixed before execution? |

## Interface

Use one page with five sections:

1. **Question** — what is being studied?
2. **Library check** — what is ready and what is missing?
3. **Agent setups** — what exact methods will be compared?
4. **Runs** — status, progress, decisions, time and cost.
5. **Results** — review and comparison.

Every missing item links directly to Build. Technical contracts, digests and receipts remain available under Technical details.

## Data rule

Licensed historical data is the default. Synthetic data is available only in a separately labelled Sandbox and never appears as thesis evidence. A missing real input blocks the run; it is never replaced silently.

## First implementation slice

The Experiments page now performs a live read-only check of:

- licensed historical data availability;
- real-data portfolios and positions;
- saved mandates;
- saved agents, graphs, workflows and tools;
- availability of a real historical runner.

It does not show development samples as results and does not claim that a run exists. The next slice will let the central Planner prepare two agent setups using saved Library items, still without executing or modifying the Library.

