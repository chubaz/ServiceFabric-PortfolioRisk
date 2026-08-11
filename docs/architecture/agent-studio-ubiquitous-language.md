# Agent Studio ubiquitous language

- Status: normative application language
- Scope: Agent Studio authoring, verification, Studio-Codex development and Registry admission
- Principle: one term names one concept throughout the interface, API projections, tests and tutorials

## Canonical terms

| Term | Exact meaning | Must not mean |
|---|---|---|
| Agent | A bounded worker that receives context, invokes admitted capabilities, produces work products and escalates under policy. | A prompt, model, workflow or capability. |
| Agent Blueprint | The reusable definition of an agent's outcome, context, capabilities, output, authority and evaluation expectations. | One run or a generated Python file. |
| Blueprint Draft | The mutable Agent Blueprint currently being designed. Each refinement is a validated diff against its prior digest. | A saved Registry version. |
| Configuration Review | The compiler and semantic verification record for one exact Blueprint Draft digest. | A human authorization or a Codex run. |
| Requirement | A user or system condition the Agent Blueprint must satisfy. | A suggested implementation detail. |
| Material Finding | An unresolved critical or high requirement. It blocks development handoff or Registry admission. | A low-priority note, satisfied requirement or repeated wording. |
| Development Proposal | The immutable, bounded request that states the blueprint, allowed paths, verification commands, skill and authority for Studio-Codex. | An Agent Blueprint or a Registry candidate. |
| Development Job | One authorized Studio-Codex execution that plans, changes, verifies and independently reviews work in its bounded workspace. | A workflow-cycle agent run. |
| Diff | The exact change between the base and revised blueprint or code workspace. Unlisted content is preserved. | A regenerated full definition. |
| Test Run | One execution against a declared fixture and expected behavior. | Configuration Review or Development Job. |
| Agent Version | An exact, immutable Agent Blueprint identity and version admitted to the Registry. | A mutable draft. |
| Registry Admission | The explicit decision to index one exact tested Agent Version in the Registry. | Code merge, deployment or activation. |
| Fixture Context | A labelled, point-in-time input environment used to test an Agent Version. | A model-generated narrative or hidden prompt context. |
| Work Product | An output from one Test Run or experiment. | A reusable definition. |
| Artifact | A Work Product deliberately retained with provenance and lifecycle policy. | Every temporary file or reusable system object. |

## Normal lifecycle

```text
Describe job
  -> Blueprint Draft
  -> Configuration Review
       -> no Material Finding
       -> or bounded diff -> Configuration Review
  -> Development Proposal (only when repository work or independent review is needed)
  -> human authorization
  -> Development Job (plan -> change -> verify -> independent review)
  -> Test Run evidence
  -> Registry Admission
  -> Agent Version
```

Only three normal user decisions are consequential:

1. define or revise the intended agent behavior;
2. authorize a bounded, cost-bearing Development Job;
3. admit an exact tested Agent Version to the Registry.

Choosing Luna versus Codex, repeating satisfied requirements, copying handoff
text, rerunning an unchanged review and manually starting an already-authorized
job are implementation mechanics and are not normal user decisions.

## Invariants

1. A refinement never rewrites the Blueprint Draft from scratch.
2. Satisfied requirements remain attached by stable identity and are not shown as open work.
3. A later formulation supersedes earlier wording of the same unresolved user refinement.
4. Only new or regressed critical/high requirements are Material Findings.
5. The Studio selects the least expensive adequate resolution route.
6. Authorization covers one exact Development Proposal and starts its job.
7. Permission requests that exceed the authorized boundary still stop for human review.
8. Development Job completion does not imply Registry Admission.
9. Registry Admission does not imply deployment, activation or financial authority.

