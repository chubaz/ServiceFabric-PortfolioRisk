# THESIS-D2-DATA — Real-data admission (accepted checkpoint)

- Status: in progress
- Depends on: `THESIS-D1` complete and accepted
- Next state: `THESIS-D2-PORTFOLIOS` / `portfolio_definition`

The CRSP/Compustat licensed local bridge is implemented and accepted. Daily-
primary and monthly-smoke builds were completed locally under explicit human
authorization. Licensed data remain external and private; CI uses synthetic
schema-compatible fixtures only.

The candidate-universe artifact is the final currently implemented artifact.
Human-governed portfolio definition is the next stage. Metrics remain queued.

The real-data gate requires explicit external paths and a daily-primary
`dsf.parquet`. A monthly smoke using `msf.parquet` is diagnostic only. CI uses
synthetic schema-compatible fixtures and reports no licensed admission.

Acceptance requires control and boundary tests, the Day 1 regression gate,
whitespace validation, and a clean `vendor/servicefabric` submodule.
