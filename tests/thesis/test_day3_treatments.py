from portfolio_risk_thesis.day3.contracts import ArchitectureReviewOutput
from portfolio_risk_thesis.day3.providers import FixtureStructuredModelProvider
from portfolio_risk_thesis.day3.treatments import b0,b1,a1,ROLES
from test_day3_contracts import bundle

def output(architecture): return {"architecture_id":architecture,"status":"REVIEW","severity":1,"summary":"review","human_review_required":True,"effects":[]}
def test_call_counts_are_frozen():
    context=bundle(); responses={("B1",ROLES[-1],context.context_digest):output("B1")}
    responses.update({("A1",role,context.context_digest):output("A1") for role in ROLES})
    provider=FixtureStructuredModelProvider(responses)
    assert len(b0(context).receipts)==0; assert len(b1(context,provider).receipts)==1; assert len(a1(context,provider).receipts)==4
