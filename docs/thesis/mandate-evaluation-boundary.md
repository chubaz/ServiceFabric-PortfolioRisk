# Mandate, policy, decision and evaluation boundary

Status: accepted design input for the future Mandate Lab and Evaluation Studio.
This document does not activate legal interpretation, compliance authority or
financial effects.

## 1. Ownership

The mandate is a reusable immutable governance definition selected before an
experiment starts. It states the portfolio purpose, horizon, eligible universe,
constraints and intended system treatment. The mandate may declare which
registered capabilities are required to interpret or evaluate each clause.

The `RiskPolicySet` is the reviewed machine-evaluable interpretation of one
exact `MandateVersion`. Each rule binds:

- one mandate constraint;
- one system treatment;
- one semantic metric or classification;
- one registered capability;
- one current, historical, proposed, scenario or forecast basis;
- one missing-data policy;
- one severity and governance route.

Clause extraction, interpretation, capability selection, rule validation and
human approval occur in System Development before an experiment selects the
immutable versions. Agents may propose changes but cannot revise either object
during a run.

A policy result is an observation. A `Finding`, `Alert` or `DecisionProposal`
communicates its consequence and routes it to the required governance level.
No mandate or policy result authorizes a live portfolio or external effect.

## 2. System treatments

| Treatment | Intended result |
|---|---|
| `compliance_test` | Current or historical compliant/breach/unable-to-assess status |
| `universe_filter` | Eligibility result for a held or proposed instrument |
| `scored_finding` | Non-binary relevance or quality finding |
| `objective_evaluation` | Progress or shortfall against a stated objective |
| `alert_trigger` | Reviewable alert when a reviewed trigger is met |
| `decision_gate` | Mandatory pause and governed decision |
| `scheduled_obligation` | Evidence that a review or report is due |
| `prospective_assessment` | Scenario or forecast warning with model provenance |
| `hard_block` | Prohibit a simulated proposal under an approved experimental policy |

`hard_block` does not create a trade, order, broker message or live portfolio
mutation. Applicable-law notes remain reference-only until a separately
approved regulatory-knowledge design exists.

## 3. Evaluation owns mandate outcomes

The mandate enables evaluation but does not retain mutable run outcomes. The
future evaluation object owns:

- point-in-time policy assessments;
- compliant, attention, breach and unable-to-assess labels;
- independently reviewed expected outcomes;
- unique breach episodes and their lifecycle;
- alert and decision quality;
- experimental failure labels;
- framework-comparison metrics and uncertainty.

A breach episode is not the same as an evaluation row. Re-evaluating one active
condition every fifteen minutes must not count as dozens of independent
breaches. An episode record should retain first observed, last observed,
maximum severity, acknowledgement, exception, cure and recurrence evidence.

Prospective model results must remain distinct from observed violations. A
scenario or forecast becomes a binding policy result only when the reviewed
rule explicitly names that evaluation basis, model/capability and threshold.

## 4. Experimental failure taxonomy

| Failure class | Question answered by the evaluation |
|---|---|
| Source interpretation | Did the design agent identify the intended clause correctly? |
| Rule compilation | Does the reviewed rule faithfully and completely represent the clause? |
| Applicability | Was the correct rule applied to the correct portfolio, sleeve, instrument and date? |
| Capability selection | Did the agent select the appropriate registered operation? |
| Data binding | Were the required semantic inputs resolved with correct units and identifiers? |
| Temporal correctness | Was every input eligible at the experiment as-of time? |
| Calculation | Does the deterministic or model capability produce the expected result? |
| Missingness | Did unavailable or stale data produce abstention rather than false compliance? |
| Detection | Was a reviewed material breach or trigger found? |
| False alert | Was a breach or trigger claimed when the reviewed outcome was negative? |
| Governance routing | Was the finding sent to the correct authority and workflow? |
| Authority | Did an agent remain inside the selected experimental authority envelope? |
| Explanation | Were meaning, evidence, uncertainty and consequence communicated correctly? |
| Decision | Was the proposed or experimental resolution consistent with mandate and policy? |

These labels should be attributed to the responsible stage. A correct policy
calculation followed by a poor narrative is an explanation failure, not a
calculation failure. A missing issuer mapping is a data-binding failure, not
evidence that the portfolio complies.

## 5. Core measures

The Evaluation Studio should support, at minimum:

- rule-extraction precision, recall and clause coverage;
- policy-compilation agreement with human-reviewed rules;
- breach detection precision, recall and critical false-negative rate;
- eligibility-classification accuracy;
- unable-to-assess and abstention appropriateness;
- point-in-time and look-ahead violation rate;
- evidence and capability-receipt coverage;
- governance-routing accuracy;
- mandate-inconsistent decision rate;
- time to detection, acknowledgement and cure;
- repeated-alert suppression and unique breach-episode counts;
- explanation usefulness and reviewer override rate;
- latency, model calls, token use and monetary cost.

Return performance is not a substitute for these measures. It may be studied
as a separate downstream outcome only when the scientific design explicitly
defines its causal limits and comparison boundary.

## 6. Experimental control

To compare agentic frameworks, hold the portfolio version, mandate version,
risk-policy version, fixture/data revision, temporal boundary and deterministic
capability versions constant. Vary the agent, graph, workflow, model route or
authority policy as declared treatment factors.

Later studies may vary mandate complexity deliberately. Those experiments must
record the mandate as a factor rather than interpreting cross-mandate result
differences as framework performance.

Outputs must be retained by exact version and run identity so that two
frameworks can be compared against the same reviewed expected outcomes.

## 7. Reference-informed synthetic fixtures

The repository fixtures in `data/fixtures/synthetic/mandates/` adapt public
institutional-policy structures into reviewed-synthetic ServiceFabric inputs:

- institutional diversified growth;
- liability-aware pension;
- European corporate-bond income.

They are research fixtures, not copied policies or legal interpretations. A
public reference has `reference_only` authority. Any metric whose implementation
is not yet registered remains a declared capability requirement and must return
unavailable or unable-to-assess in an experiment.
