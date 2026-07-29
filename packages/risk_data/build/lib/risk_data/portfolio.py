"""Bounded local portfolio-input workflow for Day 1.

Raw bytes are parsed in memory and never written.  Only normalized previews and
immutable snapshots may be stored beneath ``PORTFOLIO_RISK_DATA_ROOT``.
"""

from __future__ import annotations

import csv
import io
import os
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Mapping

import yaml
from pydantic import ValidationError

from risk_domain import CashBalance, MarketObservation, PortfolioSnapshot, Position, QualityFlag
from risk_domain.digests import sha256_digest

from .contracts import (
    PortfolioConfirmationRequest,
    PortfolioConfirmationResult,
    PortfolioInputCashBalance,
    PortfolioInputDocument,
    PortfolioInputFormat,
    PortfolioInputIssue,
    PortfolioInputPosition,
    PortfolioInputPreview,
    SnapshotComparison,
    SnapshotPositionChange,
)
from .serialization import manifest_json
from .pipeline import resolve_data_root


MAX_INPUT_BYTES = 1_000_000
MAX_INPUT_ROWS = 10_000
CSV_HEADERS = ("instrument_id", "quantity", "currency", "as_of")
YAML_FIELDS = frozenset(("profile", "as_of", "base_currency", "positions", "cash_balances"))


class PortfolioConfirmationError(ValueError):
    """Raised when a confirmation cannot create an immutable snapshot."""


def _parse_decimal(value: object, location: str, issues: list[PortfolioInputIssue]) -> Decimal | None:
    if isinstance(value, bool) or value is None:
        issues.append(PortfolioInputIssue(code="invalid_decimal", message="a finite Decimal value is required", severity="error", location=location))
        return None
    try:
        decimal = Decimal(str(value))
    except (InvalidOperation, ValueError):
        issues.append(PortfolioInputIssue(code="invalid_decimal", message="a finite Decimal value is required", severity="error", location=location))
        return None
    if not decimal.is_finite():
        issues.append(PortfolioInputIssue(code="invalid_decimal", message="a finite Decimal value is required", severity="error", location=location))
        return None
    return decimal


def _parse_timestamp(value: object, location: str, issues: list[PortfolioInputIssue]) -> datetime | None:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            issues.append(PortfolioInputIssue(code="invalid_timestamp", message="an ISO-8601 timezone-aware timestamp is required", severity="error", location=location))
            return None
    else:
        issues.append(PortfolioInputIssue(code="invalid_timestamp", message="an ISO-8601 timezone-aware timestamp is required", severity="error", location=location))
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        issues.append(PortfolioInputIssue(code="naive_timestamp", message="timestamps must be timezone-aware", severity="error", location=location))
        return None
    return parsed.astimezone(UTC)


def _unsafe_text(value: object) -> bool:
    return isinstance(value, str) and value.lstrip().startswith(("=", "+", "@"))


def _issue_from_validation(error: ValidationError) -> list[PortfolioInputIssue]:
    return [PortfolioInputIssue(code="invalid_document", message=item["msg"], severity="error", location=".".join(str(part) for part in item["loc"])) for item in error.errors()]


class PortfolioInputService:
    """Parser, preview, confirmation, and comparison service with no provider I/O."""

    def __init__(self, data_root: Path | None = None) -> None:
        configured = os.environ.get("PORTFOLIO_RISK_DATA_ROOT")
        selected_root = data_root if data_root is not None else configured
        self.data_root = resolve_data_root(selected_root) if selected_root is not None else None

    def preview(
        self,
        content: bytes,
        input_format: PortfolioInputFormat,
        *,
        profile: str | None = None,
        base_currency: str | None = None,
        as_of: datetime | None = None,
        cash_balances: tuple[PortfolioInputCashBalance, ...] = (),
    ) -> PortfolioInputPreview:
        """Create and optionally persist a normalized preview, never a snapshot."""
        issues: list[PortfolioInputIssue] = []
        document_data: dict[str, Any] | None = None
        if len(content) > MAX_INPUT_BYTES:
            issues.append(PortfolioInputIssue(code="input_too_large", message=f"input exceeds {MAX_INPUT_BYTES} byte limit", severity="error"))
        elif input_format is PortfolioInputFormat.CSV:
            document_data = self._parse_csv(content, profile, base_currency, as_of, cash_balances, issues)
        elif input_format is PortfolioInputFormat.YAML:
            document_data = self._parse_yaml(content, issues)
        else:
            issues.append(PortfolioInputIssue(code="unsupported_format", message="only CSV and YAML portfolio input is accepted", severity="error"))

        document: PortfolioInputDocument | None = None
        if document_data is not None and not any(issue.severity == "error" for issue in issues):
            document_data["content_digest"] = "sha256:" + __import__("hashlib").sha256(content).hexdigest()
            try:
                document = PortfolioInputDocument.model_validate(document_data)
            except ValidationError as error:
                issues.extend(_issue_from_validation(error))
        flags = tuple(sorted({"invalid_input" if issue.severity == "error" else issue.code for issue in issues}))
        preview_digest = sha256_digest({"document": document, "issues": issues, "quality_flags": flags})
        preview = PortfolioInputPreview(document=document, issues=tuple(issues), quality_flags=flags, preview_digest=preview_digest)
        self._write_normalized_preview(preview)
        return preview

    def _parse_csv(self, content: bytes, profile: str | None, base_currency: str | None, as_of: datetime | None, cash_balances: tuple[PortfolioInputCashBalance, ...], issues: list[PortfolioInputIssue]) -> dict[str, Any] | None:
        if profile is None or base_currency is None or as_of is None:
            issues.append(PortfolioInputIssue(code="csv_context_required", message="CSV input requires caller-supplied profile, base_currency, and as_of", severity="error"))
            return None
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError:
            issues.append(PortfolioInputIssue(code="invalid_encoding", message="CSV must be UTF-8", severity="error"))
            return None
        reader = csv.DictReader(io.StringIO(text, newline=""))
        headers = reader.fieldnames
        allowed_headers = (CSV_HEADERS[:2], CSV_HEADERS[:2] + ("currency",), CSV_HEADERS[:2] + ("as_of",), CSV_HEADERS)
        if headers is None or tuple(headers) not in allowed_headers:
            issues.append(PortfolioInputIssue(code="invalid_csv_headers", message="CSV headers must be exactly instrument_id,quantity with optional trailing currency,as_of", severity="error", location="header"))
            return None
        positions: list[dict[str, Any]] = []
        for index, row in enumerate(reader, start=2):
            if index - 1 > MAX_INPUT_ROWS:
                issues.append(PortfolioInputIssue(code="too_many_rows", message=f"CSV exceeds {MAX_INPUT_ROWS} row limit", severity="error"))
                break
            if None in row or any(_unsafe_text(value) for value in row.values()):
                issues.append(PortfolioInputIssue(code="unsafe_content", message="formula or executable CSV content is not accepted", severity="error", location=f"row:{index}"))
                continue
            quantity = _parse_decimal(row.get("quantity"), f"row:{index}.quantity", issues)
            instrument_id = row.get("instrument_id", "")
            if not instrument_id:
                issues.append(PortfolioInputIssue(code="missing_instrument_id", message="instrument_id is required", severity="error", location=f"row:{index}.instrument_id"))
            if "as_of" in row and row["as_of"]:
                row_time = _parse_timestamp(row["as_of"], f"row:{index}.as_of", issues)
                if row_time is not None and row_time != as_of.astimezone(UTC):
                    issues.append(PortfolioInputIssue(code="inconsistent_as_of", message="CSV row as_of must match caller as_of", severity="error", location=f"row:{index}.as_of"))
            if quantity is not None and instrument_id:
                positions.append({"instrument_id": instrument_id, "quantity": quantity, "currency": row.get("currency") or None})
        return {"input_format": "csv", "profile": profile, "as_of": as_of, "base_currency": base_currency, "positions": positions, "cash_balances": cash_balances}

    def _parse_yaml(self, content: bytes, issues: list[PortfolioInputIssue]) -> dict[str, Any] | None:
        try:
            payload = yaml.safe_load(content)
        except yaml.YAMLError:
            issues.append(PortfolioInputIssue(code="malformed_yaml", message="YAML could not be parsed safely", severity="error"))
            return None
        if not isinstance(payload, dict):
            issues.append(PortfolioInputIssue(code="invalid_yaml_document", message="YAML root must be a mapping", severity="error"))
            return None
        unknown = set(payload) - YAML_FIELDS
        missing = YAML_FIELDS - set(payload)
        if unknown or missing:
            issues.append(PortfolioInputIssue(code="invalid_yaml_fields", message=f"YAML fields must be exactly {', '.join(sorted(YAML_FIELDS))}", severity="error"))
            return None
        if any(_unsafe_text(value) for value in payload.values() if not isinstance(value, (list, dict))):
            issues.append(PortfolioInputIssue(code="unsafe_content", message="formula or executable YAML content is not accepted", severity="error"))
            return None
        parsed_as_of = _parse_timestamp(payload["as_of"], "as_of", issues)
        positions_value = payload["positions"]
        cash_value = payload["cash_balances"]
        if not isinstance(positions_value, list) or not isinstance(cash_value, dict):
            issues.append(PortfolioInputIssue(code="invalid_yaml_collection", message="positions must be a list and cash_balances must be a currency-to-Decimal mapping", severity="error"))
            return None
        if len(positions_value) > MAX_INPUT_ROWS:
            issues.append(PortfolioInputIssue(code="too_many_rows", message=f"YAML exceeds {MAX_INPUT_ROWS} position limit", severity="error"))
            return None
        positions: list[dict[str, Any]] = []
        for index, value in enumerate(positions_value):
            if not isinstance(value, dict) or set(value) - {"instrument_id", "quantity", "currency"} or {"instrument_id", "quantity"} - set(value):
                issues.append(PortfolioInputIssue(code="invalid_position", message="each position allows instrument_id, quantity, and optional currency only", severity="error", location=f"positions:{index}"))
                continue
            quantity = _parse_decimal(value.get("quantity"), f"positions:{index}.quantity", issues)
            if _unsafe_text(value.get("instrument_id")) or _unsafe_text(value.get("currency")):
                issues.append(PortfolioInputIssue(code="unsafe_content", message="formula or executable YAML content is not accepted", severity="error", location=f"positions:{index}"))
            elif quantity is not None:
                positions.append({"instrument_id": value.get("instrument_id"), "quantity": quantity, "currency": value.get("currency")})
        cash: list[dict[str, Any]] = []
        for currency, value in cash_value.items():
            if not isinstance(currency, str) or _unsafe_text(currency):
                issues.append(PortfolioInputIssue(code="invalid_cash_balance", message="cash balance currencies must be plain ISO codes", severity="error", location=f"cash_balances:{currency}"))
                continue
            amount = _parse_decimal(value, f"cash_balances:{currency}", issues)
            if amount is not None:
                cash.append({"currency": currency, "amount": amount})
        return {"input_format": "yaml", "profile": payload["profile"], "as_of": parsed_as_of, "base_currency": payload["base_currency"], "positions": positions, "cash_balances": cash}

    def confirm(self, preview: PortfolioInputPreview, request: PortfolioConfirmationRequest, market_observations: Mapping[str, MarketObservation]) -> PortfolioConfirmationResult:
        if not request.confirm:
            raise PortfolioConfirmationError("explicit confirm=true is required")
        if request.preview_digest != preview.preview_digest:
            raise PortfolioConfirmationError("confirmation preview digest does not match")
        if not preview.valid or preview.document is None:
            raise PortfolioConfirmationError("invalid preview cannot be confirmed")
        document = preview.document
        observations = tuple(market_observations.get(position.instrument_id) for position in document.positions)
        if any(observation is None or observation.price is None or observation.observed_at > document.as_of for observation in observations):
            raise PortfolioConfirmationError("available dated market observations are required for every position")
        if any(observation.instrument_id != position.instrument_id for position, observation in zip(document.positions, observations, strict=True) if observation is not None):
            raise PortfolioConfirmationError("market observation instrument_id must match its requested position")
        if any(set(observation.quality_flags) != {QualityFlag.COMPLETE} for observation in observations if observation is not None):
            raise PortfolioConfirmationError("complete market observations are required for every position")
        if any(observation.currency != document.base_currency for observation in observations if observation is not None):
            raise PortfolioConfirmationError("market observation currency must equal base_currency; FX conversion is not available")
        if any(balance.currency != document.base_currency for balance in document.cash_balances):
            raise PortfolioConfirmationError("cash balance currency must equal base_currency; FX conversion is not available")
        positions = tuple(Position(instrument_id=item.instrument_id, quantity=item.quantity, price=observation.price, market_value=item.quantity * observation.price, currency=observation.currency) for item, observation in zip(document.positions, observations, strict=True) if observation is not None and observation.price is not None)
        content_identity = sha256_digest({"preview_digest": preview.preview_digest, "positions": positions, "cash_balances": document.cash_balances, "observations": observations})
        snapshot = PortfolioSnapshot(snapshot_id="portfolio-" + content_identity.removeprefix("sha256:"), as_of=document.as_of, base_currency=document.base_currency, positions=positions, cash_balances=tuple(CashBalance(currency=item.currency, amount=item.amount) for item in document.cash_balances), market_observations=tuple(item for item in observations if item is not None))
        created = self._write_snapshot(snapshot)
        return PortfolioConfirmationResult(snapshot_id=snapshot.snapshot_id, snapshot_digest=snapshot.digest, created=created, quality_flags=preview.quality_flags)

    def compare(self, left: PortfolioSnapshot, right: PortfolioSnapshot) -> SnapshotComparison:
        left_positions = {position.instrument_id: position for position in left.positions}
        right_positions = {position.instrument_id: position for position in right.positions}
        changes: list[SnapshotPositionChange] = []
        for instrument_id in sorted(left_positions.keys() | right_positions.keys()):
            left_position, right_position = left_positions.get(instrument_id), right_positions.get(instrument_id)
            if left_position is None:
                changes.append(SnapshotPositionChange(instrument_id=instrument_id, change_type="added", right_quantity=right_position.quantity))
            elif right_position is None:
                changes.append(SnapshotPositionChange(instrument_id=instrument_id, change_type="removed", left_quantity=left_position.quantity))
            elif left_position.quantity != right_position.quantity:
                changes.append(SnapshotPositionChange(instrument_id=instrument_id, change_type="changed", left_quantity=left_position.quantity, right_quantity=right_position.quantity))
        left_cash = {item.currency: item.amount for item in left.cash_balances}
        right_cash = {item.currency: item.amount for item in right.cash_balances}
        cash_changes = tuple(PortfolioInputCashBalance(currency=currency, amount=right_cash.get(currency, Decimal("0")) - left_cash.get(currency, Decimal("0"))) for currency in sorted(left_cash.keys() | right_cash.keys()) if left_cash.get(currency, Decimal("0")) != right_cash.get(currency, Decimal("0")))
        return SnapshotComparison(left_snapshot_id=left.snapshot_id, right_snapshot_id=right.snapshot_id, position_changes=tuple(changes), cash_changes=cash_changes, valuation_context="Snapshot values use the dated market observations retained in each immutable snapshot; no FX conversion or refreshed valuation was performed.", evidence=(left.digest, right.digest), limitations=("Comparison is read-only.", "Missing market observations are never treated as zero."))

    def _write_normalized_preview(self, preview: PortfolioInputPreview) -> None:
        if self.data_root is None:
            return
        path = self.data_root / "portfolio-previews" / f"{preview.preview_digest.removeprefix('sha256:')}.json"
        self._write_once(path, preview.model_dump(mode="json"))

    def _write_snapshot(self, snapshot: PortfolioSnapshot) -> bool:
        if self.data_root is None:
            raise PortfolioConfirmationError("PORTFOLIO_RISK_DATA_ROOT is required to persist a confirmed snapshot")
        path = self.data_root / "portfolio-snapshots" / f"{snapshot.snapshot_id}.json"
        return self._write_once(path, snapshot.model_dump(mode="json"))

    @staticmethod
    def _write_once(path: Path, payload: dict[str, Any]) -> bool:
        path.parent.mkdir(parents=True, exist_ok=True)
        rendered = manifest_json(payload)
        try:
            with path.open("x", encoding="utf-8") as handle:
                handle.write(rendered)
            return True
        except FileExistsError:
            if path.read_text(encoding="utf-8") != rendered:
                raise PortfolioConfirmationError("immutable record path already contains different content")
            return False
