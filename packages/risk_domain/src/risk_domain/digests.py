"""Canonical, deterministic JSON and SHA-256 digest helpers."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, date, datetime
from decimal import Decimal
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel


def canonicalize(value: Any) -> Any:
    """Convert supported contract values to stable JSON-compatible values."""
    if isinstance(value, BaseModel):
        return canonicalize(value.model_dump(mode="python", exclude={"digest"}))
    if isinstance(value, dict):
        return {str(key): canonicalize(item) for key, item in value.items() if key != "digest"}
    if isinstance(value, (tuple, list)):
        return [canonicalize(item) for item in value]
    if isinstance(value, Decimal):
        if not value.is_finite():
            raise ValueError("non-finite Decimal values cannot be digested")
        return format(value, "f")
    if isinstance(value, datetime):
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("naive datetimes cannot be digested")
        utc_value = value.astimezone(UTC)
        return utc_value.isoformat(timespec="microseconds").replace("+00:00", "Z")
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Enum):
        return canonicalize(value.value)
    if isinstance(value, Path):
        return str(value)
    return value


def canonical_json(value: Any) -> str:
    """Render deterministic UTF-8 JSON without whitespace variation."""
    return json.dumps(canonicalize(value), ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_digest(value: Any) -> str:
    """Return the canonical ServiceFabric-style SHA-256 digest."""
    return "sha256:" + hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()
