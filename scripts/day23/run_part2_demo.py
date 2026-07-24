#!/usr/bin/env python3
"""Run the deterministic, local-only Day 2–3 Part 2 monitoring journey."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import socket
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any, Iterator
from unittest.mock import patch

from pydantic import ValidationError
from risk_agents import (
    ACTIVE_AGENT_ROLE_IDS,
    DeterministicContextualMonitoringOrchestrator,
)
from risk_analytics import MonitoringReportRequest
from risk_capabilities import (
    CAPABILITY_BY_ID,
    CapabilityRegistry,
    ContextualMonitoringWorkflowRequest,
    EvidenceReference,
    MonitoringReportCapabilityRequest,
    PortfolioDataContextCapabilityRequest,
    ReplayCapabilityRequest,
    ReplayEvaluationCapabilityRequest,
    ReplayStepInput,
)
from risk_data import (
    CrosswalkSnapshot,
    EventDataPlane,
    EventProviderProfile,
    EventQueryRequest,
    FixedQueryRequest,
    PublicationRestriction,
    ResearchDataPlane,
    date_effective_mappings_from_crosswalk,
)
from risk_data.pipeline import resolve_data_root
from risk_domain import PortfolioSnapshot, Position
from risk_domain.monitoring import (
    MonitoringEvidence,
    MonitoringMetric,
    MonitoringPolicyVersion,
    OutcomeLabel,
    PointInTimeObservation,
    PortfolioDataContextRequest,
    ReplaySpecification,
)
from scripts.day23.run_phase1_demo import execute_phase1_journey


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_ROOT = REPOSITORY_ROOT / "data" / "fixtures" / "synthetic" / "day23"
OUTPUT_DIRECTORY_NAME = "day23-part2"
STATE_DIRECTORY_NAME = "day23-part2-state"
PORTFOLIO_AS_OF = datetime(2026, 6, 29, 21, tzinfo=UTC)
MONITORING_TIME = datetime(2026, 6, 30, 21, tzinfo=UTC)
REPLAY_END = datetime(2026, 7, 1, 21, tzinfo=UTC)
EVALUATED_AT = datetime(2026, 7, 3, 21, tzinfo=UTC)
EVENT_RETRIEVED_AT = datetime(2026, 7, 22, 10, 0, tzinfo=UTC)
MARKET_DATASET_ID = "synthetic-crsp-like-daily"
FUNDAMENTAL_DATASET_ID = "synthetic-compustat-like-annual"
MARKET_ENTITY_ID = "security-permno-910001"
PORTFOLIO_INSTRUMENT_ID = "security-permno-910001"
ARTIFACT_NAMES = (
    "data-context.json",
    "event-import-preview.json",
    "event-snapshot.json",
    "monitoring-policy.json",
    "monitoring-run.json",
    "findings.json",
    "alert-draft.json",
    "agent-timeline.json",
    "replay-specification.json",
    "replay-runs.json",
    "monitoring-evaluation.json",
    "monitoring-report.md",
    "monitoring-report.html",
)
PROHIBITED_EFFECTS = (
    "provider_call",
    "external_llm_call",
    "broker_connectivity",
    "order_submission",
    "trade_execution",
    "automatic_rebalancing",
    "optimization",
)


def _encoded(value: object) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _write_stable(path: Path, content: bytes) -> Path:
    if path.exists():
        if path.read_bytes() != content:
            raise FileExistsError(
                f"immutable Part 2 artifact differs from existing evidence: {path}"
            )
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path


def _portable(value: object, output_directory: Path) -> object:
    if hasattr(value, "model_dump"):
        return _portable(value.model_dump(mode="json"), output_directory)  # type: ignore[union-attr]
    if isinstance(value, dict):
        return {
            str(key): _portable(item, output_directory)
            for key, item in value.items()
        }
    if isinstance(value, (tuple, list)):
        return [_portable(item, output_directory) for item in value]
    if isinstance(value, Path):
        value = str(value)
    if isinstance(value, str):
        candidate = Path(value)
        if candidate.is_absolute():
            try:
                return "fixture://day23/" + candidate.relative_to(
                    FIXTURE_ROOT
                ).as_posix()
            except ValueError:
                try:
                    return candidate.relative_to(output_directory).as_posix()
                except ValueError:
                    return value
    return value


def _timestamp(value: object) -> datetime:
    text = str(value)
    parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


@contextmanager
def _network_blocked() -> Iterator[dict[str, int]]:
    proof = {"attempts": 0}

    def reject(*_args: object, **_kwargs: object) -> None:
        proof["attempts"] += 1
        raise RuntimeError("network access is prohibited in the Part 2 journey")

    with (
        patch("socket.create_connection", reject),
        patch.object(socket.socket, "connect", reject),
        patch("urllib.request.urlopen", reject),
    ):
        yield proof


def _evidence(
    latest_snapshot: dict[str, object],
    event_source_digest: str,
) -> tuple[tuple[MonitoringEvidence, ...], tuple[EvidenceReference, ...]]:
    revisions = {
        str(item["dataset_id"]): item
        for item in latest_snapshot["dataset_revisions"]  # type: ignore[index]
    }
    sources = (
        (
            "part1-market",
            "fixture://day23/crsp_like_daily.csv",
            str(revisions[MARKET_DATASET_ID]["source_digest"]),
            "Completed Part 1 synthetic market revision.",
        ),
        (
            "part1-fundamental",
            "fixture://day23/compustat_like_annual.csv",
            str(revisions[FUNDAMENTAL_DATASET_ID]["source_digest"]),
            "Completed Part 1 synthetic fundamental revision.",
        ),
        (
            "part1-crosswalk",
            "fixture://day23/crsp_compustat_link.csv",
            str(revisions["synthetic-crsp-compustat-link"]["source_digest"]),
            "Completed Part 1 exact date-effective crosswalk revision.",
        ),
        (
            "part2-events",
            "fixture://day23/ravenpack-like-events.csv",
            event_source_digest,
            "Reviewed fictional local event export.",
        ),
    )
    domain = tuple(
        MonitoringEvidence(
            evidence_id=evidence_id,
            reference=reference,
            digest=digest,
            description=description,
        )
        for evidence_id, reference, digest, description in sources
    )
    capability = tuple(
        EvidenceReference(
            evidence_id=item.evidence_id,
            reference=item.reference,
            source_type="synthetic_fixture",
            digest=item.digest,
        )
        for item in domain
    )
    return domain, capability


def _observations(
    rows: list[dict[str, object]],
    *,
    snapshot_id: str,
    revision: str,
    retrieved_at: datetime,
    fields: tuple[tuple[str, str, str | None], ...],
    evidence: tuple[MonitoringEvidence, ...],
) -> tuple[PointInTimeObservation, ...]:
    values: list[PointInTimeObservation] = []
    for row in rows:
        quality_flags = tuple(json.loads(str(row.get("quality_flags") or "[]")))
        for source_field, field_name, unit in fields:
            value = row.get(source_field)
            if value is None:
                continue
            values.append(
                PointInTimeObservation(
                    dataset_snapshot_id=snapshot_id,
                    dataset_revision=revision,
                    entity_id=str(row["entity_id"]),
                    field_name=field_name,
                    observed_at=_timestamp(row["observed_at"]),
                    available_at=(
                        _timestamp(row["available_at"])
                        if row.get("available_at") is not None
                        else None
                    ),
                    retrieved_at=retrieved_at,
                    value=Decimal(str(value)),
                    unit=unit,
                    quality_flags=quality_flags,
                    evidence=evidence,
                )
            )
    return tuple(values)


def _latest_return_metrics(
    request: PortfolioDataContextRequest,
) -> tuple[MonitoringMetric, ...]:
    eligible = [
        item
        for item in request.market_observations
        if item.entity_id == MARKET_ENTITY_ID
        and item.field_name == "return"
        and item.value is not None
        and item.available_at is not None
        and item.available_at <= request.as_of
    ]
    if not eligible:
        return ()
    latest = max(
        eligible,
        key=lambda item: (item.available_at, item.observed_at),
    )
    return (
        MonitoringMetric(
            metric="daily_return",
            value=latest.value,
            instrument_id=PORTFOLIO_INSTRUMENT_ID,
            evidence=latest.evidence,
        ),
    )


def _outcomes(
    evidence: tuple[MonitoringEvidence, ...],
) -> tuple[OutcomeLabel, ...]:
    path = FIXTURE_ROOT / "synthetic-outcomes.csv"
    outcome_digest = "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()
    outcome_evidence = evidence + (
        MonitoringEvidence(
            evidence_id="part2-outcomes",
            reference="fixture://day23/synthetic-outcomes.csv",
            digest=outcome_digest,
            description=(
                "Reviewed synthetic outcomes with explicit integration-test bindings "
                "to the Part 1 stable PERMNO entities."
            ),
        ),
    )
    explicit_bindings = {
        "fictional-instrument-orchid": "security-permno-910001",
        "fictional-instrument-cobalt": "security-permno-910002",
    }
    with path.open("r", encoding="utf-8", newline="") as stream:
        rows = tuple(csv.DictReader(stream))
    return tuple(
        OutcomeLabel(
            outcome_id=row["outcome_id"],
            instrument_id=explicit_bindings[row["instrument_id"]],
            outcome_time=_timestamp(row["outcome_time"]),
            trigger_available_at=_timestamp(row["trigger_available_at"]),
            label=row["label"],
            method=row["method"],
            evidence=outcome_evidence,
        )
        for row in rows
    )


def execute_part2_journey(output_root: Path | str | None = None) -> dict[str, Any]:
    """Exercise the complete Part 2 path with network access actively blocked."""

    external_root = resolve_data_root(output_root)
    output_directory = external_root / OUTPUT_DIRECTORY_NAME
    with _network_blocked() as network_proof:
        phase1 = execute_phase1_journey(external_root)
        phase1_artifacts = phase1["artifacts"]
        latest_snapshot = next(
            item
            for item in phase1_artifacts["dataset_snapshots"]["snapshots"]
            if item["snapshot_id"]
            == phase1_artifacts["dataset_snapshots"]["latest_snapshot_id"]
        )
        revisions = {
            str(item["dataset_id"]): item
            for item in latest_snapshot["dataset_revisions"]
        }
        research = ResearchDataPlane(external_root / "day23-phase1" / "data-plane")
        market_query = research.run_fixed_query(
            FixedQueryRequest(
                manifest_id="daily-market-history",
                as_of=REPLAY_END,
                limit=100,
            )
        )
        fundamental_query = research.run_fixed_query(
            FixedQueryRequest(
                manifest_id="fundamentals-as-of",
                as_of=REPLAY_END,
                limit=100,
            )
        )
        crosswalk = CrosswalkSnapshot.model_validate(
            phase1_artifacts["identifier_crosswalk"]["crosswalk"]
        )
        mappings = date_effective_mappings_from_crosswalk(crosswalk)
        event_plane = EventDataPlane(external_root / STATE_DIRECTORY_NAME / "events")
        event_provider = EventProviderProfile(
            provider_id="fictional-local-event-provider",
            display_name="Fictional Local Event Provider",
            profile="synthetic_local",
            publication_restriction=PublicationRestriction.SYNTHETIC_ONLY,
            synthetic=True,
            private=False,
        )
        event_preview = event_plane.preview_event_export(
            (FIXTURE_ROOT / "ravenpack-like-events.csv").resolve(),
            provider=event_provider,
            dataset_revision="fictional-event-revision-1",
            mapping_manifest=FIXTURE_ROOT
            / "ravenpack-like-events.event-map.json",
            retrieved_at=EVENT_RETRIEVED_AT,
        )
        event_snapshot = event_plane.confirm_event_export(
            event_preview,
            confirm=True,
            preview_digest=event_preview.preview_digest,
            source_digest=event_preview.source.source_digest,
        )
        monitoring_evidence, capability_evidence = _evidence(
            latest_snapshot,
            event_preview.source.source_digest,
        )

        market_rows = [
            dict(item)
            for item in market_query.rows
            if item["dataset_id"] == MARKET_DATASET_ID
        ]
        fundamental_rows = [
            dict(item)
            for item in fundamental_query.rows
            if item["dataset_id"] == FUNDAMENTAL_DATASET_ID
        ]
        market_snapshot_id = str(market_rows[0]["snapshot_id"])
        market_revision = str(market_rows[0]["dataset_revision"])
        fundamental_snapshot_id = str(fundamental_rows[0]["snapshot_id"])
        fundamental_revision = str(fundamental_rows[0]["dataset_revision"])
        market_observations = _observations(
            market_rows,
            snapshot_id=market_snapshot_id,
            revision=market_revision,
            retrieved_at=_timestamp(revisions[MARKET_DATASET_ID]["retrieved_at"]),
            fields=(
                ("valuation_price", "valuation_price", "USD_per_share"),
                ("return", "return", "decimal_return"),
            ),
            evidence=monitoring_evidence,
        )
        fundamental_observations = _observations(
            fundamental_rows,
            snapshot_id=fundamental_snapshot_id,
            revision=fundamental_revision,
            retrieved_at=_timestamp(
                revisions[FUNDAMENTAL_DATASET_ID]["retrieved_at"]
            ),
            fields=(
                ("assets", "assets", "USD"),
                ("sales", "sales", "USD"),
            ),
            evidence=monitoring_evidence,
        )
        portfolio = PortfolioSnapshot(
            snapshot_id="day23-part2-synthetic-portfolio",
            as_of=PORTFOLIO_AS_OF,
            base_currency="USD",
            positions=(
                Position(
                    instrument_id=PORTFOLIO_INSTRUMENT_ID,
                    quantity=Decimal("10"),
                    price=Decimal("40"),
                    market_value=Decimal("400"),
                    currency="USD",
                ),
            ),
        )
        context_request = PortfolioDataContextRequest(
            portfolio_snapshot_id=portfolio.snapshot_id,
            portfolio_snapshot=portfolio,
            market_dataset_snapshot_id=market_snapshot_id,
            market_dataset_revision=market_revision,
            market_dataset_retrieved_at=_timestamp(
                revisions[MARKET_DATASET_ID]["retrieved_at"]
            ),
            market_observations=market_observations,
            fundamental_dataset_snapshot_id=fundamental_snapshot_id,
            fundamental_dataset_revision=fundamental_revision,
            fundamental_dataset_retrieved_at=_timestamp(
                revisions[FUNDAMENTAL_DATASET_ID]["retrieved_at"]
            ),
            fundamental_observations=fundamental_observations,
            crosswalk_snapshot_id=crosswalk.snapshot_id,
            crosswalk_dataset_revision=crosswalk.source_digest,
            crosswalk_retrieved_at=_timestamp(
                revisions["synthetic-crsp-compustat-link"]["retrieved_at"]
            ),
            crosswalk_records=mappings,
            event_snapshot_id=event_snapshot.snapshot_id,
            event_dataset_revision=event_snapshot.dataset_revision,
            event_dataset_retrieved_at=event_snapshot.created_at,
            as_of=MONITORING_TIME,
            stale_data_maximum_age_seconds=3 * 86_400,
            evidence=monitoring_evidence,
            assumptions=(
                "All observations and labels are fictional and synthetic.",
            ),
            limitations=(
                "The demonstration contains one synthetic portfolio position.",
            ),
        )
        registry = CapabilityRegistry()
        context_result = registry.invoke(
            "portfolio.data_context.create",
            PortfolioDataContextCapabilityRequest(
                request=context_request,
                evidence_references=capability_evidence,
            ),
        )
        if context_result.data is None or context_result.data.blocked:
            raise RuntimeError("reviewed Part 2 context was unexpectedly blocked")
        context = context_result.data
        if (
            context.bindings[0].mapping_rule != "exact_date_effective"
            or context.bindings[0].effective_start.isoformat() != "2020-01-01"
            or not context.mapping_coverage.complete
        ):
            raise RuntimeError("exact date-effective Part 1 mapping proof failed")

        ticker_portfolio = PortfolioSnapshot(
            snapshot_id="day23-part2-ticker-fallback-probe",
            as_of=PORTFOLIO_AS_OF,
            base_currency="USD",
            positions=(
                Position(
                    instrument_id="NOVA",
                    quantity=Decimal("1"),
                    price=Decimal("40"),
                    market_value=Decimal("40"),
                    currency="USD",
                ),
            ),
        )
        ticker_probe_request = context_request.model_copy(
            update={
                "portfolio_snapshot_id": ticker_portfolio.snapshot_id,
                "portfolio_snapshot": ticker_portfolio,
            }
        )
        ticker_probe = registry.invoke(
            "portfolio.data_context.create",
            PortfolioDataContextCapabilityRequest(
                request=ticker_probe_request,
                evidence_references=capability_evidence,
            ),
        )
        if (
            ticker_probe.data is None
            or not ticker_probe.data.blocked
            or not any(
                item.code == "missing_mapping"
                for item in ticker_probe.data.quality_issues
            )
        ):
            raise RuntimeError("ticker fallback was not rejected")

        event_query_request = EventQueryRequest(
            snapshot_id=event_snapshot.snapshot_id,
            as_of=MONITORING_TIME,
            limit=100,
        )
        event_query = event_plane.query_events(
            event_query_request,
            event_snapshot,
        )
        if (
            not event_query.records
            or any(
                item.available_at is None
                or item.available_at > MONITORING_TIME
                for item in event_query.records
            )
            or any(
                item.source_event_id == "fictional-rp-005"
                for item in event_query.records
            )
        ):
            raise RuntimeError("event point-in-time availability proof failed")

        policy = MonitoringPolicyVersion(
            policy_id="day23-part2-monitoring-policy",
            version=1,
            daily_percentage_move_threshold=Decimal("0.01"),
            concentration_threshold=Decimal("0.80"),
            event_relevance_minimum=Decimal("0.60"),
            negative_sentiment_threshold=Decimal("-0.50"),
            stale_data_maximum_age_seconds=3 * 86_400,
            historical_var_limit=Decimal("0.10"),
            scenario_loss_limit=Decimal("1000"),
            cadence="daily",
            cadence_metadata=(
                "Descriptive metadata only; every run is explicitly invoked."
            ),
            reviewed_by="day23-part2-integration-authority",
            reviewed_at=PORTFOLIO_AS_OF,
            evidence=monitoring_evidence,
        )
        if policy != MonitoringPolicyVersion.model_validate(
            policy.model_dump(mode="json")
        ):
            raise RuntimeError("monitoring policy revision is not immutable")

        workflow = ContextualMonitoringWorkflowRequest(
            run_id="day23-part2-monitoring-run",
            context_request=context_request,
            policy_version=policy,
            evaluation_id="day23-part2-policy-evaluation",
            run_at=MONITORING_TIME,
            metrics=_latest_return_metrics(context_request),
            event_query_request=event_query_request,
            event_snapshot=event_snapshot,
            assumptions=("The run was explicitly invoked in the deterministic journey.",),
            limitations=("Cadence metadata did not create a scheduler.",),
            evidence_references=capability_evidence,
        )
        run = DeterministicContextualMonitoringOrchestrator(registry).run(workflow)
        if (
            len(run.four_agent_timeline) != 4
            or set(item.role for item in run.four_agent_timeline)
            != set(ACTIVE_AGENT_ROLE_IDS)
            or not run.findings.findings
            or run.alert_draft.state != "draft"
            or run.effects
            or run.alert_draft.effects
        ):
            raise RuntimeError("four-agent effect-free monitoring proof failed")

        specification = ReplaySpecification(
            specification_id="day23-part2-replay-specification",
            start=PORTFOLIO_AS_OF,
            end=REPLAY_END,
            cadence_seconds=86_400,
            portfolio_snapshot_id=portfolio.snapshot_id,
            market_dataset_snapshot_id=market_snapshot_id,
            market_dataset_revision=market_revision,
            fundamental_dataset_snapshot_id=fundamental_snapshot_id,
            fundamental_dataset_revision=fundamental_revision,
            crosswalk_snapshot_id=crosswalk.snapshot_id,
            crosswalk_dataset_revision=crosswalk.source_digest,
            event_snapshot_id=event_snapshot.snapshot_id,
            event_dataset_revision=event_snapshot.dataset_revision,
            policy_revision=policy.revision or "",
            lookback_window_seconds=3 * 86_400,
            evaluation_horizon_seconds=86_400,
            minimum_labelled_outcomes=3,
            labelled_outcome_method="reviewed_synthetic_threshold_label",
            evidence=monitoring_evidence,
        )
        step_inputs: list[ReplayStepInput] = []
        for sequence, as_of in enumerate(specification.replay_times(), start=1):
            step_request = context_request.model_copy(update={"as_of": as_of})
            if sequence == len(specification.replay_times()):
                step_request = step_request.model_copy(
                    update={"market_observations": ()}
                )
            step_inputs.append(
                ReplayStepInput(
                    context_request=step_request,
                    evaluation_id=f"day23-part2-replay-step-{sequence}",
                    metrics=_latest_return_metrics(step_request),
                    event_query_request=EventQueryRequest(
                        snapshot_id=event_snapshot.snapshot_id,
                        as_of=as_of,
                        limit=100,
                    ),
                    event_snapshot=event_snapshot,
                )
            )
        replay_result = registry.invoke(
            "monitoring.replay",
            ReplayCapabilityRequest(
                run_id="day23-part2-replay-run",
                specification=specification,
                policy_version=policy,
                step_inputs=tuple(step_inputs),
                evidence_references=capability_evidence,
            ),
        )
        if replay_result.data is None:
            raise RuntimeError("monitoring replay returned no run")
        replay = replay_result.data
        if (
            tuple(item.as_of for item in replay.steps)
            != specification.replay_times()
            or replay.steps[-1].abstained is not True
            or any(
                observation.available_at is None
                or observation.available_at > step.as_of
                for step in replay.steps
                for observation in step.data_context.latest_market_observations
            )
        ):
            raise RuntimeError("deterministic replay or abstention proof failed")

        outcomes = _outcomes(monitoring_evidence)
        evaluation_result = registry.invoke(
            "monitoring.evaluate",
            ReplayEvaluationCapabilityRequest(
                evaluation_id="day23-part2-monitoring-evaluation",
                replay_run=replay,
                outcomes=outcomes,
                evaluated_at=EVALUATED_AT,
                evidence_references=capability_evidence,
            ),
        )
        undefined_result = registry.invoke(
            "monitoring.evaluate",
            ReplayEvaluationCapabilityRequest(
                evaluation_id="day23-part2-undefined-metric-example",
                replay_run=replay,
                outcomes=(),
                evaluated_at=EVALUATED_AT,
                evidence_references=capability_evidence,
            ),
        )
        if evaluation_result.data is None or undefined_result.data is None:
            raise RuntimeError("monitoring evaluation returned no result")
        evaluation = evaluation_result.data
        undefined = undefined_result.data
        if (
            (evaluation.true_positive, evaluation.false_positive, evaluation.false_negative)
            != (1, 1, 1)
            or evaluation.precision != Decimal("0.5")
            or evaluation.recall != Decimal("0.5")
            or evaluation.median_lead_time_seconds is None
            or evaluation.median_detection_delay_seconds is None
            or len({item.alert_id for item in evaluation.matches})
            != len(evaluation.matches)
            or len({item.outcome_id for item in evaluation.matches})
            != len(evaluation.matches)
        ):
            raise RuntimeError("one-to-one replay evaluation proof failed")
        if (
            undefined.recall is not None
            or "undefined_recall"
            not in {item.code for item in undefined.warnings}
        ):
            raise RuntimeError("undefined metric was not null with a warning")

        report_result = registry.invoke(
            "monitoring.report.render",
            MonitoringReportCapabilityRequest(
                request=MonitoringReportRequest(
                    report_id="day23-part2-monitoring-report",
                    title="Synthetic Day 2–3 Part 2 Monitoring and Replay Review",
                    monitoring_run=run,
                    policy_version=policy,
                    replay_run=replay,
                    evaluation=evaluation,
                    evidence=monitoring_evidence,
                ),
                evidence_references=capability_evidence,
            ),
        )
        if report_result.data is None or report_result.data.effects:
            raise RuntimeError("monitoring report was not effect-free")
        report = report_result.data

        sql_rejection = ""
        try:
            FixedQueryRequest(
                manifest_id="daily-market-history",
                parameters={"sql": "select * from daily_market"},
                as_of=MONITORING_TIME,
            )
        except ValidationError as error:
            sql_rejection = str(error.errors()[0]["msg"])
        if not sql_rejection:
            raise RuntimeError("arbitrary SQL input was unexpectedly accepted")

        part2_capabilities = (
            "portfolio.data_context.create",
            "events.query.as_of",
            "monitoring.policy.evaluate",
            "monitoring.run.contextual",
            "monitoring.replay",
            "monitoring.evaluate",
            "monitoring.report.render",
        )
        for capability_id in part2_capabilities:
            descriptor = CAPABILITY_BY_ID[capability_id]
            if descriptor.allowed_effects or not set(PROHIBITED_EFFECTS) <= set(
                descriptor.denied_effects
            ):
                raise RuntimeError(
                    f"{capability_id} does not preserve the prohibited-effect boundary"
                )
        if any(
            item.effects
            for item in (
                context_result,
                ticker_probe,
                replay_result,
                evaluation_result,
                undefined_result,
                report_result,
            )
        ):
            raise RuntimeError("a registered Part 2 invocation returned effects")
        if any("llm" in item.capability_id for item in registry.invocation_history):
            raise RuntimeError("an external LLM capability was unexpectedly invoked")
        if any(
            prohibited in capability_id
            for capability_id in registry.capability_ids
            for prohibited in (
                "notebook.execute",
                "broker.",
                "order.",
                "trade.",
                "rebalance",
                "optimization",
            )
        ):
            raise RuntimeError("a prohibited executable capability is registered")

    if network_proof["attempts"] != 0:
        raise RuntimeError("the completed journey attempted network access")

    selected_revisions = {
        "market": {
            "snapshot_id": market_snapshot_id,
            "dataset_id": MARKET_DATASET_ID,
            "revision": market_revision,
            "source_digest": revisions[MARKET_DATASET_ID]["source_digest"],
        },
        "fundamental": {
            "snapshot_id": fundamental_snapshot_id,
            "dataset_id": FUNDAMENTAL_DATASET_ID,
            "revision": fundamental_revision,
            "source_digest": revisions[FUNDAMENTAL_DATASET_ID]["source_digest"],
        },
        "event": {
            "snapshot_id": event_snapshot.snapshot_id,
            "revision": event_snapshot.dataset_revision,
            "source_digest": event_snapshot.source_digest,
        },
    }
    common = {
        "synthetic_disclosure": (
            "All market, fundamental, crosswalk, event, portfolio, and outcome "
            "observations in this journey are fictional and explicitly synthetic."
        ),
        "human_review_pending": True,
        "effects": [],
    }
    artifacts: dict[str, object] = {
        "data-context.json": {
            **common,
            "context": _portable(context, output_directory),
            "selected_dataset_revisions": selected_revisions,
            "selected_crosswalk_revision": crosswalk.source_digest,
            "exact_date_effective_mapping": True,
            "mapping_rule": context.bindings[0].mapping_rule,
            "mapping_effective_start": (
                context.bindings[0].effective_start.isoformat()
                if context.bindings[0].effective_start is not None
                else None
            ),
            "ticker_fallback_used": False,
            "ticker_probe_blocked": ticker_probe.data.blocked,
            "ticker_probe_issue_codes": [
                item.code for item in ticker_probe.data.quality_issues
            ],
            "point_in_time_rule": "available_at <= as_of",
        },
        "event-import-preview.json": {
            **common,
            "preview": _portable(event_preview, output_directory),
            "confirmable": not event_preview.has_blocking_issues,
            "local_only": True,
            "network_enabled": False,
        },
        "event-snapshot.json": {
            **common,
            "snapshot": _portable(event_snapshot, output_directory),
            "query": _portable(event_query, output_directory),
            "only_available_as_of_monitoring_time": True,
            "missing_availability_excluded": True,
        },
        "monitoring-policy.json": {
            **common,
            "policy": _portable(policy, output_directory),
            "immutable_revision": policy.revision,
            "scheduler_created": False,
            "arbitrary_expression_available": False,
        },
        "monitoring-run.json": {
            **common,
            "run": _portable(run, output_directory),
            "capability_invocations": _portable(
                registry.invocation_history, output_directory
            ),
        },
        "findings.json": {
            **common,
            "findings": _portable(run.findings, output_directory),
        },
        "alert-draft.json": {
            **common,
            "alert": _portable(run.alert_draft, output_directory),
            "state": "effect_free_analytical_draft",
            "investment_advice": False,
        },
        "agent-timeline.json": {
            **common,
            "roles": [item.role for item in run.four_agent_timeline],
            "timeline": _portable(run.four_agent_timeline, output_directory),
            "all_four_existing_agents_ran": True,
        },
        "replay-specification.json": {
            **common,
            "specification": _portable(specification, output_directory),
            "selected_dataset_revisions": selected_revisions,
            "selected_crosswalk_revision": crosswalk.source_digest,
            "policy_revision": policy.revision,
        },
        "replay-runs.json": {
            **common,
            "replay": _portable(replay, output_directory),
            "deterministic_step_times": [
                item.isoformat().replace("+00:00", "Z")
                for item in specification.replay_times()
            ],
            "abstentions_preserved": replay.steps[-1].abstained,
            "no_look_ahead": True,
        },
        "monitoring-evaluation.json": {
            **common,
            "evaluation": _portable(evaluation, output_directory),
            "undefined_metric_example": _portable(undefined, output_directory),
            "one_to_one_matching": True,
            "outcome_binding_method": (
                "Explicit reviewed fictional-name to Part 1 stable PERMNO entity "
                "mapping; no ticker, name guessing, fuzzy, or heuristic match."
            ),
        },
        "monitoring-report.md": report.markdown,
        "monitoring-report.html": report.html,
    }
    boundary_proofs = {
        "network": {
            "blocked_during_journey": True,
            "attempts": network_proof["attempts"],
        },
        "external_llm": {
            "invoked": False,
            "denied_effect": "external_llm_call",
        },
        "sql": {
            "arbitrary_sql_available": False,
            "rejection": sql_rejection,
            "fixed_query_manifests_only": True,
        },
        "notebook_execution": False,
        "broker_connectivity": False,
        "orders": False,
        "trades": False,
        "automatic_rebalancing": False,
        "optimization": False,
    }
    return {
        "output_directory": output_directory,
        "artifacts": artifacts,
        "manifest_metadata": {
            "programme_part": "D23-PART-2",
            "deterministic": True,
            "profiles": {
                "research": "reviewed synthetic evidence used",
                "personal_portfolio": (
                    "supported as local-private monitoring only; not used by this "
                    "public synthetic journey"
                ),
            },
            "selected_dataset_revisions": selected_revisions,
            "selected_crosswalk_revision": crosswalk.source_digest,
            "policy_revision": policy.revision,
            "point_in_time_rule": "available_at <= as_of",
            "synthetic_disclosure": common["synthetic_disclosure"],
            "human_review_pending": True,
            "effects": [],
            "prohibited_effects": list(PROHIBITED_EFFECTS),
            "evaluation_methodology": evaluation.methodology,
            "accepted_limitations": [
                "The sample is fictional, synthetic, local, and intentionally small.",
                "Cadence is metadata; replay and monitoring are explicit foreground invocations.",
                "Evaluation is descriptive and makes no predictive or investment-performance claim.",
                "Reports are local HTML and Markdown review artifacts only.",
                "Part 3 human QA and release decision remain pending.",
            ],
            "boundary_proofs": boundary_proofs,
            "evidence_digests": [
                {
                    "evidence_id": item.evidence_id,
                    "reference": item.reference,
                    "digest": item.digest,
                }
                for item in monitoring_evidence
            ],
        },
        "effects": (),
    }


def write_part2_artifacts(result: dict[str, Any]) -> dict[str, Path]:
    """Write or verify the immutable Part 2 evidence artifacts and manifest."""

    output_directory = Path(result["output_directory"])
    output_directory.mkdir(parents=True, exist_ok=True)
    paths: dict[str, Path] = {}
    for name in ARTIFACT_NAMES:
        value = result["artifacts"][name]
        content = (
            value.encode("utf-8")
            if name.endswith((".md", ".html"))
            else _encoded(value)
        )
        paths[name] = _write_stable(output_directory / name, content)
    manifest = {
        **result["manifest_metadata"],
        "artifacts": [
            {"path": path.name, "digest": _digest(path)}
            for path in sorted(paths.values(), key=lambda item: item.name)
        ],
    }
    paths["evidence-manifest.json"] = _write_stable(
        output_directory / "evidence-manifest.json",
        _encoded(manifest),
    )
    unexpected = {
        path.name
        for path in output_directory.iterdir()
        if path.is_file() and path.name not in {*ARTIFACT_NAMES, "evidence-manifest.json"}
    }
    if unexpected:
        raise RuntimeError(
            f"unexpected sibling Part 2 artifacts are not digested: {sorted(unexpected)}"
        )
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
    result = execute_part2_journey(args.output_root)
    paths = write_part2_artifacts(result)
    for name in (*ARTIFACT_NAMES, "evidence-manifest.json"):
        print(f"{name}: {paths[name]}")
    print("D23 Part 2 deterministic demo: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
