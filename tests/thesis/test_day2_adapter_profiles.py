from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from portfolio_risk_thesis.adapters import HistoricalMarketDataAdapter
from portfolio_risk_thesis.contracts import DatasetMetadata


def test_dataset_metadata_supports_both_local_profiles_without_weakening_day1() -> None:
    licensed = DatasetMetadata(
        dataset_id="licensed-crsp-daily",
        revision="revision-1",
        profile="licensed_local",
        publication_state="private_local_only",
        synthetic=False,
        source_paths=("/absolute/private/catalog/crsp-compustat.duckdb",),
        source_digests=("sha256:" + "1" * 64,),
        row_counts=(1,),
        coverage_start=datetime(2024, 1, 1, tzinfo=UTC),
        coverage_end=datetime(2024, 1, 2, tzinfo=UTC),
        required_columns=("permno", "observed_at", "available_at"),
        quality_warnings=("Licensed rows remain private and local.",),
    )
    assert licensed.profile == "licensed_local" and not licensed.synthetic
    with pytest.raises(ValueError, match="DuckDB"):
        HistoricalMarketDataAdapter(licensed)
    with pytest.raises(ValidationError, match="private_local_only"):
        licensed.model_copy(
            update={"publication_state": "synthetic_reviewed"}
        ).model_validate(
            licensed.model_dump(mode="python")
            | {"publication_state": "synthetic_reviewed"}
        )


def test_reviewed_real_manifest_example_contains_no_rows() -> None:
    path = (
        Path(__file__).resolve().parents[2]
        / "examples"
        / "portfolio-risk-thesis"
        / "data"
        / "real_dataset_manifest.example.yaml"
    )
    text = path.read_text(encoding="utf-8")
    assert "profile: licensed_local" in text
    assert "publication_state: private_local_only" in text
    assert "reviewed: true" in text
    assert "EXAMPLE ONLY" in text

