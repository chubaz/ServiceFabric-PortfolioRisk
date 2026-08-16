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
        "classification": {
            "purpose": "Every retained run belongs to one immutable comparison cell. A run is never moved after execution; a new context creates a new cell and rerun obligation.",
            "required_dimensions": (
                "study", "experiment", "fixed_context", "case", "baseline_architecture",
                "portfolio_mandate", "information_regime", "scenario", "evaluation", "repetition",
            ),
            "browse_dimensions": (
                "architecture", "portfolio_mandate", "information_regime", "scenario", "market_regime", "evaluation",
            ),
            "vertical_baselines": tuple(
                {"id": item.arm_id, "name": item.name, "role": item.role, "deterministic": item.deterministic}
                for item in arm_plan.arms
            ),
            "market_regime_rule": "Market regimes classify a completed Case for analysis. They are not supplied to an architecture unless an information-regime treatment explicitly permits it.",
            "realised_usage_rule": "Capability calls and returned context are retained as run observations. They explain an assigned information regime; they do not recategorise the run after execution.",
        },
        "phases": (
            {"phase": "P9", "name": "Arm output admission", "status": "blocked", "delivered": "15 exact diversified cases and B0/B1/A1 output contracts", "next_decision": arm_plan.blockers[0].resolution},
            {"phase": "P10", "name": "Outcome-label review", "status": label_gate.status, "delivered": "Four-state label schema, case coverage and label firewall", "next_decision": "Independently construct and review one exact four-state label set."},
            {"phase": "P11", "name": "Experiment matrix", "status": matrix.execution_status, "delivered": f"{len(matrix.cells)} cells and {matrix.planned_observations} planned observations", "next_decision": "Clear P9 input and processing blockers before execution."},
        ),
        "boundary": {
            "synthetic": True,
            "data_truth": "reviewed_synthetic_calibration_context",
            "architecture_view": "point_in_time_ex_ante",
            "reference_labels": "sealed_and_not_admitted",
            "outputs_generated": False,
            "labels_opened": False,
            "metrics_calculated": False,
            "external_effects": "disabled",
        },
        "future_development": (
            "Register qualified architecture versions for B0, B1 and A1.",
            "Register additional information regimes and capability environments.",
            "Persist context-supersession receipts and rerun obligations.",
            "Admit labels and mature decision outcomes before calculating thesis estimates.",
            "Build versioned analysis snapshots for paired comparisons, counterfactuals and regressions.",
        ),
    }
