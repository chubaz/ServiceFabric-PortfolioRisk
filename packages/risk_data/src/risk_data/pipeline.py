"""Deterministic local-only materialization of the Day 0 synthetic datasets."""

from __future__ import annotations

import hashlib
import os
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Literal

import duckdb
import pyarrow as pa
import pyarrow.parquet as pq
from pydantic import Field, field_validator, model_validator

from risk_domain import DatasetFile, DatasetProvenance, DatasetSnapshot as DomainDatasetSnapshot, InstrumentIdentifier, SourceReference
from risk_domain.digests import sha256_digest

from .contracts import DataContract, FIXTURE_SEED, NormalizedFundamentalRecord, NormalizedMarketRecord, QuerySpec, SYNTHETIC_LABEL, _utc
from .serialization import manifest_json


FIXTURE_CREATED_AT = datetime(2026, 7, 21, 12, 0, tzinfo=UTC)
RUN_ID = "synthetic-ingestion-20260721"
REPOSITORY_ROOT = Path(__file__).resolve().parents[4]


class SyntheticProviderRecord(DataContract):
    """Schema-validated raw record from the fictional, in-memory provider."""

    dataset: Literal["market", "fundamental"]
    symbol: str
    observed_at: datetime
    price: Decimal | None = None
    metric: str | None = None
    value: Decimal | None = None
    unit: str | None = None
    currency: str | None = None
    synthetic: bool = True
    synthetic_label: Literal["synthetic"] = SYNTHETIC_LABEL
    fixture_seed: int = FIXTURE_SEED

    _observed_at = field_validator("observed_at")(_utc)

    @model_validator(mode="after")
    def has_dataset_specific_fields(self) -> "SyntheticProviderRecord":
        if not self.synthetic or self.synthetic_label != SYNTHETIC_LABEL:
            raise ValueError("synthetic provider records must retain synthetic metadata")
        if self.dataset == "market" and self.currency is None:
            raise ValueError("market provider records require a currency")
        if self.dataset == "fundamental" and (self.metric is None or self.unit is None):
            raise ValueError("fundamental provider records require metric and unit")
        return self


class IngestionEvidence(DataContract):
    input_row_count: int = Field(ge=0)
    accepted_row_count: int = Field(ge=0)
    rejected_row_count: int = Field(ge=0)
    duplicates: int = Field(ge=0)
    missing_identifiers: int = Field(ge=0)
    stale_observations: int = Field(ge=0)
    missing_values: int = Field(ge=0)
    minimum_date: datetime | None = None
    maximum_date: datetime | None = None
    content_digests: dict[str, str]

    _minimum_date = field_validator("minimum_date")(_utc)
    _maximum_date = field_validator("maximum_date")(_utc)


class SyntheticIngestionResult(DataContract):
    data_root: Path
    ingestion_manifest: Path
    snapshot_manifest: Path
    snapshot: DomainDatasetSnapshot
    evidence: IngestionEvidence


def resolve_data_root(output_root: Path | str | None = None) -> Path:
    """Resolve the only permitted mutable root and reject repository-local output."""
    raw_root = output_root if output_root is not None else os.environ.get("PORTFOLIO_RISK_DATA_ROOT")
    if raw_root is None:
        raise ValueError("PORTFOLIO_RISK_DATA_ROOT is required when no output root is supplied")
    root = Path(raw_root).expanduser().resolve()
    if root == REPOSITORY_ROOT or REPOSITORY_ROOT in root.parents:
        raise ValueError("generated data must not be written inside the repository")
    return root


def _market_rows() -> tuple[SyntheticProviderRecord, ...]:
    dates = ("2026-07-13", "2026-07-14", "2026-07-15", "2026-07-16", "2026-07-17")
    prices = {
        "ALPHA": ("100.00", "102.00", "101.00", "100.00", "88.00"),
        "BETA": ("50.00", "50.40", "50.20", "50.60", "50.80"),
        "GAMMA": ("200.00", "201.00", "199.50", "202.00", "203.00"),
    }
    records = [
        SyntheticProviderRecord(dataset="market", symbol=symbol, observed_at=datetime.fromisoformat(f"{date}T00:00:00+00:00"), price=Decimal(price), currency="USD")
        for symbol, series in prices.items()
        for date, price in zip(dates, series, strict=True)
    ]
    # Intentional candidates for validation evidence; none reach persisted data.
    records.extend(
        (
            SyntheticProviderRecord(dataset="market", symbol="ALPHA", observed_at=datetime(2026, 7, 16, tzinfo=UTC), price=Decimal("100.50"), currency="USD"),
            SyntheticProviderRecord(dataset="market", symbol="", observed_at=datetime(2026, 7, 15, tzinfo=UTC), price=Decimal("9.00"), currency="USD"),
            SyntheticProviderRecord(dataset="market", symbol="GAMMA", observed_at=datetime(2026, 6, 1, tzinfo=UTC), price=Decimal("190.00"), currency="USD"),
            SyntheticProviderRecord(dataset="market", symbol="DELTA", observed_at=datetime(2026, 7, 17, tzinfo=UTC), price=None, currency="USD"),
        )
    )
    return tuple(records)


def _fundamental_rows() -> tuple[SyntheticProviderRecord, ...]:
    values = {"ALPHA": ("1450000", "182000"), "BETA": ("980000", "124000"), "GAMMA": ("2100000", "303000")}
    return tuple(
        SyntheticProviderRecord(dataset="fundamental", symbol=symbol, observed_at=datetime(2026, 7, 17, tzinfo=UTC), metric=metric, value=Decimal(value), unit="USD")
        for symbol, metrics in values.items()
        for metric, value in zip(("revenue", "net_income"), metrics, strict=True)
    )


def _normalise(records: tuple[SyntheticProviderRecord, ...]) -> tuple[list[dict[str, object]], list[dict[str, object]], IngestionEvidence]:
    market: list[dict[str, object]] = []
    fundamentals: list[dict[str, object]] = []
    seen: set[tuple[str, str, datetime, str | None]] = set()
    rejected = duplicates = missing_identifiers = stale_observations = missing_values = 0
    accepted_dates: list[datetime] = []
    for record in records:
        if not record.symbol:
            missing_identifiers += 1
            rejected += 1
            continue
        if record.dataset == "market" and record.price is None or record.dataset == "fundamental" and record.value is None:
            missing_values += 1
            rejected += 1
            continue
        if record.observed_at < datetime(2026, 7, 10, tzinfo=UTC):
            stale_observations += 1
            rejected += 1
            continue
        key = (record.dataset, record.symbol, record.observed_at, record.metric)
        if key in seen:
            duplicates += 1
            rejected += 1
            continue
        seen.add(key)
        identifier = InstrumentIdentifier(identifier_type="ticker", value=record.symbol)
        if record.dataset == "market":
            normalized = NormalizedMarketRecord(instrument_id=f"instrument-{record.symbol.lower()}", identifier=identifier, observed_at=record.observed_at, price=record.price, currency=record.currency or "USD")
            market.append({"symbol": record.symbol, "instrument_id": normalized.instrument_id, "identifier_type": normalized.identifier.identifier_type, "identifier_value": normalized.identifier.value, "observed_at": normalized.observed_at, "price": normalized.price, "currency": normalized.currency, "synthetic": normalized.synthetic, "synthetic_label": normalized.synthetic_label, "fixture_seed": normalized.fixture_seed, "quality_flags": "complete"})
        else:
            normalized = NormalizedFundamentalRecord(instrument_id=f"instrument-{record.symbol.lower()}", identifier=identifier, metric=record.metric or "", observed_at=record.observed_at, value=record.value, unit=record.unit or "")
            fundamentals.append({"symbol": record.symbol, "instrument_id": normalized.instrument_id, "identifier_type": normalized.identifier.identifier_type, "identifier_value": normalized.identifier.value, "metric": normalized.metric, "observed_at": normalized.observed_at, "value": normalized.value, "unit": normalized.unit, "synthetic": normalized.synthetic, "synthetic_label": normalized.synthetic_label, "fixture_seed": normalized.fixture_seed, "quality_flags": "complete"})
        accepted_dates.append(record.observed_at)
    source_digest = sha256_digest([record.model_dump(mode="python") for record in records])
    evidence = IngestionEvidence(input_row_count=len(records), accepted_row_count=len(market) + len(fundamentals), rejected_row_count=rejected, duplicates=duplicates, missing_identifiers=missing_identifiers, stale_observations=stale_observations, missing_values=missing_values, minimum_date=min(accepted_dates), maximum_date=max(accepted_dates), content_digests={"synthetic_provider_rows": source_digest})
    return market, fundamentals, evidence


def _sha256_file(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _assert_new(paths: tuple[Path, ...]) -> None:
    existing = [str(path) for path in paths if path.exists()]
    if existing:
        raise FileExistsError("immutable ingestion artifacts already exist: " + ", ".join(existing))


def ingest_synthetic(output_root: Path | str | None = None) -> SyntheticIngestionResult:
    """Materialize deterministic Parquet, DuckDB views, and immutable manifests."""
    root = resolve_data_root(output_root)
    market_path = root / "market" / "prices.parquet"
    fundamentals_path = root / "fundamentals" / "fundamentals.parquet"
    catalog_path = root / "catalog" / "day0.duckdb"
    run_path = root / "manifests" / "ingestion-run.json"
    snapshot_path = root / "manifests" / "dataset-snapshot.json"
    _assert_new((market_path, fundamentals_path, catalog_path, run_path, snapshot_path))
    for directory in {path.parent for path in (market_path, fundamentals_path, catalog_path, run_path, snapshot_path)}:
        directory.mkdir(parents=True, exist_ok=True)

    records = _market_rows() + _fundamental_rows()
    market_rows, fundamental_rows, evidence = _normalise(records)
    pq.write_table(pa.Table.from_pylist(market_rows), market_path, compression="zstd")
    pq.write_table(pa.Table.from_pylist(fundamental_rows), fundamentals_path, compression="zstd")

    with duckdb.connect(str(catalog_path)) as connection:
        market_sql = str(market_path).replace("'", "''")
        fundamentals_sql = str(fundamentals_path).replace("'", "''")
        connection.execute(f"CREATE VIEW market_prices AS SELECT * FROM read_parquet('{market_sql}')")
        connection.execute(f"CREATE VIEW fundamentals AS SELECT * FROM read_parquet('{fundamentals_sql}')")
        connection.execute("CREATE VIEW latest_market_prices AS SELECT * EXCLUDE (row_number) FROM (SELECT *, row_number() OVER (PARTITION BY instrument_id ORDER BY observed_at DESC) AS row_number FROM market_prices) WHERE row_number = 1")
        connection.execute("CREATE VIEW latest_fundamentals AS SELECT * EXCLUDE (row_number) FROM (SELECT *, row_number() OVER (PARTITION BY instrument_id, metric ORDER BY observed_at DESC) AS row_number FROM fundamentals) WHERE row_number = 1")

    evidence = evidence.model_copy(update={"content_digests": evidence.content_digests | {"market/prices.parquet": _sha256_file(market_path), "fundamentals/fundamentals.parquet": _sha256_file(fundamentals_path), "catalog/day0.duckdb": _sha256_file(catalog_path)}})
    market_query = QuerySpec(dataset="market", instrument_ids=("instrument-alpha", "instrument-beta", "instrument-gamma"), start_at=datetime(2026, 7, 13, tzinfo=UTC), end_at=datetime(2026, 7, 17, tzinfo=UTC), include_duplicate_candidates=True)
    fundamental_query = QuerySpec(dataset="fundamental", instrument_ids=("instrument-alpha", "instrument-beta", "instrument-gamma"), start_at=datetime(2026, 7, 13, tzinfo=UTC), end_at=datetime(2026, 7, 17, tzinfo=UTC), include_duplicate_candidates=False)
    run_manifest = {"run_id": RUN_ID, "created_at": FIXTURE_CREATED_AT, "synthetic": True, "synthetic_label": SYNTHETIC_LABEL, "fixture_seed": FIXTURE_SEED, "query_digests": {"market": sha256_digest(market_query), "fundamentals": sha256_digest(fundamental_query)}, "evidence": evidence}
    run_path.write_text(manifest_json(run_manifest), encoding="utf-8")
    evidence = evidence.model_copy(update={"content_digests": evidence.content_digests | {"manifests/ingestion-run.json": _sha256_file(run_path)}})

    files = tuple(DatasetFile(path=path, media_type=media_type, size=(root / path).stat().st_size, digest=_sha256_file(root / path), row_count=row_count) for path, media_type, row_count in (("market/prices.parquet", "application/vnd.apache.parquet", len(market_rows)), ("fundamentals/fundamentals.parquet", "application/vnd.apache.parquet", len(fundamental_rows)), ("catalog/day0.duckdb", "application/vnd.duckdb", 0)))
    snapshot = DomainDatasetSnapshot(snapshot_id="synthetic-day0-dataset-20260721", created_at=FIXTURE_CREATED_AT, files=files, ingestion_run_ids=(RUN_ID,), source_query_digests=(sha256_digest(market_query), sha256_digest(fundamental_query)), provenance=DatasetProvenance(synthetic=True, synthetic_label=SYNTHETIC_LABEL, synthetic_seed=FIXTURE_SEED, sources=(SourceReference(source_id="synthetic-fixture", source_type="fixture", reference="fixture://day0/20260721", retrieved_at=FIXTURE_CREATED_AT),)))
    snapshot_path.write_text(manifest_json(snapshot), encoding="utf-8")
    return SyntheticIngestionResult(data_root=root, ingestion_manifest=run_path, snapshot_manifest=snapshot_path, snapshot=snapshot, evidence=evidence)
