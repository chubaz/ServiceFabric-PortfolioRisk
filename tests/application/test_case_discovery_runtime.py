from __future__ import annotations

import json
import sys
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[2]
LABS_ROOT = ROOT / "apps" / "portfolio-risk-workbench" / "labs"
sys.path.insert(0, str(LABS_ROOT))

import case_discovery_runtime  # noqa: E402
import duckdb_server  # noqa: E402
from risk_analytics import DetectorObservation, SignalScope  # noqa: E402


START = datetime(2014, 1, 2, tzinfo=UTC)


def observations() -> tuple[DetectorObservation, ...]:
    baseline = tuple(
        Decimal(index % 7 - 3) / Decimal("1000")
        for index in range(case_discovery_runtime.LOOKBACK_SESSIONS)
    )
    values = (*baseline, Decimal("-0.10"), Decimal("0.11"))
    return tuple(
        DetectorObservation(
            series_id="company-alpha",
            scope_type=SignalScope.INSTRUMENT,
            scope_id="company-alpha",
            observed_at=START + timedelta(days=index),
            available_at=START + timedelta(days=index),
            value=value,
            benchmark_value=Decimal("0"),
            evidence_ids=(f"crsp-row:{index}",),
            quality_flags=("licensed_read_only",),
        )
        for index, value in enumerate(values)
    )


def test_real_data_projection_is_compact_and_keeps_receipts_out_of_user_payload(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PORTFOLIO_RISK_DETECTOR_CACHE_ROOT", str(tmp_path / "cache"))
    monkeypatch.setattr(
        case_discovery_runtime,
        "_query_market",
        lambda *_args, **_kwargs: (
            observations(),
            START + timedelta(days=64),
            {101: {"company_name": "Alpha Industries", "ticker": "ALP"}},
            1,
            2,
        ),
    )
    monkeypatch.setattr(
        case_discovery_runtime,
        "_positions",
        lambda *_args, **_kwargs: ([SimpleNamespace(alias="company-alpha", permno=101)], Decimal("0"), {}),
    )

    result = case_discovery_runtime.signal_preview_payload(
        tmp_path,
        portfolio_id="diversified",
        start_date=date(2014, 3, 1),
        end_date=date(2014, 3, 10),
    )

    assert result["data"] == "Licensed CRSP · read only"
    assert result["summary"]["signals"] >= 1
    assert result["signals"][0]["company"] == "Alpha Industries"
    assert set(result["signals"][0]) == {
        "company", "ticker", "date", "direction", "score", "threshold", "detector", "source"
    }
    serialized = json.dumps(result)
    assert "sha256:" not in serialized
    assert "receipt" not in serialized
    assert "capability_id" not in serialized
    assert list((tmp_path / "cache" / "receipts").rglob("*.json"))


def test_signal_preview_rejects_invalid_period_without_running_data() -> None:
    with pytest.raises(case_discovery_runtime.HistoricalReplayError, match="inside 2013–2017"):
        case_discovery_runtime.signal_preview_payload(
            Path("/unused"),
            portfolio_id="diversified",
            start_date=date(2012, 12, 1),
            end_date=date(2013, 1, 2),
        )


def test_signal_api_delegates_to_the_existing_experiment_runtime(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    expected = {"status": "complete", "signals": []}
    monkeypatch.setattr(duckdb_server, "find_private_root", lambda _root: Path("/private"))
    monkeypatch.setattr(duckdb_server, "signal_preview_payload", lambda *_args, **_kwargs: expected)

    result = duckdb_server.experiment_signal_preview(
        portfolio_id="diversified",
        start_date=date(2014, 1, 1),
        end_date=date(2014, 1, 31),
    )

    assert result is expected
