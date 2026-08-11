# Experimental object operating model

An object is either **information** (a frozen description of the world),
**processing** (a bounded way of interpreting it), or **governance** (a rule
about what may happen). Objects are immutable once admitted; improvement means
a new version and the next experiment explicitly selects it.

## 1. Scientific design, object set, Fixture, and Experiment Kernel

| Object | Definition | Agent relationship | Evolution |
|---|---|---|---|
| Scientific design | Question, hypothesis, baseline, information regime, outcome and metric | Cannot be edited during a run | New review-approved design version |
| Experiment object set | Linked governance, world, resources, authority and output/evaluation definitions | Defines the permitted universe | New set whenever an included object changes |
| Fixture Context | Resolved bytes, exact revisions, reachable resources and acceptance boundary | Only permitted starting context | Never mutates; re-resolution adds a receipt |
| Experiment Kernel | User lifecycle: resolve, define, prepare, trace, qualify | Hosts the process; not an analytical authority | Adds verified stages without altering stored runs |

The current Fixture is calibration-only. It seals outcome labels and forbids
causal, prediction, mitigation, avoidance and thesis-inference claims.

## 2. Portfolio, mandate, policies, reports, dashboards and run objects

**Portfolio version** is a dated holdings snapshot with provenance, currency
and truth class. **Mandate version** states objective, horizon, universe and
constraints. **Risk policy set** turns constraints into named rules and human
escalation. An agent may read and cite them; it cannot rewrite them or change a
portfolio.

Mandate clauses also declare their system treatment, required registered
capabilities and governance route. Clause extraction and rule approval happen
before experiment assembly. Breach episodes, mandate outcome labels and the
experimental failure taxonomy belong to evaluation, as defined in
`docs/thesis/mandate-evaluation-boundary.md`.

**Market/environment snapshot** defines the available-at data boundary,
scenario and point-in-time view. **Dataset access grants** specify which
declared capability can use which dataset and operation. Missing or denied
information remains explicit; it is never silently treated as zero.

**Report template** is presentation structure; **dashboard package** is a view
and its allowed inputs. Neither owns calculations: every displayed number must
point to an evaluated retained artifact. New templates create new versions,
while reports from old runs remain linked to their historical versions.

## 3. Agents, capabilities and supra-agents

An **agent definition** states role, expected output, evidence duties,
resources, uncertainty/abstention behaviour and authority. An **agent graph or
workflow** declares order and hand-offs. A **capability** is a typed operation
with source-access rights, output contract and tests. An agent uses a
capability; it does not become the capability.

A **supra-agent** is an orchestration policy over agents. It requires a
separate treatment, conflict policy, budget and human override. It is currently
disabled and outside the first comparative studies.

## 4. Connectors, model routes, risk context and thesis evidence

**Connector definitions** identify an integration, rights, revision and failure
semantics; credentials remain local opaque references. **Model route policy**
identifies an allowed provider/model, version, budget and prompt-output
boundary. A changed model route is a new treatment, not a hidden implementation
detail.

**Environmental risk context** combines market snapshot, scenario,
portfolio-environment view and context graph. **Thesis evidence** starts only
when retained runs, independently reviewed labels, an evaluation plan and an
acceptance record form a comparable evidence bundle. A trace alone is apparatus
evidence, not performance evidence.

## 5. Evaluations

An **evaluation suite** binds a metric, outcome protocol, thresholds,
missingness/censoring rules and required outputs. It runs after processing and
cannot be improvised by a dashboard. Thesis-capable evaluation needs
independently reviewed labels, B0 and treatment outputs on the same cases,
paired metric calculation, censoring disclosure, uncertainty and an
out-of-sample boundary.

## Current P8 workflow

1. Resolve the accepted Fixture Context.
2. Record an effect-free trace: declared access, checkpoints, finding,
   uncertainty and a human proposal.
3. Inspect the retained trace in the Artifact Repository.
4. Do not interpret it as a result. The next slice implements deterministic
   B0/treatment outputs, followed by a separate evaluation runner.
