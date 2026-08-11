# Tutorial 7 — Reproducibility and counterfactuals

Run:

```bash
python3 scripts/thesis/tutorial_s5_objects.py reproducibility
```

The first check resolves the same object set twice and obtains the same Fixture
Context digest. The second changes only the declared scenario. The world and
overall fixture digests change, while the resource, authority and evaluation
digests remain equal. This is how the apparatus identifies a controlled
counterfactual without comparing opaque configuration blobs.
