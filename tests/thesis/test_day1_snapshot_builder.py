from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from portfolio_risk_thesis.adapters import HistoricalMarketDataAdapter
from portfolio_risk_thesis.manifests import load_dataset_manifest, load_portfolio
from portfolio_risk_thesis.portfolio import SnapshotBuilder
from risk_capabilities import CapabilityRegistry


class RecordingRegistry(CapabilityRegistry):
    def __init__(self) -> None:
        super().__init__()
        self.calls: list[str] = []

    def invoke(self, capability_id, request):  # type: ignore[no-untyped-def]
        self.calls.append(capability_id)
        return super().invoke(capability_id, request)


def inputs(example_root: Path):  # type: ignore[no-untyped-def]
    market_metadata, _ = load_dataset_manifest(example_root / "data" / "dataset_manifest.yaml")
    portfolio = load_portfolio(example_root / "portfolios" / "diversified.yaml")
    as_of = datetime(2024, 6, 26, 18, tzinfo=UTC)
    adapter = HistoricalMarketDataAdapter(market_metadata)
    prices = adapter.latest_observations_as_of(as_of, tuple(item.instrument_id for item in portfolio.positions))
    return market_metadata, portfolio, as_of, prices


def test_builder_invokes_canonical_registry_and_reconciles(example_root: Path) -> None:
    metadata, portfolio, as_of, prices = inputs(example_root)
    registry = RecordingRegistry()
    result = SnapshotBuilder(registry).build(portfolio, as_of, prices, metadata.revision)
    assert registry.calls == ["portfolio.snapshot.create", "portfolio.exposure.summarize"]
    nav = sum((item.market_value for item in result.portfolio_snapshot.positions), Decimal("0")) + sum(
        (item.amount for item in result.portfolio_snapshot.cash_balances), Decimal("0")
    )
    assert result.exposure_snapshot.nav == nav
    weights = sum((item.weight for item in result.exposure_snapshot.position_exposures), Decimal("0"))
    assert abs(weights + result.exposure_snapshot.cash_weight - Decimal("1")) <= Decimal("1e-28")
    assert result.limitations
    assert all(item.digest for item in result.evidence_references)
    assert all("fixture_revision=2026-07-28.2" in (item.description or "") for item in result.evidence_references)
    assert result.portfolio_snapshot.digest
    assert result.exposure_snapshot.digest
    with pytest.raises(ValidationError):
        result.portfolio_snapshot.snapshot_id = "changed"  # type: ignore[misc]


def test_missing_price_blocks_without_zero_inference(example_root: Path) -> None:
    metadata, portfolio, as_of, prices = inputs(example_root)
    missing = prices[0].model_copy(update={"close": None, "quality_state": "missing"})
    with pytest.raises(ValueError, match="missing price"):
        SnapshotBuilder().build(portfolio, as_of, (missing,) + prices[1:], metadata.revision)


def test_execution_is_effect_free_and_uses_no_network(example_root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import socket

    metadata, portfolio, as_of, prices = inputs(example_root)

    def blocked(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise AssertionError("network operation is prohibited")

    monkeypatch.setattr(socket, "create_connection", blocked)
    registry = RecordingRegistry()
    result = SnapshotBuilder(registry).build(portfolio, as_of, prices, metadata.revision)
    assert registry.invocation_history
    assert all(entry.status == "succeeded" for entry in registry.invocation_history)
    assert not any(term in " ".join(result.limitations).lower() for term in ("order submitted", "trade executed", "rebalanced"))
