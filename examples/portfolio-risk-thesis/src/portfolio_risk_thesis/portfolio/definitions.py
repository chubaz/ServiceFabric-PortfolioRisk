"""Reviewed fixed-quantity portfolio definitions."""

from __future__ import annotations

from pathlib import Path

from ..contracts import PortfolioDefinition
from ..manifests import load_portfolio


def load_portfolios(directory: Path | str) -> tuple[PortfolioDefinition, ...]:
    root = Path(directory)
    portfolios = tuple(load_portfolio(path) for path in sorted(root.glob("*.yaml")))
    if len(portfolios) != 3:
        raise ValueError("Thesis Day 1 requires exactly three portfolio definitions")
    ids = [item.portfolio_id for item in portfolios]
    if len(ids) != len(set(ids)):
        raise ValueError("portfolio IDs must be distinct")
    return tuple(sorted(portfolios, key=lambda item: item.portfolio_id))
