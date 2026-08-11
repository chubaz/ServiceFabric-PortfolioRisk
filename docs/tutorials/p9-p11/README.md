# P9-P11 tutorial — from Fixture to executable programme

Open the Experiment Kernel and locate **Arms, labels and repeatable matrix**.
The three cards demonstrate three different duties.

## P9 — arm output admission

P9 compiles the accepted diversified Fixture into 15 exact portfolio-date
cases and two arms: deterministic B0 and structured A1. It expects 30 primary
outputs. It refuses to generate them because the current pricing binding is
metadata rather than point-in-time market observations, and the A1
agent/graph/workflow chain is not yet qualified as one executor.

## P10 — outcome-label review

P10 declares the required four states and the exact 15 case identities. It
keeps labels unreachable by B0/A1 processing. The existing Day-4 binary labels
belong to another outcome definition and cannot be reused. An independent
reviewer must admit a new digest-bound label set.

## P11 — repeatable matrix

P11 crosses two arms, one information regime and two repetitions into four
cells and 60 planned observations. It is deterministic: the same accepted
Fixture produces the same matrix digest. Compilation does not imply execution;
the P9 blockers flow into the matrix.

Run the command-line walkthrough with:

```sh
PYTHONPATH="packages/risk_experiments/src:packages/risk_registry/src:packages/risk_artifacts/src:apps/portfolio-risk-workbench/labs" .venv-day0/bin/python scripts/thesis/tutorial_p9_p11_program.py
```

The correct outcome today is **blocked with explicit resolutions**, not a
metric or winner.
