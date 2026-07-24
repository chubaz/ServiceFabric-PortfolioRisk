"""Typed, local-only Workbench adapter for Part 2 monitoring capabilities."""

from __future__ import annotations

import csv
import hashlib
import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from risk_agents import DeterministicContextualMonitoringOrchestrator
from risk_analytics import MonitoringReportRequest
from risk_capabilities import (
    CapabilityRegistry,
    ContextualMonitoringWorkflowRequest,
    EventQueryCapabilityRequest,
    EvidenceReference,
    MonitoringReportCapabilityRequest,
    PortfolioDataContextCapabilityRequest,
    ReplayCapabilityRequest,
    ReplayEvaluationCapabilityRequest,
    ReplayStepInput,
)
from risk_data import (
    CrosswalkSnapshot,
    DatasetRevision,
    EventDataPlane,
    EventDatasetSnapshot,
    EventImportPreview,
    EventMappingManifest,
    EventProviderProfile,
    EventQueryRequest,
    FixedQueryRequest,
    LocalImportError,
    PublicationRestriction,
    ResearchDatasetSnapshot,
    date_effective_mappings_from_crosswalk,
)
from risk_domain import PortfolioSnapshot
from risk_domain.digests import sha256_digest
from risk_domain.monitoring import (
    ContextualMonitoringRun,
    MonitoringEvaluation,
    MonitoringEvidence,
    MonitoringMetric,
    MonitoringPolicyVersion,
    OutcomeLabel,
    PointInTimeObservation,
    PortfolioDataContext,
    PortfolioDataContextRequest,
    ReplayRun,
    ReplaySpecification,
)


MAX_EVENT_UPLOAD_BYTES = 1_000_000
MAX_REPLAY_STEPS = 366
DEFAULT_AS_OF = datetime(2026, 7, 1, 16, tzinfo=UTC)
SAFE_ID_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,255}$"


class MonitoringAdapterError(ValueError):
    """A bounded Workbench monitoring request could not be completed."""


class ContextSelectionRequest(BaseModel):
    """Reviewed identifiers used to build a canonical data-context request."""

    model_config = ConfigDict(extra="forbid")

    profile: Literal["research", "personal_portfolio"] = "research"
    portfolio_snapshot_id: str = Field(default="", max_length=256)
    market_dataset_snapshot_id: str = Field(pattern=SAFE_ID_PATTERN)
    market_dataset_revision: str = Field(pattern=SAFE_ID_PATTERN)
    fundamental_dataset_snapshot_id: str | None = Field(
        default=None, pattern=SAFE_ID_PATTERN
    )
    fundamental_dataset_revision: str | None = Field(
        default=None, pattern=SAFE_ID_PATTERN
    )
    crosswalk_snapshot_id: str = Field(pattern=SAFE_ID_PATTERN)
    crosswalk_dataset_revision: str = Field(pattern=SAFE_ID_PATTERN)
    event_snapshot_id: str | None = Field(default=None, pattern=SAFE_ID_PATTERN)
    event_dataset_revision: str | None = Field(default=None, pattern=SAFE_ID_PATTERN)
    as_of: datetime = DEFAULT_AS_OF
    stale_data_maximum_age_seconds: int = Field(default=604_800, ge=1, le=31_536_000)
    confirm: bool = False

    @field_validator("as_of")
    @classmethod
    def aware_as_of(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("as_of must be timezone-aware")
        return value.astimezone(UTC)


class ExplicitConfirmation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    preview_id: str = Field(pattern=SAFE_ID_PATTERN)
    confirm: bool


class PolicyFields(BaseModel):
    """The fixed, reviewed policy form. No executable field is accepted."""

    model_config = ConfigDict(extra="forbid")

    policy_id: str = Field(default="workbench-monitoring-policy", pattern=SAFE_ID_PATTERN)
    daily_percentage_move_threshold: Decimal = Field(
        default=Decimal("0.05"), gt=Decimal("0"), le=Decimal("1")
    )
    concentration_threshold: Decimal = Field(
        default=Decimal("0.40"), gt=Decimal("0"), le=Decimal("1")
    )
    event_relevance_minimum: Decimal = Field(
        default=Decimal("0.60"), ge=Decimal("0"), le=Decimal("1")
    )
    negative_sentiment_threshold: Decimal = Field(
        default=Decimal("-0.50"), ge=Decimal("-1"), le=Decimal("0")
    )
    stale_data_maximum_age_seconds: int = Field(default=86_400, ge=1)
    historical_var_limit: Decimal | None = Field(default=None, ge=Decimal("0"))
    scenario_loss_limit: Decimal | None = Field(default=None, ge=Decimal("0"))
    cadence: Literal["manual", "daily", "weekly", "monthly"] = "manual"
    cadence_metadata: str = Field(
        default="Metadata only; every run is explicitly invoked.", min_length=1, max_length=512
    )
    reviewed_by: str = Field(default="workbench-human-reviewer", min_length=1, max_length=256)
    reviewed_at: datetime = DEFAULT_AS_OF
    confirm: bool = False

    @field_validator("reviewed_at")
    @classmethod
    def aware_review_time(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("reviewed_at must be timezone-aware")
        return value.astimezone(UTC)


class RunSelectionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    context_id: str = Field(pattern=SAFE_ID_PATTERN)
    policy_id: str = Field(pattern=SAFE_ID_PATTERN)
    run_at: datetime = DEFAULT_AS_OF

    @field_validator("run_at")
    @classmethod
    def aware_run_time(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("run_at must be timezone-aware")
        return value.astimezone(UTC)


class ReplaySelectionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    context_id: str = Field(pattern=SAFE_ID_PATTERN)
    policy_id: str = Field(pattern=SAFE_ID_PATTERN)
    start: datetime
    end: datetime
    cadence: Literal["daily", "weekly", "monthly"] = "daily"
    outcome_label_snapshot_id: Literal[
        "reviewed-synthetic-outcomes", "reviewed-empty-outcomes"
    ] = "reviewed-synthetic-outcomes"
    lookback_seconds: int = Field(default=259_200, ge=1)
    evaluation_horizon_seconds: int = Field(default=86_400, ge=1)

    @field_validator("start", "end")
    @classmethod
    def aware_replay_time(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("replay bounds must be timezone-aware")
        return value.astimezone(UTC)


class EventPreviewParameters(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider_profile: Literal["synthetic_local", "licensed_local"] = "synthetic_local"
    provider_id: str = Field(default="workbench-local-events", pattern=SAFE_ID_PATTERN)
    provider_name: str = Field(default="Workbench local events", min_length=1, max_length=256)
    dataset_revision: str = Field(default="local-event-revision-1", pattern=SAFE_ID_PATTERN)
    publication_restriction: Literal[
        "synthetic_only", "internal_research_only", "no_publication"
    ] = "synthetic_only"
    retrieved_at: datetime = DEFAULT_AS_OF

    @field_validator("retrieved_at")
    @classmethod
    def aware_retrieval_time(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("retrieved_at must be timezone-aware")
        return value.astimezone(UTC)


class MonitoringCollection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: tuple[dict[str, object], ...]


class MonitoringWorkspace:
    """Resolve UI/API selections and delegate all monitoring work to core packages."""

    def __init__(self, data_root: Path, registry: CapabilityRegistry) -> None:
        self.data_root = data_root
        self.registry = registry
        self.events = EventDataPlane(data_root)
        from data_workspace_service import ResearchDataWorkspace

        self.research = ResearchDataWorkspace(
            data_root, Path(__file__).resolve().parents[2]
        )

    @staticmethod
    def evidence(profile: str = "research") -> tuple[MonitoringEvidence, ...]:
        state = "local-private" if profile == "personal_portfolio" else "reviewed-synthetic"
        return (
            MonitoringEvidence(
                evidence_id=f"workbench-monitoring-{state}",
                reference=f"workbench://monitoring/{state}",
                digest=sha256_digest({"profile": profile, "state": state}),
                description=(
                    "Private local Workbench selection; publication is unavailable."
                    if profile == "personal_portfolio"
                    else "Reviewed synthetic Workbench monitoring selection."
                ),
            ),
        )

    @classmethod
    def capability_evidence(cls, profile: str = "research") -> tuple[EvidenceReference, ...]:
        item = cls.evidence(profile)[0]
        return (
            EvidenceReference(
                evidence_id=item.evidence_id,
                reference=item.reference,
                source_type=(
                    "local_private_selection"
                    if profile == "personal_portfolio"
                    else "synthetic_fixture"
                ),
                digest=item.digest,
            ),
        )

    def _directory(self, kind: str) -> Path:
        path = self.data_root / "workbench" / "monitoring" / kind
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _save(self, kind: str, record_id: str, payload: object) -> dict[str, object]:
        data = (
            payload.model_dump(mode="json")
            if hasattr(payload, "model_dump")
            else dict(payload)  # type: ignore[arg-type]
        )
        path = self._directory(kind) / f"{record_id}.json"
        encoded = json.dumps(data, sort_keys=True, indent=2) + "\n"
        if path.is_file() and path.read_text(encoding="utf-8") != encoded:
            raise MonitoringAdapterError("immutable monitoring record already exists")
        if not path.exists():
            path.write_text(encoded, encoding="utf-8")
        return data

    def _load(self, kind: str, record_id: str) -> dict[str, object]:
        if not record_id or any(
            character not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._:-"
            for character in record_id
        ):
            raise MonitoringAdapterError("monitoring record identifier is invalid")
        path = self._directory(kind) / f"{record_id}.json"
        if not path.is_file():
            raise MonitoringAdapterError("monitoring record was not found")
        return json.loads(path.read_text(encoding="utf-8"))

    def _list(self, kind: str) -> tuple[dict[str, object], ...]:
        return tuple(
            json.loads(path.read_text(encoding="utf-8"))
            for path in sorted(self._directory(kind).glob("*.json"))
        )

    @staticmethod
    def _record_id(prefix: str, digest: str) -> str:
        return f"{prefix}-{digest.removeprefix('sha256:')[:24]}"

    def context_catalogue(self) -> dict[str, tuple[dict[str, str], ...]]:
        snapshots = self.research.snapshots()
        superseded = {
            item.supersedes_snapshot_id
            for item in snapshots
            if item.supersedes_snapshot_id is not None
        }
        current = tuple(item for item in snapshots if item.snapshot_id not in superseded)
        crosswalks = {item.snapshot_id: item for item in self.research.crosswalks()}
        market: list[dict[str, str]] = []
        fundamental: list[dict[str, str]] = []
        crosswalk: list[dict[str, str]] = []
        for snapshot in current:
            kinds = {item.dataset_id: item.dataset_kind for item in snapshot.datasets}
            for revision in snapshot.dataset_revisions:
                option = {
                    "snapshot_id": snapshot.snapshot_id,
                    "revision_id": revision.revision_id,
                    "dataset_id": revision.dataset_id,
                }
                if kinds.get(revision.dataset_id) == "daily_market":
                    market.append(option)
                elif kinds.get(revision.dataset_id) == "fundamentals_annual":
                    fundamental.append(option)
            for crosswalk_id in snapshot.crosswalk_snapshot_ids:
                selected = crosswalks.get(crosswalk_id)
                if selected is not None:
                    crosswalk.append(
                        {
                            "research_snapshot_id": snapshot.snapshot_id,
                            "snapshot_id": selected.snapshot_id,
                            "revision_id": selected.source_digest,
                        }
                    )
        return {
            "market": tuple(market),
            "fundamental": tuple(fundamental),
            "crosswalk": tuple(crosswalk),
        }

    def context_request(
        self, snapshot: PortfolioSnapshot, selection: ContextSelectionRequest
    ) -> PortfolioDataContextRequest:
        as_of = selection.as_of
        if snapshot.as_of > as_of:
            raise MonitoringAdapterError(
                "the selected portfolio snapshot is newer than the context as_of"
            )
        research_snapshot = self._research_snapshot(
            selection.market_dataset_snapshot_id
        )
        market_revision = self._dataset_revision(
            research_snapshot,
            selection.market_dataset_revision,
            "daily_market",
        )
        crosswalk = self._crosswalk(
            research_snapshot,
            selection.crosswalk_snapshot_id,
            selection.crosswalk_dataset_revision,
        )
        crosswalk_revision = self._crosswalk_revision(
            research_snapshot, crosswalk
        )
        market_rows, query_evidence_ids = self._query_rows(
            research_snapshot,
            manifest_id="daily-market-history",
            dataset_id=market_revision.dataset_id,
            revision_id=market_revision.revision_id,
            as_of=as_of,
        )
        evidence = (
            self._dataset_evidence(
                research_snapshot, market_revision, query_evidence_ids
            )
            + (
                MonitoringEvidence(
                    evidence_id=f"crosswalk:{crosswalk.snapshot_id}",
                    reference=f"local-crosswalk://{crosswalk.snapshot_id}",
                    digest=crosswalk.source_digest,
                    description="Selected immutable date-effective crosswalk.",
                ),
            )
            + self.evidence(selection.profile)
        )
        observations = self._observations(
            market_rows,
            snapshot_id=research_snapshot.snapshot_id,
            revision=market_revision,
            fields=(
                ("valuation_price", "valuation_price", None),
                ("return", "return", "ratio"),
            ),
            evidence=evidence,
        )
        mappings = date_effective_mappings_from_crosswalk(crosswalk)
        values: dict[str, object] = {
            "portfolio_snapshot_id": snapshot.snapshot_id,
            "portfolio_snapshot": snapshot,
            "market_dataset_snapshot_id": research_snapshot.snapshot_id,
            "market_dataset_revision": market_revision.revision_id,
            "market_dataset_retrieved_at": market_revision.retrieved_at,
            "market_observations": observations,
            "crosswalk_snapshot_id": crosswalk.snapshot_id,
            "crosswalk_dataset_revision": crosswalk.source_digest,
            "crosswalk_retrieved_at": crosswalk_revision.retrieved_at,
            "crosswalk_records": mappings,
            "event_snapshot_id": selection.event_snapshot_id,
            "event_dataset_revision": selection.event_dataset_revision,
            "event_dataset_retrieved_at": (
                self._event_retrieved_at(
                    selection.event_snapshot_id,
                    selection.event_dataset_revision,
                )
                if selection.event_snapshot_id is not None
                else None
            ),
            "as_of": as_of,
            "stale_data_maximum_age_seconds": selection.stale_data_maximum_age_seconds,
            "evidence": evidence,
            "assumptions": (
                "The selected research records are reviewed synthetic fixtures."
                if selection.profile == "research"
                else "The selected portfolio snapshot remains private local state.",
            ),
            "limitations": (
                "No provider network call or identifier inference was performed.",
            ),
        }
        if selection.fundamental_dataset_snapshot_id is not None:
            if (
                selection.fundamental_dataset_snapshot_id
                != research_snapshot.snapshot_id
            ):
                raise MonitoringAdapterError(
                    "market and fundamental revisions must belong to the same selected research snapshot"
                )
            fundamental_revision = self._dataset_revision(
                research_snapshot,
                selection.fundamental_dataset_revision or "",
                "fundamentals_annual",
            )
            fundamental_rows, fundamental_query_evidence = self._query_rows(
                research_snapshot,
                manifest_id="fundamentals-as-of",
                dataset_id=fundamental_revision.dataset_id,
                revision_id=fundamental_revision.revision_id,
                as_of=as_of,
            )
            fundamental_evidence = self._dataset_evidence(
                research_snapshot,
                fundamental_revision,
                fundamental_query_evidence,
            )
            values.update(
                fundamental_dataset_snapshot_id=research_snapshot.snapshot_id,
                fundamental_dataset_revision=fundamental_revision.revision_id,
                fundamental_dataset_retrieved_at=fundamental_revision.retrieved_at,
                fundamental_observations=self._observations(
                    fundamental_rows,
                    snapshot_id=research_snapshot.snapshot_id,
                    revision=fundamental_revision,
                    fields=(
                        ("assets", "assets", None),
                        ("liabilities", "liabilities", None),
                        ("sales", "sales", None),
                        ("net_income", "net_income", None),
                    ),
                    evidence=fundamental_evidence,
                ),
            )
        return PortfolioDataContextRequest.model_validate(values)

    def _research_snapshot(self, snapshot_id: str) -> ResearchDatasetSnapshot:
        try:
            return self.research.get_snapshot(snapshot_id)
        except (LookupError, LocalImportError) as error:
            raise MonitoringAdapterError(
                "selected research dataset snapshot was not found"
            ) from error

    @staticmethod
    def _dataset_revision(
        snapshot: ResearchDatasetSnapshot,
        revision_id: str,
        dataset_kind: str,
    ) -> DatasetRevision:
        dataset_ids = {
            item.dataset_id
            for item in snapshot.datasets
            if item.dataset_kind == dataset_kind
        }
        matches = [
            item
            for item in snapshot.dataset_revisions
            if item.dataset_id in dataset_ids and item.revision_id == revision_id
        ]
        if len(matches) != 1:
            raise MonitoringAdapterError(
                f"selected {dataset_kind} revision is not present in the immutable snapshot"
            )
        return matches[0]

    def _crosswalk(
        self,
        snapshot: ResearchDatasetSnapshot,
        crosswalk_snapshot_id: str,
        source_digest: str,
    ) -> CrosswalkSnapshot:
        if crosswalk_snapshot_id not in snapshot.crosswalk_snapshot_ids:
            raise MonitoringAdapterError(
                "selected crosswalk is not part of the immutable research snapshot"
            )
        matches = [
            item
            for item in self.research.crosswalks()
            if item.snapshot_id == crosswalk_snapshot_id
        ]
        if len(matches) != 1 or matches[0].source_digest != source_digest:
            raise MonitoringAdapterError(
                "selected crosswalk revision does not match the immutable crosswalk"
            )
        return matches[0]

    @staticmethod
    def _crosswalk_revision(
        snapshot: ResearchDatasetSnapshot,
        crosswalk: CrosswalkSnapshot,
    ) -> DatasetRevision:
        dataset_ids = {
            item.dataset_id
            for item in snapshot.datasets
            if item.dataset_kind == "identifier_crosswalk"
        }
        matches = [
            item
            for item in snapshot.dataset_revisions
            if item.dataset_id in dataset_ids
            and item.source_digest == crosswalk.source_digest
        ]
        if len(matches) != 1:
            raise MonitoringAdapterError(
                "selected crosswalk has no matching immutable dataset revision"
            )
        return matches[0]

    def _query_rows(
        self,
        snapshot: ResearchDatasetSnapshot,
        *,
        manifest_id: str,
        dataset_id: str,
        revision_id: str,
        as_of: datetime,
    ) -> tuple[tuple[dict[str, object], ...], tuple[str, ...]]:
        try:
            result = self.research.run_query(
                FixedQueryRequest(
                    manifest_id=manifest_id,
                    parameters={},
                    as_of=as_of,
                    limit=1_000,
                )
            )
        except LocalImportError as error:
            raise MonitoringAdapterError(str(error)) from error
        if tuple(result.snapshot_ids) != (snapshot.snapshot_id,):
            raise MonitoringAdapterError(
                "the selected immutable snapshot is not queryable by the active fixed-query catalogue"
            )
        rows = tuple(
            row
            for row in result.rows
            if row.get("dataset_id") == dataset_id
            and row.get("dataset_revision") == revision_id
        )
        if not rows:
            raise MonitoringAdapterError(
                f"selected {manifest_id} revision contains no eligible observations"
            )
        return rows, tuple(result.evidence_ids)

    @staticmethod
    def _dataset_evidence(
        snapshot: ResearchDatasetSnapshot,
        revision: DatasetRevision,
        query_evidence_ids: tuple[str, ...],
    ) -> tuple[MonitoringEvidence, ...]:
        return (
            MonitoringEvidence(
                evidence_id=f"dataset:{snapshot.snapshot_id}:{revision.revision_id}",
                reference=(
                    f"local-research://{snapshot.snapshot_id}/"
                    f"{revision.dataset_id}/{revision.revision_id}"
                ),
                digest=revision.source_digest,
                description=(
                    "Selected immutable Part 1 revision; fixed-query evidence: "
                    + ", ".join(query_evidence_ids)
                ),
            ),
        )

    @staticmethod
    def _timestamp(value: object) -> datetime:
        text = str(value)
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if len(text) == 10:
            parsed = parsed.replace(tzinfo=UTC)
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise MonitoringAdapterError(
                "research observation time is not timezone-aware"
            )
        return parsed.astimezone(UTC)

    @classmethod
    def _observations(
        cls,
        rows: tuple[dict[str, object], ...],
        *,
        snapshot_id: str,
        revision: DatasetRevision,
        fields: tuple[tuple[str, str, str | None], ...],
        evidence: tuple[MonitoringEvidence, ...],
    ) -> tuple[PointInTimeObservation, ...]:
        observations: list[PointInTimeObservation] = []
        for row in rows:
            quality = row.get("quality_flags")
            try:
                quality_flags = tuple(json.loads(str(quality))) if quality else ()
            except json.JSONDecodeError:
                quality_flags = (str(quality),)
            for source_field, field_name, unit in fields:
                value = row.get(source_field)
                if value is None:
                    continue
                observations.append(
                    PointInTimeObservation(
                        dataset_snapshot_id=snapshot_id,
                        dataset_revision=revision.revision_id,
                        entity_id=str(row["entity_id"]),
                        observed_at=cls._timestamp(row["observed_at"]),
                        available_at=(
                            cls._timestamp(row["available_at"])
                            if row.get("available_at") is not None
                            else None
                        ),
                        retrieved_at=revision.retrieved_at,
                        field_name=field_name,
                        value=Decimal(str(value)),
                        unit=unit,
                        quality_flags=quality_flags,
                        evidence=evidence,
                    )
                )
        return tuple(observations)

    def _event_retrieved_at(
        self, snapshot_id: str, revision_id: str | None
    ) -> datetime:
        snapshot = self.events.load_snapshot(snapshot_id)
        if snapshot.dataset_revision != revision_id:
            raise MonitoringAdapterError(
                "selected event revision does not match the immutable event snapshot"
            )
        return snapshot.created_at

    def preview_context(
        self, snapshot: PortfolioSnapshot, selection: ContextSelectionRequest
    ) -> dict[str, object]:
        request = self.context_request(snapshot, selection)
        result = self.registry.invoke(
            "portfolio.data_context.create",
            PortfolioDataContextCapabilityRequest(
                request=request,
                evidence_references=self.capability_evidence(selection.profile),
            ),
        )
        if result.data is None:
            raise MonitoringAdapterError("data-context capability returned no context")
        preview_id = self._record_id("context-preview", result.data.digest or "")
        envelope = {
            "preview_id": preview_id,
            "profile": selection.profile,
            "request": request.model_dump(mode="json"),
            "context": result.data.model_dump(mode="json"),
            "confirmable": not result.data.blocked,
            "effects": list(result.effects),
            "human_review_required": result.human_review_required,
        }
        self._save("context-previews", preview_id, envelope)
        return envelope

    def confirm_context(self, confirmation: ExplicitConfirmation) -> dict[str, object]:
        if not confirmation.confirm:
            raise MonitoringAdapterError("explicit confirm=true is required")
        preview = self._load("context-previews", confirmation.preview_id)
        context = PortfolioDataContext.model_validate(preview["context"])
        if context.blocked:
            raise MonitoringAdapterError(
                "blocking unmapped, ambiguous, or unavailable market data prevents confirmation"
            )
        context_id = self._record_id("context", context.digest or "")
        return self._save(
            "contexts",
            context_id,
            {
                "context_id": context_id,
                "profile": preview["profile"],
                "request": preview["request"],
                "context": preview["context"],
                "confirmed": True,
                "effects": [],
                "human_review_required": True,
            },
        )

    def contexts(self) -> tuple[dict[str, object], ...]:
        return self._list("contexts")

    def context(self, context_id: str) -> dict[str, object]:
        return self._load("contexts", context_id)

    @staticmethod
    def event_mapping() -> EventMappingManifest:
        return EventMappingManifest(
            manifest_id="workbench-reviewed-event-csv-v1",
            field_mapping={
                "source_event_id": "source_event_id",
                "entity_id": "entity_id",
                "event_time": "event_time",
                "available_at": "available_at",
                "event_type": "event_type",
                "relevance": "relevance",
                "sentiment": "sentiment",
                "novelty": "novelty",
                "amendment_state": "amendment_state",
                "supersedes_event_id": "supersedes_event_id",
                "event_text": "event_text",
            },
            duplicate_source_id_policy="deterministic_version",
        )

    def preview_events(
        self, content: bytes, filename: str, parameters: EventPreviewParameters
    ) -> dict[str, object]:
        lowered = filename.lower()
        if not lowered.endswith((".csv", ".parquet")):
            raise MonitoringAdapterError("Only CSV or Parquet uploads are accepted.")
        if not content or len(content) > MAX_EVENT_UPLOAD_BYTES:
            raise MonitoringAdapterError(
                f"Event upload must contain 1 to {MAX_EVENT_UPLOAD_BYTES} bytes."
            )
        private = parameters.provider_profile == "licensed_local"
        restriction = PublicationRestriction(parameters.publication_restriction)
        if private and restriction is PublicationRestriction.SYNTHETIC_ONLY:
            raise MonitoringAdapterError(
                "licensed local events require a restrictive publication state"
            )
        if not private and restriction is not PublicationRestriction.SYNTHETIC_ONLY:
            raise MonitoringAdapterError(
                "synthetic local events require synthetic_only publication"
            )
        provider = EventProviderProfile(
            provider_id=parameters.provider_id,
            display_name=parameters.provider_name,
            profile=parameters.provider_profile,
            publication_restriction=restriction,
            synthetic=not private,
            private=private,
        )
        digest = "sha256:" + hashlib.sha256(content).hexdigest()
        source_dir = self._directory("event-sources")
        suffix = ".parquet" if lowered.endswith(".parquet") else ".csv"
        source_path = source_dir / f"{digest.removeprefix('sha256:')}{suffix}"
        if not source_path.is_file():
            source_path.write_bytes(content)
        preview = self.events.preview_event_export(
            source_path.resolve(),
            provider=provider,
            dataset_revision=parameters.dataset_revision,
            mapping_manifest=self.event_mapping(),
            retrieved_at=parameters.retrieved_at,
        )
        preview_id = self._record_id("event-preview", preview.preview_digest)
        self._save("event-previews", preview_id, preview)
        return self.event_preview_view(preview, preview_id)

    @staticmethod
    def _event_record_view(record: object, *, include_text: bool = False) -> dict[str, object]:
        values = record.model_dump(mode="json")
        if not include_text or values.get("private"):
            values["event_text"] = None
        return values

    @classmethod
    def event_preview_view(
        cls, preview: EventImportPreview, preview_id: str
    ) -> dict[str, object]:
        source = preview.source.model_dump(mode="json")
        source.pop("absolute_path", None)
        return {
            "preview_id": preview_id,
            "preview_digest": preview.preview_digest,
            "source": source,
            "provider": preview.provider.model_dump(mode="json"),
            "dataset_revision": preview.dataset_revision,
            "mapping_manifest": preview.mapping_manifest.model_dump(mode="json"),
            "retrieved_at": preview.retrieved_at.isoformat(),
            "records": [
                cls._event_record_view(item, include_text=not preview.provider.private)
                for item in preview.records
            ],
            "row_count": preview.row_count,
            "accepted_row_count": preview.accepted_row_count,
            "rejected_row_count": preview.rejected_row_count,
            "issues": [item.model_dump(mode="json") for item in preview.issues],
            "public_evidence": [
                item.model_dump(mode="json") for item in preview.public_evidence
            ],
            "confirmable": not preview.has_blocking_issues,
            "server_path_available": False,
            "network_used": False,
        }

    def event_preview(self, preview_id: str) -> dict[str, object]:
        preview = EventImportPreview.model_validate(
            self._load("event-previews", preview_id)
        )
        return self.event_preview_view(preview, preview_id)

    def confirm_events(
        self, preview_id: str, *, confirm: bool, preview_digest: str, source_digest: str
    ) -> dict[str, object]:
        preview = EventImportPreview.model_validate(
            self._load("event-previews", preview_id)
        )
        try:
            snapshot = self.events.confirm_event_export(
                preview,
                confirm=confirm,
                preview_digest=preview_digest,
                source_digest=source_digest,
            )
        except LocalImportError as error:
            raise MonitoringAdapterError(str(error)) from error
        return self.event_snapshot_view(snapshot)

    @classmethod
    def event_snapshot_view(cls, snapshot: EventDatasetSnapshot) -> dict[str, object]:
        return {
            "snapshot_id": snapshot.snapshot_id,
            "provider_id": snapshot.provider_id,
            "dataset_revision": snapshot.dataset_revision,
            "created_at": snapshot.created_at.isoformat(),
            "source_digest": snapshot.source_digest,
            "mapping_manifest_id": snapshot.mapping_manifest_id,
            "records": [
                cls._event_record_view(item, include_text=not snapshot.private)
                for item in snapshot.records
            ],
            "publication_restriction": snapshot.publication_restriction.value,
            "synthetic": snapshot.synthetic,
            "private": snapshot.private,
            "synthetic_state": snapshot.synthetic_state,
            "private_state": snapshot.private_state,
            "evidence": [item.model_dump(mode="json") for item in snapshot.public_evidence],
            "digest": snapshot.digest,
            "server_path_available": False,
            "network_used": False,
        }

    def event_snapshots(self) -> tuple[dict[str, object], ...]:
        directory = self.data_root / "manifests" / "events"
        if not directory.is_dir():
            return ()
        return tuple(
            self.event_snapshot_view(
                EventDatasetSnapshot.model_validate_json(path.read_text(encoding="utf-8"))
            )
            for path in sorted(directory.glob("*.json"))
        )

    def event_snapshot(self, snapshot_id: str) -> dict[str, object]:
        try:
            return self.event_snapshot_view(self.events.load_snapshot(snapshot_id))
        except LocalImportError as error:
            raise MonitoringAdapterError(str(error)) from error

    def preview_policy(self, fields: PolicyFields) -> dict[str, object]:
        version_number = 1 + sum(
            item.get("policy", {}).get("policy_id") == fields.policy_id
            for item in self._list("policies")
        )
        policy = MonitoringPolicyVersion(
            policy_id=fields.policy_id,
            version=version_number,
            daily_percentage_move_threshold=fields.daily_percentage_move_threshold,
            concentration_threshold=fields.concentration_threshold,
            event_relevance_minimum=fields.event_relevance_minimum,
            negative_sentiment_threshold=fields.negative_sentiment_threshold,
            stale_data_maximum_age_seconds=fields.stale_data_maximum_age_seconds,
            historical_var_limit=fields.historical_var_limit,
            scenario_loss_limit=fields.scenario_loss_limit,
            cadence=fields.cadence,
            cadence_metadata=fields.cadence_metadata,
            reviewed_by=fields.reviewed_by,
            reviewed_at=fields.reviewed_at,
            evidence=self.evidence(),
        )
        preview_id = self._record_id("policy-preview", policy.digest or "")
        envelope = {
            "preview_id": preview_id,
            "policy": policy.model_dump(mode="json"),
            "confirmable": True,
            "scheduler_created": False,
            "effects": [],
        }
        self._save("policy-previews", preview_id, envelope)
        return envelope

    def confirm_policy(self, confirmation: ExplicitConfirmation) -> dict[str, object]:
        if not confirmation.confirm:
            raise MonitoringAdapterError("explicit confirm=true is required")
        preview = self._load("policy-previews", confirmation.preview_id)
        policy = MonitoringPolicyVersion.model_validate(preview["policy"])
        policy_id = self._record_id("policy", policy.digest or "")
        return self._save(
            "policies",
            policy_id,
            {
                "policy_id": policy_id,
                "policy": policy.model_dump(mode="json"),
                "confirmed": True,
                "scheduler_created": False,
                "effects": [],
                "human_review_required": True,
            },
        )

    def policies(self) -> tuple[dict[str, object], ...]:
        return self._list("policies")

    def policy(self, policy_id: str) -> dict[str, object]:
        return self._load("policies", policy_id)

    def run(self, request: RunSelectionRequest) -> dict[str, object]:
        context_envelope = self.context(request.context_id)
        policy_envelope = self.policy(request.policy_id)
        context_request = PortfolioDataContextRequest.model_validate(
            context_envelope["request"]
        )
        if request.run_at < context_request.as_of:
            raise MonitoringAdapterError(
                "run_at cannot precede the confirmed context as_of"
            )
        policy = MonitoringPolicyVersion.model_validate(policy_envelope["policy"])
        metrics = self._metrics_for_as_of(context_request, context_request.as_of)
        event_request = None
        event_snapshot = None
        if context_request.event_snapshot_id:
            event_snapshot = self.events.load_snapshot(context_request.event_snapshot_id)
            event_request = EventQueryRequest(
                snapshot_id=event_snapshot.snapshot_id,
                as_of=context_request.as_of,
            )
        run_id = self._record_id(
            "run",
            sha256_digest(
                {
                    "context": request.context_id,
                    "policy": request.policy_id,
                    "run_at": request.run_at,
                    "metrics": metrics,
                }
            ),
        )
        run = DeterministicContextualMonitoringOrchestrator(self.registry).run(
            ContextualMonitoringWorkflowRequest(
                run_id=run_id,
                context_request=context_request,
                policy_version=policy,
                evaluation_id=f"evaluation-{run_id}",
                run_at=request.run_at,
                metrics=metrics,
                event_query_request=event_request,
                event_snapshot=event_snapshot,
                assumptions=("This run was explicitly invoked by a Workbench user.",),
                limitations=("Cadence metadata did not create a scheduler.",),
                evidence_references=self.capability_evidence(
                    str(context_envelope["profile"])
                ),
            )
        )
        return self._save(
            "runs",
            run_id,
            {
                "run_id": run_id,
                "context_id": request.context_id,
                "policy_id": request.policy_id,
                "profile": context_envelope["profile"],
                "run": run.model_dump(mode="json"),
                "review_state": "pending",
                "effects": [],
            },
        )

    def runs(self) -> tuple[dict[str, object], ...]:
        return self._list("runs")

    def run_record(self, run_id: str) -> dict[str, object]:
        return self._load("runs", run_id)

    @staticmethod
    def cadence_seconds(cadence: str) -> int:
        return {"daily": 86_400, "weekly": 604_800, "monthly": 2_592_000}[cadence]

    @staticmethod
    def _metrics_for_as_of(
        context_request: PortfolioDataContextRequest, as_of: datetime
    ) -> tuple[MonitoringMetric, ...]:
        instrument_ids = {
            item.instrument_id for item in context_request.portfolio_snapshot.positions
        }
        entity_to_instrument = {
            item.target_entity_id: item.source_instrument_id
            for item in context_request.crosswalk_records
            if item.source_instrument_id in instrument_ids
            and item.available_at <= as_of
            and item.effective_start <= as_of.date()
            and (
                item.open_ended
                or (
                    item.effective_end is not None
                    and as_of.date() <= item.effective_end
                )
            )
        }
        latest: dict[str, PointInTimeObservation] = {}
        for observation in context_request.market_observations:
            if (
                observation.dataset_snapshot_id
                != context_request.market_dataset_snapshot_id
                or observation.dataset_revision
                != context_request.market_dataset_revision
                or observation.field_name != "return"
                or observation.value is None
                or observation.available_at is None
                or observation.available_at > as_of
            ):
                continue
            current = latest.get(observation.entity_id)
            if current is None or (
                observation.available_at,
                observation.observed_at,
            ) > (current.available_at, current.observed_at):
                latest[observation.entity_id] = observation
        return tuple(
            MonitoringMetric(
                metric="daily_return",
                value=observation.value,
                instrument_id=entity_to_instrument.get(entity_id),
                evidence=observation.evidence,
            )
            for entity_id, observation in sorted(latest.items())
        )

    def _outcomes(
        self,
        snapshot_id: str,
        *,
        start: datetime,
        evaluated_at: datetime,
    ) -> tuple[tuple[OutcomeLabel, ...], str, str]:
        if snapshot_id == "reviewed-empty-outcomes":
            return (
                (),
                "reviewed_empty_outcomes_v1",
                sha256_digest(
                    {
                        "snapshot_id": "reviewed-empty-outcomes",
                        "outcomes": (),
                    }
                ),
            )
        path = (
            Path(__file__).resolve().parents[2]
            / "data"
            / "fixtures"
            / "synthetic"
            / "day23"
            / "synthetic-outcomes.csv"
        )
        content = path.read_bytes()
        digest = "sha256:" + hashlib.sha256(content).hexdigest()
        evidence = (
            MonitoringEvidence(
                evidence_id="outcomes:reviewed-synthetic-outcomes",
                reference="fixture://synthetic/day23/synthetic-outcomes.csv",
                digest=digest,
                description="Immutable reviewed synthetic outcome-label snapshot.",
            ),
        )
        with path.open("r", encoding="utf-8", newline="") as stream:
            rows = tuple(csv.DictReader(stream))
        outcomes = tuple(
            OutcomeLabel(
                outcome_id=row["outcome_id"],
                instrument_id=row["instrument_id"],
                outcome_time=self._timestamp(row["outcome_time"]),
                trigger_available_at=self._timestamp(row["trigger_available_at"]),
                label=row["label"],
                method=row["method"],
                evidence=evidence,
            )
            for row in rows
            if start <= self._timestamp(row["outcome_time"]) <= evaluated_at
            and self._timestamp(row["trigger_available_at"]) <= evaluated_at
        )
        methods = {item.method for item in outcomes}
        if len(methods) > 1:
            raise MonitoringAdapterError(
                "reviewed outcome-label snapshot contains multiple methodologies"
            )
        return (
            outcomes,
            next(iter(methods), "reviewed_synthetic_threshold_label"),
            digest,
        )

    def replay(self, request: ReplaySelectionRequest) -> dict[str, object]:
        if request.end < request.start:
            raise MonitoringAdapterError("replay end cannot precede replay start")
        context_envelope = self.context(request.context_id)
        policy_envelope = self.policy(request.policy_id)
        base = PortfolioDataContextRequest.model_validate(context_envelope["request"])
        if request.start < base.portfolio_snapshot.as_of:
            raise MonitoringAdapterError(
                "replay start cannot precede the selected portfolio snapshot as_of"
            )
        policy = MonitoringPolicyVersion.model_validate(policy_envelope["policy"])
        cadence_seconds = self.cadence_seconds(request.cadence)
        step_count = (
            int((request.end - request.start).total_seconds() // cadence_seconds)
            + 1
        )
        if step_count > MAX_REPLAY_STEPS:
            raise MonitoringAdapterError(
                f"replay exceeds the reviewed maximum of {MAX_REPLAY_STEPS} steps"
            )
        evaluated_at = request.end + timedelta(
            seconds=request.evaluation_horizon_seconds + 1
        )
        outcomes, outcome_method, outcome_snapshot_digest = self._outcomes(
            request.outcome_label_snapshot_id,
            start=request.start,
            evaluated_at=evaluated_at,
        )
        specification_id = self._record_id(
            "replay-specification", sha256_digest(request.model_dump(mode="json"))
        )
        specification = ReplaySpecification(
            specification_id=specification_id,
            start=request.start,
            end=request.end,
            cadence_seconds=cadence_seconds,
            portfolio_snapshot_id=base.portfolio_snapshot_id,
            market_dataset_snapshot_id=base.market_dataset_snapshot_id,
            market_dataset_revision=base.market_dataset_revision,
            fundamental_dataset_snapshot_id=base.fundamental_dataset_snapshot_id,
            fundamental_dataset_revision=base.fundamental_dataset_revision,
            crosswalk_snapshot_id=base.crosswalk_snapshot_id,
            crosswalk_dataset_revision=base.crosswalk_dataset_revision,
            event_snapshot_id=base.event_snapshot_id,
            event_dataset_revision=base.event_dataset_revision,
            policy_revision=policy.revision or "",
            lookback_window_seconds=request.lookback_seconds,
            evaluation_horizon_seconds=request.evaluation_horizon_seconds,
            minimum_labelled_outcomes=3,
            labelled_outcome_method=outcome_method,
            evidence=base.evidence,
        )
        step_inputs: list[ReplayStepInput] = []
        event_snapshot = (
            self.events.load_snapshot(base.event_snapshot_id)
            if base.event_snapshot_id
            else None
        )
        for index, as_of in enumerate(specification.replay_times(), start=1):
            step_request = base.model_copy(update={"as_of": as_of})
            event_query = (
                EventQueryRequest(snapshot_id=event_snapshot.snapshot_id, as_of=as_of)
                if event_snapshot is not None
                else None
            )
            step_inputs.append(
                ReplayStepInput(
                    context_request=step_request,
                    evaluation_id=f"{specification_id}-step-{index}",
                    metrics=self._metrics_for_as_of(step_request, as_of),
                    event_query_request=event_query,
                    event_snapshot=event_snapshot,
                )
            )
        replay_id = self._record_id("replay", specification.digest or "")
        replay_result = self.registry.invoke(
            "monitoring.replay",
            ReplayCapabilityRequest(
                run_id=replay_id,
                specification=specification,
                policy_version=policy,
                step_inputs=tuple(step_inputs),
                evidence_references=self.capability_evidence(
                    str(context_envelope["profile"])
                ),
            ),
        )
        if replay_result.data is None:
            raise MonitoringAdapterError("replay capability returned no replay")
        evaluation_id = self._record_id(
            "evaluation",
            sha256_digest({"replay": replay_result.data.digest, "outcomes": outcomes}),
        )
        evaluation_result = self.registry.invoke(
            "monitoring.evaluate",
            ReplayEvaluationCapabilityRequest(
                evaluation_id=evaluation_id,
                replay_run=replay_result.data,
                outcomes=outcomes,
                evaluated_at=evaluated_at,
                evidence_references=self.capability_evidence(
                    str(context_envelope["profile"])
                ),
            ),
        )
        if evaluation_result.data is None:
            raise MonitoringAdapterError("evaluation capability returned no evaluation")
        self._save(
            "evaluations",
            evaluation_id,
            {
                "evaluation_id": evaluation_id,
                "replay_id": replay_id,
                "evaluation": evaluation_result.data.model_dump(mode="json"),
                "effects": [],
            },
        )
        return self._save(
            "replays",
            replay_id,
            {
                "replay_id": replay_id,
                "context_id": request.context_id,
                "policy_id": request.policy_id,
                "profile": context_envelope["profile"],
                "evaluation_id": evaluation_id,
                "outcome_label_snapshot_id": request.outcome_label_snapshot_id,
                "outcome_label_snapshot_digest": outcome_snapshot_digest,
                "outcomes": [
                    item.model_dump(mode="json") for item in outcomes
                ],
                "replay": replay_result.data.model_dump(mode="json"),
                "effects": [],
                "human_review_required": True,
            },
        )

    def replays(self) -> tuple[dict[str, object], ...]:
        return self._list("replays")

    def replay_record(self, replay_id: str) -> dict[str, object]:
        return self._load("replays", replay_id)

    def evaluation(self, evaluation_id: str) -> dict[str, object]:
        return self._load("evaluations", evaluation_id)

    def report(self, source_id: str) -> dict[str, object]:
        try:
            source = self.run_record(source_id)
            run = source["run"]
            replay = None
            evaluation = None
        except MonitoringAdapterError:
            source = self.replay_record(source_id)
            replay_model = ReplayRun.model_validate(source["replay"])
            replay = replay_model
            evaluation = MonitoringEvaluation.model_validate(
                self.evaluation(str(source["evaluation_id"]))["evaluation"]
            )
            if not replay.steps or replay.steps[0].monitoring_run is None:
                raise MonitoringAdapterError(
                    "a replay report requires at least one completed monitoring run"
                )
            run = replay.steps[0].monitoring_run.model_dump(mode="json")
        policy = MonitoringPolicyVersion.model_validate(
            self.policy(str(source["policy_id"]))["policy"]
        )
        run_model = ContextualMonitoringRun.model_validate(run)
        report_id = self._record_id(
            "report",
            sha256_digest({"source": source_id, "run": run_model.digest}),
        )
        result = self.registry.invoke(
            "monitoring.report.render",
            MonitoringReportCapabilityRequest(
                request=MonitoringReportRequest(
                    report_id=report_id,
                    title="Local Monitoring and Replay Review"
                    if replay is not None
                    else "Local Contextual Monitoring Review",
                    monitoring_run=run_model,
                    policy_version=policy,
                    replay_run=replay,
                    evaluation=evaluation,
                    evidence=run_model.evidence_bundle.evidence,
                ),
                evidence_references=self.capability_evidence(str(source["profile"])),
            ),
        )
        if result.data is None:
            raise MonitoringAdapterError("report capability returned no report")
        return self._save(
            "reports",
            source_id,
            {
                "id": source_id,
                "profile": source["profile"],
                "report": result.data.model_dump(mode="json"),
                "publication_available": False,
                "pdf_available": False,
                "effects": [],
                "human_review_required": True,
            },
        )

    def report_record(self, source_id: str) -> dict[str, object]:
        try:
            return self._load("reports", source_id)
        except MonitoringAdapterError:
            return self.report(source_id)
