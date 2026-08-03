"""Discover existing PortfolioRisk definitions as bounded registry projections."""

from __future__ import annotations

import ast
import hashlib
import inspect
import json
import os
import sys
from datetime import datetime, timezone
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
    AssetKind,
    Compatibility,
    LocalRegistryStore,
    Provenance,
    RegistryIdentity,
    RegistryProjection,
    SourceReference,
)

DEFAULT_REGISTRY_ROOT = Path(
    os.environ.get(
        "PORTFOLIO_RISK_REGISTRY_ROOT",
        Path.home() / ".servicefabric-portfolio-risk" / "registry-v1",
    )
).expanduser()


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
    native_version: str | None = None,
    canonical: bool = True,
    compatibility_status: str = "unknown",
    tags: Iterable[str] = (),
    attributes: dict[str, Any] | None = None,
    lineage: Iterable[str] = (),
    requires: Iterable[str] = (),
    discovered_at: datetime,
) -> RegistryProjection:
    definition_digest = _digest(source_value)
    source_digest = hashlib.sha256(
        (REPOSITORY_ROOT / source_file).read_bytes()
    ).hexdigest()
    return RegistryProjection(
        identity=RegistryIdentity(
            kind=kind,
            asset_id=asset_id,
            version=version or definition_digest[:12],
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
        ),
        provenance=Provenance(
            discovered_by="portfolio-risk-registry-source-adapter/v1",
            discovered_at=discovered_at,
            notes=("Indexed metadata only; the referenced source remains authoritative.",),
        ),
        compatibility=Compatibility(
            status=compatibility_status,
            api_versions=("servicefabric.ai/v1",),
            requires=tuple(requires),
            notes=("Local development profile; compatibility is declared, not certified.",),
        ),
        lineage=tuple(lineage),
        tags=tuple(dict.fromkeys(tags)),
        attributes=attributes or {},
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
                source_value=value,
                source_type="python_registry",
                tags=("reviewed-role", "active" if role.role_id in ACTIVE_AGENT_ROLE_IDS else "inactive"),
                attributes={
                    "source_namespace": "portfolio-risk.agent-role",
                    "input_contracts": role.input_contracts,
                    "output_contracts": role.output_contracts,
                    "capability_ids": role.allowed_capability_ids,
                    "human_review_required": role.human_review_required,
                    "runtime_claim": "role card; indexing does not compile or run it",
                },
                requires=role.allowed_capability_ids,
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
                source_value=value,
                source_type="python_registry",
                tags=("reviewed-descriptor", "local-handler" if available else "descriptor-only"),
                attributes={
                    "source_namespace": "portfolio-risk.capability-descriptor",
                    "input_contract": descriptor.input_contract,
                    "output_contract": descriptor.output_contract,
                    "allowed_effects": descriptor.allowed_effects,
                    "requires_human_review": descriptor.requires_human_review,
                    "local_handler_available": available,
                },
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
            source_value=manifest_value,
            source_type="validated_yaml_manifest",
            canonical=False,
            tags=("thesis-scoped", "reviewed-synthetic-fixture", "human-review"),
            attributes={
                "source_namespace": "portfolio-risk.thesis-day4-evaluation",
                "profile": manifest.profile,
                "architecture_ids": list(manifest.architectures),
                "maximum_authorized_model_calls": manifest.maximum_authorized_model_calls,
                "human_review_required": manifest.human_review_required,
                "effects": manifest.effects,
            },
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
                source_value=source_value,
                source_type="python_renderer",
                canonical=False,
                tags=("renderer", "deterministic", "human-review"),
                attributes={
                    "source_namespace": (
                        "portfolio-risk.thesis-day4-dashboard-renderer"
                        if kind is AssetKind.DASHBOARD
                        else "portfolio-risk.report-renderer"
                    ),
                    "output_contract": output,
                    "artifact_storage": "not indexed; output belongs to Phase 2",
                },
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
                summary="Reviewed deterministic Workbench scenario: "
                + ", ".join(f"{target} {shock}" for target, shock in scenario["shocks"])
                + ".",
                source_reference=_source_path(scenario_file, "SCENARIO_CATALOGUE"),
                source_file=scenario_file,
                source_value=scenario,
                source_type="python_registry",
                canonical=False,
                tags=("workbench-local", "deterministic", "candidate-source"),
                attributes={
                    "source_namespace": "portfolio-risk.workbench-scenario",
                    "shocks": scenario["shocks"],
                    "all_snapshot_positions": scenario["all_snapshot_positions"],
                },
                requires=("risk.scenario.evaluate",),
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
                summary=f"Accepted Day 3 treatment with {treatment.model_calls} fixed model calls and {len(treatment.role_ids)} ordered roles.",
                source_reference=_source_path(workflow_file, "definitions"),
                source_file=workflow_file,
                source_value=value,
                source_type="python_factory",
                canonical=False,
                tags=("thesis-scoped", "accepted-treatment", "effect-free"),
                attributes={
                    "source_namespace": "portfolio-risk.thesis-day3-treatment",
                    "role_ids": treatment.role_ids,
                    "model_calls": treatment.model_calls,
                    "effects": [],
                },
                requires=treatment.role_ids,
                compatibility_status="compatible",
                discovered_at=observed_at,
            )
        )

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
    return payload


def discovered_payload(projection: RegistryProjection, *, indexed: bool) -> dict[str, Any]:
    return {
        "projection": projection.model_dump(mode="json"),
        "state": "candidate" if indexed else "discovered",
        "reference": projection.identity.reference,
        "indexed": indexed,
        "receipts": [],
    }
