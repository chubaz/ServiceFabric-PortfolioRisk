"""Deterministic, exact-digest fixture provider. It never performs I/O."""
import json

from ..contracts import (
    ArchitectureReviewOutput,
    ModelCallReceipt,
    ModelRequest,
    bytes_digest,
    canonical,
    digest,
)
from .base import StructuredModelProvider


class FixtureStructuredModelProvider(StructuredModelProvider):
    provider_id = "fixture"

    def __init__(
        self,
        responses: dict[tuple[str, str, str, str], dict[str, object]],
    ):
        self.responses = responses
        self.requests: list[ModelRequest] = []

    def prepare_request(self, request: ModelRequest) -> object:
        return canonical(request)

    def parse(self, request: ModelRequest, raw_output: str) -> ArchitectureReviewOutput:
        return ArchitectureReviewOutput.model_validate_json(raw_output)

    def receipt(
        self,
        request: ModelRequest,
        raw_output: str,
        output: ArchitectureReviewOutput,
        **metadata: object,
    ) -> ModelCallReceipt:
        return ModelCallReceipt(
            provider_id=self.provider_id,
            model_id="fixture-structured-v1",
            architecture_id=request.architecture_id,
            role_id=request.role_id,
            prompt_digest=request.prompt.digest,
            request_digest=digest(request),
            raw_response_digest=bytes_digest(raw_output.encode("utf-8")),
            parsed_output_digest=output.output_digest,
            warnings=("Deterministic fixture response; no actual model was called.",),
            limitations=("CI fixture provider only.",),
        )

    def generate(
        self,
        request: ModelRequest,
    ) -> tuple[ArchitectureReviewOutput, ModelCallReceipt]:
        self.requests.append(request)
        key = (
            request.architecture_id,
            request.role_id,
            request.prompt.digest,
            request.context_digest,
        )
        if key not in self.responses:
            raise ValueError(
                "fixture response is not registered for the exact "
                "architecture, role, prompt and context digest"
            )
        raw_output = json.dumps(
            self.responses[key],
            sort_keys=True,
            separators=(",", ":"),
        )
        output = self.parse(request, raw_output)
        return output, self.receipt(request, raw_output, output)
