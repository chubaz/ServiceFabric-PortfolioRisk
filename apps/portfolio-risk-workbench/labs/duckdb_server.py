"""Local read-only CRSP/Compustat query service for the thesis prototype."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import re
import statistics
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Literal

import duckdb
import uvicorn
import yaml
from fastapi import FastAPI, HTTPException, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator, model_validator

from agent_studio import (
    AgentBlueprint,
    BlueprintAdviceRequest,
    BlueprintPlanRequest,
    BlueprintRefineRequest,
    BlueprintReviewRequest,
    CompileRequest,
    COST_OPTIMIZED_LLM_MODEL,
    OutputPassRunRequest,
    RUN_ROOT,
    RunRequest,
    SectionPlanRequest,
    advise_blueprint,
    agent_development_history,
    agent_templates as all_agent_templates,
    capability_platform_manifest,
    compile_blueprint,
    _keychain_key,
    _scenario_context,
    historically_calibrated_synthetic_context,
    list_agent_runs,
    load_agent_run,
    plan_blueprint,
    refine_blueprint,
    plan_blueprint_section,
    review_blueprint_configuration,
    run_blueprint,
    run_output_pass,
    static_system_agent_fixture,
    runtime_status,
    synthetic_behavior_provenance,
)
from workflow_cycle_runtime import workflow_cycle_manager
from registry_sources import (
    discover_registry_projections,
    discovered_payload,
    document_payload,
    registry_store,
)
from artifact_repository import artifact_store, catalogue_payload, record_payload
from experiment_workspace import (
    catalogue_payload as experiment_catalogue_payload,
    experiment_store,
    record_payload as experiment_record_payload,
    set_payload as experiment_set_payload,
)
from experiment_run_audit import (
    RunAcceptanceRequest,
    RunComparisonRequest,
    catalogue_payload as run_audit_catalogue_payload,
    comparison_payload as run_comparison_payload,
    record_acceptance as record_run_acceptance,
)
from fixture_context_runtime import (
    calibration_fixture_payload,
    resolve_calibration_fixture,
)
from decision_review import (
    catalogue_payload as decision_catalogue_payload,
    decision_store,
    due_diligence_payload as decision_due_diligence_payload,
    record_payload as decision_record_payload,
)
from risk_analysis_package_runtime import (
    PackageRunRequest,
    delete_package_run as delete_risk_analysis_package_run,
    execute_package as execute_risk_analysis_package,
    list_package_runs as list_risk_analysis_package_runs,
    load_package_run as load_risk_analysis_package_run,
)
from capability_studio import (
    FixtureRunRequest as CapabilityFixtureRunRequest,
    ProposalCreateRequest as CapabilityProposalCreateRequest,
    ProposalTransitionRequest as CapabilityProposalTransitionRequest,
    RequirementAssessmentRequest as CapabilityAssessmentRequest,
    StudioDesignProposalRequest,
    approve_blueprint as approve_capability_blueprint,
    assess_requirement as assess_capability_requirement,
    capability_catalogue,
    compile_blueprint as compile_capability_blueprint,
    create_proposal as create_capability_proposal,
    create_studio_design_proposal,
    delete_fixture_run as delete_capability_fixture_run,
    delete_design_session as delete_capability_design_session,
    delete_proposal as delete_capability_proposal,
    execute_fixture as execute_capability_fixture,
    list_design_sessions as list_capability_design_sessions,
    list_fixture_runs as list_capability_fixture_runs,
    list_proposals as list_capability_proposals,
    load_design_session as load_capability_design_session,
    load_fixture_run as load_capability_fixture_run,
    save_design_session as save_capability_design_session,
    transition_proposal as transition_capability_proposal,
)
from mandate_studio import (
    MandateDesignPreviewRequest,
    MandateRegistrationRequest,
    MandateValidationRequest,
    catalogue as mandate_studio_catalogue_data,
    design_preview as prepare_mandate_design_preview,
    mandate_bundle,
    validate_bundle as validate_mandate_bundle,
)
from mandate_application import (
    MandateApplicationRequest,
    catalogue as mandate_application_catalogue_data,
    run as run_mandate_application,
)
from studio_codex import (
    CodexApprovalRequest,
    CodexProposalApprovalRequest,
    CodexProposalRequest,
    CodexSessionRequest,
    CodexTurnRequest,
    studio_codex_manager,
)
from risk_artifacts import (
    ArtifactKind,
    ArtifactManifest,
    ArtifactConflict,
    ArtifactLifecycleState,
    ArtifactNotFound,
    DataTruthClass,
    LegacyRunInvalid,
    PreviewMode,
    PublicationState,
    RetentionClass,
    RightsState,
    compile_legacy_run,
    file_manifest,
    preview_legacy_run,
)
from risk_registry import (
    AssetKind,
    LifecycleState,
    RegistryConflict,
    RegistryIdentity,
    RegistryNotFound,
)
from risk_experiments import (
    ArchitectureMappingContext,
    ArchitectureMappingError,
    GraphExecutionEnvelope,
    DataTruth,
    ExperimentBudget,
    ExperimentConflict,
    ExperimentDefinition,
    ExperimentNotFound,
    ExperimentSet,
    ExperimentState,
    PresentationMode,
    SourceBinding,
    TemporalWindow,
    analyse_counterfactual_batch,
    canonical_digest,
    counterfactual_design_map,
    dimension_catalogue as counterfactual_dimension_catalogue,
    finalize_agent_graph_execution,
    finalize_single_agent_execution,
)
from risk_agents import AgentExecutionEnvelope, AgentStructuredOutput
from run_trace_runtime import create_calibration_run_trace, run_trace_payload
from experimental_program_runtime import experimental_program_payload
from case_discovery_runtime import signal_preview_payload
from case_labelling_runtime import (
    ContextPreparationRequest,
    ContextReadinessRequest,
    ContextReviewRequest,
    ContextWorkPlanRequest,
    LabelStudyRequest,
    LabelReviewRequest,
    LabellingBatchRequest,
    SignalAnnotationRequest,
    create_labelling_batch,
    context_source_readiness,
    labelling_batch_payload,
    list_labelling_batches,
    prepare_context_work,
    record_signal_annotation,
    review_prepared_context,
    review_signal_annotation,
    study_review_unit,
    save_context_work_plan,
    validate_context_work_plan,
)
from gold_case_runtime import (
    ExperimentalCaseCompileRequest,
    GoldPreparationRequest,
    GoldReviewRequest,
    compile_gold_experimental_case,
    gold_work_payload,
    prepare_gold_reference,
    review_gold_reference,
)
from matched_run_runtime import (
    MatchedRunCompileRequest, compile_matched_plan, get_matched_plan,
    matched_run_setup,
)
from case_replay_runtime import case_replay_preview
from trajectory_execution_runtime import (
    execute_trajectory_cell, get_trajectory_result, list_trajectory_results,
)
from trajectory_evaluation_runtime import evaluate_matched_matrix
from reproducibility_runtime import (
    archive_reproducibility_bundle, create_reproducibility_bundle,
    list_reproducibility_bundles, open_reproducibility_bundle,
    remove_reproducibility_bundle, restore_reproducibility_bundle,
    verify_reproducibility_bundle,
)
from risk_experiments import (
    ContextWorkConflict, ContextWorkNotFound, GoldCaseConflict, GoldCaseNotFound,
    LabelProductionConflict, LabelProductionNotFound, MatchedRunConflict,
    MatchedRunNotFound, ReproducibilityConflict, ReproducibilityNotFound,
    TrajectoryNotFound,
)
from historical_replay_runtime import (
    HistoricalReplayError,
    professor_demo_definition,
    professor_demo_preflight,
    run_replay as run_historical_replay,
    setup_payload as historical_replay_setup_payload,
)
from risk_reports import (
    MarkdownReport,
    compose_daily_risk_report,
    default_daily_risk_plan,
    render_report,
    report_markdown,
    validate_report,
    with_rendered_html,
)
from risk_analytics import RISK_ANALYSIS_PACKAGES
from risk_decisions import (
    DecisionConflict as DecisionReviewConflict,
    DecisionNotFound as DecisionReviewNotFound,
    DecisionOutcome,
    DueDiligenceCapability,
    run_due_diligence,
    resolve as resolve_decision_record,
)


SQL_AGENT_MODEL = COST_OPTIMIZED_LLM_MODEL
SQL_AGENT_REASONING_EFFORT = "low"
MAX_QUERY_ROWS = 10_000
MAX_QUERY_COLUMNS = 200
EXPERIMENT_ELIGIBLE_REGISTRY_STATES = {
    LifecycleState.CANDIDATE,
    LifecycleState.VALIDATED,
    LifecycleState.PUBLISHED,
}
INCUBATOR_ASSET_KINDS = {AssetKind.REPORT, AssetKind.DASHBOARD}
QUERY_TIMEOUT_SECONDS = 20

LAB_RUNTIME_BOUNDARY: dict[str, Any] = {
    "profile": {
        "id": "development",
        "label": "Development",
        "development_controls": True,
    },
    "external_effects": "disabled",
    "views": {
        "dataset.live": {
            "data": "Licensed local historical data · query-specific point-in-time checks",
            "authority": "Read-only · no synthetic fallback · external effects prohibited",
            "persistence": "Unsaved browser result · CSV export is not published",
        },
        "dataset.synthetic": {
            "data": "Synthetic behavior fixture · not empirical evidence",
            "authority": "Read-only test path · external effects prohibited",
            "persistence": "Unsaved browser result · not a registry asset",
        },
        "portfolio": {
            "data": "Instrument origin shown in the builder · verify before use",
            "authority": "Prototype constraints only · no mandate authority",
            "persistence": "Browser-local draft · not published",
        },
        "agent.synthetic_behavior_sample": {
            "data": "Controlled synthetic fixture · fixed formula · no empirical calibration",
            "authority": "Findings and proposals only · effects none",
            "persistence": "Temporary review queue · explicit Artifact Repository retention",
        },
        "agent.historically_calibrated_synthetic": {
            "data": "Synthetic path fitted on licensed in-sample aggregates · OOS window reserved · licensed rows not retained",
            "authority": "Findings and proposals only · effects none",
            "persistence": "Temporary review queue · retained comparisons are rights-restricted artifacts",
        },
        "agent.real_duckdb": {
            "data": "Licensed local historical data · point-in-time qualified per run",
            "authority": "Model interpretation is effect-free · review required",
            "persistence": "Temporary review queue · explicit rights-restricted Artifact Repository retention",
        },
        "graph": {
            "data": "Browser-local agent drafts and registered catalogue previews",
            "authority": "Compiled plan preview · not registered or executable",
            "persistence": "Browser-local draft · not published",
        },
        "system": {
            "data": "Canonical sources and saved registry metadata · no run output is treated as a definition",
            "authority": "Author, isolate-test and govern reusable definitions · external effects prohibited",
            "persistence": "Saved definitions use the local versioned Registry; browser drafts remain explicitly unsaved",
        },
        "studio": {
            "data": "Canonical source definitions, Registry metadata and browser-local Studio drafts",
            "authority": "Development-only Studio–Codex · approved proposal IDs · worktree-scoped writes · human command review",
            "persistence": "Blueprint proposals and Codex receipts persist locally · Registry admission and merge remain separate",
        },
        "dictionary": {
            "data": "Platform vocabulary projected by the local application",
            "authority": "Read-only reference",
            "persistence": "Versioned with the application architecture",
        },
        "application": {
            "data": "Explicit fixture context plus saved, versioned system definitions",
            "authority": "Effect-free isolated object and agent testing · no code mutation or external effects",
            "persistence": "Run work products are temporary until separately retained as artifacts",
        },
        "registry": {
            "data": "Existing definitions · indexed metadata points to canonical sources",
            "authority": "Local lifecycle review only · no financial effects",
            "persistence": "Persistent local development registry · not production publication",
        },
        "decisions": {
            "data": "Immutable findings, proposals, evidence references and supplemental context revisions",
            "authority": "Human review only · D1 recommendation · portfolio and external effects prohibited",
            "persistence": "Persistent local Decision Repository · lifecycle and consequence receipts retained",
        },
        "decision-diligence": {
            "data": "Declared proposal references · supplemental analysis is truth-labelled and point-in-time bound",
            "authority": "Human-built temporary workflow · no decision, publication, portfolio or external effect",
            "persistence": "Runs, step receipts, evidence and candidate revisions retained in the Decision Repository",
        },
        "artifacts": {
            "data": "Retained generated outputs · data truth disclosed per record",
            "authority": "Browse and govern local artifacts only · execution and external effects prohibited",
            "persistence": "Content-addressed local repository · outside Git · not production publication",
        },
        "experiments": {
            "data": "Immutable source revisions and saved registry definitions with explicit real/synthetic/simulated declarations",
            "authority": "Local research orchestration only · external effects prohibited",
            "persistence": "Restart-safe experiment metadata outside Git · outputs remain separate artifacts",
        },
        "cycle": {
            "data": "Mixed · licensed daily anchors + simulated seeded intraday",
            "authority": "Findings and decision proposals only · effects none",
            "persistence": "In-memory session · lost when the service restarts",
        },
        "full": {
            "data": "Synthetic browser experiment · selected inputs must be inspected",
            "authority": "Simulated PortfolioEvents only · external effects prohibited",
            "persistence": "Unsaved browser state · not persistent",
        },
    },
}

# Luna receives a deliberately small, question-specific projection of the physical
# catalog.  The Parquet files remain fully queryable by DuckDB, while routine model
# calls avoid sending the 1,500+ mostly cryptic Compustat field names on every turn.
SQL_TABLE_HINTS: dict[str, tuple[str, ...]] = {
    "stocknames": (
        "company", "companies", "company name", "security name", "ticker",
        "listing", "exchange", "cusip", "sic", "share class", "identity",
    ),
    "dsf": (
        "daily", "day", "price", "return", "volume", "bid", "ask", "trade",
        "market data", "shares outstanding",
    ),
    "msf": (
        "monthly", "month", "monthly price", "monthly return", "monthly volume",
    ),
    "funda": (
        "annual", "yearly", "fiscal year", "fundamental", "fundamentals",
        "financial statement", "assets", "liabilities", "revenue", "sales",
        "income", "profit", "cash", "debt", "ebit", "ebitda", "capex",
        "research and development", "compustat",
    ),
    "fundq": (
        "quarter", "quarterly", "earnings", "fiscal quarter", "report date",
        "assets", "liabilities", "revenue", "sales", "income", "cash", "debt",
    ),
    "ccm_lookup": (
        "sector", "industry", "gics", "naics", "classification", "map", "mapping",
        "company lookup", "gvkey", "permno", "crsp compustat",
    ),
    "ccmxpf_linktable": (
        "link history", "link table", "link type", "link primary", "point in time link",
    ),
    "dsedelist": (
        "delist", "delisted", "delisting", "delisting return", "delisting code",
    ),
}

SQL_BASE_COLUMNS: dict[str, tuple[str, ...]] = {
    "stocknames": (
        "permno", "permco", "namedt", "nameenddt", "ticker", "comnam", "cusip",
        "ncusip", "exchcd", "shrcd", "siccd",
    ),
    "dsf": (
        "permno", "permco", "date", "prc", "openprc", "ret", "retx", "vol",
        "shrout", "bid", "ask", "bidlo", "askhi", "numtrd", "cfacpr", "cfacshr",
    ),
    "msf": (
        "permno", "permco", "date", "prc", "altprc", "ret", "retx", "vol",
        "shrout", "bid", "ask", "bidlo", "askhi", "spread", "cfacpr", "cfacshr",
    ),
    "funda": (
        "gvkey", "datadate", "fyear", "fyr", "tic", "cusip", "conm", "indfmt",
        "consol", "popsrc", "datafmt", "curcd", "costat",
    ),
    "fundq": (
        "gvkey", "datadate", "fyearq", "fqtr", "fyr", "tic", "cusip", "conm",
        "rdq", "fdateq", "indfmt", "consol", "popsrc", "datafmt", "curcdq",
    ),
    "ccm_lookup": (
        "gvkey", "lpermno", "lpermco", "linkdt", "linkenddt", "conm", "tic",
        "cusip", "cik", "sic", "naics", "gind", "gsubind", "year1", "year2",
    ),
    "ccmxpf_linktable": (
        "gvkey", "lpermno", "lpermco", "linkdt", "linkenddt", "linkprim",
        "linktype", "usedflag", "liid",
    ),
    "dsedelist": (
        "permno", "permco", "dlstdt", "dlstcd", "dlret", "dlretx", "dlprc",
        "dlamt", "nwperm", "nwcomp", "nextdt", "cusip",
    ),
}

SQL_METRIC_COLUMNS: dict[str, tuple[str, str]] = {
    "assets": ("at", "atq"),
    "total assets": ("at", "atq"),
    "liabilities": ("lt", "ltq"),
    "total liabilities": ("lt", "ltq"),
    "revenue": ("revt", "revtq"),
    "sales": ("sale", "saleq"),
    "net income": ("ni", "niq"),
    "operating income": ("oiadp", "oiadpq"),
    "ebitda": ("ebitda", "oibdpq"),
    "ebit": ("ebit", "oiadpq"),
    "cash": ("che", "cheq"),
    "long term debt": ("dltt", "dlttq"),
    "long-term debt": ("dltt", "dlttq"),
    "current debt": ("dlc", "dlcq"),
    "capital expenditure": ("capx", "capxy"),
    "capex": ("capx", "capxy"),
    "research and development": ("xrd", "xrdq"),
    "r&d": ("xrd", "xrdq"),
    "shareholders equity": ("seq", "seqq"),
    "book equity": ("ceq", "ceqq"),
    "shares outstanding": ("csho", "cshoq"),
    "market value": ("mkvalt", "mkvaltq"),
    "earnings per share": ("epspx", "epspxq"),
    "eps": ("epspx", "epspxq"),
    "operating cash flow": ("oancf", "oancfy"),
    "cash flow": ("oancf", "oancfy"),
    "gross profit": ("gp", "gpy"),
    "cost of goods sold": ("cogs", "cogsq"),
    "working capital": ("wcap", "wcapq"),
    "receivables": ("rect", "rectq"),
    "inventory": ("invt", "invtq"),
    "goodwill": ("gdwl", "gdwlq"),
    "intangibles": ("intan", "intanq"),
    "employees": ("emp", "emp"),
}

DISALLOWED_SQL_PATTERNS = (
    r"\b(attach|call|copy|create|delete|detach|drop|export|import|insert|install|load|merge|pragma|replace|reset|set|truncate|update|vacuum)\b",
    r"\b(read_[a-z0-9_]*|scan_[a-z0-9_]*|glob|query|query_table|parquet_scan|sqlite_scan|postgres_scan)\s*\(",
    r"\b(duckdb_[a-z0-9_]*|pragma_[a-z0-9_]*)\s*\(",
    r"https?://|s3://|\\|\.\./|\.parquet\b|\.csv\b|\.duckdb\b",
)


def find_private_root(start: Path) -> Path:
    configured_root = os.environ.get("PORTFOLIO_RISK_PRIVATE_DATA_ROOT")
    if configured_root:
        private_root = Path(configured_root).expanduser().resolve()
        if (private_root / "raw").is_dir():
            return private_root
        raise RuntimeError(
            "PORTFOLIO_RISK_PRIVATE_DATA_ROOT must contain a raw directory"
        )
    for candidate in (start, *start.parents):
        private_root = candidate / "private-data" / "crsp-compustat"
        if (private_root / "raw").is_dir():
            return private_root.resolve()
    raise RuntimeError("could not locate the private CRSP/Compustat data root")


PROTOTYPE_ROOT = Path(__file__).resolve().parent

DATASETS: dict[str, dict[str, Any]] = {
    "stocknames": {
        "file": "stocknames.parquet",
        "date_column": "namedt",
        "description": "CRSP security names and listing metadata",
    },
    "dsf": {
        "file": "dsf.parquet",
        "date_column": "date",
        "description": "CRSP daily security observations",
    },
    "msf": {
        "file": "msf.parquet",
        "date_column": "date",
        "description": "CRSP monthly security observations",
    },
    "funda": {
        "file": "funda.parquet",
        "date_column": "datadate",
        "description": "Compustat annual fundamentals",
    },
    "fundq": {
        "file": "fundq.parquet",
        "date_column": "datadate",
        "description": "Compustat quarterly fundamentals",
    },
    "ccm_lookup": {
        "file": "ccm_lookup.parquet",
        "date_column": "linkdt",
        "description": "CRSP–Compustat company lookup",
    },
    "ccmxpf_linktable": {
        "file": "ccmxpf_linktable.parquet",
        "date_column": "linkdt",
        "description": "CRSP–Compustat point-in-time link table",
    },
    "dsedelist": {
        "file": "dsedelist.parquet",
        "date_column": "dlstdt",
        "description": "CRSP delisting observations",
    },
}

GICS_SECTOR_NAMES = {
    "10": "Energy",
    "15": "Materials",
    "20": "Industrials",
    "25": "Consumer Discretionary",
    "30": "Consumer Staples",
    "35": "Health Care",
    "40": "Financials",
    "45": "Information Technology",
    "50": "Communication Services",
    "55": "Utilities",
    "60": "Real Estate",
}


class PortfolioQueryRequest(BaseModel):
    portfolio_id: str = Field(min_length=1, max_length=64)
    as_of: date
    datasets: list[Literal["market", "fundamental", "identity", "links"]] = Field(
        min_length=1, max_length=4
    )
    market_source: Literal["dsf", "msf"] = "dsf"
    include_native_ids: bool = False


class NaturalLanguageQueryRequest(BaseModel):
    question: str = Field(min_length=3, max_length=1000)


class SqlOnlyPlan(BaseModel):
    sql: str = Field(min_length=8, max_length=20_000)


class AgentInputPreviewRequest(BaseModel):
    data_mode: Literal[
        "synthetic_behavior_sample",
        "historically_calibrated_synthetic",
        "real_duckdb",
    ] = (
        "synthetic_behavior_sample"
    )
    scenario: Literal["routine", "concentration", "loss", "missing"] = "concentration"
    portfolio_id: str | None = Field(default=None, max_length=80)
    as_of: date | None = None
    datasets: list[Literal["market", "fundamental", "identity", "links"]] = Field(
        default_factory=lambda: ["market", "fundamental", "identity", "links"],
        min_length=1,
        max_length=4,
    )


class ReportComposeRequest(BaseModel):
    report_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{1,159}$")
    presentation: dict[str, Any]
    evidence_ids: list[str] = Field(default_factory=list, max_length=500)


class ReportValidationRequest(BaseModel):
    report: MarkdownReport
    available_evidence_ids: list[str] = Field(default_factory=list, max_length=500)


class ReportRenderRequest(BaseModel):
    report: MarkdownReport


class WorkflowCycleCreateRequest(BaseModel):
    portfolio_id: str = Field(min_length=1, max_length=80)
    start_date: date
    end_date: date
    seed: int = Field(default=20260802, ge=0, le=2_147_483_647)
    speed: float = Field(default=60, ge=1, le=3600)
    daily_loss_limit: float = Field(default=0.02, gt=0, le=0.25)


class WorkflowCycleControlRequest(BaseModel):
    action: Literal["start", "pause", "set_speed"]
    speed: float | None = Field(default=None, ge=1, le=3600)


class WorkflowCycleDecisionRequest(BaseModel):
    outcome: Literal["investigate", "accept_and_monitor", "defer", "reject", "escalate"]
    resolver_id: str = Field(min_length=3, max_length=120)
    resolver_type: Literal["human"] = "human"
    rationale: str = Field(min_length=3, max_length=2000)
    idempotency_key: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{1,159}$")
    expected_revision: str = Field(pattern=r"^sha256:[a-f0-9]{64}$")


class DecisionResolveRequest(WorkflowCycleDecisionRequest):
    pass


class DecisionDueDiligenceRunRequest(BaseModel):
    name: str = Field(min_length=3, max_length=160)
    investigation_question: str = Field(min_length=5, max_length=1200)
    capability_ids: list[DueDiligenceCapability] = Field(min_length=1, max_length=5)
    candidate_recommendation: Literal["investigate", "accept_and_monitor", "defer", "reject", "escalate"]
    actor_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{1,119}$")
    actor_type: Literal["human"] = "human"
    idempotency_key: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{1,159}$")
    expected_revision: str = Field(pattern=r"^sha256:[a-f0-9]{64}$")


class WorkflowCycleAgentAttachRequest(BaseModel):
    page_id: str = Field(min_length=1, max_length=80)
    agent_id: str = Field(min_length=1, max_length=120)


class RegistryBootstrapRequest(BaseModel):
    actor: str = Field(default="local.developer", min_length=3, max_length=128)


class RegistryIndexRequest(BaseModel):
    identity: RegistryIdentity
    actor: str = Field(default="local.developer", min_length=3, max_length=128)


class RegistryTransitionRequest(BaseModel):
    kind: AssetKind
    namespace: str = Field(min_length=1, max_length=160)
    asset_id: str = Field(min_length=1, max_length=256)
    version: str = Field(min_length=1, max_length=128)
    to_state: LifecycleState
    actor: str = Field(min_length=3, max_length=128)
    rationale: str = Field(min_length=3, max_length=1200)
    replacement_reference: str | None = Field(default=None, max_length=512)
    expected_revision: str = Field(pattern=r"^[a-f0-9]{64}$")


class RegistryCompareRequest(BaseModel):
    left: RegistryIdentity
    right: RegistryIdentity


class ArtifactTransitionRequest(BaseModel):
    actor: str = Field(default="local.developer", min_length=3, max_length=128)
    rationale: str = Field(min_length=3, max_length=1000)
    expected_revision: str = Field(pattern=r"^sha256:[a-f0-9]{64}$")


class ArtifactDeletionRequest(ArtifactTransitionRequest):
    confirmation_token: str = Field(pattern=r"^sha256:[a-f0-9]{64}$")


class ArtifactAdmissionRequest(BaseModel):
    run_id: str = Field(min_length=3, max_length=160)
    confirmation_token: str = Field(pattern=r"^sha256:[a-f0-9]{64}$")
    actor: str = Field(default="local.developer", min_length=3, max_length=128)


class ExperimentCreateRequest(BaseModel):
    definition: ExperimentDefinition
    actor: str = Field(default="local.researcher", min_length=3, max_length=128)
    idempotency_key: str = Field(min_length=3, max_length=160, pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]+$")


class ExperimentDraftRequest(BaseModel):
    experiment_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,159}$")
    name: str = Field(min_length=1, max_length=200)
    purpose: str = Field(min_length=3, max_length=1200)
    hypothesis: str = Field(min_length=3, max_length=1200)
    start_date: date
    end_date: date
    presentation_mode: PresentationMode
    data_truth: DataTruth
    portfolio_reference: str = Field(min_length=1, max_length=768)
    snapshot_policy_reference: str = Field(min_length=1, max_length=768)
    mandate_reference: str = Field(min_length=1, max_length=768)
    data_revision_reference: str = Field(min_length=1, max_length=768)
    system_asset: RegistryIdentity
    max_model_calls: int = Field(default=12, ge=0, le=10_000)
    max_cost_usd: Decimal = Field(default=Decimal("2.00"), ge=0, le=100_000)
    actor: str = Field(default="local.researcher", min_length=3, max_length=128)


class ExperimentTransitionRequest(BaseModel):
    to_state: ExperimentState
    actor: str = Field(default="local.researcher", min_length=3, max_length=128)
    rationale: str = Field(min_length=3, max_length=1000)
    idempotency_key: str = Field(min_length=3, max_length=160, pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]+$")
    expected_revision: str = Field(pattern=r"^sha256:[a-f0-9]{64}$")


class ExperimentEnqueueRequest(BaseModel):
    actor: str = Field(default="local.researcher", min_length=3, max_length=128)
    idempotency_key: str = Field(min_length=3, max_length=160, pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]+$")
    expected_revision: str = Field(pattern=r"^sha256:[a-f0-9]{64}$")


class ExperimentQueueControlRequest(BaseModel):
    action: Literal["start", "pause", "resume", "cancel", "complete", "fail"]
    resume_token: str = Field(pattern=r"^sha256:[a-f0-9]{64}$")


class ExperimentSetCreateRequest(BaseModel):
    definition: ExperimentSet


class RunTraceCreateRequest(BaseModel):
    actor: str = Field(default="local.researcher", min_length=3, max_length=128)


class HistoricalReplayRequest(BaseModel):
    workflow_id: str = Field(min_length=1, max_length=80)
    portfolio_id: str = Field(min_length=1, max_length=80)
    start_date: date
    end_date: date
    evaluation_id: str = Field(default="thesis_evaluation_v1", min_length=1, max_length=80)
    save_result: bool = True
    authorize_external_model_calls: bool = False


class ProfessorDemoRunRequest(BaseModel):
    authorize_external_model_calls: bool = False


class CounterfactualBatchRequest(BaseModel):
    study_id: str = Field(pattern=r"^[a-z0-9][a-z0-9._-]{2,159}$")
    study_title: str = Field(min_length=3, max_length=300)
    experiment_id: str = Field(pattern=r"^[a-z0-9][a-z0-9._-]{2,159}$")
    research_question: str = Field(min_length=10, max_length=2000)
    hypothesis: str = Field(min_length=10, max_length=2000)
    portfolio_ids: tuple[str, ...] = Field(min_length=1, max_length=3)
    workflow_ids: tuple[Literal["B0", "B1", "A1"], ...] = Field(min_length=2, max_length=3)
    baseline_workflow_id: Literal["B0"] = "B0"
    start_date: date
    end_date: date
    evaluation_id: str = Field(default="thesis_evaluation_v1", min_length=1, max_length=80)
    repetitions: int = Field(default=1, ge=1, le=3)
    max_concurrency: int = Field(default=3, ge=1, le=3)
    authorize_external_model_calls: bool = False

    @field_validator("portfolio_ids", "workflow_ids")
    @classmethod
    def unique_ordered_values(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(value) != len(set(value)):
            raise ValueError("counterfactual batch selections must be unique")
        return value

    @model_validator(mode="after")
    def architecture_batch_is_bounded(self) -> "CounterfactualBatchRequest":
        if self.baseline_workflow_id not in self.workflow_ids:
            raise ValueError("the architecture matrix must include the B0 baseline")
        if self.end_date < self.start_date:
            raise ValueError("end_date must not precede start_date")
        if len(self.portfolio_ids) * len(self.workflow_ids) * self.repetitions > 18:
            raise ValueError("the first counterfactual batch is limited to 18 Run cells")
        return self


class ArchitectureOutputMappingRequest(BaseModel):
    context: ArchitectureMappingContext
    single_agent_execution: AgentExecutionEnvelope | None = None
    graph_execution: GraphExecutionEnvelope | None = None
    mapped_at: datetime | None = None

    @model_validator(mode="after")
    def exactly_one_execution(self) -> "ArchitectureOutputMappingRequest":
        if (self.single_agent_execution is None) == (self.graph_execution is None):
            raise ValueError("provide exactly one wrapped single-agent or graph execution")
        return self


def json_safe(value: Any) -> Any:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, dict):
        return {key: json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(item) for item in value]
    return value


class ReadOnlyDataPlane:
    def __init__(self) -> None:
        self.private_root = find_private_root(PROTOTYPE_ROOT)
        self.raw_root = self.private_root / "raw"
        selection_root = (
            self.private_root
            / "portfolio-definitions"
            / "portfolio-definitions"
            / "thesis-real-portfolios-day4-v1"
        )
        selection_path = (
            self.private_root / "config" / "portfolio-selection-day4.yaml"
        )
        instrument_map_path = selection_root / "private-instrument-map.json"
        self.connection = duckdb.connect(":memory:")
        self.parser_connection = duckdb.connect(":memory:")
        self.connection.execute("SET threads=4")
        self.connection.execute("SET memory_limit='4GB'")
        self.lock = threading.Lock()
        self.selection = yaml.safe_load(selection_path.read_text())
        instrument_map = json.loads(instrument_map_path.read_text())
        self.alias_to_permno = {
            item["instrument_alias"]: int(item["permno"])
            for item in instrument_map["instruments"]
        }
        self.permno_to_alias = {
            permno: alias for alias, permno in self.alias_to_permno.items()
        }
        self.portfolios = {
            item["portfolio_id"]: item for item in self.selection["portfolios"]
        }
        self.catalog = self._build_catalog()
        self._register_query_views()

    def path(self, dataset: str) -> str:
        definition = DATASETS.get(dataset)
        if not definition:
            raise KeyError(dataset)
        path = (self.raw_root / definition["file"]).resolve()
        if path.parent != self.raw_root.resolve() or not path.is_file():
            raise RuntimeError(f"dataset file unavailable: {dataset}")
        return str(path)

    def _execute(self, sql: str, parameters: list[Any]) -> tuple[list[str], list[tuple[Any, ...]]]:
        with self.lock:
            relation = self.connection.execute(sql, parameters)
            columns = [item[0] for item in relation.description]
            rows = relation.fetchall()
        return columns, rows

    def _dict_rows(self, sql: str, parameters: list[Any]) -> list[dict[str, Any]]:
        columns, rows = self._execute(sql, parameters)
        return [dict(zip(columns, row, strict=True)) for row in rows]

    def _build_catalog(self) -> list[dict[str, Any]]:
        catalog = []
        for dataset, definition in DATASETS.items():
            path = self.path(dataset)
            date_column = definition["date_column"]
            columns, rows = self._execute(
                f"""
                SELECT
                    count(*) AS row_count,
                    min({date_column}) AS minimum_date,
                    max({date_column}) AS maximum_date
                FROM read_parquet(?)
                """,
                [path],
            )
            summary = dict(zip(columns, rows[0], strict=True))
            schema = self._dict_rows(
                "SELECT column_name, column_type FROM (DESCRIBE SELECT * FROM read_parquet(?))",
                [path],
            )
            catalog.append(
                {
                    "dataset": dataset,
                    "description": definition["description"],
                    "file": definition["file"],
                    "bytes": Path(path).stat().st_size,
                    "row_count": summary["row_count"],
                    "minimum_date": summary["minimum_date"],
                    "maximum_date": summary["maximum_date"],
                    "column_count": len(schema),
                    "columns": schema,
                }
            )
        return json_safe(catalog)

    def _register_query_views(self) -> None:
        with self.lock:
            for dataset in DATASETS:
                path_literal = self.path(dataset).replace("'", "''")
                self.connection.execute(
                    f"CREATE VIEW {dataset} AS "
                    f"SELECT * FROM read_parquet('{path_literal}')"
                )

    def sql_agent_catalog(self, question: str) -> tuple[str, dict[str, Any]]:
        """Return a deterministic, question-specific catalog projection for Luna."""

        normalized = re.sub(r"\s+", " ", question.casefold()).strip()
        tokens = set(re.findall(r"[a-z][a-z0-9_]{1,}", normalized))
        catalog_by_name = {item["dataset"]: item for item in self.catalog}
        scores: dict[str, int] = {name: 0 for name in DATASETS}
        matched_hints: dict[str, list[str]] = {name: [] for name in DATASETS}

        for dataset, hints in SQL_TABLE_HINTS.items():
            if dataset.casefold() in tokens or dataset.casefold() in normalized:
                scores[dataset] += 20
                matched_hints[dataset].append(dataset)
            for hint in hints:
                if hint in normalized:
                    scores[dataset] += 5 if " " in hint else 2
                    matched_hints[dataset].append(hint)

        quarterly = any(term in normalized for term in ("quarter", "quarterly", "fqtr"))
        annual = any(term in normalized for term in ("annual", "yearly", "fiscal year", "fyear"))
        monthly = any(term in normalized for term in ("monthly", "month", "msf"))
        daily = any(term in normalized for term in ("daily", "day", "dsf"))
        if quarterly and not annual:
            scores["fundq"] += 12
            scores["funda"] = 0
        elif annual and not quarterly:
            scores["funda"] += 12
            scores["fundq"] = 0
        elif scores["funda"] and scores["fundq"]:
            # Annual is the less ambiguous default for an unqualified fiscal year.
            scores["funda"] += 3
            scores["fundq"] = max(0, scores["fundq"] - 2)
        if monthly and not daily:
            scores["msf"] += 12
            scores["dsf"] = 0
        elif daily and not monthly:
            scores["dsf"] += 12
            scores["msf"] = 0

        ranked = sorted(scores, key=lambda name: (-scores[name], name))
        selected = [name for name in ranked if scores[name] > 0][:3]
        if not selected:
            selected = ["stocknames", "dsf", "funda", "ccm_lookup"]

        market_selected = any(name in selected for name in ("dsf", "msf"))
        fundamental_selected = any(name in selected for name in ("funda", "fundq"))
        classification_requested = any(
            term in normalized for term in ("sector", "industry", "gics", "naics", "classification")
        )
        if fundamental_selected and not market_selected and "stocknames" in selected:
            # Compustat already carries company name, ticker and CUSIP.
            selected.remove("stocknames")
        companions: list[str] = []
        if market_selected:
            companions.append("stocknames")
        if classification_requested or (market_selected and fundamental_selected):
            companions.append("ccm_lookup")
        for companion in companions:
            if companion not in selected:
                selected.append(companion)
        selected = selected[:4]

        table_blocks: list[str] = []
        routed_columns: dict[str, list[str]] = {}
        for dataset in selected:
            item = catalog_by_name[dataset]
            available = {
                str(column["column_name"]): str(column["column_type"])
                for column in item["columns"]
            }
            requested = list(SQL_BASE_COLUMNS.get(dataset, ()))
            for column_name in available:
                lowered = column_name.casefold()
                explicitly_named = (
                    (len(lowered) >= 3 and lowered in tokens)
                    or f'"{lowered}"' in normalized
                    or f"`{lowered}`" in normalized
                    or f"column {lowered}" in normalized
                )
                if explicitly_named:
                    requested.append(column_name)
            for phrase, (annual_column, quarterly_column) in SQL_METRIC_COLUMNS.items():
                if phrase in normalized:
                    if dataset == "funda":
                        requested.append(annual_column)
                    elif dataset == "fundq":
                        requested.append(quarterly_column)
            if dataset == "funda" and not any(
                phrase in normalized for phrase in SQL_METRIC_COLUMNS
            ):
                requested.extend(("at", "lt", "sale", "revt", "ni", "oiadp", "che", "dltt"))
            if dataset == "fundq" and not any(
                phrase in normalized for phrase in SQL_METRIC_COLUMNS
            ):
                requested.extend(("atq", "ltq", "saleq", "revtq", "niq", "oiadpq", "cheq", "dlttq"))
            columns = list(dict.fromkeys(name for name in requested if name in available))
            routed_columns[dataset] = columns
            rendered_columns = ", ".join(
                f'"{name}" {available[name]}' for name in columns
            )
            guidance = ""
            if dataset == "funda":
                guidance = (
                    "\nDEFAULT COMPANY FILTERS: \"datafmt\" = 'STD', \"consol\" = 'C', "
                    "\"popsrc\" = 'D', \"indfmt\" = 'INDL'. When comparing monetary "
                    "levels across companies, also use one currency such as \"curcd\" = 'USD'."
                )
            elif dataset == "fundq":
                guidance = (
                    "\nDEFAULT COMPANY FILTERS: \"datafmt\" = 'STD', \"consol\" = 'C', "
                    "\"popsrc\" = 'D', \"indfmt\" = 'INDL'. When comparing monetary "
                    "levels across companies, also use one currency such as \"curcdq\" = 'USD'. "
                    "For point-in-time questions, filter COALESCE(\"rdq\", \"fdateq\", "
                    "\"datadate\") to the requested as-of date."
                )
            table_blocks.append(
                f'TABLE "{dataset}" — {item["description"]}\nCOLUMNS {rendered_columns}{guidance}'
            )

        joins = (
            'COMMON JOINS: stocknames.permno = dsf.permno = msf.permno; '
            'ccm_lookup.lpermno = dsf.permno; '
            'ccm_lookup.gvkey = funda.gvkey = fundq.gvkey. '
            'Use date-effective link conditions when the question requires point-in-time mapping.'
        )
        rendered = "\n\n".join((*table_blocks, joins))
        routing = {
            "strategy": "deterministic_question_specific_schema_v1",
            "model_calls": 0,
            "selected_tables": selected,
            "selected_columns": routed_columns,
            "selected_column_count": sum(len(value) for value in routed_columns.values()),
            "physical_column_count": sum(
                int(catalog_by_name[name]["column_count"]) for name in selected
            ),
            "catalog_characters": len(rendered),
            "matched_hints": {
                name: list(dict.fromkeys(matched_hints[name]))
                for name in selected
                if matched_hints[name]
            },
        }
        return rendered, routing

    def validate_generated_sql(self, sql: str) -> str:
        cleaned = sql.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:sql)?\s*", "", cleaned, flags=re.IGNORECASE)
            cleaned = re.sub(r"\s*```$", "", cleaned)
        cleaned = cleaned.strip().rstrip(";").strip()
        if not cleaned:
            raise ValueError("Luna returned an empty query")
        for pattern in DISALLOWED_SQL_PATTERNS:
            if re.search(pattern, cleaned, flags=re.IGNORECASE):
                raise ValueError("query contains an operation outside the read-only boundary")
        with self.lock:
            statements = self.connection.extract_statements(cleaned)
            table_names = self.parser_connection.get_table_names(cleaned)
        if len(statements) != 1 or statements[0].type != duckdb.StatementType.SELECT:
            raise ValueError("exactly one read-only SELECT statement is required")
        unknown_tables = table_names.difference(DATASETS)
        if not table_names or unknown_tables:
            names = ", ".join(sorted(unknown_tables)) or "none"
            raise ValueError(
                f"query must use only the allow-listed datasets; unknown tables: {names}"
            )
        return cleaned

    def execute_generated_sql(self, sql: str) -> dict[str, Any]:
        cleaned = self.validate_generated_sql(sql)
        bounded_sql = (
            "SELECT * FROM (" + cleaned + ") AS luna_query "
            f"LIMIT {MAX_QUERY_ROWS + 1}"
        )
        started = time.perf_counter()
        timer = threading.Timer(QUERY_TIMEOUT_SECONDS, self.connection.interrupt)
        timer.daemon = True
        with self.lock:
            timer.start()
            try:
                relation = self.connection.execute(bounded_sql)
                columns = [item[0] for item in relation.description]
                if len(columns) > MAX_QUERY_COLUMNS:
                    raise ValueError(
                        f"query returned {len(columns)} columns; the maximum is {MAX_QUERY_COLUMNS}"
                    )
                rows = relation.fetchmany(MAX_QUERY_ROWS + 1)
            finally:
                timer.cancel()
        truncated = len(rows) > MAX_QUERY_ROWS
        rows = rows[:MAX_QUERY_ROWS]
        return json_safe(
            {
                "sql": cleaned,
                "columns": columns,
                "rows": rows,
                "row_count": len(rows),
                "column_count": len(columns),
                "truncated": truncated,
                "elapsed_ms": round((time.perf_counter() - started) * 1000, 2),
                "limits": {
                    "rows": MAX_QUERY_ROWS,
                    "columns": MAX_QUERY_COLUMNS,
                    "seconds": QUERY_TIMEOUT_SECONDS,
                },
            }
        )

    def public_portfolios(self) -> list[dict[str, Any]]:
        values = []
        for portfolio in self.portfolios.values():
            values.append(
                {
                    "portfolio_id": portfolio["portfolio_id"],
                    "title": portfolio["title"],
                    "base_currency": portfolio["base_currency"],
                    "cash": portfolio["cash"],
                    "positions": [
                        {
                            "instrument_alias": position["instrument_alias"],
                            "quantity": position["quantity"],
                        }
                        for position in portfolio["positions"]
                    ],
                }
            )
        return values

    def portfolio_bindings(self, portfolio_id: str) -> list[dict[str, Any]]:
        portfolio = self.portfolios.get(portfolio_id)
        if not portfolio:
            raise HTTPException(status_code=404, detail="unknown reviewed portfolio")
        bindings = []
        for position in portfolio["positions"]:
            alias = position["instrument_alias"]
            permno = self.alias_to_permno.get(alias)
            if permno is None:
                raise HTTPException(
                    status_code=409,
                    detail=f"approved alias has no private CRSP binding: {alias}",
                )
            bindings.append(
                {
                    "instrument_alias": alias,
                    "quantity": position["quantity"],
                    "permno": permno,
                }
            )
        return bindings

    @staticmethod
    def placeholders(values: list[Any]) -> str:
        return ",".join("?" for _ in values)

    def latest_market(
        self,
        bindings: list[dict[str, Any]],
        as_of: date,
        source: str,
    ) -> dict[int, dict[str, Any]]:
        permnos = [item["permno"] for item in bindings]
        markers = self.placeholders(permnos)
        rows = self._dict_rows(
            f"""
            SELECT permno, date, prc, ret, vol, shrout, cfacpr, cfacshr
            FROM read_parquet(?)
            WHERE permno IN ({markers}) AND date <= ? AND prc IS NOT NULL
            QUALIFY row_number() OVER (
                PARTITION BY permno ORDER BY date DESC
            ) = 1
            """,
            [self.path(source), *permnos, as_of],
        )
        return {int(item["permno"]): item for item in rows}

    def latest_classification(
        self,
        bindings: list[dict[str, Any]],
        as_of: date,
    ) -> dict[int, dict[str, Any]]:
        permnos = [item["permno"] for item in bindings]
        markers = self.placeholders(permnos)
        rows = self._dict_rows(
            f"""
            SELECT
                CAST(lpermno AS INTEGER) AS permno,
                conm,
                tic,
                sic,
                naics,
                gind,
                gsubind,
                year1,
                year2,
                linkdt,
                linkenddt
            FROM read_parquet(?)
            WHERE CAST(lpermno AS INTEGER) IN ({markers})
              AND linkdt <= ?
              AND (linkenddt IS NULL OR linkenddt >= ?)
              AND (year1 IS NULL OR year1 <= year(?))
              AND (year2 IS NULL OR year2 >= year(?))
            QUALIFY row_number() OVER (
                PARTITION BY CAST(lpermno AS INTEGER)
                ORDER BY year2 DESC NULLS LAST, linkdt DESC
            ) = 1
            """,
            [self.path("ccm_lookup"), *permnos, as_of, as_of, as_of, as_of],
        )
        return {int(item["permno"]): item for item in rows}

    def historical_portfolio_values(
        self,
        bindings: list[dict[str, Any]],
        quantities: dict[str, float],
        included_aliases: set[str],
        cash_total: float,
        as_of: date,
        lookback_days: int = 550,
    ) -> list[dict[str, Any]]:
        included = [
            item for item in bindings if item["instrument_alias"] in included_aliases
        ]
        if not included:
            return []
        permnos = [item["permno"] for item in included]
        alias_by_permno = {
            int(item["permno"]): item["instrument_alias"] for item in included
        }
        rows = self._dict_rows(
            f"""
            SELECT permno, date, abs(prc) AS price
            FROM read_parquet(?)
            WHERE permno IN ({self.placeholders(permnos)})
              AND date BETWEEN ? AND ?
              AND prc IS NOT NULL
            ORDER BY date, permno
            """,
            [
                self.path("dsf"),
                *permnos,
                as_of - timedelta(days=lookback_days),
                as_of,
            ],
        )
        prices_by_date: dict[date, dict[str, float]] = {}
        for row in rows:
            alias = alias_by_permno[int(row["permno"])]
            prices_by_date.setdefault(row["date"], {})[alias] = float(row["price"])
        observations = []
        for observed_at, prices in prices_by_date.items():
            if set(prices) != included_aliases:
                continue
            nav = cash_total + sum(
                quantities[alias] * prices[alias] for alias in included_aliases
            )
            observations.append(
                {"observed_at": observed_at, "portfolio_value": nav}
            )
        return observations[-253:]

    def latest_identity(
        self,
        bindings: list[dict[str, Any]],
        as_of: date,
    ) -> dict[int, dict[str, Any]]:
        permnos = [item["permno"] for item in bindings]
        markers = self.placeholders(permnos)
        rows = self._dict_rows(
            f"""
            SELECT permno, ticker, comnam, exchcd, shrcd, siccd, namedt, nameenddt
            FROM read_parquet(?)
            WHERE permno IN ({markers})
              AND namedt <= ?
              AND (nameenddt IS NULL OR nameenddt >= ?)
            QUALIFY row_number() OVER (
                PARTITION BY permno ORDER BY namedt DESC
            ) = 1
            """,
            [self.path("stocknames"), *permnos, as_of, as_of],
        )
        return {int(item["permno"]): item for item in rows}

    def active_links(
        self,
        bindings: list[dict[str, Any]],
        as_of: date,
    ) -> dict[int, dict[str, Any]]:
        permnos = [item["permno"] for item in bindings]
        markers = self.placeholders(permnos)
        rows = self._dict_rows(
            f"""
            SELECT
                CAST(lpermno AS INTEGER) AS permno,
                gvkey,
                linkprim,
                linktype,
                linkdt,
                linkenddt
            FROM read_parquet(?)
            WHERE CAST(lpermno AS INTEGER) IN ({markers})
              AND linkdt <= ?
              AND (linkenddt IS NULL OR linkenddt >= ?)
              AND linktype IN ('LC', 'LU', 'LS')
            QUALIFY row_number() OVER (
                PARTITION BY CAST(lpermno AS INTEGER)
                ORDER BY
                    CASE linkprim WHEN 'P' THEN 0 WHEN 'C' THEN 1 ELSE 2 END,
                    linkdt DESC,
                    gvkey
            ) = 1
            """,
            [self.path("ccmxpf_linktable"), *permnos, as_of, as_of],
        )
        return {int(item["permno"]): item for item in rows}

    def latest_fundamentals(
        self,
        links: dict[int, dict[str, Any]],
        as_of: date,
    ) -> dict[str, dict[str, Any]]:
        gvkeys = sorted({str(item["gvkey"]) for item in links.values()})
        if not gvkeys:
            return {}
        markers = self.placeholders(gvkeys)
        rows = self._dict_rows(
            f"""
            SELECT
                gvkey,
                datadate,
                rdq,
                fdateq,
                COALESCE(rdq, fdateq, datadate) AS available_date,
                fqtr,
                fyearq,
                atq,
                ltq,
                saleq,
                revtq,
                niq,
                oiadpq,
                cheq,
                dlttq,
                dlcq,
                cshoq
            FROM read_parquet(?)
            WHERE gvkey IN ({markers})
              AND COALESCE(rdq, fdateq, datadate) <= ?
              AND datafmt = 'STD'
              AND consol = 'C'
              AND popsrc = 'D'
            QUALIFY row_number() OVER (
                PARTITION BY gvkey
                ORDER BY COALESCE(rdq, fdateq, datadate) DESC, datadate DESC
            ) = 1
            """,
            [self.path("fundq"), *gvkeys, as_of],
        )
        return {str(item["gvkey"]): item for item in rows}

    def query_portfolio(self, request: PortfolioQueryRequest) -> dict[str, Any]:
        started = time.perf_counter()
        bindings = self.portfolio_bindings(request.portfolio_id)
        records: list[dict[str, Any]] = []
        links: dict[int, dict[str, Any]] | None = None

        if "market" in request.datasets:
            market = self.latest_market(bindings, request.as_of, request.market_source)
            for binding in bindings:
                item = market.get(binding["permno"])
                age_days = (request.as_of - item["date"]).days if item else None
                quality = (
                    "missing"
                    if item is None
                    else "stale"
                    if age_days is not None and age_days > 10
                    else "eligible"
                )
                record = {
                    "instrument_alias": binding["instrument_alias"],
                    "dataset": f"crsp_{request.market_source}",
                    "observed_at": item["date"] if item else None,
                    "available_at": None,
                    "values": {
                        "price": abs(item["prc"]) if item and item["prc"] is not None else None,
                        "return": item["ret"] if item else None,
                        "volume": item["vol"] if item else None,
                        "shares_outstanding": item["shrout"] if item else None,
                    },
                    "quality": quality,
                    "point_in_time_note": (
                        f"latest non-missing CRSP price is {age_days} calendar days before as-of"
                        if quality == "stale"
                        else "record date is on or before as-of; CRSP source has no publication timestamp"
                        if quality == "eligible"
                        else "no eligible CRSP observation"
                    ),
                }
                if request.include_native_ids:
                    record["native_id"] = {"permno": binding["permno"]}
                records.append(record)

        if "identity" in request.datasets:
            identities = self.latest_identity(bindings, request.as_of)
            classifications = self.latest_classification(bindings, request.as_of)
            for binding in bindings:
                item = identities.get(binding["permno"])
                classification = classifications.get(binding["permno"])
                gics_industry = str(classification.get("gind") or "") if classification else ""
                gics_subindustry = str(classification.get("gsubind") or "") if classification else ""
                sector_code = (gics_subindustry or gics_industry)[:2] or None
                record = {
                    "instrument_alias": binding["instrument_alias"],
                    "dataset": "crsp_stocknames",
                    "observed_at": item["namedt"] if item else classification["linkdt"] if classification else None,
                    "available_at": None,
                    "values": {
                        "ticker": (item["ticker"] if item else None) or (classification["tic"] if classification else None),
                        "company_name": (item["comnam"] if item else None) or (classification["conm"] if classification else None),
                        "exchange_code": item["exchcd"] if item else None,
                        "share_code": item["shrcd"] if item else None,
                        "sic_code": (item["siccd"] if item else None) or (classification["sic"] if classification else None),
                        "naics_code": classification["naics"] if classification else None,
                        "gics_sector_code": sector_code,
                        "gics_sector_name": GICS_SECTOR_NAMES.get(sector_code),
                        "gics_industry_code": gics_industry or None,
                        "gics_subindustry_code": gics_subindustry or None,
                        "name_end_date": item["nameenddt"] if item else None,
                    },
                    "quality": "eligible" if item or classification else "missing",
                    "point_in_time_note": "name/classification interval contains as-of date" if item or classification else "no active name or classification interval",
                }
                if request.include_native_ids:
                    record["native_id"] = {"permno": binding["permno"]}
                records.append(record)

        if "links" in request.datasets or "fundamental" in request.datasets:
            links = self.active_links(bindings, request.as_of)

        if "links" in request.datasets:
            for binding in bindings:
                item = links.get(binding["permno"]) if links else None
                record = {
                    "instrument_alias": binding["instrument_alias"],
                    "dataset": "ccmxpf_linktable",
                    "observed_at": item["linkdt"] if item else None,
                    "available_at": None,
                    "values": {
                        "link_primary": item["linkprim"] if item else None,
                        "link_type": item["linktype"] if item else None,
                        "link_end_date": item["linkenddt"] if item else None,
                    },
                    "quality": "eligible" if item else "missing",
                    "point_in_time_note": "link interval contains as-of date" if item else "no eligible CCM link",
                }
                if request.include_native_ids:
                    record["native_id"] = {
                        "permno": binding["permno"],
                        "gvkey": item["gvkey"] if item else None,
                    }
                records.append(record)

        if "fundamental" in request.datasets:
            fundamentals = self.latest_fundamentals(links or {}, request.as_of)
            for binding in bindings:
                link = links.get(binding["permno"]) if links else None
                item = fundamentals.get(str(link["gvkey"])) if link else None
                used_fallback = bool(item and item["rdq"] is None)
                record = {
                    "instrument_alias": binding["instrument_alias"],
                    "dataset": "compustat_fundq",
                    "observed_at": item["datadate"] if item else None,
                    "available_at": item["available_date"] if item else None,
                    "values": {
                        "fiscal_year": item["fyearq"] if item else None,
                        "fiscal_quarter": item["fqtr"] if item else None,
                        "assets": item["atq"] if item else None,
                        "liabilities": item["ltq"] if item else None,
                        "revenue": item["revtq"] if item else None,
                        "sales": item["saleq"] if item else None,
                        "net_income": item["niq"] if item else None,
                        "operating_income": item["oiadpq"] if item else None,
                        "cash": item["cheq"] if item else None,
                        "long_term_debt": item["dlttq"] if item else None,
                        "current_debt": item["dlcq"] if item else None,
                        "shares_outstanding": item["cshoq"] if item else None,
                    },
                    "quality": "fallback_date" if used_fallback else ("eligible" if item else "missing"),
                    "point_in_time_note": (
                        "report date used as availability fallback because rdq is missing"
                        if used_fallback
                        else ("earnings report date is on or before as-of" if item else "no eligible quarterly fundamental")
                    ),
                }
                if request.include_native_ids:
                    record["native_id"] = {
                        "permno": binding["permno"],
                        "gvkey": link["gvkey"] if link else None,
                    }
                records.append(record)

        quality_counts: dict[str, int] = {}
        for record in records:
            quality_counts[record["quality"]] = quality_counts.get(record["quality"], 0) + 1
        elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
        return json_safe(
            {
                "mode": "live_duckdb",
                "portfolio_id": request.portfolio_id,
                "as_of": request.as_of,
                "datasets": request.datasets,
                "position_count": len(bindings),
                "record_count": len(records),
                "quality_counts": quality_counts,
                "elapsed_ms": elapsed_ms,
                "point_in_time_rule": "source observation and known availability date <= as_of",
                "records": records,
            }
        )


def plan_sql(question: str) -> tuple[str, dict[str, Any]]:
    api_key = _keychain_key(include_value=True)
    if not api_key:
        raise RuntimeError("OpenAI credential is unavailable")
    from openai import OpenAI

    started = time.perf_counter()
    routed_catalog, catalog_routing = data_plane.sql_agent_catalog(question)
    client = OpenAI(api_key=str(api_key))
    response = client.responses.create(
        model=SQL_AGENT_MODEL,
        reasoning={"effort": SQL_AGENT_REASONING_EFFORT},
        store=False,
        tools=[],
        input=[
            {
                "role": "system",
                "content": [
                    {
                        "type": "input_text",
                        "text": (
                            "You are Luna, a narrow DuckDB SQL generator. Your only job is "
                            "to create one read-only SELECT statement answering the user's "
                            "question. Use only the supplied tables and columns. Never use "
                            "file paths, URLs, table functions, external scans, system tables, "
                            "DDL, DML, PRAGMA, COPY, ATTACH, INSTALL, LOAD, or multiple "
                            "statements. Select only useful columns, never more than 200. "
                            "Double-quote every table and column identifier because names "
                            "such as at may be DuckDB keywords. "
                            "Always include a LIMIT no greater than 10000, including for "
                            "aggregate queries. Prefer clear aliases and deterministic ordering "
                            "when ranking. Return only the SQL field required by the schema; "
                            "do not explain, narrate, or interpret results."
                        ),
                    }
                ],
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": json.dumps(
                            {
                                "question": question,
                                "duckdb_catalog": routed_catalog,
                                "hard_limits": {
                                    "rows": MAX_QUERY_ROWS,
                                    "columns": MAX_QUERY_COLUMNS,
                                },
                            },
                            sort_keys=True,
                        ),
                    }
                ],
            },
        ],
        text={
            "format": {
                "type": "json_schema",
                "name": "duckdb_sql_only",
                "strict": True,
                "schema": {
                    "type": "object",
                    "properties": {"sql": {"type": "string"}},
                    "required": ["sql"],
                    "additionalProperties": False,
                },
            }
        },
        max_output_tokens=1200,
    )
    plan = SqlOnlyPlan.model_validate(json.loads(response.output_text))
    usage = getattr(response, "usage", None)
    receipt = {
        "provider": "openai_responses",
        "model": getattr(response, "model", SQL_AGENT_MODEL),
        "reasoning_effort": SQL_AGENT_REASONING_EFFORT,
        "response_id": getattr(response, "id", None),
        "input_tokens": int(getattr(usage, "input_tokens", 0) or 0),
        "output_tokens": int(getattr(usage, "output_tokens", 0) or 0),
        "elapsed_ms": round((time.perf_counter() - started) * 1000, 2),
        "store": False,
        "tools": [],
        "data_shared": "question-specific catalog projection only; no licensed rows",
        "catalog_routing": catalog_routing,
    }
    return plan.sql, receipt


class LazyReadOnlyDataPlane:
    """Open licensed local data only when a data endpoint actually needs it."""

    def __init__(self) -> None:
        self._value: ReadOnlyDataPlane | None = None
        self._lock = threading.Lock()

    def _get(self) -> ReadOnlyDataPlane:
        if self._value is None:
            with self._lock:
                if self._value is None:
                    self._value = ReadOnlyDataPlane()
        return self._value

    def __getattr__(self, name: str) -> Any:
        return getattr(self._get(), name)


data_plane = LazyReadOnlyDataPlane()
app = FastAPI(
    title="Portfolio Replay Lab — CRSP/Compustat DuckDB API",
    version="0.1.0",
)


def prepare_agent_input(
    request: AgentInputPreviewRequest,
) -> tuple[dict[str, Any], dict[str, Any]]:
    if request.data_mode == "synthetic_behavior_sample":
        context = _scenario_context(request.scenario)
        return context, synthetic_behavior_provenance(request.scenario)

    if request.data_mode == "historically_calibrated_synthetic":
        if not request.portfolio_id or not request.as_of:
            raise HTTPException(
                status_code=422,
                detail=(
                    "historical calibration requires a reviewed portfolio and an as-of date"
                ),
            )
        real_context, _real_provenance = prepare_agent_input(
            request.model_copy(update={"data_mode": "real_duckdb"})
        )
        try:
            context, provenance = historically_calibrated_synthetic_context(
                scenario=request.scenario,
                historical_values=real_context.get("metric_pack_input", {}).get(
                    "observations", []
                ),
                portfolio_id=request.portfolio_id,
                as_of=request.as_of.isoformat(),
            )
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        provenance["calibration_source"] = {
            "provider": "local DuckDB",
            "datasets": request.datasets,
            "rights": "licensed_restricted",
            "raw_rows_in_run_output": False,
        }
        return json_safe(context), provenance

    if not request.portfolio_id or not request.as_of:
        raise HTTPException(
            status_code=422,
            detail="real-data testing requires a reviewed portfolio and an as-of date",
        )
    datasets = request.datasets or ["market", "fundamental", "identity", "links"]
    query = data_plane.query_portfolio(
        PortfolioQueryRequest(
            portfolio_id=request.portfolio_id,
            as_of=request.as_of,
            datasets=datasets,
            market_source="dsf",
            include_native_ids=False,
        )
    )
    portfolio = data_plane.portfolios.get(request.portfolio_id)
    if not portfolio:
        raise HTTPException(status_code=404, detail="unknown reviewed portfolio")
    positions = {
        item["instrument_alias"]: float(item["quantity"])
        for item in portfolio["positions"]
    }
    market_records = {
        item["instrument_alias"]: item
        for item in query["records"]
        if item["dataset"] == "crsp_dsf"
    }
    identity_records = {
        item["instrument_alias"]: item
        for item in query["records"]
        if item["dataset"] == "crsp_stocknames"
    }
    base_currency = str(portfolio.get("base_currency") or "USD")
    instrument_labels: dict[str, dict[str, Any]] = {}
    capability_positions = []
    for item in portfolio["positions"]:
        alias = item["instrument_alias"]
        market_record = market_records.get(alias, {})
        identity = identity_records.get(alias, {}).get("values", {})
        company_name = identity.get("company_name") or alias
        instrument_labels[alias] = {
            "company_name": company_name,
            "ticker": identity.get("ticker"),
            "sector": identity.get("gics_sector_name"),
            "sector_code": identity.get("gics_sector_code"),
            "industry_code": identity.get("gics_industry_code"),
            "subindustry_code": identity.get("gics_subindustry_code"),
            "sic_code": identity.get("sic_code"),
            "naics_code": identity.get("naics_code"),
        }
        eligible_price = market_record.get("quality") == "eligible"
        capability_positions.append(
            {
                "instrument_id": alias,
                "display_name": company_name,
                "ticker": identity.get("ticker"),
                "sector": identity.get("gics_sector_name"),
                "quantity": str(item["quantity"]),
                "price": market_record.get("values", {}).get("price") if eligible_price else None,
                "last_known_price": market_record.get("values", {}).get("price"),
                "currency": str(item.get("currency") or base_currency),
                "observed_at": market_record.get("observed_at"),
                "quality": market_record.get("quality", "missing"),
            }
        )
    capability_cash = [
        {
            "currency": str(item.get("currency") or base_currency),
            "amount": str(item.get("amount", 0)),
        }
        for item in portfolio.get("cash", [])
    ]
    position_values: dict[str, float] = {}
    for alias, quantity in positions.items():
        price = market_records.get(alias, {}).get("values", {}).get("price")
        if price is not None and market_records.get(alias, {}).get("quality") == "eligible":
            position_values[alias] = abs(float(price)) * quantity
    cash_total = sum(float(item.get("amount", 0)) for item in portfolio.get("cash", []))
    total_value = cash_total + sum(position_values.values())
    largest_weight = (
        max(position_values.values(), default=0.0) / total_value
        if total_value
        else 0.0
    )
    cash_weight = cash_total / total_value if total_value else 0.0
    eligible_aliases = set(position_values)
    bindings = data_plane.portfolio_bindings(request.portfolio_id)
    historical_values = data_plane.historical_portfolio_values(
        bindings,
        positions,
        eligible_aliases,
        cash_total,
        request.as_of,
    )
    daily_return = None
    if len(historical_values) >= 2:
        previous = historical_values[-2]["portfolio_value"]
        current = historical_values[-1]["portfolio_value"]
        daily_return = current / previous - 1 if previous else None
    excluded_aliases = sorted(set(positions) - eligible_aliases)
    excluded_names = [
        instrument_labels[alias]["company_name"] for alias in excluded_aliases
    ]
    missing_count = len(excluded_aliases)
    context = {
        "as_of_date": request.as_of.isoformat(),
        "portfolio_name": portfolio["title"],
        "portfolio_id": request.portfolio_id,
        "daily_return": daily_return,
        "var_95": None,
        "drawdown": None,
        "largest_weight": largest_weight,
        "cash_weight": cash_weight,
        "stress_loss": None,
        "mandate_status": "requires reviewed MetricPack evaluation",
        "evidence_state": "partial" if missing_count else "complete",
        "issue": (
            f"{len(eligible_aliases)} of {len(positions)} holdings have a current eligible "
            "valuation price. The priced sleeve requires concentration and downside-risk review."
        ),
        "eligible_event": "No governed event/news source was included in this real-data test.",
        "event_context": "Not included",
        "news_context": "Not included",
        "workflow_cycle_id": f"real-{request.portfolio_id}-{request.as_of.isoformat()}",
        "source_mode": "real_duckdb",
        "source_records": query["records"],
        "source_quality_counts": query["quality_counts"],
        "instrument_context": [
            {
                "instrument_id": alias,
                **instrument_labels[alias],
                "valuation_quality": market_records.get(alias, {}).get("quality", "missing"),
                "valuation_date": market_records.get(alias, {}).get("observed_at"),
            }
            for alias in positions
        ],
        "valuation_coverage": {
            "total_holdings": len(positions),
            "priced_holdings": len(eligible_aliases),
            "excluded_holdings": excluded_names,
            "basis": "priced sleeve; excluded holdings were not converted to zero",
        },
        "portfolio_capability_input": {
            "snapshot_id": f"real-{request.portfolio_id}-{request.as_of.isoformat()}",
            "as_of": f"{request.as_of.isoformat()}T23:59:59+00:00",
            "retrieved_at": datetime.now(timezone.utc)
            .replace(microsecond=0)
            .isoformat(),
            "base_currency": base_currency,
            "positions": capability_positions,
            "instrument_labels": instrument_labels,
            "cash_balances": capability_cash,
            "source_id": "local-duckdb-crsp-compustat",
            "source_type": "licensed_local_research_data",
            "source_reference": (
                f"duckdb://portfolio/{request.portfolio_id}?as_of={request.as_of.isoformat()}"
            ),
            "source_label": "Local DuckDB · CRSP/Compustat point-in-time query",
            "source_detail": (
                "Fetched reviewed portfolio quantities and each latest non-missing CRSP "
                "price on or before the selected as-of date, then excluded stale or missing "
                "valuations from canonical calculations."
            ),
            "evidence_id": (
                f"duckdb-evidence:{request.portfolio_id}:{request.as_of.isoformat()}"
            ),
        },
        "metric_pack_input": {
            "analysis_id": f"metric-pack:{request.portfolio_id}:{request.as_of.isoformat()}",
            "snapshot_id": f"priced-sleeve:{request.portfolio_id}:{request.as_of.isoformat()}",
            "as_of": f"{request.as_of.isoformat()}T23:59:59+00:00",
            "base_currency": base_currency,
            "observations": historical_values,
            "included_holdings": [instrument_labels[alias]["company_name"] for alias in sorted(eligible_aliases)],
            "excluded_holdings": excluded_names,
            "coverage": f"{len(eligible_aliases)}/{len(positions)} holdings",
            "source_reference": f"duckdb://portfolio/{request.portfolio_id}/historical-values?as_of={request.as_of.isoformat()}",
            "evidence_id": f"metric-evidence:{request.portfolio_id}:{request.as_of.isoformat()}",
        },
    }
    provenance = {
        "data_mode": "real_duckdb",
        "label": "REAL · point-in-time DuckDB / CRSP-Compustat",
        "licensed_data_used": True,
        "point_in_time": True,
        "portfolio_id": request.portfolio_id,
        "as_of": request.as_of.isoformat(),
        "datasets": datasets,
        "record_count": query["record_count"],
        "position_count": query["position_count"],
        "quality_counts": query["quality_counts"],
        "point_in_time_rule": query["point_in_time_rule"],
        "limitations": [
            "This source-data step does not itself create OverallDefaultContext; the agent runtime assembles it after capability calculation.",
            "CRSP observations do not provide a publication timestamp.",
            "No event or news context is included in this test mode yet.",
        ],
    }
    return json_safe(context), provenance


def prepare_workflow_cycle_configuration(
    request: WorkflowCycleCreateRequest,
) -> dict[str, Any]:
    """Bind reviewed positions to real closes and seal future anchors for simulation."""

    if request.end_date < request.start_date:
        raise HTTPException(status_code=422, detail="end date cannot precede start date")
    if (request.end_date - request.start_date).days > 40:
        raise HTTPException(
            status_code=422,
            detail="the first live-console increment is limited to 40 calendar days",
        )
    portfolio = data_plane.portfolios.get(request.portfolio_id)
    if not portfolio:
        raise HTTPException(status_code=404, detail="unknown reviewed portfolio")
    bindings = data_plane.portfolio_bindings(request.portfolio_id)
    permnos = [item["permno"] for item in bindings]
    rows = data_plane._dict_rows(
        f"""
        SELECT permno, date, abs(prc) AS price
        FROM read_parquet(?)
        WHERE permno IN ({data_plane.placeholders(permnos)})
          AND date BETWEEN ? AND ?
          AND prc IS NOT NULL
        ORDER BY date, permno
        """,
        [
            data_plane.path("dsf"),
            *permnos,
            request.start_date - timedelta(days=120),
            request.end_date,
        ],
    )
    alias_by_permno = {
        int(item["permno"]): item["instrument_alias"] for item in bindings
    }
    prices_by_date: dict[date, dict[str, float]] = {}
    history_by_alias: dict[str, list[tuple[date, float]]] = {
        item["instrument_alias"]: [] for item in bindings
    }
    for row in rows:
        alias = alias_by_permno[int(row["permno"])]
        price = float(row["price"])
        prices_by_date.setdefault(row["date"], {})[alias] = price
        history_by_alias[alias].append((row["date"], price))
    all_dates = sorted(prices_by_date)
    candidate_dates = [
        item for item in all_dates if request.start_date <= item <= request.end_date
    ]
    interval_pairs: list[tuple[date, date]] = []
    for current in candidate_dates:
        prior = next((item for item in reversed(all_dates) if item < current), None)
        if prior is not None:
            interval_pairs.append((prior, current))
    if not interval_pairs:
        raise HTTPException(
            status_code=422,
            detail="the selected range contains no eligible close-to-close interval",
        )
    included_aliases = set(alias_by_permno.values())
    for prior, current in interval_pairs:
        included_aliases &= set(prices_by_date[prior])
        included_aliases &= set(prices_by_date[current])
    if not included_aliases:
        raise HTTPException(
            status_code=422,
            detail="no holding has complete real close anchors across the selected range",
        )
    quantities = {
        item["instrument_alias"]: float(item["quantity"])
        for item in portfolio["positions"]
        if item["instrument_alias"] in included_aliases
    }
    end_bindings = [
        item for item in bindings if item["instrument_alias"] in included_aliases
    ]
    identities = data_plane.latest_identity(end_bindings, request.end_date)
    classifications = data_plane.latest_classification(end_bindings, request.end_date)
    instruments = []
    daily_volatility: dict[str, float] = {}
    for binding in end_bindings:
        alias = binding["instrument_alias"]
        identity = identities.get(binding["permno"], {})
        classification = classifications.get(binding["permno"], {})
        history = history_by_alias[alias]
        returns = [
            math.log(current / prior)
            for (_, prior), (_, current) in zip(history, history[1:])
            if prior > 0 and current > 0
        ]
        estimated = statistics.stdev(returns[-60:]) if len(returns) >= 2 else 0.02
        daily_volatility[alias] = min(max(estimated, 0.005), 0.08)
        instruments.append(
            {
                "instrument_id": alias,
                "display_name": identity.get("comnam")
                or classification.get("conm")
                or alias,
                "ticker": identity.get("ticker") or classification.get("tic"),
                "sector": GICS_SECTOR_NAMES.get(
                    str(classification.get("gsubind") or classification.get("gind") or "")[:2]
                ),
            }
        )
    intervals = [
        {
            "date": current.isoformat(),
            "prior_close_date": prior.isoformat(),
            "open_prices": {
                alias: prices_by_date[prior][alias] for alias in sorted(included_aliases)
            },
            "close_prices": {
                alias: prices_by_date[current][alias] for alias in sorted(included_aliases)
            },
            "daily_volatility": daily_volatility,
            "future_close_sealed": True,
        }
        for prior, current in interval_pairs
    ]
    excluded_aliases = sorted(set(alias_by_permno.values()) - included_aliases)
    return {
        "portfolio_id": request.portfolio_id,
        "portfolio_name": portfolio["title"],
        "base_currency": portfolio.get("base_currency", "USD"),
        "cash": sum(float(item.get("amount", 0)) for item in portfolio.get("cash", [])),
        "quantities": quantities,
        "instruments": instruments,
        "intervals": intervals,
        "seed": request.seed,
        "speed": request.speed,
        "daily_loss_limit": request.daily_loss_limit,
        "excluded_holdings": excluded_aliases,
        "generation_method": "seeded log-price Brownian bridge with real daily close anchors",
        "synthetic_intraday": True,
        "empirical_intraday": False,
    }


@app.get("/api/health")
def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "engine": "duckdb",
        "access": "read_only",
        "bind": "localhost",
        "raw_root": str(data_plane.raw_root),
        "datasets": len(data_plane.catalog),
        "reviewed_portfolios": len(data_plane.portfolios),
        "runtime_boundary": LAB_RUNTIME_BOUNDARY,
        "sql_agent": {
            "model": SQL_AGENT_MODEL,
            "reasoning_effort": SQL_AGENT_REASONING_EFFORT,
            "available": bool(_keychain_key()),
            "max_rows": MAX_QUERY_ROWS,
            "max_columns": MAX_QUERY_COLUMNS,
        },
    }


@app.get("/api/platform/workspaces")
def platform_workspaces() -> dict[str, Any]:
    """Project existing stores into the two user-facing operating areas."""

    documents = [
        item
        for item in registry_store().list()
        if item.projection.identity.kind not in INCUBATOR_ASSET_KINDS
    ]
    eligible_states = EXPERIMENT_ELIGIBLE_REGISTRY_STATES
    saved = [
        {
            "identity": item.projection.identity.model_dump(mode="json"),
            "reference": item.projection.identity.reference,
            "display_name": item.projection.display_name,
            "summary": item.projection.summary,
            "lifecycle_state": item.state.value,
            "registry_revision": item.receipts[-1].receipt_digest,
            "experiment_eligible": (
                item.state in eligible_states
                and item.projection.identity.kind
                in {AssetKind.WORKFLOW, AssetKind.EVALUATION}
            ),
        }
        for item in documents
    ]
    saved_counts: dict[str, int] = {}
    for item in saved:
        kind = item["identity"]["kind"]
        saved_counts[kind] = saved_counts.get(kind, 0) + 1
    discovered_analysis_packages = {
        item.identity.asset_id: item
        for item in discover_registry_projections()
        if item.identity.kind is AssetKind.RISK_ANALYSIS_PACKAGE
    }
    analysis_packages = []
    saved_by_reference = {item["reference"]: item for item in saved}
    for definition in RISK_ANALYSIS_PACKAGES:
        projection = discovered_analysis_packages[definition.package_id]
        indexed = saved_by_reference.get(projection.identity.reference)
        analysis_packages.append(
            {
                "definition": definition.model_dump(mode="json"),
                "registry_identity": projection.identity.model_dump(mode="json"),
                "registry_reference": projection.identity.reference,
                "registry_state": indexed["lifecycle_state"] if indexed else "discovered",
                "indexed": indexed is not None,
            }
        )
    return {
        "schema_version": "portfolio-risk.platform-workspaces/v1",
        "zones": [
            {
                "zone_id": "system",
                "title": "System Development",
                "purpose": "Build reusable definitions, then apply them with agents inside controlled fixtures.",
                "accepts": "Drafts and canonical source definitions",
                "produces": "Saved definitions plus temporary application-test work products",
            },
            {
                "zone_id": "research",
                "title": "Experimental Research",
                "purpose": "Compose reproducible experiments and comparisons from saved definitions.",
                "accepts": "Registry identities, immutable source bindings and explicit policies",
                "produces": "Experiment records, run work products, evaluations and retained artifacts",
            },
        ],
        "development_phases": [
            {
                "phase_id": "build",
                "title": "Build the system object",
                "purpose": "Model the reusable object and any companion capabilities together, test them in isolation, and prepare a Registry candidate.",
            },
            {
                "phase_id": "apply",
                "title": "Apply it with an agent",
                "purpose": "Load the saved object and its capabilities into a Fixture Context and inspect how an agent acts upon it.",
            },
        ],
        "terminology": {
            "agent": "A bounded worker that receives context, invokes admitted capabilities, creates work products and escalates under policy.",
            "agent_blueprint": "The reusable, versioned definition of an agent's outcome, context, capabilities, output, authority and evaluation expectations.",
            "agent_application": "The System Development test phase where an agent exercises saved objects inside a labelled Fixture Context.",
            "artifact": "A run work product deliberately retained with provenance and lifecycle policy.",
            "capability": "A reviewed typed operation with explicit inputs, outputs, authority, validation and receipts.",
            "companion_capability": "A capability created alongside an object to create, validate, lifecycle, modify or apply that object.",
            "definition": "A reusable system object with a stable identity and version.",
            "blueprint_draft": "The mutable Agent Blueprint being designed in the Studio. It is not a saved version and refinements apply as bounded diffs.",
            "configuration_review": "The compiler and semantic verification record for one exact blueprint digest.",
            "material_finding": "An unresolved critical or high requirement that blocks development handoff or Registry admission.",
            "development_proposal": "A reviewed, bounded request defining the blueprint, allowed paths, tests, skill and authority for one Studio-Codex job.",
            "development_job": "One authorized Studio-Codex execution that plans, changes, verifies and independently reviews work inside its bounded workspace.",
            "experiment": "A reproducible composition of saved definitions, source bindings and execution/evaluation policy.",
            "experiment_set": "A governed group or factor matrix of independent experiments answering one research question.",
            "fixture_context": "A labelled, bounded input environment used to exercise a definition.",
            "mandate_version": "An immutable version of portfolio rules, covenants, interpretations and effective dates.",
            "portfolio_version": "An immutable portfolio identity, holdings/cash state and point-in-time provenance boundary.",
            "promotion": "A separate reviewed process that turns an approved proposal into a new reusable definition version.",
            "provider_adapter": "A governed interface to an MCP, API, database or other integration with schemas, rights and effect boundaries.",
            "registry_candidate": "A saved definition version indexed for local review but not yet validated or published.",
            "registry_admission": "The explicit decision to index an exact tested definition version in the Registry; it is separate from development and execution.",
            "risk_analysis_package": "A reusable risk-question-first composition of semantic data roles, analytical capabilities, validation and structured output fields.",
            "run_work_product": "An output created during one application or experiment run.",
            "scenario_definition": "A reusable declaration of assumptions, shocks, temporal behavior, applicability and result contracts.",
            "studio_codex": "The development-only gateway that turns an authorized Development Proposal into one isolated Development Job, test evidence and a reviewed diff.",
            "system_object": "A reusable definition developed and governed by the platform rather than an output from one run.",
            "workflow_definition": "A reusable composition of agents, state, routes, interrupts, review points and output contracts.",
        },
        "definition_lifecycle": [
            "author_draft",
            "isolated_fixture_test",
            "index_candidate",
            "validate",
            "publish_locally",
            "load_into_application_or_experiment",
        ],
        "saved_definitions": saved,
        "saved_counts": saved_counts,
        "risk_analysis_packages": analysis_packages,
        "portfolios": _licensed_portfolio_projection()["portfolios"],
        "fixture_profiles": [
            {
                "fixture_id": "licensed_real",
                "label": "Licensed historical fixture",
                "data_truth": "licensed_real",
                "description": "Point-in-time CRSP/Compustat records queried locally through DuckDB.",
            },
            {
                "fixture_id": "reviewed_synthetic",
                "label": "Reviewed synthetic fixture",
                "data_truth": "reviewed_synthetic",
                "description": "Named deterministic cases for normal, failure and adversarial behavior.",
            },
            {
                "fixture_id": "simulated_intraday",
                "label": "Real-anchored simulated intraday",
                "data_truth": "simulated_intraday",
                "description": "Seeded intraday evolution between licensed daily close anchors.",
            },
        ],
        "studio_profiles": [
            {
                "studio_id": "risk_analysis",
                "title": "Risk Analysis Studio",
                "definition_label": "RiskAnalysisPackageDefinition",
                "registry_kind": "risk_analysis_package",
                "purpose": "Describe a portfolio-risk question, then compile semantic data roles, modular analytical methods, validation and a structured ArchitectureOutput.",
                "companion_policy": "Capabilities remain openly discoverable. The package pins validated defaults, permits recorded compatible substitutions and keeps supplemental work separate from the stable core.",
                "companion_examples": ["portfolio.data_context.create", "risk.volatility.annualized", "risk.drawdown.maximum", "risk.var.historical", "risk.expected_shortfall.historical"],
                "skill_id": "servicefabric-risk-analysis-package-builder",
                "availability": "reference_package_and_registry",
            },
            {
                "studio_id": "capability",
                "title": "Capability Studio",
                "definition_label": "CapabilityDefinition",
                "registry_kind": "capability",
                "purpose": "Build one typed, least-privilege operation with input preparation, execution, validation and receipts.",
                "companion_policy": "The capability is the primary object. Add a lifecycle meta-capability only when it materially improves creation, validation or versioning.",
                "companion_examples": ["capability.validate", "capability.test_case.run", "capability.publish_candidate"],
                "skill_id": "servicefabric-capability-builder",
                "availability": "registry_and_fixed_tests",
            },
            {
                "studio_id": "scenario",
                "title": "Scenario Studio",
                "definition_label": "ScenarioDefinition",
                "registry_kind": "scenario",
                "purpose": "Model scenario assumptions, shocks, temporal behavior, applicability and deterministic result contracts.",
                "companion_policy": "Create capabilities that instantiate, parameterize, validate, compare and lifecycle the scenario without silently changing its assumptions.",
                "companion_examples": ["scenario.parameterize", "scenario.validate", "scenario.compare", "scenario.revise_candidate"],
                "skill_id": "servicefabric-scenario-builder",
                "availability": "registry_and_future_studio",
            },
            {
                "studio_id": "portfolio_mandate",
                "title": "Mandate Studio",
                "definition_label": "MandateVersion + RiskPolicySet",
                "registry_kind": "mandate",
                "purpose": "Design investment intent and compile every reviewed clause into a capability-bound policy and governance route before experiment assembly.",
                "companion_policy": "Extract and classify clauses at design time, reuse registered evaluation capabilities, preserve source provenance and keep observations, breaches and experimental failures inside Evaluation.",
                "companion_examples": ["mandate.extract", "mandate.validate", "mandate.rules.compile", "monitoring.policy.evaluate"],
                "skill_id": "servicefabric-portfolio-mandate-builder",
                "availability": "reference_fixtures_and_registry",
            },
            {
                "studio_id": "workflow",
                "title": "Workflow Studio",
                "definition_label": "AgentGraphDefinition + WorkflowDefinition",
                "registry_kind": "workflow",
                "purpose": "Compose saved agents into explicit routes, state transitions, interrupts, review points and output contracts.",
                "companion_policy": "Prefer native LangGraph routing, state and interrupt methods. Add capabilities only for typed workflow lifecycle, validation or external operations.",
                "companion_examples": ["workflow.compile", "workflow.validate", "workflow.replay", "workflow.publish_candidate"],
                "skill_id": "servicefabric-workflow-builder",
                "availability": "PLATFORM-P14",
            },
            {
                "studio_id": "provider_connector",
                "title": "Provider & Connector Studio",
                "definition_label": "ProviderAdapter",
                "registry_kind": None,
                "purpose": "Model MCP, API and database integrations with rights, secrets, schemas, health checks and effect boundaries.",
                "companion_policy": "Build capabilities that discover, configure, query and health-check the adapter through reviewed typed contracts rather than granting raw provider access.",
                "companion_examples": ["provider.discover", "provider.configure", "provider.healthcheck", "provider.query"],
                "skill_id": "servicefabric-provider-adapter-builder",
                "availability": "PLATFORM-P15",
            },
            {
                "studio_id": "agent",
                "title": "Agent Studio",
                "definition_label": "AgentBlueprint",
                "registry_kind": "agent",
                "purpose": "Model a bounded agent's objective, state, routing, tools, prompts, outputs, authority and test expectations.",
                "companion_policy": "Domain capabilities remain selected dependencies. Create companion capabilities only for agent lifecycle, specialist/sub-agent creation, or operations not already native to LangGraph.",
                "companion_examples": ["agent.validate", "agent.fixture.run", "agent.specialist.propose", "agent.publish_candidate"],
                "skill_id": "servicefabric-agent-builder",
                "availability": "agent_studio_and_registry",
            },
        ],
        "future_dependencies": [
            {
                "phase": "PLATFORM-P7",
                "capability": "Fixture Context compiler and cumulative Environment Risk Context boundary",
                "unlocks": "Portable context fixtures that can be reused across object tests.",
            },
            {
                "phase": "PLATFORM-P8",
                "capability": "End-to-end Agent Application execution adapter",
                "unlocks": "Execute the selected saved agent against the selected saved objects in one vertical slice.",
            },
            {
                "phase": "PLATFORM-P9",
                "capability": "Mandate Lab and registered portfolio/mandate versions",
                "unlocks": "First-class mandate and portfolio selection rather than source-binding text references.",
            },
            {
                "phase": "PLATFORM-P14",
                "capability": "Agent graph and workflow composition",
                "unlocks": "Fractioned human-review, supra-agent and modular workflow experimental policies.",
            },
            {
                "phase": "PLATFORM-P15",
                "capability": "Provider and external adapter registry",
                "unlocks": "Governed MCP, API and external integration selection.",
            },
        ],
    }


@app.get("/api/catalog")
def catalog() -> dict[str, Any]:
    return {
        "engine": "duckdb",
        "datasets": data_plane.catalog,
    }


@app.get("/api/portfolios")
def portfolios() -> dict[str, Any]:
    return {
        "selection_id": data_plane.selection["selection_id"],
        "reviewed": data_plane.selection["reviewed"],
        "portfolios": data_plane.public_portfolios(),
    }


@app.post("/api/query/portfolio")
def query_portfolio(request: PortfolioQueryRequest) -> dict[str, Any]:
    try:
        return data_plane.query_portfolio(request)
    except HTTPException:
        raise
    except duckdb.Error as error:
        raise HTTPException(status_code=422, detail=f"DuckDB query failed: {error}") from error


@app.post("/api/query/ask")
def ask_database(request: NaturalLanguageQueryRequest) -> dict[str, Any]:
    try:
        sql, receipt = plan_sql(request.question)
        result = data_plane.execute_generated_sql(sql)
        return {
            "question": request.question,
            **result,
            "receipt": receipt,
        }
    except (ValueError, json.JSONDecodeError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except duckdb.Error as error:
        raise HTTPException(
            status_code=422,
            detail=f"DuckDB could not execute the generated query: {error}",
        ) from error
    except Exception as error:
        safe_type = re.sub(r"[^A-Za-z0-9_-]", "_", type(error).__name__)[:64]
        raise HTTPException(
            status_code=502,
            detail=f"Luna SQL generation failed: {safe_type}",
        ) from error


@app.get("/api/registry/catalogue")
def registry_catalogue(
    kind: AssetKind | None = None,
    state: LifecycleState | None = None,
    q: str | None = None,
    include_discovered: bool = True,
) -> dict[str, Any]:
    store = registry_store()
    indexed = [
        document
        for document in store.list(kind=kind, state=state, query=q)
        if document.projection.identity.kind not in INCUBATOR_ASSET_KINDS
    ]
    indexed_by_reference = {
        document.projection.identity.reference: document for document in indexed
    }
    records = [document_payload(document) for document in indexed]
    if include_discovered and state is None:
        needle = (q or "").strip().casefold()
        for projection in discover_registry_projections():
            if kind is not None and projection.identity.kind is not kind:
                continue
            if projection.identity.reference in indexed_by_reference:
                continue
            if needle and not any(
                needle in value.casefold()
                for value in (
                    projection.identity.asset_id,
                    projection.display_name,
                    projection.summary,
                    *projection.tags,
                )
            ):
                continue
            records.append(discovered_payload(projection, indexed=False))
    records.sort(
        key=lambda item: (
            item["projection"]["identity"]["kind"],
            item["projection"]["display_name"].casefold(),
            item["projection"]["identity"]["version"],
        )
    )
    counts: dict[str, int] = {}
    states: dict[str, int] = {}
    for record in records:
        asset_kind = record["projection"]["identity"]["kind"]
        counts[asset_kind] = counts.get(asset_kind, 0) + 1
        states[record["state"]] = states.get(record["state"], 0) + 1
    return {
        "profile": "development",
        "production_publication": False,
        "canonical_definitions_embedded": False,
        "storage": "local development registry",
        "records": records,
        "counts": counts,
        "states": states,
    }


@app.get("/api/incubator/catalogue")
def incubator_catalogue() -> dict[str, Any]:
    """Describe deferred objects without admitting them to active discovery."""

    path = (
        PROTOTYPE_ROOT.parents[2]
        / "config"
        / "incubator"
        / "post-thesis-user-facing-objects.yaml"
    )
    decision = yaml.safe_load(path.read_text(encoding="utf-8"))
    historical_records = [
        {
            "reference": document.projection.identity.reference,
            "display_name": document.projection.display_name,
            "kind": document.projection.identity.kind.value,
            "historical_lifecycle_state": document.state.value,
            "active": False,
        }
        for document in registry_store().list()
        if document.projection.identity.kind in INCUBATOR_ASSET_KINDS
    ]
    return {**decision, "historical_registry_records": historical_records}


@app.post("/api/registry/bootstrap")
def bootstrap_registry(request: RegistryBootstrapRequest) -> dict[str, Any]:
    store = registry_store()
    projections = discover_registry_projections()
    preview = store.preview_many(projections)
    documents, conflicts = store.index_many(projections, actor=request.actor)
    return {
        "discovered": len(projections),
        "indexed_total": len(documents),
        "newly_indexed": preview["would_index"] if not conflicts else 0,
        "already_indexed": preview["already_indexed"],
        "conflicts": conflicts,
        "records": [document_payload(document) for document in documents],
        "storage": "local development registry",
        "production_publication": False,
    }


@app.post("/api/registry/bootstrap/preview")
def preview_registry_bootstrap(request: RegistryBootstrapRequest) -> dict[str, Any]:
    projections = discover_registry_projections()
    preview = registry_store().preview_many(projections)
    return {
        **preview,
        "actor": request.actor,
        "consequence": (
            "Create local metadata projections and initial candidate receipts only; "
            "do not copy, run, deploy, or externally publish definitions."
        ),
        "production_publication": False,
    }


@app.post("/api/registry/index")
def index_registry_item(request: RegistryIndexRequest) -> dict[str, Any]:
    projection = next(
        (
            item
            for item in discover_registry_projections()
            if item.identity == request.identity
        ),
        None,
    )
    if projection is None:
        raise HTTPException(status_code=404, detail="source definition not found")
    try:
        return document_payload(registry_store().index(projection, actor=request.actor))
    except RegistryConflict as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@app.get("/api/registry/items/{kind}/{asset_id}/{version}")
def registry_item(
    kind: AssetKind, asset_id: str, version: str, namespace: str
) -> dict[str, Any]:
    identity = RegistryIdentity(
        kind=kind, namespace=namespace, asset_id=asset_id, version=version
    )
    try:
        document = registry_store().get(identity)
    except RegistryNotFound as error:
        raise HTTPException(status_code=404, detail="registry item not found") from error
    payload = document_payload(document)
    current = {
        item.identity.reference: item for item in discover_registry_projections()
    }.get(identity.reference)
    payload["source_drift"] = bool(
        current and current.source.source_digest != document.projection.source.source_digest
    )
    payload["current_source_digest"] = current.source.source_digest if current else None
    return payload


@app.post("/api/registry/transition")
def transition_registry_item(request: RegistryTransitionRequest) -> dict[str, Any]:
    identity = RegistryIdentity(
        kind=request.kind,
        namespace=request.namespace,
        asset_id=request.asset_id,
        version=request.version,
    )
    try:
        indexed = registry_store().get(identity)
        current = next(
            (
                item
                for item in discover_registry_projections()
                if item.identity == identity
            ),
            None,
        )
        if (
            request.to_state is LifecycleState.PUBLISHED
            and (
                current is None
                or current.source.definition_digest
                != indexed.projection.source.definition_digest
                or current.source.adapter_digest
                != indexed.projection.source.adapter_digest
            )
        ):
            raise RegistryConflict(
                "publication requires a current source and source-adapter observation"
            )
        document = registry_store().transition(
            identity,
            request.to_state,
            actor=request.actor,
            rationale=request.rationale,
            replacement_reference=request.replacement_reference,
            expected_revision=request.expected_revision,
        )
        return document_payload(document)
    except RegistryNotFound as error:
        raise HTTPException(status_code=404, detail="registry item not found") from error
    except (RegistryConflict, ValueError) as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@app.post("/api/registry/compare")
def compare_registry_items(request: RegistryCompareRequest) -> dict[str, Any]:
    try:
        comparison = registry_store().compare(request.left, request.right)
    except RegistryNotFound as error:
        raise HTTPException(status_code=404, detail="registry item not found") from error
    except RegistryConflict as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    return {
        "left": document_payload(comparison["left"]),
        "right": document_payload(comparison["right"]),
        "same_asset": comparison["same_asset"],
        "differences": comparison["differences"],
    }


def _artifact_error(error: Exception) -> HTTPException:
    if isinstance(error, ArtifactNotFound):
        return HTTPException(status_code=404, detail="artifact or file not found")
    return HTTPException(status_code=409, detail=str(error))


@app.get("/api/artifacts/catalogue")
def artifact_catalogue(include_deleted: bool = False) -> dict[str, Any]:
    try:
        return catalogue_payload(include_deleted=include_deleted)
    except (ArtifactConflict, ArtifactNotFound, ValueError) as error:
        raise _artifact_error(error) from error


@app.get("/api/artifacts/{artifact_id}")
def artifact_detail(artifact_id: str) -> dict[str, Any]:
    try:
        store = artifact_store()
        record = store.get(artifact_id)
        payload = record_payload(record)
        payload["verification"] = store.verify(artifact_id).model_dump(mode="json")
        if record.state in {ArtifactLifecycleState.ACTIVE, ArtifactLifecycleState.ARCHIVED}:
            payload["deletion_preview"] = store.deletion_preview(artifact_id).model_dump(mode="json")
        elif record.state == ArtifactLifecycleState.TOMBSTONED:
            payload["deletion_preview"] = store.deletion_preview(
                artifact_id, finalize=True
            ).model_dump(mode="json")
        else:
            payload["deletion_preview"] = None
        return payload
    except (ArtifactConflict, ArtifactNotFound, ValueError) as error:
        raise _artifact_error(error) from error


@app.post("/api/artifacts/{artifact_id}/verify")
def verify_artifact(artifact_id: str) -> dict[str, Any]:
    try:
        return artifact_store().verify(artifact_id).model_dump(mode="json")
    except (ArtifactConflict, ArtifactNotFound, ValueError) as error:
        raise _artifact_error(error) from error


@app.get("/api/artifacts/{artifact_id}/files/{file_id}/preview")
def preview_artifact_file(artifact_id: str, file_id: str) -> dict[str, Any]:
    try:
        record = artifact_store().get(artifact_id)
        item = next((value for value in record.manifest.files if value.file_id == file_id), None)
        if item is None:
            raise ArtifactNotFound(file_id)
        content, _media_type = artifact_store().open_file(artifact_id, item.path)
        if len(content) > 250_000:
            raise ArtifactConflict("file is too large for bounded browser preview")
        return {
            "artifact_id": artifact_id,
            "file_id": file_id,
            "logical_name": item.path,
            "rendering": "escaped_text_only",
            "text": content.decode("utf-8", errors="replace"),
        }
    except (ArtifactConflict, ArtifactNotFound, ValueError) as error:
        raise _artifact_error(error) from error


@app.get("/api/artifacts/{artifact_id}/files/{file_id}/download")
def download_artifact_file(artifact_id: str, file_id: str) -> Response:
    try:
        record = artifact_store().get(artifact_id)
        item = next((value for value in record.manifest.files if value.file_id == file_id), None)
        if item is None:
            raise ArtifactNotFound(file_id)
        content, media_type = artifact_store().open_file(artifact_id, item.path, download=True)
        safe_name = re.sub(r"[^A-Za-z0-9._-]", "_", Path(item.path).name)[:120]
        return Response(
            content=content,
            media_type=media_type,
            headers={
                "Content-Disposition": f'attachment; filename="{safe_name}"',
                "X-Content-Type-Options": "nosniff",
                "Content-Security-Policy": "default-src 'none'",
            },
        )
    except (ArtifactConflict, ArtifactNotFound, ValueError) as error:
        raise _artifact_error(error) from error


@app.post("/api/artifacts/{artifact_id}/archive")
def archive_artifact(artifact_id: str, request: ArtifactTransitionRequest) -> dict[str, Any]:
    try:
        record = artifact_store().transition(
            artifact_id,
            to_state=ArtifactLifecycleState.ARCHIVED,
            actor=request.actor,
            rationale=request.rationale,
            expected_revision=request.expected_revision,
        )
        return record_payload(record)
    except (ArtifactConflict, ArtifactNotFound, ValueError) as error:
        raise _artifact_error(error) from error


@app.post("/api/artifacts/{artifact_id}/restore")
def restore_artifact(artifact_id: str, request: ArtifactTransitionRequest) -> dict[str, Any]:
    try:
        store = artifact_store()
        current = store.get(artifact_id)
        if current.state == ArtifactLifecycleState.TOMBSTONED:
            record = store.restore_tombstone(
                artifact_id,
                actor=request.actor,
                rationale=request.rationale,
                expected_revision=request.expected_revision,
            )
        else:
            record = store.transition(
                artifact_id,
                to_state=ArtifactLifecycleState.ACTIVE,
                actor=request.actor,
                rationale=request.rationale,
                expected_revision=request.expected_revision,
            )
        return record_payload(record)
    except (ArtifactConflict, ArtifactNotFound, ValueError) as error:
        raise _artifact_error(error) from error


@app.post("/api/artifacts/{artifact_id}/tombstone")
def tombstone_artifact(artifact_id: str, request: ArtifactDeletionRequest) -> dict[str, Any]:
    try:
        record = artifact_store().tombstone(
            artifact_id,
            confirmation_token=request.confirmation_token,
            expected_revision=request.expected_revision,
            actor=request.actor,
            rationale=request.rationale,
        )
        return record_payload(record)
    except (ArtifactConflict, ArtifactNotFound, ValueError) as error:
        raise _artifact_error(error) from error


@app.post("/api/artifacts/{artifact_id}/finalize")
def finalize_artifact_deletion(artifact_id: str, request: ArtifactDeletionRequest) -> dict[str, Any]:
    try:
        record = artifact_store().finalize_delete(
            artifact_id,
            confirmation_token=request.confirmation_token,
            expected_revision=request.expected_revision,
            actor=request.actor,
            rationale=request.rationale,
        )
        return record_payload(record)
    except (ArtifactConflict, ArtifactNotFound, ValueError) as error:
        raise _artifact_error(error) from error


@app.get("/api/artifacts/admission/{run_id}/preview")
def preview_artifact_admission(run_id: str) -> dict[str, Any]:
    return preview_legacy_run(RUN_ROOT, run_id).payload()


@app.post("/api/artifacts/admission")
def admit_artifact_run(request: ArtifactAdmissionRequest) -> dict[str, Any]:
    try:
        manifest, files = compile_legacy_run(
            RUN_ROOT,
            request.run_id,
            confirmation_token=request.confirmation_token,
        )
        record = artifact_store().admit(
            manifest,
            files,
            actor=request.actor,
            rationale="Explicitly admitted a validated Agent Lab run after preview.",
        )
        verification = artifact_store().verify(record.manifest.artifact_id)
        if not verification.valid:
            raise ArtifactConflict("admitted run failed repository integrity verification")
        return record_payload(record)
    except (ArtifactConflict, ArtifactNotFound, LegacyRunInvalid, ValueError) as error:
        raise _artifact_error(error) from error


def _experiment_error(error: Exception) -> HTTPException:
    if isinstance(error, ExperimentNotFound):
        return HTTPException(status_code=404, detail="experiment, set, or queue entry not found")
    return HTTPException(status_code=409, detail=str(error))


@app.get("/api/experiments/catalogue")
def experiment_catalogue() -> dict[str, Any]:
    try:
        return experiment_catalogue_payload()
    except (ExperimentConflict, ExperimentNotFound, ValueError) as error:
        raise _experiment_error(error) from error


@app.get("/api/experiments/replay-setup")
def historical_replay_setup() -> dict[str, Any]:
    """Return only the real-data choices used by the simplified Experiment page."""

    try:
        workflows = [
            {
                "asset_id": projection.identity.asset_id,
                "display_name": projection.display_name,
            }
            for projection in discover_registry_projections()
            if projection.identity.kind is AssetKind.WORKFLOW
        ]
        return historical_replay_setup_payload(
            find_private_root(PROTOTYPE_ROOT), workflows
        )
    except (HistoricalReplayError, RuntimeError, duckdb.Error) as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


@app.get("/api/experiments/signals")
def experiment_signal_preview(
    portfolio_id: str,
    start_date: date,
    end_date: date,
) -> dict[str, Any]:
    """Run the admitted detectors behind the existing Find cases journey."""

    try:
        return signal_preview_payload(
            find_private_root(PROTOTYPE_ROOT),
            portfolio_id=portfolio_id,
            start_date=start_date,
            end_date=end_date,
        )
    except (HistoricalReplayError, RuntimeError, duckdb.Error, ValueError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


def _labelling_error(error: Exception) -> HTTPException:
    if isinstance(error, (LabelProductionNotFound, ContextWorkNotFound)):
        return HTTPException(status_code=404, detail="labelling batch or review item not found")
    return HTTPException(status_code=409, detail=str(error))


@app.get("/api/experiments/label-batches")
def experiment_label_batches() -> dict[str, Any]:
    """List resumable pre-experiment signal-labelling batches."""

    try:
        return list_labelling_batches(find_private_root(PROTOTYPE_ROOT))
    except (LabelProductionConflict, LabelProductionNotFound, HistoricalReplayError, duckdb.Error, ValueError) as error:
        raise _labelling_error(error) from error


@app.post("/api/experiments/label-batches")
def experiment_create_label_batch(request: LabellingBatchRequest) -> dict[str, Any]:
    """Select an informative detector-signal sample; do not create Gold cases."""

    try:
        return create_labelling_batch(find_private_root(PROTOTYPE_ROOT), request)
    except (LabelProductionConflict, LabelProductionNotFound, HistoricalReplayError, duckdb.Error, ValueError) as error:
        raise _labelling_error(error) from error


@app.get("/api/experiments/label-batches/{batch_id}")
def experiment_label_batch(batch_id: str) -> dict[str, Any]:
    try:
        return labelling_batch_payload(find_private_root(PROTOTYPE_ROOT), batch_id)
    except (LabelProductionConflict, LabelProductionNotFound, HistoricalReplayError, duckdb.Error, ValueError) as error:
        raise _labelling_error(error) from error


@app.post("/api/experiments/label-batches/{batch_id}/study")
def experiment_study_label_item(batch_id: str, request: LabelStudyRequest) -> dict[str, Any]:
    """Calculate retrospective study aids; never create or approve a label."""

    try:
        return study_review_unit(find_private_root(PROTOTYPE_ROOT), batch_id, request)
    except (LabelProductionConflict, LabelProductionNotFound, HistoricalReplayError, duckdb.Error, ValueError) as error:
        raise _labelling_error(error) from error


@app.post("/api/experiments/label-batches/{batch_id}/context-readiness")
def experiment_context_readiness(batch_id: str, request: ContextReadinessRequest) -> dict[str, Any]:
    """Profile later context dependencies; never retrieve or associate evidence."""

    try:
        return context_source_readiness(find_private_root(PROTOTYPE_ROOT), batch_id, request)
    except (ContextWorkConflict, ContextWorkNotFound, LabelProductionConflict, LabelProductionNotFound, HistoricalReplayError, duckdb.Error, ValueError) as error:
        raise _labelling_error(error) from error


@app.post("/api/experiments/label-batches/{batch_id}/context-plans/validate")
def experiment_validate_context_plan(batch_id: str, request: ContextWorkPlanRequest) -> dict[str, Any]:
    """Compile and validate a dormant plan; perform no retrieval or association."""

    try:
        return validate_context_work_plan(find_private_root(PROTOTYPE_ROOT), batch_id, request)
    except (ContextWorkConflict, ContextWorkNotFound, LabelProductionConflict, LabelProductionNotFound, HistoricalReplayError, duckdb.Error, ValueError) as error:
        raise _labelling_error(error) from error


@app.post("/api/experiments/label-batches/{batch_id}/context-plans")
def experiment_save_context_plan(batch_id: str, request: ContextWorkPlanRequest) -> dict[str, Any]:
    """Save an immutable plan revision; perform no retrieval or association."""

    try:
        return save_context_work_plan(find_private_root(PROTOTYPE_ROOT), batch_id, request)
    except (ContextWorkConflict, ContextWorkNotFound, LabelProductionConflict, LabelProductionNotFound, HistoricalReplayError, duckdb.Error, ValueError) as error:
        raise _labelling_error(error) from error


@app.post("/api/experiments/label-batches/{batch_id}/context-work/prepare")
def experiment_prepare_context_work(batch_id: str, request: ContextPreparationRequest) -> dict[str, Any]:
    """Prepare bounded evidence candidates for human review; never modify the label."""

    try:
        return prepare_context_work(find_private_root(PROTOTYPE_ROOT), batch_id, request)
    except (ContextWorkConflict, ContextWorkNotFound, LabelProductionConflict, LabelProductionNotFound, HistoricalReplayError, duckdb.Error, ValueError) as error:
        raise _labelling_error(error) from error


@app.post("/api/experiments/label-batches/{batch_id}/context-work/review")
def experiment_review_context_work(batch_id: str, request: ContextReviewRequest) -> dict[str, Any]:
    """Retain, reject or challenge prepared candidates without changing the label."""

    try:
        return review_prepared_context(find_private_root(PROTOTYPE_ROOT), batch_id, request)
    except (ContextWorkConflict, ContextWorkNotFound, LabelProductionConflict, LabelProductionNotFound, HistoricalReplayError, duckdb.Error, ValueError) as error:
        raise _labelling_error(error) from error


@app.get("/api/experiments/label-batches/{batch_id}/gold-work/{unit_id}")
def experiment_gold_work(batch_id: str, unit_id: str) -> dict[str, Any]:
    try:
        return gold_work_payload(batch_id, unit_id)
    except (GoldCaseConflict, GoldCaseNotFound, LabelProductionConflict, LabelProductionNotFound, ValueError) as error:
        raise _labelling_error(error) from error


@app.post("/api/experiments/label-batches/{batch_id}/gold-work/prepare")
def experiment_prepare_gold_reference(batch_id: str, request: GoldPreparationRequest) -> dict[str, Any]:
    try:
        return prepare_gold_reference(batch_id, request)
    except (GoldCaseConflict, GoldCaseNotFound, LabelProductionConflict, LabelProductionNotFound, ValueError) as error:
        raise _labelling_error(error) from error


@app.post("/api/experiments/label-batches/{batch_id}/gold-work/review")
def experiment_review_gold_reference(batch_id: str, request: GoldReviewRequest) -> dict[str, Any]:
    try:
        return review_gold_reference(batch_id, request)
    except (GoldCaseConflict, GoldCaseNotFound, LabelProductionConflict, LabelProductionNotFound, ValueError) as error:
        raise _labelling_error(error) from error


@app.post("/api/experiments/label-batches/{batch_id}/gold-work/compile-case")
def experiment_compile_gold_case(batch_id: str, request: ExperimentalCaseCompileRequest) -> dict[str, Any]:
    try:
        return compile_gold_experimental_case(batch_id, request)
    except (GoldCaseConflict, GoldCaseNotFound, LabelProductionConflict, LabelProductionNotFound, ValueError) as error:
        raise _labelling_error(error) from error


@app.get("/api/experiments/matched-run-plans/setup")
def experiment_matched_run_setup() -> dict[str, Any]:
    """Show only governed Cases and bounded compile-time choices."""
    try:
        return matched_run_setup()
    except (GoldCaseConflict, GoldCaseNotFound, MatchedRunConflict, ValueError) as error:
        raise _labelling_error(error) from error


@app.post("/api/experiments/matched-run-plans/compile")
def experiment_compile_matched_run_plan(request: MatchedRunCompileRequest) -> dict[str, Any]:
    """Save a matrix plan without invoking models, capabilities, or replay."""
    try:
        return compile_matched_plan(request)
    except (GoldCaseConflict, GoldCaseNotFound, MatchedRunConflict, ValueError) as error:
        raise _labelling_error(error) from error


@app.get("/api/experiments/matched-run-plans/{matrix_id}")
def experiment_get_matched_run_plan(matrix_id: str) -> dict[str, Any]:
    try:
        return get_matched_plan(matrix_id)
    except (MatchedRunConflict, MatchedRunNotFound, ValueError) as error:
        raise _labelling_error(error) from error


@app.get("/api/experiments/cases/{case_id}/replay-preview")
def experiment_case_replay_preview(case_id: str) -> dict[str, Any]:
    """Verify the complete point-in-time stream without exposing Gold truth."""
    try:
        return case_replay_preview(case_id)
    except (GoldCaseConflict, GoldCaseNotFound, LabelProductionConflict, LabelProductionNotFound, ValueError) as error:
        raise _labelling_error(error) from error


@app.post("/api/experiments/matched-run-plans/{matrix_id}/cells/{cell_id}/execute")
def experiment_execute_trajectory_cell(matrix_id: str, cell_id: str) -> dict[str, Any]:
    """Execute one admitted cell within its sealed budget and authorization."""
    try:
        return execute_trajectory_cell(matrix_id, cell_id)
    except (GoldCaseConflict, GoldCaseNotFound, MatchedRunConflict, MatchedRunNotFound, ValueError) as error:
        raise _labelling_error(error) from error


@app.get("/api/experiments/matched-run-plans/{matrix_id}/results")
def experiment_list_trajectory_results(matrix_id: str) -> dict[str, Any]:
    """Return a compact projection of retained results for the comparison page."""
    try:
        return list_trajectory_results(matrix_id)
    except (MatchedRunConflict, MatchedRunNotFound, ValueError) as error:
        raise _labelling_error(error) from error


@app.get("/api/experiments/matched-run-plans/{matrix_id}/cells/{cell_id}/result")
def experiment_get_trajectory_result(matrix_id: str, cell_id: str) -> dict[str, Any]:
    """Return the readable cycle timeline; internal receipts remain persisted."""
    try:
        return get_trajectory_result(matrix_id, cell_id)
    except (MatchedRunConflict, MatchedRunNotFound, TrajectoryNotFound, ValueError) as error:
        raise _labelling_error(error) from error


@app.get("/api/experiments/matched-run-plans/{matrix_id}/evaluation")
def experiment_evaluate_matched_run_plan(matrix_id: str) -> dict[str, Any]:
    """Join hidden Gold truth after execution and retain truthful Run evaluations."""
    try:
        return evaluate_matched_matrix(matrix_id)
    except (GoldCaseConflict, GoldCaseNotFound, MatchedRunConflict, MatchedRunNotFound, ValueError) as error:
        raise _labelling_error(error) from error


class ReproducibilityRemovalRequest(BaseModel):
    confirmation: str = Field(min_length=3, max_length=160)


@app.post("/api/experiments/matched-run-plans/{matrix_id}/bundle")
def experiment_save_comparison_bundle(matrix_id: str) -> dict[str, Any]:
    try:
        return create_reproducibility_bundle(matrix_id)
    except (ReproducibilityConflict, ReproducibilityNotFound, MatchedRunNotFound, ValueError) as error:
        raise _labelling_error(error) from error


@app.get("/api/experiments/reproducibility-bundles")
def experiment_list_comparison_bundles() -> dict[str, Any]:
    return list_reproducibility_bundles()


@app.get("/api/experiments/reproducibility-bundles/{bundle_id}")
def experiment_open_comparison_bundle(bundle_id: str) -> dict[str, Any]:
    try:
        return open_reproducibility_bundle(bundle_id)
    except (ReproducibilityConflict, ReproducibilityNotFound, ValueError) as error:
        raise _labelling_error(error) from error


@app.post("/api/experiments/reproducibility-bundles/{bundle_id}/verify")
def experiment_verify_comparison_bundle(bundle_id: str) -> dict[str, Any]:
    try:
        return verify_reproducibility_bundle(bundle_id)
    except (ReproducibilityConflict, ReproducibilityNotFound, ValueError) as error:
        raise _labelling_error(error) from error


@app.post("/api/experiments/reproducibility-bundles/{bundle_id}/archive")
def experiment_archive_comparison_bundle(bundle_id: str) -> dict[str, Any]:
    try:
        return archive_reproducibility_bundle(bundle_id)
    except (ReproducibilityConflict, ReproducibilityNotFound, ValueError) as error:
        raise _labelling_error(error) from error


@app.post("/api/experiments/reproducibility-bundles/{bundle_id}/restore")
def experiment_restore_comparison_bundle(bundle_id: str) -> dict[str, Any]:
    try:
        return restore_reproducibility_bundle(bundle_id)
    except (ReproducibilityConflict, ReproducibilityNotFound, ValueError) as error:
        raise _labelling_error(error) from error


@app.delete("/api/experiments/reproducibility-bundles/{bundle_id}")
def experiment_remove_comparison_bundle(bundle_id: str, request: ReproducibilityRemovalRequest) -> dict[str, Any]:
    try:
        return remove_reproducibility_bundle(bundle_id, request.confirmation)
    except (ReproducibilityConflict, ReproducibilityNotFound, ValueError) as error:
        raise _labelling_error(error) from error


@app.post("/api/experiments/label-batches/{batch_id}/annotations")
def experiment_record_label_annotation(
    batch_id: str,
    request: SignalAnnotationRequest,
) -> dict[str, Any]:
    try:
        return record_signal_annotation(find_private_root(PROTOTYPE_ROOT), batch_id, request)
    except (LabelProductionConflict, LabelProductionNotFound, HistoricalReplayError, duckdb.Error, ValueError) as error:
        raise _labelling_error(error) from error


@app.post("/api/experiments/label-batches/{batch_id}/reviews")
def experiment_review_label_annotation(
    batch_id: str,
    request: LabelReviewRequest,
) -> dict[str, Any]:
    try:
        return review_signal_annotation(find_private_root(PROTOTYPE_ROOT), batch_id, request)
    except (LabelProductionConflict, LabelProductionNotFound, HistoricalReplayError, duckdb.Error, ValueError) as error:
        raise _labelling_error(error) from error


@app.get("/api/professor-demo")
def professor_demo() -> dict[str, Any]:
    """Validate the exact demonstration boundary without saving or model use."""

    try:
        return professor_demo_preflight(find_private_root(PROTOTYPE_ROOT))
    except (HistoricalReplayError, RuntimeError, duckdb.Error, ValueError) as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


@app.post("/api/professor-demo/run")
def run_professor_demo(request: ProfessorDemoRunRequest) -> dict[str, Any]:
    """Execute and retain the frozen B0/B1/A1 demonstration comparison."""

    if not request.authorize_external_model_calls:
        raise HTTPException(
            status_code=422,
            detail=(
                "The B1 and A1 demonstration requires explicit authorization for five bounded OpenAI calls"
            ),
        )
    try:
        preflight = professor_demo_preflight(find_private_root(PROTOTYPE_ROOT))
        if not preflight["demo_ready"]:
            failed = [
                item["label"] for item in preflight["checks"]
                if item["required"] and item["status"] == "fail"
            ]
            raise HistoricalReplayError(
                "Professor Demo preflight failed: " + "; ".join(failed)
            )
        definition = professor_demo_definition()
        case = definition["case"]
        response = create_counterfactual_batch(CounterfactualBatchRequest(
            study_id=definition["study"]["study_id"],
            study_title=definition["study"]["title"],
            experiment_id=definition["experiment"]["experiment_id"],
            research_question=definition["experiment"]["research_question"],
            hypothesis=definition["experiment"]["hypothesis"],
            portfolio_ids=(case["portfolio_id"],),
            workflow_ids=tuple(definition["architectures"]),
            baseline_workflow_id="B0",
            start_date=date.fromisoformat(case["start_date"]),
            end_date=date.fromisoformat(case["end_date"]),
            evaluation_id=definition["evaluation_id"],
            repetitions=int(definition["repetitions"]),
            max_concurrency=int(definition["maximum_concurrency"]),
            authorize_external_model_calls=True,
        ))
        return {"preflight": preflight, **response}
    except (HistoricalReplayError, RuntimeError, duckdb.Error, ValueError) as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


def _single_run_assurance(
    result: dict[str, Any], *, retention_requested: bool
) -> dict[str, Any]:
    """Qualify one Run from canonical object metadata without replaying its work.

    Capability contracts remain responsible for their own payload validation and
    errors.  This gate reads only the already-validated Case, RunInput,
    ArchitectureOutput, evaluation, label and telemetry attributes.
    """

    expected_dimensions = {
        "detection_quality", "severity_understanding", "timeliness",
        "evidence_quality", "confidence_calibration", "decision_quality",
        "robustness", "stability", "efficiency",
    }
    required_capabilities = {
        "historical-replay-context",
        "portfolio-risk-metric-pack",
        "event-relevance-classifier",
        "fundamental-state-classifier",
        "mandate-policy-evaluator",
        "mandate-rule-reference-label",
        "daily-session-timeliness",
        "evidence-structural-audit",
        "execution-telemetry-collector",
    }
    hierarchy = result.get("hierarchy", {})
    run_record = result.get("run_record", {})
    run_input = run_record.get("run_input", {})
    evaluation = result.get("evaluation", {})
    reference = evaluation.get("reference_treatment", {})
    dimensions = evaluation.get("dimensions", [])
    outputs = run_record.get("architecture_outputs", [])
    receipts = run_record.get("processing_receipts", [])
    capability_configs = run_input.get("capability_configurations", [])
    capability_ids = {
        item.get("capability_id") for item in capability_configs if item.get("capability_id")
    }
    reference_capabilities = {
        item.get("capability_id")
        for item in capability_configs
        if "reference_label" in item.get("evaluation_roles", [])
    }
    dimension_ids = {item.get("id") for item in dimensions}
    execution_errors = sum(
        len((item.get("execution_summary") or {}).get("errors", [])) for item in outputs
    )
    schema_failures = sum(
        int((item.get("execution_summary") or {}).get("schema_validation_failures", 0) or 0)
        for item in outputs
    )
    semantic_failures = sum(
        int((item.get("execution_summary") or {}).get("semantic_verification_failures", 0) or 0)
        for item in outputs
    )
    limited_dimensions = sorted(
        item.get("id") for item in dimensions
        if item.get("status") in {"partial", "not_measurable", "not_applicable"}
    )

    def check(
        check_id: str,
        label: str,
        passed: bool,
        summary: str,
        *,
        required: bool = True,
        warning: bool = False,
    ) -> dict[str, Any]:
        return {
            "check_id": check_id,
            "label": label,
            "status": "pass" if passed and not warning else "warning" if passed else "fail",
            "required_for_valid_run": required,
            "summary": summary,
        }

    case_valid = bool(
        hierarchy.get("case", {}).get("case_id")
        and hierarchy.get("case", {}).get("context_digest")
        and run_input.get("case_id") == hierarchy.get("case", {}).get("case_id")
    )
    capabilities_ready = required_capabilities.issubset(capability_ids)
    labels_ready = bool(
        reference.get("label_state") == "admitted"
        and reference.get("label_set_digest")
        and int(reference.get("cycles") or 0) == int(evaluation.get("trading_days") or 0)
        and reference_capabilities
    )
    outputs_ready = bool(
        run_record.get("architecture_output")
        and outputs
        and len(outputs) == int(evaluation.get("trading_days") or 0)
        and dimension_ids == expected_dimensions
    )
    runtime_healthy = bool(
        result.get("status") == "completed"
        and int(evaluation.get("workflow_failures") or 0) == 0
        and execution_errors == 0
    )
    telemetry_ready = bool(
        receipts
        and len(receipts) == len(outputs)
        and all(item.get("processing_wall_ms") is not None for item in receipts)
    )

    checks = [
        check(
            "case-contract",
            "The frozen Case is valid",
            case_valid,
            "The RunInput points to the immutable Case and its canonical context digest."
            if case_valid else "The Run is missing a bound Case identity or context digest.",
        ),
        check(
            "capability-readiness",
            "Required capabilities are present",
            capabilities_ready,
            "The registered context, event-classification and reference-label capabilities are available. Capability payloads were not revalidated."
            if capabilities_ready else f"Missing registered capabilities: {', '.join(sorted(required_capabilities - capability_ids))}.",
        ),
        check(
            "label-readiness",
            "Appropriately labelled reference data is present",
            labels_ready,
            f"The admitted {reference.get('scope', 'reference')} labels cover {reference.get('cycles', 0)} of {evaluation.get('trading_days', 0)} workflow cycles and remain outside architecture inputs."
            if labels_ready else "The admitted label digest, reference-label capability or full cycle coverage is missing.",
        ),
        check(
            "output-and-evaluation",
            "Outputs support the Evaluation Report",
            outputs_ready,
            f"{len(outputs)} cycle outputs map to the common ArchitectureOutput and all nine evaluation dimensions are present."
            if outputs_ready else "A cycle ArchitectureOutput or one of the nine evaluation dimensions is missing.",
        ),
        check(
            "runtime-health",
            "The execution completed without an unhandled error",
            runtime_healthy,
            f"workflow_failures={evaluation.get('workflow_failures', 0)}; execution_errors={execution_errors}. Capability failures surface through their own receipts.",
        ),
        check(
            "runtime-telemetry",
            "Timing and cost evidence is available",
            telemetry_ready,
            f"{len(receipts)} processing receipts cover {len(outputs)} workflow cycles."
            if telemetry_ready else "Processing receipts do not cover every workflow cycle.",
        ),
        check(
            "structured-output-corrections",
            "Structured-output corrections are disclosed",
            True,
            f"{schema_failures + semantic_failures} schema or semantic corrections were retained before final output admission.",
            required=False,
            warning=(schema_failures + semantic_failures) > 0,
        ),
        check(
            "label-scope",
            "Label scope is explicit",
            True,
            "Current labels test mandate-rule detection and response; they do not label event relevance, future outcomes or financial regret.",
            required=False,
            warning=True,
        ),
        check(
            "evaluation-coverage",
            "Unavailable evaluation evidence is explicit",
            True,
            f"Limited dimensions: {', '.join(limited_dimensions) or 'none'}.",
            required=False,
            warning=bool(limited_dimensions),
        ),
        check(
            "retention",
            "Retention state is explicit",
            True,
            "The result and its reports will be admitted to the Saved results repository."
            if retention_requested else "The Run is valid for immediate review but was not selected for retention.",
            required=False,
            warning=not retention_requested,
        ),
    ]
    failures = [item for item in checks if item["required_for_valid_run"] and item["status"] == "fail"]
    warnings = [item for item in checks if item["status"] == "warning"]
    engine_ready = not failures
    archive_ready = engine_ready and retention_requested
    status = "failed" if failures else "passed_with_limitations" if warnings else "passed"
    label = {
        "failed": "Run failed qualification",
        "passed_with_limitations": "Run valid with limitations",
        "passed": "Run valid",
    }[status]
    narrative = (
        f"The engine {'completed this Run correctly' if engine_ready else 'did not produce a valid Run'}. "
        f"The Case, registered capabilities, labelled reference, outputs, evaluation and telemetry were checked from their canonical object attributes; capability inputs were not recalculated. "
        + (
            "The result can be archived, while the stated label and evaluation limitations must remain attached."
            if archive_ready else
            "The result is valid for immediate review but cannot be archived because retention was not selected."
            if engine_ready else
            "The result cannot be archived until the failed gates are resolved."
        )
    )
    return {
        "schema_version": "portfolio-risk.single-run-assurance/v1",
        "status": status,
        "label": label,
        "engine_ready": engine_ready,
        "archive_ready": archive_ready,
        "checks": checks,
        "narrative": narrative,
        "computation": {
            "strategy": "canonical_attribute_inspection",
            "database_queries": 0,
            "model_calls": 0,
            "capability_reexecutions": 0,
        },
        "technical_handoff": {
            "run_id": result.get("run_id"),
            "failed_check_ids": [item["check_id"] for item in failures],
            "warning_check_ids": [item["check_id"] for item in warnings],
            "diagnostic_issue_codes": [
                item.get("code") for item in result.get("diagnostics", {}).get("shortcomings", [])
            ],
            "files_for_codex": [
                "run-assurance-report.md", "runtime-report.json", "run-diagnostics.json",
                "processing-receipts.json", "evaluation-record.json", "architecture-outputs.json",
            ],
        },
    }


def _single_run_runtime_report(result: dict[str, Any]) -> dict[str, Any]:
    """Condense operational evidence already emitted by the execution wrapper."""

    run_record = result.get("run_record", {})
    outputs = run_record.get("architecture_outputs", [])
    receipts = run_record.get("processing_receipts", [])
    return {
        "schema_version": "portfolio-risk.single-run-runtime-report/v1",
        "run_id": result.get("run_id"),
        "status": result.get("status"),
        "workflow_id": result.get("workflow", {}).get("id"),
        "cycles": len(outputs),
        "processing_receipts": len(receipts),
        "resource_usage": result.get("execution_regime", {}).get("resource_usage", {}),
        "capability_errors": [
            error
            for output in outputs
            for error in (output.get("execution_summary") or {}).get("errors", [])
        ],
        "diagnostic_counts": result.get("diagnostics", {}).get("counts", {}),
        "priority_issue_codes": result.get("diagnostics", {}).get("codex_handoff", {}).get(
            "priority_issue_codes", []
        ),
    }


def _run_reproducibility_manifest(result: dict[str, Any]) -> dict[str, Any]:
    """Capture enough immutable identity to reconstruct or challenge one Run."""

    repository_root = Path(__file__).resolve().parents[3]
    source_paths = (
        Path("apps/portfolio-risk-workbench/labs/historical_replay_runtime.py"),
        Path("apps/portfolio-risk-workbench/labs/agent_treatment_runtime.py"),
        Path("apps/portfolio-risk-workbench/labs/duckdb_server.py"),
        Path("config/agent/thesis-sprint/professor-demo-v0.1.yaml"),
        Path("examples/portfolio-risk-thesis/prompts/day3/prompt-manifest.yaml"),
    )

    def git_output(*arguments: str) -> str | None:
        try:
            completed = subprocess.run(
                ("git", *arguments),
                cwd=repository_root,
                check=False,
                capture_output=True,
                text=True,
                timeout=5,
            )
        except (OSError, subprocess.SubprocessError):
            return None
        return completed.stdout.strip() if completed.returncode == 0 else None

    source_digests = {
        str(path): "sha256:" + hashlib.sha256((repository_root / path).read_bytes()).hexdigest()
        for path in source_paths
        if (repository_root / path).is_file()
    }
    status = git_output("status", "--porcelain")
    hierarchy = result.get("hierarchy", {})
    workflow = result.get("workflow", {})
    execution_regime = result.get("execution_regime", {})
    experiment_id = hierarchy.get("experiment", {}).get("experiment_id")
    local_seed = None
    if experiment_id == "experiment-professor-demo-v0.1":
        try:
            local_seed = int(professor_demo_definition().get("seed"))
        except (HistoricalReplayError, TypeError, ValueError):
            local_seed = None
    manifest = {
        "schema_version": "portfolio-risk.run-reproducibility-manifest/v1",
        "run_id": result.get("run_id"),
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "source": {
            "git_revision": git_output("rev-parse", "HEAD"),
            "git_dirty": None if status is None else bool(status),
            "source_file_digests": source_digests,
        },
        "environment": {
            "python": sys.version.split()[0],
            "platform": platform.platform(),
            "service": "portfolio-risk-workbench",
        },
        "definitions": {
            "study_digest": canonical_digest(hierarchy.get("study", {})),
            "experiment_digest": canonical_digest(hierarchy.get("experiment", {})),
            "case_digest": canonical_digest(hierarchy.get("case", {})),
            "architecture_digest": canonical_digest(
                result.get("run_record", {}).get("architecture_config", {})
            ),
            "capability_environment_digest": canonical_digest(
                result.get("evaluation", {}).get("capability_configurations", [])
            ),
            "evaluation_id": result.get("evaluation", {}).get("id"),
        },
        "data_revision": result.get("data_revision", {}),
        "runtime": {
            "workflow_id": workflow.get("id"),
            "model": workflow.get("model"),
            "prompt_manifest_digest": workflow.get("prompt_manifest_digest"),
            "call_budget": workflow.get("call_budget"),
            "maximum_output_tokens_per_call": execution_regime.get(
                "maximum_output_tokens_per_call"
            ),
            "model_timeout_seconds": execution_regime.get("model_timeout_seconds"),
            "local_random_seed": local_seed,
            "model_seed": None,
            "model_seed_limitation": (
                None
                if workflow.get("id") == "B0"
                else "The reviewed Responses route does not expose a deterministic model seed; repeated Runs measure output variation."
            ),
        },
        "outputs": {
            "architecture_output_digest": canonical_digest(
                result.get("run_record", {}).get("architecture_output", {})
            ),
            "evaluation_record_digest": canonical_digest(
                result.get("run_record", {}).get("evaluation_record", {})
            ),
        },
    }
    manifest["manifest_digest"] = canonical_digest(manifest)
    return manifest


def _save_historical_replay(result: dict[str, Any]) -> dict[str, Any]:
    result_bytes = (json.dumps(result, indent=2, sort_keys=True) + "\n").encode("utf-8")
    files = {"result.json": result_bytes}
    file_roles = {"result.json": "run_result"}
    run_record = result.get("run_record")
    hierarchy = result.get("hierarchy")
    if run_record and hierarchy:
        structured_files = {
            "case.json": hierarchy["case"],
            "run-input.json": run_record["run_input"],
            "architecture-output.json": run_record["architecture_output"],
            "architecture-outputs.json": run_record.get("architecture_outputs", []),
            "finding-episodes.json": run_record.get("finding_episodes", []),
            "decision-branches.json": run_record.get("decision_branches", []),
            "metric-specifications.json": run_record.get("metric_specifications", []),
            "run-trace.json": run_record["run_trace"],
            "processing-receipts.json": run_record.get("processing_receipts", []),
            "evaluation-record.json": run_record["evaluation_record"],
            "run-diagnostics.json": result.get("diagnostics", {}),
            "run-assurance.json": result.get("assurance", {}),
            "runtime-report.json": result.get("runtime_report", {}),
            "run-manifest.json": _run_reproducibility_manifest(result),
        }
        for path, payload in structured_files.items():
            files[path] = (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8")
        file_roles.update({
            "case.json": "experimental_case",
            "run-input.json": "run_input",
            "architecture-output.json": "architecture_output",
            "architecture-outputs.json": "cycle_architecture_outputs",
            "finding-episodes.json": "finding_episodes",
            "decision-branches.json": "decision_branches",
            "metric-specifications.json": "metric_specifications",
            "run-trace.json": "run_trace",
            "processing-receipts.json": "processing_receipts",
            "evaluation-record.json": "evaluation_record",
            "run-diagnostics.json": "run_diagnostics_and_codex_handoff",
            "run-assurance.json": "run_qualification",
            "runtime-report.json": "runtime_report",
            "run-manifest.json": "run_reproducibility_manifest",
        })
        assurance = result.get("assurance", {})
        files["run-assurance-report.md"] = ("\n".join((
            "# Single Run assurance report",
            "",
            f"**Outcome:** {assurance.get('label', 'Not assessed')}",
            f"**Engine ready:** {'Yes' if assurance.get('engine_ready') else 'No'}",
            f"**Archive ready:** {'Yes' if assurance.get('archive_ready') else 'No'}",
            "",
            assurance.get("narrative", "No assurance narrative was produced."),
            "",
            "## Checks",
            "",
            *(f"- **{item.get('label')} — {item.get('status', 'unknown').upper()}**: {item.get('summary')}" for item in assurance.get("checks", [])),
            "",
        )) + "\n").encode("utf-8")
        file_roles["run-assurance-report.md"] = "human_readable_run_assurance"
    file_records = tuple(sorted((
        file_manifest(
            path=path,
            content=content,
            media_type="text/markdown" if path.endswith(".md") else "application/json",
            role=file_roles[path],
            preview_mode=PreviewMode.ESCAPED_TEXT,
            download_allowed=True,
        )
        for path, content in files.items()
    ), key=lambda item: item.path))
    artifact_id = f"historical-replay:{result['run_id'].lower()}"
    manifest = ArtifactManifest(
        artifact_id=artifact_id,
        title=f"Historical replay — {result['portfolio']['id']}",
        kind=ArtifactKind.RETAINED_RUN,
        created_at=datetime.now(timezone.utc),
        created_by="local.researcher",
        creation_method="deterministic_historical_replay",
        run_id=result["run_id"],
        experiment_id=result.get("hierarchy", {}).get("experiment", {}).get(
            "experiment_id", f"historical-replay-{result['portfolio']['id'].replace('_', '-')}"
        ),
        data_truth=DataTruthClass.LICENSED_REAL,
        rights=RightsState.LICENSED_RESTRICTED,
        rights_policy_id="rights:licensed-research-only",
        publication=PublicationState.RESTRICTED,
        retention=RetentionClass.EXPERIMENT_EVIDENCE,
        entry_file="architecture-output.json" if run_record and hierarchy else "result.json",
        files=file_records,
        total_size_bytes=sum(item.size_bytes for item in file_records),
        restrictions=("licensed-data-no-redistribution",),
    )
    record = artifact_store().admit(
        manifest,
        files,
        actor="local.researcher",
        rationale="Saved an explicitly requested licensed-data historical replay for later review.",
    )
    return {
        "artifact_id": record.manifest.artifact_id,
        "saved_at": record.receipts[0].occurred_at.isoformat(),
        "state": record.state.value,
    }


def _saved_historical_replays() -> list[dict[str, Any]]:
    saved = []
    for record in artifact_store().list():
        if record.manifest.creation_method != "deterministic_historical_replay":
            continue
        if record.state.value in {"tombstoned", "deleted"}:
            continue
        result_bytes, _ = artifact_store().open_file(record.manifest.artifact_id, "result.json")
        result = json.loads(result_bytes)
        saved.append({
            "artifact_id": record.manifest.artifact_id,
            "run_id": result["run_id"],
            "portfolio_id": result["portfolio"]["id"],
            "mandate": result["mandate"]["name"],
            "period": result["period"],
            "created_at": record.manifest.created_at.isoformat(),
        })
    return sorted(saved, key=lambda item: item["created_at"], reverse=True)


@app.get("/api/experiments/replay-runs")
def list_historical_replays() -> dict[str, Any]:
    try:
        return {"runs": _saved_historical_replays()}
    except (ArtifactConflict, ArtifactNotFound, ValueError) as error:
        raise _artifact_error(error) from error


@app.get("/api/experiments/architecture-output/mapping-contract")
@app.get("/api/experiments/architecture-output/projection-contract", deprecated=True)
def architecture_output_projection_contract() -> dict[str, Any]:
    """Describe the common structured-output mapping boundary."""

    return {
        "flow": ["headless_agent_or_graph_wrapper", "evaluation_byproducts_and_observed_behavior", "deterministic_mapping", "architecture_output", "evaluation"],
        "agent_writes_architecture_output": False,
        "primary_artifact_is_rewritten": False,
        "checks": [
            "run_cycle_architecture_identity",
            "point_in_time_evidence_eligibility",
            "available_capabilities_and_agents",
            "effect_free_capability_receipts",
            "structured_byproduct_quality",
            "presentation_artifacts_excluded",
            "final_decision_and_specialist_node_scope",
            "execution_and_graph_behavior_observed",
        ],
        "output_schema": AgentStructuredOutput.model_json_schema(),
        "single_agent_wrapper_schema": AgentExecutionEnvelope.model_json_schema(),
        "graph_wrapper_schema": GraphExecutionEnvelope.model_json_schema(),
        "context_schema": ArchitectureMappingContext.model_json_schema(),
    }


@app.post("/api/experiments/architecture-output/map")
def map_architecture_output(request: ArchitectureOutputMappingRequest) -> dict[str, Any]:
    """Map one agent output into the common experiment output without rewriting it."""

    try:
        result = (
            finalize_single_agent_execution(
                request.single_agent_execution,
                request.context,
                mapped_at=request.mapped_at,
            )
            if request.single_agent_execution is not None
            else finalize_agent_graph_execution(
                request.graph_execution,
                request.context,
                mapped_at=request.mapped_at,
            )
        )
    except ArchitectureMappingError as error:
        raise HTTPException(
            status_code=422,
            detail={"message": "output cannot be mapped to this experiment cycle", "violations": error.violations},
        ) from error
    return result.model_dump(mode="json")


@app.get("/api/experiments/replay-runs/{artifact_id:path}")
def load_historical_replay(artifact_id: str) -> dict[str, Any]:
    try:
        record = artifact_store().get(artifact_id)
        if record.manifest.creation_method != "deterministic_historical_replay":
            raise ArtifactNotFound(artifact_id)
        content, _ = artifact_store().open_file(artifact_id, "result.json")
        result = json.loads(content)
        result["saved"] = {
            "artifact_id": artifact_id,
            "saved_at": record.manifest.created_at.isoformat(),
            "state": record.state.value,
        }
        return result
    except (ArtifactConflict, ArtifactNotFound, ValueError) as error:
        raise _artifact_error(error) from error


@app.post("/api/experiments/replay-runs")
def create_historical_replay(request: HistoricalReplayRequest) -> dict[str, Any]:
    """Run the bounded, deterministic historical baseline on licensed data."""

    try:
        if request.workflow_id in {"B1", "A1"} and not request.authorize_external_model_calls:
            raise HistoricalReplayError(
                "B1 and A1 require explicit authorization to send bounded, derived licensed-data context to OpenAI for this run"
            )
        result = run_historical_replay(
            find_private_root(PROTOTYPE_ROOT),
            workflow_id=request.workflow_id,
            portfolio_id=request.portfolio_id,
            start_date=request.start_date,
            end_date=request.end_date,
            evaluation_id=request.evaluation_id,
        )
        result["assurance"] = _single_run_assurance(
            result, retention_requested=request.save_result
        )
        result["runtime_report"] = _single_run_runtime_report(result)
        result["saved"] = _save_historical_replay(result) if request.save_result else None
        return result
    except HistoricalReplayError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except (RuntimeError, duckdb.Error) as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


def _counterfactual_batch_definition(request: CounterfactualBatchRequest) -> dict[str, Any]:
    cells = []
    for portfolio_id in request.portfolio_ids:
        case_id = f"case-{portfolio_id.replace('_', '-')}-{request.start_date.isoformat()}-{request.end_date.isoformat()}"
        for repetition in range(1, request.repetitions + 1):
            for workflow_id in request.workflow_ids:
                cells.append(
                    {
                        "cell_id": f"{case_id}:r{repetition}:{workflow_id}",
                        "case_id": case_id,
                        "portfolio_id": portfolio_id,
                        "workflow_id": workflow_id,
                        "repetition": repetition,
                        "is_baseline": workflow_id == request.baseline_workflow_id,
                        "changed_dimension": "architecture",
                    }
                )
    return {
        "schema_version": "portfolio-risk.counterfactual-batch-definition/v1",
        "study": {
            "study_id": request.study_id,
            "title": request.study_title,
        },
        "experiment": {
            "experiment_id": request.experiment_id,
            "research_question": request.research_question,
            "hypothesis": request.hypothesis,
            "baseline_workflow_id": request.baseline_workflow_id,
            "planned_variable_dimensions": ["architecture", "repetition"],
            "controlled_factors": [
                "data_revision",
                "evaluation_protocol",
                "information_regime",
                "mandate_version",
                "point_in_time_boundary",
                "portfolio_quantities",
            ],
        },
        "cases": sorted({item["case_id"] for item in cells}),
        "regime_role": "cross_cutting_case_classification",
        "execution": {
            "mode": "concurrent_independent_runs",
            "max_concurrency": request.max_concurrency,
            "terminal_analysis_required": True,
            "external_effects": "disabled",
        },
        "period": {"start": request.start_date.isoformat(), "end": request.end_date.isoformat()},
        "evaluation_id": request.evaluation_id,
        "cells": cells,
    }


def _experiment_assurance(
    analysis: dict[str, Any],
    completed_cells: list[dict[str, Any]],
    *,
    use_narrative_agent: bool,
) -> dict[str, Any]:
    """Run post-execution gates and prepare one readable + technical report."""

    expected_dimensions = {
        "detection_quality", "severity_understanding", "timeliness",
        "evidence_quality", "confidence_calibration", "decision_quality",
        "robustness", "stability", "efficiency",
    }
    completed = analysis.get("matrix_coverage", {}).get("completed", 0)
    planned = analysis.get("matrix_coverage", {}).get("planned", 0)
    failed = analysis.get("matrix_coverage", {}).get("failed", 0)
    results = [item["result"] for item in completed_cells]
    dimension_sets = [
        {item.get("id") for item in result.get("evaluation", {}).get("dimensions", [])}
        for result in results
    ]
    mapped_outputs = [
        result.get("run_record", {}).get("architecture_output")
        for result in results
    ]
    integrity_failures = []
    for item in completed_cells:
        try:
            verification = artifact_store().verify(item["artifact_id"])
        except (ArtifactConflict, ArtifactNotFound, ValueError):
            integrity_failures.append(item["artifact_id"])
        else:
            if not verification.valid:
                integrity_failures.append(item["artifact_id"])
    execution_errors = sum(
        int(dimension.get("metrics", {}).get("execution_errors") or 0)
        for result in results
        for dimension in result.get("evaluation", {}).get("dimensions", [])
        if dimension.get("id") == "efficiency"
    )
    validation_corrections = sum(
        int(dimension.get("metrics", {}).get("schema_validation_failures") or 0)
        + int(dimension.get("metrics", {}).get("semantic_verification_failures") or 0)
        for result in results
        for dimension in result.get("evaluation", {}).get("dimensions", [])
        if dimension.get("id") == "efficiency"
    )
    unavailable_dimensions = sorted({
        dimension.get("id")
        for result in results
        for dimension in result.get("evaluation", {}).get("dimensions", [])
        if dimension.get("status") in {"partial", "not_measurable", "not_applicable"}
    })

    def check(check_id: str, label: str, passed: bool, summary: str, *, required: bool = True, warning: bool = False) -> dict[str, Any]:
        return {
            "check_id": check_id,
            "label": label,
            "status": "pass" if passed and not warning else "warning" if passed else "fail",
            "required_for_archive": required,
            "summary": summary,
        }

    checks = [
        check("matrix-complete", "All planned runs completed", completed == planned and failed == 0, f"{completed}/{planned} runs completed; {failed} failed."),
        check("architecture-output", "Every run produced a mapped ArchitectureOutput", bool(results) and all(mapped_outputs), f"{sum(bool(item) for item in mapped_outputs)}/{len(results)} final outputs are present."),
        check("evaluation-contract", "Every run contains all nine evaluation dimensions", bool(dimension_sets) and all(items == expected_dimensions for items in dimension_sets), "The evaluator returned the complete nine-dimension contract for every completed run."),
        check("execution-errors", "No unhandled execution error", execution_errors == 0, f"{execution_errors} unhandled execution errors were retained."),
        check("matched-controls", "Architecture contrasts preserve the frozen controls", not analysis.get("confounds"), f"{len(analysis.get('confounds', []))} confounded contrasts were found."),
        check("repository-integrity", "Retained run files pass integrity verification", not integrity_failures, "All retained run files match their manifests." if not integrity_failures else f"Integrity failed for: {', '.join(integrity_failures)}"),
        check("validation-corrections", "Structured-output validation", True, f"{validation_corrections} schema or semantic corrections were recorded; final admitted outputs remained valid.", required=False, warning=validation_corrections > 0),
        check("evaluation-coverage", "All dimensions are fully measurable", True, f"Limited or unavailable dimensions: {', '.join(unavailable_dimensions) or 'none'}.", required=False, warning=bool(unavailable_dimensions)),
    ]
    required_failures = [item for item in checks if item["required_for_archive"] and item["status"] == "fail"]
    warnings = [item for item in checks if item["status"] == "warning"]
    archive_ready = not required_failures
    status = "failed" if required_failures else "passed_with_limitations" if warnings else "passed"
    label = {"failed": "Failed", "passed_with_limitations": "Passed with limitations", "passed": "Passed"}[status]
    deterministic_narrative = (
        f"The experiment {label.lower()}. {completed} of {planned} planned runs completed and "
        f"{sum(bool(item) for item in mapped_outputs)} produced a valid final ArchitectureOutput. "
        + (
            "The retained evidence is internally consistent and the result is ready to archive. "
            if archive_ready else
            "The result is not ready to archive until the failed post-run checks are resolved. "
        )
        + (
            f"Interpretation remains limited for {', '.join(unavailable_dimensions)}. "
            if unavailable_dimensions else "All declared evaluation dimensions were measurable. "
        )
        + (f"The agent critic corrected {validation_corrections} structured-output issue(s) before admission." if validation_corrections else "No output correction was required.")
    )
    narrative = deterministic_narrative
    narrative_agent = {"used": False, "model": None, "status": "deterministic_fallback", "input_tokens": 0, "output_tokens": 0}
    if use_narrative_agent and _keychain_key():
        try:
            from openai import OpenAI

            compact = {
                "status": status,
                "archive_ready": archive_ready,
                "checks": checks,
                "diagnostic_counts": analysis.get("diagnostics", {}).get("counts", {}),
                "priority_issue_codes": analysis.get("diagnostics", {}).get("codex_handoff", {}).get("priority_issue_codes", []),
            }
            response = OpenAI(api_key=str(_keychain_key(include_value=True))).responses.create(
                model=COST_OPTIMIZED_LLM_MODEL,
                reasoning={"effort": "low"},
                store=False,
                tools=[],
                max_output_tokens=500,
                input=[
                    {"role": "system", "content": [{"type": "input_text", "text": "Write a concise experiment assurance narrative for a researcher. State whether execution succeeded, whether it is archive-ready, the most important limitations, and the next correction. Do not invent facts, repeat every test, or discuss implementation jargon unless needed. Use two short paragraphs."}]},
                    {"role": "user", "content": [{"type": "input_text", "text": json.dumps(compact, sort_keys=True)}]},
                ],
            )
            if response.output_text.strip():
                narrative = response.output_text.strip()
            usage = getattr(response, "usage", None)
            narrative_agent = {
                "used": True,
                "model": getattr(response, "model", COST_OPTIMIZED_LLM_MODEL),
                "status": "completed",
                "input_tokens": int(getattr(usage, "input_tokens", 0) or 0),
                "output_tokens": int(getattr(usage, "output_tokens", 0) or 0),
            }
        except Exception as error:
            narrative_agent["error"] = f"{type(error).__name__}: {str(error)[:240]}"
    return {
        "schema_version": "portfolio-risk.experiment-assurance/v1",
        "status": status,
        "label": label,
        "archive_ready": archive_ready,
        "checks": checks,
        "narrative": narrative,
        "narrative_agent": narrative_agent,
        "technical_handoff": {
            "run_ids": sorted(result.get("run_id") for result in results),
            "failed_check_ids": [item["check_id"] for item in required_failures],
            "warning_check_ids": [item["check_id"] for item in warnings],
            "priority_issue_codes": analysis.get("diagnostics", {}).get("codex_handoff", {}).get("priority_issue_codes", []),
            "files_for_codex": ["experiment-assurance-report.md", "shortcomings.json", "counterfactual-analysis.json"],
        },
    }


def _save_counterfactual_analysis(
    definition: dict[str, Any], analysis: dict[str, Any]
) -> dict[str, Any]:
    assurance = analysis.get("assurance", {})
    assurance_markdown = "\n".join((
        "# Experiment assurance report",
        "",
        f"**Outcome:** {assurance.get('label', 'Not assessed')}",
        f"**Archive ready:** {'Yes' if assurance.get('archive_ready') else 'No'}",
        "",
        assurance.get("narrative", "No assurance narrative was produced."),
        "",
        "## Post-run checks",
        "",
        *(
            f"- **{item.get('label')} — {item.get('status', 'unknown').upper()}**: {item.get('summary')}"
            for item in assurance.get("checks", [])
        ),
        "",
        "## Codex handoff",
        "",
        "```json",
        json.dumps(assurance.get("technical_handoff", {}), indent=2, sort_keys=True),
        "```",
        "",
    ))
    raw_files = {
        "batch-definition.json": (
            json.dumps(definition, indent=2, sort_keys=True) + "\n"
        ).encode("utf-8"),
        "counterfactual-analysis.json": (
            json.dumps(analysis, indent=2, sort_keys=True) + "\n"
        ).encode("utf-8"),
        "shortcomings.json": (
            json.dumps(analysis.get("diagnostics", {}), indent=2, sort_keys=True) + "\n"
        ).encode("utf-8"),
        "experiment-assurance-report.md": assurance_markdown.encode("utf-8"),
    }
    roles = {
        "batch-definition.json": "counterfactual_batch_definition",
        "counterfactual-analysis.json": "counterfactual_terminal_analysis",
        "shortcomings.json": "batch_diagnostics_and_codex_handoff",
        "experiment-assurance-report.md": "human_readable_experiment_assurance_report",
    }
    files = tuple(
        file_manifest(
            path=path,
            content=raw_files[path],
            media_type="application/json",
            role=roles[path],
            preview_mode=PreviewMode.ESCAPED_TEXT,
            download_allowed=True,
        )
        for path in sorted(raw_files)
    )
    suffix = analysis["analysis_digest"].removeprefix("sha256:")[:20]
    artifact_id = f"counterfactual-analysis:{definition['experiment']['experiment_id']}:{suffix}"
    parent_ids = tuple(
        sorted(
            {
                item["artifact_id"]
                for item in analysis["cells"]
                if item.get("artifact_id")
            }
        )
    )
    manifest = ArtifactManifest(
        artifact_id=artifact_id,
        title=f"Counterfactual analysis — {definition['study']['title']}"[:200],
        kind=ArtifactKind.EVIDENCE_BUNDLE,
        created_at=datetime.now(timezone.utc),
        created_by="local.researcher",
        creation_method="experiment-lab.counterfactual-terminal-analysis",
        experiment_id=definition["experiment"]["experiment_id"],
        data_truth=DataTruthClass.LICENSED_REAL,
        rights=RightsState.LICENSED_RESTRICTED,
        rights_policy_id="rights.licensed.research.only",
        publication=PublicationState.RESTRICTED,
        retention=RetentionClass.EXPERIMENT_EVIDENCE,
        entry_file="counterfactual-analysis.json",
        files=files,
        total_size_bytes=sum(len(item) for item in raw_files.values()),
        parent_artifact_ids=parent_ids,
        restrictions=(
            "licensed-data-no-redistribution",
            "review-required-before-thesis-use",
        ),
    )
    record = artifact_store().admit(
        manifest,
        raw_files,
        actor="local.researcher",
        rationale=(
            "Retain the terminal analysis separately from every immutable Run output."
        ),
    )
    verification = artifact_store().verify(record.manifest.artifact_id)
    if not verification.valid:
        raise ArtifactConflict("counterfactual analysis failed repository integrity verification")
    return {
        "artifact_id": record.manifest.artifact_id,
        "artifact_digest": record.manifest.artifact_digest,
        "created_at": record.manifest.created_at.isoformat(),
        "state": record.state.value,
    }


def _counterfactual_analysis_artifacts() -> list[dict[str, Any]]:
    values = []
    for record in artifact_store().list():
        if record.manifest.creation_method != "experiment-lab.counterfactual-terminal-analysis":
            continue
        if record.state.value in {"tombstoned", "deleted"}:
            continue
        content, _ = artifact_store().open_file(
            record.manifest.artifact_id, "counterfactual-analysis.json"
        )
        analysis = json.loads(content)
        values.append(
            {
                "artifact_id": record.manifest.artifact_id,
                "artifact_digest": record.manifest.artifact_digest,
                "study_id": analysis["study_id"],
                "experiment_id": analysis["experiment_id"],
                "status": analysis["status"],
                "matrix_coverage": analysis["matrix_coverage"],
                "generated_at": analysis["generated_at"],
                "analysis_digest": analysis["analysis_digest"],
            }
        )
    return sorted(values, key=lambda item: item["generated_at"], reverse=True)


@app.get("/api/experiments/counterfactual-dimensions")
def counterfactual_dimensions() -> dict[str, Any]:
    design_map = counterfactual_design_map()
    return {
        "hierarchy": ["study", "experiment", "case", "run"],
        "regime_role": "cross_cutting_case_classification",
        "dimensions": counterfactual_dimension_catalogue(),
        **design_map,
        "first_executable_slice": "architecture_with_optional_repetition",
        "terminal_analysis_required": True,
    }


@app.get("/api/experiments/counterfactual-batches")
def list_counterfactual_batches() -> dict[str, Any]:
    try:
        return {"analyses": _counterfactual_analysis_artifacts()}
    except (ArtifactConflict, ArtifactNotFound, ValueError) as error:
        raise _artifact_error(error) from error


@app.get("/api/experiments/counterfactual-batches/{artifact_id:path}")
def load_counterfactual_batch(artifact_id: str) -> dict[str, Any]:
    try:
        record = artifact_store().get(artifact_id)
        if record.manifest.creation_method != "experiment-lab.counterfactual-terminal-analysis":
            raise ArtifactNotFound(artifact_id)
        definition, _ = artifact_store().open_file(artifact_id, "batch-definition.json")
        analysis, _ = artifact_store().open_file(artifact_id, "counterfactual-analysis.json")
        return {
            "definition": json.loads(definition),
            "analysis": json.loads(analysis),
            "analysis_artifact": {
                "artifact_id": artifact_id,
                "artifact_digest": record.manifest.artifact_digest,
                "created_at": record.manifest.created_at.isoformat(),
                "state": record.state.value,
            },
        }
    except (ArtifactConflict, ArtifactNotFound, ValueError) as error:
        raise _artifact_error(error) from error


@app.post("/api/experiments/counterfactual-batches")
def create_counterfactual_batch(request: CounterfactualBatchRequest) -> dict[str, Any]:
    """Execute one bounded architecture matrix and retain its terminal analysis."""

    if any(item in {"B1", "A1"} for item in request.workflow_ids) and not request.authorize_external_model_calls:
        raise HTTPException(
            status_code=422,
            detail=(
                "B1 and A1 require explicit authorization to send bounded, derived licensed-data context to OpenAI for this batch"
            ),
        )
    definition = _counterfactual_batch_definition(request)
    private_root = find_private_root(PROTOTYPE_ROOT)

    def execute(cell: dict[str, Any]) -> dict[str, Any]:
        return run_historical_replay(
            private_root,
            workflow_id=cell["workflow_id"],
            portfolio_id=cell["portfolio_id"],
            start_date=request.start_date,
            end_date=request.end_date,
            evaluation_id=request.evaluation_id,
            study_id=request.study_id,
            experiment_id=request.experiment_id,
            study_title=request.study_title,
            research_question=request.research_question,
            hypothesis=request.hypothesis,
            repetition=cell["repetition"],
        )

    completed_cells = []
    failed_cells = []
    with ThreadPoolExecutor(max_workers=min(request.max_concurrency, len(definition["cells"]))) as executor:
        futures = {executor.submit(execute, cell): cell for cell in definition["cells"]}
        for future in as_completed(futures):
            cell = futures[future]
            try:
                result = future.result()
                result["assurance"] = _single_run_assurance(
                    result, retention_requested=True
                )
                result["runtime_report"] = _single_run_runtime_report(result)
                saved = _save_historical_replay(result)
                result["saved"] = saved
                completed_cells.append({**cell, "result": result, "artifact_id": saved["artifact_id"]})
            except Exception as error:  # one failed cell must not erase completed counterfactual evidence
                failed_cells.append(
                    {
                        **cell,
                        "error": str(error)[:800],
                    }
                )

    analysis = analyse_counterfactual_batch(
        study_id=request.study_id,
        experiment_id=request.experiment_id,
        research_question=request.research_question,
        hypothesis=request.hypothesis,
        baseline_workflow_id=request.baseline_workflow_id,
        planned_cells=definition["cells"],
        completed_cells=completed_cells,
        failed_cells=failed_cells,
    )
    analysis["assurance"] = _experiment_assurance(
        analysis,
        completed_cells,
        use_narrative_agent=request.authorize_external_model_calls,
    )
    analysis.pop("analysis_digest", None)
    analysis["analysis_digest"] = canonical_digest(analysis)
    analysis_artifact = _save_counterfactual_analysis(definition, analysis)
    return {
        "definition": definition,
        "analysis": analysis,
        "analysis_artifact": analysis_artifact,
        "run_artifacts": [
            {
                "cell_id": item["cell_id"],
                "case_id": item["case_id"],
                "workflow_id": item["workflow_id"],
                "repetition": item["repetition"],
                "run_id": item["result"]["run_id"],
                "artifact_id": item["artifact_id"],
                "regimes": item["result"].get("hierarchy", {}).get("regimes", []),
            }
            for item in sorted(completed_cells, key=lambda value: value["cell_id"])
        ],
    }


@app.get("/api/experiments/options")
def experiment_options() -> dict[str, Any]:
    return _experiment_options_payload()


@app.get("/api/experiments/fixture-context")
def experiment_fixture_context() -> dict[str, Any]:
    try:
        return calibration_fixture_payload(registry_store())
    except (RegistryConflict, RegistryNotFound, ValueError) as error:
        raise _experiment_error(error) from error


@app.post("/api/experiments/fixture-context/resolve")
def resolve_experiment_fixture_context() -> dict[str, Any]:
    try:
        return resolve_calibration_fixture(registry_store())
    except (RegistryConflict, RegistryNotFound, ValueError) as error:
        raise _experiment_error(error) from error


@app.get("/api/experiments/run-traces")
def experiment_run_traces() -> dict[str, Any]:
    try:
        return run_trace_payload()
    except (ArtifactConflict, ArtifactNotFound, ValueError) as error:
        raise _artifact_error(error) from error


@app.post("/api/experiments/run-traces")
def create_experiment_run_trace(request: RunTraceCreateRequest) -> dict[str, Any]:
    try:
        return create_calibration_run_trace(actor=request.actor)
    except (ArtifactConflict, ArtifactNotFound, KeyError, ValueError) as error:
        raise _artifact_error(error) from error


@app.get("/api/experiments/program")
def experiment_program() -> dict[str, Any]:
    try:
        return experimental_program_payload()
    except (KeyError, ValueError) as error:
        raise _experiment_error(error) from error


@app.get("/api/experiments/run-audit")
def experiment_run_audit_catalogue() -> dict[str, Any]:
    try:
        return run_audit_catalogue_payload()
    except (ArtifactConflict, ArtifactNotFound, ValueError) as error:
        raise _artifact_error(error) from error


@app.post("/api/experiments/run-audit/compare")
def compare_experiment_runs(request: RunComparisonRequest) -> dict[str, Any]:
    try:
        return run_comparison_payload(request)
    except (ArtifactConflict, ArtifactNotFound, ValueError) as error:
        raise _artifact_error(error) from error


@app.post("/api/experiments/run-audit/acceptance")
def accept_experiment_run_comparison(request: RunAcceptanceRequest) -> dict[str, Any]:
    try:
        return record_run_acceptance(request)
    except (ArtifactConflict, ArtifactNotFound, ValueError) as error:
        raise _artifact_error(error) from error


def _experiment_registry_documents() -> list[Any]:
    """Return only saved registry definitions that may enter new experiments."""

    return [
        document
        for document in registry_store().list()
        if document.projection.identity.kind in {AssetKind.WORKFLOW, AssetKind.EVALUATION}
        and document.state in EXPERIMENT_ELIGIBLE_REGISTRY_STATES
    ]


def _require_experiment_registry_assets(identities: tuple[RegistryIdentity, ...]) -> None:
    eligible = {
        document.projection.identity.reference: document
        for document in registry_store().list()
        if document.state in EXPERIMENT_ELIGIBLE_REGISTRY_STATES
    }
    missing = [identity.reference for identity in identities if identity.reference not in eligible]
    if missing:
        raise ExperimentConflict(
            "experiment assets must be saved in the Registry and remain candidate, validated, "
            "or published: " + ", ".join(missing)
        )


def _experiment_definition_registry_assets(
    definition: ExperimentDefinition,
) -> tuple[RegistryIdentity, ...]:
    return definition.system_assets + (
        (definition.scientific_design,) if definition.scientific_design is not None else ()
    ) + (
        (definition.object_set,) if definition.object_set is not None else ()
    )


def _licensed_portfolio_projection() -> dict[str, Any]:
    """Describe licensed portfolios without making metadata depend on private data.

    Public CI and development installations may not mount the licensed
    CRSP/Compustat root. Metadata views must remain usable in that state, while
    the data and query endpoints continue to fail explicitly when invoked.
    """

    try:
        selection = data_plane.selection
        portfolios = data_plane.public_portfolios()
    except RuntimeError:
        return {
            "available": False,
            "status": "unavailable",
            "unavailable_reason": "licensed data root is not configured",
            "selection_id": None,
            "source_snapshot_id": None,
            "selection_digest": None,
            "portfolios": [],
        }
    return {
        "available": True,
        "status": "available",
        "unavailable_reason": None,
        "selection_id": selection["selection_id"],
        "source_snapshot_id": selection["source_snapshot_id"],
        "selection_digest": selection["candidate_artifact"]["sha256"],
        "portfolios": portfolios,
    }


def _experiment_options_payload() -> dict[str, Any]:
    assets = [
        {
            "identity": document.projection.identity.model_dump(mode="json"),
            "reference": document.projection.identity.reference,
            "display_name": document.projection.display_name,
            "summary": document.projection.summary,
            "lifecycle_state": document.state.value,
            "registry_revision": document.receipts[-1].receipt_digest,
            "saved": True,
        }
        for document in _experiment_registry_documents()
    ]
    licensed = _licensed_portfolio_projection()
    selection_id = licensed["selection_id"]
    snapshot_id = licensed["source_snapshot_id"]
    selection_digest = licensed["selection_digest"]
    real_portfolios = [
        {
            "portfolio_id": item["portfolio_id"],
            "title": item["title"],
            "position_count": len(item.get("positions", ())),
            "base_currency": item.get("base_currency"),
            "reference": f"portfolio-selection:{selection_id}:{item['portfolio_id']}@{selection_digest}",
            "data_truth": "licensed_real",
            "data_revision_reference": f"dataset-snapshot:{snapshot_id}",
        }
        for item in licensed["portfolios"]
    ]
    simulated_portfolios = [
        {
            **item,
            "data_truth": "simulated_intraday",
            "data_revision_reference": f"simulation:seeded-intraday@v1+anchor:{snapshot_id}",
        }
        for item in real_portfolios
    ]
    synthetic_portfolios = []
    fixture_root = PROTOTYPE_ROOT.parents[2] / "examples" / "portfolio-risk-thesis" / "portfolios"
    for path in sorted(fixture_root.glob("*.yaml")):
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
        digest = "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()
        synthetic_portfolios.append(
            {
                "portfolio_id": document["portfolio_id"],
                "title": document["title"],
                "reference": f"portfolio-fixture:{document['portfolio_id']}@{digest}",
                "data_truth": "reviewed_synthetic",
                "data_revision_reference": "fixture:portfolio-risk-thesis@2026-07-28.2",
            }
        )
    return {
        "system_assets": assets,
        "eligibility_policy": {
            "registry_required": True,
            "accepted_lifecycle_states": sorted(
                state.value for state in EXPERIMENT_ELIGIBLE_REGISTRY_STATES
            ),
            "meaning": "Only explicitly indexed, versioned definitions can enter a new experiment.",
        },
        "defaults": {
            "snapshot_policy_reference": "snapshot-policy:point-in-time-available-at@v1",
            "mandate_reference": "mandate:research-default@v1",
            "data_truth": "licensed_real",
        },
        "portfolios": [*real_portfolios, *synthetic_portfolios, *simulated_portfolios],
        "licensed_data": {
            "available": licensed["available"],
            "status": licensed["status"],
            "unavailable_reason": licensed["unavailable_reason"],
            "source_snapshot_id": snapshot_id,
            "selection_id": selection_id,
            "access": "read_only",
            "synthetic_fallback": False,
        },
    }


@app.post("/api/experiments/draft")
def draft_experiment(request: ExperimentDraftRequest) -> dict[str, Any]:
    try:
        expected_kind = (
            AssetKind.EVALUATION
            if request.presentation_mode == PresentationMode.EVALUATION_ONLY
            else AssetKind.WORKFLOW
        )
        if request.system_asset.kind != expected_kind:
            raise ExperimentConflict(
                f"{request.presentation_mode.value} requires a {expected_kind.value} definition"
            )
        _require_experiment_registry_assets((request.system_asset,))
        options = _experiment_options_payload()
        portfolio_option = next(
            (
                item
                for item in options["portfolios"]
                if item["reference"] == request.portfolio_reference
                and item["data_truth"] == request.data_truth.value
            ),
            None,
        )
        if portfolio_option is None:
            raise ExperimentConflict(
                "portfolio reference is not reviewed for the selected data-truth class"
            )
        if portfolio_option["data_revision_reference"] != request.data_revision_reference:
            raise ExperimentConflict(
                "data revision does not match the reviewed portfolio/data-truth option"
            )
        raw_bindings = {
            "portfolio": request.portfolio_reference,
            "snapshot_policy": request.snapshot_policy_reference,
            "mandate": request.mandate_reference,
            "data_revision": request.data_revision_reference,
        }
        bindings = tuple(
            SourceBinding(
                role=role,
                reference=reference,
                revision="declared-v1",
                digest=canonical_digest(
                    {"kind": "experiment-source-binding/v1", "role": role, "reference": reference}
                ),
            )
            for role, reference in sorted(raw_bindings.items())
        )
        definition = ExperimentDefinition(
            experiment_id=request.experiment_id,
            version="0.1.0",
            name=request.name,
            purpose=request.purpose,
            hypothesis=request.hypothesis,
            owner=request.actor,
            created_at=datetime.now(timezone.utc),
            temporal=TemporalWindow(start_date=request.start_date, end_date=request.end_date),
            presentation_mode=request.presentation_mode,
            data_truth=request.data_truth,
            source_bindings=bindings,
            system_assets=(request.system_asset,),
            budget=ExperimentBudget(
                max_model_calls=request.max_model_calls,
                max_cost_usd=request.max_cost_usd,
            ),
        )
        record = experiment_store().create(
            definition,
            actor=request.actor,
            idempotency_key=f"create-{request.experiment_id}",
        )
        return experiment_record_payload(record)
    except (ExperimentConflict, ExperimentNotFound, ValueError) as error:
        raise _experiment_error(error) from error


@app.post("/api/experiments")
def create_experiment(request: ExperimentCreateRequest) -> dict[str, Any]:
    try:
        _require_experiment_registry_assets(
            _experiment_definition_registry_assets(request.definition)
        )
        record = experiment_store().create(
            request.definition,
            actor=request.actor,
            idempotency_key=request.idempotency_key,
        )
        return experiment_record_payload(record)
    except (ExperimentConflict, ExperimentNotFound, ValueError) as error:
        raise _experiment_error(error) from error


@app.get("/api/experiments/{experiment_id}")
def experiment_detail(experiment_id: str) -> dict[str, Any]:
    try:
        return experiment_record_payload(experiment_store().get(experiment_id))
    except (ExperimentConflict, ExperimentNotFound, ValueError) as error:
        raise _experiment_error(error) from error


@app.post("/api/experiments/{experiment_id}/transition")
def transition_experiment(
    experiment_id: str, request: ExperimentTransitionRequest
) -> dict[str, Any]:
    try:
        if request.to_state == ExperimentState.VALIDATED:
            current = experiment_store().get(experiment_id)
            _require_experiment_registry_assets(
                _experiment_definition_registry_assets(current.definition)
            )
        record = experiment_store().transition(
            experiment_id,
            request.to_state,
            actor=request.actor,
            rationale=request.rationale,
            idempotency_key=request.idempotency_key,
            expected_revision=request.expected_revision,
        )
        return experiment_record_payload(record)
    except (ExperimentConflict, ExperimentNotFound, ValueError) as error:
        raise _experiment_error(error) from error


@app.post("/api/experiments/{experiment_id}/enqueue")
def enqueue_experiment(
    experiment_id: str, request: ExperimentEnqueueRequest
) -> dict[str, Any]:
    try:
        record, queue = experiment_store().enqueue(
            experiment_id,
            actor=request.actor,
            idempotency_key=request.idempotency_key,
            expected_revision=request.expected_revision,
        )
        return {
            "experiment": experiment_record_payload(record),
            "queue": queue.model_dump(mode="json"),
        }
    except (ExperimentConflict, ExperimentNotFound, ValueError) as error:
        raise _experiment_error(error) from error


@app.get("/api/experiment-queue")
def experiment_queue_entries() -> dict[str, Any]:
    try:
        return {"entries": [item.model_dump(mode="json") for item in experiment_store().queue_entries()]}
    except (ExperimentConflict, ExperimentNotFound, ValueError) as error:
        raise _experiment_error(error) from error


@app.post("/api/experiment-queue/{queue_id}/control")
def control_experiment_queue(
    queue_id: str, request: ExperimentQueueControlRequest
) -> dict[str, Any]:
    try:
        record, queue = experiment_store().update_queue(
            queue_id, action=request.action, resume_token=request.resume_token
        )
        return {
            "experiment": experiment_record_payload(record),
            "queue": queue.model_dump(mode="json"),
        }
    except (ExperimentConflict, ExperimentNotFound, ValueError) as error:
        raise _experiment_error(error) from error


@app.get("/api/experiment-sets")
def experiment_sets() -> dict[str, Any]:
    try:
        store = experiment_store()
        return {"sets": [experiment_set_payload(item, store) for item in store.list_sets()]}
    except (ExperimentConflict, ExperimentNotFound, ValueError) as error:
        raise _experiment_error(error) from error


@app.post("/api/experiment-sets")
def create_experiment_set(request: ExperimentSetCreateRequest) -> dict[str, Any]:
    try:
        store = experiment_store()
        definition = store.create_set(request.definition)
        return experiment_set_payload(definition, store)
    except (ExperimentConflict, ExperimentNotFound, ValueError) as error:
        raise _experiment_error(error) from error


@app.get("/api/agents/runtime")
def agent_runtime() -> dict[str, Any]:
    return runtime_status()


@app.post("/api/report-composer/plan")
def report_composer_plan() -> dict[str, Any]:
    return default_daily_risk_plan().model_dump(mode="json")


@app.post("/api/report-composer/compose")
def report_composer_compose(request: ReportComposeRequest) -> dict[str, Any]:
    report = compose_daily_risk_report(
        request.presentation,
        report_id=request.report_id,
        evidence_ids=request.evidence_ids,
    )
    report = with_rendered_html(report)
    validation = validate_report(
        report,
        available_evidence_ids=request.evidence_ids,
    )
    return {
        "report": report.model_dump(mode="json"),
        "validation": validation.model_dump(mode="json"),
        "markdown": report_markdown(report),
    }


@app.post("/api/report-composer/validate")
def report_composer_validate(request: ReportValidationRequest) -> dict[str, Any]:
    return validate_report(
        request.report,
        available_evidence_ids=request.available_evidence_ids,
    ).model_dump(mode="json")


@app.post("/api/report-composer/render")
def report_composer_render(request: ReportRenderRequest) -> dict[str, Any]:
    return {
        "renderer_version": request.report.renderer_version,
        "safe_html": render_report(request.report),
    }


@app.post("/api/workflow-cycle/sessions")
def create_workflow_cycle_session(
    request: WorkflowCycleCreateRequest,
) -> dict[str, Any]:
    configuration = prepare_workflow_cycle_configuration(request)
    session = workflow_cycle_manager.create(configuration)
    return session.snapshot()


@app.get("/api/workflow-cycle/sessions/{session_id}")
def workflow_cycle_session(session_id: str) -> dict[str, Any]:
    try:
        return workflow_cycle_manager.get(session_id).snapshot()
    except KeyError as error:
        raise HTTPException(status_code=404, detail="workflow cycle not found") from error


@app.post("/api/workflow-cycle/sessions/{session_id}/control")
def control_workflow_cycle_session(
    session_id: str, request: WorkflowCycleControlRequest
) -> dict[str, Any]:
    try:
        session = workflow_cycle_manager.get(session_id)
        if request.action == "start":
            session.start()
        elif request.action == "pause":
            session.pause()
        elif request.action == "set_speed":
            if request.speed is None:
                raise HTTPException(status_code=422, detail="set_speed requires speed")
            session.set_speed(request.speed)
        return session.snapshot()
    except KeyError as error:
        raise HTTPException(status_code=404, detail="workflow cycle not found") from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.post(
    "/api/workflow-cycle/sessions/{session_id}/decision-proposals/{proposal_id}/resolve"
)
def resolve_workflow_cycle_decision_proposal(
    session_id: str,
    proposal_id: str,
    request: WorkflowCycleDecisionRequest,
) -> dict[str, Any]:
    try:
        session = workflow_cycle_manager.get(session_id)
        session.resolve_proposal(
            proposal_id,
            request.outcome,
            resolver_id=request.resolver_id,
            resolver_type=request.resolver_type,
            rationale=request.rationale,
            idempotency_key=request.idempotency_key,
            expected_revision=request.expected_revision,
        )
        return session.snapshot()
    except KeyError as error:
        raise HTTPException(
            status_code=404,
            detail="session or decision proposal not found",
        ) from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.get("/api/decisions")
def decision_catalogue() -> dict[str, Any]:
    return decision_catalogue_payload()


@app.get("/api/decisions/{proposal_id}")
def decision_record(proposal_id: str) -> dict[str, Any]:
    try:
        return decision_record_payload(decision_store().get(proposal_id))
    except DecisionReviewNotFound as error:
        raise HTTPException(status_code=404, detail="decision proposal not found") from error


@app.post("/api/decisions/{proposal_id}/resolve")
def resolve_persisted_decision(proposal_id: str, request: DecisionResolveRequest) -> dict[str, Any]:
    try:
        session = workflow_cycle_manager.find_by_proposal(proposal_id)
        if session is not None:
            session.resolve_proposal(
                proposal_id, request.outcome, resolver_id=request.resolver_id,
                resolver_type=request.resolver_type, rationale=request.rationale,
                idempotency_key=request.idempotency_key,
                expected_revision=request.expected_revision,
            )
            record = session.decision_store.get(proposal_id)
        else:
            record = resolve_decision_record(
                decision_store(), proposal_id, DecisionOutcome(request.outcome),
                resolver_id=request.resolver_id, rationale=request.rationale,
                idempotency_key=request.idempotency_key,
                expected_revision=request.expected_revision,
            )
        return decision_record_payload(record)
    except DecisionReviewNotFound as error:
        raise HTTPException(status_code=404, detail="decision proposal not found") from error
    except DecisionReviewConflict as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@app.get("/api/decisions/{proposal_id}/due-diligence")
def decision_due_diligence(proposal_id: str) -> dict[str, Any]:
    try:
        return decision_due_diligence_payload(decision_store().get(proposal_id))
    except DecisionReviewNotFound as error:
        raise HTTPException(status_code=404, detail="decision proposal not found") from error


@app.post("/api/decisions/{proposal_id}/due-diligence/runs")
def execute_decision_due_diligence(
    proposal_id: str,
    request: DecisionDueDiligenceRunRequest,
) -> dict[str, Any]:
    try:
        session = workflow_cycle_manager.find_by_proposal(proposal_id)
        store = session.decision_store if session is not None else decision_store()
        record = run_due_diligence(
            store,
            proposal_id,
            name=request.name,
            investigation_question=request.investigation_question,
            capability_ids=tuple(request.capability_ids),
            candidate_recommendation=DecisionOutcome(request.candidate_recommendation),
            actor_id=request.actor_id,
            idempotency_key=request.idempotency_key,
            expected_revision=request.expected_revision,
        )
        return decision_due_diligence_payload(record)
    except DecisionReviewNotFound as error:
        raise HTTPException(status_code=404, detail="decision proposal not found") from error
    except DecisionReviewConflict as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@app.post("/api/workflow-cycle/sessions/{session_id}/agents")
def attach_workflow_cycle_agent(
    session_id: str,
    request: WorkflowCycleAgentAttachRequest,
) -> dict[str, Any]:
    try:
        session = workflow_cycle_manager.get(session_id)
        session.attach_agent(request.page_id, request.agent_id)
        return session.snapshot()
    except KeyError as error:
        raise HTTPException(status_code=404, detail="session or dashboard page not found") from error


@app.delete("/api/workflow-cycle/sessions/{session_id}")
def delete_workflow_cycle_session(session_id: str) -> dict[str, Any]:
    try:
        workflow_cycle_manager.delete(session_id)
        return {"deleted": True, "session_id": session_id}
    except KeyError as error:
        raise HTTPException(status_code=404, detail="workflow cycle not found") from error


@app.get("/api/agents/capability-platform")
def agent_capability_platform() -> dict[str, Any]:
    return capability_platform_manifest()


@app.get("/api/agents/templates")
def agent_templates() -> dict[str, Any]:
    agents = all_agent_templates()
    return {
        "agents": agents,
        "classes": {
            "static_system": [item for item in agents if item["agent_class"] == "static_system"],
            "experimental_specialist": [
                item for item in agents if item["agent_class"] == "experimental_specialist"
            ],
        },
    }


@app.get("/api/agents/system-agents")
def system_agents() -> dict[str, Any]:
    agents = [
        item for item in all_agent_templates() if item["agent_class"] == "static_system"
    ]
    return {"agents": agents, "count": len(agents)}


@app.post("/api/agents/system-agents/agent-studio-architect/fixture")
def run_agent_studio_architect_fixture() -> dict[str, Any]:
    return static_system_agent_fixture()


@app.get("/api/studios/codex/status")
def studio_codex_status(probe: bool = False) -> dict[str, Any]:
    """Inspect the local development provider without exposing authentication data."""

    return studio_codex_manager.status(probe=probe)


@app.get("/api/studios/codex/proposals")
def studio_codex_proposals() -> dict[str, Any]:
    proposals = studio_codex_manager.list_proposals()
    return {"proposals": proposals, "count": len(proposals)}


@app.post("/api/studios/codex/proposals")
def create_studio_codex_proposal(request: CodexProposalRequest) -> dict[str, Any]:
    try:
        return studio_codex_manager.create_proposal(request)
    except Exception as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.post("/api/studios/codex/proposals/{proposal_id}/approve")
def approve_studio_codex_proposal(
    proposal_id: str, request: CodexProposalApprovalRequest
) -> dict[str, Any]:
    try:
        return studio_codex_manager.approve_proposal(proposal_id, request)
    except KeyError as error:
        raise HTTPException(status_code=404, detail="Studio-Codex proposal not found") from error
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@app.get("/api/studios/codex/sessions")
def studio_codex_sessions(recover: bool = False) -> dict[str, Any]:
    if recover:
        studio_codex_manager.schedule_recovery()
    sessions = studio_codex_manager.list_sessions()
    return {"sessions": sessions, "count": len(sessions)}


@app.post("/api/studios/codex/sessions")
def start_studio_codex_session(request: CodexSessionRequest) -> dict[str, Any]:
    try:
        return studio_codex_manager.start_session(request)
    except KeyError as error:
        raise HTTPException(status_code=404, detail="Studio-Codex proposal not found") from error
    except PermissionError as error:
        raise HTTPException(status_code=403, detail=str(error)) from error
    except (RuntimeError, ValueError) as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@app.get("/api/studios/codex/sessions/{session_id}")
def studio_codex_session(session_id: str) -> dict[str, Any]:
    try:
        return studio_codex_manager.get_session(session_id)
    except KeyError as error:
        raise HTTPException(status_code=404, detail="Studio-Codex session not found") from error


@app.post("/api/studios/codex/sessions/{session_id}/turns")
def continue_studio_codex_session(
    session_id: str, request: CodexTurnRequest
) -> dict[str, Any]:
    try:
        return studio_codex_manager.start_turn(session_id, request)
    except KeyError as error:
        raise HTTPException(status_code=404, detail="Studio-Codex session not found") from error
    except (RuntimeError, ValueError) as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@app.post("/api/studios/codex/sessions/{session_id}/review")
def review_studio_codex_session(session_id: str) -> dict[str, Any]:
    try:
        return studio_codex_manager.review(session_id)
    except KeyError as error:
        raise HTTPException(status_code=404, detail="Studio-Codex session not found") from error
    except (RuntimeError, ValueError) as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@app.post("/api/studios/codex/sessions/{session_id}/interrupt")
def interrupt_studio_codex_session(session_id: str) -> dict[str, Any]:
    try:
        return studio_codex_manager.interrupt(session_id)
    except KeyError as error:
        raise HTTPException(status_code=404, detail="Studio-Codex session not found") from error
    except (RuntimeError, ValueError) as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@app.post("/api/studios/codex/sessions/{session_id}/approvals")
def resolve_studio_codex_approval(
    session_id: str, request: CodexApprovalRequest
) -> dict[str, Any]:
    try:
        return studio_codex_manager.respond_approval(session_id, request)
    except KeyError as error:
        raise HTTPException(status_code=404, detail="Codex approval request not found") from error
    except (RuntimeError, ValueError) as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@app.post("/api/studios/codex/sessions/{session_id}/archive")
def archive_studio_codex_session(session_id: str) -> dict[str, Any]:
    try:
        return studio_codex_manager.archive(session_id)
    except KeyError as error:
        raise HTTPException(status_code=404, detail="Studio-Codex session not found") from error
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@app.post("/api/agents/blueprint/validate")
def validate_agent_blueprint(blueprint: AgentBlueprint) -> dict[str, Any]:
    result = compile_blueprint(blueprint, persist=False)
    return {
        "valid": True,
        "blueprint": result["blueprint"],
        "graph": result["graph"],
        "checks": result["checks"],
    }


@app.post("/api/agents/blueprint/review")
def review_agent_blueprint_configuration(
    request: BlueprintReviewRequest,
) -> dict[str, Any]:
    try:
        return review_blueprint_configuration(request)
    except Exception as error:
        safe_type = re.sub(r"[^A-Za-z0-9_-]", "_", type(error).__name__)[:64]
        raise HTTPException(
            status_code=422,
            detail=f"Agent configuration review failed: {safe_type}",
        ) from error


@app.get("/api/agents/history")
def agent_history(agent_name: str, version: str = "0.1.0") -> dict[str, Any]:
    if not agent_name.strip():
        raise HTTPException(status_code=422, detail="agent_name is required")
    if not re.fullmatch(r"\d+\.\d+\.\d+", version):
        raise HTTPException(status_code=422, detail="version must use semantic versioning")
    return agent_development_history(agent_name.strip()[:80], version)


@app.post("/api/agents/blueprint/plan")
def create_agent_blueprint(request: BlueprintPlanRequest) -> dict[str, Any]:
    try:
        return plan_blueprint(request)
    except ModuleNotFoundError as error:
        missing = getattr(error, "name", None) or "required runtime dependency"
        raise HTTPException(
            status_code=503,
            detail=(
                f"Agent Blueprint planning is unavailable because {missing} is not "
                "installed in the server runtime. Restart the application with "
                "apps/portfolio-risk-workbench/labs/start_live_data.sh."
            ),
        ) from error
    except Exception as error:
        safe_type = re.sub(r"[^A-Za-z0-9_-]", "_", type(error).__name__)[:64]
        raise HTTPException(
            status_code=502,
            detail=f"OpenAI blueprint planning failed: {safe_type}",
        ) from error


@app.post("/api/agents/blueprint/refine")
def refine_agent_blueprint(request: BlueprintRefineRequest) -> dict[str, Any]:
    try:
        return refine_blueprint(request)
    except ModuleNotFoundError as error:
        missing = getattr(error, "name", None) or "required runtime dependency"
        raise HTTPException(
            status_code=503,
            detail=(
                f"Agent Blueprint refinement is unavailable because {missing} is not "
                "installed in the server runtime. Restart the application with "
                "apps/portfolio-risk-workbench/labs/start_live_data.sh."
            ),
        ) from error
    except Exception as error:
        detail = str(error).strip() or type(error).__name__
        detail = re.sub(r"[\r\n\t]+", " ", detail)[:1200]
        raise HTTPException(
            status_code=422,
            detail=f"Agent refinement failed: {detail}",
        ) from error


@app.post("/api/agents/blueprint/plan-section")
def create_agent_blueprint_section(request: SectionPlanRequest) -> dict[str, Any]:
    try:
        return plan_blueprint_section(request)
    except Exception as error:
        safe_type = re.sub(r"[^A-Za-z0-9_-]", "_", type(error).__name__)[:64]
        raise HTTPException(
            status_code=502,
            detail=f"OpenAI section planning failed: {safe_type}",
        ) from error


@app.post("/api/agents/advisor")
def review_agent_blueprint(request: BlueprintAdviceRequest) -> dict[str, Any]:
    try:
        return advise_blueprint(request)
    except Exception as error:
        safe_type = re.sub(r"[^A-Za-z0-9_-]", "_", type(error).__name__)[:64]
        raise HTTPException(
            status_code=502,
            detail=f"OpenAI design advisor failed: {safe_type}",
        ) from error


@app.post("/api/agents/compile")
def compile_agent(request: CompileRequest) -> dict[str, Any]:
    try:
        return compile_blueprint(request.blueprint, persist=request.persist)
    except Exception as error:
        raise HTTPException(
            status_code=422,
            detail=f"LangGraph compilation failed: {type(error).__name__}",
        ) from error


@app.post("/api/agents/input-preview")
def preview_agent_input(request: AgentInputPreviewRequest) -> dict[str, Any]:
    context, provenance = prepare_agent_input(request)
    return {"context": context, "provenance": provenance}


@app.post("/api/agents/run")
def run_agent(request: RunRequest) -> dict[str, Any]:
    try:
        if request.blueprint.agent_class == "static_system":
            raise HTTPException(
                status_code=409,
                detail=(
                    "Static System Agents use the Studio design fixture, not the portfolio "
                    "experiment runner. Run the Agent Studio Architect fixture instead."
                ),
            )
        preview_request = AgentInputPreviewRequest(
            data_mode=request.data_mode,
            scenario=request.scenario,
            portfolio_id=request.portfolio_id,
            as_of=date.fromisoformat(request.as_of) if request.as_of else None,
            datasets=request.datasets or ["market", "fundamental", "identity", "links"],
        )
        context, provenance = prepare_agent_input(preview_request)
        hydrated = request.model_copy(
            update={"input_context": context, "input_provenance": provenance}
        )
        return run_blueprint(hydrated)
    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(
            status_code=422,
            detail=f"LangGraph execution failed: {type(error).__name__}: {error}",
        ) from error


@app.post("/api/agents/compare")
def compare_agent_execution(request: RunRequest) -> dict[str, Any]:
    """Run one frozen input through deterministic and model-backed drafting."""

    if request.blueprint.agent_class == "static_system":
        raise HTTPException(
            status_code=409,
            detail="Static System Agents do not use the portfolio comparison runner.",
        )
    try:
        preview_request = AgentInputPreviewRequest(
            data_mode=request.data_mode,
            scenario=request.scenario,
            portfolio_id=request.portfolio_id,
            as_of=date.fromisoformat(request.as_of) if request.as_of else None,
            datasets=request.datasets or ["market", "fundamental", "identity", "links"],
        )
        context, provenance = prepare_agent_input(preview_request)
        created_at = datetime.now(timezone.utc).replace(microsecond=0)
        comparison_digest = hashlib.sha256(
            json.dumps(
                {
                    "blueprint": request.blueprint.model_dump(mode="json"),
                    "context": context,
                    "created_at": created_at.isoformat(),
                },
                sort_keys=True,
                default=str,
            ).encode()
        ).hexdigest()[:8]
        comparison_id = (
            f"comparison-{created_at.strftime('%Y%m%dT%H%M%SZ')}-{comparison_digest}"
        )
        common = {
            "input_context": context,
            "input_provenance": provenance,
            "comparison_id": comparison_id,
            "persist_run": True,
        }
        deterministic = run_blueprint(
            request.model_copy(update={**common, "execution_mode": "deterministic"})
        )
        live_llm = run_blueprint(
            request.model_copy(update={**common, "execution_mode": "live_llm"})
        )
        input_digest = "sha256:" + hashlib.sha256(
            json.dumps(context, sort_keys=True, separators=(",", ":"), default=str).encode()
        ).hexdigest()
        return {
            "comparison_id": comparison_id,
            "input_digest": input_digest,
            "same_frozen_input": True,
            "deterministic": deterministic,
            "live_llm": live_llm,
            "summary": {
                "deterministic_semantic_status": deterministic.get("final_state", {})
                .get("semantic_verification", {})
                .get("status"),
                "model_semantic_status": live_llm.get("final_state", {})
                .get("semantic_verification", {})
                .get("status"),
                "model_tokens": sum(
                    item.get("total_tokens", 0)
                    for item in live_llm.get("final_state", {}).get("model_receipts", [])
                ),
                "deterministic_elapsed_ms": deterministic.get("elapsed_ms"),
                "model_elapsed_ms": live_llm.get("elapsed_ms"),
            },
        }
    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(
            status_code=422,
            detail=f"Agent comparison failed: {type(error).__name__}: {error}",
        ) from error


@app.get("/api/agents/runs")
def agent_runs(include_retained: bool = False) -> dict[str, Any]:
    runs = list_agent_runs()
    retained_run_ids = {
        record.manifest.run_id
        for record in artifact_store().list(include_deleted=False)
        if record.manifest.run_id is not None
    }
    visible = runs if include_retained else [
        run for run in runs if run.get("run_id") not in retained_run_ids
    ]
    return {
        "runs": visible,
        "retained_run_count": len(retained_run_ids),
        "hidden_retained_run_count": len(runs) - len(visible),
    }


@app.get("/api/agents/runs/{run_id}")
def agent_run_detail(run_id: str) -> dict[str, Any]:
    try:
        return load_agent_run(run_id)
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail="agent run not found") from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.delete("/api/agents/runs/{run_id}")
def remove_agent_run(run_id: str) -> dict[str, Any]:
    raise HTTPException(
        status_code=409,
        detail=(
            "Immediate run-folder deletion is disabled. Review and explicitly admit the "
            "run in the Artifact Repository, then use its recoverable deletion lifecycle."
        ),
    )


@app.post("/api/agents/output-pass")
def run_agent_output_pass(request: OutputPassRunRequest) -> dict[str, Any]:
    try:
        return run_output_pass(request)
    except Exception as error:
        safe_type = re.sub(r"[^A-Za-z0-9_-]", "_", type(error).__name__)[:64]
        raise HTTPException(
            status_code=422,
            detail=f"Structured output pass failed: {safe_type}: {error}",
        ) from error


@app.post("/api/studios/risk-analysis/runs")
def run_risk_analysis_package(request: PackageRunRequest) -> dict[str, Any]:
    try:
        return execute_risk_analysis_package(request)
    except RuntimeError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except Exception as error:
        safe_type = re.sub(r"[^A-Za-z0-9_-]", "_", type(error).__name__)[:64]
        raise HTTPException(
            status_code=502,
            detail=f"Risk Analysis Package execution failed: {safe_type}",
        ) from error


@app.get("/api/studios/risk-analysis/runs")
def risk_analysis_package_runs() -> dict[str, Any]:
    return {"runs": list_risk_analysis_package_runs()}


@app.get("/api/studios/risk-analysis/runs/{run_id}")
def risk_analysis_package_run(run_id: str) -> dict[str, Any]:
    try:
        return load_risk_analysis_package_run(run_id)
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail="risk analysis package run not found") from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.delete("/api/studios/risk-analysis/runs/{run_id}")
def remove_risk_analysis_package_run(run_id: str) -> dict[str, Any]:
    try:
        return delete_risk_analysis_package_run(run_id)
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail="risk analysis package run not found") from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


def _mandate_catalogue_payload() -> dict[str, Any]:
    payload = mandate_studio_catalogue_data()
    projections = {
        (item.identity.kind, item.identity.asset_id): item
        for item in discover_registry_projections()
        if item.identity.kind in {AssetKind.MANDATE, AssetKind.RISK_POLICY}
    }
    documents = {
        item.projection.identity.reference: item
        for item in registry_store().list()
        if item.projection.identity.kind in {AssetKind.MANDATE, AssetKind.RISK_POLICY}
    }
    records = []
    for record in payload["records"]:
        mandate = record["mandate"]
        policy = record["risk_policy"]
        mandate_projection = projections[(AssetKind.MANDATE, mandate["object_id"])]
        policy_projection = projections[(AssetKind.RISK_POLICY, policy["object_id"])]
        mandate_document = documents.get(mandate_projection.identity.reference)
        policy_document = documents.get(policy_projection.identity.reference)
        records.append(
            {
                **record,
                "registry": {
                    "mandate_identity": mandate_projection.identity.model_dump(mode="json"),
                    "mandate_reference": mandate_projection.identity.reference,
                    "mandate_state": mandate_document.state.value if mandate_document else "discovered",
                    "policy_identity": policy_projection.identity.model_dump(mode="json"),
                    "policy_reference": policy_projection.identity.reference,
                    "policy_state": policy_document.state.value if policy_document else "discovered",
                    "registered": mandate_document is not None and policy_document is not None,
                },
            }
        )
    return {**payload, "records": records}


@app.get("/api/studios/mandates/catalogue")
def mandate_studio_catalogue() -> dict[str, Any]:
    return _mandate_catalogue_payload()


@app.post("/api/studios/mandates/design-preview")
def mandate_studio_design_preview(request: MandateDesignPreviewRequest) -> dict[str, Any]:
    try:
        return prepare_mandate_design_preview(request)
    except KeyError as error:
        raise HTTPException(status_code=404, detail="Mandate fixture not found") from error


@app.post("/api/studios/mandates/validate")
def mandate_studio_validate(request: MandateValidationRequest) -> dict[str, Any]:
    try:
        _, mandate, policy = mandate_bundle(request.mandate_id)
    except KeyError as error:
        raise HTTPException(status_code=404, detail="Mandate fixture not found") from error
    return validate_mandate_bundle(mandate, policy)


@app.post("/api/studios/mandates/register")
def mandate_studio_register(request: MandateRegistrationRequest) -> dict[str, Any]:
    try:
        _, mandate, policy = mandate_bundle(request.mandate_id)
    except KeyError as error:
        raise HTTPException(status_code=404, detail="Mandate fixture not found") from error
    validation = validate_mandate_bundle(mandate, policy)
    if not validation["valid"]:
        raise HTTPException(status_code=409, detail="Mandate bundle did not pass design validation")
    wanted = {
        (AssetKind.MANDATE, mandate.object_id),
        (AssetKind.RISK_POLICY, policy.object_id),
    }
    projections = [
        item
        for item in discover_registry_projections()
        if (item.identity.kind, item.identity.asset_id) in wanted
    ]
    if len(projections) != 2:
        raise HTTPException(status_code=409, detail="Exact mandate Registry projections are unavailable")
    try:
        documents, conflicts = registry_store().index_many(projections, actor=request.actor)
    except (RegistryConflict, ValueError) as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    if conflicts:
        raise HTTPException(status_code=409, detail="; ".join(conflicts))
    return {
        "registered": True,
        "mandate_id": mandate.object_id,
        "records": [document_payload(document) for document in documents],
        "validation": validation,
        "production_publication": False,
        "effects": [],
    }


@app.get("/api/application/mandate")
def mandate_application_catalogue() -> dict[str, Any]:
    try:
        return mandate_application_catalogue_data(registry_store())
    except (KeyError, RegistryConflict, ValueError) as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@app.post("/api/application/mandate/run")
def mandate_application_run(request: MandateApplicationRequest) -> dict[str, Any]:
    try:
        return run_mandate_application(request, registry_store())
    except KeyError as error:
        raise HTTPException(status_code=404, detail="Mandate application input was not found") from error
    except (PermissionError, RegistryConflict, ValueError) as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@app.get("/api/studios/capabilities/catalogue")
def capability_studio_catalogue() -> dict[str, Any]:
    return capability_catalogue()


@app.post("/api/studios/capabilities/assess")
def capability_studio_assessment(request: CapabilityAssessmentRequest) -> dict[str, Any]:
    try:
        assessment = assess_capability_requirement(request)
        save_capability_design_session(request, assessment)
        return assessment.model_dump(mode="json")
    except RuntimeError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.get("/api/studios/capabilities/design-sessions")
def capability_studio_design_sessions() -> dict[str, Any]:
    return {"sessions": list_capability_design_sessions()}


@app.get("/api/studios/capabilities/design-sessions/{session_id}")
def capability_studio_design_session(session_id: str) -> dict[str, Any]:
    try:
        return load_capability_design_session(session_id)
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail="capability design session not found") from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.delete("/api/studios/capabilities/design-sessions/{session_id}")
def capability_studio_delete_design_session(session_id: str) -> dict[str, Any]:
    try:
        return delete_capability_design_session(session_id)
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail="capability design session not found") from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.get("/api/studios/capabilities/proposals")
def capability_studio_proposals() -> dict[str, Any]:
    return {"proposals": list_capability_proposals()}


@app.post("/api/studios/capabilities/proposals")
def capability_studio_create_proposal(request: CapabilityProposalCreateRequest) -> dict[str, Any]:
    try:
        return create_capability_proposal(request)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.post("/api/studios/capabilities/blueprints")
def capability_studio_compile_blueprint(request: CapabilityProposalCreateRequest) -> dict[str, Any]:
    return {
        "decision": request.decision,
        "blueprint": compile_capability_blueprint(request).model_dump(mode="json"),
    }


@app.post("/api/studios/capabilities/proposals/approve")
def capability_studio_approve_blueprint(request: CapabilityProposalCreateRequest) -> dict[str, Any]:
    try:
        return approve_capability_blueprint(request)
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@app.post("/api/studios/design-proposals")
def studio_design_proposal(request: StudioDesignProposalRequest) -> dict[str, Any]:
    try:
        return create_studio_design_proposal(request)
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@app.delete("/api/studios/capabilities/proposals/{proposal_id}")
def capability_studio_delete_proposal(proposal_id: str) -> dict[str, Any]:
    try:
        return delete_capability_proposal(proposal_id)
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail="capability proposal not found") from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.post("/api/studios/capabilities/proposals/{proposal_id}/transition")
def capability_studio_transition_proposal(
    proposal_id: str,
    request: CapabilityProposalTransitionRequest,
) -> dict[str, Any]:
    try:
        return transition_capability_proposal(proposal_id, request)
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail="capability proposal not found") from error
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@app.get("/api/studios/capabilities/runs")
def capability_studio_runs() -> dict[str, Any]:
    return {"runs": list_capability_fixture_runs()}


@app.post("/api/studios/capabilities/runs")
def capability_studio_execute_run(request: CapabilityFixtureRunRequest) -> dict[str, Any]:
    try:
        return execute_capability_fixture(request)
    except RuntimeError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except Exception as error:
        safe_type = re.sub(r"[^A-Za-z0-9_-]", "_", type(error).__name__)[:64]
        raise HTTPException(status_code=502, detail=f"Capability fixture execution failed: {safe_type}") from error


@app.get("/api/studios/capabilities/runs/{run_id}")
def capability_studio_run(run_id: str) -> dict[str, Any]:
    try:
        return load_capability_fixture_run(run_id)
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail="capability fixture run not found") from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.delete("/api/studios/capabilities/runs/{run_id}")
def capability_studio_delete_run(run_id: str) -> dict[str, Any]:
    try:
        return delete_capability_fixture_run(run_id)
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail="capability fixture run not found") from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


app.mount("/", StaticFiles(directory=PROTOTYPE_ROOT, html=True), name="prototype")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    arguments = parser.parse_args()
    if arguments.host not in {"127.0.0.1", "localhost"}:
        raise SystemExit("licensed-data service may bind only to localhost")
    uvicorn.run(app, host=arguments.host, port=arguments.port, log_level="info")


if __name__ == "__main__":
    main()
