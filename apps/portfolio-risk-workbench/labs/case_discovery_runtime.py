"""Compact real-data projection for the Experiment page's Find cases step."""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

import duckdb

from artifact_repository import artifact_root
from historical_replay_runtime import (
    COMMON_END,
    COMMON_START,
    HistoricalReplayError,
    _current_security_context,
    _database,
    _positions,
)
from risk_analytics import (
    AnalysisEvidence,
    DetectorDefinition,
    DetectorKind,
    DetectorObservation,
    DetectorParameter,
    SignalScope,
)
from risk_capabilities import CapabilityRegistry, DetectorExecutionRequest
from risk_data import query_crsp_detector_market
from risk_domain.digests import sha256_digest


CRSP_SNAPSHOT_ID = "crsp_compustat_01322048b75d7ac69e858b1e"
CRSP_CATALOGUE_DIGEST = "sha256:8c43f179b7cb16ab8f5e719a025419d33ada314cc2fe8b110e2fc7cc979708da"
LOOKBACK_SESSIONS = 63
QUERY_LOOKBACK_DAYS = 140
MAX_PREVIEW_DAYS = 366
MAX_VISIBLE_SIGNALS = 40


@dataclass(frozen=True)
class DetectorScanResult:
    runs: tuple[Any, ...]
    observations: tuple[DetectorObservation, ...]
    as_of: datetime
    security_context: dict[str, dict[str, str]]
    instrument_count: int
    missing_returns: int


def _definitions() -> tuple[DetectorDefinition, ...]:
    return (
        DetectorDefinition(
            detector_id="robust-residual-z",
            version="1.0.0",
            kind=DetectorKind.ROBUST_RESIDUAL_Z_SCORE,
            lookback=LOOKBACK_SESSIONS,
            threshold=Decimal("4.5"),
            residualization="supplied_benchmark",
            regime_id="unconditioned",
        ),
        DetectorDefinition(
            detector_id="two-sided-cusum",
            version="1.0.0",
            kind=DetectorKind.TWO_SIDED_CUSUM,
            lookback=LOOKBACK_SESSIONS,
            threshold=Decimal("8"),
            residualization="supplied_benchmark",
            regime_id="unconditioned",
            parameters=(DetectorParameter(name="drift", value=Decimal("0.5")),),
        ),
    )


def _cache_root() -> Path:
    configured = os.environ.get("PORTFOLIO_RISK_DETECTOR_CACHE_ROOT")
    if configured:
        return Path(configured).expanduser().absolute()
    return (artifact_root().parent / "detector-cache-v1").absolute()


def _write_receipt(cache_root: Path, value: dict[str, Any]) -> None:
    """Persist a machine-only receipt; the research UI never renders it."""

    receipt_digest = sha256_digest(value)
    directory = cache_root / "receipts" / receipt_digest[7:9]
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    path = directory / f"{receipt_digest[7:]}.json"
    if path.exists():
        return
    descriptor, temporary = tempfile.mkstemp(prefix=".receipt-", suffix=".tmp", dir=directory)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            descriptor = -1
            json.dump(value, stream, indent=2, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, 0o400)
        try:
            os.link(temporary, path, follow_symlinks=False)
        except FileExistsError:
            existing = json.loads(path.read_text(encoding="utf-8"))
            if existing != value:
                raise ValueError("detector receipt digest conflicts with existing content")
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        if os.path.exists(temporary):
            os.unlink(temporary)


def _query_market(
    private_root: Path,
    *,
    portfolio_id: str,
    start_date: date,
    end_date: date,
) -> tuple[
    tuple[DetectorObservation, ...],
    datetime,
    dict[int, dict[str, str]],
    int,
    int,
]:
    positions, _cash, _config = _positions(private_root, portfolio_id)
    permnos = sorted({item.permno for item in positions})
    alias_by_permno = {item.permno: item.alias for item in positions}
    database = _database(private_root)
    if not database.is_file():
        raise HistoricalReplayError("licensed CRSP database is unavailable")
    query_start = start_date - timedelta(days=QUERY_LOOKBACK_DAYS)
    with duckdb.connect(str(database), read_only=True) as connection:
        batch = query_crsp_detector_market(
            connection,
            dataset_snapshot_id=CRSP_SNAPSHOT_ID,
            permnos=tuple(permnos),
            start_date=query_start,
            end_date=end_date,
        )
        security_context = _current_security_context(
            connection, {item.alias: item.permno for item in positions}
        )

    by_date: dict[datetime, list[Decimal]] = {}
    normalized: list[tuple[datetime, int, Decimal, datetime]] = []
    for row in batch.rows:
        by_date.setdefault(row.observed_at, []).append(row.total_return)
        normalized.append((row.observed_at, row.permno, row.total_return, row.available_at))
    benchmarks = {
        observed: sum(values, Decimal("0")) / Decimal(len(values))
        for observed, values in by_date.items()
    }
    observations = tuple(
        DetectorObservation(
            series_id=alias_by_permno[permno],
            scope_type=SignalScope.INSTRUMENT,
            scope_id=alias_by_permno[permno],
            observed_at=observed,
            available_at=available,
            value=value,
            benchmark_value=benchmarks[observed],
            evidence_ids=(
                f"crsp:{CRSP_SNAPSHOT_ID}:{permno}:{observed.date().isoformat()}",
            ),
            quality_flags=("licensed_read_only",),
        )
        for observed, permno, value, available in normalized
    )
    if not observations:
        raise HistoricalReplayError("no eligible complete CRSP returns exist for the requested period")
    return observations, batch.as_of, security_context, len(permnos), batch.missing_return_count


def execute_detector_scan(
    private_root: Path,
    *,
    portfolio_id: str,
    start_date: date,
    end_date: date,
) -> DetectorScanResult:
    """Execute the admitted scan once for projections and label production."""

    if start_date < COMMON_START or end_date > COMMON_END or start_date > end_date:
        raise HistoricalReplayError("case discovery dates must fall inside 2013–2017")
    if (end_date - start_date).days > MAX_PREVIEW_DAYS:
        raise HistoricalReplayError(
            f"one interactive case scan is limited to {MAX_PREVIEW_DAYS} calendar days"
        )
    observations, as_of, security_context, instrument_count, missing_returns = _query_market(
        private_root,
        portfolio_id=portfolio_id,
        start_date=start_date,
        end_date=end_date,
    )
    evidence = (
        AnalysisEvidence(
            evidence_id=f"crsp-snapshot-{CRSP_SNAPSHOT_ID}",
            reference=f"dataset://licensed/crsp/{CRSP_SNAPSHOT_ID}",
            digest=CRSP_CATALOGUE_DIGEST,
            description="Licensed read-only CRSP daily total-return revision used for case discovery.",
        ),
    )
    registry = CapabilityRegistry()
    cache_root = _cache_root()
    runs = []
    for definition in _definitions():
        result = registry.invoke(
            "market.anomaly.scan",
            DetectorExecutionRequest(
                definition=definition,
                observations=observations,
                as_of=as_of,
                evidence=evidence,
                cache_root=cache_root,
            ),
        )
        if result.status != "succeeded" or result.data is None:
            raise HistoricalReplayError(
                "case discovery detector failed: " + "; ".join(result.warnings)
            )
        runs.append(result.data)
    _write_receipt(
        cache_root,
        {
            "schema_version": "portfolio-risk.detector-preview-receipt/v1",
            "portfolio_id": portfolio_id,
            "requested_period": {"start": start_date.isoformat(), "end": end_date.isoformat()},
            "as_of": as_of.isoformat(),
            "dataset_snapshot_id": CRSP_SNAPSHOT_ID,
            "invocations": [item.model_dump(mode="json") for item in registry.invocation_history],
        },
    )

    alias_to_context = {
        position.alias: security_context.get(position.permno, {})
        for position in _positions(private_root, portfolio_id)[0]
    }
    return DetectorScanResult(
        runs=tuple(runs),
        observations=observations,
        as_of=as_of,
        security_context=alias_to_context,
        instrument_count=instrument_count,
        missing_returns=missing_returns,
    )


def signal_preview_payload(
    private_root: Path,
    *,
    portfolio_id: str,
    start_date: date,
    end_date: date,
) -> dict[str, Any]:
    """Run both admitted detectors and return a minimal user projection."""

    scan = execute_detector_scan(
        private_root,
        portfolio_id=portfolio_id,
        start_date=start_date,
        end_date=end_date,
    )
    detector_labels = {
        "robust-residual-z": "Unusual daily move",
        "two-sided-cusum": "Accumulating unusual moves",
    }
    visible = []
    for run in scan.runs:
        for signal in run.signals:
            if not start_date <= signal.observation_time.date() <= end_date:
                continue
            context = scan.security_context.get(signal.series_id, {})
            visible.append(
                {
                    "company": context.get("company_name", signal.series_id),
                    "ticker": context.get("ticker", "—"),
                    "date": signal.observation_time.date().isoformat(),
                    "direction": signal.direction.value,
                    "score": round(float(signal.standardised_score), 2),
                    "threshold": round(float(signal.threshold), 2),
                    "detector": detector_labels.get(signal.detector_id, signal.detector_id),
                    "source": "CRSP total return · portfolio-relative",
                }
            )
    visible.sort(key=lambda item: (abs(item["score"]), item["date"]), reverse=True)
    displayed = visible[:MAX_VISIBLE_SIGNALS]
    sessions = len({item.observed_at.date() for item in scan.observations if start_date <= item.observed_at.date() <= end_date})
    return {
        "status": "complete",
        "data": "Licensed CRSP · read only",
        "period": {"start": start_date.isoformat(), "end": end_date.isoformat()},
        "summary": {
            "instruments": scan.instrument_count,
            "sessions": sessions,
            "signals": len(visible),
            "downside": sum(item["direction"] == "downside" for item in visible),
            "upside": sum(item["direction"] == "upside" for item in visible),
            "missing_returns_excluded": scan.missing_returns,
        },
        "signals": displayed,
        "more_signals": max(0, len(visible) - len(displayed)),
        "method_note": (
            "The scan compares each security with the same-day portfolio average and uses only "
            "the preceding 63 sessions to identify unusually large or accumulating moves."
        ),
        "interpretation_note": (
            "These are statistical leads for case review. They are not alerts, causes, or accepted risk episodes."
        ),
    }
