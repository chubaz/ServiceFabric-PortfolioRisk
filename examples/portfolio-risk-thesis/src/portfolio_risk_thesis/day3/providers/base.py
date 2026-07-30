from abc import ABC, abstractmethod
from ..contracts import ModelRequest, ModelCallReceipt, ArchitectureReviewOutput
class StructuredModelProvider(ABC):
    provider_id: str
    @abstractmethod
    def generate(self, request: ModelRequest) -> tuple[ArchitectureReviewOutput, ModelCallReceipt]: ...
