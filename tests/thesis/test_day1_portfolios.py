from decimal import Decimal
from pathlib import Path

import yaml

from portfolio_risk_thesis.portfolio import load_portfolios


def test_three_valid_fixed_quantity_portfolios(example_root: Path) -> None:
    portfolios = load_portfolios(example_root / "portfolios")
    assert {item.portfolio_id for item in portfolios} == {
        "diversified",
        "technology_concentrated",
        "defensive_multi_asset",
    }
    assert all(5 <= len(item.positions) <= 8 for item in portfolios)
    assert all(position.quantity > 0 and isinstance(position.quantity, Decimal) for item in portfolios for position in item.positions)
    for path in (example_root / "portfolios").glob("*.yaml"):
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        assert "target_weights" not in raw
        assert "rebalance" not in raw


def test_portfolio_composition_constraints(example_root: Path) -> None:
    values = {item.portfolio_id: item for item in load_portfolios(example_root / "portfolios")}
    tech = {item.instrument_id: item.quantity for item in values["technology_concentrated"].positions}
    assert {"instrument-aurora-tech", "instrument-cobalt-tech"}.issubset(tech)
    starting = {
        "instrument-aurora-tech": Decimal("100"),
        "instrument-cobalt-tech": Decimal("82"),
        "instrument-marrow-health": Decimal("73"),
        "instrument-pantry-staples": Decimal("49"),
        "instrument-civic-bond": Decimal("101"),
    }
    technology_value = tech["instrument-aurora-tech"] * starting["instrument-aurora-tech"] + tech["instrument-cobalt-tech"] * starting["instrument-cobalt-tech"]
    total = sum((quantity * starting[instrument] for instrument, quantity in tech.items()), Decimal("0"))
    assert technology_value / total > Decimal("0.5")
    defensive = {item.instrument_id for item in values["defensive_multi_asset"].positions}
    assert {
        "instrument-civic-bond",
        "instrument-harbor-credit",
        "instrument-pantry-staples",
        "instrument-marrow-health",
        "instrument-sunstone-gold",
    }.issubset(defensive)
