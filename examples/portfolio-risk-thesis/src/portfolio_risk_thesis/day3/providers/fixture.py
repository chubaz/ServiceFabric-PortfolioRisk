from ..contracts import *
from .base import StructuredModelProvider
class FixtureStructuredModelProvider(StructuredModelProvider):
    provider_id="fixture"
    def __init__(self, responses: dict[tuple[str,str,str],dict]): self.responses=responses
    def generate(self, request):
        key=(request.architecture_id,request.role_id,request.context_digest)
        if key not in self.responses: raise ValueError("fixture response is not registered for exact context digest")
        output=ArchitectureReviewOutput.model_validate(self.responses[key])
        receipt=ModelCallReceipt(provider_id=self.provider_id,model_id="fixture",request_digest=digest(request),parsed_output_digest=output.output_digest)
        return output,receipt
