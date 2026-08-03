#!/usr/bin/env python3
"""Write the accepted deterministic Thesis Sprint Day 1 evidence bundle."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from typing import Any

from portfolio_risk_thesis.adapters import (
    HistoricalEventDataAdapter,
    HistoricalMarketDataAdapter,
)
from portfolio_risk_thesis.manifests import (
    load_dataset_manifest,
    load_experiment,
    load_yaml,
    sha256_file,
)
from portfolio_risk_thesis.portfolio import SnapshotBuilder, load_portfolios
from portfolio_risk_thesis.replay import ReplayChannel, ReplayClock
from risk_capabilities import CapabilityRegistry


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
EXAMPLE_ROOT = REPOSITORY_ROOT / "examples" / "portfolio-risk-thesis"
DATASET_MANIFEST = EXAMPLE_ROOT / "data" / "dataset_manifest.yaml"
INSTRUMENT_MAP = EXAMPLE_ROOT / "data" / "instrument_map.yaml"
PORTFOLIOS_ROOT = EXAMPLE_ROOT / "portfolios"
EXPERIMENT_MANIFEST = EXAMPLE_ROOT / "experiments" / "day1_smoke.yaml"
STATUS_PATH = REPOSITORY_ROOT / "config" / "agent" / "thesis-sprint" / "status.json"
SYNTHETIC_DISCLOSURE = (
    "All observations, events, instruments, issuers, and portfolios are "
    "fictional synthetic research inputs; outputs are not investment advice."
)
ARTIFACT_NAMES = (
    "dataset-metadata.json",
    "instrument-map.json",
    "portfolio-definitions.json",
    "replay-specification.json",
    "replay-steps.json",
    "portfolio-snapshots.json",
    "exposure-snapshots.json",
    "nav-and-weights.json",
    "run-manifest.json",
)
SOFTWARE_SOURCE_ROOTS = (
    EXAMPLE_ROOT / "src",
    REPOSITORY_ROOT / "packages" / "risk_capabilities" / "src",
    REPOSITORY_ROOT / "packages" / "risk_data" / "src",
    REPOSITORY_ROOT / "packages" / "risk_domain" / "src",
    REPOSITORY_ROOT / "packages" / "risk_planning" / "src",
)
SOFTWARE_METADATA_FILES = (
    EXAMPLE_ROOT / "pyproject.toml",
    REPOSITORY_ROOT / "requirements" / "day1.lock",
)


class RecordingCapabilityRegistry(CapabilityRegistry):
    """Retain the empty effects returned by each canonical invocation."""

    def __init__(self) -> None:
        super().__init__()
        self.results: list[dict[str, Any]] = []

    def invoke(self, capability_id: str, request: Any) -> Any:
        result = super().invoke(capability_id, request)
        self.results.append(
            {
                "capability_id": result.capability_id,
                "status": result.status,
                "effects": list(result.effects),
                "output_digest": result.output_digest,
            }
        )
        return result


def _json_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    ).encode("utf-8")


def _digest_bytes(value: bytes) -> str:
    return f"sha256:{hashlib.sha256(value).hexdigest()}"


def _semantic_digest(value: Any) -> str:
    payload = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return _digest_bytes(payload)


def automatic_software_revision() -> str:
    """Digest every source and lock file that can affect the Day 1 evidence."""

    paths = [Path(__file__).resolve(), *SOFTWARE_METADATA_FILES]
    for root in SOFTWARE_SOURCE_ROOTS:
        paths.extend(sorted(root.rglob("*.py")))
    source_digests = {
        str(path.resolve().relative_to(REPOSITORY_ROOT)): sha256_file(path)
        for path in sorted(set(paths))
    }
    return _semantic_digest(source_digests)


def resolve_software_revision(explicit_revision: str | None) -> str:
    if explicit_revision is None:
        return automatic_software_revision()
    revision = explicit_revision.strip()
    if not revision:
        raise ValueError("software revision must not be empty")
    return revision


def _relative_source(metadata: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(metadata)
    normalized["source_paths"] = [
        str(Path(path).resolve().relative_to(REPOSITORY_ROOT))
        for path in metadata["source_paths"]
    ]
    return normalized


def _validate_data_root(data_root: Path) -> Path:
    if not data_root.is_absolute():
        raise ValueError("THESIS_DATA_ROOT must be an explicit absolute path")
    resolved = data_root.resolve(strict=False)
    configured = os.environ.get("THESIS_DATA_ROOT")
    if not configured:
        raise ValueError("THESIS_DATA_ROOT must be configured")
    configured_root = Path(configured)
    if not configured_root.is_absolute():
        raise ValueError("THESIS_DATA_ROOT must be an absolute path")
    if configured_root.resolve(strict=False) != resolved:
        raise ValueError("--data-root must equal THESIS_DATA_ROOT")
    if resolved == REPOSITORY_ROOT or resolved.is_relative_to(REPOSITORY_ROOT):
        raise ValueError("THESIS_DATA_ROOT must remain outside Git")
    return resolved


def _write_immutable(output_root: Path, artifacts: dict[str, bytes]) -> None:
    output_root.mkdir(parents=True, exist_ok=True)
    unexpected = {
        path.name for path in output_root.iterdir() if path.name not in artifacts
    }
    if unexpected:
        raise ValueError(
            f"immutable run directory contains unexpected artifacts: {sorted(unexpected)}"
        )
    for name, content in artifacts.items():
        path = output_root / name
        if path.exists():
            if not path.is_file() or path.read_bytes() != content:
                raise ValueError(f"immutable artifact differs from accepted content: {path}")
            continue
        path.write_bytes(content)


def run_day1_demo(
    data_root: Path,
    *,
    software_revision: str | None = None,
) -> Path:
    """Run all portfolios and write a content-addressed external evidence bundle."""

    data_root = _validate_data_root(data_root)
    software_revision = resolve_software_revision(software_revision)
    status = json.loads(STATUS_PATH.read_text(encoding="utf-8"))
    market_metadata, event_metadata = load_dataset_manifest(DATASET_MANIFEST)
    market = HistoricalMarketDataAdapter(market_metadata)
    events = HistoricalEventDataAdapter(event_metadata)
    portfolios = load_portfolios(PORTFOLIOS_ROOT)
    instrument_map = load_yaml(INSTRUMENT_MAP)

    portfolio_sources = {
        portfolio.portfolio_id: PORTFOLIOS_ROOT / f"{portfolio.portfolio_id}.yaml"
        for portfolio in portfolios
    }
    portfolio_digests = {
        portfolio_id: sha256_file(path)
        for portfolio_id, path in sorted(portfolio_sources.items())
    }
    specifications = {
        portfolio.portfolio_id: load_experiment(
            EXPERIMENT_MANIFEST, portfolio.portfolio_id
        )
        for portfolio in portfolios
    }

    replay_payloads: list[dict[str, Any]] = []
    portfolio_snapshot_payloads: list[dict[str, Any]] = []
    exposure_snapshot_payloads: list[dict[str, Any]] = []
    nav_payloads: list[dict[str, Any]] = []
    for portfolio in portfolios:
        specification = specifications[portfolio.portfolio_id]
        if specification.dataset_revision != market_metadata.revision:
            raise ValueError("experiment and dataset revisions do not match")
        registry = RecordingCapabilityRegistry()
        clock = ReplayClock(specification, specification.review_time)
        results = ReplayChannel(
            market,
            events,
            SnapshotBuilder(registry),
        ).replay(clock, specification, portfolio)
        if len(registry.results) != len(results) * 2:
            raise ValueError("each replay step must invoke exactly two capabilities")

        replay_steps: list[dict[str, Any]] = []
        for index, result in enumerate(results):
            invocations = registry.results[index * 2 : index * 2 + 2]
            replay_steps.append(
                {
                    **result.step.model_dump(mode="json"),
                    "capability_invocations": invocations,
                    "effects": [],
                }
            )
            portfolio_snapshot_payloads.append(
                {
                    "portfolio_id": portfolio.portfolio_id,
                    "run_id": result.step.run_id,
                    "ordinal": result.step.ordinal,
                    "snapshot": result.snapshot.portfolio_snapshot.model_dump(
                        mode="json"
                    ),
                    "effects": [],
                }
            )
            exposure = result.snapshot.exposure_snapshot
            exposure_snapshot_payloads.append(
                {
                    "portfolio_id": portfolio.portfolio_id,
                    "run_id": result.step.run_id,
                    "ordinal": result.step.ordinal,
                    "snapshot": exposure.model_dump(mode="json"),
                    "effects": [],
                }
            )
            nav_payloads.append(
                {
                    "portfolio_id": portfolio.portfolio_id,
                    "run_id": result.step.run_id,
                    "ordinal": result.step.ordinal,
                    "as_of": result.step.as_of.isoformat().replace("+00:00", "Z"),
                    "nav": str(exposure.nav),
                    "position_weights": {
                        item.instrument_id: str(item.weight)
                        for item in exposure.position_exposures
                    },
                    "cash_weight": str(exposure.cash_weight),
                    "effects": [],
                }
            )
        replay_payloads.append(
            {
                "portfolio_id": portfolio.portfolio_id,
                "run_id": clock.run_id,
                "steps": replay_steps,
                "effects": [],
            }
        )

    market_dump = _relative_source(market_metadata.model_dump(mode="json"))
    event_dump = _relative_source(event_metadata.model_dump(mode="json"))
    instrument_map_digest = sha256_file(INSTRUMENT_MAP)
    total_steps = sum(len(item["steps"]) for item in replay_payloads)
    first_specification = next(iter(specifications.values()))
    identity = {
        "experiment_id": status["experiment_id"],
        "dataset_revision": market_metadata.revision,
        "market_source_digest": market_metadata.source_digests[0],
        "event_source_digest": event_metadata.source_digests[0],
        "instrument_map_digest": instrument_map_digest,
        "portfolio_definition_digests": portfolio_digests,
        "start": first_specification.start.isoformat(),
        "end": first_specification.end.isoformat(),
        "cadence": first_specification.cadence,
        "number_of_replay_steps": total_steps,
        "no_look_ahead_rule": first_specification.no_look_ahead_rule,
        "fixture_seed": first_specification.deterministic_seed,
        "software_revision": software_revision,
    }
    run_id = _semantic_digest(identity)
    run_manifest: dict[str, Any] = {
        "run_id": run_id,
        "experiment_id": status["experiment_id"],
        "replay_experiment_id": first_specification.experiment_id,
        "dataset_revision": market_metadata.revision,
        "market_source_digest": market_metadata.source_digests[0],
        "event_source_digest": event_metadata.source_digests[0],
        "instrument_map_digest": instrument_map_digest,
        "portfolio_definition_digests": portfolio_digests,
        "start": first_specification.start.isoformat().replace("+00:00", "Z"),
        "end": first_specification.end.isoformat().replace("+00:00", "Z"),
        "cadence": first_specification.cadence,
        "portfolio_count": len(portfolios),
        "replay_steps_per_portfolio": len(replay_payloads[0]["steps"]),
        "number_of_replay_steps": total_steps,
        "no_look_ahead_rule": first_specification.no_look_ahead_rule,
        "fixture_seed": first_specification.deterministic_seed,
        "software_revision": software_revision,
        "synthetic": True,
        "synthetic_disclosure": SYNTHETIC_DISCLOSURE,
        "effects": [],
    }
    payloads = {
        "dataset-metadata.json": {
            "market": market_dump,
            "events": event_dump,
            "synthetic": True,
            "synthetic_disclosure": SYNTHETIC_DISCLOSURE,
        },
        "instrument-map.json": {
            "digest": instrument_map_digest,
            "instrument_map": instrument_map,
        },
        "portfolio-definitions.json": {
            "portfolios": [
                {
                    "definition": portfolio.model_dump(mode="json"),
                    "digest": portfolio_digests[portfolio.portfolio_id],
                }
                for portfolio in portfolios
            ],
            "effects": [],
        },
        "replay-specification.json": {
            "specifications": [
                specifications[portfolio.portfolio_id].model_dump(mode="json")
                for portfolio in portfolios
            ],
            "synthetic": True,
            "effects": [],
        },
        "replay-steps.json": {
            "portfolios": replay_payloads,
            "effects": [],
        },
        "portfolio-snapshots.json": {
            "snapshots": portfolio_snapshot_payloads,
            "effects": [],
        },
        "exposure-snapshots.json": {
            "snapshots": exposure_snapshot_payloads,
            "effects": [],
        },
        "nav-and-weights.json": {
            "values": nav_payloads,
            "effects": [],
        },
        "run-manifest.json": run_manifest,
    }
    artifacts = {name: _json_bytes(payloads[name]) for name in ARTIFACT_NAMES}
    evidence_manifest = {
        "run_id": run_id,
        "algorithm": "sha256",
        "artifacts": {
            name: _digest_bytes(artifacts[name]) for name in ARTIFACT_NAMES
        },
        "synthetic": True,
        "effects": [],
    }
    artifacts["evidence-manifest.json"] = _json_bytes(evidence_manifest)

    output_root = data_root / "day1" / run_id
    _write_immutable(output_root, artifacts)
    return output_root


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data-root",
        type=Path,
        default=os.environ.get("THESIS_DATA_ROOT"),
        required=os.environ.get("THESIS_DATA_ROOT") is None,
        help="Absolute external root equal to THESIS_DATA_ROOT",
    )
    parser.add_argument(
        "--software-revision",
        help=(
            "Explicit software revision; defaults to a canonical digest of the "
            "accepted execution sources and locked environment"
        ),
    )
    args = parser.parse_args(argv)
    try:
        output_root = run_day1_demo(
            args.data_root, software_revision=args.software_revision
        )
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as error:
        parser.exit(1, f"Thesis Day 1 demo failed: {error}\n")
    print(f"Thesis Day 1 demo: PASS ({output_root})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
