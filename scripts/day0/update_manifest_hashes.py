#!/usr/bin/env python3
"""Synchronize declared application source hashes without changing manifest data."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def application_files(application_dir: Path, manifest_path: Path) -> set[Path]:
    excluded_names = {"__pycache__", ".pytest_cache"}
    return {
        path.relative_to(application_dir)
        for path in application_dir.rglob("*")
        if path.is_file()
        and path != manifest_path
        and not any(part in excluded_names or part.startswith(".") for part in path.parts)
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path, help="Path to servicefabric-package.json")
    parser.add_argument("--check", action="store_true", help="Fail instead of writing stale hashes")
    args = parser.parse_args()

    manifest_path = args.manifest.resolve()
    application_dir = manifest_path.parent
    with manifest_path.open(encoding="utf-8") as manifest_file:
        manifest = json.load(manifest_file)

    entries = manifest.get("source_files")
    if not isinstance(entries, list) or not entries:
        raise SystemExit("Manifest must declare a non-empty source_files list.")

    declared: set[Path] = set()
    changed = False
    for entry in entries:
        if not isinstance(entry, dict) or set(entry) != {"path", "sha256"}:
            raise SystemExit("Each source_files entry must contain only path and sha256.")
        relative_path = Path(entry["path"])
        if relative_path.is_absolute() or ".." in relative_path.parts:
            raise SystemExit(f"Invalid declared source path: {entry['path']}")
        if relative_path in declared:
            raise SystemExit(f"Duplicate declared source path: {entry['path']}")
        declared.add(relative_path)
        source_path = application_dir / relative_path
        if not source_path.is_file():
            raise SystemExit(f"Declared source file is missing: {entry['path']}")
        actual_hash = sha256(source_path)
        if entry["sha256"] != actual_hash:
            entry["sha256"] = actual_hash
            changed = True

    undeclared = sorted(application_files(application_dir, manifest_path) - declared)
    if undeclared:
        raise SystemExit(
            "Undeclared application source file(s): "
            + ", ".join(path.as_posix() for path in undeclared)
        )

    rendered = json.dumps(manifest, indent=2) + "\n"
    if args.check:
        if changed:
            print("Manifest source hashes are stale.", file=sys.stderr)
            return 1
        return 0
    manifest_path.write_text(rendered, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
