"""Immutable contracts for portfolio-linked monitoring and historical replay."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal
from statistics import median
from typing import Literal

from pydantic import Field, field_validator, model_validator

from .common import ImmutableDomainModel, NonEmptyString, decimal_value, normalize_utc
from .digests import sha256_digest
from .models import PortfolioSnapshot, SHA256_DIGEST_PATTERN


Digest = str
MappingState = Literal["mapped", "unmapped", "ambiguous"]
FindingSeverity = Literal["info", "warning", "high", "blocking"]
FOUR_MONITORING_ROLES = (
    "risk.agent.market_data",
    "risk.agent.portfolio_exposure",
    "risk.agent.news_sentiment",
    "risk.agent.alert_recommendation",
)


def _optional_utc(value: datetime | None) -> datetime | None:
    return normalize_utc(value) if value is not None else None


class MonitoringEvidence(ImmutableDomainModel):
    """A publication-safe reference to retained local evidence."""

    evidence_id: NonEmptyString
    reference: NonEmptyString
    digest: Digest | None = Field(default=None, pattern=rf"^{SHA256_DIGEST_PATTERN}$")
    description: str | None = None


class DateEffectiveMapping(ImmutableDomainModel):
    """An explicit, date-effective stable-identifier link."""

    crosswalk_snapshot_id: NonEmptyString
    crosswalk_dataset_revision: NonEmptyString
    source_instrument_id: NonEmptyString
    target_entity_id: NonEmptyString
    fundamental_entity_id: str | None = None
    effective_start: date
    effective_end: date | None = None
    open_ended: bool = False
    available_at: datetime
    reviewed_primary: bool = False
    evidence: tuple[MonitoringEvidence, ...] = Field(min_length=1)

    _available_at = field_validator("available_at")(_optional_utc)

    @model_validator(mode="after")
    def effective_range_is_explicit(self) -> "DateEffectiveMapping":
        if self.open_ended != (self.effective_end is None):
            raise ValueError("open-ended mappings must be explicit")
        if self.effective_end is not None and self.effective_end < self.effective_start:
            raise ValueError("effective_end cannot precede effective_start")
        return self


class PointInTimeObservation(ImmutableDomainModel):
    """One local observation with separate observation and availability time."""

    dataset_snapshot_id: NonEmptyString
    dataset_revision: NonEmptyString
    entity_id: NonEmptyString
    field_name: NonEmptyString = "valuation_price"
    observed_at: datetime
    available_at: datetime | None
    retrieved_at: datetime
    value: Decimal | None = None
    unit: str | None = None
    quality_flags: tuple[str, ...] = ()
    evidence: tuple[MonitoringEvidence, ...] = Field(min_length=1)

    _observed_at = field_validator("observed_at")(normalize_utc)
    _available_at = field_validator("available_at")(_optional_utc)
    _retrieved_at = field_validator("retrieved_at")(normalize_utc)

    @field_validator("value")
    @classmethod
    def finite_value(cls, value: Decimal | None) -> Decimal | None:
        return decimal_value(value) if value is not None else None


class DataVintageSelection(ImmutableDomainModel):
    dataset_kind: Literal["portfolio", "market", "fundamental", "crosswalk", "event"]
    dataset_snapshot_id: NonEmptyString
    dataset_revision: NonEmptyString
    retrieved_at: datetime
    as_of: datetime
    selection_rule: Literal["available_at_lte_as_of"] = "available_at_lte_as_of"
    selected_observation_count: int = Field(ge=0)
    evidence: tuple[MonitoringEvidence, ...] = Field(min_length=1)

    _retrieved_at = field_validator("retrieved_at")(normalize_utc)
    _as_of = field_validator("as_of")(normalize_utc)

class InstrumentDataBinding(ImmutableDomainModel):
    instrument_id: NonEmptyString
    entity_id: str | None = None
    fundamental_entity_id: str | None = None
    state: MappingState
    crosswalk_snapshot_id: NonEmptyString
    mapping_rule: Literal["exact_date_effective", "reviewed_primary", "none"]
    effective_start: date | None = None
    effective_end: date | None = None
    evidence: tuple[MonitoringEvidence, ...] = ()

    @model_validator(mode="after")
    def mapping_state_is_consistent(self) -> "InstrumentDataBinding":
        if self.state == "mapped" and (self.entity_id is None or not self.evidence):
            raise ValueError("mapped bindings require an entity and mapping evidence")
        if self.state != "mapped" and (
            self.entity_id is not None or self.fundamental_entity_id is not None
        ):
            raise ValueError("unmapped or ambiguous bindings cannot claim an entity")
        if self.state == "mapped" and self.mapping_rule == "none":
            raise ValueError("mapped bindings must record the exact resolution rule")
        if self.state != "mapped" and self.mapping_rule != "none":
            raise ValueError("unresolved bindings must record rule none")
        return self


class MappingCoverage(ImmutableDomainModel):
    position_count: int = Field(ge=0)
    mapped_count: int = Field(ge=0)
    unmapped_count: int = Field(ge=0)
    ambiguous_count: int = Field(ge=0)
    coverage: Decimal = Field(ge=Decimal("0"), le=Decimal("1"))
    complete: bool

    _coverage = field_validator("coverage")(decimal_value)

    @model_validator(mode="after")
    def counts_and_ratio_are_exact(self) -> "MappingCoverage":
        if self.mapped_count + self.unmapped_count + self.ambiguous_count != self.position_count:
            raise ValueError("mapping coverage counts must reconcile to position_count")
        expected = (
            Decimal(self.mapped_count) / Decimal(self.position_count)
            if self.position_count
            else Decimal("0")
        )
        if self.coverage != expected:
            raise ValueError("mapping coverage must equal mapped_count divided by position_count")
        expected_complete = self.position_count > 0 and self.mapped_count == self.position_count
        if self.complete != expected_complete:
            raise ValueError("mapping completeness must reflect all portfolio positions")
        if not self.complete and self.coverage == Decimal("1"):
            raise ValueError("incomplete mapping coverage cannot be represented as 100%")
        return self


class ContextQualityIssue(ImmutableDomainModel):
    code: NonEmptyString
    severity: Literal["warning", "blocking"]
    message: NonEmptyString
    instrument_id: str | None = None
    dataset_snapshot_id: str | None = None


class PortfolioDataContextRequest(ImmutableDomainModel):
    portfolio_snapshot_id: NonEmptyString
    portfolio_snapshot: PortfolioSnapshot
    market_dataset_snapshot_id: NonEmptyString
    market_dataset_revision: NonEmptyString
    market_dataset_retrieved_at: datetime
    market_observations: tuple[PointInTimeObservation, ...]
    fundamental_dataset_snapshot_id: str | None = None
    fundamental_dataset_revision: str | None = None
    fundamental_dataset_retrieved_at: datetime | None = None
    fundamental_observations: tuple[PointInTimeObservation, ...] = ()
    crosswalk_snapshot_id: NonEmptyString
    crosswalk_dataset_revision: NonEmptyString
    crosswalk_retrieved_at: datetime
    crosswalk_records: tuple[DateEffectiveMapping, ...]
    event_snapshot_id: str | None = None
    event_dataset_revision: str | None = None
    event_dataset_retrieved_at: datetime | None = None
    as_of: datetime
    stale_data_maximum_age_seconds: int = Field(ge=1)
    reviewed_primary_rule: Literal["reviewed_primary=true"] | None = None
    evidence: tuple[MonitoringEvidence, ...] = Field(min_length=1)
    assumptions: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()

    _market_retrieved = field_validator("market_dataset_retrieved_at")(normalize_utc)
    _fundamental_retrieved = field_validator("fundamental_dataset_retrieved_at")(_optional_utc)
    _crosswalk_retrieved = field_validator("crosswalk_retrieved_at")(normalize_utc)
    _event_retrieved = field_validator("event_dataset_retrieved_at")(_optional_utc)
    _as_of = field_validator("as_of")(normalize_utc)

    @model_validator(mode="after")
    def linked_fields_are_consistent(self) -> "PortfolioDataContextRequest":
        if self.portfolio_snapshot.snapshot_id != self.portfolio_snapshot_id:
            raise ValueError("portfolio_snapshot_id must identify portfolio_snapshot")
        fundamental = (
            self.fundamental_dataset_snapshot_id,
            self.fundamental_dataset_revision,
            self.fundamental_dataset_retrieved_at,
        )
        if any(item is not None for item in fundamental) and not all(item is not None for item in fundamental):
            raise ValueError("optional fundamental dataset identity must be complete")
        event = (
            self.event_snapshot_id,
            self.event_dataset_revision,
            self.event_dataset_retrieved_at,
        )
        if any(item is not None for item in event) and not all(item is not None for item in event):
            raise ValueError("optional event dataset identity must be complete")
        if any(
            item.crosswalk_snapshot_id != self.crosswalk_snapshot_id
            or item.crosswalk_dataset_revision != self.crosswalk_dataset_revision
            for item in self.crosswalk_records
        ):
            raise ValueError(
                "every crosswalk record must belong to the selected snapshot and revision"
            )
        return self


class PortfolioDataContext(ImmutableDomainModel):
    portfolio_snapshot_id: NonEmptyString
    market_dataset_snapshot_id: NonEmptyString
    fundamental_dataset_snapshot_id: str | None = None
    crosswalk_snapshot_id: NonEmptyString
    event_snapshot_id: str | None = None
    as_of: datetime
    bindings: tuple[InstrumentDataBinding, ...]
    mapping_coverage: MappingCoverage
    data_vintages: tuple[DataVintageSelection, ...]
    latest_market_observations: tuple[PointInTimeObservation, ...]
    latest_fundamental_observations: tuple[PointInTimeObservation, ...] = ()
    quality_issues: tuple[ContextQualityIssue, ...] = ()
    evidence: tuple[MonitoringEvidence, ...] = Field(min_length=1)
    assumptions: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()
    blocked: bool
    digest: Digest | None = Field(default=None, pattern=rf"^{SHA256_DIGEST_PATTERN}$")

    _as_of = field_validator("as_of")(normalize_utc)

    @model_validator(mode="after")
    def context_is_reconciled_and_content_addressed(self) -> "PortfolioDataContext":
        ids = [item.instrument_id for item in self.bindings]
        if ids != sorted(ids) or len(ids) != len(set(ids)):
            raise ValueError("instrument bindings must be unique and deterministically ordered")
        if len(ids) != self.mapping_coverage.position_count:
            raise ValueError("mapping coverage must describe every binding")
        expected_blocked = any(item.severity == "blocking" for item in self.quality_issues)
        if self.blocked != expected_blocked:
            raise ValueError("blocked must reflect blocking context quality issues")
        expected = sha256_digest(self)
        if self.digest is not None and self.digest != expected:
            raise ValueError("digest must equal the canonical portfolio data context digest")
        object.__setattr__(self, "digest", expected)
        return self


def _latest_observations(
    observations: tuple[PointInTimeObservation, ...],
    *,
    snapshot_id: str,
    revision: str,
    entity_ids: set[str],
    as_of: datetime,
) -> tuple[PointInTimeObservation, ...]:
    selected: dict[tuple[str, str], PointInTimeObservation] = {}
    for item in observations:
        if (
            item.dataset_snapshot_id != snapshot_id
            or item.dataset_revision != revision
            or item.entity_id not in entity_ids
            or item.available_at is None
            or item.available_at > as_of
        ):
            continue
        key = (item.entity_id, item.field_name)
        current = selected.get(key)
        if current is None or (item.available_at, item.observed_at) > (
            current.available_at,
            current.observed_at,
        ):
            selected[key] = item
    return tuple(selected[key] for key in sorted(selected))


def create_portfolio_data_context(request: PortfolioDataContextRequest) -> PortfolioDataContext:
    """Select exact mappings and latest available local observations without look-ahead."""

    issues: list[ContextQualityIssue] = []
    bindings: list[InstrumentDataBinding] = []
    as_of_date = request.as_of.date()
    for position in sorted(request.portfolio_snapshot.positions, key=lambda item: item.instrument_id):
        active = [
            record
            for record in request.crosswalk_records
            if record.source_instrument_id == position.instrument_id
            and record.available_at <= request.as_of
            and record.effective_start <= as_of_date
            and (record.open_ended or (record.effective_end is not None and as_of_date <= record.effective_end))
        ]
        if not active:
            bindings.append(
                InstrumentDataBinding(
                    instrument_id=position.instrument_id,
                    state="unmapped",
                    crosswalk_snapshot_id=request.crosswalk_snapshot_id,
                    mapping_rule="none",
                )
            )
            issues.append(
                ContextQualityIssue(
                    code="missing_mapping",
                    severity="blocking",
                    message="No explicit date-effective crosswalk mapping is available; no ticker or heuristic fallback was used.",
                    instrument_id=position.instrument_id,
                    dataset_snapshot_id=request.crosswalk_snapshot_id,
                )
            )
            continue
        chosen: DateEffectiveMapping | None = None
        rule: Literal["exact_date_effective", "reviewed_primary"] = "exact_date_effective"
        if len(active) == 1:
            chosen = active[0]
        elif request.reviewed_primary_rule == "reviewed_primary=true":
            primaries = [item for item in active if item.reviewed_primary]
            if len(primaries) == 1:
                chosen = primaries[0]
                rule = "reviewed_primary"
        if chosen is None:
            bindings.append(
                InstrumentDataBinding(
                    instrument_id=position.instrument_id,
                    state="ambiguous",
                    crosswalk_snapshot_id=request.crosswalk_snapshot_id,
                    mapping_rule="none",
                )
            )
            issues.append(
                ContextQualityIssue(
                    code="ambiguous_mapping",
                    severity="blocking",
                    message="Overlapping active links are blocking without one explicit reviewed primary.",
                    instrument_id=position.instrument_id,
                    dataset_snapshot_id=request.crosswalk_snapshot_id,
                )
            )
            continue
        bindings.append(
            InstrumentDataBinding(
                instrument_id=position.instrument_id,
                entity_id=chosen.target_entity_id,
                fundamental_entity_id=chosen.fundamental_entity_id,
                state="mapped",
                crosswalk_snapshot_id=request.crosswalk_snapshot_id,
                mapping_rule=rule,
                effective_start=chosen.effective_start,
                effective_end=chosen.effective_end,
                evidence=chosen.evidence,
            )
        )

    mapped = [item for item in bindings if item.state == "mapped"]
    coverage = MappingCoverage(
        position_count=len(bindings),
        mapped_count=len(mapped),
        unmapped_count=sum(item.state == "unmapped" for item in bindings),
        ambiguous_count=sum(item.state == "ambiguous" for item in bindings),
        coverage=Decimal(len(mapped)) / Decimal(len(bindings)) if bindings else Decimal("0"),
        complete=bool(bindings) and len(mapped) == len(bindings),
    )

    vintage_specs: list[tuple[str, str, str, datetime, int]] = [
        (
            "portfolio",
            request.portfolio_snapshot_id,
            request.portfolio_snapshot.digest or "portfolio-contract",
            request.portfolio_snapshot.as_of,
            len(request.portfolio_snapshot.positions),
        ),
        (
            "market",
            request.market_dataset_snapshot_id,
            request.market_dataset_revision,
            request.market_dataset_retrieved_at,
            0,
        ),
        (
            "crosswalk",
            request.crosswalk_snapshot_id,
            request.crosswalk_dataset_revision,
            request.crosswalk_retrieved_at,
            len(mapped),
        ),
    ]
    if request.fundamental_dataset_snapshot_id is not None:
        vintage_specs.append(
            (
                "fundamental",
                request.fundamental_dataset_snapshot_id,
                request.fundamental_dataset_revision or "",
                request.fundamental_dataset_retrieved_at or request.as_of,
                0,
            )
        )
    if request.event_snapshot_id is not None:
        vintage_specs.append(
            (
                "event",
                request.event_snapshot_id,
                request.event_dataset_revision or "",
                request.event_dataset_retrieved_at or request.as_of,
                0,
            )
        )
    entity_ids = {item.entity_id for item in mapped if item.entity_id is not None}
    fundamental_entity_ids = {
        item.fundamental_entity_id or item.entity_id
        for item in mapped
        if item.fundamental_entity_id is not None or item.entity_id is not None
    }
    market = _latest_observations(
        request.market_observations,
        snapshot_id=request.market_dataset_snapshot_id,
        revision=request.market_dataset_revision,
        entity_ids=entity_ids,
        as_of=request.as_of,
    )
    fundamental = (
        _latest_observations(
            request.fundamental_observations,
            snapshot_id=request.fundamental_dataset_snapshot_id or "",
            revision=request.fundamental_dataset_revision or "",
            entity_ids={item for item in fundamental_entity_ids if item is not None},
            as_of=request.as_of,
        )
        if request.fundamental_dataset_snapshot_id
        else ()
    )
    for observation, dataset_kind in (
        *((item, "market") for item in request.market_observations),
        *((item, "fundamental") for item in request.fundamental_observations),
    ):
        relevant_entities = (
            entity_ids if dataset_kind == "market" else fundamental_entity_ids
        )
        expected_snapshot_id = (
            request.market_dataset_snapshot_id
            if dataset_kind == "market"
            else request.fundamental_dataset_snapshot_id
        )
        expected_revision = (
            request.market_dataset_revision
            if dataset_kind == "market"
            else request.fundamental_dataset_revision
        )
        if (
            observation.dataset_snapshot_id == expected_snapshot_id
            and observation.dataset_revision == expected_revision
            and observation.entity_id in relevant_entities
            and observation.available_at is None
        ):
            issues.append(
                ContextQualityIssue(
                    code="missing_availability",
                    severity="warning",
                    message=(
                        f"A supplied {dataset_kind} observation has no available_at; "
                        "it remains ineligible and observed_at was not substituted."
                    ),
                    instrument_id=next(
                        (
                            item.instrument_id
                            for item in mapped
                            if (
                                item.entity_id == observation.entity_id
                                or item.fundamental_entity_id == observation.entity_id
                            )
                        ),
                        None,
                    ),
                    dataset_snapshot_id=observation.dataset_snapshot_id,
                )
            )
    market_entities = {item.entity_id for item in market if item.value is not None}
    for binding in mapped:
        if binding.entity_id not in market_entities:
            issues.append(
                ContextQualityIssue(
                    code="missing_required_market_data",
                    severity="blocking",
                    message="No required market observation with available_at <= as_of is available; zero was not inferred.",
                    instrument_id=binding.instrument_id,
                    dataset_snapshot_id=request.market_dataset_snapshot_id,
                )
            )
    maximum_age = timedelta(seconds=request.stale_data_maximum_age_seconds)
    for observation in market:
        if request.as_of - observation.observed_at > maximum_age:
            issues.append(
                ContextQualityIssue(
                    code="stale_market_data",
                    severity="warning",
                    message="The latest available market observation exceeds the reviewed stale-data maximum age.",
                    instrument_id=next(
                        (
                            item.instrument_id
                            for item in mapped
                            if item.entity_id == observation.entity_id
                        ),
                        None,
                    ),
                    dataset_snapshot_id=request.market_dataset_snapshot_id,
                )
            )

    counts = {
        "market": len(market),
        "fundamental": len(fundamental),
        "portfolio": len(request.portfolio_snapshot.positions),
        "crosswalk": len(mapped),
        "event": 0,
    }
    vintages: list[DataVintageSelection] = []
    for kind, snapshot_id, revision, retrieved_at, _count in vintage_specs:
        vintages.append(
            DataVintageSelection(
                dataset_kind=kind,  # type: ignore[arg-type]
                dataset_snapshot_id=snapshot_id,
                dataset_revision=revision,
                retrieved_at=retrieved_at,
                as_of=request.as_of,
                selected_observation_count=counts[kind],
                evidence=request.evidence,
            )
        )
    warnings = tuple(sorted({item.message for item in issues if item.severity == "warning"}))
    limitations = tuple(
        sorted(
            set(request.limitations)
            | {
                "Only supplied local immutable dataset revisions were considered.",
                "Identifier mapping used exact date-effective crosswalk records only.",
            }
        )
    )
    return PortfolioDataContext(
        portfolio_snapshot_id=request.portfolio_snapshot_id,
        market_dataset_snapshot_id=request.market_dataset_snapshot_id,
        fundamental_dataset_snapshot_id=request.fundamental_dataset_snapshot_id,
        crosswalk_snapshot_id=request.crosswalk_snapshot_id,
        event_snapshot_id=request.event_snapshot_id,
        as_of=request.as_of,
        bindings=tuple(bindings),
        mapping_coverage=coverage,
        data_vintages=tuple(sorted(vintages, key=lambda item: item.dataset_kind)),
        latest_market_observations=market,
        latest_fundamental_observations=fundamental,
        quality_issues=tuple(
            sorted(issues, key=lambda item: (item.severity, item.code, item.instrument_id or ""))
        ),
        evidence=request.evidence,
        assumptions=tuple(sorted(set(request.assumptions))),
        warnings=warnings,
        limitations=limitations,
        blocked=any(item.severity == "blocking" for item in issues),
    )


class MonitoringPolicy(ImmutableDomainModel):
    policy_id: NonEmptyString
    name: NonEmptyString
    description: NonEmptyString
    owner: NonEmptyString
    human_review_required: Literal[True] = True


class MonitoringPolicyVersion(ImmutableDomainModel):
    policy_id: NonEmptyString
    version: int = Field(ge=1)
    daily_percentage_move_threshold: Decimal = Field(gt=Decimal("0"), le=Decimal("1"))
    concentration_threshold: Decimal = Field(gt=Decimal("0"), le=Decimal("1"))
    event_relevance_minimum: Decimal = Field(ge=Decimal("0"), le=Decimal("1"))
    negative_sentiment_threshold: Decimal = Field(ge=Decimal("-1"), le=Decimal("0"))
    stale_data_maximum_age_seconds: int = Field(ge=1)
    historical_var_limit: Decimal | None = Field(default=None, ge=Decimal("0"))
    scenario_loss_limit: Decimal | None = Field(default=None, ge=Decimal("0"))
    cadence: Literal["manual", "daily", "weekly", "monthly"]
    cadence_metadata: NonEmptyString
    reviewed_by: NonEmptyString
    reviewed_at: datetime
    evidence: tuple[MonitoringEvidence, ...] = Field(min_length=1)
    human_review_required: Literal[True] = True
    revision: str | None = Field(default=None, pattern=r"^policy:[a-f0-9]{64}$")
    digest: Digest | None = Field(default=None, pattern=rf"^{SHA256_DIGEST_PATTERN}$")

    _reviewed_at = field_validator("reviewed_at")(normalize_utc)
    _daily_move = field_validator("daily_percentage_move_threshold")(decimal_value)
    _concentration = field_validator("concentration_threshold")(decimal_value)
    _relevance = field_validator("event_relevance_minimum")(decimal_value)
    _sentiment = field_validator("negative_sentiment_threshold")(decimal_value)

    @field_validator("historical_var_limit", "scenario_loss_limit")
    @classmethod
    def finite_optional_threshold(cls, value: Decimal | None) -> Decimal | None:
        return decimal_value(value) if value is not None else None

    @model_validator(mode="after")
    def immutable_revision_and_digest(self) -> "MonitoringPolicyVersion":
        payload = self.model_dump(mode="python", exclude={"revision", "digest"})
        digest = sha256_digest(payload)
        revision = "policy:" + digest.removeprefix("sha256:")
        if self.digest is not None and self.digest != digest:
            raise ValueError("digest must equal the canonical policy-version digest")
        if self.revision is not None and self.revision != revision:
            raise ValueError("revision must equal the canonical immutable policy revision")
        object.__setattr__(self, "digest", digest)
        object.__setattr__(self, "revision", revision)
        return self


class MonitoringMetric(ImmutableDomainModel):
    metric: Literal[
        "daily_return",
        "volatility",
        "drawdown",
        "historical_var",
        "weight",
        "concentration",
        "scenario_loss",
        "contribution",
    ]
    value: Decimal
    instrument_id: str | None = None
    evidence: tuple[MonitoringEvidence, ...] = Field(min_length=1)

    _value = field_validator("value")(decimal_value)


class MonitoringEventSignal(ImmutableDomainModel):
    event_id: NonEmptyString
    entity_id: NonEmptyString
    instrument_id: str | None = None
    event_time: datetime
    available_at: datetime
    relevance: Decimal = Field(ge=Decimal("0"), le=Decimal("1"))
    sentiment: Decimal = Field(ge=Decimal("-1"), le=Decimal("1"))
    novelty: Decimal = Field(ge=Decimal("0"), le=Decimal("1"))
    amendment_state: Literal["original", "amendment", "retraction"]
    evidence: tuple[MonitoringEvidence, ...] = Field(min_length=1)

    _event_time = field_validator("event_time")(normalize_utc)
    _available_at = field_validator("available_at")(normalize_utc)
    _relevance = field_validator("relevance")(decimal_value)
    _sentiment = field_validator("sentiment")(decimal_value)
    _novelty = field_validator("novelty")(decimal_value)


class PolicyEvaluationRequest(ImmutableDomainModel):
    evaluation_id: NonEmptyString
    policy_version: MonitoringPolicyVersion
    context: PortfolioDataContext
    evaluated_at: datetime
    metrics: tuple[MonitoringMetric, ...] = ()
    events: tuple[MonitoringEventSignal, ...] = ()
    evidence: tuple[MonitoringEvidence, ...] = Field(min_length=1)

    _evaluated_at = field_validator("evaluated_at")(normalize_utc)


class PolicyBreach(ImmutableDomainModel):
    breach_id: Digest | None = Field(default=None, pattern=rf"^{SHA256_DIGEST_PATTERN}$")
    breach_type: Literal[
        "daily_percentage_move",
        "concentration",
        "event_sentiment",
        "stale_data",
        "historical_var",
        "scenario_loss",
    ]
    observed_value: Decimal | None = None
    threshold: Decimal | int
    instrument_id: str | None = None
    event_id: str | None = None
    summary: NonEmptyString
    evidence: tuple[MonitoringEvidence, ...] = Field(min_length=1)

    @field_validator("observed_value")
    @classmethod
    def finite_observed_value(cls, value: Decimal | None) -> Decimal | None:
        return decimal_value(value) if value is not None else None

    @model_validator(mode="after")
    def deterministic_breach_id(self) -> "PolicyBreach":
        expected = sha256_digest(self.model_dump(mode="python", exclude={"breach_id"}))
        if self.breach_id is not None and self.breach_id != expected:
            raise ValueError("breach_id must equal the canonical breach digest")
        object.__setattr__(self, "breach_id", expected)
        return self


class PolicyEvaluationResult(ImmutableDomainModel):
    evaluation_id: NonEmptyString
    policy_revision: NonEmptyString
    context_digest: Digest = Field(pattern=rf"^{SHA256_DIGEST_PATTERN}$")
    evaluated_at: datetime
    as_of: datetime
    breaches: tuple[PolicyBreach, ...]
    abstained: bool
    evidence: tuple[MonitoringEvidence, ...] = Field(min_length=1)
    assumptions: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()
    human_review_required: Literal[True] = True
    effects: tuple[()] = ()
    digest: Digest | None = Field(default=None, pattern=rf"^{SHA256_DIGEST_PATTERN}$")

    _evaluated_at = field_validator("evaluated_at")(normalize_utc)
    _as_of = field_validator("as_of")(normalize_utc)

    @model_validator(mode="after")
    def deterministic_evaluation(self) -> "PolicyEvaluationResult":
        expected = sha256_digest(self)
        if self.digest is not None and self.digest != expected:
            raise ValueError("digest must equal the canonical policy-evaluation digest")
        object.__setattr__(self, "digest", expected)
        return self


def evaluate_monitoring_policy(request: PolicyEvaluationRequest) -> PolicyEvaluationResult:
    """Evaluate only the reviewed fixed policy fields."""

    policy = request.policy_version
    breaches: list[PolicyBreach] = []
    if request.context.blocked:
        return PolicyEvaluationResult(
            evaluation_id=request.evaluation_id,
            policy_revision=policy.revision or "",
            context_digest=request.context.digest or "",
            evaluated_at=request.evaluated_at,
            as_of=request.context.as_of,
            breaches=(),
            abstained=True,
            evidence=request.evidence,
            warnings=("Monitoring abstained because the point-in-time data context is incomplete.",),
            limitations=("No missing observation was treated as zero.",),
        )
    for metric in request.metrics:
        threshold: Decimal | None = None
        breach_type: str | None = None
        observed = abs(metric.value)
        if metric.metric == "daily_return":
            threshold, breach_type = policy.daily_percentage_move_threshold, "daily_percentage_move"
        elif metric.metric in {"weight", "concentration"}:
            threshold, breach_type = policy.concentration_threshold, "concentration"
        elif metric.metric == "historical_var" and policy.historical_var_limit is not None:
            threshold, breach_type = policy.historical_var_limit, "historical_var"
        elif metric.metric == "scenario_loss" and policy.scenario_loss_limit is not None:
            threshold, breach_type = policy.scenario_loss_limit, "scenario_loss"
        if threshold is not None and observed >= threshold:
            breaches.append(
                PolicyBreach(
                    breach_type=breach_type,  # type: ignore[arg-type]
                    observed_value=metric.value,
                    threshold=threshold,
                    instrument_id=metric.instrument_id,
                    summary=f"{metric.metric} {metric.value} met or exceeded reviewed threshold {threshold}.",
                    evidence=metric.evidence,
                )
            )
    for event in request.events:
        if (
            event.available_at <= request.context.as_of
            and event.amendment_state != "retraction"
            and event.relevance >= policy.event_relevance_minimum
            and event.sentiment <= policy.negative_sentiment_threshold
        ):
            breaches.append(
                PolicyBreach(
                    breach_type="event_sentiment",
                    observed_value=event.sentiment,
                    threshold=policy.negative_sentiment_threshold,
                    instrument_id=event.instrument_id,
                    event_id=event.event_id,
                    summary="A sufficiently relevant, available negative event met the reviewed sentiment threshold.",
                    evidence=event.evidence,
                )
            )
    maximum_age = timedelta(seconds=policy.stale_data_maximum_age_seconds)
    instrument_by_entity = {
        item.entity_id: item.instrument_id
        for item in request.context.bindings
        if item.entity_id is not None
    }
    for observation in request.context.latest_market_observations:
        if request.context.as_of - observation.observed_at > maximum_age:
            breaches.append(
                PolicyBreach(
                    breach_type="stale_data",
                    threshold=policy.stale_data_maximum_age_seconds,
                    instrument_id=instrument_by_entity.get(observation.entity_id),
                    summary=(
                        "The latest point-in-time market observation exceeds the "
                        "policy's reviewed stale-data maximum age."
                    ),
                    evidence=observation.evidence,
                )
            )
    return PolicyEvaluationResult(
        evaluation_id=request.evaluation_id,
        policy_revision=policy.revision or "",
        context_digest=request.context.digest or "",
        evaluated_at=request.evaluated_at,
        as_of=request.context.as_of,
        breaches=tuple(sorted(breaches, key=lambda item: item.breach_id or "")),
        abstained=False,
        evidence=request.evidence,
        assumptions=("Cadence is descriptive metadata only; this evaluation was explicitly invoked.",),
        limitations=("Policy evaluation is analytical and cannot authorize a transaction or portfolio effect.",),
    )


class MonitoringFinding(ImmutableDomainModel):
    finding_id: Digest | None = Field(default=None, pattern=rf"^{SHA256_DIGEST_PATTERN}$")
    finding_type: NonEmptyString
    severity: FindingSeverity
    instrument_id: str | None = None
    summary: NonEmptyString
    evidence: tuple[MonitoringEvidence, ...] = Field(min_length=1)
    assumptions: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()

    @model_validator(mode="after")
    def deterministic_finding_id(self) -> "MonitoringFinding":
        expected = sha256_digest(self.model_dump(mode="python", exclude={"finding_id"}))
        if self.finding_id is not None and self.finding_id != expected:
            raise ValueError("finding_id must equal the canonical finding digest")
        object.__setattr__(self, "finding_id", expected)
        return self


class MonitoringFindingSet(ImmutableDomainModel):
    findings: tuple[MonitoringFinding, ...]
    digest: Digest | None = Field(default=None, pattern=rf"^{SHA256_DIGEST_PATTERN}$")

    @model_validator(mode="after")
    def ordered_and_content_addressed(self) -> "MonitoringFindingSet":
        ordered = tuple(sorted(self.findings, key=lambda item: item.finding_id or ""))
        if self.findings != ordered:
            object.__setattr__(self, "findings", ordered)
        expected = sha256_digest(self)
        if self.digest is not None and self.digest != expected:
            raise ValueError("digest must equal the canonical finding-set digest")
        object.__setattr__(self, "digest", expected)
        return self


class MonitoringEvidenceBundle(ImmutableDomainModel):
    context_digest: Digest = Field(pattern=rf"^{SHA256_DIGEST_PATTERN}$")
    policy_revision: NonEmptyString
    dataset_revisions: tuple[NonEmptyString, ...]
    evidence: tuple[MonitoringEvidence, ...] = Field(min_length=1)
    assumptions: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()
    digest: Digest | None = Field(default=None, pattern=rf"^{SHA256_DIGEST_PATTERN}$")

    @model_validator(mode="after")
    def deterministic_bundle(self) -> "MonitoringEvidenceBundle":
        expected = sha256_digest(self)
        if self.digest is not None and self.digest != expected:
            raise ValueError("digest must equal the canonical monitoring evidence digest")
        object.__setattr__(self, "digest", expected)
        return self


class MonitoringCapabilityReceipt(ImmutableDomainModel):
    capability_id: NonEmptyString
    status: Literal["succeeded", "stopped"]
    input_digest: Digest = Field(pattern=rf"^{SHA256_DIGEST_PATTERN}$")
    output_digest: Digest = Field(pattern=rf"^{SHA256_DIGEST_PATTERN}$")
    evidence: tuple[MonitoringEvidence, ...] = Field(min_length=1)
    effects: tuple[()] = ()


class MonitoringAgentStep(ImmutableDomainModel):
    sequence: int = Field(ge=1, le=4)
    role: Literal[
        "risk.agent.market_data",
        "risk.agent.portfolio_exposure",
        "risk.agent.news_sentiment",
        "risk.agent.alert_recommendation",
    ]
    capability_id: NonEmptyString
    started_at: datetime
    completed_at: datetime
    summary: NonEmptyString
    receipt: MonitoringCapabilityReceipt
    warnings: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()
    effects: tuple[()] = ()

    _started_at = field_validator("started_at")(normalize_utc)
    _completed_at = field_validator("completed_at")(normalize_utc)


class MonitoringAlertDraft(ImmutableDomainModel):
    alert_id: Digest | None = Field(default=None, pattern=rf"^{SHA256_DIGEST_PATTERN}$")
    state: Literal["draft", "no_breach", "abstained"]
    created_at: datetime
    instrument_ids: tuple[str, ...] = ()
    summary: NonEmptyString
    suggested_next_steps: tuple[
        Literal["continue_monitoring", "scenario_analysis", "further_review"], ...
    ]
    evidence: tuple[MonitoringEvidence, ...] = Field(min_length=1)
    human_review_required: Literal[True] = True
    investment_advice: Literal[False] = False
    effects: tuple[()] = ()
    digest: Digest | None = Field(default=None, pattern=rf"^{SHA256_DIGEST_PATTERN}$")

    _created_at = field_validator("created_at")(normalize_utc)

    @model_validator(mode="after")
    def effect_free_content_addressed_alert(self) -> "MonitoringAlertDraft":
        payload = self.model_dump(mode="python", exclude={"alert_id", "digest"})
        digest = sha256_digest(payload)
        if self.alert_id is not None and self.alert_id != digest:
            raise ValueError("alert_id must equal the canonical alert digest")
        if self.digest is not None and self.digest != digest:
            raise ValueError("digest must equal the canonical alert digest")
        object.__setattr__(self, "alert_id", digest)
        object.__setattr__(self, "digest", digest)
        return self


class ContextualMonitoringRequest(ImmutableDomainModel):
    run_id: NonEmptyString
    context: PortfolioDataContext
    policy_evaluation: PolicyEvaluationResult
    run_at: datetime
    metrics: tuple[MonitoringMetric, ...] = ()
    events: tuple[MonitoringEventSignal, ...] = ()
    capability_receipts: tuple[MonitoringCapabilityReceipt, ...] = Field(
        min_length=4, max_length=4
    )
    alert_draft: MonitoringAlertDraft
    evidence: tuple[MonitoringEvidence, ...] = Field(min_length=1)
    assumptions: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()

    _run_at = field_validator("run_at")(normalize_utc)

    @model_validator(mode="after")
    def inputs_share_context(self) -> "ContextualMonitoringRequest":
        if self.policy_evaluation.context_digest != self.context.digest:
            raise ValueError("policy evaluation and monitoring request must share one data context")
        capability_ids = tuple(
            item.capability_id for item in self.capability_receipts
        )
        if capability_ids != (
            "portfolio.data_context.create",
            "monitoring.policy.evaluate",
            "events.query.as_of",
            "monitoring.alert.synthesize",
        ):
            raise ValueError(
                "contextual monitoring receipts must preserve the four completed role invocations"
            )
        return self


class ContextualMonitoringRun(ImmutableDomainModel):
    run_id: NonEmptyString
    status: Literal["succeeded", "stopped"]
    policy_revision: NonEmptyString
    context_digest: Digest = Field(pattern=rf"^{SHA256_DIGEST_PATTERN}$")
    run_at: datetime
    as_of: datetime
    dataset_revisions: tuple[NonEmptyString, ...]
    capability_receipts: tuple[MonitoringCapabilityReceipt, ...] = Field(min_length=4)
    four_agent_timeline: tuple[MonitoringAgentStep, ...] = Field(min_length=4, max_length=4)
    findings: MonitoringFindingSet
    alert_draft: MonitoringAlertDraft
    evidence_bundle: MonitoringEvidenceBundle
    warnings: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()
    effects: tuple[()] = ()
    human_review_required: Literal[True] = True
    digest: Digest | None = Field(default=None, pattern=rf"^{SHA256_DIGEST_PATTERN}$")

    _run_at = field_validator("run_at")(normalize_utc)
    _as_of = field_validator("as_of")(normalize_utc)

    @model_validator(mode="after")
    def four_roles_and_digest_are_deterministic(self) -> "ContextualMonitoringRun":
        roles = tuple(item.role for item in self.four_agent_timeline)
        sequences = tuple(item.sequence for item in self.four_agent_timeline)
        if roles != FOUR_MONITORING_ROLES or sequences != (1, 2, 3, 4):
            raise ValueError("contextual monitoring requires the existing four roles in deterministic order")
        if tuple(item.receipt for item in self.four_agent_timeline) != self.capability_receipts:
            raise ValueError("timeline must preserve the four capability receipts")
        expected = sha256_digest(self)
        if self.digest is not None and self.digest != expected:
            raise ValueError("digest must equal the canonical monitoring-run digest")
        object.__setattr__(self, "digest", expected)
        return self


def synthesize_monitoring_alert(
    *,
    policy_evaluation: PolicyEvaluationResult,
    run_at: datetime,
    evidence: tuple[MonitoringEvidence, ...],
) -> MonitoringAlertDraft:
    """Create the effect-free alert draft used by the registered alert capability."""

    stopped = policy_evaluation.abstained
    instruments = tuple(
        sorted(
            {
                item.instrument_id
                for item in policy_evaluation.breaches
                if item.instrument_id is not None
            }
        )
    )
    if stopped:
        state: Literal["draft", "no_breach", "abstained"] = "abstained"
        summary = "Monitoring abstained because required point-in-time context was incomplete."
        next_steps = ("further_review",)
    elif policy_evaluation.breaches:
        state = "draft"
        summary = (
            f"{len(policy_evaluation.breaches)} reviewed policy breach finding(s) require "
            "human analytical review; this draft is not investment advice."
        )
        next_steps = ("continue_monitoring", "scenario_analysis", "further_review")
    else:
        state = "no_breach"
        summary = "No reviewed policy breach was detected in the supplied point-in-time context."
        next_steps = ("continue_monitoring",)
    return MonitoringAlertDraft(
        state=state,
        created_at=run_at,
        instrument_ids=instruments,
        summary=summary,
        suggested_next_steps=next_steps,  # type: ignore[arg-type]
        evidence=evidence,
    )


def run_contextual_monitoring(request: ContextualMonitoringRequest) -> ContextualMonitoringRun:
    """Assemble a deterministic run from four completed registered invocations."""

    breach_findings = tuple(
        MonitoringFinding(
            finding_type=breach.breach_type,
            severity="high" if breach.breach_type != "stale_data" else "warning",
            instrument_id=breach.instrument_id,
            summary=breach.summary,
            evidence=breach.evidence,
            assumptions=request.policy_evaluation.assumptions,
            limitations=request.policy_evaluation.limitations,
        )
        for breach in request.policy_evaluation.breaches
    )
    event_findings = tuple(
        MonitoringFinding(
            finding_type="event_intelligence",
            severity=(
                "warning"
                if event.amendment_state in {"amendment", "retraction"}
                else "info"
            ),
            instrument_id=event.instrument_id,
            summary=(
                f"Available event {event.event_id}: relevance {event.relevance}, "
                f"sentiment {event.sentiment}, novelty {event.novelty}, "
                f"state {event.amendment_state}."
            ),
            evidence=event.evidence,
            limitations=("No event text classification or external LLM inference was performed.",),
        )
        for event in request.events
        if event.available_at <= request.context.as_of
    )
    findings = breach_findings + event_findings
    finding_set = MonitoringFindingSet(findings=findings)
    dataset_revisions = tuple(
        sorted(
            f"{item.dataset_kind}:{item.dataset_snapshot_id}:{item.dataset_revision}"
            for item in request.context.data_vintages
        )
    )
    evidence_bundle = MonitoringEvidenceBundle(
        context_digest=request.context.digest or "",
        policy_revision=request.policy_evaluation.policy_revision,
        dataset_revisions=dataset_revisions,
        evidence=request.evidence,
        assumptions=tuple(sorted(set(request.assumptions) | set(request.context.assumptions))),
        warnings=tuple(sorted(set(request.context.warnings) | set(request.policy_evaluation.warnings))),
        limitations=tuple(
            sorted(
                set(request.limitations)
                | set(request.context.limitations)
                | set(request.policy_evaluation.limitations)
            )
        ),
    )
    stopped = request.context.blocked or request.policy_evaluation.abstained
    role_data = (
        (
            "risk.agent.market_data",
            "portfolio.data_context.create",
            "Reviewed point-in-time market observations, returns, volatility, drawdown, and tail-risk context.",
        ),
        (
            "risk.agent.portfolio_exposure",
            "monitoring.policy.evaluate",
            "Reviewed weights, concentration, fixed scenario, and supplied contributions.",
        ),
        (
            "risk.agent.news_sentiment",
            "events.query.as_of",
            "Reviewed point-in-time relevance, sentiment, novelty, amendments, and retractions.",
        ),
        (
            "risk.agent.alert_recommendation",
            "monitoring.alert.synthesize",
            "Synthesized an effect-free analytical alert draft for explicit human review.",
        ),
    )
    steps: list[MonitoringAgentStep] = []
    for sequence, ((role, capability_id, summary), receipt) in enumerate(
        zip(role_data, request.capability_receipts, strict=True), start=1
    ):
        event_disclosures = (
            tuple(
                sorted(
                    {
                        f"Event {event.event_id} is retained as {event.amendment_state}."
                        for event in request.events
                        if event.amendment_state in {"amendment", "retraction"}
                        and event.available_at <= request.context.as_of
                    }
                )
            )
            if role == "risk.agent.news_sentiment"
            else ()
        )
        steps.append(
            MonitoringAgentStep(
                sequence=sequence,
                role=role,  # type: ignore[arg-type]
                capability_id=capability_id,
                started_at=request.run_at,
                completed_at=request.run_at,
                summary=summary,
                receipt=receipt,
                warnings=(
                    request.policy_evaluation.warnings if stopped else ()
                )
                + event_disclosures,
                limitations=("No external provider or external LLM was used.",),
            )
        )
    return ContextualMonitoringRun(
        run_id=request.run_id,
        status="stopped" if stopped else "succeeded",
        policy_revision=request.policy_evaluation.policy_revision,
        context_digest=request.context.digest or "",
        run_at=request.run_at,
        as_of=request.context.as_of,
        dataset_revisions=dataset_revisions,
        capability_receipts=request.capability_receipts,
        four_agent_timeline=tuple(steps),
        findings=finding_set,
        alert_draft=request.alert_draft,
        evidence_bundle=evidence_bundle,
        warnings=evidence_bundle.warnings,
        limitations=tuple(
            sorted(
                set(evidence_bundle.limitations)
                | {
                    "This analytical run makes no predictive claim.",
                    "No transaction, order, trade, rebalance, optimization, or portfolio effect was produced.",
                }
            )
        ),
    )


class OutcomeLabel(ImmutableDomainModel):
    outcome_id: NonEmptyString
    instrument_id: NonEmptyString
    outcome_time: datetime
    trigger_available_at: datetime
    label: NonEmptyString
    method: NonEmptyString
    evidence: tuple[MonitoringEvidence, ...] = Field(min_length=1)

    _outcome_time = field_validator("outcome_time")(normalize_utc)
    _trigger_available_at = field_validator("trigger_available_at")(normalize_utc)

    @model_validator(mode="after")
    def trigger_precedes_outcome(self) -> "OutcomeLabel":
        if self.trigger_available_at > self.outcome_time:
            raise ValueError("trigger_available_at cannot follow outcome_time")
        return self


class ReplaySpecification(ImmutableDomainModel):
    specification_id: NonEmptyString
    start: datetime
    end: datetime
    cadence_seconds: int = Field(ge=1)
    portfolio_snapshot_id: NonEmptyString
    market_dataset_snapshot_id: NonEmptyString
    market_dataset_revision: NonEmptyString
    fundamental_dataset_snapshot_id: str | None = None
    fundamental_dataset_revision: str | None = None
    crosswalk_snapshot_id: NonEmptyString
    crosswalk_dataset_revision: NonEmptyString
    event_snapshot_id: str | None = None
    event_dataset_revision: str | None = None
    policy_revision: NonEmptyString
    lookback_window_seconds: int = Field(ge=1)
    evaluation_horizon_seconds: int = Field(ge=1)
    minimum_labelled_outcomes: int = Field(default=30, ge=1)
    labelled_outcome_method: NonEmptyString
    point_in_time_rule: Literal["available_at_lte_step_as_of"] = "available_at_lte_step_as_of"
    evidence: tuple[MonitoringEvidence, ...] = Field(min_length=1)
    digest: Digest | None = Field(default=None, pattern=rf"^{SHA256_DIGEST_PATTERN}$")

    _start = field_validator("start")(normalize_utc)
    _end = field_validator("end")(normalize_utc)

    @model_validator(mode="after")
    def bounds_and_digest(self) -> "ReplaySpecification":
        if self.end < self.start:
            raise ValueError("replay end cannot precede replay start")
        if (self.fundamental_dataset_snapshot_id is None) != (
            self.fundamental_dataset_revision is None
        ):
            raise ValueError(
                "fundamental replay snapshot and revision must be supplied together"
            )
        if (self.event_snapshot_id is None) != (
            self.event_dataset_revision is None
        ):
            raise ValueError("event replay snapshot and revision must be supplied together")
        expected = sha256_digest(self)
        if self.digest is not None and self.digest != expected:
            raise ValueError("digest must equal the canonical replay specification digest")
        object.__setattr__(self, "digest", expected)
        return self

    def replay_times(self) -> tuple[datetime, ...]:
        values: list[datetime] = []
        current = self.start
        while current <= self.end:
            values.append(current)
            current += timedelta(seconds=self.cadence_seconds)
        return tuple(values)


class ReplayStep(ImmutableDomainModel):
    sequence: int = Field(ge=1)
    as_of: datetime
    data_context: PortfolioDataContext
    monitoring_run: ContextualMonitoringRun | None = None
    abstained: bool
    warnings: tuple[str, ...] = ()
    evidence: tuple[MonitoringEvidence, ...] = Field(min_length=1)
    digest: Digest | None = Field(default=None, pattern=rf"^{SHA256_DIGEST_PATTERN}$")

    _as_of = field_validator("as_of")(normalize_utc)

    @model_validator(mode="after")
    def point_in_time_step_is_consistent(self) -> "ReplayStep":
        if self.data_context.as_of != self.as_of:
            raise ValueError("every replay step must contain a context created at that step as_of")
        if self.monitoring_run is not None and (
            self.monitoring_run.context_digest != self.data_context.digest
            or self.monitoring_run.as_of != self.as_of
        ):
            raise ValueError("replay monitoring run must use the step's exact point-in-time context")
        if self.abstained != (self.monitoring_run is None or self.monitoring_run.status == "stopped"):
            raise ValueError("replay abstention must preserve an absent or stopped monitoring run")
        expected = sha256_digest(self)
        if self.digest is not None and self.digest != expected:
            raise ValueError("digest must equal the canonical replay-step digest")
        object.__setattr__(self, "digest", expected)
        return self


class ReplayRun(ImmutableDomainModel):
    run_id: NonEmptyString
    specification: ReplaySpecification
    steps: tuple[ReplayStep, ...]
    warnings: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()
    evidence: tuple[MonitoringEvidence, ...] = Field(min_length=1)
    effects: tuple[()] = ()
    human_review_required: Literal[True] = True
    digest: Digest | None = Field(default=None, pattern=rf"^{SHA256_DIGEST_PATTERN}$")

    @model_validator(mode="after")
    def deterministic_times_and_digest(self) -> "ReplayRun":
        if tuple(item.sequence for item in self.steps) != tuple(range(1, len(self.steps) + 1)):
            raise ValueError("replay steps must have contiguous deterministic sequence numbers")
        if tuple(item.as_of for item in self.steps) != self.specification.replay_times():
            raise ValueError("replay steps must exactly match deterministic specification times")
        if any(item.data_context.as_of != item.as_of for item in self.steps):
            raise ValueError("every replay step must create its own point-in-time data context")
        expected = sha256_digest(self)
        if self.digest is not None and self.digest != expected:
            raise ValueError("digest must equal the canonical replay-run digest")
        object.__setattr__(self, "digest", expected)
        return self


class AlertOutcomeMatch(ImmutableDomainModel):
    alert_id: NonEmptyString
    outcome_id: NonEmptyString
    instrument_id: NonEmptyString
    alert_time: datetime
    outcome_time: datetime
    lead_time_seconds: Decimal = Field(ge=Decimal("0"))
    detection_delay_seconds: Decimal = Field(ge=Decimal("0"))

    _alert_time = field_validator("alert_time")(normalize_utc)
    _outcome_time = field_validator("outcome_time")(normalize_utc)
    _lead = field_validator("lead_time_seconds")(decimal_value)
    _delay = field_validator("detection_delay_seconds")(decimal_value)


class EvaluationWarning(ImmutableDomainModel):
    code: NonEmptyString
    message: NonEmptyString


class MonitoringEvaluation(ImmutableDomainModel):
    evaluation_id: NonEmptyString
    replay_run_digest: Digest = Field(pattern=rf"^{SHA256_DIGEST_PATTERN}$")
    evaluated_at: datetime
    alert_count: int = Field(ge=0)
    labelled_outcome_count: int = Field(ge=0)
    evaluated_alert_count: int = Field(ge=0)
    true_positive: int = Field(ge=0)
    false_positive: int = Field(ge=0)
    false_negative: int = Field(ge=0)
    precision: Decimal | None = Field(default=None, ge=Decimal("0"), le=Decimal("1"))
    recall: Decimal | None = Field(default=None, ge=Decimal("0"), le=Decimal("1"))
    median_lead_time_seconds: Decimal | None = Field(default=None, ge=Decimal("0"))
    median_detection_delay_seconds: Decimal | None = Field(default=None, ge=Decimal("0"))
    coverage: Decimal | None = Field(default=None, ge=Decimal("0"), le=Decimal("1"))
    abstention_count: int = Field(ge=0)
    matches: tuple[AlertOutcomeMatch, ...] = ()
    methodology: NonEmptyString
    warnings: tuple[EvaluationWarning, ...] = ()
    limitations: tuple[str, ...] = ()
    evidence: tuple[MonitoringEvidence, ...] = Field(min_length=1)
    human_review_required: Literal[True] = True
    effects: tuple[()] = ()
    digest: Digest | None = Field(default=None, pattern=rf"^{SHA256_DIGEST_PATTERN}$")

    _evaluated_at = field_validator("evaluated_at")(normalize_utc)

    @model_validator(mode="after")
    def counts_metrics_and_digest_reconcile(self) -> "MonitoringEvaluation":
        if self.true_positive + self.false_positive != self.evaluated_alert_count:
            raise ValueError("evaluated_alert_count must equal true positives plus false positives")
        if self.true_positive != len(self.matches):
            raise ValueError("true_positive must equal the one-to-one match count")
        expected_precision = (
            Decimal(self.true_positive) / Decimal(self.true_positive + self.false_positive)
            if self.true_positive + self.false_positive
            else None
        )
        expected_recall = (
            Decimal(self.true_positive) / Decimal(self.true_positive + self.false_negative)
            if self.true_positive + self.false_negative
            else None
        )
        if self.precision != expected_precision or self.recall != expected_recall:
            raise ValueError("precision and recall must use their disclosed denominators")
        warning_codes = {item.code for item in self.warnings}
        if self.precision is None and "undefined_precision" not in warning_codes:
            raise ValueError("undefined precision requires an explicit warning")
        if self.recall is None and "undefined_recall" not in warning_codes:
            raise ValueError("undefined recall requires an explicit warning")
        expected = sha256_digest(self)
        if self.digest is not None and self.digest != expected:
            raise ValueError("digest must equal the canonical monitoring-evaluation digest")
        object.__setattr__(self, "digest", expected)
        return self


def evaluate_replay(
    *,
    evaluation_id: str,
    replay_run: ReplayRun,
    outcomes: tuple[OutcomeLabel, ...],
    evaluated_at: datetime,
) -> MonitoringEvaluation:
    """Apply deterministic closest-prior one-to-one alert/outcome matching."""

    evaluated_at = normalize_utc(evaluated_at)
    outcome_ids = [item.outcome_id for item in outcomes]
    if len(outcome_ids) != len(set(outcome_ids)):
        raise ValueError("outcome labels must be unique for one-to-one matching")
    alerts: list[
        tuple[str, tuple[str, ...], datetime, tuple[MonitoringEvidence, ...]]
    ] = []
    for step in replay_run.steps:
        run = step.monitoring_run
        if run is None or run.alert_draft.state != "draft":
            continue
        alerts.append(
            (
                run.alert_draft.alert_id or "",
                run.alert_draft.instrument_ids,
                run.alert_draft.created_at,
                run.alert_draft.evidence,
            )
        )
    alert_ids = [item[0] for item in alerts]
    if len(alert_ids) != len(set(alert_ids)):
        raise ValueError("replay alert identifiers must be unique")
    alerts.sort(key=lambda item: (item[2], item[0]))
    used_alerts: set[str] = set()
    matches: list[AlertOutcomeMatch] = []
    lookback = timedelta(seconds=replay_run.specification.lookback_window_seconds)
    for outcome in sorted(outcomes, key=lambda item: (item.outcome_time, item.outcome_id)):
        eligible = [
            alert
            for alert in alerts
            if alert[0] not in used_alerts
            and outcome.instrument_id in alert[1]
            and alert[2] <= outcome.outcome_time
            and alert[2] >= outcome.outcome_time - lookback
        ]
        if not eligible:
            continue
        alert = max(eligible, key=lambda item: (item[2], item[0]))
        delay = Decimal(str((alert[2] - outcome.trigger_available_at).total_seconds()))
        if delay < 0:
            raise ValueError("negative detection delay is invalid")
        lead = Decimal(str((outcome.outcome_time - alert[2]).total_seconds()))
        used_alerts.add(alert[0])
        matches.append(
            AlertOutcomeMatch(
                alert_id=alert[0],
                outcome_id=outcome.outcome_id,
                instrument_id=outcome.instrument_id,
                alert_time=alert[2],
                outcome_time=outcome.outcome_time,
                lead_time_seconds=lead,
                detection_delay_seconds=delay,
            )
        )
    horizon = timedelta(seconds=replay_run.specification.evaluation_horizon_seconds)
    false_positive_ids = {
        alert[0]
        for alert in alerts
        if alert[0] not in used_alerts and alert[2] + horizon <= evaluated_at
    }
    matched_outcomes = {item.outcome_id for item in matches}
    tp = len(matches)
    fp = len(false_positive_ids)
    fn = sum(item.outcome_id not in matched_outcomes for item in outcomes)
    warnings: list[EvaluationWarning] = []
    precision = Decimal(tp) / Decimal(tp + fp) if tp + fp else None
    recall = Decimal(tp) / Decimal(tp + fn) if tp + fn else None
    if precision is None:
        warnings.append(
            EvaluationWarning(
                code="undefined_precision",
                message="Precision is null because no alert reached an evaluated outcome.",
            )
        )
    if recall is None:
        warnings.append(
            EvaluationWarning(
                code="undefined_recall",
                message="Recall is null because there are no labelled positive outcomes.",
            )
        )
    if len(outcomes) < replay_run.specification.minimum_labelled_outcomes:
        warnings.append(
            EvaluationWarning(
                code="small_labelled_sample",
                message=(
                    f"The labelled outcome sample ({len(outcomes)}) is below the reviewed minimum "
                    f"({replay_run.specification.minimum_labelled_outcomes})."
                ),
            )
        )
    coverage = (
        Decimal(tp + fp) / Decimal(len(alerts))
        if alerts
        else None
    )
    if coverage is None:
        warnings.append(
            EvaluationWarning(
                code="undefined_coverage",
                message="Coverage is null because the replay produced no alerts.",
            )
        )
    lead_values = [item.lead_time_seconds for item in matches]
    delay_values = [item.detection_delay_seconds for item in matches]
    evidence_by_id = {item.evidence_id: item for item in replay_run.evidence}
    for outcome in outcomes:
        evidence_by_id.update({item.evidence_id: item for item in outcome.evidence})
    return MonitoringEvaluation(
        evaluation_id=evaluation_id,
        replay_run_digest=replay_run.digest or "",
        evaluated_at=evaluated_at,
        alert_count=len(alerts),
        labelled_outcome_count=len(outcomes),
        evaluated_alert_count=tp + fp,
        true_positive=tp,
        false_positive=fp,
        false_negative=fn,
        precision=precision,
        recall=recall,
        median_lead_time_seconds=Decimal(str(median(lead_values))) if lead_values else None,
        median_detection_delay_seconds=Decimal(str(median(delay_values))) if delay_values else None,
        coverage=coverage,
        abstention_count=sum(item.abstained for item in replay_run.steps),
        matches=tuple(matches),
        methodology=(
            "Deterministic one-to-one closest eligible unmatched prior alert matching; "
            f"labelled outcomes use {replay_run.specification.labelled_outcome_method}. "
            "This retrospective evaluation makes no predictive claim."
        ),
        warnings=tuple(sorted(warnings, key=lambda item: item.code)),
        limitations=(
            "Results describe only the disclosed local labelled sample.",
            "No predictive performance, investment advice, or live-trading fitness is claimed.",
        ),
        evidence=tuple(evidence_by_id[key] for key in sorted(evidence_by_id)),
    )
