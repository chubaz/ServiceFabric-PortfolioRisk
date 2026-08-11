---
name: servicefabric-portfolio-mandate-builder
description: Build or revise a governed ServiceFabric PortfolioRisk MandateVersion and its exact RiskPolicySet from an approved Mandate Studio design brief. Use when Studio-Codex is asked to implement, correct, validate, or prepare a candidate portfolio mandate, IPS interpretation, mandate clause, governance rule, or mandate fixture in the ServiceFabric PortfolioRisk repository.
---

# Build a ServiceFabric Portfolio Mandate

Turn an approved Mandate Studio brief into a bounded, tested candidate. Treat the mandate and its machine-evaluable policy as one design bundle with separate immutable identities. Never silently register, activate, publish, merge, or apply the candidate to an experiment.

## Required inputs

Require:

- a base mandate reference or an explicit new-mandate decision;
- the portfolio purpose, governed scope, horizon, effective date, and requested change;
- clause classifications: constraint, objective, preference, trigger, obligation, or reference-only note;
- semantic metrics, units, denominator, temporal basis, and missing-data treatment;
- intended system treatment, severity, and governance route;
- source provenance and its authority effect;
- representative, boundary, and missing-data fixtures.

If a material field is unresolved, return the smallest blocking question. Do not convert ambiguous prose into an executable hard constraint.

## Workflow

1. Read `AGENTS.md`, `docs/workplans/current.md`, the active workplan, and `references/mandate-contract.md`.
2. Load the exact base `MandateVersion` and `RiskPolicySet`. Work as a diff: preserve satisfied clauses, stable identifiers, provenance, governance, and tests unless the approved brief changes them.
3. Search existing mandate fixtures, policy rules, capabilities, semantic data roles, and Registry projections. Reuse before proposing a new object or capability.
4. Separate non-operative source text from executable policy. Applicable-law material remains reference-only unless an independently approved regulatory-knowledge design exists.
5. Implement the candidate with the canonical `risk_experiments` models. Bind every executable clause to exactly one reviewed policy rule and a registered capability.
6. Make missing or stale data produce `unable_to_assess`, abstention, or escalation as declared. Never interpret missing data as compliance.
7. Validate exact-version binding, clause coverage, capability availability, semantic units, temporal eligibility, governance routing, and absence of unauthorized effects.
8. Run normal, threshold-boundary, missing-data, identifier-mismatch, and look-ahead fixtures plus focused repository tests.
9. Return a candidate handoff containing the diff, changed files, validation results, unresolved dependencies, version impact, and the explicit human decision required next.

## Hard boundaries

- Do not create a parallel mandate, policy, breach, finding, decision, or evaluation domain model.
- Do not store mutable run outcomes or breach episodes in the mandate.
- Do not write to licensed or external data sources.
- Do not add order, broker, trade, hedge, rebalance, live-portfolio, or external communication effects.
- Do not claim a public reference is a copied policy, legal interpretation, or compliance opinion.
- Do not register, publish, activate, merge, or attach the candidate to an experiment without explicit approval.
- Do not replace the whole candidate when a bounded diff can satisfy the request.

## Done when

The candidate uses canonical contracts, every executable clause is traceable to a reviewed policy rule and available capability, temporal and missing-data behavior is tested, source authority remains honest, effects remain within the approved boundary, and the handoff clearly separates executable behavior from deferred work.
