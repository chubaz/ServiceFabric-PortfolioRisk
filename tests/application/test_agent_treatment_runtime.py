from datetime import datetime, timezone

import agent_treatment_runtime as runtime
from portfolio_risk_thesis.day3.contracts import ArchitectureReviewOutput, ModelCallReceipt


NOW = datetime(2017, 12, 1, 21, tzinfo=timezone.utc)


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
