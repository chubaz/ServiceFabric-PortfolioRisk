# THESIS-D2-PORTFOLIOS — Human-governed portfolio definition

- Status: in progress
- Depends on: accepted CRSP/Compustat bridge and candidate-universe artifact
- Next state: `THESIS-D2` / `metrics_decision_kernel`

The specialist entry point is the candidate-universe artifact written by the
accepted `risk_data` bridge. Implement the contract in
`docs/contracts/thesis-real-portfolio-selection-v0.1.md`:

```text
candidate-universe artifact + human-reviewed selection YAML
    -> validated fixed-quantity PortfolioDefinition YAML files
```

The system must never choose securities or quantities. The specialist may add
only the frozen Day 2 paths in `config/agent/thesis-sprint/lanes.json`, plus
the exact Day 2 handoff. No metrics, portfolio selection algorithm, optimizer,
broker, order, trade, rebalance, or portfolio mutation is in scope.

Inputs and outputs are external under `THESIS_DATA_ROOT`; candidate universe
and reviewed selections must retain immutable snapshot and point-in-time
evidence. Missing availability remains missing and requires rejection or an
explicit warning.
