"""Deterministic retrospective study aids for selective signal labelling.

These calculations propose paths, intervals, severity observations and
associations.  They are not labels, findings, causal claims or Gold cases.
Nothing in this module can approve or mutate a human annotation.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Context, Decimal, ROUND_HALF_EVEN, localcontext
from enum import Enum
from math import sqrt
from statistics import mean
from typing import Literal

from pydantic import Field, field_validator, model_validator

from risk_domain.common import ImmutableDomainModel, decimal_value, normalize_utc
from risk_domain.digests import sha256_digest
from risk_domain.models import SHA256_DIGEST_PATTERN


STUDY_CONTEXT = Context(prec=34, rounding=ROUND_HALF_EVEN)


class StudyDirection(str, Enum):
    DOWNSIDE = "downside"
    UPSIDE = "upside"


class PathObservation(ImmutableDomainModel):
    scope_id: str = Field(min_length=1, max_length=200)
    observed_at: datetime
    available_at: datetime
    total_return: Decimal
    valuation_price: Decimal | None = Field(default=None, gt=0)
    evidence_id: str = Field(min_length=1, max_length=240)
    quality_flags: tuple[str, ...] = ()

    _times = field_validator("observed_at", "available_at")(normalize_utc)
    _return = field_validator("total_return")(decimal_value)

    @field_validator("valuation_price")
    @classmethod
    def price_is_finite(cls, value: Decimal | None) -> Decimal | None:
        return None if value is None else decimal_value(value)


class PathPoint(ImmutableDomainModel):
    observed_at: datetime
    indexed_value: Decimal = Field(gt=0)
    total_return: Decimal
    is_signal_date: bool = False

    _time = field_validator("observed_at")(normalize_utc)
    _values = field_validator("indexed_value", "total_return")(decimal_value)


class ChangePointProposal(ImmutableDomainModel):
    method: Literal["mean_variance_split"] = "mean_variance_split"
    observed_at: datetime
    score: Decimal = Field(ge=0)
    pre_mean_return: Decimal
    post_mean_return: Decimal
    supported: bool
    method_version: Literal["1.0.0"] = "1.0.0"

    _time = field_validator("observed_at")(normalize_utc)
    _values = field_validator("score", "pre_mean_return", "post_mean_return")(decimal_value)


class IntervalKind(str, Enum):
    PUNCTUAL = "punctual"
    DRAWDOWN = "drawdown"
    SLOW_DETERIORATION = "slow_deterioration"
    REGIME_TRANSITION = "regime_transition"


class IntervalProposal(ImmutableDomainModel):
    proposal_id: str = Field(pattern=r"^[a-z][a-z0-9_.-]{2,127}$")
    kind: IntervalKind
    onset: datetime
    peak: datetime
    resolution: datetime | None = None
    censored: bool
    confidence: Decimal = Field(ge=0, le=1)
    rationale_code: str = Field(pattern=r"^[a-z][a-z0-9_]{2,80}$")
    proposal_digest: str | None = Field(default=None, pattern=rf"^{SHA256_DIGEST_PATTERN}$")

    _times = field_validator("onset", "peak")(normalize_utc)

    @field_validator("resolution")
    @classmethod
    def resolution_is_utc(cls, value: datetime | None) -> datetime | None:
        return None if value is None else normalize_utc(value)

    _confidence = field_validator("confidence")(decimal_value)

    @model_validator(mode="after")
    def ordered_and_addressed(self) -> "IntervalProposal":
        if self.peak < self.onset or (self.resolution is not None and self.resolution < self.peak):
            raise ValueError("interval proposal dates must be ordered")
        if self.censored != (self.resolution is None):
            raise ValueError("censored proposals have no resolution; resolved proposals require one")
        expected = sha256_digest(self.model_dump(mode="python", exclude={"proposal_digest"}))
        if self.proposal_digest is not None and self.proposal_digest != expected:
            raise ValueError("interval proposal digest does not match its content")
        object.__setattr__(self, "proposal_digest", expected)
        return self


class SeverityObservation(ImmutableDomainModel):
    horizon_sessions: int = Field(ge=1, le=252)
    observed_sessions: int = Field(ge=0)
    directional_impact_basis_points: Decimal = Field(ge=0)
    signed_return: Decimal
    complete_horizon: bool

    _values = field_validator("directional_impact_basis_points", "signed_return")(decimal_value)


class GroupContext(ImmutableDomainModel):
    member_count: int = Field(ge=1)
    observed_member_count: int = Field(ge=0)
    adverse_breadth: Decimal | None = Field(default=None, ge=0, le=1)
    pre_average_correlation: Decimal | None = Field(default=None, ge=-1, le=1)
    post_average_correlation: Decimal | None = Field(default=None, ge=-1, le=1)
    correlation_change: Decimal | None = Field(default=None, ge=-2, le=2)
    quality_flags: tuple[str, ...] = ()

    @field_validator("adverse_breadth", "pre_average_correlation", "post_average_correlation", "correlation_change")
    @classmethod
    def finite_optional(cls, value: Decimal | None) -> Decimal | None:
        return None if value is None else decimal_value(value)


class AssociationEdge(ImmutableDomainModel):
    related_unit_id: str = Field(min_length=3, max_length=160)
    edge_type: Literal["same_scope_nearby", "synchronised_group_move"]
    distance_sessions: int = Field(ge=0, le=20)
    direction_agrees: bool
    association_score: Decimal = Field(ge=0, le=1)
    causal_claim: Literal[False] = False

    _score = field_validator("association_score")(decimal_value)


class LabelStudyProposal(ImmutableDomainModel):
    study_id: str = Field(pattern=r"^[a-z][a-z0-9_.-]{2,127}$")
    unit_id: str = Field(min_length=3, max_length=160)
    dataset_snapshot_id: str = Field(min_length=1, max_length=256)
    retrospective_cutoff: datetime
    information_plane: Literal["retrospective_reference"] = "retrospective_reference"
    path: tuple[PathPoint, ...] = Field(min_length=1)
    change_point: ChangePointProposal | None = None
    interval_proposals: tuple[IntervalProposal, ...] = Field(min_length=1)
    severity_observations: tuple[SeverityObservation, ...] = Field(min_length=1)
    maximum_adverse_excursion_basis_points: Decimal = Field(ge=0)
    group_context: GroupContext
    association_edges: tuple[AssociationEdge, ...] = ()
    evidence_ids: tuple[str, ...] = Field(min_length=1)
    quality_flags: tuple[str, ...] = ()
    annotation_status: Literal["proposal_only"] = "proposal_only"
    gold_case_created: Literal[False] = False
    study_digest: str | None = Field(default=None, pattern=rf"^{SHA256_DIGEST_PATTERN}$")

    _cutoff = field_validator("retrospective_cutoff")(normalize_utc)
    _excursion = field_validator("maximum_adverse_excursion_basis_points")(decimal_value)

    @model_validator(mode="after")
    def reproducible_and_firewalled(self) -> "LabelStudyProposal":
        if tuple(self.path) != tuple(sorted(self.path, key=lambda item: item.observed_at)):
            raise ValueError("study path must be chronological")
        if any(item.observed_at > self.retrospective_cutoff for item in self.path):
            raise ValueError("study path exceeds its retrospective cutoff")
        if tuple(item.horizon_sessions for item in self.severity_observations) != tuple(
            sorted(set(item.horizon_sessions for item in self.severity_observations))
        ):
            raise ValueError("severity horizons must be unique and ordered")
        expected = sha256_digest(self.model_dump(mode="python", exclude={"study_digest"}))
        if self.study_digest is not None and self.study_digest != expected:
            raise ValueError("study digest does not match its content")
        object.__setattr__(self, "study_digest", expected)
        return self


def _decimal(value: float | Decimal) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.00000001"))


def _path_points(observations: tuple[PathObservation, ...], signal_time: datetime) -> tuple[PathPoint, ...]:
    ordered = tuple(sorted(observations, key=lambda item: item.observed_at))
    base_price = next((item.valuation_price for item in ordered if item.valuation_price), None)
    cumulative = Decimal("100")
    points: list[PathPoint] = []
    for item in ordered:
        if base_price and item.valuation_price:
            indexed = item.valuation_price / base_price * Decimal("100")
        else:
            cumulative *= Decimal("1") + item.total_return
            indexed = cumulative
        points.append(
            PathPoint(
                observed_at=item.observed_at,
                indexed_value=indexed,
                total_return=item.total_return,
                is_signal_date=item.observed_at.date() == signal_time.date(),
            )
        )
    return tuple(points)


def _change_point(points: tuple[PathPoint, ...], signal_index: int) -> ChangePointProposal | None:
    if len(points) < 12:
        return None
    start = max(5, signal_index - 10)
    end = min(len(points) - 5, signal_index + 6)
    best: tuple[float, int, float, float] | None = None
    returns = [float(item.total_return) for item in points]
    for split in range(start, end + 1):
        pre = returns[max(0, split - 10):split]
        post = returns[split:min(len(returns), split + 10)]
        if len(pre) < 5 or len(post) < 5:
            continue
        pre_mean, post_mean = mean(pre), mean(post)
        pooled = sqrt((sum((x - pre_mean) ** 2 for x in pre) + sum((x - post_mean) ** 2 for x in post)) / max(1, len(pre) + len(post) - 2))
        score = abs(post_mean - pre_mean) / max(pooled, 1e-9)
        candidate = (score, split, pre_mean, post_mean)
        if best is None or candidate[0] > best[0]:
            best = candidate
    if best is None:
        return None
    score, split, pre_mean, post_mean = best
    return ChangePointProposal(
        observed_at=points[split].observed_at,
        score=_decimal(score),
        pre_mean_return=_decimal(pre_mean),
        post_mean_return=_decimal(post_mean),
        supported=score >= 0.75,
    )


def _resolution(points: tuple[PathPoint, ...], peak_index: int, target: Decimal) -> datetime | None:
    consecutive = 0
    for item in points[peak_index + 1:]:
        consecutive = consecutive + 1 if item.indexed_value >= target else 0
        if consecutive >= 3:
            return item.observed_at
    return None


def _intervals(points: tuple[PathPoint, ...], signal_index: int, direction: StudyDirection, change: ChangePointProposal | None) -> tuple[IntervalProposal, ...]:
    signal = points[signal_index]
    before = points[max(0, signal_index - 20):signal_index + 1]
    after = points[signal_index:min(len(points), signal_index + 21)]
    if direction is StudyDirection.DOWNSIDE:
        onset_point = max(before, key=lambda item: item.indexed_value)
        peak_point = min(after, key=lambda item: item.indexed_value)
        recovery_target = onset_point.indexed_value
    else:
        onset_point = min(before, key=lambda item: item.indexed_value)
        peak_point = max(after, key=lambda item: item.indexed_value)
        recovery_target = onset_point.indexed_value
    peak_index = points.index(peak_point)
    resolved = _resolution(points, peak_index, recovery_target) if direction is StudyDirection.DOWNSIDE else next(
        (item.observed_at for item in points[peak_index + 1:] if item.indexed_value <= recovery_target), None
    )
    values: list[tuple[IntervalKind, datetime, datetime, datetime | None, Decimal, str]] = [
        (IntervalKind.PUNCTUAL, signal.observed_at, signal.observed_at, signal.observed_at, Decimal("0.70"), "threshold_crossing_date"),
        (IntervalKind.DRAWDOWN, onset_point.observed_at, peak_point.observed_at, resolved, Decimal("0.78"), "high_water_to_extreme_then_recovery"),
    ]
    if change and change.supported:
        slow_onset = change.observed_at
        if slow_onset <= peak_point.observed_at:
            halfway = (onset_point.indexed_value + peak_point.indexed_value) / Decimal("2")
            slow_resolution = _resolution(points, peak_index, halfway) if direction is StudyDirection.DOWNSIDE else next(
                (item.observed_at for item in points[peak_index + 1:] if item.indexed_value <= halfway), None
            )
            values.append((IntervalKind.SLOW_DETERIORATION, slow_onset, peak_point.observed_at, slow_resolution, Decimal("0.62"), "change_point_with_hysteresis"))
            values.append((IntervalKind.REGIME_TRANSITION, slow_onset, peak_point.observed_at, None, Decimal("0.52"), "return_distribution_change"))
    proposals = []
    for kind, onset, peak, resolution, confidence, rationale in values:
        identity = sha256_digest({"kind": kind.value, "onset": onset, "peak": peak, "resolution": resolution})
        proposals.append(IntervalProposal(
            proposal_id=f"interval-{identity[7:31]}", kind=kind, onset=onset, peak=peak,
            resolution=resolution, censored=resolution is None, confidence=confidence, rationale_code=rationale,
        ))
    return tuple(proposals)


def _severity(points: tuple[PathPoint, ...], signal_index: int, direction: StudyDirection) -> tuple[tuple[SeverityObservation, ...], Decimal]:
    values: list[SeverityObservation] = []
    start = points[signal_index].indexed_value
    available = points[signal_index + 1:]
    adverse_values: list[Decimal] = []
    for item in available:
        signed = item.indexed_value / start - Decimal("1")
        adverse_values.append(max(Decimal("0"), -signed if direction is StudyDirection.DOWNSIDE else signed))
    for horizon in (1, 5, 20):
        observed = min(horizon, len(available))
        signed = Decimal("0") if observed == 0 else available[observed - 1].indexed_value / start - Decimal("1")
        horizon_path = available[:observed]
        directional = max(
            (
                max(Decimal("0"), -(item.indexed_value / start - Decimal("1")))
                if direction is StudyDirection.DOWNSIDE
                else max(Decimal("0"), item.indexed_value / start - Decimal("1"))
                for item in horizon_path
            ),
            default=Decimal("0"),
        )
        values.append(SeverityObservation(
            horizon_sessions=horizon,
            observed_sessions=observed,
            directional_impact_basis_points=directional * Decimal("10000"),
            signed_return=signed,
            complete_horizon=observed == horizon,
        ))
    maximum = max(adverse_values, default=Decimal("0")) * Decimal("10000")
    return tuple(values), maximum


def _correlation(left: list[float], right: list[float]) -> float | None:
    if len(left) < 5 or len(left) != len(right):
        return None
    lm, rm = mean(left), mean(right)
    numerator = sum((a - lm) * (b - rm) for a, b in zip(left, right, strict=True))
    denominator = sqrt(sum((a - lm) ** 2 for a in left) * sum((b - rm) ** 2 for b in right))
    return None if denominator <= 1e-14 else numerator / denominator


def _average_pairwise_correlation(series: list[list[float]]) -> Decimal | None:
    values = [value for i, left in enumerate(series) for right in series[i + 1:] if (value := _correlation(left, right)) is not None]
    return None if not values else _decimal(mean(values))


def _group_context(peer_observations: tuple[PathObservation, ...], signal_time: datetime, direction: StudyDirection) -> GroupContext:
    by_scope: dict[str, dict[datetime, PathObservation]] = {}
    for item in peer_observations:
        by_scope.setdefault(item.scope_id, {})[item.observed_at] = item
    signal_date_rows = [rows.get(next((time for time in rows if time.date() == signal_time.date()), signal_time)) for rows in by_scope.values()]
    observed = [item for item in signal_date_rows if item is not None]
    adverse = [item for item in observed if (item.total_return < 0 if direction is StudyDirection.DOWNSIDE else item.total_return > 0)]
    times = sorted({item.observed_at for item in peer_observations})
    signal_position = next((i for i, value in enumerate(times) if value.date() >= signal_time.date()), len(times) - 1)

    def aligned(window: list[datetime]) -> list[list[float]]:
        return [[float(rows[t].total_return) for t in window if t in rows] for rows in by_scope.values()]

    pre_times = times[max(0, signal_position - 20):signal_position]
    post_times = times[signal_position + 1:signal_position + 21]
    pre = _average_pairwise_correlation([row for row in aligned(pre_times) if len(row) == len(pre_times)])
    post = _average_pairwise_correlation([row for row in aligned(post_times) if len(row) == len(post_times)])
    flags = []
    if len(observed) < len(by_scope): flags.append("incomplete_cross_section")
    if pre is None or post is None: flags.append("insufficient_correlation_history")
    return GroupContext(
        member_count=len(by_scope), observed_member_count=len(observed),
        adverse_breadth=None if not observed else Decimal(len(adverse)) / Decimal(len(observed)),
        pre_average_correlation=pre, post_average_correlation=post,
        correlation_change=None if pre is None or post is None else post - pre,
        quality_flags=tuple(sorted(flags)),
    )


def build_label_study(
    *,
    unit_id: str,
    scope_id: str,
    signal_time: datetime,
    direction: StudyDirection,
    dataset_snapshot_id: str,
    retrospective_cutoff: datetime,
    observations: tuple[PathObservation, ...],
    peer_observations: tuple[PathObservation, ...],
    association_edges: tuple[AssociationEdge, ...] = (),
) -> LabelStudyProposal:
    signal_time = normalize_utc(signal_time)
    cutoff = normalize_utc(retrospective_cutoff)
    scoped = tuple(item for item in observations if item.scope_id == scope_id and item.observed_at <= cutoff)
    if not scoped:
        raise ValueError("no retrospective path is available for the selected review item")
    points = _path_points(scoped, signal_time)
    signal_index = min(range(len(points)), key=lambda index: abs((points[index].observed_at - signal_time).total_seconds()))
    change = _change_point(points, signal_index)
    intervals = _intervals(points, signal_index, direction, change)
    severity, maximum = _severity(points, signal_index, direction)
    group_context = _group_context(peer_observations, signal_time, direction)
    identity = sha256_digest({
        "unit": unit_id, "dataset": dataset_snapshot_id, "cutoff": cutoff,
        "path": [item.model_dump(mode="python") for item in points],
        "change_point": None if change is None else change.model_dump(mode="python"),
        "intervals": [item.model_dump(mode="python") for item in intervals],
        "severity": [item.model_dump(mode="python") for item in severity],
        "maximum_adverse_excursion_basis_points": maximum,
        "group_context": group_context.model_dump(mode="python"),
        "associations": [item.model_dump(mode="python") for item in association_edges],
    })
    return LabelStudyProposal(
        study_id=f"label-study-{identity[7:31]}", unit_id=unit_id,
        dataset_snapshot_id=dataset_snapshot_id, retrospective_cutoff=cutoff,
        path=points, change_point=change, interval_proposals=intervals,
        severity_observations=severity, maximum_adverse_excursion_basis_points=maximum,
        group_context=group_context,
        association_edges=association_edges,
        evidence_ids=tuple(sorted({item.evidence_id for item in scoped})),
        quality_flags=tuple(sorted({flag for item in scoped for flag in item.quality_flags})),
    )
