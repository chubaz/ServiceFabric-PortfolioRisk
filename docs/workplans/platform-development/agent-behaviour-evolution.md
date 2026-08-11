# Agent and graph behaviour evolution

- Status: active roadmap
- Parent: STUDIO-S3 Agent Studio
- Scope: Experimental Specialist Agents and their executable graphs
- Boundary: research/development only; no external financial effects

## Purpose

Improve agent behaviour in observable increments until it is sufficient for
the first thesis experiments, then continue development on a separate track
without changing the frozen thesis apparatus. Every increment must be directly
testable in Agent Studio before it can be composed into an experiment.

Central composition and study management are governed by
`docs/architecture/central-agent-native-research-program.md`. Agent Studio
qualifies individual reusable agents; it is not the primary surface for designing
or operating a complete architecture study.

## Data truth and evaluation split

Agent tests use three visibly distinct sources:

1. **Controlled synthetic fixture** — fixed formulas used to verify wiring,
   failure handling and policies. It is not empirically calibrated.
2. **Historically calibrated synthetic** — a versioned synthetic process fitted
   only on licensed in-sample aggregates. Licensed rows and native identifiers
   are not retained in the run. A named OOS window is reserved and cannot tune
   that fixture version.
3. **Licensed historical OOS** — immutable point-in-time inputs used only for
   evaluation after the agent, graph, prompts, policies and thresholds are
   frozen.

Generated observations are always synthetic evidence. Historical calibration
does not turn them into empirical observations. Calibration parameters, method,
seed, data revision, window, rights policy and digest remain reproducible.

## Behaviour increments

### B0 — Semantic execution contract — implemented in this slice

- Normalize capability results into one versioned semantic fact ledger.
- Resolve aliases such as `drawdown`/`maximum_drawdown` and
  `exposure_coverage`/`valuation_coverage` before model projection.
- Check availability and numerical consistency independently of the drafting
  model.
- Preserve field-by-field checks and conflicts as a run artifact.
- Compare deterministic and Luna interpretation on one frozen input.
- Retain selected outputs in the governed Artifact Repository; retained outputs
  leave the temporary Agent Studio queue.

### B0.5 — Headless experimental wrapper — implemented

- Compile every Experimental Specialist with the wrapper contract at creation.
- Run experiment agents headlessly and label presentation artifacts as excluded.
- Distinguish the one final decision agent from reusable specialist nodes.
- Map only a final decision output to `ArchitectureOutput`; keep specialist
  findings and node-advisory decisions as graph contributions.
- Capture runtime telemetry outside the model: timing, tokens, cost, capability
  calls, retries, failures and deterministic digests.
- Aggregate graph disagreement, dispersion, critic correction, handoffs and
  coordination overhead without rewriting the final decision.
- Persist isolated Studio results as `agent-output.json` with
  `not_admitted_to_experiment`, never as an experimental ArchitectureOutput.

Exit: implemented and covered by focused wrapper, kernel, Agent Studio and API
tests. Graph topology and synthesis policy remain deliberately deferred to B4.

### B1 — Complete deterministic research baseline

- Replace remaining supplied-context metric latches with canonical capabilities.
- Retrieve limits from a versioned Mandate/IPS object, never from issue prose.
- Add typed event/news absence and data-quality states.
- Create golden arithmetic and temporal tests for each material fact.
- Add a deterministic claim-to-fact reconciliation table to every run.

Exit: all material measures and mandate findings have canonical receipts; no
available value can be reported as missing without a failing semantic check.

### B2 — Bounded agent-directed capability use

- Give the agent a compact capability index rather than all schemas.
- Let it rewrite the research question, select a capability family and request
  exact schemas only when needed.
- Use a low-cost parametrizer to prepare typed arguments; validate them before
  invocation.
- Maintain capability memory by input digest, point-in-time boundary and method
  version.
- Require an explicit stop reason: sufficient evidence, budget reached,
  unavailable dependency or human escalation.

Exit: the graph can choose among reviewed effect-free capabilities while token,
latency and call budgets remain deterministic and auditable.

### B3 — Connectors and governed retrieval

- Expose Registry-backed DuckDB, HTTP/API and MCP adapters through the same
  typed capability boundary.
- Present a compact data-context catalogue with rights, freshness, temporal
  semantics and availability.
- Enforce look-ahead checks before retrieval and again before context assembly.
- Never replace connector failure with synthetic data.
- Allow missing integrations to create human-reviewed capability proposals,
  not self-installed tools.

Exit: every external read has a source revision, eligibility decision, receipt
and rights policy; OOS evaluation remains sealed.

### B4 — Adaptive graph behaviour

- Add plan, act, semantic critic, evidence critic and synthesis nodes as
  independently versioned policies.
- Permit bounded reflection only when a named verification gate fails.
- Support specialist sub-agents where context, capability grants or evaluation
  criteria materially differ.
- Compare LangGraph patterns and other agent-framework adapters behind the same
  assignment/output/evaluation contracts.
- Persist routing decisions and concise rationales without private
  chain-of-thought.

Exit: graph topology is an experimental variable, not an undocumented code
change, and every branch has deterministic termination and budget rules.

### B5 — Experimental decisions and object effects

- Agents may propose decisions against Portfolio, Mandate, Thesis, Scenario,
  Report and Dashboard experiment objects.
- Human or policy-bound supra-agent resolution is explicit and versioned.
- Only isolated experiment objects may mutate; licensed/external databases stay
  read-only and external effects remain fake placeholders.
- Record proposal, policy, resolver, consequence and counterfactual separately.

Exit: an experiment can test both analytical quality and decision consequence
without implying production authority.

## Initial thesis threshold

Freeze a thesis candidate after B3 plus the minimum B4 graph patterns when:

- 100% of material calculations and mandate findings have canonical receipts;
- 100% of runs pass point-in-time and rights checks;
- no prohibited effect occurs;
- semantic contradiction rate is below 1% on the locked regression suite;
- unsupported material-claim rate is below 2%;
- high-materiality false-negative rate is below 5% on labelled replay cases;
- evidence coverage is at least 95%;
- deterministic, failure and adversarial suites pass for every candidate;
- latency, tokens and cost are recorded for every model-backed run;
- blind reviewers can distinguish evidence, interpretation, uncertainty,
  proposal and decision, and achieve an agreed acceptance score.

These are proposed starting gates, not empirical conclusions. They must be
recorded in the decision register before the OOS panel is opened.

## Beyond the thesis threshold

While the frozen candidates run against OOS cases, a separate development
track may add richer MCP/API integrations, agent-generated capability
proposals, sub-agent crews, live dashboards, report packages, scenarios and
experimental object effects. None may silently alter a frozen candidate,
evaluation set, label, threshold or OOS boundary. Improvements enter a later
version and can be compared against the frozen baseline.

## Experiment attachments

Other reusable objects attach to an experiment through immutable references:

- AgentBlueprint and graph version;
- Capability and connector versions;
- Portfolio, Mandate/IPS and context-pack revisions;
- scenario and synthetic calibration specification;
- report/dashboard definitions;
- decision and authority policy;
- evaluation suite and budget;
- retained input, receipts, outputs and reviewer labels.

This keeps new objects composable without expanding every agent prompt or
turning the Agent Studio into the experiment runner.

## Verification cadence

- Run focused contract and behaviour tests in every increment.
- Run representative browser/API qualification at every visible slice.
- Run the broader cross-object suite every three increments or immediately when
  temporal, rights, authority, storage or external-integration boundaries
  change.
- Freeze exact versions before OOS evaluation; corrections create a new
  candidate rather than rewriting the evaluated one.
