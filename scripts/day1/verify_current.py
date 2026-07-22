#!/usr/bin/env python3
"""Run only the gates justified by the current Day 1 lifecycle state."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts.day1.check_preparation import status_errors


def run(*command: str) -> None:
    subprocess.run(command, cwd=ROOT, check=True)


def verification_target(status: dict[str, object]) -> str | None:
    errors = status_errors(status)
    if errors:
        raise ValueError("; ".join(errors))
    current = status.get("current")
    if current == "D1-WAVE-1A" and status.get("wave_1a") == "queued":
        return "verify-day1-prep"
    if current == "D1-WAVE-1A" and status.get("wave_1a") == "in_progress":
        return None
    if current == "D1-WAVE-1B":
        return "verify-wave-1a"
    if current == "D1-WAVE-1C":
        return "verify-wave-1b"
    if current in {"D1-QA", "D1-COMPLETE"}:
        return "verify-day1"
    raise ValueError("Day 1 lifecycle state is invalid")


def main() -> int:
    status = json.loads((ROOT / "config/agent/day1/status.json").read_text(encoding="utf-8"))
    try:
        target = verification_target(status)
    except ValueError as error:
        print(f"Day 1 lifecycle state is invalid; refusing to select a verification gate: {error}", file=sys.stderr)
        return 1
    checker = [sys.executable, "scripts/day1/check_preparation.py"]
    if target == "verify-day1-prep":
        checker.append("--require-prepared")
    run(*checker)
    if target is not None:
        run("make", target)
    if status["current"] in {"D1-WAVE-1A", "D1-WAVE-1B", "D1-WAVE-1C"} and status.get("wave_1a") != "queued":
        print(f"{status['current']} is in progress; its gate is not reported complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
