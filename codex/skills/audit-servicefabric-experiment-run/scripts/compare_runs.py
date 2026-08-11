#!/usr/bin/env python3
"""List or compare retained ServiceFabric experiment-run artifacts."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
PACKAGE_ROOT = REPOSITORY_ROOT / "packages" / "risk_artifacts" / "src"
if str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))

from risk_artifacts import (  # noqa: E402
    ArtifactKind,
    LocalArtifactRepository,
    VARIABLE_DIMENSIONS,
    compare_retained_runs,
)


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description=__doc__)
    value.add_argument(
        "command",
        choices=("list", "compare"),
        help="List eligible retained runs or compare an exact pair.",
    )
    value.add_argument(
        "--artifact-root",
        default=os.environ.get("PORTFOLIO_RISK_ARTIFACT_ROOT"),
        help="Governed Artifact Repository root; defaults to PORTFOLIO_RISK_ARTIFACT_ROOT.",
    )
    value.add_argument("--left", help="Baseline retained artifact ID.")
    value.add_argument("--right", help="Counterfactual retained artifact ID.")
    value.add_argument(
        "--variable",
        action="append",
        default=[],
        choices=VARIABLE_DIMENSIONS,
        help="Predeclared dimension intentionally changed; repeat as needed.",
    )
    value.add_argument("--output", help="Optional approved JSON report path.")
    return value


def _write(payload: object, output: str | None) -> None:
    content = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    if output:
        target = Path(output).expanduser().absolute()
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    else:
        print(content, end="")


def main() -> int:
    arguments = parser().parse_args()
    if not arguments.artifact_root:
        parser().error("--artifact-root or PORTFOLIO_RISK_ARTIFACT_ROOT is required")
    repository = LocalArtifactRepository(Path(arguments.artifact_root))
    if arguments.command == "list":
        records = [
            {
                "artifact_id": record.manifest.artifact_id,
                "run_id": record.manifest.run_id,
                "experiment_id": record.manifest.experiment_id,
                "data_truth": record.manifest.data_truth.value,
                "state": record.state.value,
                "file_count": len(record.manifest.files),
                "artifact_digest": record.manifest.artifact_digest,
            }
            for record in repository.list()
            if record.manifest.kind == ArtifactKind.RETAINED_RUN
        ]
        _write({"retained_runs": records, "count": len(records)}, arguments.output)
        return 0
    if not arguments.left or not arguments.right:
        parser().error("compare requires --left and --right retained artifact IDs")
    result = compare_retained_runs(
        repository,
        arguments.left,
        arguments.right,
        planned_variable_dimensions=tuple(arguments.variable),
    )
    _write(result.model_dump(mode="json"), arguments.output)
    return 0 if result.pair_comparable else 2


if __name__ == "__main__":
    raise SystemExit(main())
