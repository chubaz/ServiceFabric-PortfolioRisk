# Studio Foundation 6 — Mandate Studio

Status: implemented and browser-qualified foundation.

## Purpose

Provide one System Development surface for designing, reviewing, validating, and admitting immutable portfolio mandates and their exact machine-evaluable risk policies. The Studio reuses `MandateVersion`, `RiskPolicySet`, registered capabilities, and the shared Registry; it does not introduce a parallel UI-only mandate object.

## Delivered slice

- a minimal five-stage Mandate Studio workflow;
- three reviewed-synthetic, public-reference-informed mandate and policy bundles;
- exact clause-to-rule-to-capability validation;
- readable governance and missing-data review;
- diff-only Studio-Codex design briefs;
- a dedicated bounded Studio-Codex skill;
- atomic admission of one Mandate and one Risk Policy candidate into the shared Registry;
- Registry filtering and exact relationships between the admitted projections.

## Metric and data readiness

Mandate validation distinguishes three separate facts:

1. the clause and policy rule are structurally valid;
2. the named capability exists;
3. a reviewed capability chain actually constructs the named metric with the declared unit, denominator and temporal basis.

The third fact cannot be inferred from a capability name. A missing semantic implementation creates a stable proposal candidate attached to the rule. It is loaded into Capability Studio for reuse-first discussion, but is not written to the approved proposal backlog until a human concludes and approves that design discussion.

Private or confidential assumptions are declared as semantic `MandateDataRequirement` roles, never stored as values inside the Mandate or Portfolio. An experiment binds each role to an exact `DatasetRevisionBinding` in its point-in-time `DataSnapshotManifest`. The binding records revision, digest, availability time, truth label and rights policy; raw values remain in the governed source. Missing or ineligible inputs produce `unable_to_assess_and_escalate`, never a constant assumption or synthetic fallback.

The liability-aware pension fixture now contains seven policy clauses and eight explicit experiment-scoped data roles, including restricted benefit outflow, liability cash-flow, funded-status and sponsor-contribution inputs.

## Authority boundary

The Studio works only at design time. Public sources remain reference-only. Validation and Registry admission create no experiment, breach, decision, legal interpretation, live portfolio mutation, trade, order, broker message, or other external effect.

## Deferred dependencies

- Broader PortfolioVersion composition and experiment selection remains deferred; the first institutional-mandate application slice is recorded in `studio-foundation-7-mandate-application.md`.
- Graph-backed clause and covenant navigation: future knowledge/context phase.
- Document ingestion and LLM-assisted clause extraction: future provider/connector phase.
- Breach episodes, experimental failures, and framework comparison: Evaluation Studio design.
- Regulatory knowledge and applicable-law effects: separately approved future design.

## Acceptance evidence

The foundation is acceptable when all reference bundles validate structurally, each executable clause proves a reviewed metric construction chain, unresolved metrics produce governed proposal candidates, Mandate and Risk Policy projections can be admitted together, the UI explains the resulting policy without exposing low-level form clutter, and the Studio-Codex handoff preserves satisfied clauses as a bounded diff.

Qualification evidence: 61 focused contract, Registry, application and control-plane tests pass; the JavaScript bundle parses cleanly; the localhost workflow was verified from mandate selection through validation, diff-brief preparation and the Registry-admission confirmation boundary without admitting a version automatically.
