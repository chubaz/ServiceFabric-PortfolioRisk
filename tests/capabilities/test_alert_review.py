from risk_capabilities import AlertDraft, AlertReviewRequest, CapabilityRegistry, DecisionPoint, EvidenceReference


def test_alert_review_records_human_decision_without_external_effect() -> None:
    evidence = (EvidenceReference(evidence_id="review-evidence", reference="fixture://synthetic/review", source_type="synthetic_fixture"),)
    draft = AlertDraft(alert_id="alert-test", summary="Synthetic review draft", suggested_next_steps=("investigation",))
    decision = DecisionPoint(decision_id="decision-test", alert_id=draft.alert_id, decision="request_changes", rationale="Need additional scenario context.", human_reviewer_id="reviewer-1")
    result = CapabilityRegistry().invoke("alert.draft.review", AlertReviewRequest(draft=draft, decision_point=decision, evidence_references=evidence))
    assert result.status == "succeeded"
    assert result.data.decision_point == decision
    assert result.effects == ()
