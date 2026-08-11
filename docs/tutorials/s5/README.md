# S5 experiment-object tutorials

These seven tutorials exercise the object contracts completed before Fixture
Context development. They use one deterministic reviewed-synthetic teaching
fixture. The output is not thesis evidence and does not run an agent, model,
worker, connector or portfolio effect.

For a non-technical overview, start with
[What S5 built in plain language](what-s5-built.md).

Run every tutorial from the repository root:

```bash
python3 scripts/thesis/tutorial_s5_objects.py all
```

A successful run ends with `"status": "PASS"` and displays the component and
fixture digests. Individual tutorials are:

1. [Scientific design](01-scientific-design.md)
2. [Portfolio governance](02-portfolio-governance.md)
3. [World context](03-world-context.md)
4. [Reachable resources](04-reachable-resources.md)
5. [Agent and decision authority](05-agent-authority.md)
6. [Outputs and evaluation](06-output-evaluation.md)
7. [Reproducibility and counterfactuals](07-reproducibility.md)

These are contract tutorials. The later P7 tutorial will resolve the same
objects into materialized Fixture Context inputs.
