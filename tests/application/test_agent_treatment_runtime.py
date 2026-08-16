from datetime import datetime, timezone

import agent_treatment_runtime as runtime
from portfolio_risk_thesis.day3.contracts import ArchitectureReviewOutput, ModelCallReceipt


NOW = datetime(2017, 12, 1, 21, tzinfo=timezone.utc)


def test_model_metric_references_are_normalized_to_contract_identifiers() -> None:
    assert runtime._canonical_metric_id("metric:cash_weight:2017-12-01", "fallback") == "cash-weight"
    assert runtime._canonical_metric_id("metric:novel ratio", "fallback") == "metric-novel-ratio"


class _Provider:
    def __init__(self, *_args, **_kwargs):
        pass

    def generate(self, request):
        evidence = tuple(request.payload.get("evidence_refs", ()))
        output = ArchitectureReviewOutput(
            architecture_id=request.architecture_id,
            status="NO_ISSUE",
            severity=0,
            summary="No material portfolio-risk conclusion is supported by the supplied context.",
            evidence_refs=evidence[:1],
            recommended_next_steps=("continue_monitoring",),
        )
        return output, ModelCallReceipt(
            provider_id="fixture",
            model_id="fixture",
            architecture_id=request.architecture_id,
            role_id=request.role_id,
            prompt_digest=request.prompt.digest,
            request_digest="sha256:" + "1" * 64,
            raw_response_digest="sha256:" + "2" * 64,
            parsed_output_digest=output.output_digest,
            input_tokens=100,
            output_tokens=40,
            elapsed_ms=2,
        )


class _AbstainingProvider(_Provider):
    def generate(self, request):
        output = ArchitectureReviewOutput(
            architecture_id=request.architecture_id,
            status="ABSTAINED_AGENT_OUTPUT",
            severity=0,
            summary="Model output was unavailable; deterministic abstention applied.",
            uncertainties=("provider_error:BadRequestError:invalid_json_schema:400",),
            human_review_required=True,
            effects=(),
        )
        return output, ModelCallReceipt(
            provider_id="fixture",
            model_id="fixture",
            architecture_id=request.architecture_id,
            role_id=request.role_id,
            prompt_digest=request.prompt.digest,
            request_digest="sha256:" + "3" * 64,
            raw_response_digest="sha256:" + "4" * 64,
            parsed_output_digest=output.output_digest,
            elapsed_ms=1,
            warnings=("provider_error",),
        )


def _row():
    return {
        "date": "2017-12-01",
        "data_available_at": NOW.isoformat(),
        "daily_return": 0.001,
        "annualised_volatility": 0.15,
        "drawdown": 0.02,
        "cash_weight": 0.1,
        "largest_issuer_weight": 0.2,
        "largest_sector_weight": 0.4,
        "warnings": [],
        "ravenpack_events": {
            "count": 0,
            "high_relevance": 0,
            "high_relevance_negative": 0,
            "maximum_relevance": None,
            "first_available_at": None,
        },
        "classified_context": {
            "context_id": "classified-context-2017-12-01",
            "event_state": "quiet",
            "fundamentals": {"context_id": "fundamental-context-2017-12-01"},
        },
    }


def test_b1_and_a1_use_the_canonical_headless_mapping(monkeypatch) -> None:
    monkeypatch.setattr(runtime, "_keychain_key", lambda **_kwargs: "test-key")
    monkeypatch.setattr(runtime, "OpenAIResponsesProvider", _Provider)
    holdings = (
        {"company_name": "Alpha Holdings", "market_value": 60.0},
        {"company_name": "Beta Industries", "market_value": 40.0},
    )

    b1_output, b1_receipt = runtime.execute_agent_cycle(
        workflow_id="B1", run_id="run-b1", case_id="case-01",
        portfolio_id="diversified", row=_row(), holdings=holdings,
        cycle_at=NOW, trigger_available_at=NOW,
        previous_assessment_state=None, previous_severity=None,
    )
    assert b1_output.architecture_type == "single_agent"
    assert b1_output.execution_summary.model_calls == 1
    assert b1_receipt["model_calls"] == 1
    assert b1_receipt["processing_clock"]["replay_paused_at"] == b1_receipt["processing_clock"]["replay_resumed_at"]
    assert b1_receipt["processing_clock"]["processing_wall_ms"] >= b1_receipt["processing_clock"]["model_processing_ms"]
    assert b1_receipt["execution_timing"]["price_policy"] == "first_eligible_end_of_day_close"
    assert b1_receipt["execution_timing"]["intraday_alpha_decay_identifiable"] is False

    a1_output, a1_receipt = runtime.execute_agent_cycle(
        workflow_id="A1", run_id="run-a1", case_id="case-01",
        portfolio_id="diversified", row=_row(), holdings=holdings,
        cycle_at=NOW, trigger_available_at=NOW,
        previous_assessment_state=None, previous_severity=None,
    )
    assert a1_output.architecture_type == "agent_graph"
    assert a1_output.execution_summary.model_calls == 4
    assert len(a1_output.architecture_behavior.contributions) == 4
    assert a1_output.architecture_behavior.handoff_count == 3
    assert a1_receipt["model_calls"] == 4


def test_model_abstention_cannot_erase_deterministic_mandate_findings(monkeypatch) -> None:
    monkeypatch.setattr(runtime, "_keychain_key", lambda **_kwargs: "test-key")
    monkeypatch.setattr(runtime, "OpenAIResponsesProvider", _AbstainingProvider)
    row = _row()
    row["cash_weight"] = 0.02
    row["warnings"] = [{
        "level": "urgent",
        "reason": "Minimum cash reserve",
        "rule_id": "cash-minimum",
        "metric": "cash_weight",
        "observed_value": 0.02,
        "threshold": 0.05,
        "threshold_distance": 0.6,
        "metric_quality": "complete",
        "evidence_ids": [
            "metric:cash_weight:2017-12-01",
            "mandate:diversified@1.0.0",
        ],
    }]
    output, receipt = runtime.execute_agent_cycle(
        workflow_id="B1", run_id="run-b1-abstain", case_id="case-01",
        portfolio_id="diversified", row=row,
        holdings=({"company_name": "Alpha Holdings", "market_value": 100.0},),
        cycle_at=NOW, trigger_available_at=NOW,
        previous_assessment_state=None, previous_severity=None,
    )
    assert output.assessment_state == "alert"
    assert output.severity == 3
    assert len(output.findings) == 1
    assert output.findings[0].metric_id == "cash-weight"
    assert output.decision.portfolio_action == "review_exposure"
    assert output.capabilities_used == (runtime.CONTEXT_CAPABILITY_ID,)
    assert output.execution_summary.capability_calls == 1
    assert receipt["critic_passed"] is True
