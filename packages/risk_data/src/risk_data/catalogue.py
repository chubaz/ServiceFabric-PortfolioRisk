"""Reviewed Day 1 provider catalogue and fixed query-manifest contracts."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ProviderCatalogueEntry(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    provider_id: str
    enabled: bool
    access_state: Literal["available", "unavailable"]
    rights_state: Literal["reviewed_synthetic", "licensed_restricted", "unavailable"]
    data_zone: Literal["local_synthetic", "external_local"]
    credential_secret_ref: str | None = Field(default=None, pattern=r"^secret-ref:[a-z0-9/_-]+$")
    provenance: str
    freshness: str
    quality_flags: tuple[str, ...]
    publication_restriction: str


class FixedQueryManifest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    manifest_id: str
    source_id: str
    view_name: Literal["market_prices", "fundamentals", "latest_market_prices", "latest_fundamentals"]
    requested_fields: tuple[str, ...]
    rights_state: str
    access_state: str
    data_zone: str
    provenance: str
    freshness: str
    quality_flags: tuple[str, ...]
    publication_restriction: str


def provider_catalogue() -> tuple[ProviderCatalogueEntry, ...]:
    local = (
        ProviderCatalogueEntry(provider_id="local-synthetic-market-data", enabled=True, access_state="available", rights_state="reviewed_synthetic", data_zone="local_synthetic", provenance="reviewed local synthetic fixture", freshness="fixture-dated", quality_flags=("synthetic",), publication_restriction="Synthetic-only; label synthetic when presented."),
        ProviderCatalogueEntry(provider_id="local-synthetic-fundamentals", enabled=True, access_state="available", rights_state="reviewed_synthetic", data_zone="local_synthetic", provenance="reviewed local synthetic fixture", freshness="fixture-dated", quality_flags=("synthetic",), publication_restriction="Synthetic-only; label synthetic when presented."),
    )
    external = ("wrds", "crsp", "compustat", "ravenpack", "accern", "bloomberg")
    return local + tuple(ProviderCatalogueEntry(provider_id=provider, enabled=False, access_state="unavailable", rights_state="licensed_restricted", data_zone="external_local", credential_secret_ref=f"secret-ref:provider/{provider}", provenance="external provider is not contacted in Day 1", freshness="unavailable", quality_flags=("unavailable", "rights_restricted"), publication_restriction="Licensed or personal material must remain outside Git and public outputs.") for provider in external)


def reviewed_query_manifests() -> tuple[FixedQueryManifest, ...]:
    fields = {
        "market_prices": ("instrument_id", "observed_at", "price", "currency", "synthetic", "quality_flags"),
        "fundamentals": ("instrument_id", "metric", "observed_at", "value", "unit", "synthetic", "quality_flags"),
        "latest_market_prices": ("instrument_id", "observed_at", "price", "currency", "synthetic", "quality_flags"),
        "latest_fundamentals": ("instrument_id", "metric", "observed_at", "value", "unit", "synthetic", "quality_flags"),
    }
    return tuple(FixedQueryManifest(manifest_id=f"local-synthetic-{view}", source_id="local-synthetic-market-data" if "market" in view else "local-synthetic-fundamentals", view_name=view, requested_fields=fields[view], rights_state="reviewed_synthetic", access_state="available", data_zone="local_synthetic", provenance="reviewed fixed local DuckDB view", freshness="fixture-dated", quality_flags=("synthetic",), publication_restriction="Synthetic-only; label synthetic when presented.") for view in fields)
