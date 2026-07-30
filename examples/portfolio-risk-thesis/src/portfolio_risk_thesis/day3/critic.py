"""Deterministic critic. It never repairs an invalid model output."""
import json
import re

from .contracts import (
    ArchitectureInputBundle, ArchitectureReviewOutput, CriticReport,
    CriticViolation, TRANSACTION_MARKERS, contains_private_material,
)


NUMBER = re.compile(r"(?<![\w-])[+-]?\d+(?:\.\d+)?%?")
SAFE_EFFECT_DISCLOSURES = (
    "no network, broker, order, trade, rebalance or portfolio mutation effect.",
    "no network, provider, broker, order, trade, rebalance or portfolio mutation effect.",
    "no network, broker, order, trade, rebalance, optimization or portfolio mutation effect.",
)


def critic(
    output: ArchitectureReviewOutput,
    bundle: ArchitectureInputBundle,
    expected_architecture: str | None = None,
) -> CriticReport:
    violations: list[CriticViolation] = []
    positions = {item.position_alias for item in bundle.exposures}
    events = {item.event_id for item in bundle.events}
    evidence = set(bundle.evidence_refs) | {event.evidence_digest for event in bundle.events}
    severity_by_status = {
        "NO_ISSUE": {0},
        "REVIEW": {1, 2},
        "URGENT_REVIEW": {3},
        "ABSTAIN": {0},
        "ABSTAINED_AGENT_OUTPUT": {0},
    }
    if output.severity not in severity_by_status[output.status]:
        violations.append(CriticViolation(code="severity", message="status and severity disagree"))
    if expected_architecture is not None and output.architecture_id != expected_architecture:
        violations.append(CriticViolation(code="architecture", message="model changed the treatment identity"))
    if set(output.affected_positions).difference(positions):
        violations.append(CriticViolation(code="position", message="output names a non-portfolio position"))
    if set(output.metric_refs).difference(bundle.metrics):
        violations.append(CriticViolation(code="metric", message="output references an unknown metric"))
    if set(output.event_refs).difference(events):
        violations.append(CriticViolation(code="event", message="output references an ineligible event"))
    if set(output.evidence_refs).difference(evidence):
        violations.append(CriticViolation(code="evidence", message="output references unknown evidence"))
    claims = output.supporting_claims + output.contradictory_claims
    claim_ids = [claim.claim_id for claim in claims]
    if len(claim_ids) != len(set(claim_ids)):
        violations.append(CriticViolation(code="claim_id", message="claim identifiers must be unique"))
    for claim in claims:
        if claim.metric_ref and bundle.metrics.get(claim.metric_ref) != claim.reported_metric_value:
            violations.append(CriticViolation(code="metric", message="claim metric value is not authoritative"))
        if claim.event_ref and claim.event_ref not in events:
            violations.append(CriticViolation(code="event", message="claim references an ineligible event"))
        if set(claim.affected_positions).difference(positions):
            violations.append(CriticViolation(code="position", message="claim names a non-portfolio position"))
        if claim.claim_type in {"metric", "event", "portfolio"} and (
            not claim.evidence_refs or set(claim.evidence_refs).difference(evidence)
        ):
            violations.append(CriticViolation(code="evidence", message="factual claim lacks authoritative evidence"))
    text = " ".join(
        (output.summary,)
        + tuple(claim.statement for claim in claims)
        + output.uncertainties
    ).casefold()
    transaction_text = text
    for disclosure in SAFE_EFFECT_DISCLOSURES:
        transaction_text = transaction_text.replace(disclosure, "")
    if any(marker in transaction_text for marker in TRANSACTION_MARKERS):
        violations.append(CriticViolation(code="effect", message="transaction instruction is prohibited"))
    if contains_private_material(output):
        violations.append(CriticViolation(code="privacy", message="output contains a private identifier or path"))

    supported_numbers: set[str] = set()
    for claim in claims:
        if claim.claim_type == "metric" and claim.reported_metric_value is not None:
            value = format(claim.reported_metric_value, "f")
            supported_numbers.add(value)
            try:
                supported_numbers.add(format(claim.reported_metric_value * 100, "f") + "%")
            except Exception:
                pass
    for token in NUMBER.findall(text):
        normalized = token.lstrip("+")
        if normalized not in supported_numbers:
            violations.append(
                CriticViolation(
                    code="numeric_claim",
                    message=f"numeric statement {json.dumps(token)} lacks a structured metric claim",
                )
            )

    return CriticReport(
        passed=not violations,
        violations=tuple(violations),
        original_output_digest=output.output_digest,
    )


def abstain(output: ArchitectureReviewOutput, report: CriticReport) -> ArchitectureReviewOutput:
    if report.passed:
        return output
    return ArchitectureReviewOutput(
        architecture_id=output.architecture_id,
        status="ABSTAINED_AGENT_OUTPUT",
        severity=0,
        summary="Agent output abstained after deterministic critic failure.",
        uncertainties=(f"Original output digest: {report.original_output_digest}",),
        human_review_required=True,
        effects=(),
    )
