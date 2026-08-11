from datetime import datetime

from risk_experiments import (
    FixtureContext, build_calibration_pilot, calibration_acceptance_record,
    calibration_source_manifest, compile_arm_plan, compile_label_gate, compile_matrix,
    MandateVersion, RiskPolicySet,
)


def _context():
    candidate = build_calibration_pilot()
    return FixtureContext(
        object_set=candidate,
        acceptance=calibration_acceptance_record(candidate),
        sources=calibration_source_manifest(),
        reachable_capability_references=tuple(item.reference for item in candidate.resource_envelope.capability_pack.capabilities),
        reachable_dataset_references=tuple(item.reference for item in candidate.world_context.data_manifest.datasets),
        fixture_context_digest=candidate.fixture_context_digest,
    )


def test_p9_arm_plan_is_exact_and_honestly_blocked():
    dates = tuple(datetime.fromisoformat(f"2024-04-{day:02d}T17:00:00+00:00") for day in range(1, 6))
    plan = compile_arm_plan(_context(), dates)
    assert [item.arm_id for item in plan.arms] == ["b0", "a1"]
    assert plan.expected_outputs == 10
    assert not plan.executable
    assert {item.issue_id for item in plan.blockers} == {"point-in-time-prices-unbound", "processing-identities-unqualified"}


def test_p10_labels_remain_sealed_and_p11_matrix_is_repeatable():
    dates = tuple(datetime.fromisoformat(f"2024-04-{day:02d}T17:00:00+00:00") for day in range(1, 6))
    plan = compile_arm_plan(_context(), dates)
    gate = compile_label_gate(_context(), plan)
    assert gate.status == "awaiting_independent_review"
    assert gate.labels_reachable_by_processing is False
    first = compile_matrix(_context(), plan, repeats=2)
    second = compile_matrix(_context(), plan, repeats=2)
    assert len(first.cells) == 4
    assert first.planned_observations == 20
    assert first.matrix_digest == second.matrix_digest
    assert first.execution_status == "blocked"


def test_accepted_p7_governance_objects_remain_readable_after_richer_contracts():
    mandate = MandateVersion.model_validate({
        "kind": "mandate", "namespace": "portfolio-risk.thesis", "object_id": "calibration-mandate", "version": "1.0.0", "name": "Calibration pilot mandate",
        "object_digest": "sha256:3f9a2e5f40a74d50e56a1c9a1871cab2a467a8679cce32bf2ba94a4bd67ef9a3",
        "objective": "Preserve capital in a fictional diversified portfolio while testing effect-free concentration-risk assessment.",
        "horizon_seconds": 31557600, "eligible_universe_reference": "universe:reviewed-synthetic-securities@1.0.0",
        "constraints": [{"constraint_id": "largest-position", "category": "concentration", "statement": "Largest position weight must not exceed 35%."}],
        "effective_from": "2024-01-02T00:00:00Z", "effective_until": None,
    })
    policy = RiskPolicySet.model_validate({
        "kind": "risk_policy", "namespace": "portfolio-risk.thesis", "object_id": "calibration-risk-policy", "version": "1.0.0", "name": "Calibration concentration policy",
        "object_digest": "sha256:7bac2e5f5e4c06bf5a16d2917376fc6cfad346f0c4c3cac772cc9997c1e656c6", "mandate_reference": mandate.reference,
        "rules": [{"rule_id": "largest-position", "metric_reference": "metric:risk:largest-position-weight@1.0.0", "operator": "lte", "threshold": "0.35", "severity": "breach", "escalation": "human_review"}],
        "conflict_rule": "most_restrictive_wins", "missing_metric_rule": "abstain_and_escalate",
    })
    assert mandate.object_digest.endswith("f9a3")
    assert policy.object_digest.endswith("56c6")
