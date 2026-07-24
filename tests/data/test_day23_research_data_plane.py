"""Phase 1 governed local research data-plane acceptance tests."""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from pydantic import ValidationError

from risk_data import (
    DatasetDefinition,
    FieldDefinition,
    FieldMapping,
    FixedQueryManifest,
    FixedQueryRequest,
    LocalMappingManifest,
    LocalImportConfirmation,
    LocalImportError,
    PointInTimePolicy,
    ProviderAccessState,
    ProviderDefinition,
    PublicationRestriction,
    ResearchFixedQueryManifest,
    ResearchDataPlane,
    RightsState,
    fixed_query_manifests,
    load_mapping_manifest,
    reviewed_query_manifests,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
FIXTURES = REPOSITORY_ROOT / "data" / "fixtures" / "synthetic" / "day23"
RETRIEVED_AT = datetime(2026, 7, 22, 10, tzinfo=UTC)


def provider(profile: str = "synthetic_local") -> ProviderDefinition:
    return ProviderDefinition(provider_id="fictional-local-provider", display_name="Fictional Local Provider", profile=profile, access_state=ProviderAccessState.AVAILABLE)


def dataset(kind: str, dataset_id: str | None = None) -> DatasetDefinition:
    return DatasetDefinition(dataset_id=dataset_id or f"fictional-{kind}", provider_id="fictional-local-provider", dataset_kind=kind, description="Explicitly synthetic Phase 1 fixture")


def preview(plane: ResearchDataPlane, source: Path, kind: str, *, revision: str = "revision-1", mapping: Path | None = None, profile: str = "synthetic_local", retain_raw: bool = False):  # type: ignore[no-untyped-def]
    mapping_names = {"daily_market": "crsp_like_daily.mapping.json", "fundamentals_annual": "compustat_like_annual.mapping.json", "identifier_crosswalk": "crsp_compustat_link.mapping.json"}
    return plane.preview_local_export(source, provider=provider(profile), dataset=dataset(kind), revision_id=revision, rights_state=RightsState.REVIEWED_SYNTHETIC if profile == "synthetic_local" else RightsState.LICENSED_RESTRICTED, publication_restriction=PublicationRestriction.SYNTHETIC_ONLY if profile == "synthetic_local" else PublicationRestriction.NO_PUBLICATION, mapping_manifest=mapping or FIXTURES / mapping_names[kind], retrieved_at=RETRIEVED_AT, retain_raw_source=retain_raw)


def confirm(plane: ResearchDataPlane, item):  # type: ignore[no-untyped-def]
    return plane.confirm_local_export(item, LocalImportConfirmation(confirm=True, preview_digest=item.preview_digest, source_digest=item.source.source_digest))


def external_copy(tmp_path: Path, name: str) -> Path:
    path = tmp_path / name
    path.write_bytes((FIXTURES / name).read_bytes())
    return path


def import_all(plane: ResearchDataPlane, tmp_path: Path) -> None:
    confirm(plane, preview(plane, external_copy(tmp_path, "crsp_like_daily.csv"), "daily_market"))
    confirm(plane, preview(plane, external_copy(tmp_path, "compustat_like_annual.csv"), "fundamentals_annual"))
    confirm(plane, preview(plane, external_copy(tmp_path, "crsp_compustat_link.csv"), "identifier_crosswalk"))


def test_csv_schema_preview_is_non_curating_and_reports_mapping_quality(tmp_path: Path) -> None:
    root = tmp_path / "data-root"
    plane = ResearchDataPlane(root)
    item = preview(plane, external_copy(tmp_path, "crsp_like_daily.csv"), "daily_market")

    assert item.row_count == item.accepted_row_count == 4
    assert {field.field_name for field in item.source_schema} >= {"permno", "date", "prc", "ret"}
    assert item.rejected_row_count == 0 and not item.has_blocking_issues
    assert next(metric.value for metric in item.quality_report.metrics if metric.metric == "declared_units") != "none"
    assert not root.exists()


def test_parquet_preview_and_confirm_create_external_immutable_zones(tmp_path: Path) -> None:
    csv_path = external_copy(tmp_path, "crsp_like_daily.csv")
    import csv
    with csv_path.open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    parquet_path = tmp_path / "fictional-market.parquet"
    pq.write_table(pa.Table.from_pylist(rows), parquet_path)
    root = tmp_path / "data-root"
    plane = ResearchDataPlane(root)
    item = preview(plane, parquet_path, "daily_market")
    result = confirm(plane, item)

    assert item.source.file_format == "parquet"
    assert result.created and all(path.is_file() for path in result.normalized_paths)
    assert result.curated_path.is_file() and result.manifest_path.is_file()
    assert {path.name for path in root.iterdir()} == {"landing", "normalized", "curated", "manifests", "quality", "evidence"}
    assert not any((root / "landing").iterdir())


def test_raw_retention_is_opt_in_and_copies_only_to_external_landing(tmp_path: Path) -> None:
    source = external_copy(tmp_path, "crsp_like_daily.csv")
    root = tmp_path / "retained-root"
    plane = ResearchDataPlane(root)
    result = confirm(plane, preview(plane, source, "daily_market", retain_raw=True))
    evidence = json.loads((root / "evidence" / result.evidence_ids[0]).with_suffix(".json").read_text())
    landing_path = Path(evidence["source"]["landing_path"])

    assert evidence["source"]["retained"] is True
    assert landing_path.is_file() and landing_path.read_bytes() == source.read_bytes()
    assert root in landing_path.parents and REPOSITORY_ROOT not in landing_path.parents


@pytest.mark.parametrize("suffix", [".xlsx", ".sas7bdat", ".zip", ".duckdb", ".sqlite"])
def test_non_phase1_source_formats_are_rejected(tmp_path: Path, suffix: str) -> None:
    source = tmp_path / f"unsupported{suffix}"
    source.write_text("not a supported data source", encoding="utf-8")
    with pytest.raises(LocalImportError, match="CSV and Parquet"):
        preview(ResearchDataPlane(tmp_path / "root"), source, "daily_market")


def test_confirmation_digest_rights_publication_and_path_boundaries(tmp_path: Path) -> None:
    plane = ResearchDataPlane(tmp_path / "root")
    source = external_copy(tmp_path, "crsp_like_daily.csv")
    item = preview(plane, source, "daily_market")
    with pytest.raises(LocalImportError, match="confirm=true"):
        plane.confirm_local_export(item, LocalImportConfirmation(confirm=False, preview_digest=item.preview_digest, source_digest=item.source.source_digest))
    with pytest.raises(LocalImportError, match="preview digest"):
        plane.confirm_local_export(item, LocalImportConfirmation(confirm=True, preview_digest="sha256:" + "0" * 64, source_digest=item.source.source_digest))
    source.write_text(source.read_text() + "\n", encoding="utf-8")
    with pytest.raises(LocalImportError, match="source digest"):
        confirm(plane, item)
    with pytest.raises(LocalImportError, match="absolute"):
        preview(plane, Path("relative.csv"), "daily_market")
    with pytest.raises(LocalImportError, match="outside the repository"):
        preview(plane, FIXTURES / "crsp_like_daily.csv", "daily_market", profile="licensed_local")
    with pytest.raises((ValidationError, TypeError)):
        ProviderDefinition(provider_id="x", display_name="x", profile="licensed_local", access_state=ProviderAccessState.AVAILABLE, network_enabled=True)


def test_mapping_manifest_id_cannot_escape_external_storage(tmp_path: Path) -> None:
    plane = ResearchDataPlane(tmp_path / "root")
    source = external_copy(tmp_path, "crsp_like_daily.csv")
    mapping = load_mapping_manifest(FIXTURES / "crsp_like_daily.mapping.json")
    unsafe_mapping = mapping.model_copy(update={"manifest_id": "x/../../../../escaped"})
    with pytest.raises(ValidationError, match="manifest_id"):
        plane.preview_local_export(source, provider=provider(), dataset=dataset("daily_market"), revision_id="revision-unsafe-id", rights_state=RightsState.REVIEWED_SYNTHETIC, publication_restriction=PublicationRestriction.SYNTHETIC_ONLY, mapping_manifest=unsafe_mapping, retrieved_at=RETRIEVED_AT)

    assert not plane.data_root.exists()
    assert not (tmp_path / "escaped").exists()

    unsafe_path = tmp_path / "unsafe.mapping.json"
    payload = json.loads((FIXTURES / "crsp_like_daily.mapping.json").read_text())
    payload["manifest_id"] = "../../escaped"
    unsafe_path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(LocalImportError, match="invalid mapping manifest"):
        load_mapping_manifest(unsafe_path)


def test_rights_state_must_match_profile(tmp_path: Path) -> None:
    plane = ResearchDataPlane(tmp_path / "root")
    source = external_copy(tmp_path, "crsp_like_daily.csv")
    with pytest.raises(LocalImportError, match="rights state"):
        plane.preview_local_export(source, provider=provider("licensed_local"), dataset=dataset("daily_market"), revision_id="r1", rights_state=RightsState.REVIEWED_SYNTHETIC, publication_restriction=PublicationRestriction.NO_PUBLICATION, mapping_manifest=FIXTURES / "crsp_like_daily.mapping.json", retrieved_at=RETRIEVED_AT)


def test_missing_availability_warns_remains_missing_and_is_never_looked_ahead(tmp_path: Path) -> None:
    source = external_copy(tmp_path, "crsp_like_daily.csv")
    source.write_text(source.read_text().replace("2026-06-30T21:00:00Z,-41.00", ",-41.00", 1), encoding="utf-8")
    plane = ResearchDataPlane(tmp_path / "root")
    item = preview(plane, source, "daily_market")
    assert any(issue.code == "missing_available_at" and issue.severity == "warning" for issue in item.issues)
    result = confirm(plane, item)
    rows = pq.read_table(result.normalized_paths[0]).to_pylist()
    assert any(row["available_at"] is None and "missing_available_at" in row["quality_flags"] for row in rows)
    queried = plane.run_fixed_query(FixedQueryRequest(manifest_id="daily-market-history", as_of=datetime(2026, 7, 1, tzinfo=UTC), limit=20))
    assert len(queried.rows) == 3


def test_non_nullable_fields_and_timezone_naive_availability_are_blocking(tmp_path: Path) -> None:
    source = external_copy(tmp_path, "crsp_like_daily.csv")
    source.write_text(source.read_text().replace(",NOVA,USD", ",NOVA,", 1).replace("2026-06-30T21:00:00Z", "2026-06-30T21:00:00", 1), encoding="utf-8")
    plane = ResearchDataPlane(tmp_path / "root")
    item = preview(plane, source, "daily_market")

    assert any(issue.code == "missing_required_field" and issue.field == "currency" for issue in item.issues)
    assert any(issue.code == "invalid_date" and issue.field == "available_at" for issue in item.issues)
    assert item.rejected_row_count == 2
    with pytest.raises(LocalImportError, match="blocking"):
        confirm(plane, item)


def test_provider_numeric_missing_codes_do_not_erase_string_ticker_c(tmp_path: Path) -> None:
    source = external_copy(tmp_path, "crsp_like_daily.csv")
    source.write_text(source.read_text().replace(",NOVA,USD", ",C,USD"), encoding="utf-8")
    plane = ResearchDataPlane(tmp_path / "root")
    result = confirm(plane, preview(plane, source, "daily_market"))
    rows = pq.read_table(result.normalized_paths[0]).to_pylist()

    assert {row["ticker"] for row in rows if row["permno"] == "910001"} == {"C"}


def test_duplicate_invalid_date_and_missing_identifier_are_blocking(tmp_path: Path) -> None:
    source = external_copy(tmp_path, "crsp_like_daily.csv")
    lines = source.read_text().splitlines()
    lines[1] = lines[1].replace("910001", "", 1).replace("2026-06-29", "not-a-date", 1)
    lines.append(lines[2])
    source.write_text("\n".join(lines) + "\n", encoding="utf-8")
    plane = ResearchDataPlane(tmp_path / "root")
    item = preview(plane, source, "daily_market")
    assert {issue.code for issue in item.issues} >= {"missing_identifier", "invalid_date", "duplicate_key"}
    assert item.rejected_row_count == 2
    with pytest.raises(LocalImportError, match="blocking"):
        confirm(plane, item)


def test_transformations_retain_raw_price_and_emit_unit_evidence(tmp_path: Path) -> None:
    plane = ResearchDataPlane(tmp_path / "root")
    result = confirm(plane, preview(plane, external_copy(tmp_path, "crsp_like_daily.csv"), "daily_market"))
    rows = pq.read_table(result.normalized_paths[0]).to_pylist()
    evidence = json.loads((plane.data_root / "evidence" / f"evidence-{result.snapshot_id}.json").read_text())

    assert rows[0]["raw_price"] == "-40.00" and rows[0]["valuation_price"] == "40.00"
    assert json.loads(rows[0]["source_values"])["prc"] == "-40.00"
    assert evidence["transformations"][0]["operation"] == "sign_normalization"
    quality = json.loads(result.quality_path.read_text())
    assert next(metric["value"] for metric in quality["metrics"] if metric["metric"] == "declared_units") != "none"


def test_repeat_is_idempotent_and_corrected_revision_creates_new_snapshot(tmp_path: Path) -> None:
    plane = ResearchDataPlane(tmp_path / "root")
    source = external_copy(tmp_path, "crsp_like_daily.csv")
    first_preview = preview(plane, source, "daily_market")
    first = confirm(plane, first_preview)
    repeated = confirm(plane, first_preview)
    source.write_text(source.read_text().replace("-41.00", "-41.50"), encoding="utf-8")
    corrected = confirm(plane, preview(plane, source, "daily_market", revision="revision-2"))

    assert first.snapshot_id == repeated.snapshot_id and not repeated.created
    assert corrected.snapshot_id != first.snapshot_id and corrected.created
    assert first.curated_path.is_file() and corrected.curated_path.is_file()
    assert len(plane.list_research_datasets()) == 2


def test_same_source_new_revision_gets_distinct_quality_report_without_partial_import(tmp_path: Path) -> None:
    plane = ResearchDataPlane(tmp_path / "root")
    source = external_copy(tmp_path, "crsp_like_daily.csv")
    first = confirm(plane, preview(plane, source, "daily_market", revision="revision-1"))
    second = confirm(plane, preview(plane, source, "daily_market", revision="revision-2"))

    assert first.snapshot_id != second.snapshot_id
    assert first.quality_path != second.quality_path
    assert first.quality_path.is_file() and second.quality_path.is_file()
    assert len(plane.list_research_datasets()) == 2


def test_date_effective_crosswalk_and_overlap_rejection(tmp_path: Path) -> None:
    plane = ResearchDataPlane(tmp_path / "root")
    link_source = external_copy(tmp_path, "crsp_compustat_link.csv")
    item = preview(plane, link_source, "identifier_crosswalk")
    result = confirm(plane, item)
    rows = pq.read_table(result.normalized_paths[0]).to_pylist()
    assert all(row["open_ended"] for row in rows)

    overlapping = tmp_path / "overlap.csv"
    overlapping.write_text(link_source.read_text() + "990001,919999,2022-01-01,,LC,P,2022-01-03T13:00:00Z\n", encoding="utf-8")
    blocked = preview(plane, overlapping, "identifier_crosswalk", revision="overlap")
    assert any(issue.code == "overlapping_link" and issue.severity == "blocking" for issue in blocked.issues)
    with pytest.raises(LocalImportError, match="blocking"):
        confirm(plane, blocked)


def test_fixed_queries_enforce_as_of_limit_columns_and_link_dates(tmp_path: Path) -> None:
    plane = ResearchDataPlane(tmp_path / "root")
    import_all(plane, tmp_path)
    before = plane.run_fixed_query(FixedQueryRequest(manifest_id="fundamentals-as-of", as_of=datetime(2026, 3, 10, tzinfo=UTC), limit=10))
    after = plane.run_fixed_query(FixedQueryRequest(manifest_id="fundamentals-as-of", as_of=datetime(2026, 4, 1, tzinfo=UTC), limit=10))
    linked = plane.run_fixed_query(FixedQueryRequest(manifest_id="linked-market-fundamentals-as-of", as_of=datetime(2026, 7, 1, tzinfo=UTC), limit=10))

    assert [row["gvkey"] for row in before.rows] == ["990001"]
    assert [row["gvkey"] for row in after.rows] == ["990001", "990002"]
    assert linked.rows and all(row["link_effective_to"] is None for row in linked.rows)
    assert tuple(linked.rows[0]) == linked.columns
    assert linked.snapshot_ids and linked.evidence_ids
    with pytest.raises(LocalImportError, match="as_of"):
        plane.run_fixed_query(FixedQueryRequest(manifest_id="daily-market-history", limit=10))
    with pytest.raises(LocalImportError, match="maximum"):
        plane.run_fixed_query(FixedQueryRequest(manifest_id="security-master", limit=1001))
    with pytest.raises((LocalImportError, ValidationError), match="SQL|sql|unknown"):
        plane.run_fixed_query(FixedQueryRequest(manifest_id="select * from daily_market", limit=10))
    with pytest.raises(ValidationError, match="SQL|expression"):
        FixedQueryRequest(manifest_id="daily-market-history", parameters={"sql": "select 1"}, as_of=datetime(2026, 7, 1, tzinfo=UTC))
    assert not hasattr(plane, "execute_sql")


def test_imported_security_master_rows_are_available_through_fixed_query(tmp_path: Path) -> None:
    source = tmp_path / "security-master.csv"
    source.write_text("entity_id,permno,gvkey,cusip,ticker,cik\nsecurity-fictional-1,919001,999001,99190010,C,0000999001\n", encoding="utf-8")
    mapping = LocalMappingManifest(
        manifest_id="synthetic-security-master-v1",
        dataset_kind="security_master",
        target_dataset="security_master",
        key_fields=("entity_id",),
        fields=(
            FieldMapping(source_field="entity_id", target_field="entity_id", data_type="string", nullable=False),
            FieldMapping(source_field="permno", target_field="permno", data_type="string"),
            FieldMapping(source_field="gvkey", target_field="gvkey", data_type="string"),
            FieldMapping(source_field="cusip", target_field="cusip", data_type="string"),
            FieldMapping(source_field="ticker", target_field="ticker", data_type="string"),
            FieldMapping(source_field="cik", target_field="cik", data_type="string"),
        ),
        field_definitions=(FieldDefinition(field_name="entity_id", data_type="string", nullable=False),),
        point_in_time_policy=PointInTimePolicy(observed_at_field="entity_id", available_at_field=None),
    )
    plane = ResearchDataPlane(tmp_path / "root")
    item = plane.preview_local_export(source, provider=provider(), dataset=dataset("security_master"), revision_id="revision-1", rights_state=RightsState.REVIEWED_SYNTHETIC, publication_restriction=PublicationRestriction.SYNTHETIC_ONLY, mapping_manifest=mapping, retrieved_at=RETRIEVED_AT)
    confirm(plane, item)
    result = plane.run_fixed_query(FixedQueryRequest(manifest_id="security-master", parameters={"entity_id": "security-fictional-1"}, limit=10))

    assert len(result.rows) == 1
    assert result.rows[0]["ticker"] == "C"
    assert result.rows[0]["dataset_id"] == "fictional-security_master"


def test_day1_fixed_query_manifest_export_remains_compatible() -> None:
    legacy = reviewed_query_manifests()[0]
    research = fixed_query_manifests()[0]

    assert isinstance(legacy, FixedQueryManifest)
    assert not isinstance(legacy, ResearchFixedQueryManifest)
    assert isinstance(research, ResearchFixedQueryManifest)


def test_workflows_never_open_network_connections(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def prohibited(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise AssertionError("network access attempted")

    monkeypatch.setattr(socket, "socket", prohibited)
    plane = ResearchDataPlane(tmp_path / "root")
    item = preview(plane, external_copy(tmp_path, "crsp_like_daily.csv"), "daily_market")
    confirm(plane, item)
    assert plane.run_fixed_query(FixedQueryRequest(manifest_id="daily-market-history", as_of=datetime(2026, 7, 1, tzinfo=UTC), limit=10)).rows


def test_phase1_cli_preview_confirm_list_query_and_quality(tmp_path: Path) -> None:
    source = external_copy(tmp_path, "crsp_like_daily.csv")
    root = tmp_path / "cli-root"
    environment = os.environ | {"PYTHONPATH": os.pathsep.join((str(REPOSITORY_ROOT), str(REPOSITORY_ROOT / "packages" / "risk_data" / "src"), str(REPOSITORY_ROOT / "packages" / "risk_domain" / "src")))}
    common = ["--data-root", str(root), "--source", str(source), "--provider-id", "fictional-local-provider", "--provider-name", "Fictional Provider", "--profile", "synthetic_local", "--dataset-id", "fictional-daily-market", "--dataset-kind", "daily_market", "--dataset-description", "Synthetic market fixture", "--revision-id", "revision-1", "--rights-state", "reviewed_synthetic", "--publication-restriction", "synthetic_only", "--mapping-manifest", str(FIXTURES / "crsp_like_daily.mapping.json"), "--retrieved-at", "2026-07-22T10:00:00Z"]
    preview_run = subprocess.run([sys.executable, "-m", "risk_data.cli", "preview-local-export", *common], cwd=REPOSITORY_ROOT, env=environment, check=True, capture_output=True, text=True)
    preview_payload = json.loads(preview_run.stdout)
    confirm_run = subprocess.run([sys.executable, "-m", "risk_data.cli", "confirm-local-export", *common, "--confirm", "--preview-digest", preview_payload["preview_digest"], "--source-digest", preview_payload["source"]["source_digest"]], cwd=REPOSITORY_ROOT, env=environment, check=True, capture_output=True, text=True)
    result = json.loads(confirm_run.stdout)
    listed = json.loads(subprocess.run([sys.executable, "-m", "risk_data.cli", "list-research-datasets", "--data-root", str(root)], cwd=REPOSITORY_ROOT, env=environment, check=True, capture_output=True, text=True).stdout)
    queried = json.loads(subprocess.run([sys.executable, "-m", "risk_data.cli", "run-fixed-query", "--data-root", str(root), "--manifest-id", "daily-market-history", "--as-of", "2026-07-01T00:00:00Z", "--limit", "2"], cwd=REPOSITORY_ROOT, env=environment, check=True, capture_output=True, text=True).stdout)
    quality = json.loads(subprocess.run([sys.executable, "-m", "risk_data.cli", "show-data-quality", "--data-root", str(root)], cwd=REPOSITORY_ROOT, env=environment, check=True, capture_output=True, text=True).stdout)

    assert result["created"] and listed[0]["snapshot_id"] == result["snapshot_id"]
    assert len(queried["rows"]) == 2 and queried["manifest_id"] == "daily-market-history"
    assert quality[0]["dataset_id"] == "fictional-daily-market"


def test_repo_fixtures_are_text_only_explicitly_synthetic_and_fictional() -> None:
    files = [path for path in FIXTURES.rglob("*") if path.is_file()]
    allowed_parquet = FIXTURES / "accern-like-events.parquet"
    assert files and all(
        path.suffix in {".csv", ".json"} or path == allowed_parquet for path in files
    )
    combined = "\n".join(
        path.read_text(encoding="utf-8")
        for path in files
        if path.suffix in {".csv", ".json"}
    ).lower()
    assert "fictional" in combined
    binary_files = {
        path
        for path in (REPOSITORY_ROOT / "data").rglob("*")
        if path.suffix in {".parquet", ".duckdb", ".db", ".sqlite"}
    }
    assert binary_files == {allowed_parquet}
