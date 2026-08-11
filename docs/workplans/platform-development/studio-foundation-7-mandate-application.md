# Studio Foundation 7 — Mandate Application

Status: implemented and browser-qualified first vertical slice.

## Purpose

Demonstrate how a saved Mandate and its exact Risk Policy govern a portfolio inside Agent Application before adding narrative agent interpretation. The slice keeps calculation, interpretation, and authority separate: canonical capabilities calculate typed results, deterministic policy assessment creates findings, and any resulting Decision Proposal remains temporary and human-only.

## Delivered slice

- an Agent Application surface for selecting an admitted mandate and a reviewed fixture case;
- exact Registry gates for the Institutional diversified growth Mandate and Risk Policy versions;
- reuse of the existing reviewed-synthetic diversified `PortfolioVersion` and point-in-time synthetic market fixture;
- canonical `portfolio.snapshot.create` and `portfolio.exposure.summarize` capability execution with typed receipts;
- clause assessments with explicit `compliant`, `breach`, and `unable_to_assess` states;
- canonical `RiskFinding` records and an effect-free D1 `DecisionProposal` for a material breach;
- a missing-price case that fails closed instead of inferring a zero price or false compliance;
- readable inputs, calculations, governance, capability receipts, and decision consequences in one review surface.

## Qualified result

For the reviewed snapshot, the application reports:

- cash minimum: compliant at 18.69% against a 5% minimum;
- issuer concentration: breach at 21.35% against a 10% maximum;
- five-year annualized real-return objective: unable to assess because no current capability supplies the required inflation-adjusted five-year portfolio return.

The incomplete-data case reports all three rules as unable to assess, retains the failed snapshot receipt, creates no compliance finding, and creates no Decision Proposal.

## Boundaries

- The source portfolio and market observations are explicitly reviewed synthetic data.
- No LLM is called in this first calculation slice.
- No portfolio, mandate, policy, Registry, external database, or source fixture is mutated by a run.
- Application outputs are temporary work products and are not automatically admitted to the Artifact or Decision repositories.
- The real-return objective is not approximated with a semantically different return capability.

## Next increments

1. Add a registered Experimental Specialist that interprets the deterministic assessment without replacing or recalculating its facts.
2. Add historically grounded portfolio/data bindings while preserving the same point-in-time and data-truth declarations.
3. Implement and validate a capability chain for annualized inflation-adjusted five-year portfolio return.
4. Permit explicit retention of comparable run outputs in the Artifact Repository.
5. Permit explicit human lifecycle action on temporary Decision Proposals; never admit them automatically.
6. Move breach episodes, experimental failures, and cross-framework quality measures into the future Evaluation object rather than the Mandate.

## Acceptance evidence

The relevant architecture, Registry, application, runtime, experiment, and phase suites pass with 99 tests. The JavaScript bundle parses cleanly, the diff has no whitespace errors, and both the reviewed and missing-price cases were qualified through the browser against an isolated temporary Registry. The default local Registry was not changed during qualification.
