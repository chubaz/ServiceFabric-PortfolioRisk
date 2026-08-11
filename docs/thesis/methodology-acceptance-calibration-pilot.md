# Methodology acceptance — calibration pilot

- Decision: **accepted for apparatus calibration only**
- Review date: 2026-08-10
- Reviewer: `codex.delegated-methodology-review`
- Authority: explicit user instruction in the active development task
- Scientific design: `scientific_design:portfolio-risk.thesis:calibration-agent-vs-b0@1.0.0`
- Scientific digest: `sha256:28e8855df265b4b32325a19bf00b58b4de3e138a5ae0f753a07a12b22afb4a97`
- Object set: `experiment_object_set:portfolio-risk.thesis:calibration-agent-vs-b0@1.0.0`
- Fixture digest: `sha256:2b2c347ecafa775853aad88f49b7565263726c17c61850d22e1b789d984761d9`
- Acceptance digest: `sha256:2d35f843aae6527c350f98c3336d78369b02cffba1a2d5426026bab4a200c297`

## Decision in ordinary language

The candidate is sufficiently precise to test whether the experimental
apparatus freezes and resolves the right information. It is not sufficiently
powered or labelled to answer the thesis question. It may therefore enter P7
Fixture Context development, but results produced from it must remain technical
calibration evidence.

## Review of the scientific design

| Question | Decision |
|---|---|
| Primary question | Accepted for calibration. It names the 45 synthetic portfolio-date cases, paired B0 comparator, structured-agent treatment and paired error estimand. |
| Hypothesis | Accepted for calibration. Direction and falsification include zero/worse performance and differential censoring. |
| Baseline | Accepted. B0 is one deterministic 35% largest-position policy applied to the same context. |
| Information regime | Accepted. Holdings, prices and declared window context are finite; unavailable data remains missing. |
| Outcome | Protocol accepted, labels pending. The scale is `optimal`, `good`, `bad`, `very bad`, with five-session headroom, breach duration and magnitude rules. |
| Primary metric | Accepted for descriptive calibration. It is the paired treatment-minus-B0 difference in absolute ordinal error. |
| Uncertainty | Accepted only as descriptive. A clustered paired bootstrap is specified, but the current fixture does not justify inferential claims. |
| Mandate and risk policy | Accepted for this narrow pilot. Only concentration risk is represented; 35% matches the fictional diversified portfolio definition. |
| Scenarios | Accepted for deterministic technical coverage. The three stress/control windows are fictional and cannot establish external validity. |
| Repetitions | Accepted for repeatability testing only. Two repeats are not a power calculation. |
| Authority | Accepted. Resolution is human-only; supra-agent and external effects are disabled. |
| Sealed outcomes | Accepted. `labels.parquet` is explicitly outside the reachable source manifest. |

## Claims that are prohibited

This candidate cannot support claims of:

- thesis-level inference;
- predictive superiority;
- a causal effect;
- risk avoidance;
- risk mitigation.

The effect-free run may classify, explain and propose. It cannot change a
portfolio outcome, so mitigation or avoidance requires a separately designed
simulated-intervention counterfactual.

## Required revision before the first inferential experiment

1. Create and independently review the four-state forward outcome labels.
2. Run power and dependence analysis before fixing the sample size.
3. Add at least one historical point-in-time scenario family.
4. Predeclare breach, calibration and abstention metrics and multiplicity rules.
5. Qualify any non-deterministic model route before replacing the fixture provider.

This is a cyclical acceptance record. Those revisions create a new version and
new digest; they do not overwrite this calibration decision.
