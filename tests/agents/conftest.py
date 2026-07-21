"""Expose the Day 0 capability and agent packages to focused tests."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "packages" / "risk_capabilities" / "src"))
sys.path.insert(0, str(ROOT / "packages" / "risk_agents" / "src"))
