"""Application projection for P9-P11 experimental-program readiness."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from risk_experiments import compile_arm_plan, compile_label_gate, compile_matrix

from fixture_context_runtime import fixture_store


FIXTURE_DIGEST = "sha256:2b2c347ecafa775853aad88f49b7565263726c17c61850d22e1b789d984761d9"
WINDOWS_PATH = Path(__file__).resolve().parents[3] / "data/fixtures/synthetic/thesis-day4/windows.json"


def _review_dates() -> tuple[datetime, ...]:
    value = json.loads(WINDOWS_PATH.read_text(encoding="utf-8"))
    dates = value["portfolios"]["diversified"]["eligible_review_dates"]
    return tuple(datetime.fromisoformat(item.replace("Z", "+00:00")) for item in dates)


def experimental_program_payload() -> dict[str, Any]:
    context = fixture_store().get(FIXTURE_DIGEST)
    arm_plan = compile_arm_plan(context, _review_dates())
    label_gate = compile_label_gate(context, arm_plan)
    matrix = compile_matrix(context, arm_plan, repeats=2)
    return {
        "arm_plan": arm_plan.model_dump(mode="json"),
        "label_gate": label_gate.model_dump(mode="json"),
        "matrix": matrix.model_dump(mode="json"),
        "phases": (
            {"phase": "P9", "name": "Arm output admission", "status": "blocked", "delivered": "15 exact diversified cases and B0/A1 output contracts", "next_decision": arm_plan.blockers[0].resolution},
            {"phase": "P10", "name": "Outcome-label review", "status": label_gate.status, "delivered": "Four-state label schema, case coverage and label firewall", "next_decision": "Independently construct and review one exact four-state label set."},
            {"phase": "P11", "name": "Experiment matrix", "status": matrix.execution_status, "delivered": f"{len(matrix.cells)} cells and {matrix.planned_observations} planned observations", "next_decision": "Clear P9 input and processing blockers before execution."},
        ),
        "boundary": {
            "synthetic": True,
            "outputs_generated": False,
            "labels_opened": False,
            "metrics_calculated": False,
            "external_effects": "disabled",
        },
    }
