"""Tiny schema-compatible tests for the licensed local-export bridge."""

from __future__ import annotations

import ast
import hashlib
import json
import os
import socket
import subprocess
import sys
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import duckdb
import pyarrow as pa
import pyarrow.parquet as pq
import pytest
import yaml
from pydantic import ValidationError

from risk_data.cli import main as cli_main
from risk_data import (
    DatasetBuildSpecification,
    LicensedDataError,
    SourceColumnMapping,
    WhitelistedTransformation,
    build_crsp_compustat,
    candidate_crsp_universe,
    init_crsp_compustat_manifest,
    load_licensed_manifest,
    profile_crsp_compustat,
    verify_crsp_compustat,
)


ROOT = Path(__file__).resolve().parents[2]
RETRIEVED_AT = datetime(2026, 7, 29, 10, tzinfo=UTC)


def _fingerprint(schema: pa.Schema) -> str:
    return "sha256:" + hashlib.sha256(str(schema).encode()).hexdigest()


def _profile_type(field: pa.Field) -> str:
    if pa.types.is_string(field.type):
        return "string"
    if pa.types.is_int16(field.type):
        return "int16"
    if pa.types.is_int32(field.type):
        return "int32"
    if pa.types.is_int64(field.type):
        return "int64"
    if pa.types.is_floating(field.type):
        return "double"
    if pa.types.is_date32(field.type):
        return "date32[day]"
    raise AssertionError(field.type)


def _write(path: Path, rows: list[dict[str, object]], schema: pa.Schema) -> None:
    pq.write_table(pa.Table.from_pylist(rows, schema=schema), path, compression="zstd")


@pytest.fixture
def private_sources(tmp_path: Path) -> tuple[Path, Path]:
    source_root = tmp_path / "licensed-sources"
    source_root.mkdir()
    daily_schema = pa.schema(
        [
            ("permno", pa.int64()),
            ("permco", pa.int64()),
            ("date", pa.date32()),
            ("prc", pa.float64()),
            ("vol", pa.float64()),
            ("ret", pa.float64()),
            ("retx", pa.float64()),
            ("shrout", pa.float64()),
            ("cfacpr", pa.float64()),
            ("cfacshr", pa.float64()),
        ]
    )
    daily_rows = [
        {"permno": 10001, "permco": 9001, "date": date(2024, 1, 2), "prc": -20.0, "vol": 100.0, "ret": 0.1, "retx": 0.08, "shrout": 10.0, "cfacpr": 2.0, "cfacshr": 2.0},
        {"permno": 10001, "permco": 9001, "date": date(2024, 1, 3), "prc": 21.0, "vol": 110.0, "ret": 0.05, "retx": 0.04, "shrout": 10.0, "cfacpr": 2.0, "cfacshr": 2.0},
        {"permno": 10001, "permco": 9001, "date": date(2024, 1, 5), "prc": 22.0, "vol": 120.0, "ret": 0.02, "retx": 0.01, "shrout": 10.0, "cfacpr": 2.0, "cfacshr": 2.0},
    ]
    _write(source_root / "dsf.parquet", daily_rows, daily_schema)
    _write(source_root / "msf.parquet", daily_rows[:2], daily_schema)

    ccm_schema = pa.schema(
        [
            ("gvkey", pa.string()),
            ("lpermno", pa.int64()),
            ("lpermco", pa.int64()),
            ("linkdt", pa.date32()),
            ("linkenddt", pa.date32()),
            ("linktype", pa.string()),
            ("linkprim", pa.string()),
        ]
    )
    _write(
        source_root / "ccm_lookup.parquet",
        [{"gvkey": "001001", "lpermno": 10001, "lpermco": 9001, "linkdt": date(2020, 1, 1), "linkenddt": None, "linktype": "LC", "linkprim": "P"}],
        ccm_schema,
    )
    annual_schema = pa.schema(
        [
            ("gvkey", pa.string()),
            ("datadate", pa.date32()),
            ("pdate", pa.date32()),
            ("fyear", pa.int32()),
            ("indfmt", pa.string()),
            ("consol", pa.string()),
            ("popsrc", pa.string()),
            ("datafmt", pa.string()),
            ("curcd", pa.string()),
            ("at", pa.float64()),
            ("lt", pa.float64()),
            ("ceq", pa.float64()),
            ("sale", pa.float64()),
            ("ni", pa.float64()),
        ]
    )
    _write(
        source_root / "funda.parquet",
        [
            {"gvkey": "001001", "datadate": date(2023, 12, 31), "pdate": date(2024, 2, 15), "fyear": 2023, "indfmt": "INDL", "consol": "C", "popsrc": "D", "datafmt": "STD", "curcd": "USD", "at": 100.0, "lt": 50.0, "ceq": 50.0, "sale": 80.0, "ni": 8.0},
            {"gvkey": "001001", "datadate": date(2022, 12, 31), "pdate": None, "fyear": 2022, "indfmt": "INDL", "consol": "C", "popsrc": "D", "datafmt": "STD", "curcd": "USD", "at": 90.0, "lt": 45.0, "ceq": 45.0, "sale": 70.0, "ni": 7.0},
        ],
        annual_schema,
    )
    quarterly_schema = pa.schema(
        [
            ("gvkey", pa.string()),
            ("datadate", pa.date32()),
            ("rdq", pa.date32()),
            ("fyearq", pa.int32()),
            ("fqtr", pa.int32()),
            ("indfmt", pa.string()),
            ("consol", pa.string()),
            ("popsrc", pa.string()),
            ("datafmt", pa.string()),
            ("curcdq", pa.string()),
            ("atq", pa.float64()),
            ("ltq", pa.float64()),
            ("ceqq", pa.float64()),
            ("saleq", pa.float64()),
            ("niq", pa.float64()),
        ]
    )
    _write(
        source_root / "fundq.parquet",
        [{"gvkey": "001001", "datadate": date(2024, 3, 31), "rdq": date(2024, 4, 20), "fyearq": 2024, "fqtr": 1, "indfmt": "INDL", "consol": "C", "popsrc": "D", "datafmt": "STD", "curcdq": "USD", "atq": 110.0, "ltq": 52.0, "ceqq": 58.0, "saleq": 22.0, "niq": 2.0}],
        quarterly_schema,
    )
    delist_schema = pa.schema(
        [
            ("permno", pa.int64()),
            ("permco", pa.int64()),
            ("dlstdt", pa.date32()),
            ("dlstcd", pa.int16()),
            ("dlprc", pa.float64()),
            ("dlret", pa.float64()),
            ("dlretx", pa.float64()),
        ]
    )
    _write(
        source_root / "dsedelist.parquet",
        [{"permno": 10001, "permco": 9001, "dlstdt": date(2024, 1, 5), "dlstcd": 500, "dlprc": 19.0, "dlret": None, "dlretx": -0.1}],
        delist_schema,
    )
    names_schema = pa.schema(
        [
            ("permno", pa.int64()),
            ("permco", pa.int64()),
            ("namedt", pa.date32()),
            ("nameenddt", pa.date32()),
            ("shrcd", pa.int16()),
            ("exchcd", pa.int16()),
            ("siccd", pa.int32()),
            ("ncusip", pa.string()),
            ("ticker", pa.string()),
            ("comnam", pa.string()),
            ("shrcls", pa.string()),
        ]
    )
    _write(
        source_root / "stocknames.parquet",
        [
            {"permno": 10001, "permco": 9001, "namedt": date(2020, 1, 1), "nameenddt": date(2023, 12, 31), "shrcd": 10, "exchcd": 1, "siccd": 1234, "ncusip": "00000001", "ticker": "OLD", "comnam": "Fictional Old", "shrcls": "A"},
            {"permno": 10001, "permco": 9001, "namedt": date(2024, 1, 1), "nameenddt": None, "shrcd": 10, "exchcd": 1, "siccd": 1234, "ncusip": "00000001", "ticker": "NEW", "comnam": "Fictional New", "shrcls": "A"},
        ],
        names_schema,
    )

    source_name_for_file = {
        "dsf.parquet": "crsp_daily",
        "msf.parquet": "crsp_monthly",
        "ccm_lookup.parquet": "ccm_links",
        "funda.parquet": "compustat_annual",
        "fundq.parquet": "compustat_quarterly",
        "dsedelist.parquet": "crsp_delist",
        "stocknames.parquet": "crsp_stock_names",
    }
    sources = []
    for path in sorted(source_root.glob("*.parquet")):
        schema = pq.read_schema(path)
        sources.append(
            {
                "source_name": source_name_for_file[path.name],
                "filename": path.name,
                "schema_fingerprint": _fingerprint(schema),
                "columns": [
                    {"name": field.name, "type": _profile_type(field), "nullable": field.nullable}
                    for field in schema
                ],
            }
        )
    profile = tmp_path / "source-schemas.json"
    profile.write_text(
        json.dumps(
            {
                "inventory_type": "schema-only-crsp-compustat-source-profile",
                "contains_licensed_rows": False,
                "contains_private_paths": False,
                "contains_source_digests": False,
                "sources": sources,
            }
        ),
        encoding="utf-8",
    )
    return source_root, profile


def _reviewed_manifest(private_sources: tuple[Path, Path], tmp_path: Path) -> Path:
    source_root, profile = private_sources
    path = tmp_path / "private" / "licensed.yaml"
    init_crsp_compustat_manifest(
        profile,
        source_root,
        path,
        revision="revision-1",
        retrieved_at=RETRIEVED_AT,
    )
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert raw["reviewed"] is False
    raw["reviewed"] = True
    path.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")
    return path


def _build(private_sources: tuple[Path, Path], tmp_path: Path):
    manifest = _reviewed_manifest(private_sources, tmp_path)
    return build_crsp_compustat(
        DatasetBuildSpecification(
            manifest_path=manifest,
            data_root=tmp_path / "data-root",
            temp_directory=tmp_path / "data-root" / "tmp",
            memory_limit="256MB",
            threads=1,
            code_revision="test-revision",
        )
    )


def test_contracts_are_frozen_safe_and_reject_query_language() -> None:
    mapping = SourceColumnMapping(
        canonical_name="raw_price",
        source_columns=("prc",),
        canonical_type="DECIMAL",
    )
    with pytest.raises(ValidationError):
        mapping.canonical_name = "changed"  # type: ignore[misc]
    with pytest.raises(ValidationError, match="pattern"):
        SourceColumnMapping(
            canonical_name="raw_price; select",
            source_columns=("prc",),
            canonical_type="DECIMAL",
        )
    assert "sql" not in SourceColumnMapping.model_fields
    assert "expression" not in WhitelistedTransformation.model_fields


def test_initializer_requires_human_review_and_manifest_rejects_false(
    private_sources: tuple[Path, Path], tmp_path: Path
) -> None:
    source_root, profile = private_sources
    path = tmp_path / "private" / "licensed.yaml"
    init_crsp_compustat_manifest(
        profile, source_root, path, revision="r1", retrieved_at=RETRIEVED_AT
    )
    with pytest.raises(LicensedDataError, match="reviewed"):
        load_licensed_manifest(path)


def test_profile_detects_digest_mismatch_and_schema_drift(
    private_sources: tuple[Path, Path], tmp_path: Path
) -> None:
    manifest_path = _reviewed_manifest(private_sources, tmp_path)
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    manifest["sources"][0]["source_digest"] = "sha256:" + "0" * 64
    manifest_path.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")
    with pytest.raises(LicensedDataError, match="digest"):
        profile_crsp_compustat(manifest_path, temp_directory=tmp_path / "tmp")

    manifest_path = _reviewed_manifest(private_sources, tmp_path / "other")
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    manifest["sources"][0]["schema_fingerprint"]["columns"][0]["name"] = "drifted"
    manifest_path.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")
    with pytest.raises(LicensedDataError, match="schema drift"):
        profile_crsp_compustat(manifest_path, temp_directory=tmp_path / "tmp2")


@pytest.mark.parametrize(
    ("source_name", "required_column"),
    [
        ("ccm_links", "gvkey"),
        ("ccm_links", "lpermno"),
        ("ccm_links", "linkdt"),
        ("compustat_annual", "datadate"),
        ("compustat_quarterly", "gvkey"),
        ("crsp_delist", "dlstdt"),
    ],
)
def test_initializer_rejects_profiles_missing_required_join_keys(
    private_sources: tuple[Path, Path],
    tmp_path: Path,
    source_name: str,
    required_column: str,
) -> None:
    source_root, profile_path = private_sources
    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    source = next(
        item for item in profile["sources"] if item["source_name"] == source_name
    )
    source["columns"] = [
        item for item in source["columns"] if item["name"] != required_column
    ]
    profile_path.write_text(json.dumps(profile), encoding="utf-8")
    with pytest.raises(LicensedDataError, match="required join-key"):
        init_crsp_compustat_manifest(
            profile_path,
            source_root,
            tmp_path / "private" / "invalid.yaml",
            revision="invalid",
            retrieved_at=RETRIEVED_AT,
        )


def test_build_preserves_temporal_price_return_delist_and_frequency_semantics(
    private_sources: tuple[Path, Path], tmp_path: Path
) -> None:
    result = _build(private_sources, tmp_path)
    with duckdb.connect(str(result.catalogue_path), read_only=True) as connection:
        prices = connection.execute(
            "SELECT raw_price, valuation_price, split_adjusted_price, "
            "total_return, return_ex_distributions, CAST(available_at AS VARCHAR) "
            "FROM crsp_daily ORDER BY observed_at"
        ).fetchall()
        assert prices[0][:5] == (-20, 20, 10, Decimal("0.100000000000"), Decimal("0.080000000000"))
        assert prices[0][5].startswith("2024-01-03")
        assert prices[1][5].startswith("2024-01-05")
        assert prices[2][5] is None
        assert connection.execute(
            "SELECT count(*) FROM crsp_daily WHERE available_at <= TIMESTAMPTZ '2024-01-02 12:00:00+00'"
        ).fetchone()[0] == 0
        delist = connection.execute(
            "SELECT total_return, delisting_return, delisting_return_ex_distributions "
            "FROM crsp_with_delist WHERE delisting_date IS NOT NULL"
        ).fetchone()
        assert delist == (Decimal("0.020000000000"), None, Decimal("-0.100000000000"))
        assert connection.execute(
            "SELECT count(*) FROM compustat_annual"
        ).fetchone()[0] == 2
        assert connection.execute(
            "SELECT count(*) FROM compustat_quarterly"
        ).fetchone()[0] == 1
        assert connection.execute(
            "SELECT count(*) FROM fundamentals_as_of"
        ).fetchone()[0] == 2
        assert connection.execute(
            "SELECT ticker FROM security_history "
            "WHERE DATE '2023-01-01' BETWEEN valid_from AND coalesce(valid_to, DATE '9999-12-31')"
        ).fetchone()[0] == "OLD"
        assert connection.execute(
            "SELECT ticker FROM security_history "
            "WHERE DATE '2024-01-02' BETWEEN valid_from AND coalesce(valid_to, DATE '9999-12-31')"
        ).fetchone()[0] == "NEW"


def test_partition_receipt_catalogue_repeat_and_verification(
    private_sources: tuple[Path, Path], tmp_path: Path
) -> None:
    first = _build(private_sources, tmp_path)
    second = build_crsp_compustat(
        DatasetBuildSpecification(
            manifest_path=tmp_path / "private" / "licensed.yaml",
            data_root=tmp_path / "data-root",
            temp_directory=tmp_path / "data-root" / "tmp",
            memory_limit="256MB",
            threads=1,
            code_revision="test-revision",
        )
    )
    assert first.created and not second.created
    assert first.snapshot_id == second.snapshot_id
    assert first.catalogue_path == tmp_path / "data-root" / "catalog" / "crsp-compustat.duckdb"
    assert all(first.receipt.partitions.values())
    assert all(
        any("partition_year=" in path for path in paths)
        for name, paths in first.receipt.partitions.items()
        if name in first.receipt.source_digests
    )
    assert verify_crsp_compustat(tmp_path / "data-root").snapshot_id == first.snapshot_id
    snapshot_catalogue = (
        tmp_path
        / "data-root"
        / "catalog"
        / "snapshots"
        / first.snapshot_id
        / "crsp-compustat.duckdb"
    )
    assert snapshot_catalogue.is_file()
    assert first.receipt.catalogue_digest.startswith("sha256:")


def test_revised_input_creates_a_new_immutable_snapshot(
    private_sources: tuple[Path, Path], tmp_path: Path
) -> None:
    first = _build(private_sources, tmp_path)
    source_root, profile = private_sources
    table = pq.read_table(source_root / "dsf.parquet")
    rows = table.to_pylist()
    rows[0]["prc"] = -20.5
    pq.write_table(
        pa.Table.from_pylist(rows, schema=table.schema),
        source_root / "dsf.parquet",
        compression="zstd",
    )
    second_manifest = tmp_path / "private" / "licensed-revision-2.yaml"
    init_crsp_compustat_manifest(
        profile,
        source_root,
        second_manifest,
        revision="revision-2",
        retrieved_at=datetime(2026, 7, 29, 11, tzinfo=UTC),
    )
    raw = yaml.safe_load(second_manifest.read_text(encoding="utf-8"))
    raw["reviewed"] = True
    second_manifest.write_text(
        yaml.safe_dump(raw, sort_keys=False), encoding="utf-8"
    )
    second = build_crsp_compustat(
        DatasetBuildSpecification(
            manifest_path=second_manifest,
            data_root=tmp_path / "data-root",
            temp_directory=tmp_path / "data-root" / "tmp",
            memory_limit="256MB",
            threads=1,
            code_revision="test-revision",
        )
    )
    assert second.created and second.snapshot_id != first.snapshot_id
    assert first.receipt_path.is_file() and second.receipt_path.is_file()
    assert len(list((tmp_path / "data-root" / "normalized").iterdir())) == 2
    with duckdb.connect(str(second.catalogue_path), read_only=True) as connection:
        assert connection.execute(
            "SELECT snapshot_id FROM catalogue_snapshot_metadata"
        ).fetchone()[0] == second.snapshot_id
    assert (
        verify_crsp_compustat(
            tmp_path / "data-root", snapshot_id=first.snapshot_id
        ).snapshot_id
        == first.snapshot_id
    )
    first_catalogue = (
        tmp_path
        / "data-root"
        / "catalog"
        / "snapshots"
        / first.snapshot_id
        / "crsp-compustat.duckdb"
    )
    second_catalogue = (
        tmp_path
        / "data-root"
        / "catalog"
        / "snapshots"
        / second.snapshot_id
        / "crsp-compustat.duckdb"
    )
    first_catalogue.write_bytes(second_catalogue.read_bytes())
    with pytest.raises(LicensedDataError, match="catalogue digest mismatch"):
        verify_crsp_compustat(
            tmp_path / "data-root", snapshot_id=first.snapshot_id
        )


def test_empty_partitioned_source_emits_schema_bearing_parquet(
    private_sources: tuple[Path, Path], tmp_path: Path
) -> None:
    source_root, _ = private_sources
    path = source_root / "dsedelist.parquet"
    schema = pq.read_schema(path)
    pq.write_table(
        pa.Table.from_pylist([], schema=schema), path, compression="zstd"
    )
    result = _build(private_sources, tmp_path)
    assert result.receipt.output_row_counts["crsp_delist"] == 0
    assert result.receipt.partitions["crsp_delist"] == ("data.parquet",)
    with duckdb.connect(str(result.catalogue_path), read_only=True) as connection:
        assert connection.execute("SELECT count(*) FROM crsp_delist").fetchone()[0] == 0


def test_ambiguous_ccm_links_block_without_ticker_fallback(
    private_sources: tuple[Path, Path], tmp_path: Path
) -> None:
    source_root, _ = private_sources
    table = pq.read_table(source_root / "ccm_lookup.parquet")
    rows = table.to_pylist()
    rows.append(rows[0] | {"gvkey": "009999"})
    pq.write_table(pa.Table.from_pylist(rows, schema=table.schema), source_root / "ccm_lookup.parquet")
    manifest_path = _reviewed_manifest(private_sources, tmp_path)
    with pytest.raises(LicensedDataError, match="ambiguous"):
        build_crsp_compustat(
            DatasetBuildSpecification(
                manifest_path=manifest_path,
                data_root=tmp_path / "root",
                temp_directory=tmp_path / "root" / "tmp",
                code_revision="r1",
            )
        )
    assert not list((tmp_path / "root" / "normalized").glob("*"))
    manifest = load_licensed_manifest(manifest_path)
    assert manifest.link_policy.ticker_fallback is False


def test_candidate_universe_rejects_overlapping_stock_name_intervals(
    private_sources: tuple[Path, Path], tmp_path: Path
) -> None:
    source_root, _ = private_sources
    path = source_root / "stocknames.parquet"
    table = pq.read_table(path)
    rows = table.to_pylist()
    rows[1]["namedt"] = date(2023, 1, 1)
    pq.write_table(
        pa.Table.from_pylist(rows, schema=table.schema), path, compression="zstd"
    )
    result = _build(private_sources, tmp_path)
    assert result.join_quality.stock_name_overlap_rows > 0
    with pytest.raises(LicensedDataError, match="overlapping StockNames"):
        candidate_crsp_universe(
            tmp_path / "data-root",
            as_of=datetime(2024, 1, 6, tzinfo=UTC),
            minimum_observations=1,
            limit=10,
        )


def test_candidate_cli_writes_private_v2_evidence_without_printing_rows(
    private_sources: tuple[Path, Path],
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    result = _build(private_sources, tmp_path)
    output_parent = tmp_path / "data-root" / "evidence" / "reviewer-shared"
    output_parent.mkdir()
    output_parent.chmod(0o750)
    output = output_parent / "candidate-artifact.json"
    assert cli_main(
        [
            "candidate-crsp-universe",
            "--data-root",
            str(tmp_path / "data-root"),
            "--as-of",
            "2024-01-06T00:00:00Z",
            "--minimum-observations",
            "1",
            "--limit",
            "10",
            "--output",
            str(output),
        ]
    ) == 0
    console_text = capsys.readouterr().out
    console = json.loads(console_text)
    assert set(console) == {
        "artifact_id",
        "candidate_count",
        "snapshot_id",
        "rows_printed",
    }
    assert console["snapshot_id"] == result.snapshot_id
    assert console["candidate_count"] == 1
    assert console["rows_printed"] == 0

    artifact = json.loads(output.read_text(encoding="utf-8"))
    assert artifact["artifact_version"] == "2.0"
    assert artifact["artifact_id"] == console["artifact_id"]
    assert artifact["snapshot_id"] == result.snapshot_id
    assert artifact["minimum_observations"] == 1
    assert artifact["created_from"] == {
        "dataset_receipt_id": result.receipt.receipt_id,
        "catalogue_digest": result.receipt.catalogue_digest,
    }
    candidate = artifact["candidates"][0]
    assert set(candidate) == {
        "candidate_id",
        "permno",
        "observation_count",
        "latest_eligible_date",
        "missing_total_return_count",
        "missing_valuation_price_count",
        "active_stock_names_coverage",
        "sector",
        "sic_code",
        "ccm_eligible_link_count",
        "fundamental_availability_coverage",
        "quality_warnings",
    }
    assert candidate["permno"] == 10001
    assert candidate["sic_code"] == 1234
    assert candidate["observation_count"] == 2
    assert "ticker" not in candidate and "company_name" not in candidate
    assert "Fictional" not in console_text
    assert output.stat().st_mode & 0o777 == 0o600
    assert output_parent.stat().st_mode & 0o777 == 0o750

    first = output.read_bytes()
    assert cli_main(
        [
            "candidate-crsp-universe",
            "--data-root",
            str(tmp_path / "data-root"),
            "--as-of",
            "2024-01-06T00:00:00Z",
            "--minimum-observations",
            "1",
            "--limit",
            "10",
            "--output",
            str(output),
        ]
    ) == 0
    assert output.read_bytes() == first
    capsys.readouterr()

    with pytest.raises(
        LicensedDataError, match="beneath the governed data root"
    ):
        cli_main(
            [
                "candidate-crsp-universe",
                "--data-root",
                str(tmp_path / "data-root"),
                "--as-of",
                "2024-01-06T00:00:00Z",
                "--minimum-observations",
                "1",
                "--limit",
                "10",
                "--output",
                str(tmp_path / "outside-governed-root.json"),
            ]
        )
    capsys.readouterr()


def test_candidate_universe_supports_daily_catalogue_without_stock_names(
    private_sources: tuple[Path, Path],
    tmp_path: Path,
) -> None:
    manifest_path = _reviewed_manifest(private_sources, tmp_path)
    raw = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    raw["sources"] = [
        source
        for source in raw["sources"]
        if source["source_name"] != "crsp_stock_names"
    ]
    manifest_path.write_text(
        yaml.safe_dump(raw, sort_keys=False),
        encoding="utf-8",
    )
    result = build_crsp_compustat(
        DatasetBuildSpecification(
            manifest_path=manifest_path,
            data_root=tmp_path / "data-root",
            temp_directory=tmp_path / "data-root" / "tmp",
            memory_limit="256MB",
            threads=1,
            code_revision="test-revision",
        )
    )
    candidates = candidate_crsp_universe(
        tmp_path / "data-root",
        as_of=datetime(2024, 1, 6, tzinfo=UTC),
        minimum_observations=1,
        limit=10,
    )
    assert result.snapshot_id
    assert len(candidates) == 1
    assert candidates[0]["sic_code"] is None
    assert candidates[0]["active_stock_names_coverage"] == {
        "eligible_observations": 2,
        "covered_observations": 0,
        "missing_observations": 2,
    }
    assert any(
        "StockNames coverage is incomplete" in warning
        for warning in candidates[0]["quality_warnings"]
    )


def test_bridge_source_has_no_full_table_python_materialization() -> None:
    source = (
        ROOT
        / "packages"
        / "risk_data"
        / "src"
        / "risk_data"
        / "licensed_crsp_compustat.py"
    ).read_text(encoding="utf-8")
    ast.parse(source)
    for forbidden in (
        "pyarrow.parquet.read_table",
        ".to_pylist(",
        "pandas.read_parquet",
        "pandas.DataFrame",
        ".collect(",
    ):
        assert forbidden not in source


def test_crsp_cli_loads_from_uninstalled_source_tree() -> None:
    environment = os.environ | {
        "PYTHONPATH": os.pathsep.join(
            (
                str(ROOT / "packages" / "risk_domain" / "src"),
                str(ROOT / "packages" / "risk_data" / "src"),
                str(ROOT / "examples" / "portfolio-risk-thesis" / "src"),
            )
        )
    }
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "risk_data.cli",
            "init-crsp-compustat-manifest",
            "--help",
        ],
        cwd=ROOT,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    assert "--schema-profile" in completed.stdout
    assert "--source-root" in completed.stdout
    assert "--manifest" in completed.stdout


def test_requested_profile_and_build_cli_forms(
    private_sources: tuple[Path, Path], tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    manifest = _reviewed_manifest(private_sources, tmp_path)
    profile_output = tmp_path / "profile" / "validated-profile.json"
    assert (
        cli_main(
            [
                "profile-crsp-compustat",
                "--source-manifest",
                str(manifest),
                "--output",
                str(profile_output),
            ]
        )
        == 0
    )
    profile = json.loads(profile_output.read_text(encoding="utf-8"))
    assert profile["sources_verified"] == 7
    assert profile["licensed_rows_printed"] == 0

    output_root = tmp_path / "output"
    assert (
        cli_main(
            [
                "build-crsp-compustat",
                "--source-manifest",
                str(manifest),
                "--output-root",
                str(output_root),
                "--mode",
                "daily-primary",
            ]
        )
        == 0
    )
    summary = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert summary["created"] is True
    assert summary["rows_printed"] == 0
    assert (output_root / "catalog" / "crsp-compustat.duckdb").is_file()
    assert (
        cli_main(
            [
                "verify-crsp-compustat",
                "--output-root",
                str(output_root),
                "--mode",
                "daily-primary",
            ]
        )
        == 0
    )


def test_no_network_and_no_repository_output(
    private_sources: tuple[Path, Path], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        socket,
        "socket",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("network")),
    )
    manifest = _reviewed_manifest(private_sources, tmp_path)
    profile_crsp_compustat(manifest, temp_directory=tmp_path / "tmp")
    with pytest.raises((ValidationError, LicensedDataError), match="outside Git"):
        build_crsp_compustat(
            DatasetBuildSpecification(
                manifest_path=manifest,
                data_root=ROOT / "generated",
                temp_directory=tmp_path / "tmp",
                code_revision="r1",
            )
        )


def test_monthly_smoke_and_daily_primary_require_explicit_source_kind(
    private_sources: tuple[Path, Path], tmp_path: Path
) -> None:
    manifest_path = _reviewed_manifest(private_sources, tmp_path)
    raw = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    raw["sources"] = [
        item for item in raw["sources"] if item["source_name"] == "crsp_monthly"
    ]
    monthly = tmp_path / "private" / "monthly.yaml"
    monthly.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")
    with pytest.raises(LicensedDataError, match="daily-primary"):
        build_crsp_compustat(
            DatasetBuildSpecification(
                manifest_path=monthly,
                data_root=tmp_path / "daily",
                temp_directory=tmp_path / "daily" / "tmp",
                code_revision="r1",
            )
        )
    result = build_crsp_compustat(
        DatasetBuildSpecification(
            manifest_path=monthly,
            data_root=tmp_path / "monthly",
            temp_directory=tmp_path / "monthly" / "tmp",
            code_revision="r1",
            mode="monthly_smoke",
        )
    )
    assert result.receipt.output_row_counts["crsp_monthly"] == 2
    assert "crsp_daily" not in result.receipt.output_row_counts


def test_legacy_and_ciz_style_columns_are_explicitly_mappable() -> None:
    legacy = SourceColumnMapping(
        canonical_name="total_return",
        source_columns=("ret",),
        canonical_type="DECIMAL",
    )
    ciz = SourceColumnMapping(
        canonical_name="total_return",
        source_columns=("dlyret",),
        canonical_type="DECIMAL",
    )
    assert legacy.source_columns != ciz.source_columns
    with pytest.raises(ValidationError, match="coalesce"):
        WhitelistedTransformation(
            transformation_id="bad_coalesce",
            operation="explicit_ordered_coalesce",
            version="1",
            source_columns=("ret",),
            disclosure="Invalid single-source coalesce.",
        )
