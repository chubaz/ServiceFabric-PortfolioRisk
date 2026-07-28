from __future__ import annotations

import sys
from pathlib import Path

import pytest


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
EXAMPLE_ROOT = REPOSITORY_ROOT / "examples" / "portfolio-risk-thesis"
for source in (
    EXAMPLE_ROOT / "src",
    REPOSITORY_ROOT / "packages" / "risk_domain" / "src",
    REPOSITORY_ROOT / "packages" / "risk_data" / "src",
    REPOSITORY_ROOT / "packages" / "risk_capabilities" / "src",
    REPOSITORY_ROOT / "packages" / "risk_analytics" / "src",
    REPOSITORY_ROOT / "packages" / "risk_agents" / "src",
    REPOSITORY_ROOT / "packages" / "risk_planning" / "src",
):
    if str(source) not in sys.path:
        sys.path.insert(0, str(source))


@pytest.fixture
def example_root() -> Path:
    return EXAMPLE_ROOT


@pytest.fixture
def fixture_root() -> Path:
    return REPOSITORY_ROOT / "data" / "fixtures" / "synthetic" / "thesis-day1"
