# Agent output and ArchitectureOutput

## Mandatory experiment boundary

Every Experimental Specialist is created with the same wrapper contract. This
is part of the blueprint, not an option selected after development:

```text
Agent blueprint
  ├─ experimental role: final decision agent | specialist node
  ├─ execution mode: headless
  ├─ output contract: AgentStructuredOutput/v1
  └─ presentation policy: label and exclude
```

The wrapper is instrumentation. It records execution and validates structure;
it does not judge, improve, rewrite, or approve an agent conclusion.

All experiment agents run headlessly. A Markdown brief, chart, dashboard, or
other user-facing file may be retained as a labelled `presentation_artifact`,
but its status is always `excluded_user_facing`. It is not an experimental
input, an `ArchitectureOutput`, or a source of missing evaluation claims.

## Two experimental roles

A **final decision agent** produces the architecture-level assessment and
proposed decision. A single-agent architecture has exactly one. An agent graph
also has exactly one final decision contribution, normally from its synthesizer.
Only this output can be mapped directly to `ArchitectureOutput`.

A **specialist node** produces bounded findings, evidence, uncertainty,
confidence, and optionally a `node_advisory` decision. Its contribution is
retained for graph analysis but cannot claim to be the architecture result. The
later graph design will determine routing and synthesis; this contract does not.

## Output anatomy

```text
AgentStructuredOutput
  ├─ primary_artifact       useful machine-readable work product
  ├─ evaluation_byproducts  findings, interpretation, confidence and decision
  ├─ capability_uses        canonical receipts and timing
  ├─ presentation_artifacts labelled and excluded from evaluation
  └─ identity               run, cycle, architecture, agents, as-of and digest
```

The model supplies semantic content. The runtime supplies stable identifiers,
timestamps, token usage, capability receipts, retries, failures and cost. The
model is never asked to invent runtime telemetry.

Every admitted finding has its own severity, materiality, confidence,
confidence method, affected asset, direction, observation time and evidence.
Uncited claims are excluded from evaluation and disclosed as a warning.

## Single-agent execution

```text
headless agent
  -> AgentExecutionEnvelope(output + observed telemetry)
  -> deterministic mapping
  -> ArchitectureOutput
```

The mapper checks run, cycle, architecture, as-of, evidence eligibility,
capability receipts, effects and output role. It copies the declared semantic
by-products without changing the decision.

## Graph execution

```text
specialist wrappers ─┐
critic wrapper ──────┼─> GraphExecutionEnvelope
final wrapper ───────┘       ├─ all contributions
                             ├─ edges and handoffs
                             ├─ critic corrections
                             └─ timing and token totals
                                      |
                                      v
                              deterministic mapping
                                      |
                                      v
                              ArchitectureOutput
```

The graph wrapper maps only the declared final contribution. It also retains:

- finding disagreement;
- severity and confidence dispersion;
- node-advisory decision disagreement;
- critic additions, removals and accepted corrections;
- handoffs, synthesis time and coordination overhead;
- aggregate model, token, cost, capability and failure telemetry.

These are observations about architecture behavior, not a second judgement of
the financial conclusion.

## Evaluation coverage

| Dimension | ArchitectureOutput basis | Additional comparison basis |
|---|---|---|
| Detection quality | findings, clusters, affected assets | independently hidden labels |
| Severity and risk understanding | severity/materiality and interpretation | reviewed severity labels |
| Timeliness | trigger, observation, first-finding and production times | event eligibility time |
| Evidence quality | claim citations, conflicts and capability receipts | evidence review policy |
| Confidence and calibration | confidence value, kind and method | repeated outcomes or labels |
| Decision quality | selected action, rationale and alternatives | matured decision branches |
| Robustness | case and perturbation identity | matched perturbation cases |
| Stability | repetition identity and canonical digests | repeated identical cases |
| Efficiency | tokens, cost, latency, retries and calls | declared budget |

The output provides the required architecture-side measurements; it does not
contain hidden answer keys or future outcomes. The evaluator joins those only
after execution.

## Interfaces

- `GET /api/experiments/architecture-output/mapping-contract` exposes wrapper,
  graph-envelope and `ArchitectureOutput` schemas.
- `POST /api/experiments/architecture-output/map` accepts exactly one wrapped
  single-agent execution or one wrapped graph execution.
- `finalize_single_agent_execution` and `finalize_agent_graph_execution` are the
  canonical in-process paths.
- Direct mapping remains compatibility-only because it lacks observed behavior.
