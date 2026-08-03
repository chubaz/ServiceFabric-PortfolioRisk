"""Strict structured-provider interface for the research-local experiment."""
from abc import ABC, abstractmethod

from ..contracts import ArchitectureReviewOutput, ModelCallReceipt, ModelRequest


class StructuredModelProvider(ABC):
    provider_id: str

    @abstractmethod
    def prepare_request(self, request: ModelRequest) -> object: ...

    @abstractmethod
    def parse(self, request: ModelRequest, raw_output: str) -> ArchitectureReviewOutput: ...

    @abstractmethod
    def receipt(
        self,
        request: ModelRequest,
        raw_output: str,
        output: ArchitectureReviewOutput,
        **metadata: object,
    ) -> ModelCallReceipt: ...

    @abstractmethod
    def generate(self, request: ModelRequest) -> tuple[ArchitectureReviewOutput, ModelCallReceipt]: ...
