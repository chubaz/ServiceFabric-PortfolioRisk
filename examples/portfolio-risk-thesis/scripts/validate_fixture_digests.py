#!/usr/bin/env python3
"""Validate committed Thesis Day 1 fixture SHA-256 digests and row counts."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import pyarrow.parquet as pq


def digest(path: Path) -> str:
    return f"sha256:{hashlib.sha256(path.read_bytes()).hexdigest()}"


def validate(fixtures: Path) -> None:
    manifest = json.loads((fixtures / "fixture-manifest.json").read_text(encoding="utf-8"))
    if manifest.get("synthetic") is not True:
        raise ValueError("fixture manifest must disclose synthetic=true")
    for name, declared in sorted(manifest["files"].items()):
        path = fixtures / name
        if digest(path) != declared["sha256"]:
            raise ValueError(f"digest mismatch for {name}")
        if pq.read_metadata(path).num_rows != declared["row_count"]:
            raise ValueError(f"row-count mismatch for {name}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixtures", type=Path, required=True, help="Reviewed fixture directory")
    args = parser.parse_args()
    try:
        validate(args.fixtures.resolve())
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as error:
        parser.exit(1, f"fixture validation failed: {error}\n")
    print("Thesis Day 1 fixture digests: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
