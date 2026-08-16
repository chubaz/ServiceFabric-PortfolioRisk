from __future__ import annotations

import json
import sys
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest
import duckdb


ROOT = Path(__file__).resolve().parents[2]
LABS_ROOT = ROOT / "apps" / "portfolio-risk-workbench" / "labs"
sys.path.insert(0, str(LABS_ROOT))

import case_labelling_runtime  # noqa: E402
import duckdb_server  # noqa: E402
from risk_analytics import (  # noqa: E402
    AnalysisEvidence,
    DetectorDefinition,
    DetectorKind,
    DetectorObservation,
    SignalScope,
    execute_detector,
)
from risk_experiments import ReviewOutcome  # noqa: E402


START = datetime(2015, 1, 2, 21, tzinfo=UTC)


def runs():  # type: ignore[no-untyped-def]
    values = ("-0.01", "0", "0.01", "-0.02", "0.02", "-0.10", "0.12")
    observations = tuple(
        DetectorObservation(
            series_id="company-alpha",
            scope_type=SignalScope.INSTRUMENT,
            scope_id="company-alpha",
            observed_at=START + timedelta(days=index),
            available_at=START + timedelta(days=index),
            value=Decimal(value),
            benchmark_value=Decimal("0"),
            evidence_ids=(f"crsp:alpha:{index}",),
            quality_flags=("licensed_read_only",),
        )
        for index, value in enumerate(values)
    )
    evidence = (
        AnalysisEvidence(
            evidence_id="licensed-read-only-test-revision",
            reference="dataset://licensed/test",
            digest="sha256:" + "d" * 64,
            description="Licensed-shaped test rows; no licensed bytes are committed.",
        ),
    )
    return (
        execute_detector(
            DetectorDefinition(
                detector_id="robust-residual-z",
                version="1.0.0",
                kind=DetectorKind.ROBUST_RESIDUAL_Z_SCORE,
                lookback=5,
                threshold=Decimal("3"),
            ),
            observations,
            as_of=START + timedelta(days=6),
            evidence=evidence,
        ),
    )


@pytest.fixture
def configured_runtime(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):  # type: ignore[no-untyped-def]
    monkeypatch.setenv("PORTFOLIO_RISK_LABEL_ROOT", str(tmp_path / "label-store"))
    monkeypatch.setattr(
        case_labelling_runtime,
        "execute_detector_scan",
        lambda *_args, **_kwargs: SimpleNamespace(runs=runs(), as_of=START + timedelta(days=6)),
    )
    monkeypatch.setattr(
        case_labelling_runtime,
        "_display_context",
        lambda *_args, **_kwargs: {"company-alpha": {"company_name": "Alpha Industries", "ticker": "ALP"}},
    )
    database = tmp_path / "study.duckdb"
    with duckdb.connect(str(database)) as connection:
        connection.execute("CREATE TABLE crsp_daily (observed_at DATE, permno BIGINT, total_return DECIMAL(18,8), valuation_price DECIMAL(18,4), available_at TIMESTAMPTZ)")
        connection.execute("CREATE TABLE ravenpack_events_linked (provider_id VARCHAR, dataset_revision VARCHAR, source_event_id VARCHAR, local_event_id VARCHAR, event_time TIMESTAMPTZ, available_at TIMESTAMPTZ, permno BIGINT, event_type VARCHAR, topic VARCHAR, category VARCHAR, provider_entity_name VARCHAR, position_name VARCHAR, relevance DOUBLE, novelty DOUBLE, sentiment DOUBLE)")
        connection.execute("CREATE TABLE ravenpack_integration_status (provider_id VARCHAR, publication_restriction VARCHAR)")
        connection.execute("INSERT INTO ravenpack_integration_status VALUES ('ravenpack', 'private_local')")
        connection.execute("CREATE TABLE ccm_links (permno BIGINT, gvkey VARCHAR, link_start DATE, link_end DATE)")
        connection.execute("CREATE TABLE compustat_quarterly (gvkey VARCHAR, observed_at DATE, available_at TIMESTAMPTZ, source_revision VARCHAR, currency VARCHAR, total_assets DECIMAL(18,2), total_liabilities DECIMAL(18,2), common_equity DECIMAL(18,2), revenue DECIMAL(18,2), net_income DECIMAL(18,2))")
        connection.execute("INSERT INTO ccm_links VALUES (101, '00101', DATE '2010-01-01', NULL)")
        connection.execute("INSERT INTO ravenpack_events_linked VALUES ('ravenpack', 'rp-test', 'source-event-1', 'event-1', TIMESTAMPTZ '2015-01-07 10:00:00+00', TIMESTAMPTZ '2015-01-07 10:01:00+00', 101, 'Earnings', 'Guidance', 'Results', 'Alpha Industries', 'Alpha Industries', 0.9, 0.8, -0.4)")
        connection.execute("INSERT INTO compustat_quarterly VALUES ('00101', DATE '2015-01-07', TIMESTAMPTZ '2015-01-07 12:00:00+00', 'cq-test', 'USD', 1000, 600, 400, 250, 20)")
        rows = []
        price = Decimal("100")
        for index in range(12):
            result = Decimal("-0.08") if index == 8 else Decimal("0.005")
            price *= Decimal("1") + result
            observed = date(2014, 12, 31) + timedelta(days=index)
            rows.append((observed, 101, result, price, datetime.combine(observed, datetime.min.time(), tzinfo=UTC) + timedelta(hours=1)))
        connection.executemany("INSERT INTO crsp_daily VALUES (?, ?, ?, ?, ?)", rows)
    monkeypatch.setattr(case_labelling_runtime, "_database", lambda *_args, **_kwargs: database)
    monkeypatch.setattr(case_labelling_runtime, "_positions", lambda *_args, **_kwargs: ((SimpleNamespace(alias="company-alpha", permno=101),), Decimal("0"), {}))
    return tmp_path


def create_request() -> case_labelling_runtime.LabellingBatchRequest:
    return case_labelling_runtime.LabellingBatchRequest(
        portfolio_id="portfolio-alpha",
        start_date=date(2015, 1, 7),
        end_date=date(2015, 1, 8),
        target_count=4,
        actor="researcher-primary",
    )


def test_batch_creation_is_idempotent_selective_and_hides_developer_records(
    configured_runtime,
) -> None:  # type: ignore[no-untyped-def]
    first = case_labelling_runtime.create_labelling_batch(configured_runtime, create_request())
    second = case_labelling_runtime.create_labelling_batch(configured_runtime, create_request())

    assert first["batch_id"] == second["batch_id"]
    assert first["summary"]["selected"] >= 1
    assert first["units"][0]["company"] == "Alpha Industries"
    assert first["summary"]["to_label"] == first["summary"]["selected"]
    serialized = json.dumps(first)
    assert "sha256:" not in serialized
    assert "evidence_ids" not in serialized
    assert "detector_run" not in serialized
    assert "gold_case" not in serialized
    assert "No Gold case" in first["boundary_note"]


def test_on_demand_study_is_readable_retained_and_does_not_create_a_label(configured_runtime) -> None:  # type: ignore[no-untyped-def]
    batch = case_labelling_runtime.create_labelling_batch(configured_runtime, create_request())
    unit = batch["units"][0]
    studied = case_labelling_runtime.study_review_unit(
        configured_runtime,
        batch["batch_id"],
        case_labelling_runtime.LabelStudyRequest(unit_id=unit["id"]),
    )
    result = studied["units"][0]
    assert result["study"]["path"]
    assert result["study"]["intervals"]
    assert [item["horizon"] for item in result["study"]["severity"]] == [1, 5, 20]
    assert result["annotation"] is None
    assert result["state"] == "unlabelled"
    assert "Suggestion only" not in json.dumps(studied)  # UI supplies the concise badge.
    serialized = json.dumps(result["study"])
    assert "sha256:" not in serialized
    assert "evidence_id" not in serialized
    assert "study_id" not in serialized
    assert "Gold" not in serialized
    assert "related_moves" not in serialized
    assert "association" not in serialized.lower()
    repeated = case_labelling_runtime.study_review_unit(
        configured_runtime,
        batch["batch_id"],
        case_labelling_runtime.LabelStudyRequest(unit_id=unit["id"]),
    )
    assert repeated == studied


def test_context_readiness_profiles_sources_without_association(configured_runtime) -> None:  # type: ignore[no-untyped-def]
    batch = case_labelling_runtime.create_labelling_batch(configured_runtime, create_request())
    result = case_labelling_runtime.context_source_readiness(
        configured_runtime,
        batch["batch_id"],
        case_labelling_runtime.ContextReadinessRequest(),
    )
    assert result["association_state"] == "Not started"
    assert result["association_count"] == 0
    assert {item["name"] for item in result["sources"]} == {"RavenPack events", "Compustat fundamentals"}
    assert all(item["eligible_rows"] == 1 for item in result["sources"])
    assert "association" in result["message"].lower()


def test_context_plan_validates_saves_and_reloads_without_execution(configured_runtime) -> None:  # type: ignore[no-untyped-def]
    batch = case_labelling_runtime.create_labelling_batch(configured_runtime, create_request())
    unit = batch["units"][0]
    request = case_labelling_runtime.ContextWorkPlanRequest(
        unit_id=unit["id"], purpose="test_competing_explanations",
        channels=("events", "fundamentals"), event_days_before=30,
        event_days_after=10, fundamental_lookback_quarters=6,
        alternatives_required=True,
        controls=("ambiguous_event", "no_material_event"), expected_revision=0,
    )
    preview = case_labelling_runtime.validate_context_work_plan(
        configured_runtime, batch["batch_id"], request
    )
    assert preview["valid"] and not preview["saved"]
    assert preview["plan"]["execution"] == "Not started"
    assert preview["plan"]["retrieved"] == preview["plan"]["associations"] == 0

    saved = case_labelling_runtime.save_context_work_plan(
        configured_runtime, batch["batch_id"], request
    )
    assert saved["plan"]["revision"] == 1
    assert saved["plan"]["execution"] == "Not started"
    loaded = case_labelling_runtime.labelling_batch_payload(configured_runtime, batch["batch_id"])
    plan = loaded["units"][0]["context_plan"]
    assert plan["purpose"] == "test_competing_explanations"
    assert plan["associations"] == plan["retrieved"] == plan["controls_generated"] == 0
    assert "plan_id" not in json.dumps(plan)
    assert "digest" not in json.dumps(plan)


def test_context_preparation_is_bounded_reviewable_and_does_not_modify_label(configured_runtime) -> None:  # type: ignore[no-untyped-def]
    batch = case_labelling_runtime.create_labelling_batch(configured_runtime, create_request())
    unit = batch["units"][0]
    saved = case_labelling_runtime.save_context_work_plan(
        configured_runtime,
        batch["batch_id"],
        case_labelling_runtime.ContextWorkPlanRequest(
            unit_id=unit["id"], channels=("events", "fundamentals"), expected_revision=0,
        ),
    )
    assert saved["plan"]["state"] == "ready_for_later_execution"
    prepared = case_labelling_runtime.prepare_context_work(
        configured_runtime,
        batch["batch_id"],
        case_labelling_runtime.ContextPreparationRequest(
            unit_id=unit["id"], expected_plan_revision=1,
        ),
    )
    work = prepared["context_work"]
    assert work["state"] == "Awaiting review"
    assert work["candidate_count"] == 2
    assert {item["source"] for item in work["candidates"]} == {"Event", "Fundamental"}
    assert any("lifecycle unverified" in value for item in work["candidates"] for value in item["limitations"])
    assert all(item["review"] is None for item in work["candidates"])

    decisions = tuple(
        case_labelling_runtime.ContextCandidateReviewRequest(
            candidate_id=item["key"],
            outcome="retain" if index == 0 else "reject",
            evidence_role="precursor" if index == 0 else "unrelated",
            evidence_position="supporting" if index == 0 else "alternative",
            rationale="Retained for bounded case context." if index == 0 else "Not sufficiently specific to this manifestation.",
        )
        for index, item in enumerate(work["candidates"])
    )
    reviewed = case_labelling_runtime.review_prepared_context(
        configured_runtime,
        batch["batch_id"],
        case_labelling_runtime.ContextReviewRequest(
            unit_id=unit["id"], expected_plan_revision=1,
            expected_review_revision=0, outcome="accept_context",
            candidate_reviews=decisions, limitations_acknowledged=True,
            summary="One candidate is useful and the known source limitations remain explicit.",
        ),
    )
    assert reviewed["context_work"]["state"] == "Context accepted"
    reloaded = case_labelling_runtime.labelling_batch_payload(configured_runtime, batch["batch_id"])
    result = reloaded["units"][0]
    assert result["context_work"]["review"]["outcome"] == "accept_context"
    assert result["annotation"] is None
    assert "gold" not in json.dumps(result["context_work"]).lower().replace("gold or an experimental case", "")


def test_context_preparation_rejects_stale_plan_and_review(configured_runtime) -> None:  # type: ignore[no-untyped-def]
    batch = case_labelling_runtime.create_labelling_batch(configured_runtime, create_request())
    unit = batch["units"][0]
    case_labelling_runtime.save_context_work_plan(
        configured_runtime, batch["batch_id"],
        case_labelling_runtime.ContextWorkPlanRequest(unit_id=unit["id"], channels=("events",), expected_revision=0),
    )
    with pytest.raises(ValueError, match="changed"):
        case_labelling_runtime.prepare_context_work(
            configured_runtime, batch["batch_id"],
            case_labelling_runtime.ContextPreparationRequest(unit_id=unit["id"], expected_plan_revision=2),
        )


def test_annotation_revision_and_independent_review_produce_readiness_not_gold(
    configured_runtime,
) -> None:  # type: ignore[no-untyped-def]
    batch = case_labelling_runtime.create_labelling_batch(configured_runtime, create_request())
    unit = batch["units"][0]
    annotated = case_labelling_runtime.record_signal_annotation(
        configured_runtime,
        batch["batch_id"],
        case_labelling_runtime.SignalAnnotationRequest(
            idempotency_key="annotation-request-alpha",
            expected_revision=batch["revision"],
            unit_id=unit["id"],
            outcome="materialised_risk",
            relevance="relevant",
            scope_type="instrument",
            direction=unit["direction"],
            morphology="punctual_shock",
            interval_start=date.fromisoformat(unit["date"]),
            interval_peak=date.fromisoformat(unit["date"]),
            interval_end=date.fromisoformat(unit["date"]),
            severity_level=2,
            severity_basis_points=Decimal("450"),
            severity_horizon_sessions=5,
            review_confidence=Decimal("0.8"),
            notes="Market manifestation reviewed against the retained path.",
            annotated_by="researcher-primary",
        ),
    )
    assert annotated["units"][0]["state"] == "awaiting_independent_review"
    assert annotated["units"][0]["annotation"]["revision"] == 1

    retried = case_labelling_runtime.record_signal_annotation(
        configured_runtime,
        batch["batch_id"],
        case_labelling_runtime.SignalAnnotationRequest(
            idempotency_key="annotation-request-alpha",
            expected_revision=batch["revision"],
            unit_id=unit["id"],
            outcome="materialised_risk",
            relevance="relevant",
            scope_type="instrument",
            direction=unit["direction"],
            morphology="punctual_shock",
            interval_start=date.fromisoformat(unit["date"]),
            interval_peak=date.fromisoformat(unit["date"]),
            interval_end=date.fromisoformat(unit["date"]),
            severity_level=2,
            severity_basis_points=Decimal("450"),
            severity_horizon_sessions=5,
            review_confidence=Decimal("0.8"),
            notes="Market manifestation reviewed against the retained path.",
            annotated_by="researcher-primary",
        ),
    )
    assert retried["revision"] == annotated["revision"]

    reviewed = case_labelling_runtime.review_signal_annotation(
        configured_runtime,
        batch["batch_id"],
        case_labelling_runtime.LabelReviewRequest(
            idempotency_key="review-request-alpha",
            expected_revision=annotated["revision"],
            annotation_id=annotated["units"][0]["annotation"]["id"],
            outcome=ReviewOutcome.ACCEPT_FOR_GOLD_PREPARATION,
            detection_fields_verified=True,
            severity_fields_verified=True,
            evidence_fields_verified=True,
            temporal_fields_verified=True,
            reviewer_confidence=Decimal("0.8"),
            rationale="Every required field reconciles to the independently reviewed evidence.",
            reviewed_by="reviewer-independent",
        ),
    )
    assert reviewed["units"][0]["state"] == "ready"
    assert reviewed["summary"]["ready"] == 1
    assert "Gold case or experimental Case has been created" in reviewed["boundary_note"]


def test_self_review_and_stale_updates_are_rejected(configured_runtime) -> None:  # type: ignore[no-untyped-def]
    batch = case_labelling_runtime.create_labelling_batch(configured_runtime, create_request())
    unit = batch["units"][0]
    annotated = case_labelling_runtime.record_signal_annotation(
        configured_runtime,
        batch["batch_id"],
        case_labelling_runtime.SignalAnnotationRequest(
            idempotency_key="annotation-for-self-review",
            expected_revision=batch["revision"],
            unit_id=unit["id"],
            outcome="non_material_move",
            relevance="not_relevant",
            scope_type="instrument",
            direction=unit["direction"],
            morphology="punctual_shock",
            severity_level=0,
            notes="The move does not satisfy the predeclared materiality requirement.",
            annotated_by="same-researcher",
        ),
    )
    with pytest.raises(ValueError, match="cannot independently review"):
        case_labelling_runtime.review_signal_annotation(
            configured_runtime,
            batch["batch_id"],
            case_labelling_runtime.LabelReviewRequest(
                idempotency_key="invalid-self-review",
                expected_revision=annotated["revision"],
                annotation_id=annotated["units"][0]["annotation"]["id"],
                outcome="accept_for_gold_preparation",
                detection_fields_verified=True,
                severity_fields_verified=True,
                evidence_fields_verified=True,
                temporal_fields_verified=True,
                reviewer_confidence=Decimal("0.8"),
                rationale="This review is intentionally invalid because the reviewer is the annotator.",
                reviewed_by="same-researcher",
            ),
        )


def test_labelling_api_routes_delegate_without_creating_an_experimental_case(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    expected = {"batch_id": "label-batch-alpha", "summary": {"selected": 4}}
    monkeypatch.setattr(duckdb_server, "find_private_root", lambda _root: Path("/private"))
    monkeypatch.setattr(duckdb_server, "create_labelling_batch", lambda *_args, **_kwargs: expected)

    result = duckdb_server.experiment_create_label_batch(create_request())

    assert result is expected
    assert "case_id" not in result


def test_study_api_route_delegates_without_creating_a_label(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    expected = {"units": [{"study": {"path": []}, "annotation": None}]}
    monkeypatch.setattr(duckdb_server, "find_private_root", lambda _root: Path("/private"))
    monkeypatch.setattr(duckdb_server, "study_review_unit", lambda *_args, **_kwargs: expected)
    result = duckdb_server.experiment_study_label_item(
        "label-batch-alpha",
        case_labelling_runtime.LabelStudyRequest(unit_id="signal-review-alpha"),
    )
    assert result is expected
    assert result["units"][0]["annotation"] is None


def test_context_readiness_api_delegates_without_association(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    expected = {"association_state": "Not started", "association_count": 0}
    monkeypatch.setattr(duckdb_server, "find_private_root", lambda _root: Path("/private"))
    monkeypatch.setattr(duckdb_server, "context_source_readiness", lambda *_args, **_kwargs: expected)
    result = duckdb_server.experiment_context_readiness(
        "label-batch-alpha", case_labelling_runtime.ContextReadinessRequest()
    )
    assert result == expected


def test_context_plan_api_routes_are_validation_and_persistence_only(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    request = case_labelling_runtime.ContextWorkPlanRequest(unit_id="signal-review-alpha")
    preview = {"valid": True, "saved": False, "plan": {"associations": 0}}
    saved = {"saved": True, "plan": {"associations": 0}}
    monkeypatch.setattr(duckdb_server, "find_private_root", lambda _root: Path("/private"))
    monkeypatch.setattr(duckdb_server, "validate_context_work_plan", lambda *_args, **_kwargs: preview)
    monkeypatch.setattr(duckdb_server, "save_context_work_plan", lambda *_args, **_kwargs: saved)
    assert duckdb_server.experiment_validate_context_plan("label-batch-alpha", request) == preview
    assert duckdb_server.experiment_save_context_plan("label-batch-alpha", request) == saved
    assert preview["plan"]["associations"] == saved["plan"]["associations"] == 0


def test_context_preparation_and_review_routes_preserve_the_label_firewall(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    prepared = {"prepared": True, "context_work": {"candidate_count": 2}}
    reviewed = {"saved": True, "context_work": {"state": "Context accepted"}}
    monkeypatch.setattr(duckdb_server, "find_private_root", lambda _root: Path("/private"))
    monkeypatch.setattr(duckdb_server, "prepare_context_work", lambda *_args, **_kwargs: prepared)
    monkeypatch.setattr(duckdb_server, "review_prepared_context", lambda *_args, **_kwargs: reviewed)
    prepare_request = case_labelling_runtime.ContextPreparationRequest(
        unit_id="signal-review-alpha", expected_plan_revision=1,
    )
    review_request = case_labelling_runtime.ContextReviewRequest(
        unit_id="signal-review-alpha", expected_plan_revision=1,
        expected_review_revision=0, outcome="request_changes",
        candidate_reviews=(), limitations_acknowledged=False,
        summary="No candidates were accepted because more context work is required.",
    )
    assert duckdb_server.experiment_prepare_context_work("label-batch-alpha", prepare_request) == prepared
    assert duckdb_server.experiment_review_context_work("label-batch-alpha", review_request) == reviewed
    assert "annotation" not in prepared and "annotation" not in reviewed


def test_gold_routes_delegate_to_the_gated_workflow(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    status = {"gate": {"ready": False}, "record": None}
    prepared = {"saved": True, "record": {"state": "awaiting_independent_review"}}
    reviewed = {"saved": True, "record": {"state": "accepted"}}
    compiled = {"saved": True, "case": {"gold_hidden_from_architecture": True}}
    monkeypatch.setattr(duckdb_server, "gold_work_payload", lambda *_args: status)
    monkeypatch.setattr(duckdb_server, "prepare_gold_reference", lambda *_args: prepared)
    monkeypatch.setattr(duckdb_server, "review_gold_reference", lambda *_args: reviewed)
    monkeypatch.setattr(duckdb_server, "compile_gold_experimental_case", lambda *_args: compiled)

    prepare_request = duckdb_server.GoldPreparationRequest(
        unit_id="signal-review-alpha", study_id="study-alpha", experiment_id="experiment-alpha",
        research_use="Compare architecture behaviour on one accepted historical reference.",
        checkpoint_label="First actionable review", checkpoint_date=date(2015, 8, 24),
        acceptable_actions=("investigate", "monitor"),
    )
    review_request = duckdb_server.GoldReviewRequest(
        reference_id="gold-reference-alpha", expected_review_revision=0, outcome="accept",
        label_reconciled=True, evidence_reconciled=True, temporal_firewall_verified=True,
        limitations_acceptable=True,
        rationale="The exact retained records reconcile and future truth remains isolated.",
    )
    compile_request = duckdb_server.ExperimentalCaseCompileRequest(
        reference_id="gold-reference-alpha", evaluation_horizon_end=date(2015, 9, 24),
    )

    assert duckdb_server.experiment_gold_work("label-batch-alpha", "signal-review-alpha") == status
    assert duckdb_server.experiment_prepare_gold_reference("label-batch-alpha", prepare_request) == prepared
    assert duckdb_server.experiment_review_gold_reference("label-batch-alpha", review_request) == reviewed
    assert duckdb_server.experiment_compile_gold_case("label-batch-alpha", compile_request) == compiled
