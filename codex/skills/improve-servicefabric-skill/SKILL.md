---
name: improve-servicefabric-skill
description: Improve an existing repository-owned ServiceFabric Codex skill from completed Studio-Codex run evidence. Use after a real agent, capability, workflow, report, dashboard, scenario, provider, portfolio, mandate, or experiment development run exposes a reusable procedural gap, repeated failure, ambiguous instruction, missing validation, or inefficient context-loading pattern. Produce a bounded candidate diff and validation evidence; never activate, publish, or broaden a skill automatically.
---

# Improve a ServiceFabric Skill

Turn observed run evidence into the smallest reusable skill correction. Treat
the current skill as the baseline and the completed Studio-Codex record as
evidence, not as permission to redesign the workflow.

## Required evidence

Require:

- the exact skill and baseline digest;
- the completed run's durable plan, messages, diff, tests, review and failures;
- the approved object or agent contract;
- a concrete explanation of what Codex could not do reliably or efficiently.

Do not revise a skill from transient processing deltas, private reasoning,
speculation, one stylistic preference, or an unresolved product decision.

## Workflow

1. Read the nearest `AGENTS.md`, the target `SKILL.md`, and only the references
   directly needed for the observed gap.
2. Classify the evidence as one of: missing procedure, ambiguous boundary,
   missing deterministic helper, missing reference, weak trigger description,
   or task-specific issue that should not enter the skill.
3. Check whether `AGENTS.md`, configuration, a contract, test, or application
   code is the correct durable surface. Do not force repository conventions or
   one-run data into a skill.
4. Propose the smallest diff. Keep the skill concise, imperative and focused on
   non-obvious reusable knowledge. Prefer a reference or deterministic script
   when detailed material would inflate the always-loaded workflow.
5. Preserve authority, paths, denied effects, validation integrity and
   progressive disclosure. Never weaken a gate because a run found it
   inconvenient.
6. Validate the skill folder with the repository's declared checks and
   `quick_validate.py` when available. Forward-test only when separately
   approved and useful.
7. Return a candidate revision with evidence traceability, expected future
   benefit, possible regressions, tests, and the human decision required.

## Boundaries

- Modify only the approved repository-owned skill paths.
- Do not edit global or user-owned Codex skills.
- Do not activate, install, publish, merge, or delete a skill automatically.
- Do not store run transcripts, licensed data, secrets, private reasoning, or
  large examples in a skill.
- Do not claim improvement without a before/after test or a precise test plan.
- Keep one-off implementation details in the run record, not in `SKILL.md`.

## Required output

Return:

- observed reusable gap and supporting run records;
- chosen durable surface and why;
- exact skill files changed;
- concise semantic diff;
- validation and forward-test status;
- token/context impact;
- risks and unresolved questions;
- explicit approve, revise, or reject decision.
