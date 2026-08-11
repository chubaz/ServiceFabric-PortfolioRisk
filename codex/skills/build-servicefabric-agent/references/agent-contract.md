# ServiceFabric agent candidate contract

## Classes

### Static System Agent

A versioned system object supporting one bounded Studio. It may explain, teach, clarify, compare alternatives, assess feasibility, critique, plan, synthesize, validate, and produce typed design proposals. It receives design context rather than portfolio context. It cannot finalize, implement, register, activate, or publish its proposal.

Required visible scope:

- owning Studio;
- supported intents;
- repository-relative codebase paths;
- knowledge sources;
- skills;
- proposal-only authority.

The foundational recipe is `system-agent-agent-studio-architect@0.1.0` in `apps/portfolio-risk-workbench/labs/agent_studio.py`.

### Experimental Specialist Agent

A Registry-pinned agent used inside an isolated experiment. It receives canonical point-in-time portfolio-risk context, may request only effect-free registered risk capabilities, produces a typed experimental work product, and stops at the declared human or experimental supra-agent decision boundary.

## Correct Codex context

Supply Codex with decisions, not the complete history:

1. approved blueprint and version;
2. relevant Registry records and canonical contract schemas;
3. selected skill and bounded paths;
4. current workplan and acceptance criteria;
5. focused code excerpts or file references;
6. representative, failure, and adversarial fixtures;
7. explicit done-when checks.

Do not send entire run logs, datasets, or broad repository dumps when a digest and file references suffice.

## Reuse-first resolution

Resolve every request in this order:

1. reuse an existing agent version;
2. configure or compose existing contracts and capabilities;
3. revise an existing candidate version;
4. implement a new agent candidate only when the first three cannot satisfy the outcome.

## Lifecycle

`design discussion -> validated proposal -> human approval -> isolated candidate build -> fixture qualification -> human review -> optional Registry admission -> optional activation`

Studio-Codex owns candidate implementation and worktree mechanics only after approval. The Agent Studio Architect owns design assistance and proposal preparation. Neither may silently cross the Registry or activation boundary.

## Minimum evaluation

- Representative: the intended job produces the declared typed output.
- Failure: missing context, dependency, capability, or mapping leads to abstention or review.
- Adversarial: embedded instructions cannot expand scope, capabilities, authority, or effects.
- Regression: the relevant existing Agent Studio and canonical contract tests remain green.
- Budget: any paid model evaluation declares call, token, and monetary ceilings before execution.

## Candidate handoff

Report:

- candidate ID, class, and version;
- configuration-only versus code-required outcome;
- reused definitions and new dependencies;
- changed files and why;
- fixtures and tests run;
- known limitations and deferred phases;
- next human decision: revise, reject, admit to Registry, or activate in an approved environment.
