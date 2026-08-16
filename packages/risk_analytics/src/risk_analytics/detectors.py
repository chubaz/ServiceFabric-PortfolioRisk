"""Deterministic, point-in-time anomaly detectors for historical case discovery.

The module produces statistical signals only.  It deliberately contains no
finding, alert, causal, materiality, or narrative construction.
"""

from __future__ import annotations

import json
import os
import tempfile
from collections.abc import Callable
from datetime import datetime
from decimal import Context, Decimal, ROUND_HALF_EVEN, localcontext
from enum import Enum
from pathlib import Path
from statistics import median
from types import MappingProxyType
from typing import Literal

from pydantic import Field, field_validator, model_validator

from risk_domain.common import ImmutableDomainModel, NonEmptyString, decimal_value, normalize_utc
from risk_domain.digests import sha256_digest
from risk_domain.models import SHA256_DIGEST_PATTERN

from .contracts import AnalysisEvidence, SamplePeriod


DETECTOR_CONTEXT = Context(prec=34, rounding=ROUND_HALF_EVEN)
MAD_NORMALIZATION = Decimal("1.4826")


class DetectorKind(str, Enum):
    ROBUST_RESIDUAL_Z_SCORE = "robust_residual_z_score"
    TWO_SIDED_CUSUM = "two_sided_cusum"


class SignalDirection(str, Enum):
    DOWNSIDE = "downside"
    UPSIDE = "upside"


class SignalScope(str, Enum):
    INSTRUMENT = "instrument"
    GROUP = "group"


class DetectorParameter(ImmutableDomainModel):
    name: str = Field(pattern=r"^[a-z][a-z0-9_]{0,63}$")
    value: Decimal | int | str | bool

    @field_validator("value")
    @classmethod
    def finite_decimal_parameter(cls, value: Decimal | int | str | bool):  # type: ignore[no-untyped-def]
        return decimal_value(value) if isinstance(value, Decimal) else value


class DetectorDefinition(ImmutableDomainModel):
    """One immutable statistical method and its complete configuration."""

    detector_id: str = Field(pattern=r"^[a-z][a-z0-9_.-]{0,127}$")
    version: str = Field(pattern=r"^[0-9]+\.[0-9]+\.[0-9]+$")
    kind: DetectorKind
    lookback: int = Field(ge=5, le=2_520)
    horizon_sessions: int = Field(default=1, ge=1, le=252)
    threshold: Decimal = Field(gt=Decimal("0"))
    normalization: Literal["rolling_median_mad"] = "rolling_median_mad"
    residualization: Literal["supplied_benchmark", "none"] = "supplied_benchmark"
    regime_id: NonEmptyString = "unconditioned"
    parameters: tuple[DetectorParameter, ...] = ()
    definition_digest: str | None = Field(default=None, pattern=rf"^{SHA256_DIGEST_PATTERN}$")

    _threshold = field_validator("threshold")(decimal_value)

    @field_validator("parameters")
    @classmethod
    def parameters_are_unique_and_ordered(
        cls, values: tuple[DetectorParameter, ...]
    ) -> tuple[DetectorParameter, ...]:
        names = [item.name for item in values]
        if len(names) != len(set(names)):
            raise ValueError("detector parameter names must be unique")
        return tuple(sorted(values, key=lambda item: item.name))

    @model_validator(mode="after")
    def definition_is_complete_and_content_addressed(self) -> "DetectorDefinition":
        parameters = {item.name: item.value for item in self.parameters}
        if self.kind is DetectorKind.TWO_SIDED_CUSUM:
            drift = parameters.get("drift")
            if not isinstance(drift, Decimal) or drift < 0:
                raise ValueError("two-sided CUSUM requires a non-negative Decimal drift parameter")
        expected = sha256_digest(self.model_dump(mode="python", exclude={"definition_digest"}))
        if self.definition_digest is not None and self.definition_digest != expected:
            raise ValueError("definition_digest must equal the canonical detector definition digest")
        object.__setattr__(self, "definition_digest", expected)
        return self

    def parameter(self, name: str, default: Decimal | int | str | bool | None = None):  # type: ignore[no-untyped-def]
        return next((item.value for item in self.parameters if item.name == name), default)


class DetectorObservation(ImmutableDomainModel):
    """One eligible value; benchmark_value is subtracted when configured."""

    series_id: NonEmptyString
    scope_type: SignalScope
    scope_id: NonEmptyString
    observed_at: datetime
    available_at: datetime
    value: Decimal
    benchmark_value: Decimal | None = None
    evidence_ids: tuple[NonEmptyString, ...] = Field(min_length=1)
    quality_flags: tuple[NonEmptyString, ...] = ()

    _observed_at = field_validator("observed_at")(normalize_utc)
    _available_at = field_validator("available_at")(normalize_utc)
    _value = field_validator("value")(decimal_value)

    @field_validator("benchmark_value")
    @classmethod
    def benchmark_is_finite(cls, value: Decimal | None) -> Decimal | None:
        return decimal_value(value) if value is not None else None

    @field_validator("evidence_ids", "quality_flags")
    @classmethod
    def string_values_are_unique_and_ordered(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        if len(values) != len(set(values)):
            raise ValueError("observation references and flags must be unique")
        return tuple(sorted(values))

    @model_validator(mode="after")
    def availability_does_not_precede_observation(self) -> "DetectorObservation":
        if self.available_at < self.observed_at:
            raise ValueError("available_at cannot precede observed_at")
        return self


class AnomalySignal(ImmutableDomainModel):
    """Sparse, versioned output from one detector threshold crossing."""

    signal_id: NonEmptyString
    series_id: NonEmptyString
    scope_type: SignalScope
    scope_id: NonEmptyString
    observation_time: datetime
    available_at: datetime
    detector_id: NonEmptyString
    detector_version: NonEmptyString
    detector_definition_digest: str = Field(pattern=rf"^{SHA256_DIGEST_PATTERN}$")
    lookback: int = Field(ge=5)
    forecast_horizon_sessions: int = Field(ge=1)
    direction: SignalDirection
    raw_score: Decimal
    standardised_score: Decimal
    threshold: Decimal = Field(gt=Decimal("0"))
    regime_id: NonEmptyString
    interval_start: datetime
    interval_end: datetime
    peak_time: datetime
    status: Literal["confirmed"] = "confirmed"
    quality_flags: tuple[NonEmptyString, ...] = ()
    evidence_ids: tuple[NonEmptyString, ...] = Field(min_length=1)

    _timestamps = field_validator(
        "observation_time", "available_at", "interval_start", "interval_end", "peak_time"
    )(normalize_utc)
    _raw_score = field_validator("raw_score")(decimal_value)
    _standardised_score = field_validator("standardised_score")(decimal_value)
    _signal_threshold = field_validator("threshold")(decimal_value)

    @field_validator("quality_flags", "evidence_ids")
    @classmethod
    def signal_values_are_unique_and_ordered(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        if len(values) != len(set(values)):
            raise ValueError("signal references and flags must be unique")
        return tuple(sorted(values))

    @model_validator(mode="after")
    def interval_and_direction_are_consistent(self) -> "AnomalySignal":
        if not self.interval_start <= self.peak_time <= self.interval_end:
            raise ValueError("signal peak must fall inside its interval")
        if self.available_at < self.observation_time:
            raise ValueError("signal availability cannot precede observation")
        expected_direction = (
            SignalDirection.UPSIDE if self.standardised_score > 0 else SignalDirection.DOWNSIDE
        )
        if self.standardised_score == 0 or self.direction is not expected_direction:
            raise ValueError("signal direction must match its signed standardized score")
        return self


class DetectorRun(ImmutableDomainModel):
    """Content-addressed execution result suitable for immutable caching."""

    run_id: NonEmptyString
    definition: DetectorDefinition
    as_of: datetime
    sample_period: SamplePeriod
    data_digest: str = Field(pattern=rf"^{SHA256_DIGEST_PATTERN}$")
    cache_key: str = Field(pattern=rf"^{SHA256_DIGEST_PATTERN}$")
    input_observation_count: int = Field(ge=0)
    eligible_observation_count: int = Field(ge=0)
    rejected_future_observation_count: int = Field(ge=0)
    evaluated_point_count: int = Field(ge=0)
    series_count: int = Field(ge=0)
    signals: tuple[AnomalySignal, ...] = ()
    quality_flags: tuple[NonEmptyString, ...] = ()
    evidence: tuple[AnalysisEvidence, ...] = Field(min_length=1)
    output_digest: str | None = Field(default=None, pattern=rf"^{SHA256_DIGEST_PATTERN}$")

    _as_of = field_validator("as_of")(normalize_utc)

    @field_validator("signals")
    @classmethod
    def signals_are_unique_and_ordered(
        cls, values: tuple[AnomalySignal, ...]
    ) -> tuple[AnomalySignal, ...]:
        ids = [item.signal_id for item in values]
        if len(ids) != len(set(ids)):
            raise ValueError("signal IDs must be unique")
        return tuple(sorted(values, key=lambda item: (item.observation_time, item.series_id, item.signal_id)))

    @field_validator("quality_flags")
    @classmethod
    def run_flags_are_unique_and_ordered(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        if len(values) != len(set(values)):
            raise ValueError("run quality flags must be unique")
        return tuple(sorted(values))

    @field_validator("evidence")
    @classmethod
    def evidence_is_unique_and_ordered(
        cls, values: tuple[AnalysisEvidence, ...]
    ) -> tuple[AnalysisEvidence, ...]:
        ids = [item.evidence_id for item in values]
        if len(ids) != len(set(ids)):
            raise ValueError("detector evidence IDs must be unique")
        return tuple(sorted(values, key=lambda item: item.evidence_id))

    @model_validator(mode="after")
    def run_counts_and_digests_are_consistent(self) -> "DetectorRun":
        if self.eligible_observation_count + self.rejected_future_observation_count != self.input_observation_count:
            raise ValueError("eligible and future observation counts must reconcile to input count")
        if any(item.available_at > self.as_of for item in self.signals):
            raise ValueError("detector signals cannot contain future information")
        expected_cache_key = sha256_digest(
            {
                "definition_digest": self.definition.definition_digest,
                "data_digest": self.data_digest,
                "as_of": self.as_of,
            }
        )
        if self.cache_key != expected_cache_key:
            raise ValueError("cache_key must identify the exact data, definition and as_of boundary")
        expected = sha256_digest(self.model_dump(mode="python", exclude={"output_digest"}))
        if self.output_digest is not None and self.output_digest != expected:
            raise ValueError("output_digest must equal the canonical detector run digest")
        object.__setattr__(self, "output_digest", expected)
        return self


def _residual(observation: DetectorObservation, definition: DetectorDefinition) -> Decimal | None:
    if definition.residualization == "none":
        return observation.value
    if observation.benchmark_value is None:
        return None
    with localcontext(DETECTOR_CONTEXT):
        return observation.value - observation.benchmark_value


def _robust_score(value: Decimal, history: list[Decimal]) -> Decimal | None:
    centre = Decimal(str(median(history)))
    deviations = [abs(item - centre) for item in history]
    scale = MAD_NORMALIZATION * Decimal(str(median(deviations)))
    if scale == 0:
        return None
    with localcontext(DETECTOR_CONTEXT):
        return (value - centre) / scale


def _signal(
    definition: DetectorDefinition,
    observation: DetectorObservation,
    *,
    raw_score: Decimal,
    standardised_score: Decimal,
    evidence_ids: tuple[str, ...],
    quality_flags: tuple[str, ...] = (),
) -> AnomalySignal:
    identity = sha256_digest(
        {
            "definition": definition.definition_digest,
            "series_id": observation.series_id,
            "observed_at": observation.observed_at,
            "available_at": observation.available_at,
            "score": standardised_score,
        }
    )
    return AnomalySignal(
        signal_id=f"signal-{identity[7:31]}",
        series_id=observation.series_id,
        scope_type=observation.scope_type,
        scope_id=observation.scope_id,
        observation_time=observation.observed_at,
        available_at=observation.available_at,
        detector_id=definition.detector_id,
        detector_version=definition.version,
        detector_definition_digest=definition.definition_digest,
        lookback=definition.lookback,
        forecast_horizon_sessions=definition.horizon_sessions,
        direction=SignalDirection.UPSIDE if standardised_score > 0 else SignalDirection.DOWNSIDE,
        raw_score=raw_score,
        standardised_score=standardised_score,
        threshold=definition.threshold,
        regime_id=definition.regime_id,
        interval_start=observation.observed_at,
        interval_end=observation.observed_at,
        peak_time=observation.observed_at,
        quality_flags=tuple(sorted(set((*observation.quality_flags, *quality_flags)))),
        evidence_ids=evidence_ids,
    )


def _robust_residual_signals(
    definition: DetectorDefinition, observations: tuple[DetectorObservation, ...]
) -> tuple[tuple[AnomalySignal, ...], int, tuple[str, ...]]:
    history: list[Decimal] = []
    signals: list[AnomalySignal] = []
    evaluated = 0
    flags: set[str] = set()
    for observation in observations:
        residual = _residual(observation, definition)
        if residual is None:
            flags.add("missing_benchmark")
            continue
        if len(history) >= definition.lookback:
            score = _robust_score(residual, history[-definition.lookback :])
            if score is None:
                flags.add("zero_mad_window")
            else:
                evaluated += 1
                if abs(score) >= definition.threshold:
                    signals.append(
                        _signal(
                            definition,
                            observation,
                            raw_score=residual,
                            standardised_score=score,
                            evidence_ids=observation.evidence_ids,
                        )
                    )
        history.append(residual)
    return tuple(signals), evaluated, tuple(sorted(flags))


def _cusum_signals(
    definition: DetectorDefinition, observations: tuple[DetectorObservation, ...]
) -> tuple[tuple[AnomalySignal, ...], int, tuple[str, ...]]:
    history: list[Decimal] = []
    positive = Decimal("0")
    negative = Decimal("0")
    signals: list[AnomalySignal] = []
    evaluated = 0
    flags: set[str] = set()
    drift = definition.parameter("drift")
    assert isinstance(drift, Decimal)
    for observation in observations:
        residual = _residual(observation, definition)
        if residual is None:
            flags.add("missing_benchmark")
            continue
        if len(history) >= definition.lookback:
            score = _robust_score(residual, history[-definition.lookback :])
            if score is None:
                flags.add("zero_mad_window")
            else:
                evaluated += 1
                with localcontext(DETECTOR_CONTEXT):
                    positive = max(Decimal("0"), positive + score - drift)
                    negative = min(Decimal("0"), negative + score + drift)
                crossing = positive if positive >= definition.threshold else negative if negative <= -definition.threshold else None
                if crossing is not None:
                    signals.append(
                        _signal(
                            definition,
                            observation,
                            raw_score=crossing,
                            standardised_score=crossing,
                            evidence_ids=observation.evidence_ids,
                            quality_flags=("sequential_accumulation",),
                        )
                    )
                    positive = Decimal("0")
                    negative = Decimal("0")
        history.append(residual)
    return tuple(signals), evaluated, tuple(sorted(flags))


DetectorHandler = Callable[
    [DetectorDefinition, tuple[DetectorObservation, ...]],
    tuple[tuple[AnomalySignal, ...], int, tuple[str, ...]],
]


class DetectorRegistry:
    """Explicit, finite detector dispatch; arbitrary methods cannot be invoked."""

    def __init__(self, handlers: dict[DetectorKind, DetectorHandler] | None = None) -> None:
        self._handlers = MappingProxyType(
            handlers
            or {
                DetectorKind.ROBUST_RESIDUAL_Z_SCORE: _robust_residual_signals,
                DetectorKind.TWO_SIDED_CUSUM: _cusum_signals,
            }
        )

    @property
    def kinds(self) -> tuple[DetectorKind, ...]:
        return tuple(sorted(self._handlers, key=lambda item: item.value))

    def run(
        self,
        definition: DetectorDefinition,
        observations: tuple[DetectorObservation, ...],
        *,
        as_of: datetime,
        evidence: tuple[AnalysisEvidence, ...],
    ) -> DetectorRun:
        as_of = normalize_utc(as_of)
        ordered = tuple(sorted(observations, key=lambda item: (item.series_id, item.observed_at)))
        if not ordered:
            raise ValueError("detector execution requires at least one observation")
        identities = [(item.series_id, item.observed_at) for item in ordered]
        if len(identities) != len(set(identities)):
            raise ValueError("detector observations must be unique by series and observed_at")
        eligible = tuple(item for item in ordered if item.available_at <= as_of)
        if not eligible:
            raise ValueError("no observation is eligible at the requested as_of boundary")
        data_digest = sha256_digest(ordered)
        cache_key = sha256_digest(
            {
                "definition_digest": definition.definition_digest,
                "data_digest": data_digest,
                "as_of": as_of,
            }
        )
        handler = self._handlers.get(definition.kind)
        if handler is None:
            raise ValueError(f"detector is not registered: {definition.kind.value}")
        by_series: dict[str, list[DetectorObservation]] = {}
        for item in eligible:
            by_series.setdefault(item.series_id, []).append(item)
        signals: list[AnomalySignal] = []
        flags: set[str] = set()
        evaluated = 0
        for series_id in sorted(by_series):
            series_signals, series_evaluated, series_flags = handler(
                definition, tuple(by_series[series_id])
            )
            signals.extend(series_signals)
            evaluated += series_evaluated
            flags.update(series_flags)
        if len(eligible) < len(ordered):
            flags.add("future_observations_excluded")
        period = SamplePeriod(
            start=min(item.observed_at for item in eligible),
            end=max(item.observed_at for item in eligible),
        )
        return DetectorRun(
            run_id=f"detector-run-{cache_key[7:31]}",
            definition=definition,
            as_of=as_of,
            sample_period=period,
            data_digest=data_digest,
            cache_key=cache_key,
            input_observation_count=len(ordered),
            eligible_observation_count=len(eligible),
            rejected_future_observation_count=len(ordered) - len(eligible),
            evaluated_point_count=evaluated,
            series_count=len(by_series),
            signals=tuple(signals),
            quality_flags=tuple(flags),
            evidence=evidence,
        )


class DetectorRunCache:
    """Path-safe immutable cache keyed by DetectorRun.cache_key."""

    def __init__(self, root: Path | str) -> None:
        self.root = Path(root).expanduser().absolute()

    def _path(self, cache_key: str) -> Path:
        if not cache_key.startswith("sha256:") or len(cache_key) != 71:
            raise ValueError("invalid detector cache key")
        return self.root / cache_key[7:9] / f"{cache_key[7:]}.json"

    def _ensure_root(self) -> None:
        current = Path(self.root.anchor)
        for part in self.root.parts[1:]:
            current /= part
            if os.path.lexists(current) and current.is_symlink():
                raise ValueError("detector cache path components may not be symbolic links")
        self.root.mkdir(mode=0o700, parents=True, exist_ok=True)

    def load(self, cache_key: str) -> DetectorRun | None:
        self._ensure_root()
        path = self._path(cache_key)
        if not path.exists():
            return None
        if path.is_symlink() or not path.resolve().is_relative_to(self.root.resolve()):
            raise ValueError("detector cache entry is unsafe")
        run = DetectorRun.model_validate_json(path.read_text(encoding="utf-8"))
        if run.cache_key != cache_key:
            raise ValueError("detector cache entry has a mismatched key")
        return run

    def store(self, run: DetectorRun) -> DetectorRun:
        self._ensure_root()
        path = self._path(run.cache_key)
        existing = self.load(run.cache_key)
        if existing is not None:
            if existing != run:
                raise ValueError("immutable detector cache key conflicts with existing output")
            return existing
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        if path.parent.is_symlink() or not path.parent.resolve().is_relative_to(self.root.resolve()):
            raise ValueError("detector cache directory is unsafe")
        descriptor, temporary = tempfile.mkstemp(prefix=".detector-", suffix=".tmp", dir=path.parent)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                descriptor = -1
                stream.write(json.dumps(run.model_dump(mode="json"), indent=2, sort_keys=True))
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
            os.chmod(temporary, 0o400)
            try:
                os.link(temporary, path, follow_symlinks=False)
            except FileExistsError:
                concurrent = self.load(run.cache_key)
                if concurrent != run:
                    raise ValueError("concurrent detector cache output conflicts with this run")
        finally:
            if descriptor >= 0:
                os.close(descriptor)
            if os.path.exists(temporary):
                os.unlink(temporary)
        return run


DEFAULT_DETECTOR_REGISTRY = DetectorRegistry()


def execute_detector(
    definition: DetectorDefinition,
    observations: tuple[DetectorObservation, ...],
    *,
    as_of: datetime,
    evidence: tuple[AnalysisEvidence, ...],
    cache: DetectorRunCache | None = None,
) -> DetectorRun:
    """Execute one registered detector and reuse an exact immutable result."""

    ordered = tuple(sorted(observations, key=lambda item: (item.series_id, item.observed_at)))
    data_digest = sha256_digest(ordered)
    cache_key = sha256_digest(
        {
            "definition_digest": definition.definition_digest,
            "data_digest": data_digest,
            "as_of": normalize_utc(as_of),
        }
    )
    if cache is not None:
        existing = cache.load(cache_key)
        if existing is not None:
            return existing
    result = DEFAULT_DETECTOR_REGISTRY.run(
        definition, ordered, as_of=as_of, evidence=evidence
    )
    return cache.store(result) if cache is not None else result
