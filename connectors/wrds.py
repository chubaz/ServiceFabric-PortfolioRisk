"""WRDS placeholders: network access is deliberately disabled for Day 0."""

from __future__ import annotations

from risk_data import ConnectorDisabledError, QuerySpec


class WrdsCrspConnector:
    connector_id = "wrds-crsp"

    def ingest(self, query: QuerySpec):  # type: ignore[no-untyped-def]
        raise ConnectorDisabledError("WRDS CRSP access is disabled during Day 0")


class WrdsCompustatConnector:
    connector_id = "wrds-compustat"

    def ingest(self, query: QuerySpec):  # type: ignore[no-untyped-def]
        raise ConnectorDisabledError("WRDS Compustat access is disabled during Day 0")
