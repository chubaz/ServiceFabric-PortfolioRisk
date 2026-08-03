"""Discover existing PortfolioRisk definitions as bounded registry projections."""

from __future__ import annotations

import ast
import hashlib
import inspect
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable

from agent_studio import _ensure_workspace_packages

_ensure_workspace_packages()

LABS_ROOT = Path(__file__).resolve().parent
REPOSITORY_ROOT = LABS_ROOT.parents[2]
THESIS_SOURCE_ROOT = REPOSITORY_ROOT / "examples" / "portfolio-risk-thesis" / "src"
if str(THESIS_SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(THESIS_SOURCE_ROOT))

from portfolio_risk_thesis.day3.treatments import definitions as day3_definitions  # noqa: E402
from portfolio_risk_thesis.day4.manifest import load_day4_manifest  # noqa: E402
from portfolio_risk_thesis.day4.report import (  # noqa: E402
    render_dashboard as render_day4_dashboard,
    render_preliminary_results,
)
from risk_agents.roles import ACTIVE_AGENT_ROLE_IDS, AGENT_ROLES  # noqa: E402
from risk_analytics.monitoring_reports import render_monitoring_report  # noqa: E402
from risk_analytics.reports import render_report  # noqa: E402
from risk_capabilities import CAPABILITY_DESCRIPTORS  # noqa: E402
from risk_capabilities.registry import DEFAULT_CAPABILITY_REGISTRY  # noqa: E402
from risk_registry import (  # noqa: E402
    LIFECYCLE_TRANSITIONS,
    AssetKind,
    Compatibility,
    LocalRegistryStore,
    Provenance,
    RegistryIdentity,
    RegistryProjection,
    RegistryRelationship,
    SourceReference,
)

DEFAULT_REGISTRY_ROOT = Path(
    os.environ.get(
        "PORTFOLIO_RISK_REGISTRY_ROOT",
        Path.home() / ".servicefabric-portfolio-risk" / "registry-v1",
    )
).expanduser()
ADAPTER_ID = "portfolio-risk.registry-source-adapter/v1"
ADAPTER_DIGEST = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


@lru_cache(maxsize=1)
def _repository_commit() -> str:
    configured = os.environ.get("PORTFOLIO_RISK_REPOSITORY_COMMIT")
    if configured:
        return configured
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=REPOSITORY_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def registry_store() -> LocalRegistryStore:
    """Resolve on demand so tests can safely override the environment."""

    root = Path(os.environ.get("PORTFOLIO_RISK_REGISTRY_ROOT", DEFAULT_REGISTRY_ROOT))
    return LocalRegistryStore(root)


def _canonical_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value)).hexdigest()


def _source_path(relative: str, anchor: str | None = None) -> str:
    return f"{relative}{f'#{anchor}' if anchor else ''}"


def _projection(
    *,
    kind: AssetKind,
    asset_id: str,
    version: str | None,
    display_name: str,
    summary: str,
    source_reference: str,
    source_value: Any,
    source_type: str,
    source_file: str,
    source_namespace: str,
    source_contract: str,
    native_version: str | None = None,
    canonical: bool = True,
    compatibility_status: str = "unknown",
    tags: Iterable[str] = (),
    lineage: Iterable[str] = (),
    relationships: Iterable[tuple[str, str]] = (),
    discovered_at: datetime,
) -> RegistryProjection:
    definition_digest = _digest(source_value)
    registry_version = (
        f"{version}+adapter.{ADAPTER_DIGEST[:8]}"
        if version
        else hashlib.sha256(
            f"{definition_digest}:{ADAPTER_DIGEST}".encode("utf-8")
        ).hexdigest()[:12]
    )
    source_digest = hashlib.sha256(
        (REPOSITORY_ROOT / source_file).read_bytes()
    ).hexdigest()
    return RegistryProjection(
        identity=RegistryIdentity(
            kind=kind,
            namespace=source_namespace,
            asset_id=asset_id,
            version=registry_version,
        ),
        display_name=display_name,
        summary=summary,
        source=SourceReference(
            source_type=source_type,
            source_reference=source_reference,
            source_digest=source_digest,
            definition_digest=definition_digest,
            native_version=native_version,
            canonical=canonical,
            adapter_id=ADAPTER_ID,
            adapter_digest=ADAPTER_DIGEST,
        ),
        provenance=Provenance(
            discovered_by=ADAPTER_ID,
            discovered_at=discovered_at,
            repository_commit=_repository_commit(),
            notes=("Indexed metadata only; the referenced source remains authoritative.",),
        ),
        compatibility=Compatibility(
            status=compatibility_status,
            api_versions=("servicefabric.ai/v1",),
            evaluated_source_digest=(
                definition_digest if compatibility_status == "compatible" else None
            ),
            evaluator_revision=ADAPTER_DIGEST,
            notes=("Local development profile; compatibility is declared, not certified.",),
        ),
        lineage=tuple(lineage),
        source_contract=source_contract,
        relationships=tuple(
            RegistryRelationship(
                relationship=relationship,
                target_native_id=target,
                target_reference=None,
                resolution="unresolved",
            )
            for relationship, target in relationships
        ),
        tags=tuple(dict.fromkeys(tags)),
    )


def _literal_assignment(path: Path, name: str) -> Any:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                target_name = target.id if isinstance(target, ast.Name) else None
                target_attr = target.attr if isinstance(target, ast.Attribute) else None
                if name in {target_name, target_attr}:
                    try:
                        return ast.literal_eval(node.value)
                    except (ValueError, TypeError):
                        continue
    raise ValueError(f"literal assignment {name!r} not found in {path}")


def discover_registry_projections(
    *, discovered_at: datetime | None = None
) -> list[RegistryProjection]:
    observed_at = discovered_at or datetime.now(timezone.utc).replace(microsecond=0)
    projections: list[RegistryProjection] = []

    agent_file = "packages/risk_agents/src/risk_agents/roles.py"
    for role in AGENT_ROLES:
        value = role.model_dump(mode="json")
        projections.append(
            _projection(
                kind=AssetKind.AGENT,
                asset_id=role.role_id,
                version=None,
                display_name=role.role_id.rsplit(".", 1)[-1].replace("_", " ").title(),
                summary=role.objective,
                source_reference=_source_path(agent_file, "AGENT_ROLES"),
                source_file=agent_file,
                source_namespace="portfolio-risk.agent-role",
                source_contract="risk_agents.AgentRole",
                source_value=value,
                source_type="python_registry",
                tags=("reviewed-role", "active" if role.role_id in ACTIVE_AGENT_ROLE_IDS else "inactive"),
                relationships=(
                    ("uses_capability", capability_id)
                    for capability_id in role.allowed_capability_ids
                ),
                compatibility_status="compatible",
                discovered_at=observed_at,
            )
        )

    capability_file = "packages/risk_capabilities/src/risk_capabilities/catalog.py"
    runtime_ids = set(DEFAULT_CAPABILITY_REGISTRY.capability_ids)
    for descriptor in CAPABILITY_DESCRIPTORS:
        value = descriptor.model_dump(mode="json")
        available = descriptor.capability_id in runtime_ids
        projections.append(
            _projection(
                kind=AssetKind.CAPABILITY,
                asset_id=descriptor.capability_id,
                version=None,
                display_name=descriptor.capability_id.replace(".", " ").replace("_", " ").title(),
                summary=descriptor.objective,
                source_reference=_source_path(capability_file, "CAPABILITY_DESCRIPTORS"),
                source_file=capability_file,
                source_namespace="portfolio-risk.capability-descriptor",
                source_contract="risk_capabilities.CapabilityDescriptor",
                source_value=value,
                source_type="python_registry",
                tags=("reviewed-descriptor", "local-handler" if available else "descriptor-only"),
                compatibility_status="compatible" if available else "unavailable",
                discovered_at=observed_at,
            )
        )

    evaluation_file = "examples/portfolio-risk-thesis/experiments/day4_fixture.yaml"
    manifest = load_day4_manifest(REPOSITORY_ROOT / evaluation_file)
    manifest_value = manifest.model_dump(mode="json")
    projections.append(
        _projection(
            kind=AssetKind.EVALUATION,
            asset_id=manifest.experiment_id,
            version=str(manifest.version),
            native_version=str(manifest.version),
            display_name="Day 4 Synthetic Fixture Architecture Evaluation",
            summary="Reviewed descriptive B0/B1/A1 historical replay evaluation with a strict label firewall and human QA.",
            source_reference=evaluation_file,
            source_file=evaluation_file,
            source_namespace="portfolio-risk.thesis-day4-evaluation",
            source_contract="portfolio_risk_thesis.Day4ExperimentManifest",
            source_value=manifest_value,
            source_type="validated_yaml_manifest",
            canonical=False,
            tags=("thesis-scoped", "reviewed-synthetic-fixture", "human-review"),
            relationships=(
                ("evaluates_workflow", architecture_id)
                for architecture_id in manifest.architectures
            ),
            compatibility_status="compatible",
            discovered_at=observed_at,
        )
    )

    renderer_sources = (
        (
            AssetKind.REPORT,
            "risk_analytics.reports.render_report",
            "Risk Analytics Report Renderer",
            "Deterministic Markdown and semantic HTML renderer for one reviewed analytics result.",
            render_report,
            "packages/risk_analytics/src/risk_analytics/reports.py",
            "RiskReport",
        ),
        (
            AssetKind.REPORT,
            "risk_analytics.monitoring_reports.render_monitoring_report",
            "Monitoring Report Renderer",
            "Deterministic monitoring and replay report renderer for human review.",
            render_monitoring_report,
            "packages/risk_analytics/src/risk_analytics/monitoring_reports.py",
            "MonitoringReport",
        ),
        (
            AssetKind.REPORT,
            "portfolio_risk_thesis.day4.report.render_preliminary_results",
            "Day 4 Preliminary Results Renderer",
            "Cautious aggregate Markdown renderer for the thesis Day 4 evaluation.",
            render_preliminary_results,
            "examples/portfolio-risk-thesis/src/portfolio_risk_thesis/day4/report.py",
            "Markdown",
        ),
        (
            AssetKind.DASHBOARD,
            "portfolio_risk_thesis.day4.report.render_dashboard",
            "Day 4 Offline Dashboard Renderer",
            "Thesis-scoped self-contained local HTML renderer for completed synthetic-fixture evaluation data.",
            render_day4_dashboard,
            "examples/portfolio-risk-thesis/src/portfolio_risk_thesis/day4/report.py",
            "Offline HTML",
        ),
    )
    for kind, asset_id, name, summary, renderer, source_file, output in renderer_sources:
        source_value = {
            "symbol": asset_id,
            "signature": str(inspect.signature(renderer)),
            "source": inspect.getsource(renderer),
        }
        projections.append(
            _projection(
                kind=kind,
                asset_id=asset_id,
                version=None,
                display_name=name,
                summary=summary,
                source_reference=_source_path(source_file, renderer.__name__),
                source_file=source_file,
                source_namespace=(
                    "portfolio-risk.thesis-day4-dashboard-renderer"
                    if kind is AssetKind.DASHBOARD
                    else "portfolio-risk.report-renderer"
                ),
                source_contract="python.callable.renderer",
                source_value=source_value,
                source_type="python_renderer",
                canonical=False,
                tags=("renderer", "deterministic", "human-review"),
                compatibility_status="compatible",
                discovered_at=observed_at,
            )
        )

    scenario_file = "apps/portfolio-risk-workbench/analysis_service.py"
    for scenario in _literal_assignment(REPOSITORY_ROOT / scenario_file, "SCENARIO_CATALOGUE"):
        projections.append(
            _projection(
                kind=AssetKind.SCENARIO,
                asset_id=scenario["scenario_id"],
                version=None,
                display_name=scenario["label"],
                summary="Reviewed deterministic Workbench scenario definition for local effect-free analysis.",
                source_reference=_source_path(scenario_file, "SCENARIO_CATALOGUE"),
                source_file=scenario_file,
                source_namespace="portfolio-risk.workbench-scenario",
                source_contract="portfolio-risk-workbench.SCENARIO_CATALOGUE entry",
                source_value=scenario,
                source_type="python_registry",
                canonical=False,
                tags=("workbench-local", "deterministic", "candidate-source"),
                relationships=(("uses_capability", "risk.scenario.evaluate"),),
                compatibility_status="compatible",
                discovered_at=observed_at,
            )
        )

    workflow_file = "examples/portfolio-risk-thesis/src/portfolio_risk_thesis/day3/treatments.py"
    labels = {
        "B0": "Deterministic Reference Treatment",
        "B1": "Single Structured-Agent Treatment",
        "A1": "Ordered Specialist-Team Treatment",
    }
    for treatment in day3_definitions():
        value = treatment.model_dump(mode="json")
        projections.append(
            _projection(
                kind=AssetKind.WORKFLOW,
                asset_id=treatment.architecture_id,
                version=None,
                display_name=labels[treatment.architecture_id],
                summary="Accepted thesis-scoped architecture treatment for effect-free historical replay.",
                source_reference=_source_path(workflow_file, "definitions"),
                source_file=workflow_file,
                source_namespace="portfolio-risk.thesis-day3-treatment",
                source_contract="portfolio_risk_thesis.ArchitectureTreatment",
                source_value=value,
                source_type="python_factory",
                canonical=False,
                tags=("thesis-scoped", "accepted-treatment", "effect-free"),
                relationships=(
                    ("uses_agent", role_id) for role_id in treatment.role_ids
                ),
                compatibility_status="compatible",
                discovered_at=observed_at,
            )
        )

    targets_by_kind_and_id = {
        (projection.identity.kind, projection.identity.asset_id): projection.identity.reference
        for projection in projections
    }
    relationship_kinds = {
        "uses_capability": AssetKind.CAPABILITY,
        "uses_agent": AssetKind.AGENT,
        "evaluates_workflow": AssetKind.WORKFLOW,
    }
    resolved_projections: list[RegistryProjection] = []
    for projection in projections:
        relationships = []
        for relationship in projection.relationships:
            target_kind = relationship_kinds[relationship.relationship]
            target_reference = targets_by_kind_and_id.get(
                (target_kind, relationship.target_native_id)
            )
            relationships.append(
                relationship.model_copy(
                    update={
                        "target_reference": target_reference,
                        "resolution": "resolved" if target_reference else "unavailable",
                    }
                )
            )
        resolved_projections.append(
            projection.model_copy(
                update={
                    "relationships": tuple(relationships),
                    "lineage": tuple(
                        relationship.target_reference
                        for relationship in relationships
                        if relationship.target_reference
                    ),
                }
            )
        )
    projections = resolved_projections
    identities = [projection.identity.reference for projection in projections]
    if len(identities) != len(set(identities)):
        raise ValueError("source discovery produced duplicate registry identities")
    if len(projections) != 44:
        raise ValueError(f"reviewed source adapter set must produce 44 projections, got {len(projections)}")
    return sorted(projections, key=lambda item: item.identity.reference)


def document_payload(document: Any) -> dict[str, Any]:
    payload = document.model_dump(mode="json")
    payload["state"] = document.state.value
    payload["reference"] = document.projection.identity.reference
    payload["indexed"] = True
    payload["revision"] = document.receipts[-1].receipt_digest
    payload["allowed_transitions"] = [
        state.value for state in LIFECYCLE_TRANSITIONS[document.state]
    ]
    return payload


def discovered_payload(projection: RegistryProjection, *, indexed: bool) -> dict[str, Any]:
    return {
        "projection": projection.model_dump(mode="json"),
        "state": "candidate" if indexed else "discovered",
        "reference": projection.identity.reference,
        "indexed": indexed,
        "receipts": [],
        "revision": None,
        "allowed_transitions": [],
    }
