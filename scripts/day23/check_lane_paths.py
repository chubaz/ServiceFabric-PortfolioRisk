#!/usr/bin/env python3
"""Validate a git change set against an explicit Day 2–3 lane manifest."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import PurePosixPath
from typing import Any


def safe_path(path: str) -> bool:
    """Accept repository-relative POSIX paths without traversal components."""
    if not path or "\\" in path:
        return False
    candidate = PurePosixPath(path)
    return not candidate.is_absolute() and all(part not in {"", ".", ".."} for part in path.split("/"))


def is_allowed(path: str, allowed_files: set[str], allowed_directories: tuple[str, ...]) -> bool:
    if not safe_path(path):
        return False
    return path in allowed_files or any(path.startswith(f"{directory}/") for directory in allowed_directories)


def changed_paths(base: str, head: str) -> list[tuple[str, tuple[str, ...]]]:
    output = subprocess.run(
        ["git", "diff", "--name-status", "-M", "-C", base, head],
        check=True, capture_output=True, text=True,
    ).stdout
    changes: list[tuple[str, tuple[str, ...]]] = []
    for line in output.splitlines():
        fields = line.split("\t")
        if not fields or not fields[0]:
            continue
        status, paths = fields[0], tuple(fields[1:])
        expected = 2 if status[:1] in {"R", "C"} else 1
        if len(paths) != expected:
            raise ValueError(f"malformed git change record: {line!r}")
        changes.append((status, paths))
    return changes


def validate_changes(changes: list[tuple[str, tuple[str, ...]]], lane: dict[str, Any]) -> list[str]:
    allowed_files = set(lane.get("allowed_files", []))
    allowed_directories = tuple(lane.get("allowed_directories", []))
    errors: list[str] = []
    for status, paths in changes:
        # This deliberately examines every path of renames and copies.
        for path in paths:
            if not is_allowed(path, allowed_files, allowed_directories):
                errors.append(f"{status}: forbidden path {path!r}")
    return errors


def validate_manifest_changes(
    changes: list[tuple[str, tuple[str, ...]]], lanes: dict[str, dict[str, Any]]
) -> list[str]:
    """Validate a cumulative integration diff against every owning lane."""
    allowances = {
        lane_name: (
            set(lane.get("allowed_files", [])),
            tuple(lane.get("allowed_directories", [])),
        )
        for lane_name, lane in lanes.items()
    }
    errors: list[str] = []
    for status, paths in changes:
        # A rename or copy is valid only when both source and destination are
        # owned, though each side may legitimately belong to a different lane.
        for path in paths:
            owners = [
                lane_name
                for lane_name, (allowed_files, allowed_directories) in allowances.items()
                if is_allowed(path, allowed_files, allowed_directories)
            ]
            if not owners:
                errors.append(f"{status}: path has no owning lane {path!r}")
    return errors


def validate_manifest(manifest: object) -> list[str]:
    """Reject ambiguous or overlapping lane ownership before checking a diff."""
    if not isinstance(manifest, dict) or not isinstance(manifest.get("lanes"), dict):
        return ["manifest must contain a lanes object"]
    if "allowed_paths" in json.dumps(manifest):
        return ["ambiguous allowed_paths key is present"]

    errors: list[str] = []
    owned: dict[str, str] = {}
    for lane_name, lane in manifest["lanes"].items():
        if not isinstance(lane, dict):
            errors.append(f"{lane_name}: lane record must be an object")
            continue
        allowed_directories = lane.get("allowed_directories")
        allowed_files = lane.get("allowed_files")
        if not isinstance(allowed_directories, list) or not isinstance(allowed_files, list):
            errors.append(
                f"{lane_name}: explicit allowed_directories and allowed_files are required"
            )
            continue
        for path in (*allowed_directories, *allowed_files):
            if not isinstance(path, str) or not safe_path(path):
                errors.append(f"{lane_name}: invalid allowance {path!r}")
                continue
            previous = owned.setdefault(path, lane_name)
            if previous != lane_name:
                errors.append(
                    f"{lane_name}: allowance {path!r} overlaps lane {previous!r}"
                )
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument("--lane")
    selection.add_argument("--all-lanes", action="store_true")
    parser.add_argument("--base", required=True)
    parser.add_argument("--head", required=True)
    parser.add_argument("--manifest", required=True, help="Path to the lane manifest JSON")
    args = parser.parse_args()
    try:
        manifest = json.loads(open(args.manifest, encoding="utf-8").read())
        manifest_errors = validate_manifest(manifest)
        if manifest_errors:
            print("Day 2–3 lane manifest: FAIL", file=sys.stderr)
            print("\n".join(f"- {error}" for error in manifest_errors), file=sys.stderr)
            return 1
        lanes = manifest["lanes"]
        changes = changed_paths(args.base, args.head)
        if args.all_lanes:
            errors = validate_manifest_changes(changes, lanes)
            scope = "all lanes"
        else:
            errors = validate_changes(changes, lanes[args.lane])
            scope = args.lane
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
        print(f"Day 2–3 lane path check: invalid input: {error}", file=sys.stderr)
        return 2
    if errors:
        print("Day 2–3 lane path check: FAIL", file=sys.stderr)
        print("\n".join(f"- {error}" for error in errors), file=sys.stderr)
        return 1
    print(f"Day 2–3 lane path check ({scope}): PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
