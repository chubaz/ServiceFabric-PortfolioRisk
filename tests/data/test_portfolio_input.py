"""Day 1 local portfolio input, immutability, and catalogue tests."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from risk_data import PortfolioConfirmationError, PortfolioConfirmationRequest, PortfolioInputFormat, PortfolioInputService, provider_catalogue, reviewed_query_manifests
from risk_domain import MarketObservation, QualityFlag


AS_OF = datetime(2026, 7, 21, tzinfo=UTC)


def observation(instrument_id: str, *, price: str = "10", observed_at: datetime = AS_OF, quality_flags: tuple[QualityFlag, ...] = (QualityFlag.COMPLETE,)) -> MarketObservation:
    return MarketObservation(instrument_id=instrument_id, observed_at=observed_at, price=Decimal(price), currency="USD", synthetic=True, quality_flags=quality_flags)


def csv_input(quantity: str = "2") -> bytes:
    return f"instrument_id,quantity,currency,as_of\ninstrument-nova,{quantity},USD,2026-07-21T00:00:00Z\n".encode()


def yaml_input() -> bytes:
    return b"profile: personal_portfolio\nas_of: '2026-07-21T00:00:00Z'\nbase_currency: USD\npositions:\n  - instrument_id: instrument-nova\n    quantity: '2.5'\n    currency: USD\ncash_balances:\n  USD: '100'\n"


def test_valid_csv_preview_has_decimal_positions_and_never_creates_snapshot(tmp_path) -> None:
    service = PortfolioInputService(tmp_path)
    preview = service.preview(csv_input(), PortfolioInputFormat.CSV, profile="personal_portfolio", base_currency="USD", as_of=AS_OF)

    assert preview.valid
    assert preview.document is not None
    assert preview.document.positions[0].quantity == Decimal("2")
    assert not (tmp_path / "portfolio-snapshots").exists()
    assert (tmp_path / "portfolio-previews").is_dir()


def test_repository_local_and_relative_data_roots_are_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    repository_root = Path(__file__).resolve().parents[2]
    with pytest.raises(ValueError, match="must not be written inside the repository"):
        PortfolioInputService(repository_root / "private-portfolio-data")
    monkeypatch.chdir(repository_root)
    with pytest.raises(ValueError, match="must not be written inside the repository"):
        PortfolioInputService(Path("private-portfolio-data"))


def test_valid_yaml_safe_load_and_validation_errors_are_visible(tmp_path) -> None:
    service = PortfolioInputService(tmp_path)
    preview = service.preview(yaml_input(), PortfolioInputFormat.YAML)
    typed_timestamp = service.preview(yaml_input().replace(b"'2026-07-21T00:00:00Z'", b"2026-07-21T00:00:00Z"), PortfolioInputFormat.YAML)
    malformed = service.preview(b"profile: [", PortfolioInputFormat.YAML)
    naive = service.preview(yaml_input().replace(b"2026-07-21T00:00:00Z", b"2026-07-21T00:00:00"), PortfolioInputFormat.YAML)

    assert preview.valid and preview.document is not None
    assert typed_timestamp.valid
    assert preview.document.positions[0].quantity == Decimal("2.5")
    assert not malformed.valid and malformed.issues[0].code == "malformed_yaml"
    assert not naive.valid and any(issue.code == "naive_timestamp" for issue in naive.issues)


def test_malformed_yaml_error_does_not_persist_raw_input_fragments(tmp_path) -> None:
    raw_fragment = b"PRIVATE-INSTRUMENT-123"
    preview = PortfolioInputService(tmp_path).preview(b"positions: [" + raw_fragment + b"\n", PortfolioInputFormat.YAML)
    persisted = next((tmp_path / "portfolio-previews").glob("*.json")).read_bytes()

    assert not preview.valid
    assert preview.issues[0].message == "YAML could not be parsed safely"
    assert raw_fragment not in persisted


@pytest.mark.parametrize("content", [b"instrument_id,quantity,other\ninstrument-nova,1,x\n", b"instrument_id,quantity\ninstrument-nova,nope\n"])
def test_malformed_csv_and_invalid_decimal_are_blocked(content: bytes) -> None:
    preview = PortfolioInputService().preview(content, PortfolioInputFormat.CSV, profile="research", base_currency="USD", as_of=AS_OF)
    assert not preview.valid


def test_duplicate_positions_and_unknown_yaml_fields_are_blocked() -> None:
    content = yaml_input().replace(b"cash_balances:", b"unexpected: nope\ncash_balances:")
    duplicate = yaml_input().replace(b"cash_balances:", b"  - instrument_id: instrument-nova\n    quantity: '3'\ncash_balances:")
    assert not PortfolioInputService().preview(content, PortfolioInputFormat.YAML).valid
    assert not PortfolioInputService().preview(duplicate, PortfolioInputFormat.YAML).valid


def test_confirmation_requires_valid_matching_explicit_preview_and_dated_observations(tmp_path) -> None:
    service = PortfolioInputService(tmp_path)
    preview = service.preview(csv_input(), PortfolioInputFormat.CSV, profile="personal_portfolio", base_currency="USD", as_of=AS_OF)
    with pytest.raises(PortfolioConfirmationError, match="confirm=true"):
        service.confirm(preview, PortfolioConfirmationRequest(confirm=False, preview_digest=preview.preview_digest), {"instrument-nova": observation("instrument-nova")})
    with pytest.raises(PortfolioConfirmationError, match="does not match"):
        service.confirm(preview, PortfolioConfirmationRequest(confirm=True, preview_digest="sha256:" + "0" * 64), {"instrument-nova": observation("instrument-nova")})
    with pytest.raises(PortfolioConfirmationError, match="dated market"):
        service.confirm(preview, PortfolioConfirmationRequest(confirm=True, preview_digest=preview.preview_digest), {})


def test_confirmation_rejects_mismatched_future_and_incomplete_observations(tmp_path) -> None:
    service = PortfolioInputService(tmp_path)
    preview = service.preview(csv_input(), PortfolioInputFormat.CSV, profile="personal_portfolio", base_currency="USD", as_of=AS_OF)
    request = PortfolioConfirmationRequest(confirm=True, preview_digest=preview.preview_digest)

    with pytest.raises(PortfolioConfirmationError, match="instrument_id must match"):
        service.confirm(preview, request, {"instrument-nova": observation("instrument-other")})
    with pytest.raises(PortfolioConfirmationError, match="dated market"):
        service.confirm(preview, request, {"instrument-nova": observation("instrument-nova", observed_at=datetime(2026, 7, 21, 16, tzinfo=UTC))})
    for flags in ((), (QualityFlag.PARTIAL,), (QualityFlag.MISSING,)):
        with pytest.raises(PortfolioConfirmationError, match="complete market"):
            service.confirm(preview, request, {"instrument-nova": observation("instrument-nova", quality_flags=flags)})


def test_confirmation_is_immutable_idempotent_and_corrections_create_new_snapshot(tmp_path) -> None:
    service = PortfolioInputService(tmp_path)
    first_preview = service.preview(csv_input(), PortfolioInputFormat.CSV, profile="personal_portfolio", base_currency="USD", as_of=AS_OF)
    request = PortfolioConfirmationRequest(confirm=True, preview_digest=first_preview.preview_digest)
    first = service.confirm(first_preview, request, {"instrument-nova": observation("instrument-nova")})
    repeated = service.confirm(first_preview, request, {"instrument-nova": observation("instrument-nova")})
    correction = service.preview(csv_input("3"), PortfolioInputFormat.CSV, profile="personal_portfolio", base_currency="USD", as_of=AS_OF)
    corrected = service.confirm(correction, PortfolioConfirmationRequest(confirm=True, preview_digest=correction.preview_digest), {"instrument-nova": observation("instrument-nova")})

    assert first.created and not repeated.created
    assert first.snapshot_id == repeated.snapshot_id
    assert corrected.snapshot_id != first.snapshot_id
    assert len(list((tmp_path / "portfolio-snapshots").glob("*.json"))) == 2
    assert b"instrument_id,quantity" not in b"".join(path.read_bytes() for path in tmp_path.rglob("*.json"))


def test_read_only_snapshot_comparison_identifies_position_and_cash_changes(tmp_path) -> None:
    service = PortfolioInputService(tmp_path)
    first_preview = service.preview(yaml_input(), PortfolioInputFormat.YAML)
    first = service.confirm(first_preview, PortfolioConfirmationRequest(confirm=True, preview_digest=first_preview.preview_digest), {"instrument-nova": observation("instrument-nova")})
    second_preview = service.preview(yaml_input().replace(b"'2.5'", b"'3'"), PortfolioInputFormat.YAML)
    second = service.confirm(second_preview, PortfolioConfirmationRequest(confirm=True, preview_digest=second_preview.preview_digest), {"instrument-nova": observation("instrument-nova")})
    import json
    from risk_domain import PortfolioSnapshot
    left = PortfolioSnapshot.model_validate(json.loads((tmp_path / "portfolio-snapshots" / f"{first.snapshot_id}.json").read_text()))
    right = PortfolioSnapshot.model_validate(json.loads((tmp_path / "portfolio-snapshots" / f"{second.snapshot_id}.json").read_text()))
    comparison = service.compare(left, right)

    assert comparison.left_snapshot_id == first.snapshot_id
    assert comparison.position_changes[0].change_type == "changed"
    assert "read-only" in comparison.limitations[0].lower()


def test_catalogue_has_disabled_external_sources_and_fixed_views_only() -> None:
    catalogue = provider_catalogue()
    external = [entry for entry in catalogue if entry.provider_id in {"wrds", "crsp", "compustat", "ravenpack", "accern", "bloomberg"}]
    manifests = reviewed_query_manifests()

    assert all(not entry.enabled and entry.access_state == "unavailable" for entry in external)
    assert all(entry.credential_secret_ref and not any(word in entry.credential_secret_ref.lower() for word in ("token", "password", "key=")) for entry in external)
    assert {manifest.view_name for manifest in manifests} == {"market_prices", "fundamentals", "latest_market_prices", "latest_fundamentals"}
    assert not hasattr(PortfolioInputService, "execute_sql")
