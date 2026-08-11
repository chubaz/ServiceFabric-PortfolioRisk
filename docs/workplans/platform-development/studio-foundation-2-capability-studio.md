# STUDIO-S2 — Capability Studio v1.2

- Status: implemented and browser-qualified; awaiting user review
- Parent boundary: accepted PLATFORM-P6 structural correction
- Branch: `integration/platform-studio-foundation`
- Verification: `make verify-studio-foundation-s2`
- External financial effects: disabled

## Outcome

Build a minimal description-first Capability Studio over ServiceFabric's
existing CapabilityDefinition, OperationDefinition, schema, effect, Registry
and invocation contracts. A user first asks whether an operation can be
satisfied by the Capability Library. Only a demonstrated gap can become a
human-approved proposal for a new or improved capability.

## Accepted interaction model

1. A compact design conversation occupies the top of the Studio.
2. The assistant searches existing capabilities and packages before proposing
   new development.
3. The assistant may use separate bounded calls for design reasoning and four-option clarification quizzes; suggested answers remain editable.
4. Reuse, compose, improve, create and blocked remain hidden until all material questions are resolved and consensus is explicitly recorded.
5. A decision compiles a temporary blueprint without changing the Proposal Backlog; only explicit blueprint approval persists a proposal.
6. Mature Agent, Workflow, Dashboard, Report and Package discussions may create non-final proposals for their owning Studios.
7. Human approval is required before a capability proposal becomes ready for the future
   Studio-Codex gateway.
8. The Capability Library remains a searchable table at the bottom.
9. Technical definitions remain available in progressive detail rather than
   becoming the default UX.

The Studio–Codex transport and knowledge contract is maintained in
`docs/workplans/platform-development/studio-codex-gateway.md`.

## Resolution and effect policy

- Experiments pin exact capability versions.
- Development may use a validated compatible revision only with a receipt.
- Different methodologies are explicit capabilities, never silent fallbacks.
- Real or provider failures never fall back to synthetic responses.
- Capabilities may read eligible sources and return typed results.
- Writes are limited to System Development definitions/proposals and isolated
  experiment objects or work products.
- Licensed/source databases are always read-only.
- External effects remain visibly disabled placeholders.

## Hosted capability model

Form and functionality are one capability definition. A capability may return a
backend-only typed result or carry a `host_binding` that places its working form
inside a registered ServiceFabric environment: dashboard component, report
section, experiment database view/table, decision record, workflow event,
artifact or localhost development API. The binding pins the framework,
placement, lifecycle operations and connection contract; it is not a separate
object proposal.

The Host Library is extensible through versioned host records and adapters. It
currently exposes the Dashboard, Report Composer, Experiment Data Store,
Decision Repository, Workflow Cycle, Artifact Repository and Local Development
API. Licensed/source databases remain read-only. Studio–Codex builds the
capability implementation and its declared host connection together, and the
agent invokes that unified capability through its registered operations.

Agent, graph/workflow and package architecture discussions may still be handed
to their owning Studios. A dashboard graph, report section, data table,
decision-log event or schedule event requested as capability behavior remains
inside Capability Studio.

## Prototype dependency-aware design

The current implementation proves the interaction and persistence contract; it
is not the final System Agent architecture.

- Capability design requires semantic input sufficiency, not advance certainty
  about every upstream field name or transport format.
- A bounded Agent Schema Adaptation step may convert eligible upstream results
  into the target capability's validated input schema. This is an explicit,
  assumed, non-blocking dependency—not permission to invent missing facts.
- A genuinely absent calculation or source operation becomes a proposed
  capability dependency. It may block implementation while leaving the parent
  design discussion free to reach consensus.
- Dependency relationships are compiled into blueprints, proposals and the
  Studio-Codex build brief.
- Every design turn is auto-saved as a revisioned discussion. A proposed
  dependency can start a child discussion while its parent remains resumable,
  which makes requirement refinement repeatable and idempotent.
- Prototype sessions remain local development records and can be deleted
  without deleting approved proposals, Registry definitions or capability
  implementations.

The bootstrap assistant currently enforces this behavior through bounded
prompting and deterministic contract checks. A later Studio phase should
replace that bootstrap layer with a versioned Static System Agent, or a System
Agent Workflow when feasibility analysis, dependency planning, independent
critique and synthesis benefit from separate bounded roles. The persisted
session and dependency contracts are intended to survive that replacement.

## Fixture review

Level 1 renders a human-readable result appropriate to the output schema.
Level 2 shows input, preparation, validation, resolution, execution and render
stages. Level 3 retains canonical inputs, schemas, operation resolution,
digests, effects, files and receipts.

## Exit gates

1. Existing CapabilityDefinitions and package views are searchable without
   sending every schema to a model.
2. Requirement assessment produces a bounded top-candidate set and one of five
   clear recommendations.
3. Proposal decisions compile temporary blueprints; only explicit blueprint approval persists in the local backlog.
4. Only explicit human approval reaches `ready_for_studio_codex`.
5. At least one real local capability executes through ServiceFabric's
   canonical definition/operation/invocation resolution boundary.
6. A fixture run produces readable, structured and reloadable output plus all
   three review levels and an isolated run folder.
7. Data truth, effects, availability and lifecycle remain continuously visible.
8. Focused contract, API, runtime and browser checks pass.

## Qualification record

- `make verify-studio-foundation-s2` passes 13 focused tests, Python
  compilation, JavaScript syntax, manifest integrity and diff hygiene.
- The browser journey completed deterministic reuse assessment, proposal
  creation, human approval, Studio-Codex brief preparation and a canonical
  historical-VaR fixture run.
- The fixture exposed a readable result, seven-stage work trace, nine-file
  technical record, exact capability resolution, no effects and a read-only
  source-database boundary.
- Desktop and compact-width inspections produced no console warnings or errors.

- The renewed v1.2 browser journey used a live GPT-5.6 Luna feasibility call and
  a separate quiz call, rendered four editable answers plus Other, and reached
  consensus only after two material design questions were answered.
- Compiling the decision left the seven-record backlog unchanged; explicit
  approval created record eight, and deletion returned the backlog to seven.
- A separate dashboard discussion produced a non-final Dashboard Studio
  proposal with four proposed registered capabilities, pre-filled the owning
  Studio, and did not create a Capability proposal or final DashboardPackage.
