#!/usr/bin/env python3
"""Run the deterministic, local-only Day 2–3 Phase 1 data-plane journey."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import duckdb
from pydantic import ValidationError
from risk_data import (
    CrosswalkSnapshot,
    DatasetDefinition,
    FixedQueryRequest,
    LocalImportConfirmation,
    LocalImportError,
    ProviderAccessState,
    ProviderDefinition,
    PublicationRestriction,
    ResearchDataPlane,
    RightsState,
    fixed_query_manifests,
    provider_catalogue,
)
from risk_data.pipeline import resolve_data_root


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_ROOT = REPOSITORY_ROOT / "data" / "fixtures" / "synthetic" / "day23"
OUTPUT_DIRECTORY_NAME = "day23-phase1"
DATA_PLANE_DIRECTORY_NAME = "data-plane"
RETRIEVED_AT = datetime(2026, 7, 22, 10, 0, tzinfo=UTC)
QUERY_AS_OF = datetime(2026, 7, 1, 0, 0, tzinfo=UTC)
FUNDAMENTALS_BEFORE = datetime(2026, 3, 10, 0, 0, tzinfo=UTC)
FUNDAMENTALS_AFTER = datetime(2026, 4, 1, 0, 0, tzinfo=UTC)
ARTIFACT_NAMES = {
    "provider_register": "provider-register.json",
    "import_previews": "import-previews.json",
    "import_confirmations": "import-confirmations.json",
    "dataset_snapshots": "dataset-snapshots.json",
    "quality_reports": "quality-reports.json",
    "identifier_crosswalk": "identifier-crosswalk.json",
    "fixed_query_results": "fixed-query-results.json",
    "point_in_time_proof": "point-in-time-proof.json",
    "evidence_manifest": "evidence-manifest.json",
}
IMPORTS = (
    {
        "source": "crsp_like_daily.csv",
        "mapping": "crsp_like_daily.mapping.json",
        "dataset_id": "synthetic-crsp-like-daily",
        "dataset_kind": "daily_market",
        "description": "Explicitly synthetic CRSP-like daily market export",
        "revision_id": "revision-2026-07-22",
    },
    {
        "source": "compustat_like_annual.csv",
        "mapping": "compustat_like_annual.mapping.json",
        "dataset_id": "synthetic-compustat-like-annual",
        "dataset_kind": "fundamentals_annual",
        "description": "Explicitly synthetic Compustat-like annual fundamentals export",
        "revision_id": "revision-2026-07-22",
    },
    {
        "source": "crsp_compustat_link.csv",
        "mapping": "crsp_compustat_link.mapping.json",
        "dataset_id": "synthetic-crsp-compustat-link",
        "dataset_kind": "identifier_crosswalk",
        "description": "Explicitly synthetic date-effective CRSP-Compustat-like link export",
        "revision_id": "revision-2026-07-22",
    },
)
REQUIRED_CURATED_VIEWS = {
    "security_master",
    "daily_market",
    "fundamentals_annual",
    "identifier_crosswalk",
    "data_quality_summary",
    "latest_available_market",
    "latest_available_fundamentals",
    "linked_market_fundamentals",
}


def _encoded(value: object) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _write_stable(path: Path, content: bytes) -> Path:
    if path.exists():
        if path.read_bytes() != content:
            raise FileExistsError(f"immutable Phase 1 artifact differs from existing evidence: {path}")
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path


def _portable(value: object, output_directory: Path) -> object:
    if hasattr(value, "model_dump"):
        return _portable(value.model_dump(mode="json"), output_directory)  # type: ignore[union-attr]
    if isinstance(value, dict):
        return {str(key): _portable(item, output_directory) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_portable(item, output_directory) for item in value]
    if isinstance(value, Path):
        value = str(value)
    if isinstance(value, str):
        candidate = Path(value)
        if candidate.is_absolute():
            try:
                return candidate.relative_to(output_directory).as_posix()
            except ValueError:
                try:
                    return "fixture://day23/" + candidate.relative_to(FIXTURE_ROOT).as_posix()
                except ValueError:
                    return value
    return value


def _provider() -> ProviderDefinition:
    return ProviderDefinition(
        provider_id="fictional-local-provider",
        display_name="Fictional Local Provider",
        profile="synthetic_local",
        access_state=ProviderAccessState.AVAILABLE,
        network_enabled=False,
    )


def _preview(plane: ResearchDataPlane, specification: dict[str, str]) -> object:
    return plane.preview_local_export(
        FIXTURE_ROOT / specification["source"],
        provider=_provider(),
        dataset=DatasetDefinition(
            dataset_id=specification["dataset_id"],
            provider_id="fictional-local-provider",
            dataset_kind=specification["dataset_kind"],
            description=specification["description"],
        ),
        revision_id=specification["revision_id"],
        rights_state=RightsState.REVIEWED_SYNTHETIC,
        publication_restriction=PublicationRestriction.SYNTHETIC_ONLY,
        mapping_manifest=FIXTURE_ROOT / specification["mapping"],
        retrieved_at=RETRIEVED_AT,
        retain_raw_source=False,
    )


def _query_requests() -> tuple[FixedQueryRequest, ...]:
    return (
        FixedQueryRequest(manifest_id="security-master", limit=100),
        FixedQueryRequest(
            manifest_id="daily-market-history",
            as_of=QUERY_AS_OF,
            limit=100,
        ),
        FixedQueryRequest(
            manifest_id="fundamentals-as-of",
            as_of=FUNDAMENTALS_AFTER,
            limit=100,
        ),
        FixedQueryRequest(
            manifest_id="linked-market-fundamentals-as-of",
            as_of=QUERY_AS_OF,
            limit=100,
        ),
        FixedQueryRequest(manifest_id="data-quality-summary", limit=100),
    )


def execute_phase1_journey(output_root: Path | str | None = None) -> dict[str, Any]:
    """Exercise every Phase 1 seam without provider, SQL, or portfolio effects."""
    external_root = resolve_data_root(output_root)
    output_directory = external_root / OUTPUT_DIRECTORY_NAME
    plane = ResearchDataPlane(output_directory / DATA_PLANE_DIRECTORY_NAME)

    # Preview all three explicit local exports before any confirmation mutates
    # the governed data plane.
    previews = tuple(_preview(plane, specification) for specification in IMPORTS)
    if any(item.has_blocking_issues for item in previews):
        raise LocalImportError("reviewed Phase 1 fixture unexpectedly has blocking preview issues")

    confirmations = tuple(
        plane.confirm_local_export(
            preview,
            LocalImportConfirmation(
                confirm=True,
                preview_digest=preview.preview_digest,
                source_digest=preview.source.source_digest,
            ),
        )
        for preview in previews
    )
    snapshots = plane.list_research_datasets()
    quality_reports = plane.show_data_quality()
    latest_snapshot = next(
        item for item in snapshots if item.snapshot_id == confirmations[-1].snapshot_id
    )

    with duckdb.connect(str(latest_snapshot.curated_path), read_only=True) as connection:
        curated_views = {
            row[0]
            for row in connection.execute(
                "SELECT table_name FROM information_schema.views WHERE table_schema = 'main'"
            ).fetchall()
        }
    if not REQUIRED_CURATED_VIEWS <= curated_views:
        raise RuntimeError("the immutable curated snapshot is missing reviewed Phase 1 views")

    crosswalk_ids = latest_snapshot.crosswalk_snapshot_ids
    if len(crosswalk_ids) != 1:
        raise RuntimeError("the reviewed Phase 1 journey requires exactly one crosswalk snapshot")
    crosswalk_path = (
        plane.data_root / "manifests" / "crosswalks" / f"{crosswalk_ids[0]}.json"
    )
    crosswalk = CrosswalkSnapshot.model_validate_json(crosswalk_path.read_text(encoding="utf-8"))
    if any(
        identifier.identifier_type == "ticker"
        for record in crosswalk.records
        for identifier in (record.source_identifier, record.target_identifier)
    ):
        raise RuntimeError("ticker-based guessed matching is prohibited")

    query_results = tuple(plane.run_fixed_query(request) for request in _query_requests())
    expected_manifests = {item.manifest_id for item in fixed_query_manifests()}
    if {item.manifest_id for item in query_results} != expected_manifests:
        raise RuntimeError("not every reviewed fixed query manifest was executed")

    before = plane.run_fixed_query(
        FixedQueryRequest(
            manifest_id="fundamentals-as-of",
            as_of=FUNDAMENTALS_BEFORE,
            limit=100,
        )
    )
    after = plane.run_fixed_query(
        FixedQueryRequest(
            manifest_id="fundamentals-as-of",
            as_of=FUNDAMENTALS_AFTER,
            limit=100,
        )
    )
    before_ids = {str(row["gvkey"]) for row in before.rows}
    after_ids = {str(row["gvkey"]) for row in after.rows}
    if before_ids != {"990001"} or after_ids != {"990001", "990002"}:
        raise RuntimeError("available_at point-in-time exclusion proof failed")

    arbitrary_sql_rejections: list[str] = []
    try:
        FixedQueryRequest(
            manifest_id="daily-market-history",
            parameters={"sql": "select * from daily_market"},
            as_of=QUERY_AS_OF,
        )
    except ValidationError as error:
        arbitrary_sql_rejections.append(str(error.errors()[0]["msg"]))
    else:
        raise RuntimeError("typed fixed-query input unexpectedly accepted SQL")
    try:
        plane.run_fixed_query(
            FixedQueryRequest(manifest_id="select * from daily_market", limit=1)
        )
    except LocalImportError as error:
        arbitrary_sql_rejections.append(str(error))
    else:
        raise RuntimeError("unknown fixed-query manifest unexpectedly executed")

    catalogue = provider_catalogue()
    external_providers = tuple(
        item
        for item in catalogue
        if item.provider_id in {"wrds", "crsp", "compustat", "ravenpack", "accern", "bloomberg"}
    )
    if not external_providers or any(
        item.enabled or item.access_state != "unavailable" for item in external_providers
    ):
        raise RuntimeError("an external network provider is not explicitly disabled")

    preview_records = [
        {
            "dataset_id": preview.dataset.dataset_id,
            "dataset_kind": preview.dataset.dataset_kind,
            "provider_id": preview.provider.provider_id,
            "network_enabled": preview.provider.network_enabled,
            "rights_state": preview.rights_state.value,
            "publication_restriction": preview.publication_restriction.value,
            "source": f"fixture://day23/{specification['source']}",
            "source_digest": preview.source.source_digest,
            "source_schema": _portable(preview.source_schema, output_directory),
            "mapping_manifest": _portable(preview.mapping_manifest, output_directory),
            "mapping_digest": preview.mapping_digest,
            "row_count": preview.row_count,
            "accepted_row_count": preview.accepted_row_count,
            "rejected_row_count": preview.rejected_row_count,
            "issues": _portable(preview.issues, output_directory),
            "quality_report_id": preview.quality_report.report_id,
            "preview_digest": preview.preview_digest,
            "retain_raw_source": preview.retain_raw_source,
        }
        for specification, preview in zip(IMPORTS, previews, strict=True)
    ]
    confirmation_records = [
        {
            **_portable(result, output_directory),
            # Canonical evidence records the confirmed outcome, not whether
            # this invocation reused the immutable receipt.
            "created": True,
        }
        for result in confirmations
    ]

    return {
        "output_directory": output_directory,
        "artifacts": {
            "provider_register": {
                "phase": "D23-PHASE-1",
                "network_access": "external-disabled; local-loopback-runtime-only",
                "providers": _portable(catalogue, output_directory),
                "phase_1_local_provider": _portable(_provider(), output_directory),
                "external_provider_ids": [item.provider_id for item in external_providers],
                "external_network_providers_disabled": True,
                "effects": [],
            },
            "import_previews": {
                "phase": "D23-PHASE-1",
                "preview_only": True,
                "previews": preview_records,
                "effects": [],
            },
            "import_confirmations": {
                "phase": "D23-PHASE-1",
                "explicit_confirmations": confirmation_records,
                "confirmation_count": len(confirmation_records),
                "effects": [],
            },
            "dataset_snapshots": {
                "phase": "D23-PHASE-1",
                "immutable": True,
                "snapshots": _portable(snapshots, output_directory),
                "normalized_parquet_paths": sorted(
                    {
                        str(path)
                        for result in confirmation_records
                        for path in result["normalized_paths"]
                        if str(path).endswith(".parquet")
                    }
                ),
                "curated_duckdb_paths": sorted(
                    {str(result["curated_path"]) for result in confirmation_records}
                ),
                "latest_snapshot_id": latest_snapshot.snapshot_id,
                "latest_curated_path": _portable(
                    latest_snapshot.curated_path,
                    output_directory,
                ),
                "latest_curated_views": sorted(curated_views),
                "effects": [],
            },
            "quality_reports": {
                "phase": "D23-PHASE-1",
                "reports": _portable(quality_reports, output_directory),
                "all_non_blocking": all(not report.blocking for report in quality_reports),
                "effects": [],
            },
            "identifier_crosswalk": {
                "phase": "D23-PHASE-1",
                "crosswalk": _portable(crosswalk, output_directory),
                "matching_policy": "explicit-date-effective-permno-gvkey-links-only",
                "ticker_matching_used": False,
                "guessed_matches": [],
                "effects": [],
            },
            "fixed_query_results": {
                "phase": "D23-PHASE-1",
                "query_manifests": _portable(fixed_query_manifests(), output_directory),
                "results": _portable(query_results, output_directory),
                "arbitrary_sql_available": False,
                "arbitrary_sql_rejections": arbitrary_sql_rejections,
                "effects": [],
            },
            "point_in_time_proof": {
                "phase": "D23-PHASE-1",
                "rule": "available_at <= as_of",
                "before": _portable(before, output_directory),
                "after": _portable(after, output_directory),
                "excluded_before_as_of": {
                    "gvkey": "990002",
                    "available_at": "2026-03-16T13:00:00Z",
                    "as_of": FUNDAMENTALS_BEFORE.isoformat().replace("+00:00", "Z"),
                },
                "no_look_ahead": before_ids == {"990001"} and "990002" in after_ids,
                "effects": [],
            },
        },
        "effects": (),
    }


def write_phase1_artifacts(result: dict[str, Any]) -> dict[str, Path]:
    """Write or verify the nine immutable Phase 1 evidence artifacts."""
    output_directory = Path(result["output_directory"])
    artifacts = result["artifacts"]
    paths: dict[str, Path] = {}
    for key, name in ARTIFACT_NAMES.items():
        if key == "evidence_manifest":
            continue
        paths[key] = _write_stable(output_directory / name, _encoded(artifacts[key]))

    manifest = {
        "phase": "D23-PHASE-1",
        "deterministic": True,
        "external_network_providers_disabled": True,
        "arbitrary_sql_available": False,
        "effects": [],
        "artifacts": [
            {"path": path.name, "digest": _digest(path)}
            for path in sorted(paths.values(), key=lambda item: item.name)
        ],
    }
    paths["evidence_manifest"] = _write_stable(
        output_directory / ARTIFACT_NAMES["evidence_manifest"],
        _encoded(manifest),
    )
    return paths


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-root",
        type=Path,
        default=os.environ.get("PORTFOLIO_RISK_DATA_ROOT"),
        help="External data root (defaults to PORTFOLIO_RISK_DATA_ROOT).",
    )
    args = parser.parse_args()
    result = execute_phase1_journey(args.output_root)
    paths = write_phase1_artifacts(result)
    for key in ARTIFACT_NAMES:
        print(f"{key}: {paths[key]}")
    print("D23 Phase 1 deterministic demo: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
