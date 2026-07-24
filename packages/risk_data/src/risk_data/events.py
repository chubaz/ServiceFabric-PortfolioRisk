"""Governed local CSV/Parquet event import and point-in-time query service."""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Literal

from pydantic import Field, field_validator, model_validator

from risk_domain.common import ImmutableDomainModel, NonEmptyString, decimal_value, normalize_utc
from risk_domain.digests import sha256_digest
from risk_domain.models import SHA256_DIGEST_PATTERN
from risk_domain.monitoring import MonitoringEvidence

from .pipeline import REPOSITORY_ROOT, resolve_data_root
from .research import SYNTHETIC_FIXTURE_ROOT, LocalImportError, _read_source, _sha256_file
from .research_contracts import PublicationRestriction, SourceFileReference
from .serialization import manifest_json


EVENT_FIELDS = frozenset(
    {
        "source_event_id",
        "entity_id",
        "event_time",
        "available_at",
        "event_type",
        "relevance",
        "sentiment",
        "novelty",
        "amendment_state",
        "supersedes_event_id",
        "event_text",
    }
)


def _optional_utc(value: datetime | None) -> datetime | None:
    return normalize_utc(value) if value is not None else None


class EventProviderProfile(ImmutableDomainModel):
    provider_id: NonEmptyString
    display_name: NonEmptyString
    profile: Literal["synthetic_local", "licensed_local"]
    publication_restriction: PublicationRestriction
    synthetic: bool
    private: bool
    network_enabled: Literal[False] = False

    @model_validator(mode="after")
    def profile_boundary_is_explicit(self) -> "EventProviderProfile":
        if self.profile == "synthetic_local":
            if not self.synthetic or self.private:
                raise ValueError("synthetic_local event profiles must be synthetic and non-private")
            if self.publication_restriction is not PublicationRestriction.SYNTHETIC_ONLY:
                raise ValueError("synthetic event profiles require synthetic_only publication")
        else:
            if self.synthetic or not self.private:
                raise ValueError("licensed_local event profiles must be non-synthetic and private")
            if self.publication_restriction is PublicationRestriction.SYNTHETIC_ONLY:
                raise ValueError("licensed event profiles require a restrictive publication state")
        return self


class EventMappingManifest(ImmutableDomainModel):
    manifest_id: NonEmptyString
    field_mapping: dict[str, str]
    duplicate_source_id_policy: Literal["reject", "deterministic_version"] = "reject"
    relevance_minimum: Decimal = Field(default=Decimal("0"), ge=Decimal("0"), le=Decimal("1"))
    relevance_maximum: Decimal = Field(default=Decimal("1"), ge=Decimal("0"), le=Decimal("1"))
    sentiment_minimum: Decimal = Field(default=Decimal("-1"), ge=Decimal("-1"), le=Decimal("1"))
    sentiment_maximum: Decimal = Field(default=Decimal("1"), ge=Decimal("-1"), le=Decimal("1"))
    novelty_minimum: Decimal = Field(default=Decimal("0"), ge=Decimal("0"), le=Decimal("1"))
    novelty_maximum: Decimal = Field(default=Decimal("1"), ge=Decimal("0"), le=Decimal("1"))
    entity_matching: Literal["explicit_identifier_only"] = "explicit_identifier_only"

    @model_validator(mode="after")
    def fixed_fields_and_ranges_are_reviewed(self) -> "EventMappingManifest":
        required = EVENT_FIELDS - {"event_text", "supersedes_event_id"}
        if not required.issubset(self.field_mapping):
            raise ValueError(f"event mapping is missing required targets: {sorted(required - self.field_mapping)}")
        if not set(self.field_mapping).issubset(EVENT_FIELDS):
            raise ValueError("event mapping contains an unsupported target field")
        if len(set(self.field_mapping.values())) != len(self.field_mapping):
            raise ValueError("event source fields must map at most once")
        if self.relevance_minimum > self.relevance_maximum:
            raise ValueError("relevance reviewed range is invalid")
        if self.sentiment_minimum > self.sentiment_maximum:
            raise ValueError("sentiment reviewed range is invalid")
        if self.novelty_minimum > self.novelty_maximum:
            raise ValueError("novelty reviewed range is invalid")
        return self


class EventImportIssue(ImmutableDomainModel):
    code: NonEmptyString
    severity: Literal["warning", "blocking"]
    message: NonEmptyString
    row_number: int | None = Field(default=None, ge=1)
    field: str | None = None


class LocalEventRecord(ImmutableDomainModel):
    provider_id: NonEmptyString
    source_event_id: NonEmptyString
    local_event_id: NonEmptyString
    entity_id: NonEmptyString
    event_time: datetime
    available_at: datetime | None
    retrieved_at: datetime
    event_type: NonEmptyString
    relevance: Decimal = Field(ge=Decimal("0"), le=Decimal("1"))
    sentiment: Decimal = Field(ge=Decimal("-1"), le=Decimal("1"))
    novelty: Decimal = Field(ge=Decimal("0"), le=Decimal("1"))
    amendment_state: Literal["original", "amendment", "retraction"]
    supersedes_event_id: str | None = None
    publication_restriction: PublicationRestriction
    synthetic: bool
    private: bool
    synthetic_state: Literal["synthetic", "non_synthetic"] | None = None
    private_state: Literal["public_metadata", "private_local"] | None = None
    event_text: str | None = None
    evidence: tuple[MonitoringEvidence, ...] = Field(min_length=1)

    _event_time = field_validator("event_time")(normalize_utc)
    _available_at = field_validator("available_at")(_optional_utc)
    _retrieved_at = field_validator("retrieved_at")(normalize_utc)
    _relevance = field_validator("relevance")(decimal_value)
    _sentiment = field_validator("sentiment")(decimal_value)
    _novelty = field_validator("novelty")(decimal_value)

    @model_validator(mode="after")
    def amendment_link_is_explicit(self) -> "LocalEventRecord":
        if self.amendment_state == "original" and self.supersedes_event_id is not None:
            raise ValueError("original events cannot supersede another event")
        if self.amendment_state in {"amendment", "retraction"} and self.supersedes_event_id is None:
            raise ValueError("amendments and retractions must link to the prior event")
        if self.private and self.publication_restriction is PublicationRestriction.SYNTHETIC_ONLY:
            raise ValueError("private event records cannot claim synthetic-only publication")
        expected_synthetic_state = "synthetic" if self.synthetic else "non_synthetic"
        expected_private_state = "private_local" if self.private else "public_metadata"
        if self.synthetic_state not in {None, expected_synthetic_state}:
            raise ValueError("synthetic_state must reflect the explicit synthetic flag")
        if self.private_state not in {None, expected_private_state}:
            raise ValueError("private_state must reflect the explicit private flag")
        object.__setattr__(self, "synthetic_state", expected_synthetic_state)
        object.__setattr__(self, "private_state", expected_private_state)
        return self

    def public_copy(self) -> "LocalEventRecord":
        """Return permitted metadata only; private event text never enters public evidence."""

        return self.model_copy(update={"event_text": None}) if self.private else self

    @property
    def event_id(self) -> str:
        """Compatibility accessor; serialized contracts expose local_event_id."""

        return self.local_event_id


class EventImportPreview(ImmutableDomainModel):
    preview_digest: str = Field(pattern=rf"^{SHA256_DIGEST_PATTERN}$")
    source: SourceFileReference
    provider: EventProviderProfile
    dataset_revision: NonEmptyString
    mapping_manifest: EventMappingManifest
    retrieved_at: datetime
    records: tuple[LocalEventRecord, ...]
    row_count: int = Field(ge=0)
    accepted_row_count: int = Field(ge=0)
    rejected_row_count: int = Field(ge=0)
    issues: tuple[EventImportIssue, ...] = ()
    public_evidence: tuple[MonitoringEvidence, ...] = Field(min_length=1)

    _retrieved_at = field_validator("retrieved_at")(normalize_utc)

    @property
    def has_blocking_issues(self) -> bool:
        return any(item.severity == "blocking" for item in self.issues)


class EventDatasetSnapshot(ImmutableDomainModel):
    snapshot_id: NonEmptyString
    provider_id: NonEmptyString
    dataset_revision: NonEmptyString
    created_at: datetime
    source_digest: str = Field(pattern=rf"^{SHA256_DIGEST_PATTERN}$")
    mapping_manifest_id: NonEmptyString
    records: tuple[LocalEventRecord, ...]
    publication_restriction: PublicationRestriction
    synthetic: bool
    private: bool
    synthetic_state: Literal["synthetic", "non_synthetic"] | None = None
    private_state: Literal["public_metadata", "private_local"] | None = None
    public_evidence: tuple[MonitoringEvidence, ...] = Field(min_length=1)
    evidence: tuple[MonitoringEvidence, ...] = ()
    supersedes_snapshot_id: str | None = None
    digest: str | None = Field(default=None, pattern=rf"^{SHA256_DIGEST_PATTERN}$")

    _created_at = field_validator("created_at")(normalize_utc)

    @model_validator(mode="after")
    def immutable_snapshot(self) -> "EventDatasetSnapshot":
        ids = [item.local_event_id for item in self.records]
        if ids != sorted(ids) or len(ids) != len(set(ids)):
            raise ValueError("event records must be uniquely and deterministically ordered")
        expected_synthetic_state = "synthetic" if self.synthetic else "non_synthetic"
        expected_private_state = "private_local" if self.private else "public_metadata"
        if self.synthetic_state not in {None, expected_synthetic_state}:
            raise ValueError("snapshot synthetic_state is inconsistent")
        if self.private_state not in {None, expected_private_state}:
            raise ValueError("snapshot private_state is inconsistent")
        object.__setattr__(self, "synthetic_state", expected_synthetic_state)
        object.__setattr__(self, "private_state", expected_private_state)
        if self.evidence and self.evidence != self.public_evidence:
            raise ValueError("event snapshot evidence must be publication-safe evidence")
        object.__setattr__(self, "evidence", self.public_evidence)
        expected = sha256_digest(self)
        if self.digest is not None and self.digest != expected:
            raise ValueError("digest must equal the canonical event-snapshot digest")
        object.__setattr__(self, "digest", expected)
        return self


class EventQueryRequest(ImmutableDomainModel):
    snapshot_id: NonEmptyString
    as_of: datetime
    entity_ids: tuple[str, ...] = ()
    event_types: tuple[str, ...] = ()
    minimum_relevance: Decimal | None = Field(default=None, ge=Decimal("0"), le=Decimal("1"))
    include_private_text: bool = False
    limit: int = Field(default=100, ge=1, le=1000)

    _as_of = field_validator("as_of")(normalize_utc)


class EventQueryResult(ImmutableDomainModel):
    snapshot_id: NonEmptyString
    dataset_revision: NonEmptyString
    as_of: datetime
    records: tuple[LocalEventRecord, ...]
    evidence: tuple[MonitoringEvidence, ...] = Field(min_length=1)
    warnings: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()
    digest: str | None = Field(default=None, pattern=rf"^{SHA256_DIGEST_PATTERN}$")

    _as_of = field_validator("as_of")(normalize_utc)

    @model_validator(mode="after")
    def deterministic_query_result(self) -> "EventQueryResult":
        if any(item.available_at is None or item.available_at > self.as_of for item in self.records):
            raise ValueError("event query results must satisfy available_at <= as_of")
        expected = sha256_digest(self)
        if self.digest is not None and self.digest != expected:
            raise ValueError("digest must equal the canonical event-query digest")
        object.__setattr__(self, "digest", expected)
        return self


def query_event_snapshot(
    request: EventQueryRequest,
    snapshot: EventDatasetSnapshot,
) -> EventQueryResult:
    """Query a supplied immutable snapshot without storage or network access."""

    if snapshot.snapshot_id != request.snapshot_id:
        raise LocalImportError("event query snapshot ID does not match supplied snapshot")
    entity_filter = set(request.entity_ids)
    type_filter = set(request.event_types)
    records = [
        item
        for item in snapshot.records
        if item.available_at is not None
        and item.available_at <= request.as_of
        and (not entity_filter or item.entity_id in entity_filter)
        and (not type_filter or item.event_type in type_filter)
        and (
            request.minimum_relevance is None
            or item.relevance >= request.minimum_relevance
        )
    ]
    records.sort(
        key=lambda item: (item.available_at, item.event_time, item.local_event_id)
    )
    records = records[: request.limit]
    if not request.include_private_text:
        records = [item.public_copy() for item in records]
    warnings = []
    if any(item.available_at is None for item in snapshot.records):
        warnings.append(
            "Events with missing available_at were excluded; event_time was not substituted."
        )
    if snapshot.private and not request.include_private_text:
        warnings.append("Private licensed event text was redacted from the query result.")
    return EventQueryResult(
        snapshot_id=snapshot.snapshot_id,
        dataset_revision=snapshot.dataset_revision,
        as_of=request.as_of,
        records=tuple(records),
        evidence=snapshot.public_evidence,
        warnings=tuple(warnings),
        limitations=(
            "Entity filtering uses explicit stable identifiers only; no ticker or fuzzy matching is available.",
            "This local query performs no provider network access.",
        ),
    )


def load_event_mapping_manifest(path: Path | str) -> EventMappingManifest:
    candidate = Path(path)
    if not candidate.is_file() or candidate.suffix.lower() != ".json":
        raise LocalImportError("event mapping manifest must be an existing JSON file")
    try:
        return EventMappingManifest.model_validate(json.loads(candidate.read_text(encoding="utf-8")))
    except (json.JSONDecodeError, ValueError) as error:
        raise LocalImportError(f"invalid event mapping manifest: {error}") from error


def _parse_datetime(value: Any, *, nullable: bool = False) -> datetime | None:
    text = "" if value is None else str(value).strip()
    if not text and nullable:
        return None
    parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    return normalize_utc(parsed)


def _parse_decimal(value: Any) -> Decimal:
    parsed = Decimal(str(value).strip())
    return decimal_value(parsed)


class EventDataPlane:
    """Local-only event storage with explicit preview and confirmation."""

    def __init__(self, data_root: Path | str | None = None) -> None:
        self.data_root = resolve_data_root(data_root)

    @staticmethod
    def _validate_source(source_path: Path | str, provider: EventProviderProfile) -> Path:
        supplied = Path(source_path)
        if not supplied.is_absolute():
            raise LocalImportError("event source path must be absolute")
        source = supplied.resolve(strict=True)
        in_repository = source == REPOSITORY_ROOT or REPOSITORY_ROOT in source.parents
        reviewed_fixture = (
            provider.profile == "synthetic_local"
            and (source == SYNTHETIC_FIXTURE_ROOT or SYNTHETIC_FIXTURE_ROOT in source.parents)
        )
        if in_repository and not reviewed_fixture:
            raise LocalImportError("private or licensed event sources must remain outside the repository")
        if source.suffix.lower() not in {".csv", ".parquet"}:
            raise LocalImportError("event import accepts local CSV and Parquet only")
        return source

    def preview_event_export(
        self,
        source_path: Path | str,
        *,
        provider: EventProviderProfile,
        dataset_revision: str,
        mapping_manifest: EventMappingManifest | Path | str,
        retrieved_at: datetime,
    ) -> EventImportPreview:
        source = self._validate_source(source_path, provider)
        mapping = (
            load_event_mapping_manifest(mapping_manifest)
            if isinstance(mapping_manifest, (Path, str))
            else mapping_manifest
        )
        retrieved_at = normalize_utc(retrieved_at)
        rows, schema = _read_source(source)
        available_fields = {item.field_name for item in schema}
        issues: list[EventImportIssue] = []
        missing = sorted(set(mapping.field_mapping.values()) - available_fields)
        issues.extend(
            EventImportIssue(
                code="missing_source_field",
                severity="blocking",
                message=f"Mapped event source field {field} is absent.",
                field=field,
            )
            for field in missing
        )
        normalized: list[dict[str, Any]] = []
        if not missing:
            for row_number, source_row in enumerate(rows, start=2):
                values = {
                    target: source_row.get(source_field)
                    for target, source_field in mapping.field_mapping.items()
                }
                try:
                    source_event_id = str(values["source_event_id"]).strip()
                    entity_id = str(values["entity_id"]).strip()
                    event_type = str(values["event_type"]).strip()
                    amendment_state = str(values["amendment_state"]).strip().lower()
                    if not source_event_id or not entity_id or not event_type:
                        raise ValueError("required event identifier is missing")
                    if amendment_state not in {"original", "amendment", "retraction"}:
                        raise ValueError("unsupported amendment state")
                    event_time = _parse_datetime(values["event_time"])
                    available_at = _parse_datetime(values["available_at"], nullable=True)
                    relevance = _parse_decimal(values["relevance"])
                    sentiment = _parse_decimal(values["sentiment"])
                    novelty = _parse_decimal(values["novelty"])
                except (ValueError, TypeError, InvalidOperation) as error:
                    issues.append(
                        EventImportIssue(
                            code="invalid_event_record",
                            severity="blocking",
                            message=f"Invalid event record: {error}",
                            row_number=row_number,
                        )
                    )
                    continue
                if available_at is None:
                    issues.append(
                        EventImportIssue(
                            code="missing_available_at",
                            severity="warning",
                            message="Missing event availability remains missing and is excluded from point-in-time queries.",
                            row_number=row_number,
                            field=mapping.field_mapping["available_at"],
                        )
                    )
                ranges = (
                    ("relevance", relevance, mapping.relevance_minimum, mapping.relevance_maximum),
                    ("sentiment", sentiment, mapping.sentiment_minimum, mapping.sentiment_maximum),
                    ("novelty", novelty, mapping.novelty_minimum, mapping.novelty_maximum),
                )
                out_of_range = False
                for field, value, minimum, maximum in ranges:
                    if value < minimum or value > maximum:
                        issues.append(
                            EventImportIssue(
                                code="score_out_of_reviewed_range",
                                severity="blocking",
                                message=f"{field} is outside its reviewed Decimal range.",
                                row_number=row_number,
                                field=mapping.field_mapping[field],
                            )
                        )
                        out_of_range = True
                if out_of_range:
                    continue
                normalized.append(
                    {
                        "row_number": row_number,
                        "source_event_id": source_event_id,
                        "entity_id": entity_id,
                        "event_time": event_time,
                        "available_at": available_at,
                        "event_type": event_type,
                        "relevance": relevance,
                        "sentiment": sentiment,
                        "novelty": novelty,
                        "amendment_state": amendment_state,
                        "supersedes_source_id": (
                            str(values.get("supersedes_event_id") or "").strip() or None
                        ),
                        "event_text": str(values.get("event_text") or "").strip() or None,
                    }
                )
        counts = Counter(item["source_event_id"] for item in normalized)
        duplicates = {key for key, count in counts.items() if count > 1}
        if duplicates:
            severity: Literal["warning", "blocking"] = (
                "blocking"
                if mapping.duplicate_source_id_policy == "reject"
                else "warning"
            )
            for duplicate in sorted(duplicates):
                issues.append(
                    EventImportIssue(
                        code=(
                            "duplicate_source_event_id"
                            if severity == "blocking"
                            else "duplicate_source_event_id_versioned"
                        ),
                        severity=severity,
                        message=(
                            f"Duplicate source event ID {duplicate!r} was "
                            + (
                                "rejected."
                                if severity == "blocking"
                                else "deterministically versioned."
                            )
                        ),
                    )
                )
        occurrence: Counter[str] = Counter()
        built: list[LocalEventRecord] = []
        prior_by_source: dict[str, str] = {}
        for item in sorted(
            normalized,
            key=lambda value: (
                value["available_at"] or value["event_time"],
                value["event_time"],
                value["source_event_id"],
                value["row_number"],
            ),
        ):
            if (
                mapping.duplicate_source_id_policy == "reject"
                and item["source_event_id"] in duplicates
            ):
                continue
            occurrence[item["source_event_id"]] += 1
            version = occurrence[item["source_event_id"]]
            event_id = sha256_digest(
                {
                    "provider_id": provider.provider_id,
                    "source_event_id": item["source_event_id"],
                    "version": version,
                    "event_time": item["event_time"],
                    "available_at": item["available_at"],
                    "amendment_state": item["amendment_state"],
                }
            )
            supersedes = item["supersedes_source_id"]
            if item["amendment_state"] in {"amendment", "retraction"}:
                linked = prior_by_source.get(supersedes or "") or prior_by_source.get(
                    item["source_event_id"]
                )
                if linked is None:
                    issues.append(
                        EventImportIssue(
                            code="missing_superseded_event",
                            severity="blocking",
                            message="Amendment or retraction does not identify a prior imported event.",
                            row_number=item["row_number"],
                        )
                    )
                    continue
                supersedes = linked
            else:
                supersedes = None
            metadata = {
                "provider_id": provider.provider_id,
                "source_event_id": item["source_event_id"],
                "local_event_id": event_id,
                "entity_id": item["entity_id"],
                "event_time": item["event_time"],
                "available_at": item["available_at"],
                "event_type": item["event_type"],
                "relevance": item["relevance"],
                "sentiment": item["sentiment"],
                "novelty": item["novelty"],
                "amendment_state": item["amendment_state"],
                "supersedes_event_id": supersedes,
                "event_text_digest": sha256_digest(item["event_text"]) if item["event_text"] else None,
            }
            evidence = MonitoringEvidence(
                evidence_id=f"event:{event_id.removeprefix('sha256:')}",
                reference=f"local-event://{provider.provider_id}/{event_id.removeprefix('sha256:')}",
                digest=sha256_digest(metadata),
                description="Publication-safe event metadata and optional private-text digest.",
            )
            built.append(
                LocalEventRecord(
                    provider_id=provider.provider_id,
                    source_event_id=item["source_event_id"],
                    local_event_id=event_id,
                    entity_id=item["entity_id"],
                    event_time=item["event_time"],
                    available_at=item["available_at"],
                    retrieved_at=retrieved_at,
                    event_type=item["event_type"],
                    relevance=item["relevance"],
                    sentiment=item["sentiment"],
                    novelty=item["novelty"],
                    amendment_state=item["amendment_state"],
                    supersedes_event_id=supersedes,
                    publication_restriction=provider.publication_restriction,
                    synthetic=provider.synthetic,
                    private=provider.private,
                    event_text=item["event_text"],
                    evidence=(evidence,),
                )
            )
            prior_by_source[item["source_event_id"]] = event_id
        source_digest = _sha256_file(source)
        source_reference = SourceFileReference(
            absolute_path=source,
            file_format="csv" if source.suffix.lower() == ".csv" else "parquet",
            source_digest=source_digest,
            byte_count=source.stat().st_size,
        )
        public_evidence = tuple(
            sorted(
                (record.evidence[0] for record in built),
                key=lambda item: item.evidence_id,
            )
        ) or (
            MonitoringEvidence(
                evidence_id=f"event-source:{source_digest.removeprefix('sha256:')}",
                reference=f"local-event-source://{provider.provider_id}",
                digest=source_digest,
                description="Local event source digest; source contents are not public evidence.",
            ),
        )
        rejected = len(rows) - len(built)
        payload = {
            "source": source_reference,
            "provider": provider,
            "dataset_revision": dataset_revision,
            "mapping_manifest": mapping,
            "retrieved_at": retrieved_at,
            "records": tuple(sorted(built, key=lambda item: item.local_event_id)),
            "row_count": len(rows),
            "accepted_row_count": len(built),
            "rejected_row_count": rejected,
            "issues": tuple(issues),
            "public_evidence": public_evidence,
        }
        return EventImportPreview(preview_digest=sha256_digest(payload), **payload)

    def confirm_event_export(
        self,
        preview: EventImportPreview,
        *,
        confirm: bool,
        preview_digest: str,
        source_digest: str,
    ) -> EventDatasetSnapshot:
        if not confirm:
            raise LocalImportError("explicit confirm=true is required")
        if preview_digest != preview.preview_digest:
            raise LocalImportError("event confirmation preview digest does not match")
        if source_digest != preview.source.source_digest or _sha256_file(
            preview.source.absolute_path
        ) != preview.source.source_digest:
            raise LocalImportError("event source digest no longer matches preview")
        if preview.has_blocking_issues:
            raise LocalImportError("event preview contains unresolved blocking issues")
        snapshot_id = (
            "events-"
            + sha256_digest(
                {
                    "preview": preview.preview_digest,
                    "revision": preview.dataset_revision,
                    "provider": preview.provider.provider_id,
                }
            ).removeprefix("sha256:")[:24]
        )
        path = self._snapshot_path(snapshot_id)
        if path.is_file():
            return EventDatasetSnapshot.model_validate(
                json.loads(path.read_text(encoding="utf-8"))
            )
        prior = self._latest_snapshot_id(preview.provider.provider_id)
        snapshot = EventDatasetSnapshot(
            snapshot_id=snapshot_id,
            provider_id=preview.provider.provider_id,
            dataset_revision=preview.dataset_revision,
            created_at=preview.retrieved_at,
            source_digest=preview.source.source_digest,
            mapping_manifest_id=preview.mapping_manifest.manifest_id,
            records=tuple(
                sorted(preview.records, key=lambda item: item.local_event_id)
            ),
            publication_restriction=preview.provider.publication_restriction,
            synthetic=preview.provider.synthetic,
            private=preview.provider.private,
            public_evidence=preview.public_evidence,
            supersedes_snapshot_id=prior,
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("x", encoding="utf-8") as stream:
            stream.write(manifest_json(snapshot))
        return snapshot

    def query_events(
        self,
        request: EventQueryRequest,
        snapshot: EventDatasetSnapshot | None = None,
    ) -> EventQueryResult:
        return query_event_snapshot(request, snapshot or self.load_snapshot(request.snapshot_id))

    def load_snapshot(self, snapshot_id: str) -> EventDatasetSnapshot:
        if not snapshot_id or any(character not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-" for character in snapshot_id):
            raise LocalImportError("event snapshot ID must be path-safe")
        path = self._snapshot_path(snapshot_id)
        if not path.is_file():
            raise LocalImportError(f"event snapshot is unavailable: {snapshot_id}")
        return EventDatasetSnapshot.model_validate(json.loads(path.read_text(encoding="utf-8")))

    def _snapshot_path(self, snapshot_id: str) -> Path:
        root = self.data_root.resolve()
        path = (root / "manifests" / "events" / f"{snapshot_id}.json").resolve(
            strict=False
        )
        if root not in path.parents:
            raise LocalImportError("event snapshot path escapes the local data root")
        return path

    def _latest_snapshot_id(self, provider_id: str) -> str | None:
        directory = self.data_root / "manifests" / "events"
        if not directory.exists():
            return None
        snapshots = [
            EventDatasetSnapshot.model_validate(json.loads(path.read_text(encoding="utf-8")))
            for path in directory.glob("*.json")
        ]
        matching = [item for item in snapshots if item.provider_id == provider_id]
        return (
            max(matching, key=lambda item: (item.created_at, item.snapshot_id)).snapshot_id
            if matching
            else None
        )
