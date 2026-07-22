"""Typed Workbench adapter for the reviewed Wave 1B data services."""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Iterable

import yaml

from risk_data import (
    FixedQueryManifest,
    PortfolioConfirmationRequest,
    PortfolioConfirmationResult,
    PortfolioInputFormat,
    PortfolioInputPreview,
    PortfolioInputService,
    ProviderCatalogueEntry,
    SnapshotComparison,
    provider_catalogue,
    reviewed_query_manifests,
)
from risk_data.portfolio import MAX_INPUT_BYTES
from risk_domain import DatasetSnapshot, MarketObservation, PortfolioSnapshot, QualityFlag


PREVIEW_ID = re.compile(r"^sha256:[a-f0-9]{64}$")
SNAPSHOT_ID = re.compile(r"^portfolio-[a-f0-9]{64}$")


class WorkspaceRecordNotFound(LookupError):
    """A requested immutable workspace record does not exist."""


def input_format(filename: str) -> PortfolioInputFormat:
    lowered = filename.lower()
    if lowered.endswith(".csv"):
        return PortfolioInputFormat.CSV
    if lowered.endswith((".yaml", ".yml")):
        return PortfolioInputFormat.YAML
    raise ValueError("Only CSV and YAML files are accepted. No input was retained.")


def parse_as_of(value: str) -> datetime | None:
    if not value.strip():
        return None
    try:
        return datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError("CSV as-of must be an ISO-8601 timezone-aware timestamp.") from error


class PortfolioWorkspace:
    """Bind HTTP presentation to typed data contracts without reimplementing them."""

    def __init__(self, data_root: Path) -> None:
        self.data_root = data_root
        self.inputs = PortfolioInputService(data_root)

    def create_preview(
        self,
        content: bytes,
        filename: str,
        *,
        profile: str = "personal_portfolio",
        base_currency: str | None = None,
        as_of: str = "",
    ) -> PortfolioInputPreview:
        selected_format = input_format(filename)
        if selected_format is PortfolioInputFormat.YAML:
            try:
                payload = yaml.safe_load(content)
            except yaml.YAMLError:
                payload = None
            if isinstance(payload, dict) and payload.get("profile") != "personal_portfolio":
                raise ValueError("portfolio input is available only in the personal_portfolio profile")
        return self.inputs.preview(
            content,
            selected_format,
            profile=profile,
            base_currency=base_currency or None,
            as_of=parse_as_of(as_of),
        )

    def get_preview(self, preview_id: str) -> PortfolioInputPreview:
        if not PREVIEW_ID.fullmatch(preview_id):
            raise WorkspaceRecordNotFound("portfolio preview not found")
        path = self.data_root / "portfolio-previews" / f"{preview_id.removeprefix('sha256:')}.json"
        if not path.is_file():
            raise WorkspaceRecordNotFound("portfolio preview not found")
        return PortfolioInputPreview.model_validate_json(path.read_text(encoding="utf-8"))

    def snapshots(self) -> tuple[PortfolioSnapshot, ...]:
        directory = self.data_root / "portfolio-snapshots"
        values = tuple(PortfolioSnapshot.model_validate_json(path.read_text(encoding="utf-8")) for path in sorted(directory.glob("*.json"))) if directory.is_dir() else ()
        return tuple(sorted(values, key=lambda item: (item.as_of, item.snapshot_id)))

    def get_snapshot(self, snapshot_id: str) -> PortfolioSnapshot:
        if not SNAPSHOT_ID.fullmatch(snapshot_id):
            raise WorkspaceRecordNotFound("portfolio snapshot not found")
        path = self.data_root / "portfolio-snapshots" / f"{snapshot_id}.json"
        if not path.is_file():
            raise WorkspaceRecordNotFound("portfolio snapshot not found")
        return PortfolioSnapshot.model_validate_json(path.read_text(encoding="utf-8"))

    def confirm(
        self,
        preview_id: str,
        *,
        preview_digest: str,
        confirm: bool,
        observations: Iterable[MarketObservation],
    ) -> tuple[PortfolioConfirmationResult, PortfolioSnapshot]:
        preview = self.get_preview(preview_id)
        request = PortfolioConfirmationRequest(confirm=confirm, preview_digest=preview_digest)
        as_of = preview.document.as_of if preview.document is not None else None
        selected: dict[str, MarketObservation] = {}
        if as_of is not None:
            for observation in observations:
                if observation.observed_at > as_of or observation.price is None or QualityFlag.COMPLETE not in observation.quality_flags:
                    continue
                current = selected.get(observation.instrument_id)
                if current is None or observation.observed_at > current.observed_at:
                    selected[observation.instrument_id] = observation
        result = self.inputs.confirm(preview, request, selected)
        return result, self.get_snapshot(result.snapshot_id)

    def compare(self, left_snapshot_id: str, right_snapshot_id: str) -> SnapshotComparison:
        return self.inputs.compare(self.get_snapshot(left_snapshot_id), self.get_snapshot(right_snapshot_id))

    def providers(self) -> tuple[ProviderCatalogueEntry, ...]:
        return provider_catalogue()

    def query_manifests(self) -> tuple[FixedQueryManifest, ...]:
        return reviewed_query_manifests()

    def dataset_snapshot(self) -> DatasetSnapshot | None:
        path = self.data_root / "manifests" / "dataset-snapshot.json"
        return DatasetSnapshot.model_validate_json(path.read_text(encoding="utf-8")) if path.is_file() else None


def provider_views(providers: tuple[ProviderCatalogueEntry, ...], manifests: tuple[FixedQueryManifest, ...]) -> tuple[dict[str, object], ...]:
    """Create display-only joins over immutable typed catalogue records."""
    by_source: dict[str, list[str]] = {}
    for manifest in manifests:
        by_source.setdefault(manifest.source_id, []).append(manifest.manifest_id)
    return tuple(
        entry.model_dump(mode="json") | {"query_manifest_ids": tuple(sorted(by_source.get(entry.provider_id, ())))}
        for entry in providers
    )


__all__ = ["MAX_INPUT_BYTES", "PortfolioWorkspace", "WorkspaceRecordNotFound", "provider_views"]
