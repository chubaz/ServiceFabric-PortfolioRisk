"""Expose the src-layout domain package to focused contract tests."""

from __future__ import annotations

import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "packages" / "risk_domain" / "src"))
