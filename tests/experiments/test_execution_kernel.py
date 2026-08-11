from datetime import datetime, timedelta, timezone

import pytest

from risk_agents import (
    AgentCapabilityUse,
    AgentDecisionByproduct,
    AgentEvaluationByproducts,
    AgentFindingByproduct,
    AgentPresentationArtifact,
    AgentRuntimeTelemetry,
    AgentStructuredOutput,
    CapabilityReceipt,
    wrap_agent_execution,
)
from risk_capabilities import EvidenceReference
from risk_experiments import (
    ArchitectureMappingContext,
    ArchitectureMappingError,
    GraphExecutionEnvelope,
    KernelEvidence,
    compare_critic_revision,
    finalize_agent_graph_execution,
    finalize_single_agent_execution,
    map_agent_output,
    wrap_agent_graph,
)


AS_OF = datetime(2020, 1, 2, 16, tzinfo=timezone.utc)
DIGEST_A = "sha256:" + "a" * 64
DIGEST_B = "sha256:" + "b" * 64
DIGEST_C = "sha256:" + "c" * 64


def _receipt(evidence_id: str = "evidence-01") -> CapabilityReceipt:
    return CapabilityReceipt(
        capability_id="risk.capability.market_data",
        status="succeeded",
        input_digest=DIGEST_A,
        output_digest=DIGEST_B,
        evidence=(EvidenceReference(
            evidence_id=evidence_id,
            reference=f"observation:{evidence_id}",
            source_type="runtime-observation",
        ),),
        methodology="registered-capability",
    )


def _output(
    evidence_id: str = "evidence-01",
    *,
    architecture_type: str = "single_agent",
    experimental_role: str = "final_decision_agent",
    output_id: str = "agent-output-01",
    agent_id: str = "risk.agent.specialist",
    participants: tuple[str, ...] | None = None,
    cluster_key: str = "issuer-loss",
    severity: int = 3,
    confidence: float = 0.8,
    advisory_action: str = "continue_monitoring",
) -> AgentStructuredOutput:
    agent_ids = participants or (agent_id,)
    decision = AgentDecisionByproduct(
        decision_id=f"decision-{output_id}",
        decision_scope=(
            "architecture_final" if experimental_role == "final_decision_agent" else "node_advisory"
        ),
        monitoring_action=advisory_action,
        portfolio_action="none",
        rationale_finding_ids=(f"finding-{output_id}",),
        alternatives_considered=("continue_monitoring", "review_exposure"),
    )
    return AgentStructuredOutput(
        output_id=output_id,
        run_id="run-01",
        cycle_id="cycle-01",
        architecture_id="agent-architecture-01",
        architecture_type=architecture_type,
        experimental_role=experimental_role,
        as_of=AS_OF,
        produced_at=AS_OF + timedelta(seconds=2),
        output_contract="DailyPortfolioRiskReview/v1",
        primary_artifact={"structured_result": "headless risk analysis"},
        presentation_artifacts=(AgentPresentationArtifact(
            artifact_id=f"presentation-{output_id}",
            label="Optional human-readable review",
            media_type="text/markdown",
            reference=f"presentation/{output_id}.md",
            content_digest=DIGEST_C,
        ),),
        evaluation_byproducts=AgentEvaluationByproducts(
            assessment_state="alert",
            findings=(AgentFindingByproduct(
                finding_id=f"finding-{output_id}",
                cluster_key=cluster_key,
                claim="The issuer loss threshold is materially breached.",
                risk_type="loss",
                affected_asset="Example Issuer",
                direction="negative",
                materiality=0.9,
                severity=severity,
                confidence=confidence,
                confidence_method="Agent judgement constrained by the finding schema.",
                evidence_ids=(evidence_id,),
                metric_id="daily-return",
                observed_value=-0.08,
                threshold_value=-0.04,
                observed_at=AS_OF,
            ),),
            risk_interpretation="The loss is large relative to the active mandate threshold.",
            expectations="Continued weakness would keep the finding open.",
            confidence=confidence,
            confidence_kind="ordinal_judgement",
            confidence_method="Schema-constrained agent judgement awaiting empirical calibration.",
            decision=decision,
            supporting_evidence_ids=(evidence_id,),
            classified_context_ids=("classified-context-01",),
            missing_information=("later outcome",),
            assumptions=("mandate threshold is active",),
            data_quality_score=0.9,
        ),
        agent_ids=agent_ids,
        capability_uses=(AgentCapabilityUse(
            receipt=_receipt(evidence_id),
            started_at=AS_OF,
            completed_at=AS_OF + timedelta(seconds=1),
        ),),
    )


def _execution(output: AgentStructuredOutput, agent_id: str, *, offset_ms: int = 0):
    return wrap_agent_execution(
        output,
        AgentRuntimeTelemetry(
            agent_id=agent_id,
            agent_version="0.1.0",
            started_at=AS_OF + timedelta(milliseconds=offset_ms),
            first_finding_at=AS_OF + timedelta(seconds=1, milliseconds=offset_ms),
            completed_at=AS_OF + timedelta(seconds=2, milliseconds=offset_ms),
            model_calls=1,
            input_tokens=120,
            cached_input_tokens=20,
            output_tokens=40,
            cost_usd=0.001,
            capability_calls=1,
            route=("gather", "interpret"),
        ),
    )


def _context(
    evidence_id: str = "evidence-01",
    *,
    available_at: datetime | None = None,
    architecture_type: str = "single_agent",
    agents: tuple[str, ...] = ("risk.agent.specialist",),
) -> ArchitectureMappingContext:
    return ArchitectureMappingContext(
        run_id="run-01",
        cycle_id="cycle-01",
        architecture_id="agent-architecture-01",
        architecture_type=architecture_type,
        as_of=AS_OF,
        trigger_available_at=AS_OF - timedelta(minutes=1),
        input_context_digest=DIGEST_A,
        case_id="case-01",
        repetition=1,
        eligible_evidence=(KernelEvidence(
            evidence_id=evidence_id,
            available_at=available_at or AS_OF,
        ),),
        allowed_capability_ids=("risk.capability.market_data",),
        allowed_agent_ids=agents,
        classified_context_ids=("classified-context-01",),
    )


def test_single_agent_wrapper_populates_all_behavioral_evaluation_inputs() -> None:
    output = _output()
    mapped = finalize_single_agent_execution(
        _execution(output, "risk.agent.specialist"),
        _context(),
        mapped_at=AS_OF + timedelta(seconds=3),
    )

    assert mapped.findings[0].confidence == 0.8
    assert mapped.decision.monitoring_action == "continue_monitoring"
    assert mapped.source_output_digest == output.output_digest
    assert mapped.trigger_available_at == AS_OF - timedelta(minutes=1)
    assert mapped.input_context_digest == DIGEST_A
    assert mapped.execution_summary is not None
    assert mapped.execution_summary.input_tokens == 120
    assert mapped.execution_summary.model_calls == 1
    assert mapped.architecture_behavior is not None
    assert len(mapped.architecture_behavior.contributions) == 1
    assert output.presentation_artifacts[0].evaluation_status == "excluded_user_facing"


def test_graph_wrapper_aggregates_disagreement_coordination_and_critic_correction() -> None:
    participants = ("risk.agent.market", "risk.agent.credit", "risk.agent.synthesizer")
    market = _output(
        architecture_type="agent_graph", experimental_role="specialist_node",
        output_id="market-output", agent_id=participants[0], cluster_key="market-loss",
        confidence=0.7, advisory_action="increase_monitoring",
    )
    credit = _output(
        architecture_type="agent_graph", experimental_role="specialist_node",
        output_id="credit-output", agent_id=participants[1], cluster_key="credit-event",
        confidence=0.5, severity=2, advisory_action="continue_monitoring",
    )
    final = _output(
        architecture_type="agent_graph", experimental_role="final_decision_agent",
        output_id="final-output", agent_id=participants[2], participants=participants,
        cluster_key="market-loss", confidence=0.75,
    )
    executions = (
        _execution(market, participants[0]),
        _execution(credit, participants[1], offset_ms=200),
        _execution(final, participants[2], offset_ms=400),
    )
    correction = compare_critic_revision(
        market,
        market.model_copy(update={"output_id": "market-revised", "output_digest": None}),
        critic_agent_id=participants[1],
        accepted=True,
    )
    graph = wrap_agent_graph(
        executions,
        final_output_id="final-output",
        started_at=AS_OF,
        completed_at=AS_OF + timedelta(seconds=4),
        edge_traversals=("market->synthesizer", "credit->synthesizer"),
        handoff_count=2,
        synthesis_ms=500,
        critic_corrections=(correction,),
    )
    mapped = finalize_agent_graph_execution(
        graph,
        _context(architecture_type="agent_graph", agents=participants),
        mapped_at=AS_OF + timedelta(seconds=5),
    )

    behavior = mapped.architecture_behavior
    assert behavior is not None
    assert len(behavior.contributions) == 3
    assert behavior.finding_disagreement == 1.0
    assert behavior.severity_dispersion > 0
    assert behavior.confidence_dispersion > 0
    assert behavior.decision_disagreement == 1.0
    assert behavior.handoff_count == 2
    assert behavior.coordination_overhead_ms > 0
    assert len(behavior.critic_corrections) == 1
    assert mapped.execution_summary.model_calls == 3
    assert mapped.execution_summary.input_tokens == 360


def test_specialist_node_cannot_be_mapped_as_architecture_result() -> None:
    specialist = _output(
        architecture_type="agent_graph", experimental_role="specialist_node",
        output_id="specialist-output",
    )
    with pytest.raises(ArchitectureMappingError, match="not-final-output"):
        map_agent_output(
            specialist,
            _context(architecture_type="agent_graph"),
            mapped_at=AS_OF + timedelta(seconds=3),
        )


def test_wrapper_rejects_output_created_before_observed_execution() -> None:
    output = _output()
    with pytest.raises(ValueError, match="inside wrapped execution"):
        wrap_agent_execution(
            output,
            AgentRuntimeTelemetry(
                agent_id="risk.agent.specialist",
                agent_version="0.1.0",
                started_at=AS_OF + timedelta(seconds=3),
                completed_at=AS_OF + timedelta(seconds=4),
            ),
        )


def test_graph_wrapper_rejects_more_than_one_final_decision_contribution() -> None:
    participants = ("risk.agent.market", "risk.agent.final-a", "risk.agent.final-b")
    specialist = _output(
        architecture_type="agent_graph", experimental_role="specialist_node",
        output_id="market-output", agent_id=participants[0],
    )
    final_a = _output(
        architecture_type="agent_graph", output_id="final-a",
        agent_id=participants[1], participants=participants,
    )
    final_b = _output(
        architecture_type="agent_graph", output_id="final-b",
        agent_id=participants[2], participants=participants,
    )
    with pytest.raises(ValueError, match="exactly one final decision contribution"):
        GraphExecutionEnvelope(
            graph_execution_id="graph-execution-invalid",
            executions=(
                _execution(specialist, participants[0]),
                _execution(final_a, participants[1]),
                _execution(final_b, participants[2]),
            ),
            final_output_id="final-a",
            started_at=AS_OF,
            completed_at=AS_OF + timedelta(seconds=5),
        )


def test_mapper_stops_unknown_and_look_ahead_evidence() -> None:
    with pytest.raises(ArchitectureMappingError) as unknown:
        map_agent_output(
            _output("evidence-unknown"), _context(),
            mapped_at=AS_OF + timedelta(seconds=3),
        )
    assert {code for code, _ in unknown.value.violations} == {"evidence-not-eligible"}

    with pytest.raises(ArchitectureMappingError) as look_ahead:
        map_agent_output(
            _output(), _context(available_at=AS_OF + timedelta(days=1)),
            mapped_at=AS_OF + timedelta(seconds=3),
        )
    assert "look-ahead-evidence" in {code for code, _ in look_ahead.value.violations}


def test_mapper_requires_exact_cycle_identity() -> None:
    context = _context().model_copy(update={"cycle_id": "cycle-02"})
    with pytest.raises(ArchitectureMappingError) as caught:
        map_agent_output(_output(), context, mapped_at=AS_OF + timedelta(seconds=3))
    assert "context-mismatch" in {code for code, _ in caught.value.violations}
