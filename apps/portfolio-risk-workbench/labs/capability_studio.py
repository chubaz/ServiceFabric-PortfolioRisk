"""Capability Studio catalogue, proposal backlog and fixed-test runner."""

from __future__ import annotations

import hashlib
import inspect
import json
import os
import re
import shutil
import sys
import threading
import time
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from agent_studio import COST_OPTIMIZED_LLM_MODEL, RUN_ROOT, _keychain_key
from risk_analytics import (
    AnalysisEvidence, AnalysisHorizon, DetectorDefinition, DetectorKind,
    DetectorObservation, SamplePeriod, ScenarioShock, SignalScope,
)
from risk_capabilities import (
    AlertDraft,
    AlertReviewRequest,
    AlertSynthesisRequest,
    AnomalyDetectionRequest,
    CAPABILITY_DESCRIPTORS,
    CAPABILITY_REQUEST_TYPES,
    CapabilityResult,
    ContributionSummaryRequest,
    ContributionValue,
    ContextualMonitoringCapabilityRequest,
    ContextualMonitoringWorkflowRequest,
    DEFAULT_CAPABILITY_REGISTRY,
    DecisionPoint,
    DerivedReturnsRequest,
    DetectorExecutionRequest,
    EventQueryCapabilityRequest,
    EvidenceReference,
    ExposureSummaryRequest,
    HistoricalTailRiskRequest,
    MonitoringAlertSynthesisCapabilityRequest,
    NewsClassificationRequest,
    PolicyEvaluationCapabilityRequest,
    PortfolioDataContextCapabilityRequest,
    PortfolioSnapshotRequest,
    PositionSpecification,
    ReplayCapabilityRequest,
    ReplayEvaluationCapabilityRequest,
    ReplayStepInput,
    ReportRequest,
    ReturnsRequest,
    ScenarioRequest,
    SyntheticNewsEvent,
    VolatilityRequest,
    build_contextual_monitoring_request,
    event_signals_from_result,
)
from risk_capabilities.registry import KnowledgeDueRequest, SyntheticIngestRequest
from risk_data import (
    DatasetSnapshot,
    EventDatasetSnapshot,
    EventQueryRequest,
    EventQueryResult,
    IngestionRun,
    LocalEventRecord,
    NormalizedMarketRecord,
    PublicationRestriction,
    QuerySpec,
    ValidationSummary,
)
from risk_domain import CashBalance, InstrumentIdentifier, PortfolioSnapshot, Position
from risk_domain.monitoring import (
    DateEffectiveMapping,
    MonitoringEvidence,
    MonitoringAlertDraft,
    MonitoringMetric,
    MonitoringPolicyVersion,
    OutcomeLabel,
    PointInTimeObservation,
    PolicyEvaluationRequest,
    PolicyEvaluationResult,
    PortfolioDataContext,
    ReplayRun,
    ReplaySpecification,
)
from risk_planning import load_seed_catalog
from risk_capabilities.catalog import CAPABILITY_BY_ID
from risk_domain.digests import sha256_digest
from risk_analysis_package_runtime import _synthetic_fixture


def _repository_root(start: Path) -> Path:
    for candidate in (start, *start.parents):
        if (candidate / ".git").exists():
            return candidate
    return start


REPOSITORY_ROOT = _repository_root(Path(__file__).resolve())
SERVICEFABRIC_PACKAGES = REPOSITORY_ROOT / "vendor" / "servicefabric" / "packages"


def _expose_servicefabric_packages() -> None:
    required = (
        "servicefabric_contracts/src",
        "servicefabric_capability_model/src",
        "servicefabric_capability_registry/src",
        "servicefabric_capability_invocation",
        "servicefabric_operation_model",
    )
    missing = [item for item in required if not (SERVICEFABRIC_PACKAGES / item).exists()]
    if missing:
        raise RuntimeError(
            "pinned ServiceFabric submodule is unavailable: " + ", ".join(missing)
        )
    for relative in reversed(required):
        path = str(SERVICEFABRIC_PACKAGES / relative)
        if path not in sys.path:
            sys.path.insert(0, path)


_expose_servicefabric_packages()

from servicefabric_capability_invocation import (  # noqa: E402
    CapabilityAvailability,
    CapabilityInvocationRequest,
    CapabilityInvocationService,
)
from servicefabric_capability_model import (  # noqa: E402
    CapabilityDefinition,
    CapabilityDefinitionSpec,
    CapabilityMetadata,
)
from servicefabric_capability_registry import CapabilityRegistry  # noqa: E402
from servicefabric_contracts.effects import EffectContract, EffectDeclaration  # noqa: E402
from servicefabric_operation_model import HttpBinding, OperationDefinition  # noqa: E402


CAPABILITY_STUDIO_ROOT = Path(
    os.environ.get(
        "PORTFOLIO_RISK_CAPABILITY_STUDIO_ROOT",
        RUN_ROOT.parent / "capability-studio",
    )
).expanduser().resolve()
PROPOSAL_ROOT = CAPABILITY_STUDIO_ROOT / "proposals"
STUDIO_DESIGN_PROPOSAL_ROOT = CAPABILITY_STUDIO_ROOT / "studio-design-proposals"
DESIGN_SESSION_ROOT = CAPABILITY_STUDIO_ROOT / "design-sessions"
RUN_REPOSITORY = CAPABILITY_STUDIO_ROOT / "runs"
CAPABILITY_BRIDGE_VERSION = "bridge-v2"
CANONICAL_REGISTRY_ROOT = CAPABILITY_STUDIO_ROOT / "canonical-registry" / CAPABILITY_BRIDGE_VERSION
PROPOSAL_ID_PATTERN = r"^cap-proposal-[0-9]{8}T[0-9]{6}Z-[a-f0-9]{8}$"
STUDIO_DESIGN_PROPOSAL_ID_PATTERN = r"^studio-design-[0-9]{8}T[0-9]{6}Z-[a-f0-9]{8}$"
DESIGN_SESSION_ID_PATTERN = r"^cap-design-[0-9]{8}T[0-9]{6}Z-[a-f0-9]{8}$"
RUN_ID_PATTERN = r"^cap-run-[0-9]{8}T[0-9]{6}Z-[a-f0-9]{8}$"
_STORE_LOCK = threading.RLock()


CAPABILITY_PACKAGES: tuple[dict[str, Any], ...] = (
    {
        "package_id": "portfolio_context",
        "name": "Portfolio context",
        "purpose": "Create and inspect immutable portfolio and exposure context.",
        "description": "This package establishes the portfolio facts that other work can safely use: holdings, cash, prices, weights and the time-specific data context. It does not recommend or change a position.",
        "b0_role": "Use this first in B0. Its inputs should be fixed in the experiment setup.",
        "members": (
            "portfolio.snapshot.create",
            "portfolio.exposure.summarize",
            "portfolio.data_context.create",
        ),
    },
    {
        "package_id": "downside_risk",
        "name": "Downside risk",
        "purpose": "Calculate return, volatility, drawdown, tail-risk, contribution and scenario evidence.",
        "description": "This package turns an accepted portfolio and price series into measurable downside-risk evidence. Most methods can use a fixed B0 configuration; scenario shocks may also be chosen by an agent when the experiment permits it.",
        "b0_role": "Use fixed windows, confidence levels and scenarios for B0; allow agent adjustments only in explicit treatment arms.",
        "members": (
            "risk.returns.simple",
            "risk.volatility.annualized",
            "risk.drawdown.maximum",
            "risk.var.historical",
            "risk.expected_shortfall.historical",
            "risk.contribution.summarize",
            "risk.scenario.evaluate",
        ),
    },
    {
        "package_id": "portfolio_monitoring",
        "name": "Portfolio monitoring",
        "purpose": "Assemble point-in-time monitoring, policy, replay and evaluation operations.",
        "description": "This package applies a reviewed policy to the information available at each replay time, records any breach or abstention, and evaluates the resulting replay. It keeps time and evidence boundaries explicit.",
        "b0_role": "Use a frozen policy and replay specification for B0. Agent configuration is optional only where an experimental arm authorises it.",
        "members": tuple(
            item.capability_id
            for item in CAPABILITY_DESCRIPTORS
            if item.capability_id.startswith("monitoring.")
        ),
    },
    {
        "package_id": "review_material",
        "name": "Review material",
        "purpose": "Create effect-free alerts, reports and evidence-backed review outputs.",
        "description": "This package prepares reviewable alert material from completed analysis. It is effect-free: it can explain and draft, but cannot trade, rebalance or change the portfolio.",
        "b0_role": "Use fixed alert rules and review routes for B0.",
        "members": (
            "alert.draft.synthesize",
            "risk.report.render",
            "monitoring.report.render",
        ),
    },
)


# Placement environments are registered data, not separate object types in the
# authoring model. A capability owns both its behavior and any hosted form.
CAPABILITY_HOSTS: tuple[dict[str, Any], ...] = (
    {
        "host_id": "servicefabric.dashboard",
        "display_name": "Dashboard pages",
        "status": "available",
        "surface_kinds": ("dashboard_component",),
        "frameworks": ("D3.js", "TypeScript", "Three.js", "Vega-Lite"),
        "connection_contract": "DashboardComponentHost@v1",
        "write_boundary": "system proposal or isolated experiment dashboard",
        "description": "Provides a visual home for a completed capability result. It is for user-facing review and does not participate in headless agent reasoning.",
        "capability_integration": "A capability supplies a typed dashboard view model through DashboardComponentHost@v1; the host renders that result inside an isolated dashboard or experiment surface.",
        "effect_boundary": "Can create only a versioned dashboard proposal or an isolated experiment dashboard. It cannot change a portfolio, broker, or source database.",
    },
    {
        "host_id": "servicefabric.report",
        "display_name": "Report composer",
        "status": "available",
        "surface_kinds": ("report_section",),
        "frameworks": ("Markdown", "HTML", "Matplotlib", "Python"),
        "connection_contract": "ReportSectionHost@v1",
        "write_boundary": "versioned report draft or experiment work product",
        "description": "Provides a user-facing report section for a completed analysis. It is a presentation surface, not an input to headless reasoning.",
        "capability_integration": "A capability supplies a typed report section through ReportSectionHost@v1; the host places the resulting text, tables, or figures in a versioned review document.",
        "effect_boundary": "Can create only a versioned report draft or experiment work product. It cannot change a portfolio, broker, or source database.",
    },
    {
        "host_id": "servicefabric.experiment_data",
        "display_name": "Experiment data store",
        "status": "available",
        "surface_kinds": ("database_view", "database_table"),
        "frameworks": ("DuckDB", "Arrow", "Python"),
        "connection_contract": "ExperimentDataHost@v1",
        "write_boundary": "isolated experiment database only; source databases remain read-only",
        "description": "Provides the isolated tables and views used to prepare, store, and replay experiment data without modifying the licensed source data.",
        "capability_integration": "A capability reads an approved input view and writes a typed derived table or view through ExperimentDataHost@v1, so later capabilities can use the same recorded result.",
        "effect_boundary": "Can write only to the experiment database. Licensed and source databases remain read-only.",
    },
    {
        "host_id": "servicefabric.decision_log",
        "display_name": "Decision repository",
        "status": "available",
        "surface_kinds": ("decision_record",),
        "frameworks": ("Python", "TypeScript"),
        "connection_contract": "DecisionRecordHost@v1",
        "write_boundary": "proposal and review lifecycle; no external execution",
        "description": "Provides a reviewable record of a proposed risk decision, its evidence, and its review state.",
        "capability_integration": "A capability supplies a typed recommendation and evidence bundle through DecisionRecordHost@v1; the host records it for review and links it to its inputs.",
        "effect_boundary": "Can advance a proposal through the review lifecycle only. It cannot execute an external decision.",
    },
    {
        "host_id": "servicefabric.workflow_cycle",
        "display_name": "Workflow cycle",
        "status": "available",
        "surface_kinds": ("workflow_event",),
        "frameworks": ("Python", "LangGraph"),
        "connection_contract": "WorkflowEventHost@v1",
        "write_boundary": "isolated workflow state and scheduled lifecycle events",
        "description": "Provides the controlled sequence in which capabilities are called during a replay or a repeatable workflow.",
        "capability_integration": "Each capability receives the typed output of its permitted predecessors and returns a typed event result through WorkflowEventHost@v1, making the sequence inspectable and repeatable.",
        "effect_boundary": "Can change only isolated workflow state and scheduled lifecycle events. It cannot cause an external portfolio action.",
    },
    {
        "host_id": "servicefabric.artifact_repository",
        "display_name": "Artifact repository",
        "status": "available",
        "surface_kinds": ("artifact",),
        "frameworks": ("JSON", "Python"),
        "connection_contract": "ArtifactHost@v1",
        "write_boundary": "candidate or experiment work product",
        "description": "Provides versioned storage for an analysis output, evidence bundle, or candidate work product created during an experiment.",
        "capability_integration": "A capability stores its typed output and provenance through ArtifactHost@v1; later permitted steps can retrieve that exact saved artifact.",
        "effect_boundary": "Can create or revise candidate and experiment work products only. It cannot alter source data or execute a portfolio action.",
    },
    {
        "host_id": "servicefabric.local_api",
        "display_name": "Local development API",
        "status": "development_only",
        "surface_kinds": ("api_endpoint",),
        "frameworks": ("FastAPI", "Python"),
        "connection_contract": "LocalApiHost@v1",
        "write_boundary": "localhost development service; never an external effect",
        "description": "Provides a local development endpoint for testing a capability integration before it is used in an experiment.",
        "capability_integration": "A capability exchanges a typed request and response through LocalApiHost@v1, allowing its contract to be tested from the local application.",
        "effect_boundary": "Is limited to a localhost development service and cannot produce an external effect.",
    },
)

# Presentation capabilities and hosts remain source-compatible for historical
# runs, but are excluded from the active thesis authoring catalogue.
INCUBATOR_CAPABILITY_IDS = {"risk.report.render", "monitoring.report.render"}
INCUBATOR_HOST_IDS = {"servicefabric.dashboard", "servicefabric.report"}
ACTIVE_CAPABILITY_DESCRIPTORS = tuple(
    item for item in CAPABILITY_DESCRIPTORS
    if item.capability_id not in INCUBATOR_CAPABILITY_IDS
)


class StudioModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)


class BlueprintInput(StudioModel):
    name: str = Field(pattern=r"^[a-z][a-z0-9_]{0,127}$")
    semantic_role: str = Field(min_length=2, max_length=240)
    type: str = Field(default="object", min_length=1, max_length=80)
    preparation: str = Field(min_length=2, max_length=500)
    required: bool = True


class CapabilityHostBinding(StudioModel):
    host_id: str = Field(pattern=r"^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*){1,3}$")
    surface_kind: Literal[
        "dashboard_component",
        "report_section",
        "database_view",
        "database_table",
        "decision_record",
        "workflow_event",
        "artifact",
        "api_endpoint",
    ]
    framework: str = Field(min_length=2, max_length=80)
    placement: str = Field(min_length=4, max_length=240)
    lifecycle_operations: tuple[
        Literal["create", "bind", "refresh", "revise", "validate", "archive", "retire"], ...
    ] = Field(min_length=1, max_length=7)
    connection_contract: str = Field(min_length=4, max_length=240)


class CapabilityDependency(StudioModel):
    dependency_id: str = Field(pattern=r"^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*){1,4}$")
    display_name: str = Field(min_length=2, max_length=120)
    dependency_type: Literal["existing_capability", "proposed_capability", "agent_schema_adaptation"]
    status: Literal["available", "proposed", "assumed"]
    purpose: str = Field(min_length=5, max_length=500)
    provides: str = Field(min_length=2, max_length=240)
    depends_on: tuple[str, ...] = Field(default=(), max_length=8)
    blocks_design: bool = False
    blocks_build: bool = False


class CapabilityBlueprint(StudioModel):
    capability_id: str = Field(pattern=r"^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*){1,3}$")
    display_name: str = Field(min_length=2, max_length=120)
    family: Literal[
        "acquisition",
        "preparation",
        "analytics",
        "quantitative_model",
        "interpretation",
        "presentation",
        "governance",
        "meta_capability",
    ]
    outcome: str = Field(min_length=5, max_length=1200)
    implementation_class: Literal[
        "python",
        "duckdb",
        "http_api",
        "mcp",
        "quantitative_model",
        "model_backed",
        "agent_backed",
        "typescript",
    ]
    inputs: tuple[BlueprintInput, ...] = Field(min_length=1, max_length=12)
    output_contract: str = Field(min_length=2, max_length=160)
    output_description: str = Field(min_length=4, max_length=700)
    renderer: Literal[
        "metric",
        "table",
        "time_series",
        "distribution",
        "markdown",
        "chart",
        "dashboard_component",
        "artifact",
        "generic_schema",
    ] = "generic_schema"
    effect_profile: Literal[
        "observe",
        "system_object_write",
        "experiment_object_write",
        "external_placeholder",
    ] = "observe"
    test_cases: tuple[str, ...] = (
        "representative valid input",
        "missing or invalid input",
        "adversarial boundary input",
    )
    package_ids: tuple[str, ...] = ()
    host_binding: CapabilityHostBinding | None = None
    dependency_ids: tuple[str, ...] = Field(default=(), max_length=12)


class DesignMessage(StudioModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=2400)


class DesignQuizOption(StudioModel):
    label: str = Field(min_length=2, max_length=80)
    answer: str = Field(min_length=4, max_length=360)
    explanation: str = Field(min_length=4, max_length=140)


class DesignQuiz(StudioModel):
    question: str = Field(min_length=8, max_length=500)
    options: tuple[DesignQuizOption, ...] = Field(min_length=4, max_length=4)
    allow_other: bool = True


class RequirementAssessmentRequest(StudioModel):
    requirement: str = Field(min_length=8, max_length=4000)
    use_llm: bool = False
    conversation: tuple[DesignMessage, ...] = Field(default=(), max_length=24)
    conclude: bool = False
    session_id: str | None = Field(default=None, pattern=DESIGN_SESSION_ID_PATTERN)
    parent_session_id: str | None = Field(default=None, pattern=DESIGN_SESSION_ID_PATTERN)


class RequirementAssessment(StudioModel):
    assessment_id: str
    requirement: str
    recommendation: Literal["reuse", "compose", "improve", "new", "blocked"]
    response: str
    rationale: str
    candidates: tuple[dict[str, Any], ...]
    compact_candidate_count: int
    total_library_count: int
    estimated_prompt_characters: int
    blueprint: CapabilityBlueprint
    model_receipt: dict[str, Any]
    discussion_status: Literal["refining", "consensus_ready", "concluded"]
    open_questions: tuple[str, ...]
    next_question: str | None
    consensus_summary: str
    user_turn_count: int
    intent: Literal["answer_question", "clarify", "plan", "feasibility_review", "synthesize"]
    plan_steps: tuple[str, ...]
    quiz: DesignQuiz | None
    design_target: Literal["capability", "agent", "workflow", "dashboard", "report", "package"]
    proposed_capability_ids: tuple[str, ...]
    dependency_map: tuple[CapabilityDependency, ...] = ()
    session_id: str


class ProposalCreateRequest(StudioModel):
    assessment: RequirementAssessment
    decision: Literal["reuse", "compose", "improve", "new", "blocked"]


class ProposalTransitionRequest(StudioModel):
    action: Literal["approve", "prepare_codex", "return_to_design", "reject"]
    actor: str = Field(default="local.human", min_length=3, max_length=120)


class StudioDesignProposalRequest(StudioModel):
    assessment: RequirementAssessment
    actor: str = Field(default="local.human", min_length=3, max_length=120)


class FixtureRunRequest(StudioModel):
    capability_id: str
    fixture_id: Literal["reviewed_synthetic"] = "reviewed_synthetic"


def _tokens(value: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9]+", value.casefold())
        if len(token) > 2 and token not in {"with", "from", "that", "this", "using", "into"}
    }


def _family(capability_id: str, objective: str) -> str:
    value = f"{capability_id} {objective}".casefold()
    if any(item in value for item in ("render", "report", "visual")):
        return "presentation"
    if any(item in value for item in ("ingest", "query", "market_data", "event")):
        return "acquisition"
    if capability_id.startswith("risk.capability."):
        return "interpretation"
    if capability_id.startswith("risk."):
        return "analytics"
    if any(item in value for item in ("policy", "review", "evaluate")):
        return "governance"
    if any(item in value for item in ("classify", "synthesize", "recommendation")):
        return "interpretation"
    if any(item in value for item in ("snapshot", "context", "normalize", "mapping")):
        return "preparation"
    return "analytics"


def _implementation_class(capability_id: str) -> str:
    if capability_id.startswith("events.query"):
        return "duckdb"
    if capability_id.startswith("risk.capability."):
        return "model_backed"
    return "python"


def _renderer(capability_id: str, output_contract: str) -> str:
    value = f"{capability_id} {output_contract}".casefold()
    if "report" in value or "alert" in value:
        return "markdown"
    if "returnseries" in value or "replay" in value:
        return "time_series"
    if "exposure" in value or "contribution" in value:
        return "table"
    if any(item in value for item in ("volatility", "tailrisk", "scenarioresult")):
        return "metric"
    return "generic_schema"


def _packages_for(capability_id: str) -> tuple[str, ...]:
    return tuple(
        item["package_id"]
        for item in CAPABILITY_PACKAGES
        if capability_id in item["members"]
    )


def _execution_profile(capability_id: str, *, available: bool) -> dict[str, str]:
    if not available:
        return {
            "kind": "generative",
            "kind_label": "Generative",
            "kind_description": "A model would interpret or generate content rather than apply only a fixed calculation.",
            "parameterisation": "agent_required",
            "parameterisation_label": "Agent configuration required",
            "parameterisation_description": "This cannot be used in B0 until an implementation and its agent configuration are reviewed.",
        }
    if capability_id in {
        "market.anomaly.detect",
        "risk.volatility.annualized",
        "risk.var.historical",
        "risk.expected_shortfall.historical",
    }:
        return {
            "kind": "statistical",
            "kind_label": "Statistical",
            "kind_description": "It estimates or tests a quantity from an observation sample.",
            "parameterisation": "agent_optional" if capability_id == "market.anomaly.detect" else "a_priori",
            "parameterisation_label": "B0 ready — agent may adjust" if capability_id == "market.anomaly.detect" else "B0 ready",
            "parameterisation_description": "A B0 run can freeze its thresholds, windows and confidence level before execution." if capability_id != "market.anomaly.detect" else "B0 can freeze thresholds; an authorised agent may adjust them only in a treatment arm.",
        }
    if capability_id in {"risk.scenario.evaluate", "monitoring.run.contextual", "monitoring.replay"}:
        return {
            "kind": "deterministic",
            "kind_label": "Deterministic",
            "kind_description": "The same approved inputs produce the same result.",
            "parameterisation": "agent_optional",
            "parameterisation_label": "B0 ready — agent may adjust",
            "parameterisation_description": "B0 can use fixed settings; an authorised agent may select approved scenarios or analysis settings in a treatment arm.",
        }
    return {
        "kind": "deterministic",
        "kind_label": "Deterministic",
        "kind_description": "The same approved inputs produce the same result.",
        "parameterisation": "a_priori",
        "parameterisation_label": "B0 ready",
        "parameterisation_description": "Its inputs and settings can be fixed before the B0 run begins.",
    }


def _capability_description(descriptor: Any, *, available: bool, profile: dict[str, str]) -> dict[str, Any]:
    capability_id = descriptor.capability_id
    handler = DEFAULT_CAPABILITY_REGISTRY._handlers.get(capability_id) if available else None
    source = ""
    source_file = ""
    callable_name = ""
    if handler is not None:
        callable_name = getattr(handler, "__name__", handler.__class__.__name__)
        try:
            source = inspect.getsource(handler)
            resolved = Path(inspect.getsourcefile(handler) or "").resolve()
            source_file = str(resolved.relative_to(REPOSITORY_ROOT)) if resolved.is_relative_to(REPOSITORY_ROOT) else str(resolved)
        except (OSError, TypeError, ValueError):
            source = "Source is not available for this registered callable."
    evidence_rule = "Evidence references are required." if descriptor.requires_evidence else "Evidence references are optional."
    review_rule = "A human must review the result." if descriptor.requires_human_review else "Human review is not required by this contract."
    agent_contract = "\n".join(
        (
            f"Capability: {capability_id}",
            f"Purpose: {descriptor.objective}",
            f"Input: {descriptor.input_contract}",
            f"Output: {descriptor.output_contract}",
            f"Evidence: {evidence_rule}",
            f"Review: {review_rule}",
            f"Method: {profile['kind_label']}. {profile['kind_description']}",
            f"Setup: {profile['parameterisation_label']}. {profile['parameterisation_description']}",
            "Effects: Return analysis only. Do not place orders, rebalance a portfolio, call an external provider, or write to a licensed source database.",
        )
    )
    return {
        "contract": {
            "agent_text": agent_contract,
            "input": descriptor.input_contract,
            "output": descriptor.output_contract,
            "requires_evidence": descriptor.requires_evidence,
            "requires_human_review": descriptor.requires_human_review,
            "allowed_effects": tuple(descriptor.allowed_effects),
            "denied_effects": tuple(descriptor.denied_effects),
        },
        "script": {
            "available": handler is not None,
            "language": "Python" if handler is not None else None,
            "module": getattr(handler, "__module__", None) if handler is not None else None,
            "callable": callable_name or None,
            "source_file": source_file or None,
            "source": source or "No executable implementation is registered for this capability.",
        },
        "human": {
            "summary": descriptor.objective,
            "receives": descriptor.input_contract,
            "returns": descriptor.output_contract,
            "how_it_runs": "It runs locally against the supplied, fixed inputs and returns a typed result without changing the portfolio or an external system." if available else "This is currently a definition only. It cannot run until an implementation is registered.",
            "method": profile["kind_label"],
            "setup": profile["parameterisation_label"],
            "setup_description": profile["parameterisation_description"],
            "review": review_rule,
            "status": "Available" if available else "Implementation required",
        },
    }


def _validation_tests(
    descriptor: Any,
    *,
    available: bool,
    fixture_supported: bool,
    fixture_passed: bool,
) -> tuple[dict[str, str], ...]:
    test_case_status = "passed" if fixture_passed else "available" if fixture_supported else "blocked"
    return (
        {
            "test_id": "contract",
            "name": "Input and output contract",
            "status": "passed" if descriptor.input_contract and descriptor.output_contract else "blocked",
            "evidence": "The source definition declares both typed contracts.",
        },
        {
            "test_id": "resolution",
            "name": "Registry resolution",
            "status": "passed" if available else "blocked",
            "evidence": "The exact capability resolves in the active registry." if available else "No active implementation resolves for this definition.",
        },
        {
            "test_id": "fixed_tests",
            "name": "Fixed tests",
            "status": test_case_status,
            "evidence": "A completed fixed-test run is retained." if fixture_passed else "The fixed tests can be run now." if fixture_supported else "The capability implementation is unavailable, so no honest execution tests can run.",
        },
        {
            "test_id": "effect_boundary",
            "name": "Effect boundary",
            "status": "passed" if fixture_passed else "available" if fixture_supported else "missing",
            "evidence": "The retained run produced no undeclared effects." if fixture_passed else "This check is included in the fixed tests." if fixture_supported else "This check requires an executable implementation.",
        },
    )


def _capability_record(
    descriptor: Any,
    completed_fixture_ids: set[str] | None = None,
) -> dict[str, Any]:
    capability_id = descriptor.capability_id
    completed_fixture_ids = completed_fixture_ids or set()
    available = capability_id in DEFAULT_CAPABILITY_REGISTRY.capability_ids
    fixture_supported = capability_id in _fixture_capability_ids()
    execution_profile = _execution_profile(capability_id, available=available)
    validation_tests = _validation_tests(
        descriptor,
        available=available,
        fixture_supported=fixture_supported,
        fixture_passed=capability_id in completed_fixture_ids,
    )
    family = _family(capability_id, descriptor.objective)
    return {
        "capability_id": capability_id,
        "name": capability_id.replace(".", " ").replace("_", " ").title(),
        "family": family,
        "purpose": descriptor.objective,
        "input_contract": descriptor.input_contract,
        "output_contract": descriptor.output_contract,
        "implementation_class": _implementation_class(capability_id),
        "execution_profile": execution_profile,
        "renderer": _renderer(capability_id, descriptor.output_contract),
        "availability": "available" if available else "descriptor_only",
        "lifecycle": "source_reviewed",
        "test_health": "fixture_ready" if fixture_supported else "contract_only",
        "test_case_status": "ready" if fixture_supported else "implementation_required",
        "validation_tests": validation_tests,
        "validation_gate": {
            "status": "ready_for_review" if all(item["status"] == "passed" for item in validation_tests) else "tests_pending",
            "passed": sum(item["status"] == "passed" for item in validation_tests),
            "required": len(validation_tests),
            "validated": False,
        },
        "effect_level": "observe",
        "package_ids": _packages_for(capability_id),
        "requires_evidence": descriptor.requires_evidence,
        "human_review_required": descriptor.requires_human_review,
        "description": _capability_description(descriptor, available=available, profile=execution_profile),
    }


def capability_catalogue() -> dict[str, Any]:
    completed_fixture_ids = {
        item["capability_id"]
        for item in list_fixture_runs()
        if item.get("status") == "completed" and item.get("capability_id")
    }
    records = tuple(
        _capability_record(item, completed_fixture_ids)
        for item in CAPABILITY_DESCRIPTORS
        if item.capability_id not in INCUBATOR_CAPABILITY_IDS
    )
    packages = tuple(
        {**package, "members": tuple(item for item in package["members"] if item not in INCUBATOR_CAPABILITY_IDS)}
        for package in CAPABILITY_PACKAGES
        if any(item not in INCUBATOR_CAPABILITY_IDS for item in package["members"])
    )
    hosts = tuple(item for item in CAPABILITY_HOSTS if item["host_id"] not in INCUBATOR_HOST_IDS)
    return {
        "capabilities": records,
        "packages": packages,
        "hosts": hosts,
        "families": tuple(sorted({item["family"] for item in records})),
        "counts": {
            "capabilities": len(records),
            "available": sum(item["availability"] == "available" for item in records),
            "fixture_ready": sum(item["test_health"] == "fixture_ready" for item in records),
            "test_case_ready": sum(item["test_case_status"] == "ready" for item in records),
            "implementation_required": sum(item["test_case_status"] == "implementation_required" for item in records),
            "validation_eligible": sum(item["validation_gate"]["status"] == "ready_for_review" for item in records),
            "packages": len(packages),
            "hosts": len(hosts),
        },
        "resolution_policy": "exact_first_explicit_compatible_substitution",
        "effect_policy": {
            "available": ("observe", "system_object_write", "experiment_object_write"),
            "external": "placeholder_disabled",
            "licensed_source_database": "read_only",
        },
    }


def _semantic_title(requirement: str) -> str:
    first_request = next(
        (part.strip() for part in requirement.split("\n\n") if part.strip()),
        requirement.strip(),
    )
    sentence = re.split(r"(?<=[.!?])\s+", first_request, maxsplit=1)[0]
    sentence = re.sub(
        r"^(?:please\s+)?(?:i\s+(?:would\s+like|want|need)\s+(?:you\s+)?to\s+)",
        "",
        sentence,
        flags=re.IGNORECASE,
    )
    sentence = re.sub(
        r"^(?:create|build|design|develop)\s+(?:a|an|the)?\s*(?:new\s+)?(?:reusable\s+)?(?:capability|operation|function|utility)\s+(?:that|which|to)\s+",
        "",
        sentence,
        flags=re.IGNORECASE,
    )
    sentence = re.split(
        r"\s+(?:using|with access to|so that|in order to|which should|that should)\s+",
        sentence,
        maxsplit=1,
        flags=re.IGNORECASE,
    )[0]
    sentence = re.split(
        r"\s+and\s+(?:show|shows|render|renders|display|displays|place|places|host|hosts)\b",
        sentence,
        maxsplit=1,
        flags=re.IGNORECASE,
    )[0]
    sentence = re.sub(
        r"^(calculates|calculation of)\b",
        "Calculate",
        sentence,
        flags=re.IGNORECASE,
    )
    sentence = re.sub(r"^(creates)\b", "Create", sentence, flags=re.IGNORECASE)
    sentence = re.sub(r"^(renders)\b", "Render", sentence, flags=re.IGNORECASE)
    sentence = re.sub(r"^(generates)\b", "Generate", sentence, flags=re.IGNORECASE)
    words = re.findall(r"[A-Za-z0-9]+(?:[-.][A-Za-z0-9]+)*", sentence)
    stop = {"a", "an", "the", "some", "any", "type", "kind", "possible"}
    selected = [word for word in words if word.casefold() not in stop][:10]
    if not selected:
        return "Proposed Capability"
    casing = {
        "api": "API",
        "d3.js": "D3.js",
        "duckdb": "DuckDB",
        "fastapi": "FastAPI",
        "html": "HTML",
        "json": "JSON",
        "llm": "LLM",
        "point-in-time": "Point-in-Time",
        "sql": "SQL",
        "three.js": "Three.js",
        "typescript": "TypeScript",
    }
    title = " ".join(casing.get(word.casefold(), word.capitalize()) for word in selected)
    return title[:120].strip()


def _host_binding(requirement: str) -> CapabilityHostBinding | None:
    normalized = requirement.casefold()
    framework = None
    for term, label in (
        ("d3.js", "D3.js"),
        ("d3", "D3.js"),
        ("three.js", "Three.js"),
        ("threejs", "Three.js"),
        ("typescript", "TypeScript"),
        ("matplotlib", "Matplotlib"),
        ("fastapi", "FastAPI"),
        ("duckdb", "DuckDB"),
        ("vega", "Vega-Lite"),
        ("markdown", "Markdown"),
        ("html", "HTML"),
        ("python", "Python"),
    ):
        if term in normalized:
            framework = label
            break
    if any(term in normalized for term in ("dashboard", "interactive chart", "interactive graph", "three.js", "d3.js")):
        return CapabilityHostBinding(
            host_id="servicefabric.dashboard",
            surface_kind="dashboard_component",
            framework=framework or "TypeScript",
            placement="A registered component on a ServiceFabric dashboard page.",
            lifecycle_operations=("create", "bind", "refresh", "revise", "validate", "retire"),
            connection_contract="DashboardComponentHost@v1",
        )
    if any(term in normalized for term in ("report", "dossier", "memo", "report section")):
        return CapabilityHostBinding(
            host_id="servicefabric.report",
            surface_kind="report_section",
            framework=framework or "Markdown",
            placement="A versioned section in the ServiceFabric report composer.",
            lifecycle_operations=("create", "bind", "refresh", "revise", "validate", "archive"),
            connection_contract="ReportSectionHost@v1",
        )
    if any(term in normalized for term in ("database view", "database table", "duckdb", "sql view", "analytical table")):
        surface = "database_table" if "table" in normalized and "view" not in normalized else "database_view"
        return CapabilityHostBinding(
            host_id="servicefabric.experiment_data",
            surface_kind=surface,
            framework=framework or "DuckDB",
            placement="An isolated experiment data object; registered source databases remain read-only.",
            lifecycle_operations=("create", "bind", "refresh", "validate", "retire"),
            connection_contract="ExperimentDataHost@v1",
        )
    if any(term in normalized for term in ("decision log", "decision card", "decision point", "decision record")):
        return CapabilityHostBinding(
            host_id="servicefabric.decision_log",
            surface_kind="decision_record",
            framework=framework or "Python",
            placement="A governed proposal or review event in the Decision Repository.",
            lifecycle_operations=("create", "bind", "revise", "validate", "archive"),
            connection_contract="DecisionRecordHost@v1",
        )
    if any(term in normalized for term in ("schedule", "scheduled event", "workflow cycle", "lifecycle event")):
        return CapabilityHostBinding(
            host_id="servicefabric.workflow_cycle",
            surface_kind="workflow_event",
            framework=framework or "Python",
            placement="A lifecycle event or checkpoint inside an isolated workflow cycle.",
            lifecycle_operations=("create", "bind", "refresh", "revise", "validate", "retire"),
            connection_contract="WorkflowEventHost@v1",
        )
    if any(term in normalized for term in ("api endpoint", "fastapi", "local api")):
        return CapabilityHostBinding(
            host_id="servicefabric.local_api",
            surface_kind="api_endpoint",
            framework=framework or "FastAPI",
            placement="A localhost-only endpoint in the ServiceFabric development API.",
            lifecycle_operations=("create", "bind", "refresh", "validate", "retire"),
            connection_contract="LocalApiHost@v1",
        )
    if any(term in normalized for term in ("artifact", "file output", "saved file")):
        return CapabilityHostBinding(
            host_id="servicefabric.artifact_repository",
            surface_kind="artifact",
            framework=framework or "JSON",
            placement="A candidate or experiment work product in the Artifact Repository.",
            lifecycle_operations=("create", "bind", "revise", "validate", "archive"),
            connection_contract="ArtifactHost@v1",
        )
    return None


def _dependency_map(
    requirement: str,
    candidates: tuple[dict[str, Any], ...],
    blueprint: CapabilityBlueprint,
) -> tuple[CapabilityDependency, ...]:
    dependencies: list[CapabilityDependency] = []
    for candidate in candidates[:3]:
        dependencies.append(
            CapabilityDependency(
                dependency_id=candidate["capability_id"],
                display_name=candidate["name"],
                dependency_type="existing_capability",
                status="available",
                purpose=candidate["purpose"],
                provides=candidate["output_contract"],
                blocks_design=False,
                blocks_build=False,
            )
        )
    if candidates:
        dependencies.append(
            CapabilityDependency(
                dependency_id="agent.schema.adaptation",
                display_name="Agent Schema Adaptation",
                dependency_type="agent_schema_adaptation",
                status="assumed",
                purpose=(
                    "Convert semantically sufficient upstream capability results into the exact validated "
                    "input contract required by this capability."
                ),
                provides="Validated input matching the target capability schema.",
                depends_on=tuple(item["capability_id"] for item in candidates[:3]),
                blocks_design=False,
                blocks_build=False,
            )
        )
    normalized = requirement.casefold()
    needs_distribution = "return distribution" in normalized or "distribution of returns" in normalized
    has_distribution = any("distribution" in f"{item['capability_id']} {item['output_contract']}".casefold() for item in candidates)
    if needs_distribution and not has_distribution:
        dependencies.append(
            CapabilityDependency(
                dependency_id="risk.proposed.portfolio_return_distribution",
                display_name="Calculate Portfolio Return Distribution",
                dependency_type="proposed_capability",
                status="proposed",
                purpose="Calculate a governed point-in-time return distribution from semantically sufficient portfolio and observation evidence.",
                provides="PortfolioReturnDistributionResult with observations, summary statistics, evidence and temporal metadata.",
                depends_on=tuple(item["capability_id"] for item in candidates[:2]),
                blocks_design=False,
                blocks_build=True,
            )
        )
    return tuple(dependencies[:8])


def _blueprint(requirement: str, candidates: tuple[dict[str, Any], ...]) -> CapabilityBlueprint:
    display_name = _semantic_title(requirement)
    words = [item for item in re.findall(r"[a-z0-9]+", display_name.casefold()) if item not in {"a", "an", "the"}]
    slug = "_".join(words[:8])[:70] or "requested_operation"
    first = candidates[0] if candidates else None
    family = first["family"] if first else "analytics"
    implementation = first["implementation_class"] if first else "python"
    output_contract = first["output_contract"] if first else "ProposedCapabilityResult"
    host_binding = _host_binding(requirement)
    renderer = first["renderer"] if first else "generic_schema"
    if host_binding and host_binding.framework in {"D3.js", "Three.js", "TypeScript", "Vega-Lite"}:
        implementation = "typescript"
    if host_binding:
        renderer = {
            "dashboard_component": "dashboard_component",
            "report_section": "markdown",
            "database_view": "table",
            "database_table": "table",
            "decision_record": "artifact",
            "workflow_event": "generic_schema",
            "artifact": "artifact",
            "api_endpoint": "generic_schema",
        }[host_binding.surface_kind]
    blueprint = CapabilityBlueprint(
        capability_id=f"risk.proposed.{slug}",
        display_name=display_name,
        family=family,
        outcome=requirement[-1200:],
        implementation_class=implementation,
        inputs=(
            BlueprintInput(
                name="context",
                semantic_role="Validated point-in-time context required to perform the requested operation.",
                preparation="Resolve eligible data, normalize units and validate the exact input schema.",
            ),
        ),
        output_contract=output_contract,
        output_description="Typed, evidence-backed result that answers the requested operation without hidden effects.",
        renderer=renderer,
        package_ids=first["package_ids"] if first else (),
        host_binding=host_binding,
    )
    dependencies = _dependency_map(requirement, candidates, blueprint)
    return blueprint.model_copy(update={"dependency_ids": tuple(item.dependency_id for item in dependencies)})


def _rank(requirement: str) -> tuple[dict[str, Any], ...]:
    request_tokens = _tokens(requirement)
    ranked: list[dict[str, Any]] = []
    for descriptor in ACTIVE_CAPABILITY_DESCRIPTORS:
        record = _capability_record(descriptor)
        candidate_tokens = _tokens(
            " ".join(
                (
                    record["capability_id"],
                    record["purpose"],
                    record["input_contract"],
                    record["output_contract"],
                    record["family"],
                )
            )
        )
        overlap = request_tokens & candidate_tokens
        score = len(overlap) / max(1, len(request_tokens))
        if overlap:
            ranked.append(
                {
                    "capability_id": record["capability_id"],
                    "name": record["name"],
                    "family": record["family"],
                    "purpose": record["purpose"],
                    "input_contract": record["input_contract"],
                    "output_contract": record["output_contract"],
                    "implementation_class": record["implementation_class"],
                    "renderer": record["renderer"],
                    "package_ids": record["package_ids"],
                    "availability": record["availability"],
                    "score": round(score, 3),
                    "matched_terms": tuple(sorted(overlap)),
                }
            )
    return tuple(sorted(ranked, key=lambda item: (-item["score"], item["capability_id"]))[:6])


def _design_text(request: RequirementAssessmentRequest) -> str:
    user_parts = [item.content for item in request.conversation if item.role == "user"]
    user_parts.append(request.requirement)
    return "\n\n".join(user_parts)[-12000:]


def _deterministic_open_questions(
    design_text: str,
    user_turn_count: int,
) -> tuple[str, ...]:
    if user_turn_count < 2:
        return (
            "Which semantic data, point-in-time constraints and data-rights boundaries are required? Upstream capability formats may be adapted by the agent.",
            "What typed structured result should it return?",
            "Which existing or proposed capabilities should supply the data, and which dependencies must be developed first?",
        )
    normalized = design_text.casefold()
    questions: list[str] = []
    if not any(term in normalized for term in ("input", "data", "context", "source", "series", "portfolio")):
        questions.append("Which semantic data or governed context is required, regardless of its current upstream schema?")
    if not any(term in normalized for term in ("output", "result", "report", "chart", "table", "schema", "return")):
        questions.append("What exact typed result and readable presentation should the capability return?")
    return tuple(questions)


def _deterministic_quiz(question: str | None) -> DesignQuiz | None:
    if not question:
        return None
    normalized = question.casefold()
    if any(term in normalized for term in ("input", "data", "point-in-time", "rights")):
        options = (
            DesignQuizOption(label="Supplied context", answer="Use an immutable, validated context supplied by the calling workflow, with explicit as-of time and evidence references.", explanation="Best when an upstream workflow already assembles the eligible data."),
            DesignQuizOption(label="Local database", answer="Read a point-in-time slice from the governed local DuckDB data plane, with licensed sources kept read-only and look-ahead filters enforced.", explanation="Best for reproducible empirical analysis over registered local datasets."),
            DesignQuizOption(label="Registered provider", answer="Fetch data through a registered HTTP, API or MCP adapter, retaining provider, availability, rights and retrieval receipts.", explanation="Best when the required observation is not held locally."),
            DesignQuizOption(label="Experiment object", answer="Use only the isolated experiment's mutable objects or explicitly synthetic fixture data, clearly labelled and separated from empirical evidence.", explanation="Best for controlled simulations and development tests."),
        )
    elif any(term in normalized for term in ("result", "output", "render", "presentation")):
        options = (
            DesignQuizOption(label="Typed analysis", answer="Return a validated analytical result with metrics, evidence references, assumptions, warnings and no user-facing narrative.", explanation="Best for backend composition and downstream agents."),
            DesignQuizOption(label="Readable review", answer="Return a typed result plus a concise Markdown rendering that explains the material finding, evidence and limitations.", explanation="Best for direct human review."),
            DesignQuizOption(label="Dashboard component", answer="Return a renderer-neutral chart or table specification with data series, labels, provenance and interaction metadata.", explanation="Best for a reusable live dashboard component."),
            DesignQuizOption(label="Research artifact", answer="Return a multi-section, evidence-backed artifact contract that can accumulate models, tables, charts, methodology and conclusions.", explanation="Best for deeper report-form analysis."),
        )
    else:
        options = (
            DesignQuizOption(label="Deterministic Python", answer="Implement the operation as bounded deterministic Python with typed inputs, typed results and representative fixtures.", explanation="Best for calculations and transformations."),
            DesignQuizOption(label="DuckDB query", answer="Implement a read-only DuckDB operation over registered point-in-time views with row, column and temporal limits.", explanation="Best for governed local data retrieval."),
            DesignQuizOption(label="Registered adapter", answer="Implement the operation through a bounded HTTP/API or MCP adapter with schema validation, receipts and no undeclared effects.", explanation="Best for an external data or service integration."),
            DesignQuizOption(label="Model-backed", answer="Use a bounded quantitative model or agent-backed implementation, with explicit model receipts, evidence validation and human review.", explanation="Best when interpretation or complex modelling is essential."),
        )
    return DesignQuiz(question=question, options=options)


def _design_target(design_text: str) -> Literal["capability", "agent", "workflow", "dashboard", "report", "package"]:
    normalized = design_text.casefold()
    if any(term in normalized for term in ("design a workflow", "composable risk workflow", "agent graph", "multi-agent workflow", "orchestration")):
        return "workflow"
    if any(term in normalized for term in ("design an agent", "create an agent", "sub-agent", "langgraph agent")):
        return "agent"
    if _host_binding(design_text) is not None:
        return "capability"
    for target, terms in (
        ("workflow", ("workflow", "agent graph", "orchestration")),
        ("agent", ("agent", "sub-agent", "langgraph")),
        ("package", ("package", "analysis pack", "capability pack")),
    ):
        if any(term in normalized for term in terms):
            return target  # type: ignore[return-value]
    return "capability"


def _new_design_session_id() -> str:
    now = datetime.now(UTC).replace(microsecond=0)
    digest = hashlib.sha256(f"{now.isoformat()}:{time.time_ns()}".encode()).hexdigest()[:8]
    return f"cap-design-{now.strftime('%Y%m%dT%H%M%SZ')}-{digest}"


def assess_requirement(request: RequirementAssessmentRequest) -> RequirementAssessment:
    session_id = request.session_id or _new_design_session_id()
    design_text = _design_text(request)
    candidates = _rank(design_text)
    user_turn_count = 1 + sum(item.role == "user" for item in request.conversation)
    top = candidates[0]["score"] if candidates else 0
    second = candidates[1]["score"] if len(candidates) > 1 else 0
    requests_external_effect = any(
        term in design_text.casefold()
        for term in (
            "broker",
            "execute trade",
            "submit order",
            "external database write",
            "write changes directly into the external",
        )
    )
    requests_incubator_presentation = any(
        term in design_text.casefold()
        for term in ("dashboard", "report renderer", "render a report", "report studio")
    )
    if requests_incubator_presentation:
        recommendation = "blocked"
        rationale = (
            "Report and Dashboard presentation work is deferred under ADR-0009. "
            "Define the structured analytical output needed by the workflow instead."
        )
    elif requests_external_effect:
        recommendation = "blocked"
        rationale = "The requested external effect is outside the current research and development authority."
    elif top >= 0.48:
        recommendation = "reuse"
        rationale = "One available definition closely matches the requested outcome and contracts."
    elif top >= 0.24 and second >= 0.18:
        recommendation = "compose"
        rationale = "The requirement spans multiple existing bounded operations that should remain atomic."
    elif top >= 0.16:
        recommendation = "improve"
        rationale = "An existing capability covers part of the requirement but its contract needs a reviewed extension."
    else:
        recommendation = "new"
        rationale = "No existing capability provides sufficient semantic and contract coverage."
    blueprint = _blueprint(design_text, candidates)
    dependency_map = _dependency_map(design_text, candidates, blueprint)
    if (
        recommendation not in {"blocked", "new"}
        and blueprint.host_binding is not None
        and candidates
        and candidates[0]["renderer"] != blueprint.renderer
    ):
        recommendation = "compose"
        rationale = (
            "Existing capabilities can supply or calculate part of the result, but none provides the "
            "requested registered host form. Keep the analytical operations atomic and compose them "
            "with one hosted capability."
        )
    if recommendation in {"reuse", "improve"} and candidates:
        blueprint = blueprint.model_copy(
            update={
                "capability_id": candidates[0]["capability_id"],
                "display_name": candidates[0]["name"],
            }
        )
    if recommendation == "blocked" and requests_external_effect:
        blueprint = blueprint.model_copy(update={"effect_profile": "external_placeholder"})
    response = {
        "reuse": "A current capability appears sufficient. Review its exact input and output contract before reusing it.",
        "compose": "The requirement is best assembled from existing atomic capabilities rather than implemented as one large operation.",
        "improve": "The closest capability should be revised instead of creating a near-duplicate.",
        "new": "The Library does not currently cover this requirement. A new bounded capability proposal is justified.",
        "blocked": (
            "Presentation objects are in the post-thesis incubator; specify a structured analytical output instead."
            if requests_incubator_presentation
            else "The requested operation exceeds the current effect boundary and cannot be developed as executable functionality."
        ),
    }[recommendation]
    model_receipt: dict[str, Any] = {
        "provider": "none",
        "model": None,
        "input_tokens": 0,
        "output_tokens": 0,
        "reason": "deterministic reuse-first assessment",
    }
    open_questions = _deterministic_open_questions(design_text, user_turn_count)
    next_question = open_questions[0] if open_questions else None
    consensus_ready = user_turn_count >= 2 and not open_questions
    consensus_summary = (
        "The outcome, available implementation surface, input boundary, output contract and effect boundary are sufficiently defined for a design decision."
        if consensus_ready
        else "The design remains provisional until the feasibility questions are resolved."
    )
    intent: Literal["answer_question", "clarify", "plan", "feasibility_review", "synthesize"] = (
        "answer_question" if "?" in request.requirement else "clarify" if open_questions else "feasibility_review"
    )
    plan_steps = (
        "Search the Capability Library and packages for exact or composable coverage.",
        "Resolve input, output, implementation, effects and test boundaries.",
        "Record consensus before compiling a reviewable blueprint.",
    )
    quiz = _deterministic_quiz(next_question)
    design_target = _design_target(design_text)
    proposed_capability_ids = tuple(item["capability_id"] for item in candidates[:4])
    if request.use_llm:
        try:
            advice, primary_receipt = _live_design_advice(
                request.requirement,
                recommendation,
                rationale,
                candidates,
                blueprint,
                request.conversation,
                request.conclude,
            )
            response = advice.response
            rationale = advice.rationale
            blueprint = advice.blueprint
            inferred_host = _host_binding(design_text)
            if inferred_host is not None:
                blueprint = blueprint.model_copy(update={"host_binding": inferred_host})
            merged_dependencies = {item.dependency_id: item for item in dependency_map}
            merged_dependencies.update({item.dependency_id: item for item in advice.dependency_map})
            dependency_map = tuple(merged_dependencies.values())[:8]
            blueprint = blueprint.model_copy(
                update={"dependency_ids": tuple(item.dependency_id for item in dependency_map)}
            )
            open_questions = advice.open_questions
            next_question = advice.next_question
            consensus_ready = advice.consensus_ready and user_turn_count >= 2 and not open_questions
            consensus_summary = advice.consensus_summary
            intent = advice.intent
            plan_steps = advice.plan_steps
            design_target = advice.design_target
            if inferred_host is not None:
                design_target = "capability"
            proposed_capability_ids = tuple(
                item for item in advice.proposed_capability_ids if item in {candidate["capability_id"] for candidate in candidates}
            ) or proposed_capability_ids
            quiz = None
            quiz_receipt: dict[str, Any] = {}
            # An unresolved design question must always be answerable through the
            # four-option, editable quiz surface.  The advice model may classify
            # the turn as an explanation instead of a quiz, but that must not
            # remove the user's structured clarification path.
            if next_question:
                try:
                    quiz, quiz_receipt = _live_quiz_options(next_question, design_text, candidates)
                except Exception:
                    quiz = _deterministic_quiz(next_question)
            model_receipt = _combined_model_receipt(primary_receipt, quiz_receipt)
        except Exception as error:
            error_type = re.sub(r"[^A-Za-z0-9_-]", "_", type(error).__name__)[:64]
            response = (
                f"{response} Luna could not refine this assessment, so the validated "
                "deterministic blueprint is shown instead."
            )
            model_receipt = {
                "provider": "openai_responses",
                "model": COST_OPTIMIZED_LLM_MODEL,
                "status": "failed",
                "error_type": error_type,
                "input_tokens": 0,
                "output_tokens": 0,
                "reason": "LLM refinement failed; deterministic assessment retained",
            }
    if user_turn_count < 2:
        consensus_ready = False
        if not open_questions:
            open_questions = _deterministic_open_questions(design_text, user_turn_count)
            next_question = open_questions[0]
    discussion_status: Literal["refining", "consensus_ready", "concluded"]
    if request.conclude and consensus_ready:
        discussion_status = "concluded"
    elif consensus_ready:
        discussion_status = "consensus_ready"
    else:
        discussion_status = "refining"
        if request.conclude:
            response = f"{response} Consensus cannot be recorded while material design questions remain open."
    blueprint = blueprint.model_copy(
        update={"dependency_ids": tuple(item.dependency_id for item in dependency_map)}
    )
    assessment_digest = hashlib.sha256(
        json.dumps(
            {"requirement": design_text, "conversation": request.conversation, "candidates": candidates, "at": time.time_ns()},
            sort_keys=True,
            default=str,
        ).encode()
    ).hexdigest()[:12]
    return RequirementAssessment(
        assessment_id=f"assessment-{assessment_digest}",
        requirement=design_text,
        recommendation=recommendation,
        response=response,
        rationale=rationale,
        candidates=candidates,
        compact_candidate_count=len(candidates),
        total_library_count=len(ACTIVE_CAPABILITY_DESCRIPTORS),
        estimated_prompt_characters=sum(
            len(item["capability_id"]) + len(item["purpose"]) + 80 for item in candidates
        ) + sum(len(item.content) for item in request.conversation),
        blueprint=blueprint,
        model_receipt=model_receipt,
        discussion_status=discussion_status,
        open_questions=open_questions,
        next_question=next_question,
        consensus_summary=consensus_summary,
        user_turn_count=user_turn_count,
        intent=intent,
        plan_steps=plan_steps,
        quiz=quiz,
        design_target=design_target,
        proposed_capability_ids=proposed_capability_ids,
        dependency_map=dependency_map,
        session_id=session_id,
    )


class _Advice(StudioModel):
    response: str = Field(min_length=10, max_length=1200)
    rationale: str = Field(min_length=10, max_length=1200)
    blueprint: CapabilityBlueprint
    open_questions: tuple[str, ...] = Field(max_length=6)
    next_question: str | None
    consensus_ready: bool
    consensus_summary: str = Field(min_length=10, max_length=800)
    intent: Literal["answer_question", "clarify", "plan", "feasibility_review", "synthesize"]
    plan_steps: tuple[str, ...] = Field(max_length=6)
    quiz_needed: bool
    design_target: Literal["capability", "agent", "workflow", "dashboard", "report", "package"]
    proposed_capability_ids: tuple[str, ...] = Field(max_length=8)
    dependency_map: tuple[CapabilityDependency, ...] = Field(max_length=8)


class _QuizAdvice(StudioModel):
    question: str = Field(min_length=8, max_length=500)
    options: tuple[DesignQuizOption, ...] = Field(min_length=4, max_length=4)


def _strict_schema(model: type[BaseModel]) -> dict[str, Any]:
    schema = model.model_json_schema()

    def normalize(value: Any) -> None:
        if isinstance(value, dict):
            value.pop("default", None)
            if value.get("type") == "object" or "properties" in value:
                value["additionalProperties"] = False
                properties = value.get("properties")
                if isinstance(properties, dict):
                    value["required"] = list(properties)
            for child in value.values():
                normalize(child)
        elif isinstance(value, list):
            for child in value:
                normalize(child)

    normalize(schema)
    return schema


def _live_design_advice(
    requirement: str,
    recommendation: str,
    rationale: str,
    candidates: tuple[dict[str, Any], ...],
    blueprint: CapabilityBlueprint,
    conversation: tuple[DesignMessage, ...],
    conclude: bool,
) -> tuple[_Advice, dict[str, Any]]:
    key = _keychain_key(include_value=True)
    if not key:
        raise RuntimeError("OpenAI credential is unavailable")
    from openai import OpenAI

    compact = [
        {
            "id": item["capability_id"],
            "family": item["family"],
            "purpose": item["purpose"],
            "input": item["input_contract"],
            "output": item["output_contract"],
            "availability": item["availability"],
        }
        for item in candidates
    ]
    started = time.perf_counter()
    response = OpenAI(api_key=str(key)).responses.create(
        model=COST_OPTIMIZED_LLM_MODEL,
        store=False,
        tools=[],
        input=[
            {
                "role": "system",
                "content": [{
                    "type": "input_text",
                    "text": (
                        "You are the Capability Studio design partner. Conduct a multi-turn feasibility "
                        "discussion before allowing a design decision. Search and reuse the supplied internal "
                        "candidate definitions before proposing development. Ask one precise, high-value "
                        "question at a time about inputs, data rights and time semantics, output contract, "
                        "implementation route, effects, tests, composition or missing dependencies. Be strategically "
                        "helpful: explain the recommended path, distinguish design blockers from build dependencies, "
                        "and state what can safely be assumed. Treat semantically sufficient upstream capability "
                        "outputs as usable even when their current schemas differ; assume a bounded agent preparation "
                        "step can convert them into the target schema. Do not demand exact source formatting before "
                        "progressing. If semantic data or a required calculation is genuinely unavailable, add a "
                        "proposed_capability dependency and map what it depends on. Keep capabilities atomic. Do not "
                        "weaken effects, invent availability, authorize external writes, or place licensed data "
                        "in the blueprint. Set consensus_ready only when all material questions are resolved; "
                        "a request to conclude cannot override unresolved feasibility questions. The blueprint "
                        "is provisional and must not be treated as a saved proposal. Infer whether the mature "
                        "discussion targets a capability, agent, workflow, dashboard, report or analysis package. "
                        "A visible or programmatic form such as a dashboard component, report section, database "
                        "view/table, decision record, workflow event, artifact or local API remains part of one "
                        "CapabilityBlueprint through host_binding; do not separate form from function or hand "
                        "it off merely because it is hosted. "
                        "For non-capability targets, propose only IDs present in the supplied candidate set; the "
                        "result is a non-final handoff to the owning Studio. Return the strict schema."
                    ),
                }],
            },
            {
                "role": "user",
                "content": [{
                    "type": "input_text",
                    "text": json.dumps(
                        {
                            "requirement": requirement,
                            "conversation": [item.model_dump(mode="json") for item in conversation[-12:]],
                            "conclude_requested": conclude,
                            "deterministic_recommendation": recommendation,
                            "deterministic_rationale": rationale,
                            "compact_candidates": compact,
                            "draft_blueprint": blueprint.model_dump(mode="json"),
                            "registered_hosts": tuple(
                                item
                                for item in CAPABILITY_HOSTS
                                if item["host_id"] not in INCUBATOR_HOST_IDS
                            ),
                            "deterministic_dependency_map": [
                                item.model_dump(mode="json")
                                for item in _dependency_map(requirement, candidates, blueprint)
                            ],
                        },
                        sort_keys=True,
                    ),
                }],
            },
        ],
        text={"format": {"type": "json_schema", "name": "capability_design_advice", "strict": True, "schema": _strict_schema(_Advice)}},
        max_output_tokens=1900,
    )
    advice = _Advice.model_validate_json(response.output_text)
    usage = getattr(response, "usage", None)
    receipt = {
        "provider": "openai_responses",
        "model": getattr(response, "model", COST_OPTIMIZED_LLM_MODEL),
        "status": "completed",
        "intent": "design_reasoning",
        "response_id": getattr(response, "id", None),
        "input_tokens": int(getattr(usage, "input_tokens", 0) or 0),
        "output_tokens": int(getattr(usage, "output_tokens", 0) or 0),
        "elapsed_ms": round((time.perf_counter() - started) * 1000, 2),
        "store": False,
        "tools": [],
    }
    return advice, receipt


def _live_quiz_options(
    question: str,
    requirement: str,
    candidates: tuple[dict[str, Any], ...],
) -> tuple[DesignQuiz, dict[str, Any]]:
    key = _keychain_key(include_value=True)
    if not key:
        raise RuntimeError("OpenAI credential is unavailable")
    from openai import OpenAI

    started = time.perf_counter()
    response = OpenAI(api_key=str(key)).responses.create(
        model=COST_OPTIMIZED_LLM_MODEL,
        store=False,
        tools=[],
        input=[
            {
                "role": "system",
                "content": [{
                    "type": "input_text",
                    "text": (
                        "Create exactly four materially different, feasible answer options for one "
                        "Capability Studio clarification question. Each option must be a complete answer "
                        "the user can load into an editable text box. Keep each answer between 35 and 65 "
                        "words and each explanation to one short sentence. Finish every answer cleanly; "
                        "never abbreviate, trail off, or squeeze text to fit. Keep options grounded in the supplied "
                        "ServiceFabric capability candidates. Treat schema conversion by a bounded agent "
                        "preparation step as available; focus choices on semantic data, methodology, temporal "
                        "scope and genuine dependency gaps. Preserve read-only licensed data and "
                        "effect-free external boundaries. Do not repeat options or select one for the user."
                    ),
                }],
            },
            {
                "role": "user",
                "content": [{
                    "type": "input_text",
                    "text": json.dumps(
                        {
                            "question": question,
                            "design_requirement": requirement[-1800:],
                            "candidate_ids": [item["capability_id"] for item in candidates[:4]],
                        },
                        sort_keys=True,
                    ),
                }],
            },
        ],
        text={"format": {"type": "json_schema", "name": "capability_design_quiz", "strict": True, "schema": _strict_schema(_QuizAdvice)}},
        max_output_tokens=1500,
    )
    if getattr(response, "status", "completed") != "completed":
        raise RuntimeError("quiz option generation did not complete")
    advice = _QuizAdvice.model_validate_json(response.output_text)
    usage = getattr(response, "usage", None)
    receipt = {
        "provider": "openai_responses",
        "model": getattr(response, "model", COST_OPTIMIZED_LLM_MODEL),
        "status": "completed",
        "intent": "quiz_options",
        "response_id": getattr(response, "id", None),
        "input_tokens": int(getattr(usage, "input_tokens", 0) or 0),
        "output_tokens": int(getattr(usage, "output_tokens", 0) or 0),
        "elapsed_ms": round((time.perf_counter() - started) * 1000, 2),
        "store": False,
        "tools": [],
    }
    return DesignQuiz(question=advice.question, options=advice.options), receipt


def _combined_model_receipt(*receipts: dict[str, Any]) -> dict[str, Any]:
    calls = [item for item in receipts if item]
    if not calls:
        return {"provider": "none", "model": None, "input_tokens": 0, "output_tokens": 0, "calls": []}
    return {
        "provider": "openai_responses",
        "model": calls[0].get("model", COST_OPTIMIZED_LLM_MODEL),
        "status": "completed",
        "input_tokens": sum(int(item.get("input_tokens", 0) or 0) for item in calls),
        "output_tokens": sum(int(item.get("output_tokens", 0) or 0) for item in calls),
        "elapsed_ms": round(sum(float(item.get("elapsed_ms", 0) or 0) for item in calls), 2),
        "calls": calls,
        "store": False,
        "tools": [],
    }


def _json_write(path: Path, value: Any) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def _design_session_path(session_id: str) -> Path:
    if not re.fullmatch(DESIGN_SESSION_ID_PATTERN, session_id):
        raise ValueError("invalid capability design session identifier")
    path = (DESIGN_SESSION_ROOT / f"{session_id}.json").resolve()
    if path.parent != DESIGN_SESSION_ROOT.resolve():
        raise ValueError("capability design session path escapes its repository")
    return path


def save_design_session(
    request: RequirementAssessmentRequest,
    assessment: RequirementAssessment,
) -> dict[str, Any]:
    path = _design_session_path(assessment.session_id)
    existing: dict[str, Any] = {}
    if path.is_file() and not path.is_symlink():
        existing = json.loads(path.read_text(encoding="utf-8"))
    assistant_content = assessment.response
    if assessment.next_question and assessment.next_question not in assistant_content:
        assistant_content = f"{assistant_content}\n\n{assessment.next_question}"
    messages = [item.model_dump(mode="json") for item in request.conversation]
    messages.extend(
        (
            {"role": "user", "content": request.requirement},
            {"role": "assistant", "content": assistant_content},
        )
    )
    digest = hashlib.sha256(json.dumps(messages, sort_keys=True).encode()).hexdigest()
    if existing.get("turn_digest") == digest:
        return existing
    now = datetime.now(UTC).replace(microsecond=0).isoformat()
    parent_session_id = request.parent_session_id or existing.get("parent_session_id")
    root_session_id = existing.get("root_session_id") or parent_session_id or assessment.session_id
    session = {
        "schema_version": "portfolio-risk.capability-design-session/v1",
        "session_id": assessment.session_id,
        "title": _semantic_title(assessment.requirement),
        "created_at": existing.get("created_at", now),
        "updated_at": now,
        "revision": int(existing.get("revision", 0)) + 1,
        "status": assessment.discussion_status,
        "parent_session_id": parent_session_id,
        "root_session_id": root_session_id,
        "messages": messages,
        "assessment": assessment.model_dump(mode="json"),
        "dependency_map": [item.model_dump(mode="json") for item in assessment.dependency_map],
        "turn_digest": digest,
    }
    with _STORE_LOCK:
        _json_write(path, session)
    return session


def list_design_sessions() -> list[dict[str, Any]]:
    if not DESIGN_SESSION_ROOT.exists():
        return []
    values: list[dict[str, Any]] = []
    for path in DESIGN_SESSION_ROOT.glob("cap-design-*.json"):
        if path.is_symlink() or path.parent.resolve() != DESIGN_SESSION_ROOT.resolve():
            continue
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        values.append(
            {
                "session_id": value["session_id"],
                "title": value["title"],
                "updated_at": value["updated_at"],
                "revision": value["revision"],
                "status": value["status"],
                "parent_session_id": value.get("parent_session_id"),
                "dependency_count": len(value.get("dependency_map", [])),
            }
        )
    return sorted(values, key=lambda item: item["updated_at"], reverse=True)


def load_design_session(session_id: str) -> dict[str, Any]:
    path = _design_session_path(session_id)
    if not path.is_file() or path.is_symlink():
        raise FileNotFoundError(session_id)
    return json.loads(path.read_text(encoding="utf-8"))


def delete_design_session(session_id: str) -> dict[str, Any]:
    with _STORE_LOCK:
        path = _design_session_path(session_id)
        if not path.is_file() or path.is_symlink():
            raise FileNotFoundError(session_id)
        path.unlink()
    return {"deleted": True, "session_id": session_id, "recoverable": False}


def _proposal_path(proposal_id: str) -> Path:
    if not re.fullmatch(PROPOSAL_ID_PATTERN, proposal_id):
        raise ValueError("invalid capability proposal identifier")
    path = (PROPOSAL_ROOT / f"{proposal_id}.json").resolve()
    if path.parent != PROPOSAL_ROOT.resolve():
        raise ValueError("capability proposal path escapes its repository")
    return path


def compile_blueprint(request: ProposalCreateRequest) -> CapabilityBlueprint:
    assessment = request.assessment
    decision = request.decision
    blueprint = assessment.blueprint
    candidates = assessment.candidates
    if decision in {"reuse", "improve"} and candidates:
        blueprint = blueprint.model_copy(
            update={
                "capability_id": candidates[0]["capability_id"],
                "display_name": candidates[0]["name"],
                "effect_profile": "observe",
            }
        )
    elif decision in {"compose", "new"}:
        proposed = _blueprint(assessment.requirement, () if decision == "new" else candidates)
        blueprint = blueprint.model_copy(
            update={
                "capability_id": proposed.capability_id,
                "display_name": blueprint.display_name,
                "effect_profile": "observe",
            }
        )
    elif decision == "blocked":
        blueprint = blueprint.model_copy(update={"effect_profile": "external_placeholder"})
    return blueprint


def create_proposal(request: ProposalCreateRequest) -> dict[str, Any]:
    now = datetime.now(UTC).replace(microsecond=0)
    digest = hashlib.sha256(
        f"{request.assessment.assessment_id}:{request.decision}:{time.time_ns()}".encode()
    ).hexdigest()[:8]
    proposal_id = f"cap-proposal-{now.strftime('%Y%m%dT%H%M%SZ')}-{digest}"
    proposal = {
        "schema_version": "portfolio-risk.capability-proposal/v1",
        "proposal_id": proposal_id,
        "created_at": now.isoformat(),
        "updated_at": now.isoformat(),
        "status": "identified",
        "decision": request.decision,
        "requirement": request.assessment.requirement,
        "assessment_id": request.assessment.assessment_id,
        "rationale": request.assessment.rationale,
        "candidate_capability_ids": [item["capability_id"] for item in request.assessment.candidates],
        "dependency_map": [item.model_dump(mode="json") for item in request.assessment.dependency_map],
        "design_session_id": request.assessment.session_id,
        "blueprint": compile_blueprint(request).model_dump(mode="json"),
        "model_receipt": request.assessment.model_receipt,
        "events": [{"sequence": 1, "action": "identified", "actor": "local.user", "at": now.isoformat()}],
        "studio_codex": {"eligible": False, "reason": "human approval required", "build_brief": None},
    }
    with _STORE_LOCK:
        path = _proposal_path(proposal_id)
        if path.exists():
            raise ValueError("capability proposal already exists")
        _json_write(path, proposal)
    return proposal


def approve_blueprint(request: ProposalCreateRequest) -> dict[str, Any]:
    if request.assessment.discussion_status != "concluded":
        raise ValueError("capability design consensus is required before approval")
    proposal = create_proposal(request)
    action = "reject" if request.decision == "blocked" else "approve"
    return transition_proposal(
        proposal["proposal_id"],
        ProposalTransitionRequest(action=action, actor="local.human"),
    )


def delete_proposal(proposal_id: str) -> dict[str, Any]:
    with _STORE_LOCK:
        path = _proposal_path(proposal_id)
        if not path.is_file() or path.is_symlink():
            raise FileNotFoundError(proposal_id)
        path.unlink()
    return {"deleted": True, "proposal_id": proposal_id, "recoverable": False}


def _studio_design_proposal_path(proposal_id: str) -> Path:
    if not re.fullmatch(STUDIO_DESIGN_PROPOSAL_ID_PATTERN, proposal_id):
        raise ValueError("invalid studio design proposal identifier")
    path = (STUDIO_DESIGN_PROPOSAL_ROOT / f"{proposal_id}.json").resolve()
    if path.parent != STUDIO_DESIGN_PROPOSAL_ROOT.resolve():
        raise ValueError("studio design proposal path escapes its repository")
    return path


def create_studio_design_proposal(request: StudioDesignProposalRequest) -> dict[str, Any]:
    assessment = request.assessment
    if assessment.discussion_status != "concluded":
        raise ValueError("design consensus is required before Studio handoff")
    if assessment.design_target == "capability":
        raise ValueError("capability designs must use the reviewed blueprint approval flow")
    now = datetime.now(UTC).replace(microsecond=0)
    digest = hashlib.sha256(
        f"{assessment.assessment_id}:{assessment.design_target}:{time.time_ns()}".encode()
    ).hexdigest()[:8]
    proposal_id = f"studio-design-{now.strftime('%Y%m%dT%H%M%SZ')}-{digest}"
    proposal = {
        "schema_version": "portfolio-risk.studio-design-proposal/v1",
        "proposal_id": proposal_id,
        "created_at": now.isoformat(),
        "status": "proposed",
        "target_studio": assessment.design_target,
        "title": assessment.blueprint.display_name,
        "outcome": assessment.requirement,
        "consensus_summary": assessment.consensus_summary,
        "proposed_capability_ids": list(assessment.proposed_capability_ids),
        "limitations": [
            "This proposal does not create, publish or activate the target object.",
            "The owning Studio must validate its object contract and authority before approval.",
        ],
        "source_assessment_id": assessment.assessment_id,
        "actor": request.actor,
    }
    with _STORE_LOCK:
        _json_write(_studio_design_proposal_path(proposal_id), proposal)
    return proposal


def list_proposals() -> list[dict[str, Any]]:
    if not PROPOSAL_ROOT.exists():
        return []
    values: list[dict[str, Any]] = []
    for path in PROPOSAL_ROOT.glob("cap-proposal-*.json"):
        if path.is_symlink() or path.parent.resolve() != PROPOSAL_ROOT.resolve():
            continue
        try:
            values.append(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError):
            continue
    return sorted(values, key=lambda item: item["created_at"], reverse=True)


def transition_proposal(proposal_id: str, request: ProposalTransitionRequest) -> dict[str, Any]:
    transitions = {
        ("identified", "approve"): "human_approved",
        ("identified", "return_to_design"): "identified",
        ("human_approved", "prepare_codex"): "ready_for_studio_codex",
        ("human_approved", "return_to_design"): "identified",
        ("ready_for_studio_codex", "return_to_design"): "identified",
        ("identified", "reject"): "rejected",
        ("human_approved", "reject"): "rejected",
    }
    with _STORE_LOCK:
        path = _proposal_path(proposal_id)
        if not path.is_file() or path.is_symlink():
            raise FileNotFoundError(proposal_id)
        proposal = json.loads(path.read_text(encoding="utf-8"))
        key = (proposal["status"], request.action)
        if key not in transitions:
            raise ValueError(f"invalid capability proposal transition: {key[0]} -> {key[1]}")
        proposal["status"] = transitions[key]
        now = datetime.now(UTC).replace(microsecond=0).isoformat()
        proposal["updated_at"] = now
        proposal["events"].append({"sequence": len(proposal["events"]) + 1, "action": request.action, "actor": request.actor, "at": now})
        if proposal["status"] == "ready_for_studio_codex":
            proposal["studio_codex"] = {
                "eligible": True,
                "reason": "human-approved development proposal",
                "build_brief": _build_brief(proposal),
            }
        else:
            proposal["studio_codex"] = {
                "eligible": False,
                "reason": "human approval and explicit preparation are required",
                "build_brief": None,
            }
        _json_write(path, proposal)
        return proposal


def _build_brief(proposal: dict[str, Any]) -> str:
    blueprint = proposal["blueprint"]
    host = blueprint.get("host_binding")
    host_lines = (
        (
            f"Host: {host['host_id']} · {host['surface_kind']}",
            f"Framework: {host['framework']}",
            f"Host connection: {host['connection_contract']}",
            f"Host lifecycle: {', '.join(host['lifecycle_operations'])}",
        )
        if host
        else ("Host: backend-only typed result",)
    )
    dependency_lines = tuple(
        f"Dependency: {item['dependency_id']} · {item['status']} · build-blocking={str(item['blocks_build']).lower()}"
        for item in proposal.get("dependency_map", [])
    ) or ("Dependencies: none",)
    return "\n".join(
        (
            "# Studio-Codex capability development brief",
            f"Proposal: {proposal['proposal_id']}",
            f"Decision: {proposal['decision']}",
            f"Capability: {blueprint['capability_id']}",
            f"Outcome: {blueprint['outcome']}",
            f"Implementation: {blueprint['implementation_class']}",
            f"Output: {blueprint['output_contract']} rendered as {blueprint['renderer']}",
            *host_lines,
            *dependency_lines,
            f"Effect profile: {blueprint['effect_profile']}",
            "Use the servicefabric-capability-builder skill. Search existing definitions first. Reuse canonical CapabilityDefinition, OperationDefinition, schemas, EffectContract and invocation services. Do not edit vendor/servicefabric, write licensed/source databases, enable external effects, publish, merge or delete the worktree. Implement normal, failure and adversarial fixtures and return a candidate for human review.",
        )
    )


class _OperationResolver:
    def __init__(self, values: dict[str, OperationDefinition]):
        self.values = values

    def resolve_operation(self, operation_id: str) -> OperationDefinition:
        return self.values[operation_id]


class _AvailabilityResolver:
    def resolve_availability(self, capability_id: str) -> CapabilityAvailability:
        if capability_id not in DEFAULT_CAPABILITY_REGISTRY.capability_ids:
            return CapabilityAvailability(False, reason="local handler unavailable")
        return CapabilityAvailability(True, endpoint=f"local://{capability_id}")


class _SchemaResolver:
    def __init__(self, values: dict[str, dict[str, Any]]):
        self.values = values

    def resolve_schema(self, schema_ref: str) -> dict[str, Any]:
        return self.values[schema_ref]


class _LocalTransport:
    def invoke(self, request: Any) -> dict[str, Any]:
        request_type = CAPABILITY_REQUEST_TYPES.get(request.capability_id)
        if request_type is None:
            raise ValueError("local capability request contract is unavailable")
        typed_request = request_type.model_validate(request.input)
        result = DEFAULT_CAPABILITY_REGISTRY.invoke(request.capability_id, typed_request)
        if result.status != "succeeded":
            raise ValueError("local capability execution did not succeed")
        return result.model_dump(mode="json")


_CANONICAL_SERVICE: CapabilityInvocationService | None = None
_CANONICAL_DEFINITIONS: dict[str, CapabilityDefinition] = {}
_CANONICAL_OPERATIONS: dict[str, OperationDefinition] = {}
_CANONICAL_SCHEMAS: dict[str, dict[str, Any]] = {}


def _effect_contract(descriptor: Any) -> EffectContract:
    return EffectContract(
        effects=(
            EffectDeclaration(
                effect_type="none",
                target_category="returned_result",
                scope="Typed result returned to the caller; no system, experiment or external state change.",
                reversibility="not_applicable",
                verification_required=True,
                approval_required=False,
                idempotency_required=False,
            ),
        )
    )


def _canonical_service() -> CapabilityInvocationService:
    global _CANONICAL_SERVICE
    if _CANONICAL_SERVICE is not None:
        return _CANONICAL_SERVICE
    registry = CapabilityRegistry(CANONICAL_REGISTRY_ROOT)
    common_output_schema = {
        "$id": "portfolio-risk.capability-result.v1",
        "type": "object",
        "additionalProperties": True,
        "required": ["capability_id", "status", "evidence_references", "effects"],
        "properties": {
            "capability_id": {"type": "string"},
            "status": {"type": "string", "enum": ["succeeded"]},
            "evidence_references": {"type": "array"},
            "effects": {"type": "array", "maxItems": 0},
        },
    }
    for descriptor in ACTIVE_CAPABILITY_DESCRIPTORS:
        capability_id = descriptor.capability_id
        operation_id = f"{capability_id}.operation"
        request_type = CAPABILITY_REQUEST_TYPES.get(capability_id)
        request_schema_ref = f"{capability_id}.input.v1"
        response_schema_ref = "portfolio-risk.capability-result.v1"
        request_schema = request_type.model_json_schema() if request_type else {"type": "object"}
        request_schema["$id"] = request_schema_ref
        request_schema["x-servicefabric-semantic-role"] = descriptor.input_contract
        request_schema["x-servicefabric-source-database-policy"] = "read_only"
        _CANONICAL_SCHEMAS[request_schema_ref] = request_schema
        _CANONICAL_SCHEMAS[response_schema_ref] = common_output_schema
        definition = CapabilityDefinition(
            apiVersion="servicefabric.local/v1",
            kind="CapabilityDefinition",
            metadata=CapabilityMetadata(
                id=capability_id,
                title=capability_id.replace(".", " ").replace("_", " ").title(),
                domain=capability_id.split(".", 1)[0],
            ),
            spec=CapabilityDefinitionSpec(
                operationRef=operation_id,
                objective=descriptor.objective,
                capabilityClass=_family(capability_id, descriptor.objective),
                concepts=(capability_id, _family(capability_id, descriptor.objective)),
                expectedInputs=(descriptor.input_contract,),
                expectedOutputs=(descriptor.output_contract,),
                effects=_effect_contract(descriptor),
                suitableFor=(descriptor.objective,),
                unsuitableFor=("External financial effects or writes to licensed/source databases.",),
                qualityDimensions=("typed input", "evidence", "point-in-time safety", "effect disclosure"),
            ),
        )
        operation = OperationDefinition(
            operation_id=operation_id,
            version="1.0.0",
            application_ref="portfolio-risk-workbench",
            module_ref="risk-capabilities",
            interface_ref="local-capability-adapter",
            bindings=(
                HttpBinding(
                    binding_id=f"{operation_id}.local",
                    method="POST",
                    path=f"/internal/capabilities/{capability_id}",
                    request_schema_ref=request_schema_ref,
                    response_schema_ref=response_schema_ref,
                    timeout_seconds=120,
                ),
            ),
            name=definition.metadata.title,
            description=descriptor.objective,
        )
        registry.register(definition, "portfolio-risk-workbench")
        _CANONICAL_DEFINITIONS[capability_id] = definition
        _CANONICAL_OPERATIONS[operation_id] = operation
    _CANONICAL_SERVICE = CapabilityInvocationService(
        registry,
        _OperationResolver(_CANONICAL_OPERATIONS),
        _AvailabilityResolver(),
        _SchemaResolver(_CANONICAL_SCHEMAS),
        _LocalTransport(),
    )
    return _CANONICAL_SERVICE


def _fixture_capability_ids() -> set[str]:
    """Return active capabilities that have a real local implementation."""

    return {
        descriptor.capability_id
        for descriptor in CAPABILITY_DESCRIPTORS
        if descriptor.capability_id not in INCUBATOR_CAPABILITY_IDS
        and descriptor.capability_id in DEFAULT_CAPABILITY_REGISTRY.capability_ids
    }


def _invoke_canonical(capability_id: str, request: Any) -> dict[str, Any]:
    result = _canonical_service().invoke(
        CapabilityInvocationRequest(
            capability_id=capability_id,
            input=request.model_dump(mode="json"),
        )
    )
    return {
        "capability_id": result.capability_id,
        "operation_id": result.operation_id,
        "binding_id": result.binding_id,
        "output": result.output,
    }


TEST_CASE_TIME = datetime(2026, 7, 1, 16, tzinfo=UTC)


def _test_case_material() -> dict[str, Any]:
    digest = "sha256:" + "4" * 64
    domain_evidence = (
        MonitoringEvidence(
            evidence_id="capability-test-evidence",
            reference="test-case://capability-studio/fixed-v1",
            digest=digest,
        ),
    )
    references = (
        EvidenceReference(
            evidence_id="capability-test-evidence",
            reference="test-case://capability-studio/fixed-v1",
            source_type="reviewed_synthetic_test_case",
            digest=digest,
            description="Fixed reviewed inputs for local capability tests.",
        ),
    )
    portfolio = PortfolioSnapshot(
        snapshot_id="capability-test-portfolio",
        as_of=TEST_CASE_TIME,
        base_currency="USD",
        positions=(
            Position(
                instrument_id="instrument-orchid",
                quantity=Decimal("10"),
                price=Decimal("100"),
                market_value=Decimal("1000"),
                currency="USD",
            ),
        ),
    )
    context_request = __import__(
        "risk_domain.monitoring", fromlist=["PortfolioDataContextRequest"]
    ).PortfolioDataContextRequest(
        portfolio_snapshot_id=portfolio.snapshot_id,
        portfolio_snapshot=portfolio,
        market_dataset_snapshot_id="capability-test-market",
        market_dataset_revision="market-test-v1",
        market_dataset_retrieved_at=TEST_CASE_TIME - timedelta(hours=1),
        market_observations=(
            PointInTimeObservation(
                dataset_snapshot_id="capability-test-market",
                dataset_revision="market-test-v1",
                entity_id="entity-orchid",
                observed_at=TEST_CASE_TIME,
                available_at=TEST_CASE_TIME,
                retrieved_at=TEST_CASE_TIME - timedelta(hours=1),
                value=Decimal("100"),
                evidence=domain_evidence,
            ),
        ),
        crosswalk_snapshot_id="capability-test-crosswalk",
        crosswalk_dataset_revision="crosswalk-test-v1",
        crosswalk_retrieved_at=TEST_CASE_TIME - timedelta(days=1),
        crosswalk_records=(
            DateEffectiveMapping(
                crosswalk_snapshot_id="capability-test-crosswalk",
                crosswalk_dataset_revision="crosswalk-test-v1",
                source_instrument_id="instrument-orchid",
                target_entity_id="entity-orchid",
                effective_start=date(2020, 1, 1),
                open_ended=True,
                available_at=TEST_CASE_TIME - timedelta(days=1),
                evidence=domain_evidence,
            ),
        ),
        event_snapshot_id="capability-test-events",
        event_dataset_revision="events-test-v1",
        event_dataset_retrieved_at=TEST_CASE_TIME - timedelta(minutes=30),
        as_of=TEST_CASE_TIME,
        stale_data_maximum_age_seconds=86400,
        evidence=domain_evidence,
    )
    event_record = LocalEventRecord(
        provider_id="synthetic-provider",
        source_event_id="source-event-orchid",
        local_event_id="event-orchid",
        entity_id="entity-orchid",
        event_time=TEST_CASE_TIME - timedelta(hours=2),
        available_at=TEST_CASE_TIME - timedelta(hours=1),
        retrieved_at=TEST_CASE_TIME - timedelta(minutes=30),
        event_type="earnings_warning",
        relevance=Decimal("0.90"),
        sentiment=Decimal("-0.80"),
        novelty=Decimal("0.75"),
        amendment_state="original",
        publication_restriction=PublicationRestriction.SYNTHETIC_ONLY,
        synthetic=True,
        private=False,
        event_text="Reviewed synthetic earnings warning.",
        evidence=domain_evidence,
    )
    event_snapshot = EventDatasetSnapshot(
        snapshot_id="capability-test-events",
        provider_id="synthetic-provider",
        dataset_revision="events-test-v1",
        created_at=TEST_CASE_TIME - timedelta(minutes=30),
        source_digest=digest,
        mapping_manifest_id="capability-test-event-mapping",
        records=(event_record,),
        publication_restriction=PublicationRestriction.SYNTHETIC_ONLY,
        synthetic=True,
        private=False,
        public_evidence=domain_evidence,
    )
    event_query = EventQueryRequest(
        snapshot_id=event_snapshot.snapshot_id,
        as_of=TEST_CASE_TIME,
        entity_ids=("entity-orchid",),
        minimum_relevance=Decimal("0.60"),
    )
    policy = MonitoringPolicyVersion(
        policy_id="capability-test-policy",
        version=1,
        daily_percentage_move_threshold=Decimal("0.05"),
        concentration_threshold=Decimal("0.40"),
        event_relevance_minimum=Decimal("0.60"),
        negative_sentiment_threshold=Decimal("-0.50"),
        stale_data_maximum_age_seconds=86400,
        cadence="manual",
        cadence_metadata="Explicit fixed-test invocation.",
        reviewed_by="capability-test-reviewer",
        reviewed_at=TEST_CASE_TIME,
        evidence=domain_evidence,
    )
    metrics = (
        MonitoringMetric(
            metric="daily_return",
            value=Decimal("-0.10"),
            instrument_id="instrument-orchid",
            evidence=domain_evidence,
        ),
    )
    return {
        "domain_evidence": domain_evidence,
        "references": references,
        "portfolio": portfolio,
        "context_request": context_request,
        "event_snapshot": event_snapshot,
        "event_query": event_query,
        "policy": policy,
        "metrics": metrics,
    }


def _monitoring_preparation(material: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    references = material["references"]
    context_call = _invoke_canonical(
        "portfolio.data_context.create",
        PortfolioDataContextCapabilityRequest(
            request=material["context_request"], evidence_references=references
        ),
    )
    event_call = _invoke_canonical(
        "events.query.as_of",
        EventQueryCapabilityRequest(
            request=material["event_query"],
            snapshot=material["event_snapshot"],
            evidence_references=references,
        ),
    )
    context = PortfolioDataContext.model_validate(context_call["output"]["data"])
    event_result = CapabilityResult[EventQueryResult].model_validate(event_call["output"])
    policy_call = _invoke_canonical(
        "monitoring.policy.evaluate",
        PolicyEvaluationCapabilityRequest(
            request=PolicyEvaluationRequest(
                evaluation_id="capability-test-policy-evaluation",
                policy_version=material["policy"],
                context=context,
                evaluated_at=TEST_CASE_TIME,
                metrics=material["metrics"],
                events=event_signals_from_result(event_result, context=context),
                evidence=material["domain_evidence"],
            ),
            evidence_references=references,
        ),
    )
    policy_result = PolicyEvaluationResult.model_validate(policy_call["output"]["data"])
    alert_call = _invoke_canonical(
        "monitoring.alert.synthesize",
        MonitoringAlertSynthesisCapabilityRequest(
            policy_evaluation=policy_result,
            run_at=TEST_CASE_TIME,
            evidence=material["domain_evidence"],
            evidence_references=references,
        ),
    )
    return context_call, event_call, policy_call, alert_call, [context_call, event_call, policy_call, alert_call]


def _fixture_request(capability_id: str) -> tuple[Any, list[dict[str, Any]]]:
    snapshot, prices, evidence = _synthetic_fixture()
    evidence_tuple = (evidence,)
    limitations = ("Reviewed synthetic test case for isolated capability testing.",)
    horizon = AnalysisHorizon(label="daily", periods=1, expected_interval_seconds=86_400)
    preparation: list[dict[str, Any]] = []
    material = _test_case_material()
    references = material["references"]
    if capability_id == "portfolio.snapshot.create":
        observations = (
            NormalizedMarketRecord(
                instrument_id="instrument-orchid",
                identifier=InstrumentIdentifier(identifier_type="ticker", value="ORCHID"),
                observed_at=TEST_CASE_TIME,
                price=Decimal("100"),
            ),
        )
        return PortfolioSnapshotRequest(
            snapshot_id="capability-test-created-portfolio",
            as_of=TEST_CASE_TIME,
            positions=(PositionSpecification(instrument_id="instrument-orchid", quantity=Decimal("10")),),
            cash_balances=(CashBalance(currency="USD", amount=Decimal("100")),),
            normalized_observations=observations,
            evidence_references=references,
        ), preparation
    if capability_id == "market.anomaly.detect":
        observations = tuple(
            NormalizedMarketRecord(
                instrument_id="instrument-orchid",
                identifier=InstrumentIdentifier(identifier_type="ticker", value="ORCHID"),
                observed_at=TEST_CASE_TIME - timedelta(days=days_before),
                price=Decimal(price),
            )
            for days_before, price in ((3, "100"), (2, "101"), (1, "100"), (0, "70"))
        )
        return AnomalyDetectionRequest(
            normalized_observations=observations,
            percentage_threshold=Decimal("0.20"),
            evidence_references=references,
        ), preparation
    if capability_id == "market.anomaly.scan":
        values = ("-0.01", "0", "0.01", "-0.02", "0.02", "-0.10")
        return DetectorExecutionRequest(
            definition=DetectorDefinition(
                detector_id="capability-studio-robust-residual-z", version="1.0.0",
                kind=DetectorKind.ROBUST_RESIDUAL_Z_SCORE, lookback=5,
                threshold=Decimal("3"),
            ),
            observations=tuple(DetectorObservation(
                series_id="instrument-orchid", scope_type=SignalScope.INSTRUMENT,
                scope_id="instrument-orchid", observed_at=TEST_CASE_TIME - timedelta(days=5-index),
                available_at=TEST_CASE_TIME - timedelta(days=5-index),
                value=Decimal(value), benchmark_value=Decimal("0"),
                evidence_ids=(f"capability-test-market-row-{index}",),
                quality_flags=("reviewed_synthetic",),
            ) for index, value in enumerate(values)),
            as_of=TEST_CASE_TIME,
            evidence=(AnalysisEvidence(
                evidence_id=evidence.evidence_id, reference=evidence.reference,
                digest=evidence.digest, description=evidence.description,
            ),),
        ), preparation
    if capability_id == "news.event.classify":
        return NewsClassificationRequest(
            event=SyntheticNewsEvent(
                event_id="capability-test-news",
                instrument_id="instrument-orchid",
                headline="Synthetic issuer cuts guidance",
                sentiment="negative",
                relevance="high",
            ),
            evidence_references=references,
        ), preparation
    if capability_id == "alert.draft.synthesize":
        market_request, _ = _fixture_request("market.anomaly.detect")
        market_call = _invoke_canonical("market.anomaly.detect", market_request)
        snapshot_request, _ = _fixture_request("portfolio.snapshot.create")
        snapshot_call = _invoke_canonical("portfolio.snapshot.create", snapshot_request)
        created_snapshot = PortfolioSnapshot.model_validate(snapshot_call["output"]["data"])
        exposure_call = _invoke_canonical(
            "portfolio.exposure.summarize",
            ExposureSummaryRequest(
                snapshot_id="capability-test-exposure",
                portfolio_snapshot=created_snapshot,
                evidence_references=references,
            ),
        )
        news_request, _ = _fixture_request("news.event.classify")
        news_call = _invoke_canonical("news.event.classify", news_request)
        preparation.extend((market_call, snapshot_call, exposure_call, news_call))
        return AlertSynthesisRequest(
            market_output=CapabilityResult[Any].model_validate(market_call["output"]),
            exposure_output=CapabilityResult[Any].model_validate(exposure_call["output"]),
            news_output=CapabilityResult[Any].model_validate(news_call["output"]),
            evidence_references=references,
        ), preparation
    if capability_id == "alert.draft.review":
        synthesis_request, synthesis_preparation = _fixture_request("alert.draft.synthesize")
        synthesis_call = _invoke_canonical("alert.draft.synthesize", synthesis_request)
        preparation.extend((*synthesis_preparation, synthesis_call))
        draft = AlertDraft.model_validate(synthesis_call["output"]["data"])
        return AlertReviewRequest(
            draft=draft,
            decision_point=DecisionPoint(
                decision_id="capability-test-decision",
                alert_id=draft.alert_id,
                decision="approve",
                rationale="Reviewed synthetic test output is internally consistent.",
                human_reviewer_id="capability-test-reviewer",
            ),
            evidence_references=references,
        ), preparation
    if capability_id == "planning.knowledge.list_due":
        return KnowledgeDueRequest(
            catalog=load_seed_catalog(REPOSITORY_ROOT),
            offset_minutes=240,
            evidence_references=references,
        ), preparation
    if capability_id == "data.synthetic.ingest":
        observation = NormalizedMarketRecord(
            instrument_id="instrument-orchid",
            identifier=InstrumentIdentifier(identifier_type="ticker", value="ORCHID"),
            observed_at=TEST_CASE_TIME,
            price=Decimal("100"),
        )
        query = QuerySpec(
            dataset="market",
            instrument_ids=("instrument-orchid",),
            start_at=TEST_CASE_TIME,
            end_at=TEST_CASE_TIME,
        )
        dataset = DatasetSnapshot(
            snapshot_id="capability-test-dataset",
            created_at=TEST_CASE_TIME,
            records=(observation,),
        )
        return SyntheticIngestRequest(
            ingestion_run=IngestionRun(
                run_id="capability-test-ingestion",
                connector_id="reviewed-synthetic-local",
                query=query,
                started_at=TEST_CASE_TIME,
                completed_at=TEST_CASE_TIME,
                snapshot=dataset,
                validation=ValidationSummary(),
            ),
            evidence_references=references,
        ), preparation
    if capability_id == "risk.contribution.summarize":
        return ContributionSummaryRequest(
            analysis_id="capability-test-contribution",
            snapshot_id=snapshot.snapshot_id,
            values=tuple(
                ContributionValue(
                    instrument_id=item.instrument_id,
                    weight=Decimal("0.5"),
                    instrument_return=Decimal("0.04") if index == 0 else Decimal("-0.02"),
                )
                for index, item in enumerate(snapshot.positions[:2])
            ),
            portfolio_return=Decimal("0.01"),
            horizon=horizon,
            sample_period=SamplePeriod(start=TEST_CASE_TIME - timedelta(days=1), end=TEST_CASE_TIME),
            evidence=evidence_tuple,
            limitations=limitations,
        ), preparation
    if capability_id == "portfolio.data_context.create":
        return PortfolioDataContextCapabilityRequest(
            request=material["context_request"], evidence_references=references
        ), preparation
    if capability_id == "events.query.as_of":
        return EventQueryCapabilityRequest(
            request=material["event_query"],
            snapshot=material["event_snapshot"],
            evidence_references=references,
        ), preparation
    if capability_id in {"monitoring.policy.evaluate", "monitoring.alert.synthesize", "monitoring.run.contextual"}:
        context_call, event_call, policy_call, alert_call, calls = _monitoring_preparation(material)
        preparation.extend(calls)
        if capability_id == "monitoring.policy.evaluate":
            context = PortfolioDataContext.model_validate(context_call["output"]["data"])
            event_result = CapabilityResult[EventQueryResult].model_validate(event_call["output"])
            return PolicyEvaluationCapabilityRequest(
                request=PolicyEvaluationRequest(
                    evaluation_id="capability-test-policy-evaluation-target",
                    policy_version=material["policy"],
                    context=context,
                    evaluated_at=TEST_CASE_TIME,
                    metrics=material["metrics"],
                    events=event_signals_from_result(event_result, context=context),
                    evidence=material["domain_evidence"],
                ),
                evidence_references=references,
            ), preparation
        if capability_id == "monitoring.alert.synthesize":
            return MonitoringAlertSynthesisCapabilityRequest(
                policy_evaluation=PolicyEvaluationResult.model_validate(policy_call["output"]["data"]),
                run_at=TEST_CASE_TIME,
                evidence=material["domain_evidence"],
                evidence_references=references,
            ), preparation
        workflow = ContextualMonitoringWorkflowRequest(
            run_id="capability-test-contextual-run",
            context_request=material["context_request"],
            policy_version=material["policy"],
            evaluation_id="capability-test-contextual-evaluation",
            run_at=TEST_CASE_TIME,
            metrics=material["metrics"],
            event_query_request=material["event_query"],
            event_snapshot=material["event_snapshot"],
            evidence_references=references,
        )
        contextual = build_contextual_monitoring_request(
            workflow,
            context_result=CapabilityResult[PortfolioDataContext].model_validate(context_call["output"]),
            policy_result=CapabilityResult[PolicyEvaluationResult].model_validate(policy_call["output"]),
            event_result=CapabilityResult[EventQueryResult].model_validate(event_call["output"]),
            alert_result=CapabilityResult[MonitoringAlertDraft].model_validate(alert_call["output"]),
        )
        return ContextualMonitoringCapabilityRequest(
            request=contextual, evidence_references=references
        ), preparation
    if capability_id == "monitoring.replay":
        policy = material["policy"]
        specification = ReplaySpecification(
            specification_id="capability-test-replay-specification",
            start=TEST_CASE_TIME,
            end=TEST_CASE_TIME,
            cadence_seconds=86400,
            portfolio_snapshot_id=material["portfolio"].snapshot_id,
            market_dataset_snapshot_id="capability-test-market",
            market_dataset_revision="market-test-v1",
            crosswalk_snapshot_id="capability-test-crosswalk",
            crosswalk_dataset_revision="crosswalk-test-v1",
            event_snapshot_id="capability-test-events",
            event_dataset_revision="events-test-v1",
            policy_revision=policy.revision,
            lookback_window_seconds=86400,
            evaluation_horizon_seconds=86400,
            minimum_labelled_outcomes=1,
            labelled_outcome_method="reviewed synthetic threshold label",
            evidence=material["domain_evidence"],
        )
        return ReplayCapabilityRequest(
            run_id="capability-test-replay",
            specification=specification,
            policy_version=policy,
            step_inputs=(
                ReplayStepInput(
                    context_request=material["context_request"],
                    evaluation_id="capability-test-replay-step",
                    metrics=material["metrics"],
                    event_query_request=material["event_query"],
                    event_snapshot=material["event_snapshot"],
                ),
            ),
            evidence_references=references,
        ), preparation
    if capability_id == "monitoring.evaluate":
        replay_request, replay_preparation = _fixture_request("monitoring.replay")
        replay_call = _invoke_canonical("monitoring.replay", replay_request)
        preparation.extend((*replay_preparation, replay_call))
        replay = ReplayRun.model_validate(replay_call["output"]["data"])
        return ReplayEvaluationCapabilityRequest(
            evaluation_id="capability-test-replay-evaluation",
            replay_run=replay,
            outcomes=(
                OutcomeLabel(
                    outcome_id="capability-test-outcome",
                    instrument_id="instrument-orchid",
                    outcome_time=TEST_CASE_TIME + timedelta(days=1),
                    trigger_available_at=TEST_CASE_TIME,
                    label="material_loss",
                    method="reviewed synthetic threshold label",
                    evidence=material["domain_evidence"],
                ),
            ),
            evaluated_at=TEST_CASE_TIME + timedelta(days=1),
            evidence_references=references,
        ), preparation
    if capability_id == "portfolio.exposure.summarize":
        from risk_capabilities import EvidenceReference

        reference = EvidenceReference(
            evidence_id=evidence.evidence_id,
            reference=evidence.reference,
            source_type="reviewed_synthetic_fixture",
            digest=evidence.digest,
            description=evidence.description,
        )
        return ExposureSummaryRequest(
            snapshot_id="capability-studio:exposure",
            portfolio_snapshot=snapshot,
            evidence_references=(reference,),
        ), preparation
    if capability_id in {"risk.returns.simple", "risk.returns.log"}:
        return ReturnsRequest(
            analysis_id=f"capability-studio:{capability_id}",
            snapshot_id=snapshot.snapshot_id,
            prices=prices,
            horizon=horizon,
            evidence=evidence_tuple,
            limitations=limitations,
        ), preparation
    if capability_id == "risk.scenario.evaluate":
        return ScenarioRequest(
            analysis_id="capability-studio:scenario",
            portfolio=snapshot,
            shocks=tuple(
                ScenarioShock(instrument_id=item.instrument_id, percentage_shock=Decimal("-0.10"))
                for item in snapshot.positions
            ),
            horizon=AnalysisHorizon(label="instantaneous", periods=1),
            evidence=evidence_tuple,
            limitations=limitations,
        ), preparation
    returns_request = ReturnsRequest(
        analysis_id="capability-studio:prepared-returns",
        snapshot_id=snapshot.snapshot_id,
        prices=prices,
        horizon=horizon,
        evidence=evidence_tuple,
        limitations=limitations,
    )
    returns_call = _invoke_canonical("risk.returns.simple", returns_request)
    preparation.append(returns_call)
    from risk_analytics import HistoricalTailRiskResult, ReturnSeriesResult

    returns = ReturnSeriesResult.model_validate(returns_call["output"]["data"])
    common = {
        "analysis_id": f"capability-studio:{capability_id}",
        "returns": returns,
        "evidence": evidence_tuple,
        "limitations": limitations,
    }
    if capability_id == "risk.volatility.annualized":
        return VolatilityRequest(periods_per_year=252, **common), preparation
    if capability_id == "risk.drawdown.maximum":
        return DerivedReturnsRequest(**common), preparation
    if capability_id in {"risk.var.historical", "risk.expected_shortfall.historical"}:
        return HistoricalTailRiskRequest(confidence_level=Decimal("0.95"), **common), preparation
    if capability_id == "risk.report.render":
        tail_request = HistoricalTailRiskRequest(confidence_level=Decimal("0.95"), **common)
        tail_call = _invoke_canonical("risk.expected_shortfall.historical", tail_request)
        preparation.append(tail_call)
        tail = HistoricalTailRiskResult.model_validate(tail_call["output"]["data"])
        return ReportRequest(
            analysis_id="capability-studio:report",
            title="Capability Studio tail-risk evidence",
            result=tail,
        ), preparation
    raise ValueError("no fixed tests are available for this capability")


def _presentation(capability_id: str, output: dict[str, Any]) -> dict[str, Any]:
    data = output.get("data") or {}
    renderer = _renderer(capability_id, CAPABILITY_BY_ID[capability_id].output_contract)
    title = capability_id.replace(".", " ").replace("_", " ").title()
    base: dict[str, Any] = {
        "renderer": renderer,
        "title": title,
        "premise": CAPABILITY_BY_ID[capability_id].objective,
        "summary": "The fixed synthetic tests completed through the canonical ServiceFabric invocation boundary.",
    }
    if capability_id.startswith("risk.returns"):
        base["renderer"] = "time_series"
        base["series"] = [
            {"x": item["observed_at"], "y": float(item["value"])}
            for item in data.get("observations", [])
        ]
        base["metrics"] = [{"label": "Observations", "value": data.get("observation_count", 0), "format": "integer"}]
    elif capability_id == "portfolio.exposure.summarize":
        base["renderer"] = "table"
        base["columns"] = ("Instrument", "Market value", "Weight")
        base["rows"] = [
            (item["instrument_id"], item["market_value"], item["weight"])
            for item in data.get("position_exposures", [])
        ]
    elif capability_id == "risk.volatility.annualized":
        base["metrics"] = [{"label": "Annualized volatility", "value": data.get("annualized_volatility"), "format": "percent"}]
    elif capability_id == "risk.drawdown.maximum":
        base["metrics"] = [{"label": "Maximum drawdown", "value": data.get("maximum_drawdown"), "format": "percent"}]
    elif capability_id in {"risk.var.historical", "risk.expected_shortfall.historical"}:
        base["metrics"] = [
            {"label": "Historical VaR", "value": data.get("value_at_risk"), "format": "percent"},
            {"label": "Expected Shortfall", "value": data.get("expected_shortfall"), "format": "percent"},
            {"label": "Confidence", "value": data.get("confidence_level"), "format": "percent"},
        ]
    elif capability_id == "risk.scenario.evaluate":
        base["metrics"] = [{"label": "Portfolio P&L", "value": data.get("portfolio_profit_and_loss"), "format": "money"}]
        base["columns"] = ("Instrument", "Shock", "P&L")
        base["rows"] = [
            (item["instrument_id"], item["percentage_shock"], item["profit_and_loss"])
            for item in data.get("positions", [])
        ]
    elif capability_id == "risk.report.render":
        base["renderer"] = "markdown"
        base["markdown"] = data.get("markdown", "")
        base["html"] = data.get("html", "")
    else:
        base["renderer"] = "generic_schema"
        if isinstance(data, dict):
            base["fields"] = [
                {"name": key, "value": value}
                for key, value in list(data.items())[:12]
                if not isinstance(value, (dict, list))
            ]
        elif isinstance(data, list):
            base["fields"] = [{"name": "returned_items", "value": len(data)}]
        else:
            base["fields"] = [{"name": "result", "value": data}]
    return base


def _run_directory(run_id: str) -> Path:
    if not re.fullmatch(RUN_ID_PATTERN, run_id):
        raise ValueError("invalid capability run identifier")
    path = (RUN_REPOSITORY / run_id).resolve()
    if path.parent != RUN_REPOSITORY.resolve():
        raise ValueError("capability run path escapes its repository")
    return path


def execute_fixture(request: FixtureRunRequest) -> dict[str, Any]:
    if request.capability_id not in _fixture_capability_ids():
        raise ValueError("the selected capability has no executable implementation")
    stages: list[dict[str, Any]] = []

    def stage(stage_id: str, title: str, summary: str, started: float) -> None:
        stages.append({"sequence": len(stages) + 1, "stage_id": stage_id, "title": title, "status": "succeeded", "summary": summary, "elapsed_ms": round((time.perf_counter() - started) * 1000, 3)})

    started = time.perf_counter()
    request_value, preparation = _fixture_request(request.capability_id)
    stage("input", "Input received", "Reviewed synthetic data and evidence were frozen for this run.", started)
    prepared_at = time.perf_counter()
    stage("preparation", "Input prepared", f"{len(preparation)} prerequisite capability call(s) produced the target input.", prepared_at)
    validated_at = time.perf_counter()
    request_value.__class__.model_validate(request_value.model_dump(mode="python"))
    stage("input_validation", "Input validated", f"{request_value.__class__.__name__} passed strict typed validation.", validated_at)
    resolution_at = time.perf_counter()
    _canonical_service()
    stage("resolution", "Capability resolved", "Exact source-reviewed definition, local operation and binding resolved; no substitution.", resolution_at)
    execution_at = time.perf_counter()
    invocation = _invoke_canonical(request.capability_id, request_value)
    stage("execution", "Capability executed", f"{invocation['operation_id']} returned a successful effect-free result.", execution_at)
    output_at = time.perf_counter()
    output = invocation["output"]
    if output.get("effects"):
        raise ValueError("capability test unexpectedly produced effects")
    stage("output_validation", "Output validated", "Canonical response schema and local typed result validation passed.", output_at)
    render_at = time.perf_counter()
    presentation = _presentation(request.capability_id, output)
    stage("presentation", "Presentation rendered", f"The {presentation['renderer']} adapter created a readable review model.", render_at)
    now = datetime.now(UTC).replace(microsecond=0)
    digest = hashlib.sha256(f"{request.capability_id}:{now.isoformat()}:{time.time_ns()}".encode()).hexdigest()[:8]
    run_id = f"cap-run-{now.strftime('%Y%m%dT%H%M%SZ')}-{digest}"
    directory = _run_directory(run_id)
    directory.mkdir(mode=0o700, parents=True, exist_ok=False)
    resolution = {
        "policy": "exact_first_explicit_compatible_substitution",
        "requested_capability_id": request.capability_id,
        "resolved_capability_id": invocation["capability_id"],
        "operation_id": invocation["operation_id"],
        "binding_id": invocation["binding_id"],
        "substitution": None,
        "canonical_servicefabric_invocation": True,
    }
    effect_review = {
        "declared": "observe",
        "executed": [],
        "system_object_writes": [],
        "experiment_object_writes": [],
        "external_effects": "disabled_placeholder",
        "licensed_source_database": "read_only",
    }
    fixed_tests = (
        {"test_id": "input_contract", "name": "Input contract", "status": "passed", "evidence": f"{request_value.__class__.__name__} accepted the fixed input."},
        {"test_id": "registry_resolution", "name": "Registry resolution", "status": "passed", "evidence": f"{invocation['capability_id']} resolved without substitution."},
        {"test_id": "execution", "name": "Execution", "status": "passed", "evidence": f"{invocation['operation_id']} completed successfully."},
        {"test_id": "output_contract", "name": "Output contract", "status": "passed", "evidence": "The declared output contract passed validation."},
        {"test_id": "effect_boundary", "name": "Effect boundary", "status": "passed", "evidence": "No undeclared effect was produced."},
    )
    payloads = {
        "input.json": request_value.model_dump(mode="json"),
        "preparation.json": preparation,
        "resolution.json": resolution,
        "result.json": output,
        "presentation.json": presentation,
        "stages.json": stages,
        "effect-review.json": effect_review,
        "fixed-tests.json": fixed_tests,
        "validation.json": {"valid": True, "passed": len(fixed_tests), "required": len(fixed_tests), "tests": fixed_tests, "input_contract": request_value.__class__.__name__, "output_contract": CAPABILITY_BY_ID[request.capability_id].output_contract},
    }
    for name, value in payloads.items():
        _json_write(directory / name, value)
    manifest = {
        "schema_version": "portfolio-risk.capability-fixture-run/v1",
        "run_id": run_id,
        "created_at": now.isoformat(),
        "capability_id": request.capability_id,
        "status": "completed",
        "data_truth": "reviewed_synthetic",
        "renderer": presentation["renderer"],
        "canonical_servicefabric_invocation": True,
        "human_review_required": True,
        "effects": [],
        "elapsed_ms": round((time.perf_counter() - started) * 1000, 2),
        "folder": str(directory),
        "files": [],
    }
    _json_write(directory / "manifest.json", manifest)
    manifest["files"] = [
        {"name": path.name, "bytes": path.stat().st_size, "kind": path.suffix.removeprefix(".")}
        for path in sorted(directory.iterdir())
    ]
    _json_write(directory / "manifest.json", manifest)
    return load_fixture_run(run_id)


def list_fixture_runs() -> list[dict[str, Any]]:
    if not RUN_REPOSITORY.exists():
        return []
    result = []
    for path in RUN_REPOSITORY.glob("cap-run-*"):
        try:
            result.append(json.loads((path / "manifest.json").read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError):
            continue
    return sorted(result, key=lambda item: item["created_at"], reverse=True)


def load_fixture_run(run_id: str) -> dict[str, Any]:
    directory = _run_directory(run_id)
    if not directory.is_dir():
        raise FileNotFoundError(run_id)
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    contents: dict[str, Any] = {}
    for item in manifest["files"]:
        path = (directory / item["name"]).resolve()
        if path.parent == directory and path.is_file() and path.suffix == ".json":
            contents[path.name] = json.loads(path.read_text(encoding="utf-8"))
    contents["manifest.json"] = manifest
    return {"manifest": manifest, "contents": contents}


def delete_fixture_run(run_id: str) -> dict[str, Any]:
    directory = _run_directory(run_id)
    if not directory.is_dir():
        raise FileNotFoundError(run_id)
    shutil.rmtree(directory)
    return {"deleted": True, "run_id": run_id, "recoverable": False}
    AlertDraft,
    AlertReviewRequest,
    AlertSynthesisRequest,
    AnomalyDetectionRequest,
    CapabilityResult,
    ContributionSummaryRequest,
    ContributionValue,
    DecisionPoint,
    EventQueryCapabilityRequest,
    KnowledgeDueRequest,
    MonitoringAlertSynthesisCapabilityRequest,
    NewsClassificationRequest,
    PolicyEvaluationCapabilityRequest,
    PortfolioDataContextCapabilityRequest,
    PortfolioSnapshotRequest,
    PositionSpecification,
    ReplayCapabilityRequest,
    ReplayEvaluationCapabilityRequest,
    ReplayStepInput,
    SyntheticIngestRequest,
    SyntheticNewsEvent,
