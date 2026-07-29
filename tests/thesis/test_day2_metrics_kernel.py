from __future__ import annotations

import ast
import hashlib
import json
import socket
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import duckdb
import pytest
import yaml
from pydantic import ValidationError

from portfolio_risk_thesis.contracts import (
    DataReadiness,
    Day2ExperimentManifest,
    MetricValue,
    MorningMetricPack,
    PortfolioMaterializationReceipt,
)
from portfolio_risk_thesis.day2 import (
    Day2ExperimentError,
    _portfolio_prices,
    deterministic_decision,
    run_day2_experiment,
)
from portfolio_risk_thesis.manifests import sha256_file


AS_OF = datetime(2026, 7, 28, 23, 59, 59, tzinfo=UTC)
ROOT = Path(__file__).resolve().parents[2]


def _digest(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode()).hexdigest()


def _manifest(tmp_path: Path) -> Day2ExperimentManifest:
    source = tmp_path / "source.yaml"
    source.write_text("reviewed: true\n", encoding="utf-8")
    portfolios = tmp_path / "portfolio-definitions"
    portfolios.mkdir(exist_ok=True)
    return Day2ExperimentManifest(
        experiment_id="portfolio-risk-architecture-comparison-v1-day2",
        reviewed=True,
        reviewer_id="thesis-reviewer",
        reviewed_at=datetime(2026, 7, 28, 12, tzinfo=UTC),
        as_of=AS_OF,
        dataset_mode="daily_primary",
        source_manifest={"path": source, "sha256": sha256_file(source)},
        data_root=tmp_path,
        dataset_snapshot_id="snapshot-1",
        dataset_receipt_sha256=_digest("dataset"),
        portfolios_directory=portfolios,
        portfolio_receipt_sha256=_digest("portfolio"),
        thresholds={
            "review_daily_loss": "0.03",
            "urgent_daily_loss": "0.07",
            "review_annualized_volatility": "0.30",
            "urgent_annualized_volatility": "0.50",
            "review_maximum_drawdown": "0.15",
            "urgent_maximum_drawdown": "0.25",
        },
    )


def _pack(
    tmp_path: Path,
    *,
    daily_return: str | None = "0.01",
    volatility: str | None = "0.10",
    drawdown: str | None = "0.05",
    readiness: str = "READY",
) -> MorningMetricPack:
    values = {
        "daily_return": daily_return,
        "annualized_volatility": volatility,
        "maximum_drawdown": drawdown,
        "historical_var_95": "0.02",
        "historical_expected_shortfall_95": "0.03",
    }
    metrics = tuple(
        MetricValue(
            metric_id=metric_id,
            value=value,
            unit="ratio",
            observation_count=60,
            warning="undefined_metric" if value is None else None,
        )
        for metric_id, value in values.items()
    )
    warnings = ("insufficient_data",) if readiness == "BLOCKED" else ()
    return MorningMetricPack(
        metric_pack_id="metric_pack_" + "1" * 24,
        experiment_id="experiment-1",
        portfolio_id="diversified",
        source_snapshot_id="snapshot-1",
        portfolio_receipt_id="portfolio-receipt-1",
        as_of=AS_OF,
        readiness=DataReadiness(
            state=readiness,
            observation_count=0 if readiness == "BLOCKED" else 60,
            required_observation_count=60,
            warnings=warnings,
            limitations=("Research evidence only.",),
        ),
        metrics=metrics,
        evidence=(_digest("evidence"),),
        assumptions=("Fixed quantities.",),
        warnings=warnings,
        limitations=("Research evidence only.",),
        output_digest=_digest("metric-pack"),
    )


@pytest.mark.parametrize(
    ("pack_kwargs", "expected"),
    (
        ({}, "NO_ISSUE"),
        ({"daily_return": "-0.04"}, "REVIEW"),
        ({"volatility": "0.55"}, "URGENT_REVIEW"),
        ({"daily_return": None, "readiness": "BLOCKED"}, "ABSTAIN"),
    ),
)
def test_kernel_outcomes_are_deterministic_and_effect_free(
    tmp_path: Path, pack_kwargs: dict[str, str | None], expected: str
) -> None:
    pack = _pack(tmp_path, **pack_kwargs)
    first = deterministic_decision(pack, _manifest(tmp_path))
    second = deterministic_decision(pack, _manifest(tmp_path))
    assert first == second
    finding, review, decision = first
    assert finding.outcome == expected
    assert review.human_review_required
    assert decision.decision == expected
    assert decision.effects == ()


def _portfolio_document() -> dict[str, object]:
    return {
        "portfolio_id": "diversified",
        "title": "Reviewed test portfolio",
        "base_currency": "USD",
        "start_date": "2026-01-01",
        "positions": [
            {"instrument_id": f"real-diversified-{number:02}", "quantity": "10"}
            for number in range(1, 6)
        ],
        "cash": [{"currency": "USD", "amount": "1000"}],
        "benchmark_unavailable": True,
    }


def _receipt(tmp_path: Path) -> PortfolioMaterializationReceipt:
    portfolios = tmp_path / "portfolio-definitions"
    return PortfolioMaterializationReceipt(
        receipt_id="portfolio_receipt_" + "1" * 24,
        selection_id="selection-1",
        selection_digest=_digest("selection"),
        reviewer_id="reviewer",
        reviewed_at=datetime(2026, 7, 28, 12, tzinfo=UTC),
        effective_at=datetime(2026, 7, 28, 13, tzinfo=UTC),
        candidate_artifact={
            "path": tmp_path / "candidate.json",
            "sha256": _digest("candidate"),
            "artifact_id": "candidate-1",
        },
        source_snapshot_id="snapshot-1",
        as_of=datetime(2026, 7, 28, 11, tzinfo=UTC),
        rationale="Reviewed test rationale.",
        warnings=("Private test evidence.",),
        output_directory=portfolios,
        portfolio_definition_digests={"diversified.yaml": _digest("definition")},
        private_instrument_map_digest=_digest("map"),
        portfolio_count=1,
        limitations=("No effects.",),
    )


def _private_runtime(tmp_path: Path) -> tuple[Path, Path]:
    portfolios = tmp_path / "portfolio-definitions"
    portfolios.mkdir(exist_ok=True)
    (portfolios / "diversified.yaml").write_text(
        yaml.safe_dump(_portfolio_document(), sort_keys=False), encoding="utf-8"
    )
    (portfolios / "private-instrument-map.json").write_text(
        json.dumps(
            {
                "instruments": [
                    {
                        "instrument_alias": f"real-diversified-{number:02}",
                        "permno": 10000 + number,
                    }
                    for number in range(1, 6)
                ]
            }
        ),
        encoding="utf-8",
    )
    catalogue = tmp_path / "catalogue.duckdb"
    with duckdb.connect(str(catalogue)) as connection:
        connection.execute(
            "CREATE TABLE crsp_daily "
            "(permno BIGINT, observed_at TIMESTAMPTZ, "
            "available_at TIMESTAMPTZ, valuation_price DECIMAL(38,12))"
        )
        rows = []
        start = AS_OF - timedelta(days=90)
        for ordinal in range(61):
            observed = start + timedelta(days=ordinal)
            for number in range(1, 6):
                rows.append(
                    (
                        10000 + number,
                        observed,
                        observed + timedelta(hours=12),
                        Decimal("100") + Decimal(ordinal) + Decimal(number),
                    )
                )
        connection.executemany(
            "INSERT INTO crsp_daily VALUES (?, ?, ?, ?)", rows
        )
    return portfolios, catalogue


def test_real_runner_is_immutable_idempotent_private_and_has_no_network(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("THESIS_DATA_ROOT", str(tmp_path))
    manifest = _manifest(tmp_path)
    portfolios, catalogue = _private_runtime(tmp_path)
    manifest = manifest.model_copy(update={"portfolios_directory": portfolios})
    receipt = _receipt(tmp_path)
    monkeypatch.setattr(
        "portfolio_risk_thesis.day2.validate_day2_experiment",
        lambda _: (manifest, receipt, catalogue),
    )
    monkeypatch.setattr(
        socket,
        "create_connection",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("network is prohibited")
        ),
    )
    output_root = tmp_path / "results"
    first = run_day2_experiment(
        experiment_manifest_path=tmp_path / "experiment.yaml",
        output_root=output_root,
    )
    second = run_day2_experiment(
        experiment_manifest_path=tmp_path / "experiment.yaml",
        output_root=output_root,
    )
    assert first == second
    assert {item.name for item in first.iterdir()} == {
        "morning-metric-packs.json",
        "deterministic-findings.json",
        "kernel-decisions.json",
        "evidence-manifest.json",
    }
    decisions = json.loads((first / "kernel-decisions.json").read_text())
    assert all(item["effects"] == [] for item in decisions)
    assert "permno" not in (first / "morning-metric-packs.json").read_text().lower()


def test_daily_price_gate_fails_for_short_history_and_missing_latest_price(
    tmp_path: Path,
) -> None:
    portfolio = type(
        "Portfolio",
        (),
        {
            "portfolio_id": "test",
            "positions": tuple(
                type(
                    "Position",
                    (),
                    {
                        "instrument_id": f"alias-{number}",
                        "quantity": Decimal("1"),
                    },
                )()
                for number in range(5)
            ),
            "cash": (),
        },
    )()
    bindings = {f"alias-{number}": 10000 + number for number in range(5)}
    with duckdb.connect(":memory:") as connection:
        connection.execute(
            "CREATE TABLE crsp_daily "
            "(permno BIGINT, observed_at TIMESTAMPTZ, "
            "available_at TIMESTAMPTZ, valuation_price DECIMAL(38,12))"
        )
        for ordinal in range(10):
            observed = AS_OF - timedelta(days=10 - ordinal)
            connection.executemany(
                "INSERT INTO crsp_daily VALUES (?, ?, ?, ?)",
                [
                    (permno, observed, observed + timedelta(hours=1), Decimal("10"))
                    for permno in bindings.values()
                ],
            )
        with pytest.raises(Day2ExperimentError, match="fewer than 60"):
            _portfolio_prices(
                connection,
                portfolio=portfolio,
                bindings=bindings,
                as_of=AS_OF,
                required_returns=60,
            )
        connection.execute(
            "INSERT INTO crsp_daily VALUES (?, ?, ?, NULL)",
            [10000, AS_OF - timedelta(minutes=2), AS_OF - timedelta(minutes=1)],
        )
        with pytest.raises(Day2ExperimentError, match="prices are unavailable"):
            _portfolio_prices(
                connection,
                portfolio=portfolio,
                bindings=bindings,
                as_of=AS_OF,
                required_returns=60,
            )


def test_no_agent_llm_provider_or_effect_path_exists() -> None:
    source = (
        ROOT
        / "examples"
        / "portfolio-risk-thesis"
        / "src"
        / "portfolio_risk_thesis"
        / "day2.py"
    ).read_text(encoding="utf-8")
    tree = ast.parse(source)
    names = {
        node.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    assert not any(
        token in name.casefold()
        for name in names
        for token in ("agent", "llm", "provider", "order", "trade", "rebalance")
    )


def test_manifest_rejects_unreviewed_monthly_and_non_frozen_confidence(
    tmp_path: Path,
) -> None:
    value = _manifest(tmp_path).model_dump(mode="python")
    for replacement, message in (
        ({"reviewed": False}, "literal_error"),
        ({"dataset_mode": "monthly_smoke"}, "literal_error"),
        ({"confidence_level": Decimal("0.90")}, "frozen Day 2"),
    ):
        with pytest.raises(ValidationError, match=message):
            Day2ExperimentManifest.model_validate(value | replacement)


def test_public_day2_example_contains_only_placeholders() -> None:
    path = (
        ROOT
        / "examples"
        / "portfolio-risk-thesis"
        / "experiments"
        / "day2_real.example.yaml"
    )
    text = path.read_text(encoding="utf-8")
    assert "EXAMPLE ONLY" in text
    assert "/absolute/external/" in text
    assert not any(
        token in text.casefold()
        for token in ("permno", "gvkey", "ticker:", "company_name:")
    )
    schema = json.loads(
        (
            ROOT
            / "data"
            / "schemas"
            / "thesis-real-data"
            / "day2-experiment-v1.schema.json"
        ).read_text(encoding="utf-8")
    )
    assert schema["properties"]["dataset_mode"]["const"] == "daily_primary"
    assert schema["properties"]["reviewed"]["const"] is True
    assert schema["properties"]["effects"]["maxItems"] == 0
