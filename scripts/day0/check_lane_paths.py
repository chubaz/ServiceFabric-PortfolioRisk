#!/usr/bin/env python3
"""Reject candidate changes outside the Day 0 lane manifest."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import PurePosixPath


def git_paths(base: str, candidate: str) -> list[str]:
    result = subprocess.run(
        ["git", "diff", "--name-only", "--diff-filter=ACMRD", f"{base}...{candidate}"],
        check=True,
        capture_output=True,
        text=True,
    )
    return [line for line in result.stdout.splitlines() if line]


def permits(path: str, allowed_paths: list[str]) -> bool:
    candidate = PurePosixPath(path)
    for allowed in allowed_paths:
        root = PurePosixPath(allowed.rstrip("/"))
        if candidate == root or root in candidate.parents:
            return True
    return False


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("lane", help="Lane key from config/agent/day0/lanes.json")
    parser.add_argument("--base", default="integration/day0")
    parser.add_argument("--candidate", default="HEAD")
    parser.add_argument("--manifest", default="config/agent/day0/lanes.json")
    args = parser.parse_args()

    with open(args.manifest, encoding="utf-8") as manifest_file:
        manifest = json.load(manifest_file)
    lane = manifest["lanes"].get(args.lane)
    if lane is None:
        parser.error(f"unknown lane: {args.lane}")

    changed = git_paths(args.base, args.candidate)
    violations = [path for path in changed if not permits(path, lane["allowed_paths"])]
    if violations:
        print(f"Lane {args.lane} may not modify:", file=sys.stderr)
        print("\n".join(f"- {path}" for path in violations), file=sys.stderr)
        return 1

    print(f"Lane path check passed for {args.lane}: {len(changed)} changed path(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
