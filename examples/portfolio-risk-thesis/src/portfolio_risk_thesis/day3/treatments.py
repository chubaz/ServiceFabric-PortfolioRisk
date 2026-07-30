from .contracts import *
from .critic import critic, abstain
from .providers.base import StructuredModelProvider
ROLES=("risk.agent.market_data","risk.agent.portfolio_exposure","risk.agent.news_sentiment","risk.agent.alert_recommendation")

def definitions(): return (ArchitectureTreatmentDefinition(architecture_id="B0",role_ids=(),model_calls=0),ArchitectureTreatmentDefinition(architecture_id="B1",role_ids=("risk.agent.alert_recommendation",),model_calls=1),ArchitectureTreatmentDefinition(architecture_id="A1",role_ids=ROLES,model_calls=4))
def _request(bundle, architecture, role): return ModelRequest(architecture_id=architecture,role_id=role,prompt=PromptReference(prompt_id=role,version="v1",digest=digest(role),role=role),context_digest=bundle.context_digest,payload=bundle.model_safe())
def b0(bundle):
    output=ArchitectureReviewOutput(architecture_id="B0",status="REVIEW",severity=1,summary=bundle.deterministic_finding,evidence_refs=bundle.evidence_refs,recommended_next_steps=("continue_monitoring",))
    report=critic(output,bundle); return ArchitectureRun(architecture_id="B0",context_digest=bundle.context_digest,output=abstain(output,report),critic=report,receipts=())
def b1(bundle, provider):
    output,receipt=provider.generate(_request(bundle,"B1","risk.agent.alert_recommendation")); report=critic(output,bundle)
    return ArchitectureRun(architecture_id="B1",context_digest=bundle.context_digest,output=abstain(output,report),critic=report,receipts=(receipt,))
def a1(bundle, provider):
    receipts=[]; output=None
    for role in ROLES: output,receipt=provider.generate(_request(bundle,"A1",role)); receipts.append(receipt)
    report=critic(output,bundle); return ArchitectureRun(architecture_id="A1",context_digest=bundle.context_digest,output=abstain(output,report),critic=report,receipts=tuple(receipts))
