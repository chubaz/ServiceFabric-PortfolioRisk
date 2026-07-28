from __future__ import annotations

import hashlib
import json
import os
import subprocess
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from portfolio_risk_thesis.adapters import HistoricalMarketDataAdapter
from portfolio_risk_thesis.manifests import load_dataset_manifest, load_portfolio
from risk_domain import ExposureSnapshot, PortfolioSnapshot
from scripts.thesis.run_day1_demo import (
    ARTIFACT_NAMES,
    automatic_software_revision,
    resolve_software_revision,
    run_day1_demo,
)


ROOT = Path(__file__).resolve().parents[2]
EXAMPLE_ROOT = ROOT / "examples" / "portfolio-risk-thesis"
EXPECTED_PORTFOLIOS = {
    "defensive_multi_asset",
    "diversified",
    "technology_concentrated",
}
PROHIBITED_OBJECT_KEYS = {"broker", "order", "trade", "rebalance"}


def _read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _digest(path: Path) -> str:
    return f"sha256:{hashlib.sha256(path.read_bytes()).hexdigest()}"


def _assert_no_prohibited_object(value: Any) -> None:
    if isinstance(value, dict):
        assert PROHIBITED_OBJECT_KEYS.isdisjoint(
            {str(key).lower() for key in value}
        )
        for child in value.values():
            _assert_no_prohibited_object(child)
    elif isinstance(value, list):
        for child in value:
            _assert_no_prohibited_object(child)


def test_thesis_day1_vertical_slice_is_complete_deterministic_and_external(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    status_before = subprocess.run(
        ["git", "status", "--short", "--untracked-files=all"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    roots = (tmp_path / "first", tmp_path / "second")
    output_roots: list[Path] = []
    for root in roots:
        monkeypatch.setenv("THESIS_DATA_ROOT", str(root))
        output_roots.append(run_day1_demo(root))
    status_after = subprocess.run(
        ["git", "status", "--short", "--untracked-files=all"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    assert status_after == status_before
    assert all(not output.is_relative_to(ROOT) for output in output_roots)

    required = set(ARTIFACT_NAMES) | {"evidence-manifest.json"}
    assert {path.name for path in output_roots[0].iterdir()} == required
    assert {path.name for path in output_roots[1].iterdir()} == required
    for name in required:
        assert (output_roots[0] / name).read_bytes() == (
            output_roots[1] / name
        ).read_bytes()

    run_manifest = _read(output_roots[0] / "run-manifest.json")
    evidence_manifest = _read(output_roots[0] / "evidence-manifest.json")
    assert output_roots[0].name == output_roots[1].name == run_manifest["run_id"]
    assert evidence_manifest["run_id"] == run_manifest["run_id"]
    assert set(evidence_manifest["artifacts"]) == set(ARTIFACT_NAMES)
    for name, digest in evidence_manifest["artifacts"].items():
        assert digest == _digest(output_roots[0] / name)

    replay = _read(output_roots[0] / "replay-steps.json")
    specifications = {
        item["portfolio_id"]: item
        for item in _read(output_roots[0] / "replay-specification.json")[
            "specifications"
        ]
    }
    portfolios = {
        item["portfolio_id"]: item
        for item in replay["portfolios"]
    }
    assert set(portfolios) == set(specifications) == EXPECTED_PORTFOLIOS
    assert run_manifest["portfolio_count"] == 3
    assert run_manifest["replay_steps_per_portfolio"] == 5
    assert run_manifest["number_of_replay_steps"] == 15
    assert run_manifest["software_revision"] == automatic_software_revision()
    assert run_manifest["effects"] == []

    market_metadata, _ = load_dataset_manifest(
        EXAMPLE_ROOT / "data" / "dataset_manifest.yaml"
    )
    market = HistoricalMarketDataAdapter(market_metadata)
    portfolio_snapshots = {
        (item["portfolio_id"], item["ordinal"]): item
        for item in _read(output_roots[0] / "portfolio-snapshots.json")[
            "snapshots"
        ]
    }
    exposure_snapshots = {
        (item["portfolio_id"], item["ordinal"]): item
        for item in _read(output_roots[0] / "exposure-snapshots.json")[
            "snapshots"
        ]
    }
    nav_and_weights = {
        (item["portfolio_id"], item["ordinal"]): item
        for item in _read(output_roots[0] / "nav-and-weights.json")["values"]
    }

    semantic_ids: list[str] = [run_manifest["run_id"]]
    semantic_digests: list[str] = list(evidence_manifest["artifacts"].values())
    for portfolio_id, replay_item in portfolios.items():
        steps = replay_item["steps"]
        specification = specifications[portfolio_id]
        assert len(steps) == 5
        assert [step["ordinal"] for step in steps] == list(range(5))
        assert len({step["run_id"] for step in steps}) == 1
        assert steps[0]["run_id"] == replay_item["run_id"]
        assert datetime.fromisoformat(specification["start"].replace("Z", "+00:00"))
        assert datetime.fromisoformat(specification["end"].replace("Z", "+00:00"))

        definition = load_portfolio(
            EXAMPLE_ROOT / "portfolios" / f"{portfolio_id}.yaml"
        )
        instrument_ids = tuple(
            position.instrument_id for position in definition.positions
        )
        for step in steps:
            as_of = datetime.fromisoformat(step["as_of"].replace("Z", "+00:00"))
            assert all(
                datetime.fromisoformat(row["available_at"].replace("Z", "+00:00"))
                <= as_of
                for row in step["newly_eligible_market_records"]
            )
            assert all(
                datetime.fromisoformat(row["available_at"].replace("Z", "+00:00"))
                <= as_of
                for row in step["newly_eligible_event_records"]
            )
            assert all(
                datetime.fromisoformat(row["available_at"].replace("Z", "+00:00"))
                <= as_of
                for row in step["latest_eligible_market_records"]
            )
            expected_latest = market.latest_observations_as_of(
                as_of, instrument_ids
            )
            assert {
                row["instrument_id"]: row["content_digest"]
                for row in step["latest_eligible_market_records"]
            } == {
                row.instrument_id: row.content_digest for row in expected_latest
            }
            assert [
                item["capability_id"] for item in step["capability_invocations"]
            ] == [
                "portfolio.snapshot.create",
                "portfolio.exposure.summarize",
            ]
            assert all(
                item["status"] == "succeeded" and item["effects"] == []
                for item in step["capability_invocations"]
            )
            assert step["effects"] == []

            key = (portfolio_id, step["ordinal"])
            portfolio_item = portfolio_snapshots[key]
            exposure_item = exposure_snapshots[key]
            nav_item = nav_and_weights[key]
            portfolio_snapshot = PortfolioSnapshot.model_validate(
                portfolio_item["snapshot"]
            )
            exposure_snapshot = ExposureSnapshot.model_validate(
                exposure_item["snapshot"]
            )
            assert portfolio_snapshot.model_config["frozen"] is True
            with pytest.raises(ValidationError):
                portfolio_snapshot.snapshot_id = "mutable"  # type: ignore[misc]
            positions_value = sum(
                (position.market_value for position in portfolio_snapshot.positions),
                Decimal("0"),
            )
            cash_value = sum(
                (cash.amount for cash in portfolio_snapshot.cash_balances),
                Decimal("0"),
            )
            assert exposure_snapshot.nav > 0
            assert exposure_snapshot.nav == positions_value + cash_value
            total_weight = sum(
                (
                    position.weight
                    for position in exposure_snapshot.position_exposures
                ),
                Decimal("0"),
            ) + exposure_snapshot.cash_weight
            assert abs(total_weight - Decimal("1")) <= Decimal("1e-28")
            assert Decimal(nav_item["nav"]) == exposure_snapshot.nav
            assert all(
                item["effects"] == []
                for item in (portfolio_item, exposure_item, nav_item)
            )
            semantic_ids.extend(
                [
                    step["run_id"],
                    portfolio_snapshot.snapshot_id,
                    exposure_snapshot.snapshot_id,
                ]
            )
            semantic_digests.extend(
                [portfolio_snapshot.digest, exposure_snapshot.digest]
            )

    assert semantic_ids == list(semantic_ids)
    assert all(value and value.startswith("sha256:") for value in semantic_digests)
    for name in required:
        _assert_no_prohibited_object(_read(output_roots[0] / name))


def test_explicit_software_revision_is_preserved_and_changes_run_identity(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    automatic_root = tmp_path / "automatic"
    monkeypatch.setenv("THESIS_DATA_ROOT", str(automatic_root))
    automatic_output = run_day1_demo(automatic_root)

    explicit_root = tmp_path / "explicit"
    monkeypatch.setenv("THESIS_DATA_ROOT", str(explicit_root))
    explicit_output = run_day1_demo(
        explicit_root, software_revision="accepted-source-revision"
    )

    automatic_manifest = _read(automatic_output / "run-manifest.json")
    explicit_manifest = _read(explicit_output / "run-manifest.json")
    assert automatic_manifest["software_revision"] == automatic_software_revision()
    assert explicit_manifest["software_revision"] == "accepted-source-revision"
    assert automatic_manifest["run_id"] != explicit_manifest["run_id"]
    assert resolve_software_revision(" accepted-source-revision ") == (
        "accepted-source-revision"
    )
    with pytest.raises(ValueError, match="must not be empty"):
        resolve_software_revision(" ")
