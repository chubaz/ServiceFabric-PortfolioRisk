from .contracts import *

def critic(output: ArchitectureReviewOutput, bundle: ArchitectureInputBundle) -> CriticReport:
    violations=[]; known_positions={x.position_alias for x in bundle.exposures}; known_events={x.event_id for x in bundle.events}; evidence=set(bundle.evidence_refs)|{e.evidence_digest for e in bundle.events}
    for claim in output.supporting_claims + output.contradictory_claims:
        if claim.metric_ref and bundle.metrics.get(claim.metric_ref) != claim.reported_metric_value: violations.append(CriticViolation(code="metric",message="unknown or mismatched metric"))
        if claim.event_ref and claim.event_ref not in known_events: violations.append(CriticViolation(code="event",message="ineligible event"))
        if set(claim.affected_positions).difference(known_positions): violations.append(CriticViolation(code="position",message="unknown portfolio position"))
        if claim.claim_type in ("metric","event","portfolio") and (not claim.evidence_refs or set(claim.evidence_refs).difference(evidence)): violations.append(CriticViolation(code="evidence",message="unsupported claim"))
    text=(output.summary+" "+" ".join(c.statement for c in output.supporting_claims)).lower()
    if any(x in text for x in ("buy ","sell ","trade","broker","rebalance","order ")): violations.append(CriticViolation(code="effect",message="transaction instruction"))
    return CriticReport(passed=not violations, violations=tuple(violations))

def abstain(output: ArchitectureReviewOutput, report: CriticReport) -> ArchitectureReviewOutput:
    if report.passed: return output
    return ArchitectureReviewOutput(architecture_id=output.architecture_id,status="ABSTAINED_AGENT_OUTPUT",severity=0,summary="Agent output abstained after deterministic critic failure.",human_review_required=True,effects=())
