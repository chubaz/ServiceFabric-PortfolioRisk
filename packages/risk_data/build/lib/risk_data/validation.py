"""Deterministic quality checks for normalized ingestion candidates."""

from __future__ import annotations

from datetime import datetime, timedelta

from .contracts import DataQualityCode, DataQualityIssue, NormalizedRecord, ValidationSummary


def validate_records(records: tuple[NormalizedRecord, ...], *, requested_instrument_ids: tuple[str, ...], stale_after: timedelta = timedelta(days=7), reference_at: datetime) -> ValidationSummary:
    """Report duplicate, missing, and stale candidates without mutating them."""
    seen: set[str] = set()
    issues: list[DataQualityIssue] = []
    for record in records:
        if record.record_key in seen:
            issues.append(DataQualityIssue(code=DataQualityCode.DUPLICATE, record_key=record.record_key, message="duplicate normalized candidate", severity="error"))
        seen.add(record.record_key)
        value = record.price if hasattr(record, "price") else record.value
        if value is None:
            issues.append(DataQualityIssue(code=DataQualityCode.MISSING, record_key=record.record_key, message="observation value remains missing", severity="warning"))
        if record.observed_at < reference_at - stale_after:
            issues.append(DataQualityIssue(code=DataQualityCode.STALE, record_key=record.record_key, message="observation is stale for the ingestion reference time", severity="warning"))
    returned_instrument_ids = {record.instrument_id for record in records}
    for instrument_id in requested_instrument_ids:
        if instrument_id not in returned_instrument_ids:
            issues.append(DataQualityIssue(code=DataQualityCode.MISSING, record_key=f"query:{instrument_id}", message="requested instrument produced no observations", severity="warning"))
    return ValidationSummary(issues=tuple(issues))
