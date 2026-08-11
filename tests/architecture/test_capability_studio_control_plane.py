from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_capability_studio_has_minimal_design_library_apply_and_review_surfaces() -> None:
    html = read("apps/portfolio-risk-workbench/labs/index.html")
    javascript = read("apps/portfolio-risk-workbench/labs/labs.js")
    css = read("apps/portfolio-risk-workbench/labs/styles.css")

    for element in (
        'id="capability-studio"',
        'id="capability-chat"',
        'id="capability-blueprint"',
        'id="capability-proposal-list"',
        'id="capability-run-review"',
        'id="capability-library-body"',
        'id="capability-session-select"',
        'id="capability-tests-view"',
        'id="capability-description-view"',
        'id="capability-description-content"',
        'id="capability-package-detail"',
    ):
        assert element in html
    for decision in ("reuse", "compose", "improve", "new", "blocked"):
        assert f'data-capability-decision="{decision}"' in html
    for level in ("Level 1 · Result", "Level 2", "Level 3"):
        assert level in javascript
    assert "function assessCapabilityRequirement" in javascript
    assert "function concludeCapabilityDesign" in javascript
    assert "function approveCapabilityDraft" in javascript
    assert "function deleteCapabilityProposal" in javascript
    assert "function sendCapabilityDesignToStudio" in javascript
    assert "function resumeCapabilityDesignSession" in javascript
    assert "function discussCapabilityDependency" in javascript
    assert "function transitionCapabilityProposal" in javascript
    assert "Proposal returned to design. Update the requirement and assess it again." in javascript
    assert "function renderCapabilityRun" in javascript
    assert "function renderCapabilityInspector" in javascript
    assert "function renderCapabilityDescription" in javascript
    assert "function renderCapabilityPackageDetail" in javascript
    assert "function renderCapabilityHostDetail" in javascript
    assert 'data-capability-host' in javascript
    assert 'class="capability-human-narrative"' in javascript
    assert 'class="capability-human-grid"' not in javascript
    for view in ("contract", "script", "human"):
        assert f'data-capability-description="{view}"' in html
    assert ".capability-design-surface" in css
    assert ".capability-library-table" in css
    professional = read("apps/portfolio-risk-workbench/labs/professional.css")
    assert ".capability-blueprint .capability-codex-brief pre" in professional
    assert "color: #e7eef5" in professional
    assert "Stable work surface" in professional
    assert "height: 560px" in professional


def test_capability_studio_api_and_canonical_boundary_are_explicit() -> None:
    server = read("apps/portfolio-risk-workbench/labs/duckdb_server.py")
    runtime = read("apps/portfolio-risk-workbench/labs/capability_studio.py")
    javascript = read("apps/portfolio-risk-workbench/labs/labs.js")

    for route in (
        "/api/studios/capabilities/catalogue",
        "/api/studios/capabilities/assess",
        "/api/studios/capabilities/proposals",
        "/api/studios/capabilities/blueprints",
        "/api/studios/design-proposals",
        "/api/studios/capabilities/runs",
        "/api/studios/capabilities/design-sessions",
    ):
        assert route in server
    assert "CapabilityInvocationService" in runtime
    assert "CapabilityRegistry" in runtime
    assert "CapabilityDefinition" in runtime
    assert 'CAPABILITY_BRIDGE_VERSION = "bridge-v2"' in runtime
    assert "exact_first_explicit_compatible_substitution" in runtime
    assert '"external_effects": "disabled_placeholder"' in runtime
    assert '"licensed_source_database": "read_only"' in runtime
    assert "write licensed/source databases" in runtime
    assert "Luna unavailable · deterministic result" in javascript
    assert "The test case could not run." in javascript
    assert "Implementation required" in javascript
    assert "Nothing has been added to the backlog." in javascript
    assert "data-capability-quiz-option" in javascript
    assert "agent.schema.adaptation" in runtime
    assert "blocks_build" in runtime


def test_capability_studio_documents_thesis_role_and_handoff() -> None:
    plan = read("docs/workplans/platform-development/studio-foundation-2-capability-studio.md")
    thesis = read("docs/thesis/capabilities/README.md")
    codex = read("docs/workplans/platform-development/studio-codex-gateway.md")

    assert "reuse" in plan.casefold()
    assert "three review levels" in plan.casefold()
    assert "Studio-Codex" in plan
    assert "research questions" in thesis.casefold()
    assert "not canonical runtime contracts" in thesis.casefold()
    assert "thread/start" in codex
    assert "instructionSources" in codex
    assert "workspaceWrite" in codex
