#!/usr/bin/env python3
"""Validate a git change set against one Thesis Sprint lane."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import unicodedata
from pathlib import PurePosixPath
from typing import Any


def safe_path(path: object) -> bool:
    """Accept only canonical, repository-relative POSIX paths."""
    if not isinstance(path, str) or not path or "\\" in path:
        return False
    if any(unicodedata.category(character).startswith("C") for character in path):
        return False
    candidate = PurePosixPath(path)
    if candidate.is_absolute() or candidate.as_posix() != path:
        return False
    return all(part not in {"", ".", ".."} for part in path.split("/"))


def is_allowed(
    path: str,
    allowed_files: set[str],
    allowed_directories: tuple[str, ...],
) -> bool:
    """Treat file allowances as exact and directory allowances as descendants."""
    if not safe_path(path):
        return False
    return path in allowed_files or any(
        path.startswith(f"{directory}/") for directory in allowed_directories
    )


def changed_paths(base: str, head: str) -> list[tuple[str, tuple[str, ...]]]:
    """Read every changed path, including type changes and both rename/copy sides."""
    output = subprocess.run(
        [
            "git",
            "diff",
            "--name-status",
            "-z",
            "--find-renames",
            "--find-copies",
            "--find-copies-harder",
            base,
            head,
        ],
        check=True,
        capture_output=True,
    ).stdout
    fields = output.decode("utf-8", errors="surrogateescape").split("\0")
    if fields and fields[-1] == "":
        fields.pop()

    changes: list[tuple[str, tuple[str, ...]]] = []
    index = 0
    while index < len(fields):
        status = fields[index]
        index += 1
        path_count = 2 if status[:1] in {"R", "C"} else 1
        paths = tuple(fields[index : index + path_count])
        if not status or len(paths) != path_count:
            raise ValueError("malformed git change record")
        changes.append((status, paths))
        index += path_count
    return changes


def validate_changes(
    changes: list[tuple[str, tuple[str, ...]]],
    lane: dict[str, Any],
) -> list[str]:
    allowed_files = set(lane.get("allowed_files", []))
    allowed_directories = tuple(lane.get("allowed_directories", []))
    errors: list[str] = []
    for status, paths in changes:
        for path in paths:
            if not is_allowed(path, allowed_files, allowed_directories):
                errors.append(f"{status}: forbidden path {path!r}")
    return errors


def validate_manifest(manifest: object) -> list[str]:
    """Reject malformed, ambiguous, or unsafe lane ownership records."""
    if not isinstance(manifest, dict) or not isinstance(manifest.get("lanes"), dict):
        return ["manifest must contain a lanes object"]

    errors: list[str] = []
    seen: dict[str, str] = {}
    for lane_name, lane in manifest["lanes"].items():
        if not isinstance(lane_name, str) or not lane_name:
            errors.append("lane names must be non-empty strings")
            continue
        if not isinstance(lane, dict):
            errors.append(f"{lane_name}: lane record must be an object")
            continue
        if "allowed_paths" in lane:
            errors.append(f"{lane_name}: ambiguous path allowance key is forbidden")
        allowed_directories = lane.get("allowed_directories")
        allowed_files = lane.get("allowed_files")
        if not isinstance(allowed_directories, list) or not isinstance(
            allowed_files, list
        ):
            errors.append(
                f"{lane_name}: explicit allowed_directories and allowed_files are required"
            )
            continue
        for path in (*allowed_directories, *allowed_files):
            if not safe_path(path):
                errors.append(f"{lane_name}: invalid allowance {path!r}")
                continue
            previous = seen.setdefault(path, lane_name)
            if previous != lane_name:
                errors.append(
                    f"{lane_name}: allowance {path!r} duplicates lane {previous!r}"
                )
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--lane", required=True)
    parser.add_argument("--base", required=True)
    parser.add_argument("--head", required=True)
    parser.add_argument("--manifest", required=True)
    args = parser.parse_args()

    try:
        with open(args.manifest, encoding="utf-8") as manifest_file:
            manifest = json.load(manifest_file)
        manifest_errors = validate_manifest(manifest)
        if manifest_errors:
            print("Thesis Sprint lane manifest: FAIL", file=sys.stderr)
            print(
                "\n".join(f"- {error}" for error in manifest_errors),
                file=sys.stderr,
            )
            return 1
        lane = manifest["lanes"][args.lane]
        errors = validate_changes(changed_paths(args.base, args.head), lane)
    except (
        OSError,
        KeyError,
        TypeError,
        ValueError,
        json.JSONDecodeError,
        subprocess.CalledProcessError,
    ) as error:
        print(f"Thesis Sprint lane path check: invalid input: {error}", file=sys.stderr)
        return 2

    if errors:
        print("Thesis Sprint lane path check: FAIL", file=sys.stderr)
        print("\n".join(f"- {error}" for error in errors), file=sys.stderr)
        return 1
    print(f"Thesis Sprint lane path check ({args.lane}): PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
