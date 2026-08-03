# Thesis real-data admission contract v0.1

This `THESIS-D2-DATA` gate admits licensed Parquet metadata and schema
compatibility only. It does not implement a bridge, normalization, metrics, or
decision kernel.

Permitted source identities are `dsf`, `msf`, `ccm_lookup`, `funda`, `fundq`,
`dsedelist`, and `stocknames`. Files, inventory, digests, catalogue, and
generated outputs remain in an external private `THESIS_DATA_ROOT`. Only a
reviewed `source-schemas.json` may be shared; `source-inventory.private.json`
and raw directories are never shared with Codex.

Real-data commands require explicit absolute external paths and must not print
rows, PERMNOs, GVKEYs, complete private paths, or inventory contents.
Daily-primary requires `dsf.parquet`; monthly-smoke may use `msf.parquet` but
cannot complete Day 2. CI uses only tiny schema-compatible synthetic fixtures
and never claims licensed-data admission.

No network connector, arbitrary SQL, external LLM, ticker-based CRSP/Compustat
join, broker, order, trade, rebalance, scheduler, or portfolio mutation is
permitted. Missing availability remains missing and is never guessed.
