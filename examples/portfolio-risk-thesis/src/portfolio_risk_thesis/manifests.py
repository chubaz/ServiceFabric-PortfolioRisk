"""Reviewed YAML manifest loading and canonical file-digest validation."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import yaml

from .contracts import DatasetMetadata, PortfolioDefinition, ReplaySpecification


class ManifestError(ValueError):
    """A reviewed manifest or its declared immutable source is invalid."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"


def load_yaml(path: Path | str) -> dict[str, Any]:
    manifest_path = Path(path)
    try:
        value = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as error:
        raise ManifestError(f"unable to load manifest {manifest_path}: {error}") from error
    if not isinstance(value, dict):
        raise ManifestError(f"manifest {manifest_path} must contain a mapping")
    return value


def load_dataset_manifest(path: Path | str) -> tuple[DatasetMetadata, DatasetMetadata]:
    manifest_path = Path(path).resolve()
    raw = load_yaml(manifest_path)
    common = {
        "dataset_id": raw["dataset_id"],
        "revision": raw["revision"],
        "profile": raw.get("profile", "synthetic_local"),
        "publication_state": raw.get("publication_state", "synthetic_reviewed"),
        "synthetic": raw["synthetic"],
    }
    results: list[DatasetMetadata] = []
    for key in ("market", "events"):
        item = raw[key]
        source_path = (manifest_path.parent / item["file"]).resolve()
        metadata = DatasetMetadata(
            **common,
            source_paths=(str(source_path),),
            source_digests=(item["digest"],),
            row_counts=(item["row_count"],),
            coverage_start=item["coverage"]["start"],
            coverage_end=item["coverage"]["end"],
            required_columns=tuple(item["required_columns"]),
            quality_warnings=tuple(item.get("quality_warnings", ())),
        )
        if not source_path.is_file():
            raise ManifestError(f"declared source is missing: {source_path}")
        actual = sha256_file(source_path)
        if actual != metadata.source_digests[0]:
            raise ManifestError(f"digest mismatch for {source_path}: expected {metadata.source_digests[0]}, got {actual}")
        results.append(metadata)
    return results[0], results[1]


def load_portfolio(path: Path | str) -> PortfolioDefinition:
    return PortfolioDefinition.model_validate(load_yaml(path))


def load_experiment(path: Path | str, portfolio_id: str) -> ReplaySpecification:
    raw = load_yaml(path)
    if portfolio_id not in raw["portfolio_ids"]:
        raise ManifestError(f"portfolio {portfolio_id} is not declared by the experiment")
    return ReplaySpecification(
        experiment_id=raw["experiment_id"],
        portfolio_id=portfolio_id,
        dataset_revision=raw["dataset_revision"],
        start=raw["start"],
        end=raw["end"],
        cadence=raw["cadence"],
        review_time=raw["review_time"],
        lookback=raw["lookback"],
        no_look_ahead_rule=raw["no_look_ahead_rule"],
        deterministic_seed=raw["fixture_seed"],
    )
