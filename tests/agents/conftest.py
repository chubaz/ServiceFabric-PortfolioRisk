"""Expose the Day 0 capability and agent packages to focused tests."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
for package in ("risk_domain", "risk_data", "risk_planning", "risk_capabilities", "risk_agents"):
    sys.path.insert(0, str(ROOT / "packages" / package / "src"))
