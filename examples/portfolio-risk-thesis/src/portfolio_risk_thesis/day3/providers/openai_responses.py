"""Explicit local-only Responses API adapter; it never falls back to fixtures."""
import os
from ..contracts import *
from .base import StructuredModelProvider
class OpenAIResponsesProvider(StructuredModelProvider):
    provider_id="openai_responses"
    def __init__(self, configuration: ModelConfiguration):
        if not os.environ.get("OPENAI_API_KEY"): raise ValueError("OPENAI_API_KEY is required")
        if not configuration.model_snapshot or configuration.store or configuration.tools: raise ValueError("unsafe model configuration")
        self.configuration=configuration
    def generate(self, request):
        try:
            from openai import OpenAI
            client=OpenAI(timeout=self.configuration.timeout_seconds, max_retries=self.configuration.retry_count)
            response=client.responses.create(model=self.configuration.model_snapshot,input=request.payload,store=False,tools=[],text={"format":{"type":"json_schema","name":"architecture_review","strict":True,"schema":ArchitectureReviewOutput.model_json_schema()}})
            output=ArchitectureReviewOutput.model_validate_json(response.output_text)
            usage=getattr(response,"usage",None)
            return output,ModelCallReceipt(provider_id=self.provider_id,model_id=self.configuration.model_snapshot,request_digest=digest(request),parsed_output_digest=output.output_digest,input_tokens=getattr(usage,"input_tokens",0),output_tokens=getattr(usage,"output_tokens",0),response_id=getattr(response,"id",None))
        except Exception as error: raise RuntimeError("OpenAI structured model request failed; no provider fallback") from error
