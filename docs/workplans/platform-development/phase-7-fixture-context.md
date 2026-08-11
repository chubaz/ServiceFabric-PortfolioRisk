# PLATFORM-P7 — Fixture Context

- Status: first bounded slice implemented, locally verified, registered and live-qualified
- Baseline: locally qualified STUDIO-S5 engineering candidate
- Accepted use: apparatus calibration only
- External effects: disabled
- Verification: `make verify-platform-phase7`

## Outcome

Resolve one methodologically reviewed experiment-object set into a stable,
restart-safe starting context before any agent can act. The same accepted object
set and source bytes must produce the same `fixture_context_digest`; each
resolution receives a separate append-only receipt.

## Implemented slice

- a machine-readable calibration-only methodology acceptance record;
- one canonical reviewed-synthetic B0-versus-structured-agent pilot definition;
- a four-state forward concentration-risk outcome protocol;
- exact bindings to the fictional diversified portfolio, pricing manifest and
  declared window file;
- a source manifest that excludes future outcome labels;
- Registry projections for the scientific design and object set;
- a resolver that requires `validated` or `published` lifecycle state;
- byte-level digest verification before context creation;
- content-addressed local persistence of the immutable context and append-only
  resolution receipts;
- a temporary-store end-to-end tutorial.
- Experiment Kernel step 00 showing acceptance scope, digest, resources and
  prohibited claims, with an explicit read/resolve action;
- backward-compatible loading of pre-S5 experiment digests without rewriting
  their immutable historical values.

## Admission record — 2026-08-10

Both top-level definitions are `validated` in the local Registry. The accepted
Fixture Context is retained under
`~/.servicefabric-portfolio-risk/fixture-contexts-v1` with digest
`sha256:2b2c347ecafa775853aad88f49b7565263726c17c61850d22e1b789d984761d9`.

The focused gate passed 53 P7/Registry/application/architecture tests after the
63-test S5 gate. Live qualification reached `Ready`, displayed the exact digest,
loaded two legacy experiment records, reported no issues or console errors and
kept the experiment worker unavailable.

## Boundaries

The calibration context does not execute a worker, call a model, estimate a
metric, reveal labels, create a decision resolution, simulate a portfolio
change or authorize an external effect. Agent, graph, workflow and capability
execution contracts remain pinned references; runtime resolution is a later
slice.

The acceptance explicitly prohibits thesis inference, predictive superiority,
causal, mitigation and avoidance claims. PLATFORM-P8 must retain those
prohibitions until a new methodology acceptance version supersedes them.

## Exit gates for this slice

1. Scientific design and object-set identities are exact and digest-bound.
2. Fixture resolution rejects candidate-only Registry state.
3. Portfolio and dataset source bytes match the accepted digests.
4. Future outcome labels are outside the reachable source manifest.
5. Repeated resolution produces an identical context and distinct receipts.
6. Restarted local storage returns the same immutable context.
7. Undeclared capabilities and datasets remain denied.
8. Human-only, supra-agent-disabled and effect-free authority survives resolution.

## Next bounded slice

Attach an effect-free run-trace host that consumes an already resolved context,
records capability selections and checkpoints, and stops before any metric or
causal claim. It must not become an automatic scheduler.
