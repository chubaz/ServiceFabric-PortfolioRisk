#!/usr/bin/env python3
"""Run the reviewed private Thesis Day 2 experiment without exposing private data."""

from __future__ import annotations

import json
import os
from pathlib import Path

from portfolio_risk_thesis.day2 import (
    Day2ExperimentError,
    run_day2_experiment,
    validate_day2_experiment,
)


REQUIRED_ENVIRONMENT = (
    "THESIS_REAL_SOURCE_MANIFEST",
    "THESIS_REAL_EXPERIMENT_MANIFEST",
    "THESIS_REAL_OUTPUT_ROOT",
    "THESIS_DAY2_OUTPUT_ROOT",
)


def _required_paths() -> dict[str, Path]:
    missing = [name for name in REQUIRED_ENVIRONMENT if not os.environ.get(name)]
    if missing:
        raise ValueError(
            "required private Day 2 environment is incomplete: "
            + ", ".join(missing)
        )
    paths = {
        name: Path(os.environ[name]).expanduser()
        for name in REQUIRED_ENVIRONMENT
    }
    if any(not path.is_absolute() for path in paths.values()):
        raise ValueError("all private Day 2 paths must be absolute")
    for name in (
        "THESIS_REAL_SOURCE_MANIFEST",
        "THESIS_REAL_EXPERIMENT_MANIFEST",
    ):
        if not paths[name].is_file():
            raise ValueError(f"{name} must identify an existing file")
    if not paths["THESIS_REAL_OUTPUT_ROOT"].is_dir():
        raise ValueError("THESIS_REAL_OUTPUT_ROOT must identify an existing directory")
    return {name: path.resolve(strict=False) for name, path in paths.items()}


def run_private_day2_demo() -> dict[str, object]:
    """Validate and run one already reviewed experiment, returning public-safe facts."""

    paths = _required_paths()
    common_root = Path(
        os.path.commonpath(
            (
                paths["THESIS_REAL_SOURCE_MANIFEST"].parent,
                paths["THESIS_REAL_EXPERIMENT_MANIFEST"].parent,
                paths["THESIS_REAL_OUTPUT_ROOT"],
                paths["THESIS_DAY2_OUTPUT_ROOT"],
            )
        )
    )
    configured_root = os.environ.get("THESIS_DATA_ROOT")
    if configured_root:
        configured = Path(configured_root)
        if not configured.is_absolute():
            raise ValueError("THESIS_DATA_ROOT must be absolute")
    else:
        os.environ["THESIS_DATA_ROOT"] = str(common_root)

    manifest, receipt, _ = validate_day2_experiment(
        paths["THESIS_REAL_EXPERIMENT_MANIFEST"]
    )
    if manifest.source_manifest.path.resolve() != paths[
        "THESIS_REAL_SOURCE_MANIFEST"
    ]:
        raise ValueError("experiment source manifest does not match the reviewed input")
    if manifest.data_root.resolve() != paths["THESIS_REAL_OUTPUT_ROOT"]:
        raise ValueError("experiment data root does not match the reviewed input")

    output = run_day2_experiment(
        experiment_manifest_path=paths["THESIS_REAL_EXPERIMENT_MANIFEST"],
        output_root=paths["THESIS_DAY2_OUTPUT_ROOT"],
    )
    return {
        "status": "PASS",
        "experiment_id": manifest.experiment_id,
        "run_id": output.name,
        "dataset_mode": manifest.dataset_mode,
        "portfolio_count": receipt.portfolio_count,
        "effects": 0,
    }


def main() -> int:
    try:
        result = run_private_day2_demo()
    except (Day2ExperimentError, OSError, ValueError):
        print(
            "Thesis Day 2 private demo: FAIL "
            "(inspect the private local evidence; no paths emitted)"
        )
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
