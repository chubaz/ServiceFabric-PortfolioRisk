"""Deterministic YAML catalogue loading for knowledge products."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from .models import KnowledgeProduct, PlanningCatalog


def load_catalog(seed_directory: Path) -> PlanningCatalog:
    """Load lexically ordered YAML seed objects into a validated catalogue."""
    products: list[KnowledgeProduct] = []
    for path in sorted(seed_directory.glob("*.yaml")):
        payload: Any = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError(f"{path} must contain one YAML mapping")
        products.append(KnowledgeProduct.model_validate(payload))
    return PlanningCatalog(knowledge_products=tuple(products))


def load_seed_catalog(repository_root: Path) -> PlanningCatalog:
    """Load the repository's reviewed Day 0 knowledge-product seeds."""
    return load_catalog(repository_root / "seed" / "knowledge-products")


def load_day1_seed_catalog(repository_root: Path) -> PlanningCatalog:
    """Load the repository's reviewed Day 1 knowledge-product seeds."""
    return load_catalog(repository_root / "seed" / "knowledge-products" / "day-1")
