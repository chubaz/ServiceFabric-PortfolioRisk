# STUDIO-S5.1 — Scientific Identity Pack

- Status: implementation complete and locally verified; candidate commit pending
- Parent: STUDIO-S5 experiment object model and readiness gate
- Verification: `make verify-studio-foundation-s5-1`
- External financial effects: disabled

## Outcome

Make the scientific meaning required by the S4 evidence gate explicit and
machine-validatable before Fixture Context development. One immutable
`ScientificDesignPack` binds six independently digest-bound definitions:

1. `ResearchQuestionDefinition`;
2. `HypothesisDefinition`;
3. `BaselineDefinition`;
4. `InformationRegimeDefinition`;
5. `RiskOutcomeDefinition` with an ordered outcome scale;
6. `MetricDefinition`.

The pack supplies the five exact identity references consumed by the retained
run comparison gate. Hypothesis remains separately explicit even though it is
not itself an S4 comparison control.

## Design decisions

- `risk_experiments` owns scientific experiment meaning.
- The Registry indexes a complete pack under `scientific_design`; it does not
  reinterpret or duplicate the pack's definitions.
- Every component reference includes kind, namespace, ID, version and content
  digest. A shared label or prose string is not identity.
- Hypothesis must reference the exact research question.
- Metric must reference the exact risk outcome.
- Outcome states are ordered, contiguous and identify at least one breach
  state; an unlabelled narrative scale is invalid.
- Information regimes declare both evidence categories and resource references,
  preserve missing information as missing, and distinguish reachable resources
  from resources actually used at runtime.
- An `ExperimentDefinition` may pin one scientific-design Registry identity.
  Legacy experiments may omit it for migration, but omission prevents future
  thesis readiness.
- Experiment creation and validation reject a pinned pack that is not saved in
  an eligible Registry lifecycle state.

## Exit gates

1. All six component definitions are strict, immutable and canonically
   digest-bound.
2. A content change invalidates the prior component and pack digests.
3. Broken question/hypothesis and risk-outcome/metric links fail validation.
4. Baseline and information-regime resource sets are unique and deterministic.
5. Risk-outcome ordinals are contiguous and include a breach state.
6. The pack emits exactly the five explicit S4 comparison identities.
7. The pack has one exact Registry identity of kind `scientific_design`.
8. An experiment can pin that identity only after it is saved in the Registry.
9. Existing experiments without a pack remain readable and explicitly
   non-thesis-ready.
10. Focused contract, Registry, S4 comparison, API and architecture tests pass.

## Acceptance boundary

This batch establishes the schema and enforcement mechanism. It does not claim
that a particular thesis question, outcome scale, baseline ladder or metric has
received methodological acceptance. Candidate pack content must be reviewed
before it is registered and frozen for a pilot.

## Verification record — 2026-08-10

`make verify-studio-foundation-s5-1` passed 52 focused experiment-contract,
Registry, retained-run comparison, API and architecture tests, followed by
Python compilation, application-manifest integrity and diff checks. This is a
local working-candidate result; the dirty Studio integration worktree has not
been represented as an immutable or merged candidate.

## Non-goals

- no Scientific Design Studio UI;
- no automatic generation of research questions or metrics;
- no metric calculation, causal estimation or finding interpretation;
- no Fixture Context resolver, worker or run-state change;
- no mandate, portfolio, environment, capability-pack or supra-agent policy;
- no opening of historical out-of-sample data.
