#!/usr/bin/env python3
"""Run the deterministic, effect-free Day 1 Workbench journey headlessly."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

from risk_capabilities import CapabilityRegistry
from risk_data import (
    PortfolioConfirmationRequest,
    PortfolioInputFormat,
    PortfolioInputService,
    provider_catalogue,
    reviewed_query_manifests,
)
from risk_data.pipeline import resolve_data_root
from risk_domain import MarketObservation, PortfolioSnapshot, QualityFlag


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
APPLICATION_ROOT = REPOSITORY_ROOT / "apps" / "portfolio-risk-workbench"
if str(APPLICATION_ROOT) not in sys.path:
    sys.path.insert(0, str(APPLICATION_ROOT))

from analysis_service import (  # noqa: E402
    DEFAULT_CONFIDENCE_LEVEL,
    DEFAULT_SCENARIO_ID,
    ReviewedRiskAnalysisService,
)


AS_OF = datetime(2026, 7, 17, 16, 0, tzinfo=UTC)
OUTPUT_DIRECTORY = Path("day1-workbench")
OUTPUT_NAMES = {
    "input_preview": "input-preview.json",
    "confirmed_snapshot": "confirmed-portfolio-snapshot.json",
    "snapshot_comparison": "snapshot-comparison.json",
    "provider_catalogue": "provider-catalogue.json",
    "risk_analysis": "risk-analysis.json",
    "scenario_analysis": "scenario-analysis.json",
    "agent_timeline": "agent-timeline.json",
    "report_markdown": "report.md",
    "report_html": "report.html",
    "evidence_manifest": "evidence-manifest.json",
}
EXTERNAL_PROVIDERS = {"wrds", "crsp", "compustat", "ravenpack", "accern", "bloomberg"}
PROHIBITED_EFFECTS = (
    "broker_connectivity",
    "order_submission",
    "trade_execution",
    "automatic_rebalancing",
    "optimization",
    "notebook_execution",
)


def _json_value(value: object) -> object:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")  # type: ignore[union-attr]
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_json_value(item) for item in value]
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, datetime):
        return value.astimezone(UTC).isoformat().replace("+00:00", "Z")
    return value


def _encoded(value: object) -> bytes:
    return (json.dumps(_json_value(value), indent=2, sort_keys=True) + "\n").encode("utf-8")


def _write_stable(path: Path, content: bytes) -> Path:
    if path.exists():
        if path.read_bytes() != content:
            raise FileExistsError(f"immutable Day 1 output differs from existing artifact: {path}")
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path


def _digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _confirmation_evidence(confirmation: object) -> dict[str, object]:
    """Canonicalize the run-local creation outcome for repeatable evidence."""
    if not hasattr(confirmation, "model_dump"):
        raise TypeError("confirmation evidence must be a Pydantic contract")
    evidence = confirmation.model_dump(mode="json")  # type: ignore[union-attr]
    evidence["created"] = True
    return evidence


def _observations() -> tuple[MarketObservation, ...]:
    prices = {
        "instrument-alpha": ("100", "102", "99", "105", "100", "110", "98", "101", "95", "97", "90", "93"),
        "instrument-beta": ("50", "49", "51", "52", "50", "53", "51", "54", "52", "55", "53", "56"),
    }
    start = AS_OF - timedelta(days=len(next(iter(prices.values()))) - 1)
    return tuple(
        MarketObservation(
            instrument_id=instrument_id,
            observed_at=start + timedelta(days=index),
            price=Decimal(price),
            currency="USD",
            quality_flags=(QualityFlag.COMPLETE,),
            synthetic=True,
        )
        for instrument_id, values in sorted(prices.items())
        for index, price in enumerate(values)
    )


def _yaml_input(alpha_quantity: str) -> bytes:
    return (
        "profile: personal_portfolio\n"
        f"as_of: '{AS_OF.isoformat()}'\n"
        "base_currency: USD\n"
        "positions:\n"
        f"  - instrument_id: instrument-alpha\n    quantity: '{alpha_quantity}'\n    currency: USD\n"
        "  - instrument_id: instrument-beta\n    quantity: '20'\n    currency: USD\n"
        "cash_balances:\n  USD: '1000'\n"
    ).encode("utf-8")


def _latest_observations(observations: tuple[MarketObservation, ...]) -> dict[str, MarketObservation]:
    selected: dict[str, MarketObservation] = {}
    for observation in observations:
        current = selected.get(observation.instrument_id)
        if current is None or observation.observed_at > current.observed_at:
            selected[observation.instrument_id] = observation
    return selected


def _load_snapshot(root: Path, snapshot_id: str) -> PortfolioSnapshot:
    path = root / "portfolio-snapshots" / f"{snapshot_id}.json"
    return PortfolioSnapshot.model_validate_json(path.read_text(encoding="utf-8"))


def execute_day1_journey(output_root: Path | str | None = None) -> dict[str, Any]:
    """Execute all accepted Day 1 package seams without external effects."""
    root = resolve_data_root(output_root)
    service = PortfolioInputService(root)
    observations = _observations()
    latest = _latest_observations(observations)

    research_csv = (
        "instrument_id,quantity,currency,as_of\n"
        f"instrument-alpha,10,USD,{AS_OF.isoformat()}\n"
    ).encode("utf-8")
    research_preview = service.preview(
        research_csv,
        PortfolioInputFormat.CSV,
        profile="research",
        base_currency="USD",
        as_of=AS_OF,
    )
    personal_preview = service.preview(_yaml_input("10"), PortfolioInputFormat.YAML)
    invalid_preview = service.preview(
        b"instrument_id,quantity,currency,as_of\ninstrument-alpha,not-a-decimal,USD,invalid\n",
        PortfolioInputFormat.CSV,
        profile="personal_portfolio",
        base_currency="USD",
        as_of=AS_OF,
    )

    confirmation = service.confirm(
        personal_preview,
        PortfolioConfirmationRequest(confirm=True, preview_digest=personal_preview.preview_digest),
        latest,
    )
    initial_snapshot = _load_snapshot(root, confirmation.snapshot_id)
    corrected_preview = service.preview(_yaml_input("12"), PortfolioInputFormat.YAML)
    corrected_confirmation = service.confirm(
        corrected_preview,
        PortfolioConfirmationRequest(confirm=True, preview_digest=corrected_preview.preview_digest),
        latest,
    )
    corrected_snapshot = _load_snapshot(root, corrected_confirmation.snapshot_id)
    comparison = service.compare(initial_snapshot, corrected_snapshot)

    providers = provider_catalogue()
    manifests = reviewed_query_manifests()
    external = tuple(item for item in providers if item.provider_id in EXTERNAL_PROVIDERS)
    if len(external) != len(EXTERNAL_PROVIDERS) or any(item.enabled for item in external):
        raise RuntimeError("every reviewed external provider must remain disabled")

    analysis_service = ReviewedRiskAnalysisService(CapabilityRegistry(), corrected_snapshot, observations)
    method_ids = (
        "simple_returns",
        "log_returns",
        "annualized_volatility",
        "maximum_drawdown",
        "historical_var",
        "historical_expected_shortfall",
        "contribution_summary",
    )
    analyses = {
        method_id: analysis_service.analyze(
            method_id,
            confidence_level=DEFAULT_CONFIDENCE_LEVEL,
            scenario_id=DEFAULT_SCENARIO_ID,
        )
        for method_id in method_ids
    }
    scenario = analysis_service.analyze(
        "fixed_scenario",
        confidence_level=DEFAULT_CONFIDENCE_LEVEL,
        scenario_id=DEFAULT_SCENARIO_ID,
    )
    timeline = analysis_service.timeline()
    report_source, report = analysis_service.report(
        "historical_var",
        confidence_level=DEFAULT_CONFIDENCE_LEVEL,
        scenario_id=DEFAULT_SCENARIO_ID,
    )

    return {
        "data_root": root,
        "profiles": ("research", "personal_portfolio"),
        "research_preview": research_preview,
        "personal_preview": personal_preview,
        "invalid_preview": invalid_preview,
        "confirmation": confirmation,
        "initial_snapshot": initial_snapshot,
        "corrected_preview": corrected_preview,
        "corrected_confirmation": corrected_confirmation,
        "corrected_snapshot": corrected_snapshot,
        "comparison": comparison,
        "providers": providers,
        "query_manifests": manifests,
        "analyses": analyses,
        "scenario": scenario,
        "timeline": timeline,
        "report_source": report_source,
        "report": report,
        "effects": (),
        "prohibited_effects": PROHIBITED_EFFECTS,
        "human_review": {"required": True, "state": "pending"},
    }


def write_day1_artifacts(result: dict[str, Any]) -> dict[str, Path]:
    """Write the required deterministic Day 1 evidence set beneath the data root."""
    root = Path(result["data_root"])
    output = root / OUTPUT_DIRECTORY
    paths = {key: output / name for key, name in OUTPUT_NAMES.items()}

    json_payloads = {
        "input_preview": {
            "profiles": result["profiles"],
            "research": result["research_preview"],
            "personal_portfolio": result["personal_preview"],
            "invalid": result["invalid_preview"],
            "raw_input_persisted": False,
        },
        "confirmed_snapshot": {
            "confirmation": _confirmation_evidence(result["confirmation"]),
            "snapshot": result["initial_snapshot"],
            "corrected_confirmation": _confirmation_evidence(result["corrected_confirmation"]),
            "corrected_revision": result["corrected_snapshot"],
            "immutable": True,
        },
        "snapshot_comparison": result["comparison"],
        "provider_catalogue": {
            "providers": result["providers"],
            "fixed_query_manifests": result["query_manifests"],
            "arbitrary_sql_available": False,
        },
        "risk_analysis": {
            "analyses": result["analyses"],
            "human_review": result["human_review"],
            "effects": result["effects"],
        },
        "scenario_analysis": {
            "scenario": result["scenario"],
            "fixed_catalogue_only": True,
            "effects": result["effects"],
        },
        "agent_timeline": {
            "timeline": result["timeline"],
            "human_review": result["human_review"],
            "effects": result["effects"],
        },
    }
    for key, payload in json_payloads.items():
        _write_stable(paths[key], _encoded(payload))

    report = result["report"].data
    if report is None:
        raise RuntimeError("the reviewed report capability did not produce a report")
    _write_stable(paths["report_markdown"], report.markdown.encode("utf-8"))
    _write_stable(paths["report_html"], report.html.encode("utf-8"))

    evidence_paths = tuple(path for key, path in paths.items() if key != "evidence_manifest")
    manifest = {
        "manifest_type": "day1-workbench-evidence",
        "generated_at": AS_OF,
        "synthetic": True,
        "profiles": result["profiles"],
        "human_review": result["human_review"],
        "effects": result["effects"],
        "prohibited_effects": result["prohibited_effects"],
        "artifacts": tuple(
            {"path": path.relative_to(root).as_posix(), "digest": _digest(path)}
            for path in evidence_paths
        ),
    }
    _write_stable(paths["evidence_manifest"], _encoded(manifest))
    return paths


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-root",
        type=Path,
        default=os.environ.get("PORTFOLIO_RISK_DATA_ROOT"),
        help="External data root (defaults to PORTFOLIO_RISK_DATA_ROOT).",
    )
    args = parser.parse_args()
    result = execute_day1_journey(args.output_root)
    paths = write_day1_artifacts(result)
    print(json.dumps({key: str(value) for key, value in paths.items()}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
