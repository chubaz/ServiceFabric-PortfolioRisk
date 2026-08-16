#!/usr/bin/env python3
"""Drive the frozen Professor Demo workflow through its local HTTP contract.

The command intentionally does not discover or rewrite the Case.  The backend
owns preflight, execution, retention and digest verification; this script makes
that workflow repeatable from a terminal as well as from the Demo page.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def request_json(
    base_url: str,
    path: str,
    *,
    method: str = "GET",
    payload: dict[str, Any] | None = None,
    timeout: int = 300,
) -> dict[str, Any]:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = Request(
        f"{base_url.rstrip('/')}{path}",
        data=data,
        headers={"Content-Type": "application/json"},
        method=method,
    )
    try:
        with urlopen(request, timeout=timeout) as response:  # noqa: S310 - local URL is explicit
            return json.load(response)
    except HTTPError as error:
        body = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Professor Demo API returned HTTP {error.code}: {body}") from error
    except URLError as error:
        raise RuntimeError(
            f"Professor Demo service is unavailable at {base_url}. Start the Risk Lab first."
        ) from error


def preflight(base_url: str) -> dict[str, Any]:
    result = request_json(base_url, "/api/professor-demo")
    failed = [
        item["label"]
        for item in result.get("checks", [])
        if item.get("required") and item.get("status") != "pass"
    ]
    if not result.get("demo_ready") or failed:
        raise RuntimeError("Professor Demo preflight failed: " + "; ".join(failed))
    return result


def run(base_url: str, *, authorize_model_calls: bool) -> dict[str, Any]:
    if not authorize_model_calls:
        raise RuntimeError(
            "Run requires --authorize-model-calls for one B1 and four A1 OpenAI calls."
        )
    return request_json(
        base_url,
        "/api/professor-demo/run",
        method="POST",
        payload={"authorize_external_model_calls": True},
    )


def verify_artifact(base_url: str, artifact_id: str) -> dict[str, Any]:
    return request_json(
        base_url,
        f"/api/artifacts/{artifact_id}/verify",
        method="POST",
        payload={},
    )


def summary(preflight_result: dict[str, Any], run_result: dict[str, Any] | None) -> dict[str, Any]:
    result: dict[str, Any] = {
        "demo_ready": preflight_result.get("demo_ready"),
        "thesis_ready": preflight_result.get("thesis_ready"),
        "manifest_digest": preflight_result.get("manifest", {}).get("manifest_digest"),
        "required_checks_passed": sum(
            1
            for item in preflight_result.get("checks", [])
            if item.get("required") and item.get("status") == "pass"
        ),
        "limitations": [
            item.get("limitation") or item.get("observed")
            for item in preflight_result.get("checks", [])
            if item.get("status") == "warning"
        ],
    }
    if run_result is None:
        return result
    analysis = run_result.get("analysis", {})
    artifacts = run_result.get("run_artifacts", [])
    result.update({
        "experiment_status": analysis.get("status"),
        "analysis_digest": analysis.get("analysis_digest"),
        "completed_runs": analysis.get("matrix_coverage", {}).get("completed"),
        "planned_runs": analysis.get("matrix_coverage", {}).get("planned"),
        "critical_defects": analysis.get("assurance", {}).get("critical_count"),
        "analysis_artifact_id": run_result.get("analysis_artifact", {}).get("artifact_id"),
        "runs": [
            {
                "workflow_id": item.get("workflow_id"),
                "run_id": item.get("run_id"),
                "artifact_id": item.get("artifact_id"),
            }
            for item in artifacts
        ],
    })
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Preflight and run Professor Demo v0.1")
    parser.add_argument(
        "stage",
        choices=("preflight", "run", "all"),
        nargs="?",
        default="preflight",
        help="preflight is deterministic and free; run/all retain the B0/B1/A1 comparison",
    )
    parser.add_argument("--base-url", default="http://127.0.0.1:8776")
    parser.add_argument(
        "--authorize-model-calls",
        action="store_true",
        help="authorize exactly five bounded calls: one B1 call and four A1 calls",
    )
    parser.add_argument("--output", help="optional path for the compact JSON receipt")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        checked = preflight(args.base_url)
        executed = None
        verified: list[dict[str, Any]] = []
        if args.stage in {"run", "all"}:
            executed = run(
                args.base_url,
                authorize_model_calls=args.authorize_model_calls,
            )
            if args.stage == "all":
                artifact_ids = [
                    executed.get("analysis_artifact", {}).get("artifact_id"),
                    *[
                        item.get("artifact_id")
                        for item in executed.get("run_artifacts", [])
                    ],
                ]
                verified = [
                    verify_artifact(args.base_url, artifact_id)
                    for artifact_id in artifact_ids
                    if artifact_id
                ]
        receipt = summary(checked, executed)
        if verified:
            receipt["verified_artifacts"] = len(verified)
        rendered = json.dumps(receipt, indent=2, sort_keys=True)
        if args.output:
            from pathlib import Path

            Path(args.output).write_text(rendered + "\n", encoding="utf-8")
        print(rendered)
        return 0
    except RuntimeError as error:
        print(str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
