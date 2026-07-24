"""Immutable, bounded capability contracts for Day 0."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class CapabilityContract(BaseModel):
    """Common strict, immutable behavior for capability values."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)


class EvidenceReference(CapabilityContract):
    """An opaque reference to evidence supplied by an upstream contract."""

    evidence_id: str = Field(min_length=1, max_length=256)
    reference: str = Field(min_length=1, max_length=2048)
    source_type: str = Field(min_length=1, max_length=128)
    digest: str | None = Field(default=None, pattern=r"^sha256:[0-9a-f]{64}$")
    description: str | None = Field(default=None, min_length=1, max_length=2048)


class CapabilityInput(CapabilityContract):
    """A single immutable, non-credential input value for a capability draft."""

    name: str = Field(pattern=r"^[a-z][a-z0-9_]{0,127}$")
    value: str | int | float | bool | None

    @field_validator("name")
    @classmethod
    def name_is_not_credential_like(cls, value: str) -> str:
        forbidden_fragments = ("api_key", "apikey", "password", "secret", "token", "credential")
        if any(fragment in value.lower() for fragment in forbidden_fragments):
            raise ValueError("capability inputs must not contain credential-like names")
        return value


class CapabilityDescriptor(CapabilityContract):
    """A declared, non-executable description of a bounded capability."""

    capability_id: str = Field(pattern=r"^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*){1,3}$")
    objective: str = Field(min_length=1)
    input_contract: str = Field(min_length=1)
    output_contract: str = Field(min_length=1)
    allowed_effects: tuple[str, ...] = ()
    denied_effects: tuple[str, ...] = ()
    requires_evidence: bool = True
    requires_human_review: bool = True

    @field_validator("allowed_effects", "denied_effects")
    @classmethod
    def effects_are_distinct(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        if len(values) != len(set(values)):
            raise ValueError("capability effects must be distinct")
        return values


class CapabilityInvocation(CapabilityContract):
    """A request to apply one declared capability to supplied input."""

    invocation_id: str = Field(min_length=1, max_length=256)
    capability_id: str = Field(pattern=r"^risk\.capability\.[a-z_]+$")
    inputs: tuple[CapabilityInput, ...] = ()
    evidence_references: tuple[EvidenceReference, ...] = ()

    @model_validator(mode="before")
    @classmethod
    def normalize_inputs(cls, value: object) -> object:
        if not isinstance(value, dict):
            return value
        inputs = value.get("inputs")
        if isinstance(inputs, dict):
            normalized = dict(value)
            normalized["inputs"] = tuple(
                {"name": name, "value": input_value}
                for name, input_value in sorted(inputs.items())
            )
            return normalized
        return value

    @field_validator("inputs")
    @classmethod
    def input_names_are_unique_and_ordered(
        cls, values: tuple[CapabilityInput, ...]
    ) -> tuple[CapabilityInput, ...]:
        names = [item.name for item in values]
        if len(names) != len(set(names)):
            raise ValueError("capability input names must be unique")
        return tuple(sorted(values, key=lambda item: item.name))


class CapabilityOutcome(CapabilityContract):
    """A traceable capability result, including review and safety disclosure."""

    invocation_id: str = Field(min_length=1, max_length=256)
    capability_id: str = Field(pattern=r"^risk\.capability\.[a-z_]+$")
    status: Literal["succeeded", "failed"]
    summary: str = Field(min_length=1)
    evidence_references: tuple[EvidenceReference, ...] = ()
    disclosures: tuple[str, ...] = ()
    assumptions: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()
    human_review_required: bool = True
    executed_effects: tuple[str, ...] = ()
