# Mandate candidate contract

Read these sources before changing a candidate:

- `packages/risk_experiments/src/risk_experiments/experiment_objects.py`
- `packages/risk_experiments/src/risk_experiments/reference_mandates.py`
- `apps/portfolio-risk-workbench/labs/mandate_studio.py`
- `docs/thesis/mandate-evaluation-boundary.md`
- `data/fixtures/synthetic/mandates/README.md`

## Canonical bundle

`MandateVersion` owns stable portfolio purpose, scope, horizon, eligible universe, clauses, sources, capability requirements, and non-operative applicable-law notes.

`RiskPolicySet` is the reviewed machine-evaluable interpretation of one exact mandate version. A rule must retain the clause identifier, treatment, semantic metric, capability reference, evaluation basis, missing-data behavior, severity, and governance route.

The Registry receives two projections—Mandate and Risk Policy—but their exact-version relationship must remain resolvable. An experiment selects immutable registered versions; it does not edit them.

## System-treatment vocabulary

Use only the established treatments unless the domain contract is deliberately revised:

- `compliance_test`
- `universe_filter`
- `scored_finding`
- `objective_evaluation`
- `alert_trigger`
- `decision_gate`
- `scheduled_obligation`
- `prospective_assessment`
- `hard_block`

The treatment describes what the system does with a computed policy result. It does not itself create a finding, decision, evaluation row, or financial effect.

## Candidate evidence

The handoff must show:

1. the exact base and proposed references;
2. an identifier-level clause diff;
3. clause-to-rule-to-capability traceability;
4. semantic input roles, units, denominator, temporal basis, and missing-data outcome;
5. normal, threshold-boundary, unavailable-data, and point-in-time test results;
6. unresolved capability or data dependencies;
7. Registry admission readiness without performing admission.
