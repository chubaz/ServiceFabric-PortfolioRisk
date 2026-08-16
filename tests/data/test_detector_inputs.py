from __future__ import annotations

from datetime import UTC, date, datetime

import duckdb
import pytest
from pydantic import ValidationError

from risk_data import DetectorMarketBatch, query_crsp_detector_market


def connection() -> duckdb.DuckDBPyConnection:
    value = duckdb.connect(":memory:")
    value.execute(
        """
        CREATE TABLE crsp_daily (
          observed_at DATE,
          permno BIGINT,
          total_return DECIMAL(18, 8),
          available_at TIMESTAMPTZ
        )
        """
    )
    value.execute(
        """
        INSERT INTO crsp_daily VALUES
          (DATE '2014-01-02', 101, 0.01000000, TIMESTAMPTZ '2014-01-03 00:00:00+00'),
          (DATE '2014-01-02', 202, NULL,       TIMESTAMPTZ '2014-01-03 00:00:00+00'),
          (DATE '2014-01-03', 101, -0.02000000,TIMESTAMPTZ '2014-01-04 00:00:00+00'),
          (DATE '2014-01-06', 101, 0.90000000, TIMESTAMPTZ '2014-01-07 00:00:00+00'),
          (DATE '2014-01-03', 999, 0.80000000, TIMESTAMPTZ '2014-01-04 00:00:00+00')
        """
    )
    return value


def test_fixed_crsp_query_is_point_in_time_bounded_reconciled_and_deterministic() -> None:
    with connection() as value:
        first = query_crsp_detector_market(
            value,
            dataset_snapshot_id="licensed-crsp-a",
            permnos=(202, 101),
            start_date=date(2014, 1, 1),
            end_date=date(2014, 1, 3),
        )
        second = query_crsp_detector_market(
            value,
            dataset_snapshot_id="licensed-crsp-a",
            permnos=(101, 202),
            start_date=date(2014, 1, 1),
            end_date=date(2014, 1, 3),
        )

    assert first == second
    assert first.requested_permnos == (101, 202)
    assert first.source_row_count == 3
    assert first.missing_return_count == 1
    assert [(item.permno, str(item.total_return)) for item in first.rows] == [
        (101, "0.01000000"),
        (101, "-0.02000000"),
    ]
    assert all(item.available_at <= first.as_of for item in first.rows)
    assert all(item.observed_at.date() <= date(2014, 1, 3) for item in first.rows)
    assert first.batch_digest.startswith("sha256:")


def test_detector_market_batch_rejects_future_rows_and_digest_tampering() -> None:
    with connection() as value:
        batch = query_crsp_detector_market(
            value,
            dataset_snapshot_id="licensed-crsp-a",
            permnos=(101,),
            start_date=date(2014, 1, 1),
            end_date=date(2014, 1, 3),
        )
    payload = batch.model_dump(mode="python")
    payload["as_of"] = datetime(2014, 1, 2, tzinfo=UTC)
    with pytest.raises(ValidationError, match="future information"):
        DetectorMarketBatch.model_validate(payload)
    payload = batch.model_dump(mode="python")
    payload["batch_digest"] = "sha256:" + "0" * 64
    with pytest.raises(ValidationError, match="canonical detector input digest"):
        DetectorMarketBatch.model_validate(payload)


def test_fixed_query_rejects_empty_or_invalid_scope() -> None:
    with connection() as value:
        with pytest.raises(ValueError, match="positive PERMNO"):
            query_crsp_detector_market(
                value,
                dataset_snapshot_id="licensed-crsp-a",
                permnos=(),
                start_date=date(2014, 1, 1),
                end_date=date(2014, 1, 3),
            )
