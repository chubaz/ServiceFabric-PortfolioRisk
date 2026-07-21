"""Immutable role and provider contracts for Day 0 agents."""

from __future__ import annotations

from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, field_validator

from risk_capabilities import CapabilityInvocation, EvidenceReference


class AgentContract(BaseModel):
    """Common strict, immutable behavior for agent values."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)


class AgentRole(AgentContract):
    """A review-bound role card with explicitly limited capability grants."""

    role_id: str = Field(pattern=r"^risk\.agent\.[a-z_]+$")
    objective: str = Field(min_length=1)
    allowed_capability_ids: tuple[str, ...] = Field(min_length=1)
    denied_effects: tuple[str, ...] = Field(min_length=1)
    input_contracts: tuple[str, ...] = Field(min_length=1)
    output_contracts: tuple[str, ...] = Field(min_length=1)
    evidence_requirements: tuple[str, ...] = Field(min_length=1)
    escalation_policy: str = Field(min_length=1)
    human_review_required: bool = True

    @field_validator("allowed_capability_ids", "denied_effects")
    @classmethod
    def bounded_values_are_distinct(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        if len(values) != len(set(values)):
            raise ValueError("role card values must be distinct")
        return values


class AgentRunContext(AgentContract):
    """The bounded context for one provider invocation."""

    run_id: str = Field(min_length=1, max_length=256)
    role_id: str = Field(pattern=r"^risk\.agent\.[a-z_]+$")
    provider_id: str = Field(min_length=1, max_length=256)
    human_review_confirmed: bool = False


class DeterministicProviderDraft(AgentContract):
    """A non-executable draft to submit only through the canonical runtime."""

    invocation_id: str = Field(min_length=1, max_length=256)
    capability_id: str = Field(pattern=r"^risk\.capability\.[a-z_]+$")
    status: Literal["prepared", "blocked"]
    summary: str = Field(min_length=1)
    evidence_references: tuple[EvidenceReference, ...] = ()
    disclosures: tuple[str, ...] = ()
    assumptions: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()
    human_review_required: bool = True


class AgentProvider(Protocol):
    """Provider interface for non-executable drafts submitted through ServiceFabric."""

    provider_id: str

    def prepare(self, context: AgentRunContext, invocation: CapabilityInvocation) -> DeterministicProviderDraft:
        """Prepare a stable draft; the canonical runtime owns all invocation and results."""
