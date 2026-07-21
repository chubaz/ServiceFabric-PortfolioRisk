"""Expose the Day 0 capability package to focused tests."""

from __future__ import annotations

import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "packages" / "risk_capabilities" / "src"))
