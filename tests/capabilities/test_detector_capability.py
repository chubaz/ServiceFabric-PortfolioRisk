from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from risk_analytics import (
    AnalysisEvidence,
    DetectorDefinition,
    DetectorKind,
    DetectorObservation,
    SignalScope,
)
from risk_capabilities import CapabilityRegistry, DetectorExecutionRequest


START = datetime(2014, 2, 3, 21, tzinfo=UTC)
EVIDENCE = (
    AnalysisEvidence(
        evidence_id="licensed-market-revision",
        reference="dataset://licensed/crsp/revision-a",
        digest="sha256:" + "c" * 64,
        description="Opaque reference to a licensed read-only market revision.",
    ),
)


def request(tmp_path) -> DetectorExecutionRequest:  # type: ignore[no-untyped-def]
    values = ("-0.01", "0", "0.01", "-0.02", "0.02", "-0.10")
    return DetectorExecutionRequest(
        definition=DetectorDefinition(
            detector_id="robust-residual-z",
            version="1.0.0",
            kind=DetectorKind.ROBUST_RESIDUAL_Z_SCORE,
            lookback=5,
            threshold=Decimal("3"),
        ),
        observations=tuple(
            DetectorObservation(
                series_id="instrument-alpha",
                scope_type=SignalScope.INSTRUMENT,
                scope_id="instrument-alpha",
                observed_at=START + timedelta(days=index),
                available_at=START + timedelta(days=index),
                value=Decimal(value),
                benchmark_value=Decimal("0"),
                evidence_ids=(f"crsp-row:{index}",),
            )
            for index, value in enumerate(values)
        ),
        as_of=START + timedelta(days=5),
        evidence=EVIDENCE,
        cache_root=(tmp_path / "detector-cache").absolute(),
    )


def test_detector_capability_is_bounded_traceable_and_cache_stable(tmp_path) -> None:  # type: ignore[no-untyped-def]
    registry = CapabilityRegistry()
    first = registry.invoke("market.anomaly.scan", request(tmp_path))
    second = registry.invoke("market.anomaly.scan", request(tmp_path))

    assert first.status == second.status == "succeeded"
    assert first.data == second.data
    assert first.output_digest == second.output_digest == first.data.output_digest
    assert first.effects == second.effects == ()
    assert first.findings == second.findings == ()
    assert "not a risk episode" in first.limitations[0]
    assert len(registry.invocation_history) == 2
    assert registry.invocation_history[0].request_digest == registry.invocation_history[1].request_digest
    assert registry.invocation_history[0].output_digest == registry.invocation_history[1].output_digest
    assert registry.invocation_history[0].cache_key == first.data.cache_key


def test_detector_capability_failure_is_a_receipted_failure_not_empty_success(tmp_path) -> None:  # type: ignore[no-untyped-def]
    registry = CapabilityRegistry()
    invalid = request(tmp_path).model_copy(
        update={"as_of": START - timedelta(days=1)}
    )
    result = registry.invoke("market.anomaly.scan", invalid)

    assert result.status == "failed"
    assert result.data is None
    assert result.warnings == ("no observation is eligible at the requested as_of boundary",)
    assert registry.invocation_history[-1].status == "failed"
