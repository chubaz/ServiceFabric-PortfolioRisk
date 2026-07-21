#!/usr/bin/env python3
"""Reject changes outside the exact Day 1 lane manifest allowances."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import PurePosixPath


def safe_path(path: str) -> bool:
    candidate = PurePosixPath(path)
    parts = path.split("/")
    return bool(path) and not candidate.is_absolute() and all(part not in {"", ".", ".."} for part in parts)


def is_allowed(path: str, allowed_files: set[str], allowed_directories: tuple[str, ...]) -> bool:
    if not safe_path(path):
        return False
    return path in allowed_files or any(path.startswith(f"{directory}/") for directory in allowed_directories)


def changed_paths(base: str, head: str) -> list[tuple[str, tuple[str, ...]]]:
    output = subprocess.run(["git", "diff", "--name-status", "-M", "-C", base, head], check=True, capture_output=True, text=True).stdout
    changes: list[tuple[str, tuple[str, ...]]] = []
    for line in output.splitlines():
        fields = line.split("\t")
        if not fields:
            continue
        status, paths = fields[0], tuple(fields[1:])
        expected = 2 if status[:1] in {"R", "C"} else 1
        if len(paths) != expected:
            raise ValueError(f"malformed git change record: {line!r}")
        changes.append((status, paths))
    return changes


def validate_changes(changes: list[tuple[str, tuple[str, ...]]], lane: dict[str, object]) -> list[str]:
    allowed_files = set(lane.get("allowed_files", []))
    allowed_directories = tuple(lane.get("allowed_directories", []))
    errors: list[str] = []
    for status, paths in changes:
        for path in paths:
            if not is_allowed(path, allowed_files, allowed_directories):
                errors.append(f"{status}: forbidden path {path!r}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--lane", required=True)
    parser.add_argument("--base", required=True)
    parser.add_argument("--head", required=True)
    parser.add_argument("--manifest", required=True)
    args = parser.parse_args()
    manifest = json.loads(open(args.manifest, encoding="utf-8").read())
    try:
        lane = manifest["lanes"][args.lane]
    except KeyError:
        print(f"unknown lane: {args.lane}", file=sys.stderr)
        return 2
    errors = validate_changes(changed_paths(args.base, args.head), lane)
    if errors:
        print("Day 1 lane path check: FAIL", file=sys.stderr)
        print("\n".join(f"- {error}" for error in errors), file=sys.stderr)
        return 1
    print(f"Day 1 lane path check ({args.lane}): PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
