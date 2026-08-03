from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from portfolio_risk_thesis.contracts import (
    DataReadiness,
    DeterministicFinding,
    KernelDecisionPoint,
    MetricValue,
    MorningMetricPack,
    ReviewItem,
)
from portfolio_risk_thesis.day3.contracts import (
    ArchitectureInputBundle,
    EligibleAgentEvent,
    PositionExposure,
    bytes_digest,
    digest,
)
from portfolio_risk_thesis.day3.prompts import prompt_reference
from portfolio_risk_thesis.day3.treatments import ROLES

AS_OF = datetime(2024, 1, 3, 23, 59, 59, tzinfo=UTC)
EVIDENCE = "synthetic-evidence"


def bundle(
    *,
    deterministic_finding: str = "REVIEW",
    decision_point: str = "REVIEW",
    event_title: str = "Quoted event text.",
) -> ArchitectureInputBundle:
    event_evidence = digest("event-1")
    return ArchitectureInputBundle(
        portfolio_id="synthetic-diversified",
        as_of=AS_OF,
        metrics={
            "daily_return": Decimal("-0.04"),
            "annualized_volatility": Decimal("0.20"),
            "maximum_drawdown": Decimal("0.10"),
            "historical_var_95": Decimal("0.02"),
            "historical_expected_shortfall_95": Decimal("0.03"),
        },
        deterministic_finding=deterministic_finding,
        review_item="Review deterministic threshold evidence.",
        decision_point=decision_point,
        exposures=(
            PositionExposure(
                position_alias="position-001",
                weight=Decimal("0.60"),
                evidence_refs=(EVIDENCE,),
            ),
            PositionExposure(
                position_alias="position-002",
                weight=Decimal("0.40"),
                evidence_refs=(EVIDENCE,),
            ),
        ),
        events=(
            EligibleAgentEvent(
                event_id="event-001",
                event_time=datetime(2024, 1, 2, 12, tzinfo=UTC),
                available_at=datetime(2024, 1, 2, 13, tzinfo=UTC),
                entity_alias="entity-001",
                instrument_aliases=("position-001",),
                title=event_title,
                short_summary="Untrusted quoted event data.",
                sentiment="neutral",
                relevance=Decimal("0.5"),
                source_reference="synthetic-reference",
                evidence_digest=event_evidence,
                profile="synthetic_curated",
                publication_state="reviewed",
                limitations=("Synthetic fixture only.",),
            ),
        ),
        evidence_refs=(EVIDENCE,),
        warnings=("event_source_curated",),
        limitations=("Synthetic fixture only.",),
    )


def output(architecture: str, **updates: object) -> dict[str, object]:
    value: dict[str, object] = {
        "architecture_id": architecture,
        "status": "REVIEW",
        "severity": 1,
        "summary": "Fixture review output.",
        "human_review_required": True,
        "effects": [],
    }
    value.update(updates)
    return value


def fixture_responses(
    context: ArchitectureInputBundle,
    *,
    b1_output: dict[str, object] | None = None,
    a1_output: dict[str, object] | None = None,
) -> dict[tuple[str, str, str, str], dict[str, object]]:
    prompt_ids = {
        ROLES[0]: "a1-market-data",
        ROLES[1]: "a1-portfolio-exposure",
        ROLES[2]: "a1-news-sentiment",
        ROLES[3]: "a1-alert-synthesis",
    }
    responses = {
        (
            "B1",
            ROLES[-1],
            prompt_reference("b1-synthesizer").digest,
            context.context_digest,
        ): b1_output or output("B1")
    }
    responses.update(
        {
            (
                "A1",
                role,
                prompt_reference(prompt_ids[role]).digest,
                context.context_digest,
            ): a1_output or output("A1")
            for role in ROLES
        }
    )
    return responses


def model_configuration(provider_id: str = "fixture") -> dict[str, object]:
    fixture = provider_id == "fixture"
    model = "fixture-structured-v1" if fixture else "gpt-4.1-mini-2025-04-14"
    from portfolio_risk_thesis.day3.prompts import prompt_manifest_digest

    return {
        "provider_id": provider_id,
        "model_id": model,
        "model_snapshot": model,
        "prompt_manifest_digest": prompt_manifest_digest(),
        "temperature": None if fixture else "0",
        "temperature_supported": not fixture,
        "maximum_output_tokens": 1600,
        "timeout_seconds": 30 if fixture else 90,
        "retry_count": 0 if fixture else 1,
        "store": False,
        "tools": [],
        "response_schema_version": "v1",
    }


def write_day2_run(root: Path) -> Path:
    run = root / "day2_fixture"
    run.mkdir()
    evidence = "portfolio-receipt:" + digest("portfolio")
    metrics = tuple(
        MetricValue(
            metric_id=metric_id,
            value=value,
            unit="ratio",
            observation_count=60,
            warning=None,
        )
        for metric_id, value in {
            "daily_return": "-0.04",
            "annualized_volatility": "0.20",
            "maximum_drawdown": "0.10",
            "historical_var_95": "0.02",
            "historical_expected_shortfall_95": "0.03",
        }.items()
    )
    pack = MorningMetricPack(
        metric_pack_id="metric_pack_" + "1" * 24,
        experiment_id="experiment-1",
        portfolio_id="synthetic-diversified",
        source_snapshot_id="snapshot-1",
        portfolio_receipt_id="portfolio-receipt-1",
        as_of=AS_OF,
        readiness=DataReadiness(
            state="READY",
            observation_count=60,
            required_observation_count=60,
            warnings=(),
            limitations=("Synthetic fixture only.",),
        ),
        metrics=metrics,
        evidence=(evidence,),
        assumptions=("Fixed quantities.",),
        warnings=(),
        limitations=("Synthetic fixture only.",),
        output_digest=digest("metric-pack"),
    )
    finding = DeterministicFinding(
        finding_id="finding_" + "2" * 24,
        portfolio_id="synthetic-diversified",
        outcome="REVIEW",
        materiality="review",
        triggered_metrics=("daily_return",),
        evidence=(evidence,),
        warnings=(),
    )
    review = ReviewItem(
        review_item_id="review_item_" + "3" * 24,
        portfolio_id="synthetic-diversified",
        priority="review",
        summary="Review deterministic threshold evidence.",
        finding_id=finding.finding_id,
    )
    decision = KernelDecisionPoint(
        decision_id="kernel_decision_" + "4" * 24,
        portfolio_id="synthetic-diversified",
        decision="REVIEW",
        finding_id=finding.finding_id,
        review_item_id=review.review_item_id,
        deterministic=True,
        human_review_required=True,
        effects=(),
    )
    documents = {
        "morning-metric-packs.json": [pack.model_dump(mode="json")],
        "deterministic-findings.json": {
            "findings": [finding.model_dump(mode="json")],
            "review_items": [review.model_dump(mode="json")],
        },
        "kernel-decisions.json": [decision.model_dump(mode="json")],
    }
    for name, document in documents.items():
        (run / name).write_text(
            json.dumps(document, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    manifest = {
        "artifacts": {
            name: bytes_digest((run / name).read_bytes())
            for name in documents
        },
        "effects": [],
        "experiment_id": "portfolio-risk-architecture-comparison-v1-day2",
        "limitations": ["Synthetic fixture only."],
        "portfolio_receipt_id": "portfolio-receipt-1",
        "run_id": "day2_fixture",
        "source_snapshot_id": "snapshot-1",
    }
    (run / "evidence-manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return run
