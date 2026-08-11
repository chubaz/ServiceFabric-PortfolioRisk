# Tutorial 2 — Portfolio governance

Run:

```bash
python3 scripts/thesis/tutorial_s5_objects.py governance
```

Observe three separate references. The portfolio contains the holdings-state
identity, the mandate says what the portfolio is for, and the risk policy holds
executable thresholds. The tutorial verifies that the policy references the
exact mandate rather than copying its prose.
