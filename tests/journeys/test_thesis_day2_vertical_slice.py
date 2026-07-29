from __future__ import annotations

import hashlib
import json
import socket
from datetime import UTC, datetime
from pathlib import Path

import pytest

from portfolio_risk_thesis.contracts import (
    DataReadiness,
    Day2ExperimentManifest,
    MetricValue,
    MorningMetricPack,
)
from portfolio_risk_thesis.day2 import deterministic_decision
from scripts.thesis.run_day1_demo import run_day1_demo


AS_OF = datetime(2026, 7, 28, 23, 59, 59, tzinfo=UTC)


def _digest(value: str) -> str:
    return "sha256:" + hashlib.sha256(value.encode()).hexdigest()


def _manifest(tmp_path: Path) -> Day2ExperimentManifest:
    source = tmp_path / "source-manifest.yaml"
    source.write_text("reviewed: true\n", encoding="utf-8")
    portfolios = tmp_path / "portfolio-definitions"
    portfolios.mkdir()
    return Day2ExperimentManifest(
        experiment_id="portfolio-risk-architecture-comparison-v1-day2",
        reviewed=True,
        reviewer_id="synthetic-journey-reviewer",
        reviewed_at=datetime(2026, 7, 28, 12, tzinfo=UTC),
        as_of=AS_OF,
        dataset_mode="daily_primary",
        source_manifest={"path": source, "sha256": _digest("source")},
        data_root=tmp_path,
        dataset_snapshot_id="synthetic-day2-snapshot",
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
    *,
    portfolio_id: str,
    readiness: str,
    daily_return: str | None,
    volatility: str | None,
    drawdown: str | None,
) -> MorningMetricPack:
    warnings = (
        ()
        if readiness == "READY"
        else (
            ("event_source_not_configured",)
            if readiness == "QUALIFIED"
            else ("undefined_metric", "event_source_not_configured")
        )
    )
    values = {
        "daily_return": daily_return,
        "annualized_volatility": volatility,
        "maximum_drawdown": drawdown,
        "historical_var_95": "0.02",
        "historical_expected_shortfall_95": "0.03",
    }
    return MorningMetricPack(
        metric_pack_id="metric_pack_" + hashlib.sha256(
            portfolio_id.encode()
        ).hexdigest()[:24],
        experiment_id="portfolio-risk-architecture-comparison-v1-day2",
        portfolio_id=portfolio_id,
        source_snapshot_id="synthetic-day2-snapshot",
        portfolio_receipt_id="synthetic-portfolio-receipt",
        as_of=AS_OF,
        readiness=DataReadiness(
            state=readiness,
            observation_count=0 if readiness == "BLOCKED" else 60,
            required_observation_count=60,
            warnings=warnings,
            limitations=("Synthetic research evidence only.",),
        ),
        metrics=tuple(
            MetricValue(
                metric_id=metric_id,
                value=value,
                unit="ratio",
                observation_count=0 if value is None else 60,
                warning="undefined_metric" if value is None else None,
            )
            for metric_id, value in values.items()
        ),
        evidence=(_digest(f"evidence:{portfolio_id}"),),
        assumptions=("Portfolio quantities remain fixed.",),
        warnings=warnings,
        limitations=(
            "Synthetic research evidence only.",
            "No LLM, provider call, order, trade, rebalance, or portfolio mutation.",
        ),
        effects=(),
        output_digest=_digest(f"metric-pack:{portfolio_id}"),
    )


def test_day2_public_vertical_slice_is_deterministic_and_effect_free(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        socket,
        "create_connection",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("network and provider calls are prohibited")
        ),
    )
    replay_root = tmp_path / "day1-replay"
    monkeypatch.setenv("THESIS_DATA_ROOT", str(replay_root))
    replay_output = run_day1_demo(replay_root)
    replay = json.loads(
        (replay_output / "run-manifest.json").read_text(encoding="utf-8")
    )
    assert replay["synthetic"] is True
    assert replay["number_of_replay_steps"] == 15
    assert replay["effects"] == []

    manifest = _manifest(tmp_path)
    cases = (
        (_pack(
            portfolio_id="ready-no-issue",
            readiness="READY",
            daily_return="0.01",
            volatility="0.10",
            drawdown="0.05",
        ), "NO_ISSUE", "none"),
        (_pack(
            portfolio_id="qualified-review",
            readiness="QUALIFIED",
            daily_return="-0.04",
            volatility="0.20",
            drawdown="0.10",
        ), "REVIEW", "review"),
        (_pack(
            portfolio_id="ready-urgent",
            readiness="READY",
            daily_return="-0.08",
            volatility="0.20",
            drawdown="0.10",
        ), "URGENT_REVIEW", "urgent"),
        (_pack(
            portfolio_id="blocked-abstain",
            readiness="BLOCKED",
            daily_return=None,
            volatility="0.20",
            drawdown="0.10",
        ), "ABSTAIN", "undefined"),
    )

    observed_states = set()
    observed_outcomes = set()
    for pack, expected_outcome, expected_materiality in cases:
        first = deterministic_decision(pack, manifest)
        second = deterministic_decision(pack, manifest)
        assert first == second
        finding, review_item, decision = first
        observed_states.add(pack.readiness.state)
        observed_outcomes.add(finding.outcome)
        assert finding.outcome == expected_outcome
        assert finding.materiality == expected_materiality
        assert review_item.finding_id == finding.finding_id
        assert review_item.human_review_required is True
        assert decision.finding_id == finding.finding_id
        assert decision.review_item_id == review_item.review_item_id
        assert decision.deterministic is True
        assert decision.human_review_required is True
        assert pack.effects == decision.effects == ()

    assert observed_states == {"READY", "QUALIFIED", "BLOCKED"}
    assert observed_outcomes == {
        "NO_ISSUE",
        "REVIEW",
        "URGENT_REVIEW",
        "ABSTAIN",
    }
    assert manifest.event_source == "not_configured"
    assert "event_source_not_configured" in cases[1][0].warnings
    blocked_metric = next(
        metric
        for metric in cases[3][0].metrics
        if metric.metric_id == "daily_return"
    )
    assert blocked_metric.value is None
    assert blocked_metric.warning == "undefined_metric"
