---
name: audit-servicefabric-experiment-run
description: Audit and compare complete ServiceFabric PortfolioRisk experiment-run evidence retained in the governed Artifact Repository. Use when Codex must verify that every file compiled for a specific run is present and digest-valid, compare a baseline with a counterfactual, identify uncontrolled differences or missing thesis-design identities, prepare an experiment acceptance record, or determine which object must enter its next Studio revision cycle. Do not use to design the experiment, calculate causal effects, repair objects, or compare mutable unretained folders as thesis evidence.
---

# Audit ServiceFabric Experiment Run

Apply the retained-evidence gate before interpreting or comparing any run
result. Treat the Artifact Repository manifest and its content-addressed blobs
as the authority for file completeness. Never infer completeness from a folder
listing, UI card, filename, or model transcript.

Read [references/run-comparison-contract.md](references/run-comparison-contract.md)
before auditing a pair.

## Workflow

1. Read the repository `AGENTS.md`, current workplan, and
   `docs/workplans/platform-development/studio-foundation-4-experiment-run-audit.md`.
2. Resolve the exact retained artifact IDs for the baseline and
   counterfactual. If the user supplied temporary run IDs, locate their
   retained artifacts first. If a run is not retained, report that it is not
   eligible for thesis comparison; do not silently audit the temporary folder.
3. Ask for or recover from the approved experiment definition the dimensions
   intentionally changed. Never decide the treatment after observing results.
4. Run the deterministic comparison script. Prefer stdout for inspection; use
   `--output` only for an explicitly approved report path.

   ```bash
   python codex/skills/audit-servicefabric-experiment-run/scripts/compare_runs.py \
     compare \
     --artifact-root "$PORTFOLIO_RISK_ARTIFACT_ROOT" \
     --left retained-run-baseline-id \
     --right retained-run-counterfactual-id \
     --variable agent_definition \
     --variable baseline_step
   ```

5. Check, in order:
   - repository integrity for both bundles;
   - one comparison status for every declared file;
   - shared required controls;
   - observed changes against predeclared variable dimensions;
   - explicit thesis-design identities;
   - next-revision requirements.
6. Return the gate result before discussing metrics or findings. Use these
   meanings exactly:
   - `pair_comparable=true`: no integrity failure or uncontrolled difference;
   - `thesis_ready=true`: pair comparable and all required thesis-design
     identities are explicit;
   - `revision_required`: evidence is mechanically comparable but the apparatus
     definition is incomplete;
   - `rejected`: integrity or comparison design is confounded.
7. If the user approves an acceptance record, create it through the Experiment
   Workspace acceptance endpoint so it becomes a retained evidence artifact.
   Do not edit either source run. A new cycle must supersede the prior
   acceptance artifact and preserve both.
8. Route every revision requirement to the object that owns it. For an agent,
   capability, workflow, report, dashboard, package, portfolio/mandate,
   scenario, or provider defect, prepare a separate proposal in that object's
   Studio. Use that Studio's object-building skill through the approved
   Studio–Codex gateway. This audit skill never repairs the object itself.

## Evidence discipline

- Do not load every file into model context. The deterministic kernel validates
  every blob and compares inventory digests; inspect file contents only when a
  blocker or approved metric analysis requires them.
- Do not expose restricted bytes, host paths, credentials, or raw licensed rows
  in a report.
- Do not fabricate missing research-question, baseline-step,
  information-regime, risk-outcome, or metric-definition identities from prose.
- Do not declare a winning system, causal effect, or statistical result. This
  skill establishes evidence eligibility only.
- Do not change experiment lifecycle, queue state, Registry state, object
  activation, publication, merge, or external financial state.

## Required handoff

Return:

- artifact and run IDs for both sides;
- comparison digest and planned variables;
- integrity and complete file-coverage result;
- pair-comparable and thesis-ready states;
- blockers, warnings, and uncontrolled differences;
- acceptance verdict or unrecorded candidate verdict;
- precise next-revision requirements, each mapped to its owning object/Studio;
- commands/tests executed and any report or acceptance-artifact identity.
