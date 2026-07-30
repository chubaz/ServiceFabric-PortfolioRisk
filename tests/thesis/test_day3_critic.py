from portfolio_risk_thesis.day3 import ArchitectureReviewOutput, critic, abstain
from test_day3_contracts import bundle
def test_critic_abstains_invalid_metric():
    output=ArchitectureReviewOutput(architecture_id="B1",status="REVIEW",severity=1,summary="x",supporting_claims=({"claim_id":"c","statement":"x","claim_type":"metric","metric_ref":"unknown","reported_metric_value":"1","evidence_refs":["e1"]},))
    report=critic(output,bundle()); assert not report.passed; assert abstain(output,report).status=="ABSTAINED_AGENT_OUTPUT"
