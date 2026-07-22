"""Command-line entry points for bounded local data workflows."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

from .evidence import export_evidence
from .pipeline import FIXTURE_CREATED_AT
from .pipeline import ingest_synthetic
from .research import ResearchDataPlane
from .research_contracts import DatasetDefinition, FixedQueryRequest, LocalImportConfirmation, ProviderAccessState, ProviderDefinition, PublicationRestriction, RightsState
from .serialization import manifest_json


def _add_local_import_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--data-root", type=Path, default=None)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--provider-id", required=True)
    parser.add_argument("--provider-name", required=True)
    parser.add_argument("--profile", choices=("synthetic_local", "licensed_local"), required=True)
    parser.add_argument("--dataset-id", required=True)
    parser.add_argument("--dataset-kind", choices=("security_master", "daily_market", "fundamentals_annual", "identifier_crosswalk"), required=True)
    parser.add_argument("--dataset-description", required=True)
    parser.add_argument("--revision-id", required=True)
    parser.add_argument("--rights-state", choices=tuple(item.value for item in RightsState), required=True)
    parser.add_argument("--publication-restriction", choices=tuple(item.value for item in PublicationRestriction), required=True)
    parser.add_argument("--mapping-manifest", type=Path, required=True)
    parser.add_argument("--retrieved-at", required=True)
    parser.add_argument("--retain-raw-source", action="store_true")


def _preview_from_args(args: argparse.Namespace):  # type: ignore[no-untyped-def]
    provider = ProviderDefinition(provider_id=args.provider_id, display_name=args.provider_name, profile=args.profile, access_state=ProviderAccessState.AVAILABLE)
    dataset = DatasetDefinition(dataset_id=args.dataset_id, provider_id=args.provider_id, dataset_kind=args.dataset_kind, description=args.dataset_description)
    return ResearchDataPlane(args.data_root).preview_local_export(args.source, provider=provider, dataset=dataset, revision_id=args.revision_id, rights_state=RightsState(args.rights_state), publication_restriction=PublicationRestriction(args.publication_restriction), mapping_manifest=args.mapping_manifest, retrieved_at=datetime.fromisoformat(args.retrieved_at.replace("Z", "+00:00")), retain_raw_source=args.retain_raw_source)


def main() -> int:
    parser = argparse.ArgumentParser(prog="python -m risk_data.cli")
    subcommands = parser.add_subparsers(dest="command", required=True)
    ingest = subcommands.add_parser("ingest-synthetic", help="write deterministic synthetic artifacts")
    ingest.add_argument("--output", type=Path, required=True, metavar="ROOT")
    evidence = subcommands.add_parser("export-evidence", help="write an immutable synthetic evidence bundle")
    evidence.add_argument("--output", type=Path, required=True, metavar="ROOT")
    evidence.add_argument("--generated-at", default=FIXTURE_CREATED_AT.isoformat(), metavar="TIMESTAMP", help="caller-supplied UTC generation timestamp; deterministic fixture default")
    preview = subcommands.add_parser("preview-local-export", help="validate a local CSV/Parquet export without curating it")
    _add_local_import_arguments(preview)
    confirm = subcommands.add_parser("confirm-local-export", help="explicitly confirm a matching local export preview")
    _add_local_import_arguments(confirm)
    confirm.add_argument("--confirm", action="store_true", required=True)
    confirm.add_argument("--preview-digest", required=True)
    confirm.add_argument("--source-digest", required=True)
    listing = subcommands.add_parser("list-research-datasets", help="list immutable research snapshots")
    listing.add_argument("--data-root", type=Path, default=None)
    query = subcommands.add_parser("run-fixed-query", help="run a fixed manifest with structured parameters")
    query.add_argument("--data-root", type=Path, default=None)
    query.add_argument("--manifest-id", required=True)
    query.add_argument("--as-of")
    query.add_argument("--parameter", action="append", default=[], metavar="NAME=VALUE")
    query.add_argument("--limit", type=int, default=100)
    quality = subcommands.add_parser("show-data-quality", help="show persisted data-quality reports")
    quality.add_argument("--data-root", type=Path, default=None)
    quality.add_argument("--report-id")
    args = parser.parse_args()
    if args.command == "ingest-synthetic":
        result = ingest_synthetic(args.output)
        print(result.snapshot_manifest)
        return 0
    if args.command == "export-evidence":
        print(export_evidence(args.output, args.generated_at))
        return 0
    if args.command == "preview-local-export":
        print(manifest_json(_preview_from_args(args)), end="")
        return 0
    if args.command == "confirm-local-export":
        local_preview = _preview_from_args(args)
        result = ResearchDataPlane(args.data_root).confirm_local_export(local_preview, LocalImportConfirmation(confirm=args.confirm, preview_digest=args.preview_digest, source_digest=args.source_digest))
        print(manifest_json(result), end="")
        return 0
    if args.command == "list-research-datasets":
        print(manifest_json(ResearchDataPlane(args.data_root).list_research_datasets()), end="")
        return 0
    if args.command == "run-fixed-query":
        parameters: dict[str, str] = {}
        for item in args.parameter:
            if "=" not in item:
                parser.error("--parameter values must use NAME=VALUE")
            key, value = item.split("=", 1)
            parameters[key] = value
        as_of = datetime.fromisoformat(args.as_of.replace("Z", "+00:00")) if args.as_of else None
        print(manifest_json(ResearchDataPlane(args.data_root).run_fixed_query(FixedQueryRequest(manifest_id=args.manifest_id, parameters=parameters, as_of=as_of, limit=args.limit))), end="")
        return 0
    if args.command == "show-data-quality":
        print(manifest_json(ResearchDataPlane(args.data_root).show_data_quality(args.report_id)), end="")
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
