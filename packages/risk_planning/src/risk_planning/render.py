"""Deterministic supervisor-facing planning representations."""

from __future__ import annotations

from .models import PlanningCatalog


def supervisor_one_page_markdown(catalog: PlanningCatalog) -> str:
    """Render a compact, draft-only supervisor page from a validated catalogue."""
    lines = [
        "# Supervisor Review Page — Draft",
        "",
        "Generated deterministically from the validated knowledge-product catalogue. This page is a review aid, not investment advice, and it does not authorize a consequential action.",
        "",
        "## Review queue",
        "",
        "| ID | Product | Review state | Implementation | Blocked by |",
        "| --- | --- | --- | --- | --- |",
    ]
    for product in catalog.review_queue():
        blockers = ", ".join(item.knowledge_product_id for item in catalog.blocking_dependencies(product.knowledge_product_id)) or "none"
        lines.append(f"| {product.knowledge_product_id} | {product.title} | {product.status.value} | {product.implementation_status.value} | {blockers} |")
    lines.extend(
        [
            "",
            "## Supervisor decisions requested",
            "",
            "- Confirm the evidence, explainability, and explicit human-review requirements for the four Day 0 agent role cards.",
            "- Confirm that the demonstration remains bounded to verified local/synthetic evidence and does not imply soft-QA approval.",
            "- Prioritize the Day 1–3 backlog; no decision authorizes provider access, broker connectivity, trading, or automatic rebalancing.",
            "",
            "## Evidence and limitations",
            "",
            "- The catalogue records artifact links, source references, thesis traceability, review history, and implementation status.",
            "- Review decisions are immutable revisions; dependencies are explicit and may block a product from progressing.",
            "- This draft makes no claim of real CRSP, Compustat, WRDS, market-data, or broker access, and no soft-QA pass is claimed.",
            "",
        ]
    )
    return "\n".join(lines)
