# THESIS-D2-DATA — Real-data admission

- Status: in progress
- Depends on: `THESIS-D1` complete and accepted
- Next state: `THESIS-D2` / `metrics_decision_kernel`

Freeze the control plane for admitting seven externally held licensed Parquet
sources. This stage records source identity, schema, and access boundaries only;
no bridge or metrics implementation is in scope.

The real-data gate requires explicit external paths and a daily-primary
`dsf.parquet`. A monthly smoke using `msf.parquet` is diagnostic only. CI uses
synthetic schema-compatible fixtures and reports no licensed admission.

Acceptance requires control and boundary tests, the Day 1 regression gate,
whitespace validation, and a clean `vendor/servicefabric` submodule.
