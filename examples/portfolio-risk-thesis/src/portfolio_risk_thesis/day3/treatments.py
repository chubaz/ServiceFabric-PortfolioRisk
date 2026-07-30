"""The fixed B0, B1, and A1 treatment definitions and execution order."""
from .contracts import (
    ArchitectureInputBundle, ArchitectureReviewOutput, ArchitectureRun,
    ArchitectureTreatmentDefinition, ModelRequest, NEXT_STEPS, ROLE_IDS,
    SpecialistAgentOutput,
)
from .critic import abstain, critic
from .prompts import prompt_reference
from .providers.base import StructuredModelProvider

ROLES = ROLE_IDS


def definitions() -> tuple[ArchitectureTreatmentDefinition, ...]:
    return (
        ArchitectureTreatmentDefinition(architecture_id="B0", role_ids=(), model_calls=0),
        ArchitectureTreatmentDefinition(architecture_id="B1", role_ids=(ROLE_IDS[-1],), model_calls=1),
        ArchitectureTreatmentDefinition(architecture_id="A1", role_ids=ROLE_IDS, model_calls=4),
    )


def role_payload(bundle: ArchitectureInputBundle, role_id: str, specialists: dict[str, object] | None = None) -> dict[str, object]:
    """Return the exact bounded context granted to one role."""
    safe = bundle.model_safe()
    common = {
        "portfolio_id": safe["portfolio_id"],
        "as_of": safe["as_of"],
        "evidence_refs": safe["evidence_refs"],
    }
    if role_id == "risk.agent.market_data":
        return common | {
            "metrics": safe["metrics"],
            "warnings": safe["warnings"],
            "limitations": safe["limitations"],
        }
    if role_id == "risk.agent.portfolio_exposure":
        return common | {"exposures": safe["exposures"]}
    if role_id == "risk.agent.news_sentiment":
        return common | {
            "events": safe["events"],
            "limitations": safe["limitations"],
        }
    if role_id == "risk.agent.alert_recommendation":
        return common | {
            "deterministic_finding": safe["deterministic_finding"],
            "review_item": safe["review_item"],
            "decision_point": safe["decision_point"],
            "specialist_outputs": specialists or {},
            "permitted_next_steps": list(NEXT_STEPS),
        }
    raise ValueError(f"unknown Day 3 role: {role_id}")


def _prompt_id(architecture: str, role: str) -> str:
    if architecture == "B1":
        return "b1-synthesizer"
    return {
        ROLE_IDS[0]: "a1-market-data",
        ROLE_IDS[1]: "a1-portfolio-exposure",
        ROLE_IDS[2]: "a1-news-sentiment",
        ROLE_IDS[3]: "a1-alert-synthesis",
    }[role]


def _request(
    bundle: ArchitectureInputBundle,
    architecture: str,
    role: str,
    payload: dict[str, object],
) -> ModelRequest:
    return ModelRequest(
        architecture_id=architecture,
        role_id=role,
        prompt=prompt_reference(_prompt_id(architecture, role)),
        system_prompt=prompt_reference("common-system"),
        context_digest=bundle.context_digest,
        payload=payload,
    )


def b0(bundle: ArchitectureInputBundle) -> ArchitectureRun:
    status = bundle.decision_point
    if status not in {"NO_ISSUE", "REVIEW", "URGENT_REVIEW", "ABSTAIN"}:
        status = "ABSTAIN"
    severity = {"NO_ISSUE": 0, "REVIEW": 1, "URGENT_REVIEW": 3, "ABSTAIN": 0}[status]
    next_step = {
        "NO_ISSUE": "record_no_action",
        "REVIEW": "continue_monitoring",
        "URGENT_REVIEW": "investigate_market_cause",
        "ABSTAIN": "investigate_data_quality",
    }[status]
    output = ArchitectureReviewOutput(
        architecture_id="B0",
        status=status,
        severity=severity,
        summary=(
            f"Deterministic finding: {bundle.deterministic_finding}. "
            f"Review item: {bundle.review_item}. "
            f"Kernel decision: {bundle.decision_point}."
        ),
        evidence_refs=bundle.evidence_refs,
        uncertainties=bundle.warnings + bundle.limitations,
        recommended_next_steps=(next_step,),
    )
    report = critic(output, bundle, "B0")
    return ArchitectureRun(
        architecture_id="B0",
        context_digest=bundle.context_digest,
        output=abstain(output, report),
        critic=report,
        receipts=(),
    )


def b1(bundle: ArchitectureInputBundle, provider: StructuredModelProvider) -> ArchitectureRun:
    output, receipt = provider.generate(_request(bundle, "B1", ROLE_IDS[-1], bundle.model_safe()))
    report = critic(output, bundle, "B1")
    return ArchitectureRun(
        architecture_id="B1",
        context_digest=bundle.context_digest,
        output=abstain(output, report),
        critic=report,
        receipts=(receipt,),
    )


def a1(bundle: ArchitectureInputBundle, provider: StructuredModelProvider) -> ArchitectureRun:
    receipts = []
    specialist_outputs: dict[str, object] = {}
    retained_specialists: list[SpecialistAgentOutput] = []
    final: ArchitectureReviewOutput | None = None
    for role in ROLE_IDS:
        output, receipt = provider.generate(_request(bundle, "A1", role, role_payload(bundle, role, specialist_outputs)))
        receipts.append(receipt)
        if role == ROLE_IDS[-1]:
            final = output
        else:
            specialist_outputs[role] = output.model_dump(mode="json", exclude={"output_digest"})
            retained_specialists.append(SpecialistAgentOutput(role_id=role, output=output))
    assert final is not None
    report = critic(final, bundle, "A1")
    return ArchitectureRun(
        architecture_id="A1",
        context_digest=bundle.context_digest,
        output=abstain(final, report),
        critic=report,
        receipts=tuple(receipts),
        specialist_outputs=tuple(retained_specialists),
    )
