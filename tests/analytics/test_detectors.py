from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from pydantic import ValidationError

from risk_analytics import (
    AnalysisEvidence,
    DetectorDefinition,
    DetectorKind,
    DetectorObservation,
    DetectorParameter,
    DetectorRunCache,
    SignalDirection,
    SignalScope,
    execute_detector,
)


START = datetime(2013, 1, 2, 21, tzinfo=UTC)
EVIDENCE = (
    AnalysisEvidence(
        evidence_id="reviewed-synthetic-detector-path",
        reference="fixture://synthetic/detector-path",
        digest="sha256:" + "b" * 64,
        description="Reviewed synthetic path with a known signed threshold crossing.",
    ),
)


def observation(
    day: int,
    value: str,
    *,
    series: str = "instrument-alpha",
    available_days_later: int = 0,
) -> DetectorObservation:
    observed_at = START + timedelta(days=day)
    return DetectorObservation(
        series_id=series,
        scope_type=SignalScope.INSTRUMENT,
        scope_id=series,
        observed_at=observed_at,
        available_at=observed_at + timedelta(days=available_days_later),
        value=Decimal(value),
        benchmark_value=Decimal("0"),
        evidence_ids=(f"price:{series}:{day}",),
        quality_flags=("reviewed_synthetic",),
    )


def robust_definition() -> DetectorDefinition:
    return DetectorDefinition(
        detector_id="robust-residual-z",
        version="1.0.0",
        kind=DetectorKind.ROBUST_RESIDUAL_Z_SCORE,
        lookback=5,
        threshold=Decimal("3"),
    )


def cusum_definition() -> DetectorDefinition:
    return DetectorDefinition(
        detector_id="two-sided-cusum",
        version="1.0.0",
        kind=DetectorKind.TWO_SIDED_CUSUM,
        lookback=5,
        threshold=Decimal("1.5"),
        parameters=(DetectorParameter(name="drift", value=Decimal("0.25")),),
    )


def test_robust_detector_produces_signed_sparse_signals_without_narrative() -> None:
    baseline = ("-0.01", "0", "0.01", "-0.02", "0.02")
    observations = tuple(observation(index, value) for index, value in enumerate(baseline)) + (
        observation(5, "-0.10"),
        observation(6, "0.12"),
    )
    run = execute_detector(
        robust_definition(), observations, as_of=START + timedelta(days=6), evidence=EVIDENCE
    )

    assert [item.direction for item in run.signals] == [
        SignalDirection.DOWNSIDE,
        SignalDirection.UPSIDE,
    ]
    assert run.evaluated_point_count == 2
    assert all(abs(item.standardised_score) >= item.threshold for item in run.signals)
    assert run.output_digest and run.definition.definition_digest
    assert "summary" not in run.model_dump()
    assert "cause" not in run.model_dump()


def test_cusum_is_two_sided_resets_after_crossing_and_is_reproducible() -> None:
    values = ("-0.01", "0", "0.01", "-0.02", "0.02", "-0.04", "0.10")
    observations = tuple(observation(index, value) for index, value in enumerate(values))
    first = execute_detector(
        cusum_definition(), observations, as_of=START + timedelta(days=6), evidence=EVIDENCE
    )
    second = execute_detector(
        cusum_definition(), tuple(reversed(observations)), as_of=START + timedelta(days=6), evidence=EVIDENCE
    )

    assert {item.direction for item in first.signals} == {
        SignalDirection.DOWNSIDE,
        SignalDirection.UPSIDE,
    }
    assert first == second
    assert first.output_digest == second.output_digest
    assert all("sequential_accumulation" in item.quality_flags for item in first.signals)


def test_future_observations_are_rejected_from_the_result_not_silently_used() -> None:
    observations = tuple(
        observation(index, value)
        for index, value in enumerate(("-0.01", "0", "0.01", "-0.02", "0.02", "-0.10"))
    ) + (observation(6, "0.90", available_days_later=3),)
    run = execute_detector(
        robust_definition(), observations, as_of=START + timedelta(days=6), evidence=EVIDENCE
    )

    assert run.input_observation_count == 7
    assert run.eligible_observation_count == 6
    assert run.rejected_future_observation_count == 1
    assert "future_observations_excluded" in run.quality_flags
    assert all(item.available_at <= run.as_of for item in run.signals)


def test_zero_mad_and_missing_benchmark_are_quality_states_not_zero_scores() -> None:
    flat = tuple(observation(index, "0") for index in range(6))
    missing = observation(6, "-0.1").model_copy(update={"benchmark_value": None})
    run = execute_detector(
        robust_definition(), (*flat, missing), as_of=START + timedelta(days=6), evidence=EVIDENCE
    )

    assert run.signals == ()
    assert set(run.quality_flags) == {"missing_benchmark", "zero_mad_window"}


def test_detector_cache_reuses_exact_immutable_bytes_and_rejects_tampering(tmp_path) -> None:
    observations = tuple(
        observation(index, value)
        for index, value in enumerate(("-0.01", "0", "0.01", "-0.02", "0.02", "-0.10"))
    )
    cache = DetectorRunCache(tmp_path / "detectors")
    first = execute_detector(
        robust_definition(), observations, as_of=START + timedelta(days=5), evidence=EVIDENCE, cache=cache
    )
    second = execute_detector(
        robust_definition(), observations, as_of=START + timedelta(days=5), evidence=EVIDENCE, cache=cache
    )
    entries = list((tmp_path / "detectors").rglob("*.json"))

    assert first == second
    assert len(entries) == 1
    assert entries[0].stat().st_mode & 0o222 == 0
    tampered = entries[0].read_text(encoding="utf-8").replace("robust-residual-z", "tampered-detector")
    entries[0].chmod(0o600)
    entries[0].write_text(tampered, encoding="utf-8")
    with pytest.raises((ValidationError, ValueError)):
        cache.load(first.cache_key)


def test_detector_contract_rejects_naive_time_and_incomplete_cusum() -> None:
    invalid = observation(0, "0").model_dump(mode="python")
    invalid["observed_at"] = datetime(2013, 1, 2)
    with pytest.raises(ValidationError, match="timezone-aware"):
        DetectorObservation.model_validate(invalid)
    with pytest.raises(ValidationError, match="drift"):
        DetectorDefinition(
            detector_id="invalid-cusum",
            version="1.0.0",
            kind=DetectorKind.TWO_SIDED_CUSUM,
            lookback=5,
            threshold=Decimal("3"),
        )
