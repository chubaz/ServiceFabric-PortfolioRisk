from __future__ import annotations

import hashlib
import inspect
import json
from copy import deepcopy
from pathlib import Path

import pytest
import yaml

from portfolio_risk_thesis.cli import main as cli_main
from portfolio_risk_thesis.manifests import load_portfolio, sha256_file
from portfolio_risk_thesis.portfolio import (
    PortfolioMaterializationError,
    materialize_real_portfolios,
    validate_materialized_real_portfolios,
)
from portfolio_risk_thesis.portfolio import materialization


def _candidate(index: int) -> dict[str, object]:
    observations = 300 + index
    return {
        "candidate_id": f"candidate_{index:024x}",
        "permno": 10000 + index,
        "observation_count": observations,
        "latest_eligible_date": "2024-12-31",
        "missing_total_return_count": 0,
        "missing_valuation_price_count": 0,
        "active_stock_names_coverage": {
            "eligible_observations": observations,
            "covered_observations": observations,
            "missing_observations": 0,
        },
        "sector": None,
        "sic_code": 1000 + index,
        "ccm_eligible_link_count": 1,
        "fundamental_availability_coverage": {
            "eligible_observations": observations,
            "available_observations": observations,
            "missing_observations": 0,
        },
        "quality_warnings": [],
    }


def _artifact(path: Path) -> dict[str, object]:
    body: dict[str, object] = {
        "artifact_version": "2.0",
        "snapshot_id": "crsp_compustat_0123456789abcdef01234567",
        "as_of": "2025-01-02T00:00:00Z",
        "minimum_observations": 260,
        "created_from": {
            "dataset_receipt_id": "receipt_crsp_compustat_0123456789abcdef01234567",
            "catalogue_digest": "sha256:" + "a" * 64,
        },
        "candidates": [_candidate(index) for index in range(1, 17)],
    }
    identity_payload = json.dumps(
        body, sort_keys=True, separators=(",", ":"), default=str
    ).encode("utf-8")
    artifact = {
        "artifact_version": body["artifact_version"],
        "artifact_id": (
            "candidate_artifact_"
            + hashlib.sha256(identity_payload).hexdigest()[:24]
        ),
        **{key: value for key, value in body.items() if key != "artifact_version"},
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(artifact, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return artifact


def _selection(artifact_path: Path) -> dict[str, object]:
    artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
    return {
        "selection_version": "1.0",
        "selection_id": "reviewed-selection-001",
        "reviewed": True,
        "reviewer_id": "local-human-reviewer",
        "reviewed_at": "2025-01-02T10:00:00Z",
        "candidate_artifact": {
            "path": str(artifact_path),
            "sha256": sha256_file(artifact_path),
            "artifact_id": artifact["artifact_id"],
        },
        "source_snapshot_id": artifact["snapshot_id"],
        "as_of": artifact["as_of"],
        "effective_at": "2025-01-03T00:00:00Z",
        "rationale": (
            "Human reviewer supplied every fixed position and cash balance."
        ),
        "warnings": [
            "Private licensed evidence; not investment advice.",
        ],
        "portfolios": [
            {
                "portfolio_id": "diversified",
                "title": "Private Human-Reviewed Fixed-Quantity Portfolio",
                "base_currency": "USD",
                "benchmark_unavailable": True,
                "cash": [{"currency": "USD", "amount": "1000.00"}],
                "positions": [
                    {
                        "candidate_id": f"candidate_{index:024x}",
                        "instrument_alias": f"private-instrument-{index}",
                        "quantity": str(index),
                    }
                    for index in range(1, 6)
                ],
            }
        ],
    }


def _write_selection(path: Path, value: dict[str, object]) -> Path:
    path.write_text(yaml.safe_dump(value, sort_keys=False), encoding="utf-8")
    return path


@pytest.fixture
def private_inputs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[Path, Path, Path, dict[str, object]]:
    monkeypatch.setenv("THESIS_DATA_ROOT", str(tmp_path))
    artifact_path = tmp_path / "inputs" / "candidate-artifact.json"
    _artifact(artifact_path)
    selection = _selection(artifact_path)
    selection_path = _write_selection(
        tmp_path / "reviewed-selection.yaml", selection
    )
    return artifact_path, selection_path, tmp_path / "outputs", selection


def _materialize(
    private_inputs: tuple[Path, Path, Path, dict[str, object]]
):
    artifact, selection, output, _ = private_inputs
    return materialize_real_portfolios(
        candidate_artifact_path=artifact,
        selection_path=selection,
        output_directory=output,
    )


def test_interactive_selection_wizard_repairs_metadata_and_requires_confirmation(
    private_inputs: tuple[Path, Path, Path, dict[str, object]],
    tmp_path: Path,
) -> None:
    artifact, _, _, _ = private_inputs
    answers = iter(
        [
            "local-reviewer",
            "reviewed-selection-wizard",
            "2025-01-02T10:00:00Z",
            "2025-01-03T00:00:00Z",
            "Explicit local research design.",
            "1,2,3,4,5",
            "1000",
            "100", "100", "100", "100", "100",
            "6,7,8,9,10",
            "1000",
            "100", "100", "100", "100", "100",
            "11,12,13,14,15",
            "1000",
            "100", "100", "100", "100", "100",
            "REVIEWED",
        ]
    )
    output = tmp_path / "wizard-selection.yaml"
    written = materialization.prepare_real_selection_interactive(
        candidate_artifact_path=artifact,
        selection_path=output,
        input_fn=lambda _: next(answers),
        print_fn=lambda _: None,
    )
    assert written == output
    value = yaml.safe_load(output.read_text(encoding="utf-8"))
    assert value["reviewed"] is True
    assert value["candidate_artifact"]["path"] == str(artifact.resolve())
    assert value["source_snapshot_id"] == "crsp_compustat_0123456789abcdef01234567"
    assert len(value["portfolios"]) == 3
    assert all(len(item["positions"]) == 5 for item in value["portfolios"])
    assert output.stat().st_mode & 0o777 == 0o600


def test_no_selection_argument_fails_before_materialization() -> None:
    with pytest.raises(SystemExit):
        cli_main(
            [
                "init-real-portfolios",
                "--candidate-artifact",
                "/private/candidate.json",
                "--output-directory",
                "/private/output",
            ]
        )


def test_real_portfolio_cli_commands_materialize_and_validate(
    private_inputs: tuple[Path, Path, Path, dict[str, object]],
    capsys: pytest.CaptureFixture[str],
) -> None:
    artifact, selection, output, original = private_inputs
    assert cli_main(
        [
            "init-real-portfolios",
            "--candidate-artifact",
            str(artifact),
            "--selection",
            str(selection),
            "--output-directory",
            str(output),
        ]
    ) == 0
    initialized = json.loads(capsys.readouterr().out)
    assert initialized["selection_id"] == original["selection_id"]
    assert initialized["portfolio_count"] == 1
    assert initialized["effects"] == 0
    target = (
        output
        / "portfolio-definitions"
        / str(original["selection_id"])
    )
    assert cli_main(
        [
            "validate-real-portfolios",
            "--portfolios-directory",
            str(target),
            "--receipt",
            str(target / "portfolio-selection-receipt.json"),
        ]
    ) == 0
    validated = json.loads(capsys.readouterr().out)
    assert validated["receipt_id"] == initialized["receipt_id"]
    assert validated["validated"] is True
    assert validated["effects"] == 0


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda value: value.__setitem__("reviewed", False), "reviewed"),
        (lambda value: value.pop("reviewer_id"), "reviewer_id"),
        (lambda value: value.pop("source_snapshot_id"), "source_snapshot_id"),
        (lambda value: value.pop("as_of"), "as_of"),
        (lambda value: value.pop("rationale"), "rationale"),
        (lambda value: value.pop("warnings"), "warnings"),
        (
            lambda value: value.__setitem__(
                "source_snapshot_id", "different-reviewed-snapshot"
            ),
            "snapshot does not match",
        ),
        (
            lambda value: value.__setitem__(
                "as_of", "2025-01-01T00:00:00Z"
            ),
            "as_of does not match",
        ),
        (
            lambda value: value["candidate_artifact"].__setitem__(
                "sha256", "sha256:" + "0" * 64
            ),
            "digest mismatch",
        ),
        (
            lambda value: value["candidate_artifact"].__setitem__(
                "artifact_id", "different-artifact-id"
            ),
            "ID mismatch",
        ),
        (
            lambda value: value["portfolios"][0]["positions"][0].__setitem__(
                "candidate_id", "candidate_unknown"
            ),
            "unknown candidate",
        ),
        (
            lambda value: value["portfolios"][0]["positions"][1].__setitem__(
                "candidate_id", "candidate_000000000000000000000001"
            ),
            "distinct",
        ),
        (
            lambda value: value["portfolios"][0]["positions"][1].__setitem__(
                "instrument_alias", "private-instrument-1"
            ),
            "distinct",
        ),
        (
            lambda value: (
                value["portfolios"][0]["positions"][0].pop("candidate_id"),
                value["portfolios"][0]["positions"][0].update(
                    {"ticker": "PLACEHOLDER"}
                ),
            ),
            "ticker",
        ),
        (
            lambda value: value["portfolios"][0]["positions"][0].__setitem__(
                "quantity", "0"
            ),
            "positive",
        ),
        (
            lambda value: value["portfolios"][0]["positions"][0].__setitem__(
                "quantity", "1.25"
            ),
            "positive integer",
        ),
        (
            lambda value: value["portfolios"][0].pop("cash"),
            "cash",
        ),
        (
            lambda value: value.__setitem__(
                "effective_at", "2025-01-01T00:00:00Z"
            ),
            "as_of must not be later",
        ),
    ],
)
def test_review_and_selection_validation_fail_closed(
    private_inputs: tuple[Path, Path, Path, dict[str, object]],
    mutation,
    message: str,
) -> None:
    artifact, _, output, original = private_inputs
    changed = deepcopy(original)
    mutation(changed)
    selection_path = _write_selection(
        artifact.parent.parent / f"invalid-{hashlib.sha256(message.encode()).hexdigest()[:8]}.yaml",
        changed,
    )
    with pytest.raises(PortfolioMaterializationError, match=message):
        materialize_real_portfolios(
            candidate_artifact_path=artifact,
            selection_path=selection_path,
            output_directory=output,
        )


@pytest.mark.parametrize("position_count", [4, 9])
def test_position_count_is_bounded(
    private_inputs: tuple[Path, Path, Path, dict[str, object]],
    position_count: int,
) -> None:
    artifact, _, output, original = private_inputs
    changed = deepcopy(original)
    changed["portfolios"][0]["positions"] = [
        {
            "candidate_id": f"candidate_{index:024x}",
            "instrument_alias": f"private-instrument-{index}",
            "quantity": "1",
        }
        for index in range(1, position_count + 1)
    ]
    selection_path = _write_selection(
        artifact.parent.parent / f"invalid-count-{position_count}.yaml", changed
    )
    with pytest.raises(PortfolioMaterializationError, match="positions"):
        materialize_real_portfolios(
            candidate_artifact_path=artifact,
            selection_path=selection_path,
            output_directory=output,
        )


def test_materialization_is_immutable_idempotent_deterministic_and_loadable(
    private_inputs: tuple[Path, Path, Path, dict[str, object]]
) -> None:
    receipt = _materialize(private_inputs)
    target = Path(receipt.output_directory)
    expected = {
        "diversified.yaml",
        "private-instrument-map.json",
        "portfolio-selection-receipt.json",
        "evidence-manifest.json",
    }
    assert {item.name for item in target.iterdir()} == expected
    assert receipt.effects == ()
    assert target.stat().st_mode & 0o777 == 0o700
    assert all(item.stat().st_mode & 0o777 == 0o600 for item in target.iterdir())
    first_receipt = (target / "portfolio-selection-receipt.json").read_bytes()

    repeated = _materialize(private_inputs)
    assert repeated == receipt
    assert (target / "portfolio-selection-receipt.json").read_bytes() == first_receipt
    assert validate_materialized_real_portfolios(
        portfolios_directory=target,
        receipt_path=target / "portfolio-selection-receipt.json",
    ) == receipt

    definition = load_portfolio(target / "diversified.yaml")
    assert len(definition.positions) == 5
    assert definition.benchmark_id is None
    assert definition.benchmark_unavailable is True
    yaml_text = (target / "diversified.yaml").read_text(encoding="utf-8").casefold()
    assert all(
        forbidden not in yaml_text
        for forbidden in ("permno", "gvkey", "candidate_id", "ticker")
    )


def test_materialization_does_not_chmod_a_preexisting_output_root(
    private_inputs: tuple[Path, Path, Path, dict[str, object]]
) -> None:
    _, _, output, _ = private_inputs
    output.mkdir()
    output.chmod(0o750)
    _materialize(private_inputs)
    assert output.stat().st_mode & 0o777 == 0o750


def test_changed_reviewed_selection_uses_a_new_selection_identity(
    private_inputs: tuple[Path, Path, Path, dict[str, object]]
) -> None:
    first = _materialize(private_inputs)
    artifact, _, output, original = private_inputs
    changed = deepcopy(original)
    changed["selection_id"] = "reviewed-selection-002"
    changed["portfolios"][0]["positions"][0]["quantity"] = "99"
    selection_path = _write_selection(
        artifact.parent.parent / "reviewed-selection-002.yaml", changed
    )
    second = materialize_real_portfolios(
        candidate_artifact_path=artifact,
        selection_path=selection_path,
        output_directory=output,
    )
    assert second.selection_id != first.selection_id
    assert second.selection_digest != first.selection_digest
    assert second.receipt_id != first.receipt_id
    assert Path(second.output_directory).is_dir()
    assert Path(first.output_directory).is_dir()


def test_existing_changed_output_is_rejected(
    private_inputs: tuple[Path, Path, Path, dict[str, object]]
) -> None:
    receipt = _materialize(private_inputs)
    target = Path(receipt.output_directory)
    (target / "diversified.yaml").write_text("changed: true\n", encoding="utf-8")
    with pytest.raises(PortfolioMaterializationError, match="immutable"):
        _materialize(private_inputs)
    with pytest.raises(
        PortfolioMaterializationError, match="definition digest mismatch"
    ):
        validate_materialized_real_portfolios(
            portfolios_directory=target,
            receipt_path=target / "portfolio-selection-receipt.json",
        )


def test_edited_candidate_body_cannot_retain_a_stale_artifact_identity(
    private_inputs: tuple[Path, Path, Path, dict[str, object]]
) -> None:
    artifact_path, _, output, original = private_inputs
    artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
    artifact["candidates"][0]["observation_count"] += 1
    artifact_path.write_text(
        json.dumps(artifact, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    changed = deepcopy(original)
    changed["candidate_artifact"]["sha256"] = sha256_file(artifact_path)
    selection_path = _write_selection(
        artifact_path.parent.parent / "stale-artifact-identity.yaml",
        changed,
    )
    with pytest.raises(
        PortfolioMaterializationError, match="artifact identity mismatch"
    ):
        materialize_real_portfolios(
            candidate_artifact_path=artifact_path,
            selection_path=selection_path,
            output_directory=output,
        )


@pytest.mark.parametrize(
    ("field", "replacement"),
    [
        ("manifest_version", "9.9"),
        ("publication_state", "public"),
        ("limitations", []),
    ],
)
def test_evidence_manifest_requires_every_canonical_field(
    private_inputs: tuple[Path, Path, Path, dict[str, object]],
    field: str,
    replacement: object,
) -> None:
    receipt = _materialize(private_inputs)
    target = Path(receipt.output_directory)
    evidence_path = target / "evidence-manifest.json"
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    evidence[field] = replacement
    evidence_path.write_text(
        json.dumps(evidence, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    with pytest.raises(
        PortfolioMaterializationError, match="evidence manifest mismatch"
    ):
        validate_materialized_real_portfolios(
            portfolios_directory=target,
            receipt_path=target / "portfolio-selection-receipt.json",
        )


def test_repository_output_and_unconfigured_private_root_are_rejected(
    private_inputs: tuple[Path, Path, Path, dict[str, object]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    artifact, selection, _, _ = private_inputs
    monkeypatch.setenv("THESIS_DATA_ROOT", str(artifact.parent.parent))
    with pytest.raises(PortfolioMaterializationError, match="outside Git"):
        materialize_real_portfolios(
            candidate_artifact_path=artifact,
            selection_path=selection,
            output_directory=Path(__file__).resolve().parents[2] / "generated",
        )
    monkeypatch.delenv("THESIS_DATA_ROOT")
    with pytest.raises(PortfolioMaterializationError, match="must be configured"):
        materialize_real_portfolios(
            candidate_artifact_path=artifact,
            selection_path=selection,
            output_directory=artifact.parent.parent / "outputs",
        )


def test_no_automatic_candidate_selection_network_or_effect_surface() -> None:
    public_names = {
        name
        for name, value in inspect.getmembers(materialization, inspect.isfunction)
        if not name.startswith("_")
    }
    assert "select_candidates" not in public_names
    assert "choose_candidates" not in public_names
    assert "rank_candidates" not in public_names
    source = inspect.getsource(materialization)
    for forbidden in (
        "requests.",
        "urllib.",
        "socket.",
        "httpx.",
        "subprocess.",
        "place_order",
        "rebalance(",
    ):
        assert forbidden not in source


def test_placeholder_selection_has_no_real_or_recommended_values(
    example_root: Path,
) -> None:
    path = (
        example_root
        / "selections"
        / "real_portfolio_selection.synthetic-placeholder.example.yaml"
    )
    text = path.read_text(encoding="utf-8")
    assert "reviewed: false" in text
    assert "REPLACE_WITH_HUMAN_REVIEWED_POSITIVE_INTEGER" in text
    assert "SYNTHETIC PLACEHOLDER ONLY" in text
    assert "PERMNO" not in text and "GVKEY" not in text


def test_day1_portfolio_files_are_byte_for_byte_unchanged(example_root: Path) -> None:
    expected = {
        "defensive_multi_asset.yaml": "a2e02245f43c9233a87d0877da15f942c85f81cd38b00384d1c5394d3e81f5f8",
        "diversified.yaml": "af218b1573c16b1b7b25b33789970e3775fcf87dd430f4bc4b99e9927b33b2aa",
        "technology_concentrated.yaml": "60b092f75b83b6d06eab71c27e3f354fa77c74a0c57d37953051818a8d4a91a9",
    }
    assert {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted((example_root / "portfolios").glob("*.yaml"))
    } == expected
