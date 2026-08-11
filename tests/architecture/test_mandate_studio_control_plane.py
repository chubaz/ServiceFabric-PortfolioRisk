from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_mandate_studio_has_minimal_library_review_design_and_registry_surfaces() -> None:
    html = read("apps/portfolio-risk-workbench/labs/index.html")
    javascript = read("apps/portfolio-risk-workbench/labs/labs.js")
    css = read("apps/portfolio-risk-workbench/labs/styles.css")

    for identifier in (
        "mandate-studio",
        "mandate-library-list",
        "mandate-review",
        "mandate-design-form",
        "mandate-design-preview",
    ):
        assert f'id="{identifier}"' in html
    for function_name in (
        "initializeMandateStudio",
        "renderMandateLibrary",
        "renderMandateReview",
        "validateSelectedMandate",
        "registerSelectedMandate",
        "prepareMandateDesignPreview",
    ):
        assert f"function {function_name}" in javascript
    assert ".mandate-layout" in css
    assert ".mandate-rule" in css
    assert "Register versions" in javascript
    assert "does not publish them" in javascript
    assert "Structure valid · metric work required" in javascript
    assert "Design capability" in javascript
    assert "bound by exact experiment assignment" in javascript


def test_mandate_api_and_effect_boundaries_are_explicit() -> None:
    server = read("apps/portfolio-risk-workbench/labs/duckdb_server.py")
    runtime = read("apps/portfolio-risk-workbench/labs/mandate_studio.py")
    evaluation = read("docs/thesis/mandate-evaluation-boundary.md")

    for route in (
        "/api/studios/mandates/catalogue",
        "/api/studios/mandates/design-preview",
        "/api/studios/mandates/validate",
        "/api/studios/mandates/register",
    ):
        assert route in server
    assert '"authority": "design_time_only"' in runtime
    assert '"applicable_law": "reference_metadata_only"' in runtime
    assert '"effects": []' in runtime
    assert "A breach episode is not the same as an evaluation row" in evaluation
