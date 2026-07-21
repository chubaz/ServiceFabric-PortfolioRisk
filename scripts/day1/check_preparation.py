#!/usr/bin/env python3
"""Validate Day 1 control-plane records and its immutable prepared baseline."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REQUIRED = [
    "AGENTS.md", "README.md", "Makefile", "requirements/day1.in", "requirements/day1.lock",
    "config/agent/day1/status.json", "config/agent/day1/lanes.json", "config/agent/day1/waves.json",
    "docs/workplans/current.md", "docs/workplans/day-1/preparation.md", "docs/workplans/day-1/wave-1a.md",
    "docs/workplans/day-1/wave-1b.md", "docs/workplans/day-1/wave-1c.md", "docs/workplans/day-1/soft-qa.md",
    "docs/workplans/day-1/knowledge-products.md", "docs/architecture/adr/0003-day1-workbench-experience.md",
    "docs/architecture/adr/0004-day1-operating-profiles-and-data-boundary.md", "docs/architecture/adr/0005-day1-risk-analytics-and-explainability.md",
    "docs/design/day1-information-architecture.md", "docs/design/day1-screen-contracts.md",
    "docs/contracts/day1-portfolio-input-v0.1.md", "docs/contracts/day1-risk-analysis-v0.1.md",
    "docs/rights/day1-provider-access-boundary.md", "docs/handoffs/day-1/preparation.md",
    *(f"codex/prompts/day1/{lane}.md" for lane in ("integration", "domain-analytics", "data", "experience", "knowledge", "agents")),
    "scripts/day1/show_context.py", "scripts/day1/check_lane_paths.py", "scripts/day1/verify_current.py",
    "tests/architecture/test_day1_preparation.py", "tests/architecture/test_day1_runtime_boundaries.py", ".github/workflows/day1-preparation.yml",
]
PREPARED_STATUS = {"current": "D1-WAVE-1A", "preparation": "complete", "wave_1a": "queued", "wave_1b": "queued", "wave_1c": "queued", "soft_qa": "queued", "base_tag": "day0-complete"}
WORKPLAN_STATUS = {
    "D1-WAVE-1B": "in progress",
    "D1-WAVE-1C": "in progress",
    "D1-QA": "ready for soft qa",
    "D1-COMPLETE": "complete",
}


def read_json(relative: str) -> object:
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


def status_errors(status: object, require_prepared: bool = False) -> list[str]:
    if not isinstance(status, dict):
        return ["Day 1 status is not an object"]
    if status.get("base_tag") != "day0-complete" or status.get("preparation") != "complete":
        return ["Day 1 status does not preserve the prepared base"]
    if require_prepared:
        return [] if status == PREPARED_STATUS else ["Day 1 status does not equal the immutable preparation state"]
    states = (
        {"current": "D1-WAVE-1A", "wave_1a": "queued", "wave_1b": "queued", "wave_1c": "queued", "soft_qa": "queued"},
        {"current": "D1-WAVE-1A", "wave_1a": "in_progress", "wave_1b": "queued", "wave_1c": "queued", "soft_qa": "queued"},
        {"current": "D1-WAVE-1B", "wave_1a": "complete", "wave_1b": "in_progress", "wave_1c": "queued", "soft_qa": "queued"},
        {"current": "D1-WAVE-1C", "wave_1a": "complete", "wave_1b": "complete", "wave_1c": "in_progress", "soft_qa": "queued"},
        {"current": "D1-QA", "wave_1a": "complete", "wave_1b": "complete", "wave_1c": "complete", "soft_qa": "queued"},
        {"current": "D1-COMPLETE", "wave_1a": "complete", "wave_1b": "complete", "wave_1c": "complete", "soft_qa": "passed"},
    )
    return [] if any(all(status.get(key) == value for key, value in state.items()) for state in states) else ["Day 1 status is not a valid lifecycle state"]


def workplan_errors(status: dict[str, object], text: str) -> list[str]:
    current = str(status["current"])
    expected_status = (
        "queued"
        if current == "D1-WAVE-1A" and status["wave_1a"] == "queued"
        else "in progress"
        if current == "D1-WAVE-1A"
        else WORKPLAN_STATUS[current]
    )
    fields = {
        name: quoted or plain
        for name, quoted, plain in re.findall(
            r"^- ([A-Za-z]+):\s*(?:`([^`]+)`|(.+))$", text, re.MULTILINE
        )
    }
    workplan_id = fields.get("ID")
    workplan_status = fields.get("Status")
    errors: list[str] = []
    if workplan_id != current:
        errors.append(f"current workplan ID must be {current}")
    if workplan_status is None or not workplan_status.lower().startswith(expected_status):
        errors.append(f"current workplan status must start with {expected_status!r}")
    return errors


def validate(require_prepared: bool = False) -> list[str]:
    errors: list[str] = []
    for relative in REQUIRED:
        if not (ROOT / relative).is_file():
            errors.append(f"missing required file: {relative}")
    if errors:
        return errors
    if read_json("config/agent/day0/status.json") != {"current": "D0-COMPLETE", "preparation": "complete", "wave_0a": "complete", "wave_0b": "complete", "wave_0c": "complete", "soft_qa": "passed"}:
        errors.append("Day 0 status is not the reviewed complete/pass record")
    status = read_json("config/agent/day1/status.json")
    errors.extend(status_errors(status, require_prepared))

    lanes = read_json("config/agent/day1/lanes.json")
    lane_values = lanes["lanes"]
    if "allowed_paths" in json.dumps(lanes):
        errors.append("ambiguous allowed_paths key is present")
    owned: list[str] = []
    for lane, record in lane_values.items():
        if not isinstance(record.get("allowed_directories"), list) or not isinstance(record.get("allowed_files"), list):
            errors.append(f"{lane} lacks explicit directory/file allowances")
        handoffs = [item for item in record.get("allowed_files", []) if item.startswith("docs/handoffs/day-1/")]
        expected_handoffs = 2 if lane == "integration" else 1
        if len(handoffs) != expected_handoffs or any(Path(item).name == "" for item in handoffs):
            errors.append(f"{lane} must own only its exact Day 1 handoff file(s)")
        owned.extend(record.get("allowed_directories", []))
        owned.extend(item for item in record.get("allowed_files", []) if not item.startswith("docs/handoffs/day-1/"))
    if len(owned) != len(set(owned)):
        errors.append("specialist lane ownership overlaps")

    waves = read_json("config/agent/day1/waves.json")
    if [wave["id"] for wave in waves["waves"]] != ["D1-WAVE-1A", "D1-WAVE-1B", "D1-WAVE-1C"]:
        errors.append("wave IDs are incomplete or out of order")
    if waves["integration_order"] != ["domain-analytics", "knowledge", "data", "agents", "experience", "integration"]:
        errors.append("integration order is incorrect")
    if waves["waves"][1]["depends_on"] != ["D1-WAVE-1A"] or set(waves["waves"][2]["depends_on"]) != {"D1-WAVE-1A", "D1-WAVE-1B"}:
        errors.append("wave dependency graph is incorrect")

    text = "\n".join((ROOT / relative).read_text(encoding="utf-8") for relative in REQUIRED if (ROOT / relative).suffix in {".md", ".yml", ".py"})
    for phrase in ["disabled by default", "arbitrary SQL", "notebook execution", "broker", "order", "rebalance", "human review"]:
        if phrase.lower() not in text.lower():
            errors.append(f"required boundary phrase absent: {phrase}")
    tracked = subprocess.run(["git", "ls-files", "--cached", "--others", "--exclude-standard"], cwd=ROOT, check=True, capture_output=True, text=True).stdout.splitlines()
    forbidden_path = re.compile(r"(^|/)(broker|brokers|orders?|order_execution|trading|rebalance)(/|$)", re.I)
    if [item for item in tracked if forbidden_path.search(item)]:
        errors.append("broker/order/trading/rebalance path is tracked")
    rights = (ROOT / "docs/rights/day1-provider-access-boundary.md").read_text(encoding="utf-8").lower()
    if "enabled: false" not in rights or "access_state: unavailable" not in rights:
        errors.append("provider defaults are not explicitly disabled/unavailable")
    current = (ROOT / "docs/workplans/current.md").read_text(encoding="utf-8")
    if isinstance(status, dict) and not status_errors(status, require_prepared):
        errors.extend(workplan_errors(status, current))
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--require-prepared", action="store_true", help="require the immutable queued preparation state")
    args = parser.parse_args()
    errors = validate(args.require_prepared)
    if errors:
        print("Day 1 preparation: FAIL", file=sys.stderr)
        print("\n".join(f"- {error}" for error in errors), file=sys.stderr)
        return 1
    print("Day 1 preparation: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
