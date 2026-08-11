"""Deterministic resolution of an accepted experiment-object set into a Fixture Context."""

from __future__ import annotations

import hashlib
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal, Protocol

from pydantic import Field, field_validator, model_validator
from risk_registry import (
    LifecycleState,
    RegistryDocument,
    RegistryIdentity,
)

from .experiment_objects import ExperimentObjectSet
from .models import DIGEST, IDENTIFIER, FrozenModel, canonical_digest


ELIGIBLE_FIXTURE_STATES = frozenset(
    {LifecycleState.VALIDATED, LifecycleState.PUBLISHED}
)


class RegistryReader(Protocol):
    def get(self, identity: RegistryIdentity) -> RegistryDocument: ...


class MethodologyAcceptanceRecord(FrozenModel):
    schema_version: Literal["portfolio-risk.methodology-acceptance/v1"] = (
        "portfolio-risk.methodology-acceptance/v1"
    )
    namespace: str = Field(pattern=IDENTIFIER)
    record_id: str = Field(pattern=IDENTIFIER)
    version: str
    decision: Literal["accepted_for_apparatus_calibration"]
    reviewer: str = Field(pattern=IDENTIFIER)
    authorized_by: str = Field(min_length=3, max_length=300)
    reviewed_at: datetime
    scientific_design_identity: RegistryIdentity
    experiment_object_set_identity: RegistryIdentity
    scientific_design_digest: str = Field(pattern=DIGEST)
    fixture_context_digest: str = Field(pattern=DIGEST)
    approved_uses: tuple[str, ...] = Field(min_length=1)
    prohibited_claims: tuple[str, ...] = Field(min_length=1)
    required_revisions: tuple[str, ...] = Field(min_length=1)
    rationale: str = Field(min_length=20, max_length=3000)
    acceptance_digest: str | None = Field(default=None, pattern=DIGEST)

    @property
    def reference(self) -> str:
        return (
            f"methodology_acceptance:{self.namespace}:{self.record_id}@{self.version}"
            f"#{self.acceptance_digest}"
        )

    @field_validator("reviewed_at")
    @classmethod
    def reviewed_at_is_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("methodology review time must be timezone-aware")
        return value.astimezone(timezone.utc)

    @field_validator("approved_uses", "prohibited_claims", "required_revisions")
    @classmethod
    def list_values_are_unique(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(value) != len(set(value)):
            raise ValueError("acceptance record values must be unique")
        return value

    @model_validator(mode="after")
    def bind_acceptance_digest(self) -> "MethodologyAcceptanceRecord":
        expected = canonical_digest(
            self.model_dump(mode="json", exclude={"acceptance_digest"})
        )
        if self.acceptance_digest is not None and self.acceptance_digest != expected:
            raise ValueError("acceptance_digest does not match canonical content")
        object.__setattr__(self, "acceptance_digest", expected)
        return self


class FixtureSourceBinding(FrozenModel):
    reference: str = Field(min_length=3, max_length=1000)
    repository_relative_path: str = Field(min_length=1, max_length=1000)
    content_digest: str = Field(pattern=DIGEST)


class FixtureSourceManifest(FrozenModel):
    schema_version: Literal["portfolio-risk.fixture-source-manifest/v1"] = (
        "portfolio-risk.fixture-source-manifest/v1"
    )
    bindings: tuple[FixtureSourceBinding, ...] = Field(min_length=1)
    denied_references: tuple[str, ...] = ()
    manifest_digest: str | None = Field(default=None, pattern=DIGEST)

    @field_validator("bindings")
    @classmethod
    def bindings_are_unique_and_sorted(
        cls, value: tuple[FixtureSourceBinding, ...]
    ) -> tuple[FixtureSourceBinding, ...]:
        references = [item.reference for item in value]
        if references != sorted(set(references)):
            raise ValueError("fixture source bindings must be unique and sorted")
        return value

    @field_validator("denied_references")
    @classmethod
    def denied_references_are_unique_and_sorted(
        cls, value: tuple[str, ...]
    ) -> tuple[str, ...]:
        if value != tuple(sorted(set(value))):
            raise ValueError("denied fixture references must be unique and sorted")
        return value

    @model_validator(mode="after")
    def bind_manifest_digest(self) -> "FixtureSourceManifest":
        bound = {item.reference for item in self.bindings}
        if bound.intersection(self.denied_references):
            raise ValueError("a fixture source cannot be both reachable and denied")
        expected = canonical_digest(
            self.model_dump(mode="json", exclude={"manifest_digest"})
        )
        if self.manifest_digest is not None and self.manifest_digest != expected:
            raise ValueError("manifest_digest does not match canonical content")
        object.__setattr__(self, "manifest_digest", expected)
        return self


class FixtureContext(FrozenModel):
    schema_version: Literal["portfolio-risk.fixture-context/v1"] = (
        "portfolio-risk.fixture-context/v1"
    )
    object_set: ExperimentObjectSet
    acceptance: MethodologyAcceptanceRecord
    sources: FixtureSourceManifest
    reachable_capability_references: tuple[str, ...]
    reachable_dataset_references: tuple[str, ...]
    fixture_context_digest: str = Field(pattern=DIGEST)
    external_effects: Literal["disabled"] = "disabled"
    supra_agent_enabled: Literal[False] = False

    @model_validator(mode="after")
    def validate_closed_context(self) -> "FixtureContext":
        if self.acceptance.scientific_design_identity != self.object_set.scientific_design.registry_identity:
            raise ValueError("acceptance record names another scientific design")
        if self.acceptance.experiment_object_set_identity != self.object_set.registry_identity:
            raise ValueError("acceptance record names another experiment-object set")
        if self.acceptance.scientific_design_digest != self.object_set.scientific_design.pack_digest:
            raise ValueError("acceptance record has another scientific-design digest")
        if self.acceptance.fixture_context_digest != self.object_set.fixture_context_digest:
            raise ValueError("acceptance record has another Fixture Context digest")
        if self.fixture_context_digest != self.object_set.fixture_context_digest:
            raise ValueError("Fixture Context digest must equal the accepted object-set digest")
        capabilities = tuple(
            item.reference
            for item in self.object_set.resource_envelope.capability_pack.capabilities
        )
        datasets = tuple(
            item.reference for item in self.object_set.world_context.data_manifest.datasets
        )
        if self.reachable_capability_references != capabilities:
            raise ValueError("reachable capabilities do not match the accepted envelope")
        if self.reachable_dataset_references != datasets:
            raise ValueError("reachable datasets do not match the accepted world")
        if self.object_set.authority_envelope.effects.external_effects != "disabled":
            raise ValueError("Fixture Context cannot enable external effects")
        if self.object_set.authority_envelope.supra_agent.enabled:
            raise ValueError("the calibration Fixture Context cannot enable a supra-agent")
        expected_sources = {
            self.object_set.portfolio_governance.portfolio.snapshot_reference,
            *datasets,
        }
        actual_sources = {item.reference for item in self.sources.bindings}
        if actual_sources != expected_sources:
            raise ValueError("fixture sources do not exactly cover portfolio and datasets")
        return self

    def allows_capability(self, reference: str) -> bool:
        return reference in self.reachable_capability_references

    def allows_dataset(self, reference: str) -> bool:
        return reference in self.reachable_dataset_references


class FixtureResolutionReceipt(FrozenModel):
    schema_version: Literal["portfolio-risk.fixture-resolution-receipt/v1"] = (
        "portfolio-risk.fixture-resolution-receipt/v1"
    )
    fixture_context_digest: str = Field(pattern=DIGEST)
    acceptance_reference: str = Field(min_length=20, max_length=1200)
    scientific_design_registry_revision: str = Field(min_length=64, max_length=128)
    experiment_object_set_registry_revision: str = Field(min_length=64, max_length=128)
    resolver_version: str
    resolved_at: datetime
    receipt_digest: str | None = Field(default=None, pattern=DIGEST)

    @field_validator("resolved_at")
    @classmethod
    def resolved_at_is_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("resolution time must be timezone-aware")
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def bind_receipt_digest(self) -> "FixtureResolutionReceipt":
        expected = canonical_digest(
            self.model_dump(mode="json", exclude={"receipt_digest"})
        )
        if self.receipt_digest is not None and self.receipt_digest != expected:
            raise ValueError("receipt_digest does not match canonical content")
        object.__setattr__(self, "receipt_digest", expected)
        return self


class ResolvedFixture(FrozenModel):
    context: FixtureContext
    receipt: FixtureResolutionReceipt


class LocalFixtureContextStore:
    """Content-addressed local persistence for contexts and resolution receipts."""

    def __init__(self, root: str | Path):
        self.root = Path(root).expanduser().absolute()
        self.contexts_root = self.root / "contexts"
        self.receipts_root = self.root / "receipts"

    def _ensure_root(self) -> None:
        current = Path(self.root.anchor)
        for part in self.root.parts[1:]:
            current /= part
            if os.path.lexists(current) and current.is_symlink():
                raise ValueError("fixture-store path components may not be symbolic links")
        for path in (self.root, self.contexts_root, self.receipts_root):
            path.mkdir(mode=0o700, parents=True, exist_ok=True)
            if path.is_symlink() or not path.resolve().is_relative_to(self.root.resolve()):
                raise ValueError("fixture-store path is unsafe")

    @staticmethod
    def _key(digest: str) -> str:
        return digest.removeprefix("sha256:")

    @staticmethod
    def _write_once(path: Path, payload: bytes) -> None:
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        try:
            descriptor = os.open(path, flags, 0o400)
        except FileExistsError:
            if path.is_symlink() or path.read_bytes() != payload:
                raise ValueError("immutable fixture-store record conflicts with existing bytes")
            return
        try:
            with os.fdopen(descriptor, "wb") as handle:
                descriptor = -1
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
        finally:
            if descriptor >= 0:
                os.close(descriptor)

    def save(self, value: ResolvedFixture) -> ResolvedFixture:
        self._ensure_root()
        key = self._key(value.context.fixture_context_digest)
        context_path = self.contexts_root / f"{key}.json"
        context_bytes = (value.context.model_dump_json(indent=2) + "\n").encode()
        self._write_once(context_path, context_bytes)
        receipt_directory = self.receipts_root / key
        receipt_directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        if receipt_directory.is_symlink():
            raise ValueError("fixture receipt directory is unsafe")
        receipt_path = receipt_directory / f"{self._key(value.receipt.receipt_digest)}.json"
        receipt_bytes = (value.receipt.model_dump_json(indent=2) + "\n").encode()
        self._write_once(receipt_path, receipt_bytes)
        return value

    def get(self, fixture_context_digest: str) -> FixtureContext:
        self._ensure_root()
        path = self.contexts_root / f"{self._key(fixture_context_digest)}.json"
        if not path.is_file() or path.is_symlink():
            raise KeyError(fixture_context_digest)
        return FixtureContext.model_validate_json(path.read_text(encoding="utf-8"))

    def receipts(self, fixture_context_digest: str) -> tuple[FixtureResolutionReceipt, ...]:
        self._ensure_root()
        directory = self.receipts_root / self._key(fixture_context_digest)
        if not directory.exists():
            return ()
        if directory.is_symlink():
            raise ValueError("fixture receipt directory is unsafe")
        return tuple(
            FixtureResolutionReceipt.model_validate_json(path.read_text(encoding="utf-8"))
            for path in sorted(directory.glob("*.json"))
            if not path.is_symlink()
        )


def _digest_file(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _object_set_definition_digest(value: ExperimentObjectSet) -> str:
    return canonical_digest(value.model_dump(mode="json")).removeprefix("sha256:")


class FixtureContextResolver:
    """Resolve only validated/published definitions and verify every source byte."""

    resolver_version = "1.0.0"

    def __init__(self, registry: RegistryReader, repository_root: str | Path):
        self.registry = registry
        self.repository_root = Path(repository_root).resolve()

    def _registry_document(
        self,
        identity: RegistryIdentity,
        expected_definition_digest: str,
    ) -> RegistryDocument:
        document = self.registry.get(identity)
        if document.state not in ELIGIBLE_FIXTURE_STATES:
            raise ValueError(
                f"{identity.reference} must be validated or published for Fixture resolution"
            )
        if document.projection.source.definition_digest != expected_definition_digest:
            raise ValueError(
                f"{identity.reference} Registry definition digest does not match the candidate"
            )
        return document

    def _verify_sources(self, manifest: FixtureSourceManifest) -> None:
        for binding in manifest.bindings:
            path = (self.repository_root / binding.repository_relative_path).resolve()
            if not path.is_relative_to(self.repository_root):
                raise ValueError("fixture source path escapes the repository")
            if not path.is_file() or path.is_symlink():
                raise ValueError(f"fixture source is missing or unsafe: {binding.reference}")
            if _digest_file(path) != binding.content_digest:
                raise ValueError(f"fixture source digest mismatch: {binding.reference}")

    def resolve(
        self,
        object_set: ExperimentObjectSet,
        acceptance: MethodologyAcceptanceRecord,
        sources: FixtureSourceManifest,
        *,
        resolved_at: datetime | None = None,
    ) -> ResolvedFixture:
        design_document = self._registry_document(
            object_set.scientific_design.registry_identity,
            object_set.scientific_design.pack_digest.removeprefix("sha256:"),
        )
        object_set_document = self._registry_document(
            object_set.registry_identity,
            _object_set_definition_digest(object_set),
        )
        self._verify_sources(sources)
        capabilities = tuple(
            item.reference
            for item in object_set.resource_envelope.capability_pack.capabilities
        )
        datasets = tuple(
            item.reference for item in object_set.world_context.data_manifest.datasets
        )
        context = FixtureContext(
            object_set=object_set,
            acceptance=acceptance,
            sources=sources,
            reachable_capability_references=capabilities,
            reachable_dataset_references=datasets,
            fixture_context_digest=object_set.fixture_context_digest,
        )
        receipt = FixtureResolutionReceipt(
            fixture_context_digest=context.fixture_context_digest,
            acceptance_reference=acceptance.reference,
            scientific_design_registry_revision=(
                design_document.receipts[-1].receipt_digest
            ),
            experiment_object_set_registry_revision=(
                object_set_document.receipts[-1].receipt_digest
            ),
            resolver_version=self.resolver_version,
            resolved_at=resolved_at or datetime.now(timezone.utc),
        )
        return ResolvedFixture(context=context, receipt=receipt)
