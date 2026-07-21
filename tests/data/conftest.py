"""Expose Day 0 src-layout packages to the focused data tests."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "packages" / "risk_domain" / "src"))
sys.path.insert(0, str(ROOT / "packages" / "risk_data" / "src"))
