# P7 Fixture Context tutorial

## What this demonstrates

This tutorial takes the conditionally accepted calibration object set through a
complete pre-run path:

1. index the scientific design and experiment-object set in a temporary Registry;
2. validate both definitions under the calibration-only acceptance decision;
3. verify the portfolio, pricing and window source bytes;
4. resolve the same closed Fixture Context twice;
5. retain one immutable context and two append-only resolution receipts;
6. prove that the sealed outcome labels and undeclared resources remain unavailable.

Run it from the repository root:

```bash
PYTHONPATH="packages/risk_experiments/src:packages/risk_registry/src" \
  python3 scripts/thesis/tutorial_p7_fixture.py
```

The tutorial uses a temporary Registry and Fixture store, makes no model call,
has no external effect and deletes its temporary records at exit. A `PASS`
result qualifies the resolver mechanics only. It is not thesis evidence and it
does not approve predictive, causal, mitigation or avoidance claims.

## Reading the output

- `acceptance.prohibited_claims` is the guardrail attached to this pilot.
- `context.digest` must remain identical on every repeat over unchanged inputs.
- `reachable_*` is the complete starting resource envelope.
- `denied_references` contains the future labels that agents may not inspect.
- `resolution_receipts` increases without rewriting the immutable context.

The next runtime slice may consume this context, but it must record every
capability selection and cannot add a resource that is absent from the context.
