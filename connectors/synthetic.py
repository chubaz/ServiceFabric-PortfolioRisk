"""Deterministic, in-memory fictional fixtures for Day 0 connector testing."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from risk_domain import InstrumentIdentifier

from risk_data.contracts import DatasetSnapshot, FIXTURE_SEED, IngestionRun, NormalizedFundamentalRecord, NormalizedMarketRecord, QuerySpec
from risk_data.validation import validate_records


FIXTURE_TIME = datetime(2026, 7, 21, 12, 0, tzinfo=UTC)


class SyntheticCrspLikeConnector:
    connector_id = "synthetic-crsp-like"

    def ingest(self, query: QuerySpec) -> IngestionRun:
        if query.dataset != "market":
            raise ValueError("SyntheticCrspLikeConnector accepts market queries only")
        nova = NormalizedMarketRecord(instrument_id="instrument-nova", identifier=InstrumentIdentifier(identifier_type="ticker", value="NOVA"), observed_at=datetime(2026, 7, 20, tzinfo=UTC), price=Decimal("101.25"))
        missing = NormalizedMarketRecord(instrument_id="instrument-orbit", identifier=InstrumentIdentifier(identifier_type="ticker", value="ORBIT"), observed_at=datetime(2026, 7, 20, tzinfo=UTC), price=None)
        stale = NormalizedMarketRecord(instrument_id="instrument-quasar", identifier=InstrumentIdentifier(identifier_type="ticker", value="QUASAR"), observed_at=datetime(2026, 6, 1, tzinfo=UTC), price=Decimal("44.00"))
        # This fictional final move is intentionally reserved for later anomaly tests.
        final_move = NormalizedMarketRecord(instrument_id="instrument-nova", identifier=InstrumentIdentifier(identifier_type="ticker", value="NOVA"), observed_at=datetime(2026, 7, 21, tzinfo=UTC), price=Decimal("57.00"))
        records = (nova, missing, stale, final_move, nova) if query.include_duplicate_candidates else (nova, missing, stale, final_move)
        selected = tuple(record for record in records if record.instrument_id in query.instrument_ids and query.start_at <= record.observed_at <= query.end_at)
        snapshot = DatasetSnapshot(snapshot_id="synthetic-market-20260721", created_at=FIXTURE_TIME, records=selected)
        return IngestionRun(run_id="synthetic-market-run-20260721", connector_id=self.connector_id, query=query, started_at=FIXTURE_TIME, completed_at=FIXTURE_TIME, snapshot=snapshot, validation=validate_records(selected, requested_instrument_ids=query.instrument_ids, reference_at=FIXTURE_TIME))


class SyntheticCompustatLikeConnector:
    connector_id = "synthetic-compustat-like"

    def ingest(self, query: QuerySpec) -> IngestionRun:
        if query.dataset != "fundamental":
            raise ValueError("SyntheticCompustatLikeConnector accepts fundamental queries only")
        records = (
            NormalizedFundamentalRecord(instrument_id="instrument-nova", identifier=InstrumentIdentifier(identifier_type="gvkey", value="900001"), metric="revenue", observed_at=datetime(2026, 7, 1, tzinfo=UTC), value=Decimal("1250000")),
            NormalizedFundamentalRecord(instrument_id="instrument-orbit", identifier=InstrumentIdentifier(identifier_type="gvkey", value="900002"), metric="revenue", observed_at=datetime(2026, 7, 1, tzinfo=UTC), value=Decimal("830000")),
        )
        selected = tuple(record for record in records if record.instrument_id in query.instrument_ids and query.start_at <= record.observed_at <= query.end_at)
        snapshot = DatasetSnapshot(snapshot_id="synthetic-fundamental-20260721", created_at=FIXTURE_TIME, records=selected)
        return IngestionRun(run_id="synthetic-fundamental-run-20260721", connector_id=self.connector_id, query=query, started_at=FIXTURE_TIME, completed_at=FIXTURE_TIME, snapshot=snapshot, validation=validate_records(selected, requested_instrument_ids=query.instrument_ids, reference_at=FIXTURE_TIME))
