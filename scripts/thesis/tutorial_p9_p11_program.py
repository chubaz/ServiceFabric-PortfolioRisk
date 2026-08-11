#!/usr/bin/env python3
"""Print the accepted-fixture arm, label-gate and matrix walkthrough."""

from __future__ import annotations

import json

from experimental_program_runtime import experimental_program_payload


def main() -> int:
    value = experimental_program_payload()
    print(json.dumps({
        "tutorial": "P9-P11 experimental programme",
        "cases": len(value["arm_plan"]["cases"]),
        "arms": [item["arm_id"] for item in value["arm_plan"]["arms"]],
        "arm_outputs_planned": value["arm_plan"]["expected_outputs"],
        "arm_execution": "ready" if value["arm_plan"]["executable"] else "blocked",
        "label_status": value["label_gate"]["status"],
        "labels_visible_to_processing": value["label_gate"]["labels_reachable_by_processing"],
        "matrix_cells": len(value["matrix"]["cells"]),
        "planned_observations": value["matrix"]["planned_observations"],
        "blockers": value["arm_plan"]["blockers"],
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
