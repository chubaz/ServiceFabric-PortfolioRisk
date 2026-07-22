"""Cross-module data-contract coverage for the bounded Day 1B workspace."""

from __future__ import annotations

import importlib.util
import inspect
import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi import FastAPI
from risk_data import (
    PortfolioConfirmationError,
    PortfolioConfirmationRequest,
    PortfolioInputFormat,
    PortfolioInputService,
    provider_catalogue,
    reviewed_query_manifests,
)
from risk_domain import MarketObservation, PortfolioSnapshot, QualityFlag


ROOT = Path(__file__).resolve().parents[2]
APPLICATION_DIR = ROOT / "apps" / "portfolio-risk-workbench"
AS_OF = datetime(2026, 7, 20, 16, 0, tzinfo=UTC)
EXTERNAL_PROVIDERS = {"wrds", "crsp", "compustat", "ravenpack", "accern", "bloomberg"}
PROHIBITED_ROUTE_TERMS = ("broker", "order", "trade", "rebalance")


def csv_input(quantity: str) -> bytes:
    return f"instrument_id,quantity,currency,as_of\ninstrument-nova,{quantity},USD,{AS_OF.isoformat()}\n".encode()


def observation() -> MarketObservation:
    return MarketObservation(
        instrument_id="instrument-nova",
        observed_at=AS_OF,
        price=Decimal("125.50"),
        currency="USD",
        quality_flags=(QualityFlag.COMPLETE,),
        synthetic=True,
    )


def load_snapshot(data_root: Path, snapshot_id: str) -> PortfolioSnapshot:
    payload = json.loads((data_root / "portfolio-snapshots" / f"{snapshot_id}.json").read_text())
    return PortfolioSnapshot.model_validate(payload)


def application() -> FastAPI:
    spec = importlib.util.spec_from_file_location("day1_wave1b_workbench", APPLICATION_DIR / "app.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.app


def test_day1_portfolio_workspace_journey(tmp_path: Path) -> None:
    """Data contracts preview locally; only explicit confirmation persists revisions."""
    data_root = tmp_path / "private-local-state"
    service = PortfolioInputService(data_root)

    research_preview = service.preview(
        csv_input("2"), PortfolioInputFormat.CSV, profile="research", base_currency="USD", as_of=AS_OF
    )
    personal_preview = service.preview(
        csv_input("2"), PortfolioInputFormat.CSV, profile="personal_portfolio", base_currency="USD", as_of=AS_OF
    )
    invalid_preview = service.preview(
        b"instrument_id,quantity\ninstrument-nova,not-a-decimal\n",
        PortfolioInputFormat.CSV,
        profile="personal_portfolio",
        base_currency="USD",
        as_of=AS_OF,
    )

    assert research_preview.valid and research_preview.document is not None
    assert personal_preview.valid and personal_preview.document is not None
    assert research_preview.document.profile == "research"
    assert personal_preview.document.profile == "personal_portfolio"
    assert not invalid_preview.valid
    assert "invalid_input" in invalid_preview.quality_flags
    with pytest.raises(PortfolioConfirmationError, match="invalid preview"):
        service.confirm(
            invalid_preview,
            PortfolioConfirmationRequest(confirm=True, preview_digest=invalid_preview.preview_digest),
            {"instrument-nova": observation()},
        )

    with pytest.raises(PortfolioConfirmationError, match="confirm=true"):
        service.confirm(
            personal_preview,
            PortfolioConfirmationRequest(confirm=False, preview_digest=personal_preview.preview_digest),
            {"instrument-nova": observation()},
        )

    first = service.confirm(
        personal_preview,
        PortfolioConfirmationRequest(confirm=True, preview_digest=personal_preview.preview_digest),
        {"instrument-nova": observation()},
    )
    repeated = service.confirm(
        personal_preview,
        PortfolioConfirmationRequest(confirm=True, preview_digest=personal_preview.preview_digest),
        {"instrument-nova": observation()},
    )
    corrected_preview = service.preview(
        csv_input("3"), PortfolioInputFormat.CSV, profile="personal_portfolio", base_currency="USD", as_of=AS_OF
    )
    corrected = service.confirm(
        corrected_preview,
        PortfolioConfirmationRequest(confirm=True, preview_digest=corrected_preview.preview_digest),
        {"instrument-nova": observation()},
    )

    assert first.created is True
    assert repeated.created is False
    assert repeated.snapshot_id == first.snapshot_id
    assert corrected.snapshot_id != first.snapshot_id
    assert len(list((data_root / "portfolio-snapshots").glob("*.json"))) == 2

    comparison = service.compare(
        load_snapshot(data_root, first.snapshot_id), load_snapshot(data_root, corrected.snapshot_id)
    )
    assert comparison.left_snapshot_id == first.snapshot_id
    assert comparison.right_snapshot_id == corrected.snapshot_id
    assert comparison.position_changes[0].change_type == "changed"
    assert comparison.position_changes[0].left_quantity == Decimal("2")
    assert comparison.position_changes[0].right_quantity == Decimal("3")
    assert "read-only" in comparison.limitations[0].lower()


def test_day1_portfolio_workspace_has_only_fixed_local_data_surfaces(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Catalogue and route inventory exclude provider enablement, SQL, and financial effects."""
    external = [item for item in provider_catalogue() if item.provider_id in EXTERNAL_PROVIDERS]
    manifests = reviewed_query_manifests()

    assert {item.provider_id for item in external} == EXTERNAL_PROVIDERS
    assert all(not item.enabled and item.access_state == "unavailable" for item in external)
    assert {item.view_name for item in manifests} == {
        "market_prices", "fundamentals", "latest_market_prices", "latest_fundamentals"
    }
    assert not hasattr(PortfolioInputService, "execute_sql")
    assert "sql" not in inspect.getsource(PortfolioInputService).lower()

    monkeypatch.setenv("PORTFOLIO_RISK_DATA_ROOT", str(tmp_path / "risk-data"))
    paths = {route.path.lower() for route in application().routes}
    assert not any("provider" in path and ("enable" in path or "connect" in path) for path in paths)
    assert not any(term in path for path in paths for term in PROHIBITED_ROUTE_TERMS)
