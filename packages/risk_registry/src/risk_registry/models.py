"""Contracts for an index over canonical definitions, never their replacement."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


SHA256_PATTERN = r"^[a-f0-9]{64}$"
VERSION_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9._+-]{0,127}$"


def _digest(value: dict[str, Any]) -> str:
    payload = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        default=lambda item: item.isoformat() if isinstance(item, datetime) else str(item),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _receipt_digests(intent: dict[str, Any]) -> tuple[str, str]:
    receipt_id = _digest({"kind": "registry-lifecycle-intent/v1", **intent})
    receipt_digest = _digest(
        {"kind": "registry-lifecycle-receipt/v1", **intent, "receipt_id": receipt_id}
    )
    return receipt_id, receipt_digest


class RegistryModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class AssetKind(str, Enum):
    AGENT = "agent"
    CAPABILITY = "capability"
    EVALUATION = "evaluation"
    REPORT = "report"
    DASHBOARD = "dashboard"
    SCENARIO = "scenario"
    WORKFLOW = "workflow"


class LifecycleState(str, Enum):
    CANDIDATE = "candidate"
    VALIDATED = "validated"
    PUBLISHED = "published"
    DEPRECATED = "deprecated"
    RETIRED = "retired"
    ARCHIVED = "archived"


LIFECYCLE_TRANSITIONS: dict[LifecycleState, tuple[LifecycleState, ...]] = {
    LifecycleState.CANDIDATE: (LifecycleState.VALIDATED,),
    LifecycleState.VALIDATED: (LifecycleState.PUBLISHED,),
    LifecycleState.PUBLISHED: (LifecycleState.DEPRECATED,),
    LifecycleState.DEPRECATED: (LifecycleState.RETIRED,),
    LifecycleState.RETIRED: (LifecycleState.ARCHIVED,),
    LifecycleState.ARCHIVED: (),
}


class RegistryIdentity(RegistryModel):
    kind: AssetKind
    namespace: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,159}$")
    asset_id: str = Field(min_length=1, max_length=256)
    version: str = Field(pattern=VERSION_PATTERN)

    @field_validator("asset_id")
    @classmethod
    def asset_id_has_no_control_characters(cls, value: str) -> str:
        clean = value.strip()
        if (
            not clean
            or any(ord(character) < 32 for character in clean)
            or any(character in clean for character in ":@")
        ):
            raise ValueError(
                "asset_id must be non-empty and contain no control or reference-delimiter characters"
            )
        return clean

    @property
    def reference(self) -> str:
        return f"{self.kind.value}:{self.namespace}:{self.asset_id}@{self.version}"


class SourceReference(RegistryModel):
    source_type: str = Field(min_length=1, max_length=80)
    source_reference: str = Field(min_length=1, max_length=1024)
    source_digest: str = Field(pattern=SHA256_PATTERN)
    definition_digest: str = Field(pattern=SHA256_PATTERN)
    native_version: str | None = Field(default=None, max_length=128)
    canonical: bool = True
    adapter_id: str = Field(min_length=1, max_length=160)
    adapter_digest: str = Field(pattern=SHA256_PATTERN)


class Provenance(RegistryModel):
    discovered_by: str = Field(min_length=1, max_length=128)
    discovered_at: datetime
    repository_commit: str | None = Field(default=None, max_length=64)
    notes: tuple[str, ...] = ()

    @field_validator("discovered_at")
    @classmethod
    def timestamp_is_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("discovered_at must be timezone-aware")
        return value.astimezone(timezone.utc)


class Compatibility(RegistryModel):
    status: str = Field(
        default="declared",
        pattern=r"^(declared|compatible|incompatible|unknown|unavailable)$",
    )
    api_versions: tuple[str, ...] = ()
    evaluated_source_digest: str | None = Field(default=None, pattern=SHA256_PATTERN)
    evaluator_revision: str = Field(default="unassessed", min_length=1, max_length=160)
    notes: tuple[str, ...] = ()

    @model_validator(mode="after")
    def compatible_observations_bind_the_source(self) -> "Compatibility":
        if self.status == "compatible" and self.evaluated_source_digest is None:
            raise ValueError("compatible status requires an evaluated source digest")
        return self


class RegistryRelationship(RegistryModel):
    relationship: str = Field(min_length=1, max_length=80)
    target_native_id: str = Field(min_length=1, max_length=256)
    target_reference: str | None = Field(default=None, max_length=768)
    resolution: str = Field(pattern=r"^(resolved|unresolved|unavailable)$")


class RegistryProjection(RegistryModel):
    identity: RegistryIdentity
    display_name: str = Field(min_length=1, max_length=256)
    summary: str = Field(min_length=1, max_length=1200)
    source: SourceReference
    provenance: Provenance
    compatibility: Compatibility = Compatibility()
    lineage: tuple[str, ...] = ()
    source_contract: str = Field(min_length=1, max_length=256)
    relationships: tuple[RegistryRelationship, ...] = ()
    tags: tuple[str, ...] = ()

    @field_validator("lineage", "tags")
    @classmethod
    def values_are_unique(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        if len(values) != len(set(values)):
            raise ValueError("registry projection values must be unique")
        return values

    @model_validator(mode="after")
    def projection_remains_bounded(self) -> "RegistryProjection":
        encoded = self.model_dump_json()
        if len(encoded.encode("utf-8")) > 64_000:
            raise ValueError("registry projection exceeds the 64 KB metadata boundary")
        return self


class LifecycleReceipt(RegistryModel):
    registry_reference: str = Field(min_length=1, max_length=768)
    sequence: int = Field(ge=1)
    from_state: LifecycleState | None
    to_state: LifecycleState
    actor: str = Field(min_length=1, max_length=128)
    rationale: str = Field(min_length=3, max_length=1200)
    occurred_at: datetime
    replacement_reference: str | None = Field(default=None, max_length=512)
    prior_receipt_digest: str | None = Field(default=None, pattern=SHA256_PATTERN)
    receipt_id: str = Field(pattern=SHA256_PATTERN)
    receipt_digest: str = Field(pattern=SHA256_PATTERN)

    @field_validator("occurred_at")
    @classmethod
    def occurred_at_is_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("occurred_at must be timezone-aware")
        return value.astimezone(timezone.utc)

    @classmethod
    def create(
        cls,
        *,
        registry_reference: str,
        sequence: int,
        from_state: LifecycleState | None,
        to_state: LifecycleState,
        actor: str,
        rationale: str,
        occurred_at: datetime,
        prior_receipt_digest: str | None,
        replacement_reference: str | None = None,
    ) -> "LifecycleReceipt":
        observed_at = occurred_at.astimezone(timezone.utc)
        intent = {
            "registry_reference": registry_reference,
            "sequence": sequence,
            "from_state": from_state.value if from_state else None,
            "to_state": to_state.value,
            "actor": actor,
            "rationale": rationale,
            "occurred_at": observed_at,
            "replacement_reference": replacement_reference,
            "prior_receipt_digest": prior_receipt_digest,
        }
        receipt_id, receipt_digest = _receipt_digests(intent)
        return cls(
            **intent,
            receipt_id=receipt_id,
            receipt_digest=receipt_digest,
        )

    @model_validator(mode="after")
    def digest_is_valid(self) -> "LifecycleReceipt":
        intent = {
            "registry_reference": self.registry_reference,
            "sequence": self.sequence,
            "from_state": self.from_state.value if self.from_state else None,
            "to_state": self.to_state.value,
            "actor": self.actor,
            "rationale": self.rationale,
            "occurred_at": self.occurred_at,
            "replacement_reference": self.replacement_reference,
            "prior_receipt_digest": self.prior_receipt_digest,
        }
        receipt_id, receipt_digest = _receipt_digests(intent)
        if receipt_id != self.receipt_id or receipt_digest != self.receipt_digest:
            raise ValueError("lifecycle receipt digest verification failed")
        return self


class RegistryDocument(RegistryModel):
    schema_version: str = "risk-registry/v1"
    projection: RegistryProjection
    receipts: tuple[LifecycleReceipt, ...]

    @model_validator(mode="after")
    def receipts_form_valid_chain(self) -> "RegistryDocument":
        if not self.receipts:
            raise ValueError("registry document requires an initial lifecycle receipt")
        state: LifecycleState | None = None
        prior_digest: str | None = None
        for index, receipt in enumerate(self.receipts, start=1):
            if receipt.sequence != index or receipt.from_state != state:
                raise ValueError("lifecycle receipts must form an ordered append-only chain")
            if receipt.registry_reference != self.projection.identity.reference:
                raise ValueError("lifecycle receipt identity does not match the projection")
            if receipt.prior_receipt_digest != prior_digest:
                raise ValueError("lifecycle receipt digest chain is broken")
            if state is None:
                if receipt.to_state is not LifecycleState.CANDIDATE:
                    raise ValueError("registry documents begin as candidates")
            elif receipt.to_state not in LIFECYCLE_TRANSITIONS[state]:
                raise ValueError(f"invalid lifecycle transition: {state} -> {receipt.to_state}")
            if receipt.to_state is LifecycleState.DEPRECATED and not receipt.replacement_reference:
                raise ValueError("deprecation requires a replacement reference")
            state = receipt.to_state
            prior_digest = receipt.receipt_digest
        return self

    @property
    def state(self) -> LifecycleState:
        return self.receipts[-1].to_state
