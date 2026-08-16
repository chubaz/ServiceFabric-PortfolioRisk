from __future__ import annotations

from datetime import date

import duckdb
import pytest
from pydantic import ValidationError

from risk_data import LabelStudyMarketBatch, query_crsp_label_study_market


def connection() -> duckdb.DuckDBPyConnection:
    value = duckdb.connect(":memory:")
    value.execute("""
        CREATE TABLE crsp_daily (
          observed_at DATE, permno BIGINT, total_return DECIMAL(18,8),
          valuation_price DECIMAL(18,4), available_at TIMESTAMPTZ
        )
    """)
    value.execute("""
        INSERT INTO crsp_daily VALUES
          (DATE '2015-01-02', 101, 0.01000000, 10.0000, TIMESTAMPTZ '2015-01-03 00:00:00+00'),
          (DATE '2015-01-03', 101,-0.02000000,  9.8000, TIMESTAMPTZ '2015-01-04 00:00:00+00'),
          (DATE '2015-01-03', 202, NULL,       20.0000, TIMESTAMPTZ '2015-01-04 00:00:00+00'),
          (DATE '2015-02-01', 101, 0.90000000, 18.0000, TIMESTAMPTZ '2015-02-02 00:00:00+00')
    """)
    return value


def test_fixed_study_query_is_bounded_reconciled_and_deterministic() -> None:
    with connection() as value:
        first = query_crsp_label_study_market(value, dataset_snapshot_id="crsp-v1", permnos=(202, 101), start_date=date(2015, 1, 1), end_date=date(2015, 1, 5))
        second = query_crsp_label_study_market(value, dataset_snapshot_id="crsp-v1", permnos=(101, 202), start_date=date(2015, 1, 1), end_date=date(2015, 1, 5))
    assert first == second
    assert len(first.rows) == 2
    assert first.missing_return_count == 1
    assert all(item.observed_at.date() <= date(2015, 1, 5) for item in first.rows)


def test_study_batch_rejects_tampering_and_query_rejects_unbounded_scope() -> None:
    with connection() as value:
        batch = query_crsp_label_study_market(value, dataset_snapshot_id="crsp-v1", permnos=(101,), start_date=date(2015, 1, 1), end_date=date(2015, 1, 5))
        with pytest.raises(ValueError, match="positive PERMNO"):
            query_crsp_label_study_market(value, dataset_snapshot_id="crsp-v1", permnos=(), start_date=date(2015, 1, 1), end_date=date(2015, 1, 5))
    payload = batch.model_dump(mode="python")
    payload["batch_digest"] = "sha256:" + "0" * 64
    with pytest.raises(ValidationError, match="digest"):
        LabelStudyMarketBatch.model_validate(payload)
