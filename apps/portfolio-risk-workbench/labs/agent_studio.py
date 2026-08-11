"""Validated LangGraph blueprint compiler and isolated execution runtime."""

from __future__ import annotations

import hashlib
import importlib.metadata
import importlib.util
import json
import math
import os
import random
import re
import shutil
import statistics
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field, ValidationError, field_validator, model_validator
from risk_reports import (
    compose_daily_risk_report,
    report_markdown,
    validate_report,
    with_rendered_html,
)


COMPILER_VERSION = "agent-blueprint-compiler/0.4.0"
COST_OPTIMIZED_LLM_MODEL = "gpt-5.6-luna"
STUDIO_CODEX_MODEL = "gpt-5.6-terra"
STUDIO_CODEX_REASONING_EFFORT = "high"

def _repository_root(start: Path) -> Path:
    for candidate in (start, *start.parents):
        if (candidate / ".git").exists():
            return candidate
    return start


GENERATED_ROOT = Path(
    os.environ.get(
        "PORTFOLIO_RISK_AGENT_OUTPUT_ROOT",
        _repository_root(Path(__file__).resolve().parent)
        / ".agent-runs"
        / "generated-agents",
    )
).expanduser().resolve()


RUN_ROOT = Path(
    os.environ.get(
        "PORTFOLIO_RISK_AGENT_RUN_ROOT",
        _repository_root(Path(__file__).resolve().parent) / ".agent-runs" / "agent-lab",
    )
).expanduser().resolve()

CAPABILITY_MEMORY_ROOT = Path(
    os.environ.get(
        "PORTFOLIO_RISK_CAPABILITY_MEMORY_ROOT",
        _repository_root(Path(__file__).resolve().parent)
        / ".agent-runs"
        / "capability-memory",
    )
).expanduser().resolve()
CAPABILITY_MEMORY_MIN_ELAPSED_MS = int(
    os.environ.get("PORTFOLIO_RISK_CAPABILITY_MEMORY_MIN_MS", "5000")
)
AGENT_DEVELOPMENT_ROOT = Path(
    os.environ.get(
        "PORTFOLIO_RISK_AGENT_DEVELOPMENT_ROOT",
        _repository_root(Path(__file__).resolve().parent)
        / ".agent-runs"
        / "agent-development",
    )
).expanduser().resolve()

META_CAPABILITY_REGISTRY: tuple[dict[str, Any], ...] = (
    {
        "capability_id": "meta.data.query.duckdb",
        "name": "Governed DuckDB query",
        "purpose": "Fetch point-in-time research data through validated read-only SQL.",
        "status": "available",
        "input_contract": "GovernedSqlQueryRequest",
        "output_contract": "TabularDatasetArtifact",
        "effects": [],
        "look_ahead_guard": "Every temporal dataset must be bounded by the assignment as-of time.",
        "memory_policy": "reuse_when_identical_and_slow",
    },
    {
        "capability_id": "meta.visualisation.render",
        "name": "Visualisation renderer",
        "purpose": "Create a reviewable chart from a registered dataset artifact and chart specification.",
        "status": "foundation",
        "input_contract": "VisualisationRequest",
        "output_contract": "VisualisationArtifact",
        "effects": ["write_run_artifact"],
        "look_ahead_guard": "Inherited from the dataset artifact and its evidence receipt.",
        "memory_policy": "reuse_when_identical_and_slow",
    },
    {
        "capability_id": "meta.package.compose",
        "name": "Live package composer",
        "purpose": "Compose registered findings, tables and visualisations into a run-scoped review package.",
        "status": "foundation",
        "input_contract": "PackageCompositionRequest",
        "output_contract": "ReviewPackageArtifact",
        "effects": ["write_run_artifact"],
        "look_ahead_guard": "May only consume artifacts eligible for the same workflow date.",
        "memory_policy": "reuse_when_identical_and_slow",
    },
    {
        "capability_id": "meta.capability.propose",
        "name": "Capability proposal",
        "purpose": "Draft a non-executable capability specification when an analytical gap is found.",
        "status": "foundation",
        "input_contract": "CapabilityProposalRequest",
        "output_contract": "CapabilityProposalDraft",
        "effects": [],
        "look_ahead_guard": "The proposal inherits the assignment's data boundary and cannot self-register.",
        "memory_policy": "never",
    },
)


def _ensure_workspace_packages() -> None:
    """Make the repository's canonical packages importable in the local lab."""

    package_root = _repository_root(Path(__file__).resolve().parent) / "packages"
    for source_root in sorted(package_root.glob("*/src")):
        path = str(source_root)
        if path not in sys.path:
            sys.path.insert(0, path)


def capability_platform_manifest() -> dict[str, Any]:
    """Expose the bounded runtime surface without making draft meta-tools executable."""

    return {
        "context_lifecycle": [
            "frozen_source_data",
            "parameterized_capability_requests",
            "canonical_calculations",
            "overall_default_context",
            "agent_interpretation",
            "human_review",
        ],
        "memory": {
            "key": "capability_id + canonical_input_digest + point_in_time_boundary",
            "minimum_elapsed_ms": CAPABILITY_MEMORY_MIN_ELAPSED_MS,
            "reuse_rule": "Only successful, effect-free results on an identical input digest may be reused.",
            "root": str(CAPABILITY_MEMORY_ROOT),
        },
        "meta_capabilities": list(META_CAPABILITY_REGISTRY),
    }


def _memory_payload_key(namespace: str, value: Any) -> str:
    canonical = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(f"{namespace}:{canonical}".encode()).hexdigest()


def _load_capability_memory(namespace: str, value: Any) -> dict[str, Any] | None:
    key = _memory_payload_key(namespace, value)
    path = CAPABILITY_MEMORY_ROOT / namespace.replace(".", "-") / f"{key}.json"
    if not path.exists():
        return None
    payload = json.loads(path.read_text())
    if payload.get("input_key") != key or payload.get("status") != "succeeded":
        return None
    return payload


def _store_capability_memory(
    namespace: str,
    value: Any,
    result: dict[str, Any],
    *,
    elapsed_ms: float,
) -> None:
    if elapsed_ms < CAPABILITY_MEMORY_MIN_ELAPSED_MS:
        return
    calls = result.get("calls", [])
    if not calls or any(call.get("status") != "succeeded" for call in calls):
        return
    if any(call.get("receipt", {}).get("effects") for call in calls):
        return
    key = _memory_payload_key(namespace, value)
    directory = CAPABILITY_MEMORY_ROOT / namespace.replace(".", "-")
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{key}.json"
    payload = {
        "input_key": key,
        "namespace": namespace,
        "status": "succeeded",
        "stored_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "elapsed_ms": elapsed_ms,
        "result": result,
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n")


def _mark_memory_reuse(payload: dict[str, Any]) -> dict[str, Any]:
    result = payload["result"]
    for call in result.get("calls", []):
        receipt = call.setdefault("receipt", {})
        receipt["memory_reused"] = True
        receipt["memory_stored_at"] = payload.get("stored_at")
        receipt["original_elapsed_ms"] = payload.get("elapsed_ms")
    return result

CAPABILITIES: dict[str, dict[str, str]] = {
    "market_data": {
        "name": "Point-in-time market data",
        "description": "Reads eligible CRSP market observations as of the workflow date.",
    },
    "risk_metrics": {
        "name": "Risk metric lookup",
        "description": "Reads deterministic MetricPack values; it does not invent calculations.",
    },
    "portfolio_exposure": {
        "name": "Portfolio exposure",
        "description": "Calculates weights, concentration, and mandate headroom.",
    },
    "scenario_stress": {
        "name": "Scenario stress",
        "description": "Runs bounded deterministic shocks without portfolio mutation.",
    },
    "fundamental_change": {
        "name": "Fundamental change",
        "description": "Compares point-in-time Compustat fundamentals without look-ahead.",
    },
    "event_retrieval": {
        "name": "Event retrieval",
        "description": "Retrieves governed events known by the as-of timestamp.",
    },
    "evidence_critic": {
        "name": "Evidence critic",
        "description": "Checks whether narrative claims are supported by supplied evidence.",
    },
    "registry_agent_search": {
        "name": "Agent registry search",
        "description": "Finds reusable registered agent definitions and versions before proposing a new one.",
    },
    "agent_blueprint_examples": {
        "name": "Agent blueprint examples",
        "description": "Retrieves bounded examples and design guidance for the selected agent class and Studio scope.",
    },
    "agent_blueprint_validate": {
        "name": "Agent blueprint validator",
        "description": "Validates a candidate blueprint against class, contract, authority, and lifecycle invariants.",
    },
    "studio_codex_brief_prepare": {
        "name": "Studio-Codex brief preparation",
        "description": "Prepares a reviewable, non-executing build brief for an approved candidate blueprint.",
    },
}

RISK_CAPABILITY_IDS = frozenset(
    {
        "market_data",
        "risk_metrics",
        "portfolio_exposure",
        "scenario_stress",
        "fundamental_change",
        "event_retrieval",
        "evidence_critic",
    }
)
SYSTEM_CAPABILITY_IDS = frozenset(CAPABILITIES) - RISK_CAPABILITY_IDS
RISK_INPUT_CONTRACTS = frozenset(
    {"PortfolioContext", "RiskContext", "OverallDefaultContext", "SpecialistOutputBundle"}
)
SYSTEM_INPUT_CONTRACTS = frozenset({"AgentBlueprintContext", "StudioDesignContext"})
RISK_OUTPUT_CONTRACTS = frozenset(
    {"SpecialistInterpretation", "RiskReviewDraft", "EvidenceCritique", "CapabilityRequest"}
)
SYSTEM_OUTPUT_CONTRACTS = frozenset({"AgentBlueprintProposal", "AgentDesignCritique"})

PATTERN_NODES: dict[str, list[str]] = {
    "direct": ["load_context", "gather_evidence", "assemble_context", "draft"],
    "tool_loop": ["load_context", "gather_evidence", "assemble_context", "draft", "evidence_critic"],
    "reflection": ["load_context", "gather_evidence", "assemble_context", "draft", "evidence_critic"],
    "human_review": [
        "load_context",
        "gather_evidence",
        "assemble_context",
        "draft",
        "evidence_critic",
        "human_review",
    ],
}


class InstructionRules(BaseModel):
    objective: str = Field(min_length=20, max_length=1200)
    success_criteria: list[str] = Field(min_length=1, max_length=8)
    constraints: list[str] = Field(min_length=1, max_length=10)
    stopping_conditions: list[str] = Field(min_length=1, max_length=6)
    narrative_style: str = Field(min_length=10, max_length=600)


class PromptMessageSpec(BaseModel):
    role: Literal["system", "developer", "user"]
    name: str = Field(min_length=2, max_length=60)
    content: str = Field(min_length=10, max_length=5000)
    enabled: bool = True


class PromptTemplateSpec(BaseModel):
    template: str = Field(min_length=20, max_length=6000)
    variables: list[str] = Field(min_length=1, max_length=16)
    missing_variable_policy: Literal["fail", "preserve_placeholder", "empty"] = "fail"
    output_format_instruction: str = Field(min_length=10, max_length=1200)

    @field_validator("variables")
    @classmethod
    def variables_are_identifiers(cls, values: list[str]) -> list[str]:
        invalid = [value for value in values if not re.fullmatch(r"[a-z][a-z0-9_]*", value)]
        if invalid:
            raise ValueError(f"invalid prompt variables: {', '.join(invalid)}")
        return list(dict.fromkeys(values))


class StateFieldSpec(BaseModel):
    name: str = Field(min_length=2, max_length=64)
    value_type: Literal["string", "number", "boolean", "object", "array"]
    description: str = Field(min_length=10, max_length=500)
    source: Literal["input", "capability", "agent", "governance", "runtime"]
    required: bool = True
    reducer: Literal["replace", "append", "merge"] = "replace"

    @field_validator("name")
    @classmethod
    def name_is_identifier(cls, value: str) -> str:
        if not re.fullmatch(r"[a-z][a-z0-9_]*", value):
            raise ValueError("state field names must use lower_snake_case")
        return value


class RoutingRules(BaseModel):
    description: str = Field(min_length=20, max_length=1200)
    strategy: Literal["direct", "tool_loop", "reflection", "human_review"] = (
        "human_review"
    )
    entry_condition: str = Field(min_length=5, max_length=500)
    revision_condition: str = Field(min_length=5, max_length=500)
    escalation_condition: str = Field(min_length=5, max_length=500)
    stop_condition: str = Field(min_length=5, max_length=500)
    missing_evidence_route: Literal["abstain", "revise", "human_review"] = (
        "human_review"
    )
    max_iterations: int = Field(default=2, ge=1, le=4)


class MemoryRules(BaseModel):
    description: str = Field(min_length=20, max_length=1000)
    scope: Literal["none", "workflow_cycle", "experiment", "session"] = (
        "workflow_cycle"
    )
    checkpoint: Literal["none", "in_memory"] = "in_memory"
    remember_fields: list[str] = Field(default_factory=list, max_length=16)
    retention_rule: str = Field(min_length=10, max_length=600)
    compaction_rule: str = Field(min_length=10, max_length=600)


class GovernanceRules(BaseModel):
    description: str = Field(min_length=20, max_length=1200)
    evidence_required: bool = True
    human_approval: bool = True
    abstention_rule: str = Field(min_length=10, max_length=700)
    prohibited_actions: list[str] = Field(min_length=1, max_length=10)
    effects_allowed: Literal[False] = False


class StaticSystemScope(BaseModel):
    """Visible least-privilege boundary for proposal-producing Studio agents."""

    owning_studio: Literal[
        "agent",
        "capability",
        "workflow",
        "dashboard",
        "report",
        "risk_analysis",
        "portfolio_mandate",
        "provider_connector",
        "scenario",
    ]
    supported_intents: list[
        Literal[
            "explain",
            "teach",
            "show_examples",
            "clarify",
            "assess_feasibility",
            "plan",
            "critique",
            "synthesize",
        ]
    ] = Field(min_length=1, max_length=8)
    codebase_scope: list[str] = Field(min_length=1, max_length=16)
    skill_ids: list[str] = Field(min_length=1, max_length=8)
    knowledge_sources: list[str] = Field(min_length=1, max_length=16)
    proposal_only: Literal[True] = True

    @field_validator("codebase_scope", "knowledge_sources")
    @classmethod
    def repository_paths_are_bounded(cls, values: list[str]) -> list[str]:
        for value in values:
            path = Path(value)
            if path.is_absolute() or ".." in path.parts:
                raise ValueError("Studio agent paths must be repository-relative and bounded")
        return list(dict.fromkeys(values))

    @field_validator("skill_ids")
    @classmethod
    def skills_are_identifiers(cls, values: list[str]) -> list[str]:
        invalid = [value for value in values if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", value)]
        if invalid:
            raise ValueError(f"invalid skill identifiers: {', '.join(invalid)}")
        return list(dict.fromkeys(values))


class CapabilityLatchSpec(BaseModel):
    capability_id: str
    purpose: str = Field(min_length=10, max_length=500)
    invocation_condition: str = Field(min_length=5, max_length=700)
    output_binding: str = Field(min_length=2, max_length=64)
    required: bool = False
    failure_policy: Literal["abstain", "continue_with_warning", "retry", "human_review"]

    @field_validator("capability_id")
    @classmethod
    def capability_is_known(cls, value: str) -> str:
        if value not in CAPABILITIES:
            raise ValueError(f"unknown capability grant: {value}")
        return value

    @field_validator("output_binding")
    @classmethod
    def output_binding_is_identifier(cls, value: str) -> str:
        if not re.fullmatch(r"[a-z][a-z0-9_]*", value):
            raise ValueError("capability output bindings must use lower_snake_case")
        return value


class StructuredOutputFieldSpec(BaseModel):
    name: str = Field(min_length=2, max_length=64)
    title: str = Field(min_length=2, max_length=120)
    value_type: Literal["string", "number", "integer", "boolean", "object", "array"]
    semantic_role: Literal[
        "introduction",
        "narrative",
        "table",
        "chart_spec",
        "html_fragment",
        "d3_spec",
        "dashboard",
        "methodology",
        "results",
        "recommendations",
        "evidence",
        "metadata",
        "other",
    ]
    description: str = Field(min_length=10, max_length=1000)
    nullable: bool = False
    format: Literal[
        "none",
        "date",
        "date-time",
        "duration",
        "email",
        "uuid",
        "markdown",
        "html",
        "json",
    ] = "none"
    enum_values: list[str] = Field(default_factory=list, max_length=30)
    nested_schema_json: str = Field(default="", max_length=6000)
    merge_strategy: Literal["replace", "append", "merge"] = "replace"
    citation_required: bool = False
    validation_rule: str = Field(min_length=5, max_length=800)
    produced_in_passes: list[str] = Field(min_length=1, max_length=12)

    @field_validator("name")
    @classmethod
    def output_name_is_identifier(cls, value: str) -> str:
        if not re.fullmatch(r"[a-z][a-z0-9_]*", value):
            raise ValueError("structured output fields must use lower_snake_case")
        return value

    @field_validator("nested_schema_json")
    @classmethod
    def nested_schema_is_json(cls, value: str) -> str:
        if not value.strip():
            return ""
        parsed = json.loads(value)
        if not isinstance(parsed, dict):
            raise ValueError("nested schema JSON must describe an object")
        return json.dumps(parsed, separators=(",", ":"), sort_keys=True)


class OutputPresentationSpec(BaseModel):
    description: str = Field(min_length=20, max_length=1600)
    composition: Literal[
        "single_narrative",
        "sectioned_report",
        "dashboard",
        "report_and_dashboard",
        "data_product",
    ] = "sectioned_report"
    visual_hierarchy: str = Field(min_length=10, max_length=1000)
    tone: str = Field(min_length=5, max_length=600)
    information_density: Literal["spacious", "balanced", "dense"] = "balanced"
    typography_direction: str = Field(min_length=5, max_length=600)
    color_direction: str = Field(min_length=5, max_length=600)
    chart_policy: str = Field(min_length=10, max_length=1000)
    table_policy: str = Field(min_length=10, max_length=1000)
    html_policy: str = Field(min_length=10, max_length=1000)
    responsive_behavior: str = Field(min_length=10, max_length=800)
    accessibility_requirements: list[str] = Field(min_length=1, max_length=10)
    rendering_instructions: str = Field(min_length=10, max_length=1600)


class StructuredOutputSpec(BaseModel):
    name: str = Field(min_length=3, max_length=80)
    description: str = Field(min_length=20, max_length=1200)
    rendering_target: Literal[
        "json",
        "markdown_document",
        "html_dashboard",
        "mixed_artifact",
    ] = "mixed_artifact"
    strict: Literal[True] = True
    additional_properties: Literal[False] = False
    presentation: OutputPresentationSpec
    fields: list[StructuredOutputFieldSpec] = Field(min_length=1, max_length=32)
    completion_rule: str = Field(min_length=10, max_length=1000)
    quality_gate: str = Field(min_length=10, max_length=1000)
    versioning_strategy: Literal[
        "snapshot_each_pass",
        "final_only",
        "snapshot_and_final",
    ] = "snapshot_and_final"

    @field_validator("fields")
    @classmethod
    def output_fields_are_unique(
        cls, values: list[StructuredOutputFieldSpec]
    ) -> list[StructuredOutputFieldSpec]:
        names = [value.name for value in values]
        if len(names) != len(set(names)):
            raise ValueError("structured output field names must be unique")
        return values


class ExperimentalWrapperSpec(BaseModel):
    """Mandatory experiment instrumentation compiled with every risk agent."""

    execution_mode: Literal["headless"] = "headless"
    evaluation_contract: Literal["AgentStructuredOutput/v1"] = "AgentStructuredOutput/v1"
    presentation_artifact_policy: Literal["label_and_exclude"] = "label_and_exclude"
    captures_runtime_behavior: Literal[True] = True
    maps_to_architecture_output: bool


class OutputPassSpec(BaseModel):
    pass_id: str = Field(min_length=2, max_length=64)
    title: str = Field(min_length=3, max_length=120)
    objective: str = Field(min_length=15, max_length=1200)
    target_fields: list[str] = Field(min_length=1, max_length=16)
    operation: Literal["replace", "append", "merge"] = "replace"
    context_policy: Literal[
        "full_context",
        "evidence_subset",
        "prior_output_summary",
        "selected_prior_fields",
    ] = "selected_prior_fields"
    depends_on: list[str] = Field(default_factory=list, max_length=12)
    max_output_tokens: int = Field(default=2400, ge=256, le=16000)
    quality_gate: str = Field(min_length=10, max_length=800)
    human_review_after: bool = False

    @field_validator("pass_id")
    @classmethod
    def pass_id_is_identifier(cls, value: str) -> str:
        if not re.fullmatch(r"[a-z][a-z0-9_]*", value):
            raise ValueError("output pass IDs must use lower_snake_case")
        return value


class OutputAssemblyPlan(BaseModel):
    description: str = Field(min_length=20, max_length=1200)
    strategy: Literal[
        "sequential_section_build",
        "iterative_refinement",
        "map_reduce_sections",
    ] = "sequential_section_build"
    passes: list[OutputPassSpec] = Field(min_length=1, max_length=12)
    carry_forward_rule: str = Field(min_length=10, max_length=1000)
    finalization_rule: str = Field(min_length=10, max_length=1000)
    max_total_output_tokens: int = Field(default=24000, ge=1000, le=120000)
    stop_on_failure: bool = True
    human_review_between_passes: bool = False

    @field_validator("passes")
    @classmethod
    def pass_ids_are_unique(cls, values: list[OutputPassSpec]) -> list[OutputPassSpec]:
        pass_ids = [value.pass_id for value in values]
        if len(pass_ids) != len(set(pass_ids)):
            raise ValueError("output assembly pass IDs must be unique")
        return values


class AgentBlueprint(BaseModel):
    """Transport-level authoring contract; not a new portfolio domain object."""

    name: str = Field(min_length=3, max_length=80)
    agent_class: Literal["static_system", "experimental_specialist"] = (
        "experimental_specialist"
    )
    version: str = Field(default="0.1.0", pattern=r"^\d+\.\d+\.\d+$")
    static_system_scope: StaticSystemScope | None = None
    experimental_role: Literal["final_decision_agent", "specialist_node"] | None = None
    experimental_wrapper: ExperimentalWrapperSpec | None = None
    purpose: str = Field(min_length=20, max_length=1200)
    model: Literal["gpt-5.6-luna"] = COST_OPTIMIZED_LLM_MODEL
    input_contract: Literal[
        "PortfolioContext",
        "RiskContext",
        "OverallDefaultContext",
        "SpecialistOutputBundle",
        "AgentBlueprintContext",
        "StudioDesignContext",
    ] = "OverallDefaultContext"
    output_contract: Literal[
        "SpecialistInterpretation",
        "RiskReviewDraft",
        "EvidenceCritique",
        "CapabilityRequest",
        "AgentBlueprintProposal",
        "AgentDesignCritique",
    ] = "RiskReviewDraft"
    instructions: InstructionRules
    prompt_messages: list[PromptMessageSpec] = Field(min_length=1, max_length=8)
    prompt_template: PromptTemplateSpec
    state_management_description: str = Field(min_length=20, max_length=1200)
    state_schema: list[StateFieldSpec] = Field(min_length=1, max_length=20)
    routing: RoutingRules
    memory_rules: MemoryRules
    governance: GovernanceRules
    capability_latches: list[CapabilityLatchSpec] = Field(
        min_length=1, max_length=len(CAPABILITIES)
    )
    structured_output: StructuredOutputSpec
    output_assembly: OutputAssemblyPlan
    retry_attempts: int = Field(default=1, ge=0, le=3)
    timeout_seconds: int = Field(default=45, ge=5, le=180)

    @model_validator(mode="before")
    @classmethod
    def attach_experimental_wrapper(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value
        payload = dict(value)
        if payload.get("agent_class", "experimental_specialist") == "experimental_specialist":
            role = payload.get("experimental_role")
            if role is None:
                role = (
                    "final_decision_agent"
                    if payload.get("output_contract", "RiskReviewDraft") == "RiskReviewDraft"
                    else "specialist_node"
                )
                payload["experimental_role"] = role
            payload.setdefault(
                "experimental_wrapper",
                {
                    "execution_mode": "headless",
                    "evaluation_contract": "AgentStructuredOutput/v1",
                    "presentation_artifact_policy": "label_and_exclude",
                    "captures_runtime_behavior": True,
                    "maps_to_architecture_output": role == "final_decision_agent",
                },
            )
        return payload

    @field_validator("state_schema")
    @classmethod
    def state_fields_are_unique(cls, values: list[StateFieldSpec]) -> list[StateFieldSpec]:
        names = [value.name for value in values]
        if len(names) != len(set(names)):
            raise ValueError("state field names must be unique")
        return values

    @model_validator(mode="after")
    def governance_is_coherent(self) -> "AgentBlueprint":
        if self.governance.human_approval and self.routing.strategy != "human_review":
            raise ValueError(
                "human approval requires the human_review routing strategy"
            )
        if self.routing.strategy == "human_review" and not self.governance.human_approval:
            raise ValueError(
                "the human_review routing strategy requires human approval"
            )
        capabilities = [value.capability_id for value in self.capability_latches]
        if len(capabilities) != len(set(capabilities)):
            raise ValueError("capability latches must be unique")
        if (
            self.agent_class == "experimental_specialist"
            and self.governance.evidence_required
            and "evidence_critic" not in capabilities
        ):
            raise ValueError(
                "evidence-required governance requires an evidence_critic latch"
            )
        if self.agent_class == "static_system":
            if self.experimental_role is not None or self.experimental_wrapper is not None:
                raise ValueError("static system agents cannot declare an experimental wrapper")
            if self.static_system_scope is None:
                raise ValueError("static system agents require a visible Studio scope")
            if self.input_contract not in SYSTEM_INPUT_CONTRACTS:
                raise ValueError("static system agents require a Studio design input contract")
            if self.output_contract not in SYSTEM_OUTPUT_CONTRACTS:
                raise ValueError("static system agents produce proposals or design critiques only")
            unknown = sorted(set(capabilities) - SYSTEM_CAPABILITY_IDS)
            if unknown:
                raise ValueError(
                    "static system agents cannot use experimental risk capabilities: "
                    + ", ".join(unknown)
                )
            if not self.governance.human_approval:
                raise ValueError("static system agent proposals require human approval")
        else:
            if self.experimental_role is None or self.experimental_wrapper is None:
                raise ValueError("experimental agents require a headless evaluation wrapper")
            expected_mapping = self.experimental_role == "final_decision_agent"
            if self.experimental_wrapper.maps_to_architecture_output != expected_mapping:
                raise ValueError("only final decision agents map directly to ArchitectureOutput")
            if self.static_system_scope is not None:
                raise ValueError("experimental specialists cannot declare a Static System scope")
            if self.input_contract not in RISK_INPUT_CONTRACTS:
                raise ValueError("experimental specialists require a portfolio-risk input contract")
            if self.output_contract not in RISK_OUTPUT_CONTRACTS:
                raise ValueError("experimental specialists require a portfolio-risk output contract")
            unknown = sorted(set(capabilities) - RISK_CAPABILITY_IDS)
            if unknown:
                raise ValueError(
                    "experimental specialists cannot use Studio design capabilities: "
                    + ", ".join(unknown)
                )
        state_names = {value.name for value in self.state_schema}
        unknown_memory_fields = sorted(set(self.memory_rules.remember_fields) - state_names)
        if unknown_memory_fields:
            raise ValueError(
                "memory fields are absent from state schema: "
                + ", ".join(unknown_memory_fields)
            )
        output_names = {value.name for value in self.structured_output.fields}
        pass_ids = [value.pass_id for value in self.output_assembly.passes]
        known_passes = set(pass_ids)
        produced_fields: set[str] = set()
        for output_pass in self.output_assembly.passes:
            unknown_targets = sorted(set(output_pass.target_fields) - output_names)
            if unknown_targets:
                raise ValueError(
                    f"output pass {output_pass.pass_id} targets unknown fields: "
                    + ", ".join(unknown_targets)
                )
            unknown_dependencies = sorted(set(output_pass.depends_on) - known_passes)
            if unknown_dependencies:
                raise ValueError(
                    f"output pass {output_pass.pass_id} has unknown dependencies: "
                    + ", ".join(unknown_dependencies)
                )
            if output_pass.pass_id in output_pass.depends_on:
                raise ValueError(
                    f"output pass {output_pass.pass_id} cannot depend on itself"
                )
            produced_fields.update(output_pass.target_fields)
        for field in self.structured_output.fields:
            unknown_producers = sorted(set(field.produced_in_passes) - known_passes)
            if unknown_producers:
                raise ValueError(
                    f"structured output field {field.name} names unknown passes: "
                    + ", ".join(unknown_producers)
                )
        unproduced = sorted(output_names - produced_fields)
        if unproduced:
            raise ValueError(
                "structured output fields are not assigned to a pass: "
                + ", ".join(unproduced)
            )
        requested_budget = sum(
            value.max_output_tokens for value in self.output_assembly.passes
        )
        if requested_budget > self.output_assembly.max_total_output_tokens:
            raise ValueError(
                "sum of per-pass output budgets exceeds max_total_output_tokens"
            )
        return self

    @property
    def pattern(self) -> str:
        return self.routing.strategy

    @property
    def capabilities(self) -> list[str]:
        return [value.capability_id for value in self.capability_latches]

    @property
    def system_instructions(self) -> str:
        sections = [
            self.instructions.objective,
            "Success criteria:\n- " + "\n- ".join(self.instructions.success_criteria),
            "Constraints:\n- " + "\n- ".join(self.instructions.constraints),
            "Stopping conditions:\n- "
            + "\n- ".join(self.instructions.stopping_conditions),
            "Narrative style:\n" + self.instructions.narrative_style,
        ]
        if self.agent_class == "experimental_specialist":
            boundary = (
                "You are the final decision agent. Emit the architecture-final decision and complete evaluation by-products."
                if self.experimental_role == "final_decision_agent"
                else "You are a specialist node. Emit useful findings and optional node-advisory decisions; do not claim the architecture-final decision."
            )
            sections.append(
                "Experimental wrapper:\n"
                "Run headlessly. Produce AgentStructuredOutput evaluation by-products. "
                "Human-facing files must be labelled presentation-only and excluded from evaluation. "
                + boundary
            )
        return "\n\n".join(sections)

    @property
    def memory(self) -> str:
        return self.memory_rules.checkpoint

    @property
    def human_review(self) -> bool:
        return self.governance.human_approval

    @property
    def max_iterations(self) -> int:
        return self.routing.max_iterations

    @property
    def evidence_required(self) -> bool:
        return self.governance.evidence_required

    @property
    def effects_allowed(self) -> bool:
        return self.governance.effects_allowed


class BlueprintPlanRequest(BaseModel):
    description: str = Field(min_length=20, max_length=4000)
    draft: dict[str, Any] | None = None
    model: Literal["gpt-5.6-luna"] = COST_OPTIMIZED_LLM_MODEL


REFINABLE_BLUEPRINT_FIELDS = {
    "name",
    "purpose",
    "static_system_scope",
    "input_contract",
    "output_contract",
    "instructions",
    "prompt_messages",
    "prompt_template",
    "state_management_description",
    "state_schema",
    "routing",
    "memory_rules",
    "governance",
    "capability_latches",
    "structured_output",
    "output_assembly",
    "retry_attempts",
    "timeout_seconds",
}


class BlueprintRefinementFinding(BaseModel):
    requirement_id: str = Field(min_length=1, max_length=120)
    statement: str = Field(min_length=3, max_length=1200)
    status: Literal["satisfied", "partial", "conflict", "unproven"]
    materiality: Literal["critical", "high", "medium", "low"]
    evidence: str = Field(default="", max_length=2000)
    proposed_correction: str = Field(default="", max_length=2000)


class BlueprintDiffChange(BaseModel):
    path: Literal[
        "name",
        "purpose",
        "static_system_scope",
        "input_contract",
        "output_contract",
        "instructions",
        "prompt_messages",
        "prompt_template",
        "state_management_description",
        "state_schema",
        "routing",
        "memory_rules",
        "governance",
        "capability_latches",
        "structured_output",
        "output_assembly",
        "retry_attempts",
        "timeout_seconds",
    ]
    rationale: str = Field(min_length=8, max_length=1200)
    replacement_json: str = Field(min_length=1, max_length=20_000)


class BlueprintDiffDocument(BaseModel):
    summary: str = Field(min_length=10, max_length=1600)
    changes: list[BlueprintDiffChange] = Field(min_length=1, max_length=12)
    acceptance_criteria: list[str] = Field(min_length=1, max_length=12)


class BlueprintRefineRequest(BaseModel):
    base: AgentBlueprint
    instruction: str = Field(min_length=10, max_length=6000)
    review_findings: list[BlueprintRefinementFinding] = Field(default_factory=list, max_length=30)
    model: Literal["gpt-5.6-luna"] = COST_OPTIMIZED_LLM_MODEL


class IdentitySection(BaseModel):
    name: str = Field(min_length=3, max_length=80)
    agent_class: Literal["static_system", "experimental_specialist"]
    version: str = Field(pattern=r"^\d+\.\d+\.\d+$")
    static_system_scope: StaticSystemScope | None = None
    purpose: str = Field(min_length=20, max_length=1200)
    model: Literal["gpt-5.6-luna"]
    input_contract: Literal[
        "PortfolioContext",
        "RiskContext",
        "OverallDefaultContext",
        "SpecialistOutputBundle",
        "AgentBlueprintContext",
        "StudioDesignContext",
    ]
    output_contract: Literal[
        "SpecialistInterpretation",
        "RiskReviewDraft",
        "EvidenceCritique",
        "CapabilityRequest",
        "AgentBlueprintProposal",
        "AgentDesignCritique",
    ]


class PromptSection(BaseModel):
    prompt_messages: list[PromptMessageSpec] = Field(min_length=1, max_length=8)
    prompt_template: PromptTemplateSpec


class StateSection(BaseModel):
    state_management_description: str = Field(min_length=20, max_length=1200)
    state_schema: list[StateFieldSpec] = Field(min_length=1, max_length=20)


class CapabilitySection(BaseModel):
    capability_latches: list[CapabilityLatchSpec] = Field(
        min_length=1, max_length=len(CAPABILITIES)
    )


class ReliabilitySection(BaseModel):
    retry_attempts: int = Field(ge=0, le=3)
    timeout_seconds: int = Field(ge=5, le=180)


class SectionPlanRequest(BaseModel):
    section: Literal[
        "identity",
        "instructions",
        "prompts",
        "state",
        "routing",
        "memory",
        "capabilities",
        "governance",
        "structured_output",
        "assembly",
        "reliability",
    ]
    description: str = Field(min_length=10, max_length=3000)
    draft: dict[str, Any]
    model: Literal["gpt-5.6-luna"] = COST_OPTIMIZED_LLM_MODEL


class AdvisorMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=4000)


class BlueprintAdviceRequest(BaseModel):
    blueprint: AgentBlueprint
    message: str = Field(min_length=3, max_length=3000)
    history: list[AdvisorMessage] = Field(default_factory=list, max_length=12)
    focus: Literal[
        "whole_agent",
        "routing",
        "memory",
        "governance",
        "state",
        "capabilities",
        "prompts",
        "structured_output",
        "assembly",
    ] = "whole_agent"
    model: Literal["gpt-5.6-luna"] = COST_OPTIMIZED_LLM_MODEL


class AdviceRecommendation(BaseModel):
    section: Literal[
        "identity",
        "instructions",
        "prompts",
        "state",
        "routing",
        "memory",
        "capabilities",
        "governance",
        "structured_output",
        "assembly",
        "reliability",
    ]
    priority: Literal["high", "medium", "low"]
    title: str = Field(min_length=3, max_length=120)
    rationale: str = Field(min_length=10, max_length=800)
    proposed_change: str = Field(min_length=10, max_length=1000)


class BlueprintAdvice(BaseModel):
    response: str = Field(min_length=20, max_length=3000)
    overall_score: int = Field(ge=0, le=100)
    strengths: list[str] = Field(min_length=1, max_length=6)
    risks: list[str] = Field(min_length=1, max_length=6)
    recommendations: list[AdviceRecommendation] = Field(min_length=1, max_length=8)
    improved_design_brief: str = Field(min_length=20, max_length=3500)


class BlueprintReviewRequest(BaseModel):
    candidate: AgentBlueprint
    baseline: AgentBlueprint | None = None
    user_requirements: list[str] = Field(default_factory=list, max_length=12)
    include_luna: bool = True
    persist: bool = True

    @field_validator("user_requirements")
    @classmethod
    def compact_requirements(cls, values: list[str]) -> list[str]:
        compact: list[str] = []
        for value in values:
            cleaned = " ".join(value.split())[:1200]
            if cleaned and cleaned not in compact:
                compact.append(cleaned)
        return compact


OBJECT_CAPABILITY_SURFACES: tuple[dict[str, Any], ...] = (
    {
        "object_kind": "portfolio",
        "label": "Portfolio",
        "terms": ("portfolio", "holding", "position", "exposure"),
        "capability_markers": ("portfolio", "exposure"),
        "examples": ("portfolio.exposure.summarize", "portfolio.normalize"),
    },
    {
        "object_kind": "mandate",
        "label": "Mandate",
        "terms": ("mandate", "ips", "covenant", "limit"),
        "capability_markers": ("mandate", "policy"),
        "examples": ("mandate.validate", "mandate.compliance.evaluate"),
    },
    {
        "object_kind": "dashboard",
        "label": "Dashboard",
        "terms": ("dashboard", "panel", "visualisation", "visualization"),
        "capability_markers": ("dashboard", "visual"),
        "examples": ("dashboard.compose", "dashboard.patch", "dashboard.render"),
    },
    {
        "object_kind": "report",
        "label": "Report",
        "terms": ("report", "brief", "memo", "dossier"),
        "capability_markers": ("report", "render"),
        "examples": ("report.compose_markdown", "report.render"),
    },
    {
        "object_kind": "scenario",
        "label": "Scenario",
        "terms": ("scenario", "stress", "shock"),
        "capability_markers": ("scenario", "stress"),
        "examples": ("scenario.parameterize", "scenario.compare"),
    },
    {
        "object_kind": "workflow",
        "label": "Workflow",
        "terms": ("workflow", "agent graph", "run plan"),
        "capability_markers": ("workflow", "graph"),
        "examples": ("workflow.compile", "workflow.replay"),
    },
    {
        "object_kind": "data_context",
        "label": "Data context",
        "terms": ("database", "dataset", "data context", "duckdb", "query"),
        "capability_markers": ("data", "query", "sql", "context"),
        "examples": ("portfolio.data_context.create", "provider.query"),
    },
)


def blueprint_object_capability_dependencies(
    blueprint: AgentBlueprint,
) -> list[dict[str, Any]]:
    """Find intended object interactions and prove their capability boundary.

    The result is a review projection over existing system objects and capability
    latches.  It deliberately does not add a second object model to AgentBlueprint.
    """

    declared = [item.capability_id for item in blueprint.capability_latches]
    design_text = " ".join(
        (
            blueprint.purpose,
            blueprint.instructions.objective,
            blueprint.instructions.narrative_style,
            *blueprint.instructions.success_criteria,
            *blueprint.instructions.constraints,
            *blueprint.instructions.stopping_conditions,
        )
    ).casefold()
    action_terms = (
        "create",
        "modify",
        "update",
        "apply",
        "use",
        "query",
        "render",
        "compose",
        "validate",
        "manage",
        "analyse",
        "analyze",
        "review",
        "interpret",
    )
    dependencies: list[dict[str, Any]] = []
    for surface in OBJECT_CAPABILITY_SURFACES:
        intended = any(
            re.search(
                rf"(?:{'|'.join(action_terms)}).{{0,90}}\b{re.escape(term)}\b|"
                rf"\b{re.escape(term)}\b.{{0,90}}(?:{'|'.join(action_terms)})",
                design_text,
            )
            for term in surface["terms"]
        )
        if not intended:
            continue
        matched = [
            capability_id
            for capability_id in declared
            if any(marker in capability_id.casefold() for marker in surface["capability_markers"])
        ]
        dependencies.append(
            {
                "object_kind": surface["object_kind"],
                "label": surface["label"],
                "status": "ready" if matched else "missing_capability",
                "declared_capability_ids": matched,
                "compatible_capability_examples": list(surface["examples"]),
                "explanation": (
                    f"The intended {surface['label']} interaction is bounded by "
                    f"{', '.join(matched)}."
                    if matched
                    else f"The design intends to work with the {surface['label']} object, "
                    "but no compatible capability is latched."
                ),
            }
        )
    return dependencies


class LunaRequirementAssessment(BaseModel):
    requirement_id: str = Field(min_length=3, max_length=120)
    status: Literal["satisfied", "partial", "conflict", "unproven", "not_applicable"]
    evidence: str = Field(min_length=3, max_length=600)
    materiality: Literal["critical", "high", "medium", "low"]
    proposed_correction: str = Field(max_length=1000)


class LunaBlueprintReview(BaseModel):
    executive_assessment: str = Field(min_length=20, max_length=1800)
    requirement_assessments: list[LunaRequirementAssessment] = Field(
        default_factory=list, max_length=24
    )
    material_findings: list[AdviceRecommendation] = Field(
        default_factory=list, max_length=8
    )
    complexity_interpretation: str = Field(min_length=20, max_length=1000)
    codex_route: Literal["read_only_review", "implementation_candidate"]
    codex_rationale: str = Field(min_length=20, max_length=1000)
    graph_route: Literal["not_required", "consider_agent_graph"]
    graph_rationale: str = Field(min_length=20, max_length=1000)
    refinement_brief: str = Field(min_length=20, max_length=3500)


class CompileRequest(BaseModel):
    blueprint: AgentBlueprint
    persist: bool = True


class RunRequest(BaseModel):
    blueprint: AgentBlueprint
    scenario: Literal["routine", "concentration", "loss", "missing"] = "concentration"
    data_mode: Literal[
        "synthetic_behavior_sample",
        "historically_calibrated_synthetic",
        "real_duckdb",
    ] = (
        "synthetic_behavior_sample"
    )
    execution_mode: Literal["deterministic", "live_llm"] = "deterministic"
    execution_model: Literal["gpt-5.6-luna"] = COST_OPTIMIZED_LLM_MODEL
    input_context: dict[str, Any] | None = None
    input_provenance: dict[str, Any] = Field(default_factory=dict)
    portfolio_id: str | None = Field(default=None, max_length=80)
    as_of: str | None = Field(default=None, max_length=32)
    datasets: list[str] = Field(default_factory=list, max_length=8)
    run_label: str | None = Field(default=None, max_length=120)
    comparison_id: str | None = Field(
        default=None, pattern=r"^comparison-[0-9]{8}T[0-9]{6}Z-[a-f0-9]{8}$"
    )
    persist_run: bool = True
    auto_approve_review: bool = False


class OutputPassRunRequest(BaseModel):
    blueprint: AgentBlueprint
    pass_id: str
    scenario: Literal["routine", "concentration", "loss", "missing"] = "concentration"
    mode: Literal["preview", "openai"] = "preview"
    current_artifact: dict[str, Any] = Field(default_factory=dict)
    model: Literal["gpt-5.6-luna"] = COST_OPTIMIZED_LLM_MODEL


def _package_version(name: str) -> str | None:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return None


def _keychain_key(*, include_value: bool = False) -> str | bool:
    environment_key = os.environ.get("OPENAI_API_KEY")
    if environment_key:
        return environment_key if include_value else True
    try:
        result = subprocess.run(
            [
                "security",
                "find-generic-password",
                "-a",
                os.environ.get("USER", ""),
                "-s",
                "servicefabric-thesis-openai",
                "-w",
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=8,
        )
    except (FileNotFoundError, subprocess.SubprocessError):
        return "" if include_value else False
    if result.returncode != 0:
        return "" if include_value else False
    value = result.stdout.strip()
    return value if include_value else bool(value)


def runtime_status() -> dict[str, Any]:
    return {
        "compiler_version": COMPILER_VERSION,
        "langgraph": {
            "available": importlib.util.find_spec("langgraph") is not None,
            "version": _package_version("langgraph"),
        },
        "openai": {
            "available": importlib.util.find_spec("openai") is not None,
            "sdk_version": _package_version("openai"),
            "key_configured": bool(_keychain_key()),
            "credential_source": "macOS Keychain or server environment",
        },
        "models": [
            {
                "id": COST_OPTIMIZED_LLM_MODEL,
                "label": "GPT-5.6 Luna · lowest-cost approved model",
            },
        ],
        "capabilities": [
            {"id": capability_id, **definition}
            for capability_id, definition in CAPABILITIES.items()
        ],
        "agent_classes": [
            {
                "id": "static_system",
                "label": "Static System Agent",
                "boundary": "Studio-scoped design work; proposals only; no portfolio context or publication.",
            },
            {
                "id": "experimental_specialist",
                "label": "Experimental Specialist Agent",
                "boundary": "Point-in-time portfolio research inside an isolated experiment.",
            },
        ],
        "foundational_system_agent": {
            "id": "system-agent-agent-studio-architect",
            "name": "Agent Studio Architect",
            "version": "0.1.0",
        },
    }


def _risk_agent_template(spec: dict[str, Any]) -> dict[str, Any]:
    capability_ids = list(dict.fromkeys([*spec["capabilities"], "evidence_critic"]))
    human_review = spec["strategy"] == "human_review"
    blueprint = AgentBlueprint.model_validate(
        {
            "name": spec["name"],
            "agent_class": "experimental_specialist",
            "experimental_role": (
                "final_decision_agent"
                if spec["role"] == "reviewer"
                else "specialist_node"
            ),
            "version": "0.1.0",
            "static_system_scope": None,
            "purpose": spec["purpose"],
            "model": COST_OPTIMIZED_LLM_MODEL,
            "input_contract": spec["input_contract"],
            "output_contract": spec["output_contract"],
            "instructions": {
                "objective": spec["objective"],
                "success_criteria": [
                    "Identify only material risk findings supported by supplied point-in-time evidence.",
                    "Explain why each finding matters to the portfolio mandate and current workflow date.",
                    "Separate deterministic observations, interpretation, uncertainty and review requirements.",
                    "Return a complete typed artifact that is ready for the next workflow component.",
                ],
                "constraints": [
                    "Use only evidence available within the supplied point-in-time context.",
                    "Do not invent metrics, events, causal explanations or missing observations.",
                    "Do not execute trades, change holdings, change cash or alter mandate thresholds.",
                    "Escalate or abstain when the evidence contract cannot support a material conclusion.",
                ],
                "stopping_conditions": [
                    "Every material finding has an evidence reference or an explicit uncertainty flag.",
                    "The Structured Output fields and quality gates are complete.",
                    "The configured revision limit has been reached or no material critique remains.",
                    "Any configured human-review boundary has been reached.",
                ],
                "narrative_style": spec["narrative_style"],
            },
            "prompt_messages": [
                {
                    "role": "system",
                    "name": "Specialist risk role",
                    "content": spec["system_message"],
                    "enabled": True,
                },
                {
                    "role": "developer",
                    "name": "Point-in-time evidence boundary",
                    "content": (
                        "Use only the supplied canonical context and latched capability results. "
                        "Distinguish observations, interpretation, uncertainty and unavailable evidence."
                    ),
                    "enabled": True,
                },
                {
                    "role": "user",
                    "name": "Workflow request",
                    "content": spec["user_message"],
                    "enabled": True,
                },
            ],
            "prompt_template": {
                "template": (
                    "Workflow date: {as_of_date}\n"
                    "Portfolio: {portfolio_name}\n"
                    "Mandate status: {mandate_status}\n"
                    "Evidence state: {evidence_state}\n\n"
                    f"Specialist task: {spec['template_task']}"
                ),
                "variables": [
                    "as_of_date",
                    "portfolio_name",
                    "mandate_status",
                    "evidence_state",
                ],
                "missing_variable_policy": "fail",
                "output_format_instruction": (
                    "Return the declared strict Structured Output with evidence-grounded findings, "
                    "an executive assessment and a bounded review recommendation."
                ),
            },
            "state_management_description": (
                "Carry the immutable input context through the graph, append capability evidence, "
                "replace the current assessment and critique, and retain review state until the workflow cycle ends."
            ),
            "state_schema": [
                {
                    "name": "context",
                    "value_type": "object",
                    "description": "Immutable canonical context supplied for the current workflow date.",
                    "source": "input",
                    "required": True,
                    "reducer": "replace",
                },
                {
                    "name": "capability_results",
                    "value_type": "array",
                    "description": "Effect-free evidence returned by the configured capability latches.",
                    "source": "capability",
                    "required": True,
                    "reducer": "append",
                },
                {
                    "name": "assessment",
                    "value_type": "string",
                    "description": "Current specialist risk assessment produced from accepted evidence.",
                    "source": "agent",
                    "required": True,
                    "reducer": "replace",
                },
                {
                    "name": "critique",
                    "value_type": "string",
                    "description": "Latest evidence and point-in-time critique of the current assessment.",
                    "source": "governance",
                    "required": True,
                    "reducer": "replace",
                },
                {
                    "name": "review",
                    "value_type": "object",
                    "description": "Human review response when the configured graph contains an interrupt.",
                    "source": "runtime",
                    "required": False,
                    "reducer": "replace",
                },
            ],
            "routing": {
                "description": spec["routing_description"],
                "strategy": spec["strategy"],
                "entry_condition": "A validated canonical input context is available for the workflow date.",
                "revision_condition": "The evidence critic finds an unsupported, stale or insufficiently qualified material claim.",
                "escalation_condition": "A mandate-relevant breach, unresolved material uncertainty or review recommendation is present.",
                "stop_condition": "The output schema passes validation and any configured review boundary is resolved.",
                "missing_evidence_route": "human_review" if human_review else "abstain",
                "max_iterations": 2,
            },
            "memory_rules": {
                "description": (
                    "Retain evidence, the current assessment, critique and review state only within the current workflow cycle."
                ),
                "scope": "workflow_cycle",
                "checkpoint": "in_memory",
                "remember_fields": [
                    "capability_results",
                    "assessment",
                    "critique",
                    "review",
                ],
                "retention_rule": "Retain checkpoints until this workflow-cycle review is complete, then keep only the typed output and run receipt.",
                "compaction_rule": "Keep the latest assessment, critique, evidence references, unresolved uncertainty and review state.",
            },
            "governance": {
                "description": (
                    "Require point-in-time evidence for material claims, prohibit portfolio effects and apply the configured review boundary."
                ),
                "evidence_required": True,
                "human_approval": human_review,
                "abstention_rule": "Abstain from a material conclusion when required evidence is missing, stale, contradictory or outside the workflow date.",
                "prohibited_actions": [
                    "Execute a trade",
                    "Modify portfolio holdings or cash",
                    "Change a mandate threshold",
                    "Invent a metric, event or evidence source",
                    "Use information unavailable at the workflow date",
                ],
                "effects_allowed": False,
            },
            "capability_latches": [
                {
                    "capability_id": capability_id,
                    "purpose": CAPABILITIES[capability_id]["description"],
                    "invocation_condition": (
                        "After drafting and before completion."
                        if capability_id == "evidence_critic"
                        else "When the validated context contains the required identifiers and this evidence is relevant to the specialist task."
                    ),
                    "output_binding": (
                        "critique" if capability_id == "evidence_critic" else f"{capability_id}_result"
                    ),
                    "required": capability_id in spec["required_capabilities"] or capability_id == "evidence_critic",
                    "failure_policy": (
                        "human_review"
                        if human_review and (capability_id in spec["required_capabilities"] or capability_id == "evidence_critic")
                        else "abstain"
                        if capability_id in spec["required_capabilities"] or capability_id == "evidence_critic"
                        else "continue_with_warning"
                    ),
                }
                for capability_id in capability_ids
            ],
            "structured_output": {
                "name": f"{spec['slug'].replace('-', '_')}_artifact",
                "description": spec["output_description"],
                "rendering_target": "mixed_artifact",
                "strict": True,
                "additional_properties": False,
                "presentation": {
                    "description": "Create a restrained specialist risk report with the conclusion first, compact evidence and an explicit review boundary.",
                    "composition": "sectioned_report",
                    "visual_hierarchy": "Lead with the executive assessment, then findings, evidence limitations and the bounded review recommendation.",
                    "tone": "Analytical, concise, evidence-led and explicit about uncertainty.",
                    "information_density": "balanced",
                    "typography_direction": "Compact editorial headings with small neutral body text.",
                    "color_direction": "Restrained navy and teal with amber reserved for material review warnings.",
                    "chart_policy": "Use a chart only when it clarifies a supplied time series, distribution, threshold or scenario comparison.",
                    "table_policy": "Use compact evidence tables with units, dates, sources and unavailable values shown explicitly.",
                    "html_policy": "Generate semantic sandboxable HTML without scripts, external resources or execution controls.",
                    "responsive_behavior": "Preserve the reading order and make wide evidence tables horizontally scrollable on narrow screens.",
                    "accessibility_requirements": [
                        "Do not rely on colour alone",
                        "Provide a text explanation for every visual",
                    ],
                    "rendering_instructions": "Render fields in schema order and keep evidence references adjacent to the claims they support.",
                },
                "fields": [
                    {
                        "name": "risk_findings",
                        "title": "Risk findings",
                        "value_type": "array",
                        "semantic_role": "evidence",
                        "description": "Material specialist findings with evidence references, mandate relevance and uncertainty.",
                        "nullable": False,
                        "format": "json",
                        "enum_values": [],
                        "nested_schema_json": "",
                        "merge_strategy": "replace",
                        "citation_required": True,
                        "validation_rule": "Every finding identifies supplied evidence or explicitly records that evidence is unavailable.",
                        "produced_in_passes": ["analyze_risk"],
                    },
                    {
                        "name": "executive_assessment",
                        "title": "Executive assessment",
                        "value_type": "string",
                        "semantic_role": "narrative",
                        "description": "Concise evidence-grounded conclusion explaining the current specialist risk state.",
                        "nullable": False,
                        "format": "markdown",
                        "enum_values": [],
                        "nested_schema_json": "",
                        "merge_strategy": "replace",
                        "citation_required": True,
                        "validation_rule": "The conclusion is consistent with the findings and separates observation from interpretation.",
                        "produced_in_passes": ["write_review"],
                    },
                    {
                        "name": "review_recommendation",
                        "title": "Review recommendation",
                        "value_type": "string",
                        "semantic_role": "recommendations",
                        "description": "Effect-free recommendation describing what a human reviewer should examine next.",
                        "nullable": False,
                        "format": "markdown",
                        "enum_values": [],
                        "nested_schema_json": "",
                        "merge_strategy": "replace",
                        "citation_required": True,
                        "validation_rule": "The recommendation never claims that a portfolio action has been executed.",
                        "produced_in_passes": ["write_review"],
                    },
                ],
                "completion_rule": "All three declared fields pass their producing pass and the final evidence consistency check.",
                "quality_gate": "All material claims are point-in-time, evidence-grounded, internally consistent and effect-free.",
                "versioning_strategy": "snapshot_and_final",
            },
            "output_assembly": {
                "description": "Build the specialist artifact in one evidence-analysis pass followed by one bounded synthesis pass.",
                "strategy": "sequential_section_build",
                "passes": [
                    {
                        "pass_id": "analyze_risk",
                        "title": "Analyse specialist risk",
                        "objective": "Evaluate the supplied context and capability evidence to produce the material specialist findings.",
                        "target_fields": ["risk_findings"],
                        "operation": "replace",
                        "context_policy": "full_context",
                        "depends_on": [],
                        "max_output_tokens": 2400,
                        "quality_gate": "Every finding is material, point-in-time and linked to supplied evidence.",
                        "human_review_after": False,
                    },
                    {
                        "pass_id": "write_review",
                        "title": "Write specialist review",
                        "objective": "Synthesize accepted findings into an executive assessment and an effect-free review recommendation.",
                        "target_fields": ["executive_assessment", "review_recommendation"],
                        "operation": "replace",
                        "context_policy": "selected_prior_fields",
                        "depends_on": ["analyze_risk"],
                        "max_output_tokens": 2400,
                        "quality_gate": "The narrative and recommendation are consistent with accepted findings and disclose uncertainty.",
                        "human_review_after": human_review,
                    },
                ],
                "carry_forward_rule": "Carry accepted findings forward unchanged and provide only relevant evidence and selected prior fields to synthesis.",
                "finalization_rule": "Validate the complete schema, cross-check claims against evidence and surface the configured review boundary.",
                "max_total_output_tokens": 5200,
                "stop_on_failure": True,
                "human_review_between_passes": False,
            },
            "retry_attempts": 1,
            "timeout_seconds": 45,
        }
    )
    return {
        "id": f"risk-template-{spec['slug']}",
        "name": spec["name"],
        "agent_class": "experimental_specialist",
        "version": "0.1.0",
        "framework": "langgraph",
        "engine": "langgraph",
        "role": spec["role"],
        "experimental_role": blueprint.experimental_role,
        "input": spec["input_contract"],
        "output": spec["output_contract"],
        "instructions": spec["objective"],
        "capabilities": capability_ids,
        "blueprint": blueprint.model_dump(mode="json"),
        "built_in": True,
        "category": spec["category"],
    }


STRICT_RISK_REVIEW_FIELDS = (
    "conclusion",
    "largest_exposures",
    "mandate_comparison",
    "why_concentration_matters",
    "evidence_references",
    "missing_information_uncertainty",
    "suggested_human_review_actions",
)


def concentration_and_mandate_monitor_blueprint() -> AgentBlueprint:
    """Return the reviewed Markdown-first concentration candidate.

    This remains an Agent Studio recipe rather than a Registry admission.  The
    only calculation grant is the existing canonical exposure adapter.
    """

    return AgentBlueprint.model_validate(
        {
            "name": "concentration_and_mandate_monitor",
            "agent_class": "experimental_specialist",
            "version": "0.2.0",
            "purpose": "For one portfolio and one workflow date, review point-in-time exposure, cash and applicable mandate-limit evidence to identify matters requiring human attention without changing the portfolio.",
            "model": COST_OPTIMIZED_LLM_MODEL,
            "input_contract": "PortfolioContext",
            "output_contract": "RiskReviewDraft",
            "instructions": {
                "objective": "Produce a concise, evidence-grounded RiskReviewDraft for one canonical portfolio and one workflow date, focused on supported concentration, cash and mandate-limit conditions requiring human review.",
                "success_criteria": [
                    "Use portfolio_exposure for supported weights, largest exposures, concentration measures and mandate headroom.",
                    "Use risk_metrics only when a relevant deterministic MetricPack value is explicitly available for the workflow date.",
                    "Compare exposure with an applicable mandate limit only when it is supplied, valid and point-in-time.",
                    "Support every material claim with supplied evidence or an explicit uncertainty marker.",
                    "Provide bounded human-review checks only; never execute or authorize a portfolio action.",
                ],
                "constraints": [
                    "Use only the canonical PortfolioContext and authorized risk-capability results.",
                    "Do not invent mandate limits, metrics, calculations, events or evidence references.",
                    "Do not calculate unsupported values outside registered capabilities.",
                    "Do not trade, rebalance, modify holdings or cash, change mandate thresholds, write externally or communicate externally.",
                    "This experimental specialist cannot invoke system-design capabilities or claim that a separate Codex review occurred.",
                ],
                "stopping_conditions": [
                    "All material claims have evidence references or explicit unavailable-evidence or uncertainty markers.",
                    "Largest-exposure evidence and mandate comparison are complete or explicitly unavailable.",
                    "The evidence critic has run after the assembled draft and after any bounded material revision.",
                    "The strict Markdown output validates and the mandatory human-review boundary is reached.",
                ],
                "narrative_style": "Analytical, concise and evidence-led. State facts before interpretation, keep uncertainty explicit, and end at a human decision boundary.",
            },
            "prompt_messages": [
                {"role": "system", "name": "specialist_role", "content": "You are Concentration and Mandate Monitor, an Experimental Specialist operating on one canonical PortfolioContext and one workflow date. Produce a non-executing RiskReviewDraft for human review only.", "enabled": True},
                {"role": "developer", "name": "authority_and_evidence_boundary", "content": "Use only supplied point-in-time context and authorized risk-capability results. Separate observations, interpretation, uncertainty, evidence references and human-review checks. Portfolio effects are prohibited.", "enabled": True},
                {"role": "developer", "name": "abstention_rule", "content": "If exposure evidence is unavailable, stale, contradictory or outside the workflow date, abstain from the affected conclusion. If an applicable mandate limit is unavailable, do not assert compliance or breach; mark the comparison unavailable and route it to human review.", "enabled": True},
                {"role": "developer", "name": "revision_and_critique_rule", "content": "After the initial review sections are assembled, invoke evidence_critic. If one bounded material revision is made, invoke evidence_critic again after that revision and before finalization.", "enabled": True},
                {"role": "developer", "name": "codex_boundary", "content": "A separate approved orchestration step must perform read-only Codex review before save. Absence of its receipt blocks save; this agent neither performs nor represents that review as complete.", "enabled": True},
                {"role": "user", "name": "workflow_task", "content": "Return only the complete strict Markdown Structured Output in the declared renderer contract.", "enabled": True},
            ],
            "prompt_template": {
                "template": "Workflow date: {as_of_date}\nPortfolio: {portfolio_name}\nPortfolio context: {portfolio_context}\nCapability evidence: {capability_results}\nEvidence state: {evidence_state}\nCurrent draft: {draft_output}\nLatest critique: {critique}\nReview state: {review_state}\n\nTask: Determine whether concentration, cash or mandate-limit information requires human attention. Return only the strict Markdown Structured Output.",
                "variables": ["as_of_date", "portfolio_name", "portfolio_context", "capability_results", "evidence_state", "draft_output", "critique", "review_state"],
                "missing_variable_policy": "fail",
                "output_format_instruction": "Render exactly the declared fields in schema order as Markdown. Use the declared section titles. Render largest exposures as a Markdown table with units and dates, mandate comparison as a labeled table, evidence and uncertainty as compact lists or tables, and human-review actions as checkbox-free questions. Do not add sections, links, HTML, scripts, controls or portfolio-action language.",
            },
            "state_management_description": "Carry the immutable PortfolioContext and workflow date through the workflow, append effect-free capability results, retain the latest evidence critique and review state, and expose only the final typed RiskReviewDraft to the next workflow component.",
            "state_schema": [
                {"name": "context", "value_type": "object", "description": "Immutable canonical PortfolioContext for one portfolio and workflow date.", "source": "input", "required": True, "reducer": "replace"},
                {"name": "capability_results", "value_type": "array", "description": "Effect-free authorized capability results with point-in-time status.", "source": "capability", "required": True, "reducer": "append"},
                {"name": "evidence_state", "value_type": "string", "description": "Current evidence sufficiency status including missing, stale or contradictory evidence.", "source": "governance", "required": True, "reducer": "replace"},
                {"name": "draft_output", "value_type": "object", "description": "Current partially or fully assembled RiskReviewDraft artifact.", "source": "agent", "required": True, "reducer": "replace"},
                {"name": "critique", "value_type": "object", "description": "Latest evidence-critic findings for unsupported or insufficiently qualified claims.", "source": "governance", "required": True, "reducer": "replace"},
                {"name": "review_state", "value_type": "object", "description": "Human review, unresolved questions and external read-only Codex receipt status only.", "source": "runtime", "required": True, "reducer": "replace"},
            ],
            "routing": {
                "description": "Validate one canonical point-in-time context, invoke only relevant risk capabilities, assemble the review, critique material claims, revise once if needed, and stop at mandatory human review. Save is blocked until a separate read-only Codex review receipt is supplied.",
                "strategy": "human_review",
                "entry_condition": "A canonical PortfolioContext is available for exactly one portfolio and one workflow date.",
                "revision_condition": "evidence_critic identifies an unsupported, stale, contradictory or insufficiently qualified material claim and one bounded revision remains; invoke it again after revision.",
                "escalation_condition": "Any concern, unavailable applicable limit, unresolved uncertainty, failed strict validation or missing Codex review receipt is present.",
                "stop_condition": "The strict output validates, all claims are supported or qualified, an external read-only Codex receipt is present for save, and the artifact reaches mandatory human review.",
                "missing_evidence_route": "abstain",
                "max_iterations": 2,
            },
            "memory_rules": {
                "description": "Retain only current-workflow evidence, draft sections, critique and human-review state; never create cross-workflow portfolio memory.",
                "scope": "workflow_cycle", "checkpoint": "in_memory",
                "remember_fields": ["capability_results", "evidence_state", "draft_output", "critique", "review_state"],
                "retention_rule": "Retain checkpoints until human review and separate pre-save Codex review are complete; then retain only the typed output and run receipt.",
                "compaction_rule": "Keep the latest capability evidence summary, accepted claims, unresolved uncertainty, critique outcome, Codex receipt status and review status.",
            },
            "governance": {
                "description": "Operate as an effect-free risk-review specialist. Require point-in-time evidence, abstain when required evidence is unavailable, require separate read-only Codex review before save, and always stop at human approval.",
                "evidence_required": True, "human_approval": True,
                "abstention_rule": "Abstain from a material conclusion when exposure evidence or the applicable mandate limit is unavailable, stale, contradictory or outside the workflow date. Label the affected comparison unavailable and identify the human review needed.",
                "prohibited_actions": ["Execute, recommend as executed, or simulate a trade.", "Rebalance or modify portfolio holdings.", "Modify portfolio cash.", "Change, infer or override a mandate threshold.", "Invent a metric, limit, event, observation or evidence reference.", "Use information unavailable at the workflow date.", "Write externally or communicate externally.", "Claim compliance or breach when the applicable mandate limit is unavailable.", "Claim that read-only Codex review occurred.", "Save or publish without an external approved Codex review receipt and human approval."],
                "effects_allowed": False,
            },
            "capability_latches": [
                {"capability_id": "portfolio_exposure", "purpose": "Calculate supported position weights, largest exposures, concentration measures and mandate headroom from supplied point-in-time context.", "invocation_condition": "Invoke when the validated PortfolioContext contains identifiers and holdings or exposure inputs required by the registered capability.", "output_binding": "portfolio_exposure_result", "required": True, "failure_policy": "human_review"},
                {"capability_id": "risk_metrics", "purpose": "Retrieve deterministic MetricPack values relevant to concentration, cash or mandate review without inventing calculations.", "invocation_condition": "Invoke only when PortfolioContext explicitly identifies a relevant deterministic risk metric and its availability for the workflow date.", "output_binding": "risk_metrics_result", "required": False, "failure_policy": "continue_with_warning"},
                {"capability_id": "evidence_critic", "purpose": "Check whether material narrative claims, comparisons and interpretations are supported by supplied point-in-time evidence.", "invocation_condition": "Invoke after initial sections and after every bounded material revision, at most once per assembly state and at least once before finalization.", "output_binding": "evidence_critique_result", "required": True, "failure_policy": "human_review"},
            ],
            "structured_output": {
                "name": "concentration_and_mandate_monitor_artifact", "description": "A concise, effect-free Markdown RiskReviewDraft identifying supported concentration, cash and mandate-limit concerns for one portfolio and workflow date.", "rendering_target": "markdown_document", "strict": True, "additional_properties": False,
                "presentation": {"description": "Concrete Markdown renderer contract for a sectioned, evidence-led risk review.", "composition": "sectioned_report", "visual_hierarchy": "Render conclusion first, then exposures, mandate comparison, significance, limitations, evidence and human-review boundary in schema order.", "tone": "Concise, analytical, evidence-led and explicit about uncertainty.", "information_density": "balanced", "typography_direction": "Use level-two Markdown headings matching declared field titles, short paragraphs and compact tables with units and dates.", "color_direction": "No color semantics; convey status with text labels only.", "chart_policy": "Do not render charts; use a table unless a deterministic chart is explicitly supplied and materially required.", "table_policy": "Render largest exposures as a compact Markdown table and structured comparison and evidence as labeled Markdown tables or lists.", "html_policy": "Markdown only. Do not emit HTML, scripts, external resources, forms, buttons or execution controls.", "responsive_behavior": "Keep tables compact and preserve readable column labels.", "accessibility_requirements": ["Do not rely on color alone.", "Use descriptive Markdown table headers and explicit units.", "Provide text explanations for every warning or comparison.", "Keep evidence references readable and adjacent to claims."], "rendering_instructions": "Emit only the seven declared sections in schema order, with no title or metadata outside them. Empty arrays render as 'None identified' only when validation permits. Unavailable comparisons use explicit status text."},
                "fields": [
                    {"name": "conclusion", "title": "One-sentence conclusion", "value_type": "string", "semantic_role": "introduction", "description": "One evidence-grounded sentence stating whether supported evidence requires human attention.", "nullable": False, "format": "markdown", "enum_values": [], "nested_schema_json": "", "merge_strategy": "replace", "citation_required": True, "validation_rule": "Exactly one sentence with evidence or explicit unavailable evidence; never asserts unsupported breach or compliance.", "produced_in_passes": ["state_facts_and_exposures", "synthesize_review"]},
                    {"name": "largest_exposures", "title": "Largest exposures", "value_type": "array", "semantic_role": "table", "description": "Compact rows for largest supported exposures, including identifiers, weights, date and evidence.", "nullable": False, "format": "json", "enum_values": [], "nested_schema_json": "{\"items\":{\"additionalProperties\":false,\"properties\":{\"as_of_date\":{\"type\":\"string\"},\"cash_relevance\":{\"type\":[\"string\",\"null\"]},\"concentration_measure\":{\"type\":[\"number\",\"string\",\"null\"]},\"evidence_reference\":{\"type\":\"string\"},\"position_identifier\":{\"type\":\"string\"},\"weight\":{\"type\":[\"number\",\"null\"]}},\"required\":[\"position_identifier\",\"weight\",\"as_of_date\",\"evidence_reference\"],\"type\":\"object\"},\"type\":\"array\"}", "merge_strategy": "replace", "citation_required": True, "validation_rule": "Rows come only from portfolio_exposure or supplied PortfolioContext evidence and use null or unavailable rather than invented values.", "produced_in_passes": ["state_facts_and_exposures"]},
                    {"name": "mandate_comparison", "title": "Largest exposure versus applicable mandate limit", "value_type": "object", "semantic_role": "table", "description": "Point-in-time comparison of largest relevant exposure with applicable supplied mandate limit.", "nullable": False, "format": "json", "enum_values": [], "nested_schema_json": "{\"additionalProperties\":false,\"properties\":{\"applicable_limit\":{\"type\":[\"number\",\"string\",\"null\"]},\"comparison_status\":{\"enum\":[\"within_limit\",\"exceeds_limit\",\"comparison_unavailable\",\"contradictory_evidence\"],\"type\":\"string\"},\"evidence_references\":{\"items\":{\"type\":\"string\"},\"type\":\"array\"},\"exposure_value\":{\"type\":[\"number\",\"string\",\"null\"]},\"headroom\":{\"type\":[\"number\",\"string\",\"null\"]},\"uncertainty\":{\"type\":[\"string\",\"null\"]}},\"required\":[\"exposure_value\",\"applicable_limit\",\"comparison_status\",\"evidence_references\"],\"type\":\"object\"}", "merge_strategy": "replace", "citation_required": True, "validation_rule": "Use within_limit or exceeds_limit only when exposure and limit are supplied, valid and point-in-time; otherwise explicitly state why comparison is unavailable.", "produced_in_passes": ["state_facts_and_exposures", "synthesize_review"]},
                    {"name": "why_concentration_matters", "title": "Why the concentration matters", "value_type": "string", "semantic_role": "narrative", "description": "Short explanation of mandate relevance without unsupported causal claims.", "nullable": False, "format": "markdown", "enum_values": [], "nested_schema_json": "", "merge_strategy": "replace", "citation_required": True, "validation_rule": "Separates observation from interpretation and never implies an executed action.", "produced_in_passes": ["interpret_findings", "synthesize_review"]},
                    {"name": "evidence_references", "title": "Evidence references", "value_type": "array", "semantic_role": "evidence", "description": "References supporting material claims.", "nullable": False, "format": "json", "enum_values": [], "nested_schema_json": "{\"items\":{\"additionalProperties\":false,\"properties\":{\"as_of_date\":{\"type\":\"string\"},\"reference_id\":{\"type\":\"string\"},\"source\":{\"type\":\"string\"},\"supports\":{\"type\":\"string\"}},\"required\":[\"reference_id\",\"source\",\"as_of_date\",\"supports\"],\"type\":\"object\"},\"type\":\"array\"}", "merge_strategy": "replace", "citation_required": True, "validation_rule": "Each reference identifies a supplied source and maps to a material claim.", "produced_in_passes": ["state_facts_and_exposures", "interpret_findings", "synthesize_review"]},
                    {"name": "missing_information_uncertainty", "title": "Missing information and uncertainty", "value_type": "array", "semantic_role": "methodology", "description": "Explicit material evidence limitations and their handling.", "nullable": False, "format": "json", "enum_values": [], "nested_schema_json": "{\"items\":{\"additionalProperties\":false,\"properties\":{\"handling\":{\"type\":\"string\"},\"impact\":{\"type\":\"string\"},\"issue\":{\"type\":\"string\"}},\"required\":[\"issue\",\"impact\",\"handling\"],\"type\":\"object\"},\"type\":\"array\"}", "merge_strategy": "replace", "citation_required": False, "validation_rule": "Record every material limitation and state abstention or human-review handling.", "produced_in_passes": ["state_facts_and_exposures", "interpret_findings", "synthesize_review"]},
                    {"name": "suggested_human_review_actions", "title": "Suggested human review actions", "value_type": "array", "semantic_role": "recommendations", "description": "Bounded effect-free questions or checks for a human reviewer.", "nullable": False, "format": "markdown", "enum_values": [], "nested_schema_json": "{\"items\":{\"type\":\"string\"},\"type\":\"array\"}", "merge_strategy": "replace", "citation_required": False, "validation_rule": "Every item is a human review check or question, never an executed or authorized action.", "produced_in_passes": ["synthesize_review"]},
                ],
                "completion_rule": "All seven fields are populated, each material claim has a reference or uncertainty, the evidence critic passes or disclosures route to human review, and an external read-only Codex review receipt is present before save.", "quality_gate": "The artifact is concise, point-in-time, evidence-grounded, abstention-compliant and effect-free.", "versioning_strategy": "snapshot_and_final",
            },
            "output_assembly": {
                "description": "Populate the RiskReviewDraft through factual exposure evidence, supported interpretation, synthesis, then critique and finalization. A material revision is followed by evidence_critic before finalization.", "strategy": "sequential_section_build", "carry_forward_rule": "Carry forward accepted facts, comparison status, evidence and uncertainty unchanged. After every bounded material revision, evidence_critic must be re-invoked.", "finalization_rule": "Run evidence_critic, apply at most one bounded revision, re-run evidence_critic, validate declared fields and Markdown rendering, require external read-only Codex review before save, and stop for mandatory human approval.", "max_total_output_tokens": 4600, "stop_on_failure": True, "human_review_between_passes": False,
                "passes": [
                    {"pass_id": "state_facts_and_exposures", "title": "Establish factual exposure evidence", "objective": "Use PortfolioContext and authorized results to populate factual exposure, cash and mandate evidence without unsupported interpretation.", "target_fields": ["conclusion", "largest_exposures", "mandate_comparison", "evidence_references", "missing_information_uncertainty"], "operation": "replace", "context_policy": "evidence_subset", "depends_on": [], "max_output_tokens": 1500, "quality_gate": "Values are sourced, point-in-time and capability-supported; unavailable or contradictory evidence is explicit.", "human_review_after": False},
                    {"pass_id": "interpret_findings", "title": "Explain supported significance", "objective": "Explain supported concentration or cash observations while preserving the fact-versus-interpretation boundary.", "target_fields": ["why_concentration_matters", "evidence_references", "missing_information_uncertainty"], "operation": "replace", "context_policy": "selected_prior_fields", "depends_on": ["state_facts_and_exposures"], "max_output_tokens": 900, "quality_gate": "Interpretation is limited to supplied evidence and retains limitations.", "human_review_after": False},
                    {"pass_id": "synthesize_review", "title": "Synthesize the human-review draft", "objective": "Produce concise conclusion, mandate comparison, limitations, evidence references and bounded review checks.", "target_fields": ["conclusion", "mandate_comparison", "why_concentration_matters", "evidence_references", "missing_information_uncertainty", "suggested_human_review_actions"], "operation": "replace", "context_policy": "selected_prior_fields", "depends_on": ["state_facts_and_exposures", "interpret_findings"], "max_output_tokens": 1300, "quality_gate": "Elements are consistent, evidence-referenced and stopped at human review.", "human_review_after": True},
                    {"pass_id": "evidence_critique_and_finalize", "title": "Critique and finalize", "objective": "Invoke evidence_critic against the assembled artifact, revise at most once, invoke it again after revision, and validate strict Markdown and effect-free governance.", "target_fields": list(STRICT_RISK_REVIEW_FIELDS), "operation": "merge", "context_policy": "prior_output_summary", "depends_on": ["synthesize_review"], "max_output_tokens": 900, "quality_gate": "No unsupported material claim remains, or every issue is disclosed and routed to human review; save remains blocked until external receipt exists.", "human_review_after": True},
                ],
            },
            "retry_attempts": 1,
            "timeout_seconds": 45,
        }
    )


def risk_agent_templates() -> list[dict[str, Any]]:
    specs = [
        {
            "slug": "daily-portfolio-risk-reviewer",
            "name": "Daily Portfolio Risk Reviewer",
            "category": "Holistic review",
            "role": "reviewer",
            "input_contract": "OverallDefaultContext",
            "output_contract": "RiskReviewDraft",
            "purpose": "Interpret the complete deterministic portfolio context and prepare the daily evidence-grounded risk review for human approval.",
            "objective": "Produce a holistic daily review of market, exposure, scenario, event and mandate-relevant portfolio risk.",
            "narrative_style": "Lead with the portfolio risk conclusion, explain material changes and evidence, disclose uncertainty and end at a human decision boundary.",
            "system_message": "You are the senior daily portfolio risk reviewer in a historical point-in-time workflow.",
            "user_message": "Prepare the complete daily portfolio risk review for the current workflow date.",
            "template_task": "Synthesize the full deterministic context into the daily risk review.",
            "routing_description": "Gather all required evidence, draft the review, critique material claims, revise once and interrupt for human approval.",
            "strategy": "human_review",
            "capabilities": ["market_data", "risk_metrics", "portfolio_exposure", "scenario_stress", "event_retrieval"],
            "required_capabilities": ["risk_metrics", "portfolio_exposure"],
            "output_description": "A complete daily portfolio risk review combining material findings, narrative interpretation and an explicit human-review recommendation.",
        },
        {
            "slug": "market-liquidity-risk-analyst",
            "name": "Market and Liquidity Risk Analyst",
            "category": "Market risk",
            "role": "interpreter",
            "input_contract": "OverallDefaultContext",
            "output_contract": "SpecialistInterpretation",
            "purpose": "Interpret market moves, volatility, drawdown, liquidity proxies and exposure interactions using point-in-time evidence.",
            "objective": "Explain the portfolio's material market and liquidity risk state without recalculating unprovided metrics.",
            "narrative_style": "Write a compact market-risk note that separates price observations, metric changes, exposure implications and uncertainty.",
            "system_message": "You are a market and liquidity risk specialist operating inside a historical portfolio replay.",
            "user_message": "Assess market and liquidity risk for the current portfolio workflow date.",
            "template_task": "Interpret market observations, risk metrics and exposure interactions.",
            "routing_description": "Gather market and metric evidence, draft the specialist interpretation, critique its claims and revise when required.",
            "strategy": "reflection",
            "capabilities": ["market_data", "risk_metrics", "portfolio_exposure"],
            "required_capabilities": ["market_data", "risk_metrics"],
            "output_description": "A specialist market and liquidity interpretation with supported findings, a concise assessment and bounded review guidance.",
        },
        {
            "slug": "concentration-mandate-monitor",
            "name": "Concentration and Mandate Monitor",
            "category": "Mandate risk",
            "role": "reviewer",
            "input_contract": "PortfolioContext",
            "output_contract": "RiskReviewDraft",
            "purpose": "Evaluate portfolio concentration, cash and mandate-relevant exposure conditions and stop at a human review boundary for breaches.",
            "objective": "Identify material concentration and mandate exceptions from deterministic holdings and MetricPack evidence.",
            "narrative_style": "State the exception first, quantify the relevant exposure, cite the mandate context and avoid proposing an executed trade.",
            "system_message": "You are a concentration and mandate-control reviewer with no authority to change the portfolio.",
            "user_message": "Review concentration and mandate conditions for the current portfolio context.",
            "template_task": "Evaluate concentration, cash and mandate-relevant exposure conditions.",
            "routing_description": "Calculate exposure evidence, interpret threshold relevance, critique the finding and interrupt when a material exception exists.",
            "strategy": "human_review",
            "capabilities": ["portfolio_exposure", "risk_metrics"],
            "required_capabilities": ["portfolio_exposure"],
            "output_description": "A mandate-focused exception review with exposure findings, evidence-grounded interpretation and a human-review recommendation.",
        },
        {
            "slug": "scenario-stress-analyst",
            "name": "Scenario Stress Analyst",
            "category": "Scenario risk",
            "role": "interpreter",
            "input_contract": "OverallDefaultContext",
            "output_contract": "SpecialistInterpretation",
            "purpose": "Interpret bounded deterministic stress results and explain the exposures, assumptions and uncertainties driving scenario sensitivity.",
            "objective": "Produce an evidence-grounded specialist interpretation of deterministic portfolio stress scenarios.",
            "narrative_style": "Explain the scenario, dominant exposures, nonlinear or concentrated sensitivities and limitations in compact analytical prose.",
            "system_message": "You are a deterministic scenario-stress specialist and may not create unapproved shocks or mutate holdings.",
            "user_message": "Interpret the configured stress scenario for the current workflow date.",
            "template_task": "Explain deterministic scenario results and their exposure drivers.",
            "routing_description": "Run the approved stress capability, collect exposure and metric evidence, draft the interpretation and revise unsupported claims.",
            "strategy": "reflection",
            "capabilities": ["scenario_stress", "portfolio_exposure", "risk_metrics"],
            "required_capabilities": ["scenario_stress", "portfolio_exposure"],
            "output_description": "A deterministic scenario-risk interpretation containing material sensitivities, assumptions, evidence and effect-free review guidance.",
        },
        {
            "slug": "fundamental-event-deterioration-watcher",
            "name": "Fundamental and Event Deterioration Watcher",
            "category": "Fundamental risk",
            "role": "interpreter",
            "input_contract": "OverallDefaultContext",
            "output_contract": "SpecialistInterpretation",
            "purpose": "Detect mandate-relevant fundamental deterioration and governed events without using information unavailable at the workflow date.",
            "objective": "Explain material point-in-time fundamental changes and events that may alter the portfolio risk interpretation.",
            "narrative_style": "Use a chronological evidence-led narrative that distinguishes reported fundamentals, governed events and interpretation.",
            "system_message": "You are a point-in-time fundamental and event-risk specialist using Compustat and governed event evidence.",
            "user_message": "Assess fundamental and event deterioration for the current holdings and workflow date.",
            "template_task": "Interpret eligible fundamental changes and governed events for current holdings.",
            "routing_description": "Retrieve eligible fundamentals and events, draft the specialist interpretation, critique point-in-time eligibility and revise once.",
            "strategy": "reflection",
            "capabilities": ["fundamental_change", "event_retrieval", "market_data"],
            "required_capabilities": ["fundamental_change", "event_retrieval"],
            "output_description": "A point-in-time fundamental and event-risk interpretation with eligible findings, uncertainties and bounded follow-up guidance.",
        },
        {
            "slug": "evidence-point-in-time-critic",
            "name": "Evidence and Point-in-Time Critic",
            "category": "Governance",
            "role": "critic",
            "input_contract": "SpecialistOutputBundle",
            "output_contract": "EvidenceCritique",
            "purpose": "Audit specialist outputs for unsupported claims, invalid references, look-ahead leakage and missing uncertainty disclosures.",
            "objective": "Produce a strict evidence and point-in-time critique of the supplied specialist output bundle.",
            "narrative_style": "Write concise audit findings that identify the claim, evidence defect, consequence and required correction.",
            "system_message": "You are the independent evidence and point-in-time critic for portfolio risk agent outputs.",
            "user_message": "Audit the supplied specialist outputs before synthesis or human review.",
            "template_task": "Test every material specialist claim for evidence support and point-in-time eligibility.",
            "routing_description": "Inspect the bundle, retrieve governed event eligibility when needed, issue the critique and abstain if the audit context is incomplete.",
            "strategy": "direct",
            "capabilities": ["event_retrieval"],
            "required_capabilities": ["evidence_critic"],
            "output_description": "A strict evidence critique listing unsupported claims, point-in-time defects, uncertainty omissions and required corrections.",
        },
    ]
    templates = [_risk_agent_template(spec) for spec in specs]
    # Preserve the existing template position and browser recipe identifier while
    # replacing the provisional 0.1.0 monitor with its reviewed 0.2.0 candidate.
    templates[2] = {
        **templates[2],
        "name": "Concentration and Mandate Monitor",
        "version": "0.2.0",
        "blueprint": concentration_and_mandate_monitor_blueprint().model_dump(
            mode="json"
        ),
    }
    return templates


def agent_studio_architect_template() -> dict[str, Any]:
    """Return the first Registry-ready Static System Agent recipe.

    It uses the same compiler contract as experimental agents but cannot consume
    portfolio context, use analytical capabilities, publish, register, or write code.
    """

    payload = json.loads(json.dumps(risk_agent_templates()[0]["blueprint"]))
    payload.update(
        {
            "name": "Agent Studio Architect",
            "agent_class": "static_system",
            "version": "0.1.0",
            "static_system_scope": {
                "owning_studio": "agent",
                "supported_intents": [
                    "explain",
                    "teach",
                    "show_examples",
                    "clarify",
                    "assess_feasibility",
                    "plan",
                    "critique",
                    "synthesize",
                ],
                "codebase_scope": [
                    "apps/portfolio-risk-workbench/labs/agent_studio.py",
                    "apps/portfolio-risk-workbench/labs/index.html",
                    "apps/portfolio-risk-workbench/labs/labs.js",
                    "packages/risk_agents",
                    "tests/application/test_agent_studio.py",
                    "codex/skills/build-servicefabric-agent",
                ],
                "skill_ids": ["build-servicefabric-agent"],
                "knowledge_sources": [
                    "AGENTS.md",
                    "docs/workplans/current.md",
                    "docs/workplans/platform-development/studio-foundation-3-agent-studio.md",
                    "docs/architecture/platform-operating-zones.md",
                    "docs/workplans/platform-development/studio-codex-gateway.md",
                ],
                "proposal_only": True,
            },
            "purpose": (
                "Help a user define, challenge and refine governed agent blueprints, then prepare "
                "an approved candidate brief for Studio-Codex without writing code or publishing an agent."
            ),
            "input_contract": "AgentBlueprintContext",
            "output_contract": "AgentBlueprintProposal",
        }
    )
    payload.pop("experimental_role", None)
    payload.pop("experimental_wrapper", None)
    payload["instructions"] = {
        "objective": (
            "Turn an intended job into a clear, class-correct and testable agent proposal by finding "
            "reusable definitions first, resolving only material uncertainties and exposing every design trade-off."
        ),
        "success_criteria": [
            "Classify the agent as Static System or Experimental Specialist before selecting contracts.",
            "Search for reusable agents, skills, contracts and capability packs before proposing new code.",
            "Explain alternatives, recommend one design and preserve unresolved questions explicitly.",
            "Produce a typed blueprint proposal, evaluation plan and bounded Studio-Codex build brief.",
        ],
        "constraints": [
            "Use only supplied Registry metadata, repository knowledge sources and approved examples.",
            "Never write code, register, activate, merge or publish an agent.",
            "Never weaken effects, evidence, point-in-time or human-review policies.",
            "Do not invent capabilities or canonical contracts; record missing infrastructure as a dependency.",
            "Keep the user-facing discussion concise and ask only high-impact questions.",
        ],
        "stopping_conditions": [
            "The intended outcome, class, scope, contracts, capabilities, authority and tests are coherent.",
            "All material open questions are resolved or explicitly retained for human review.",
            "The user approves the proposal for candidate implementation or returns it to design.",
        ],
        "narrative_style": (
            "Lead with the recommendation, explain why it fits, show meaningful alternatives and avoid "
            "restating configuration that adds no decision value."
        ),
    }
    payload["prompt_messages"] = [
        {
            "role": "system",
            "name": "Agent Studio architecture role",
            "content": (
                "You are the versioned Agent Studio Architect. You design agent proposals and teach the "
                "relevant concepts, but you cannot finalize, register, activate, publish or implement them."
            ),
            "enabled": True,
        },
        {
            "role": "developer",
            "name": "ServiceFabric architecture boundary",
            "content": (
                "Apply the Static System versus Experimental Specialist boundary, reuse existing contracts, "
                "make codebase and skill scope visible, and end with a human-reviewed candidate brief."
            ),
            "enabled": True,
        },
        {
            "role": "user",
            "name": "Design request",
            "content": "Help me design, critique or improve the described agent and its evaluation plan.",
            "enabled": True,
        },
    ]
    payload["prompt_template"] = {
        "template": (
            "Design intent: {design_intent}\nAgent class: {agent_class}\nStudio scope: {studio_scope}\n"
            "Registry matches: {registry_matches}\nOpen questions: {open_questions}\n\n"
            "Recommend the smallest coherent agent definition and a bounded candidate-build brief."
        ),
        "variables": [
            "design_intent",
            "agent_class",
            "studio_scope",
            "registry_matches",
            "open_questions",
        ],
        "missing_variable_policy": "fail",
        "output_format_instruction": (
            "Return a strict AgentBlueprintProposal containing the recommendation, alternatives, proposed "
            "blueprint, evaluation plan, dependencies, open questions and Studio-Codex decision."
        ),
    }
    payload["state_management_description"] = (
        "Keep the supplied design context immutable; append Registry findings and alternatives; replace the "
        "current proposal after critique; retain open questions, consensus and review state for the design session."
    )
    payload["state_schema"] = [
        {"name": "design_context", "value_type": "object", "description": "Immutable design request, policies and supplied codebase context.", "source": "input", "required": True, "reducer": "replace"},
        {"name": "registry_matches", "value_type": "array", "description": "Reusable agent definitions, contracts, skills and examples found in the Registry.", "source": "capability", "required": True, "reducer": "append"},
        {"name": "open_questions", "value_type": "array", "description": "Material uncertainties that still change the proposed architecture.", "source": "agent", "required": True, "reducer": "replace"},
        {"name": "alternatives", "value_type": "array", "description": "Meaningful design alternatives and their explicit trade-offs.", "source": "agent", "required": True, "reducer": "replace"},
        {"name": "blueprint_proposal", "value_type": "object", "description": "Current non-final typed proposal for the requested agent.", "source": "agent", "required": True, "reducer": "replace"},
        {"name": "review", "value_type": "object", "description": "Human approval, revision request or return-to-design decision.", "source": "runtime", "required": False, "reducer": "replace"},
    ]
    payload["routing"] = {
        "description": "Search for reuse, clarify material gaps, propose alternatives, validate the candidate and stop for explicit human review.",
        "strategy": "human_review",
        "entry_condition": "A design intent and owning Studio are supplied.",
        "revision_condition": "Validation fails or the user identifies an unresolved design requirement.",
        "escalation_condition": "The request would weaken policy, cross codebase scope or require an unknown contract or capability.",
        "stop_condition": "The proposal validates and the human approves candidate implementation or returns it to design.",
        "missing_evidence_route": "human_review",
        "max_iterations": 3,
    }
    payload["memory_rules"] = {
        "description": "Retain the evolving design discussion and decisions within the current Studio design session.",
        "scope": "session",
        "checkpoint": "in_memory",
        "remember_fields": ["registry_matches", "open_questions", "alternatives", "blueprint_proposal", "review"],
        "retention_rule": "Keep the session until the proposal is approved, rejected or explicitly discarded; persist only approved proposal records.",
        "compaction_rule": "Preserve accepted requirements, rejected alternatives, open questions and the latest validated proposal.",
    }
    payload["governance"] = {
        "description": "The agent may prepare design artifacts only; a human controls approval and Studio-Codex candidate implementation.",
        "evidence_required": False,
        "human_approval": True,
        "abstention_rule": "Stop and request human direction when class, authority, contract or codebase scope cannot be resolved safely.",
        "prohibited_actions": [
            "Write or modify repository files",
            "Register, activate or publish an agent",
            "Start or merge a Studio-Codex worktree",
            "Invent canonical contracts or capabilities",
            "Weaken organization policy or human review",
        ],
        "effects_allowed": False,
    }
    payload["capability_latches"] = [
        {
            "capability_id": capability_id,
            "purpose": CAPABILITIES[capability_id]["description"],
            "invocation_condition": condition,
            "output_binding": binding,
            "required": capability_id == "agent_blueprint_validate",
            "failure_policy": "human_review" if capability_id == "agent_blueprint_validate" else "continue_with_warning",
        }
        for capability_id, condition, binding in (
            ("registry_agent_search", "Before proposing a new agent or implementation.", "registry_matches"),
            ("agent_blueprint_examples", "When examples or design techniques would resolve a material choice.", "design_examples"),
            ("agent_blueprint_validate", "After each materially revised candidate proposal.", "validation_result"),
            ("studio_codex_brief_prepare", "Only after the user approves a validated candidate for implementation.", "codex_brief"),
        )
    ]
    payload["structured_output"].update(
        {
            "name": "agent_blueprint_proposal",
            "description": "A non-final, reviewable agent design proposal and bounded candidate implementation brief.",
            "rendering_target": "mixed_artifact",
            "fields": [
                {"name": "design_summary", "title": "Recommended design", "value_type": "string", "semantic_role": "narrative", "description": "Concise outcome-led recommendation and why it fits the intended job.", "nullable": False, "format": "markdown", "enum_values": [], "nested_schema_json": "", "merge_strategy": "replace", "citation_required": False, "validation_rule": "States the agent class, outcome, scope and authority without unnecessary repetition.", "produced_in_passes": ["analyze_design"]},
                {"name": "alternatives", "title": "Alternatives", "value_type": "array", "semantic_role": "results", "description": "Meaningful alternative designs with explicit trade-offs and rejection reasons.", "nullable": False, "format": "json", "enum_values": [], "nested_schema_json": "", "merge_strategy": "replace", "citation_required": False, "validation_rule": "Includes only alternatives that materially change cost, scope, authority or evaluation.", "produced_in_passes": ["analyze_design"]},
                {"name": "blueprint_proposal", "title": "Blueprint proposal", "value_type": "object", "semantic_role": "metadata", "description": "Strict non-final candidate agent blueprint for validation and human revision.", "nullable": False, "format": "json", "enum_values": [], "nested_schema_json": "", "merge_strategy": "replace", "citation_required": False, "validation_rule": "Validates against the selected agent-class contract and references only known dependencies.", "produced_in_passes": ["prepare_candidate"]},
                {"name": "evaluation_plan", "title": "Evaluation plan", "value_type": "array", "semantic_role": "methodology", "description": "Representative, failure and adversarial fixtures with release thresholds.", "nullable": False, "format": "json", "enum_values": [], "nested_schema_json": "", "merge_strategy": "replace", "citation_required": False, "validation_rule": "Covers normal behavior, failure boundaries and policy resistance within a declared budget.", "produced_in_passes": ["prepare_candidate"]},
                {"name": "open_questions", "title": "Open questions", "value_type": "array", "semantic_role": "recommendations", "description": "Only unresolved questions that can materially change the candidate design.", "nullable": False, "format": "json", "enum_values": [], "nested_schema_json": "", "merge_strategy": "replace", "citation_required": False, "validation_rule": "Empty only when every material design decision is resolved or explicitly accepted.", "produced_in_passes": ["prepare_candidate"]},
                {"name": "codex_decision", "title": "Studio-Codex readiness", "value_type": "object", "semantic_role": "metadata", "description": "Readiness, bounded paths, required skill, tests and human approval state for candidate implementation.", "nullable": False, "format": "json", "enum_values": [], "nested_schema_json": "", "merge_strategy": "replace", "citation_required": False, "validation_rule": "Cannot be ready while validation fails, open questions remain or human approval is absent.", "produced_in_passes": ["prepare_candidate"]},
            ],
            "completion_rule": "The recommendation and alternatives are clear, the blueprint validates, tests are specified and Studio-Codex readiness is honest.",
            "quality_gate": "The proposal is class-correct, reuses existing infrastructure, preserves policy and remains non-executing until human approval.",
        }
    )
    payload["output_assembly"] = {
        "description": "Analyse the requested job and reusable infrastructure first, then prepare one validated candidate package for human review.",
        "strategy": "sequential_section_build",
        "passes": [
            {"pass_id": "analyze_design", "title": "Analyse the design", "objective": "Classify the job, search for reuse and compare only meaningful alternatives.", "target_fields": ["design_summary", "alternatives"], "operation": "replace", "context_policy": "full_context", "depends_on": [], "max_output_tokens": 1800, "quality_gate": "The recommendation follows from the intended outcome and explicit infrastructure constraints.", "human_review_after": False},
            {"pass_id": "prepare_candidate", "title": "Prepare the candidate", "objective": "Build and validate the non-final blueprint, evaluation fixtures, open questions and bounded Studio-Codex decision.", "target_fields": ["blueprint_proposal", "evaluation_plan", "open_questions", "codex_decision"], "operation": "replace", "context_policy": "selected_prior_fields", "depends_on": ["analyze_design"], "max_output_tokens": 4200, "quality_gate": "The candidate is schema-valid, policy-preserving, testable and explicit about unresolved dependencies.", "human_review_after": True},
        ],
        "carry_forward_rule": "Carry accepted requirements, Registry matches, alternatives and unresolved questions without replaying the full conversation.",
        "finalization_rule": "Validate the candidate and expose a human decision: revise, reject or approve for a bounded Studio-Codex build.",
        "max_total_output_tokens": 6400,
        "stop_on_failure": True,
        "human_review_between_passes": False,
    }
    payload["retry_attempts"] = 1
    payload["timeout_seconds"] = 60
    blueprint = AgentBlueprint.model_validate(payload)
    return {
        "id": "system-agent-agent-studio-architect",
        "name": blueprint.name,
        "agent_class": blueprint.agent_class,
        "version": blueprint.version,
        "framework": "langgraph",
        "engine": "langgraph",
        "role": "architect",
        "input": blueprint.input_contract,
        "output": blueprint.output_contract,
        "instructions": blueprint.instructions.objective,
        "capabilities": blueprint.capabilities,
        "blueprint": blueprint.model_dump(mode="json"),
        "built_in": True,
        "category": "Static System Agent",
    }


def agent_templates() -> list[dict[str, Any]]:
    return [agent_studio_architect_template(), *risk_agent_templates()]


def _strict_schema(model_type: type[BaseModel] = AgentBlueprint) -> dict[str, Any]:
    schema = model_type.model_json_schema()

    def normalize(value: Any) -> None:
        if isinstance(value, dict):
            value.pop("default", None)
            if value.get("type") == "object" and isinstance(
                value.get("properties"), dict
            ):
                value["additionalProperties"] = False
                value["required"] = list(value["properties"])
            for child in value.values():
                normalize(child)
        elif isinstance(value, list):
            for child in value:
                normalize(child)

    normalize(schema)
    return schema


def _cohere_blueprint_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Resolve cross-field invariants that JSON Schema cannot express."""
    routing = payload.get("routing")
    governance = payload.get("governance")
    if isinstance(routing, dict) and isinstance(governance, dict):
        if governance.get("human_approval"):
            routing["strategy"] = "human_review"
        elif routing.get("strategy") == "human_review":
            governance["human_approval"] = True
        if (
            governance.get("evidence_required")
            and payload.get("agent_class", "experimental_specialist")
            == "experimental_specialist"
        ):
            latches = payload.get("capability_latches")
            if isinstance(latches, list) and not any(
                item.get("capability_id") == "evidence_critic"
                for item in latches
                if isinstance(item, dict)
            ):
                latches.append(
                    {
                        "capability_id": "evidence_critic",
                        "purpose": "Check material claims against supplied evidence.",
                        "invocation_condition": (
                            "After every narrative draft and before human review."
                        ),
                        "output_binding": "critique",
                        "required": True,
                        "failure_policy": "human_review",
                    }
                )
    memory = payload.get("memory_rules")
    state_schema = payload.get("state_schema")
    if isinstance(memory, dict) and isinstance(state_schema, list):
        names = {
            item.get("name")
            for item in state_schema
            if isinstance(item, dict) and isinstance(item.get("name"), str)
        }
        remember_fields = memory.get("remember_fields")
        if isinstance(remember_fields, list):
            memory["remember_fields"] = [
                value for value in remember_fields if value in names
            ]
    return payload


def plan_blueprint(request: BlueprintPlanRequest) -> dict[str, Any]:
    api_key = _keychain_key(include_value=True)
    if not api_key:
        raise RuntimeError(
            "OpenAI credential is unavailable in the server environment or Keychain"
        )
    from openai import OpenAI

    draft = request.draft or {}
    architect = AgentBlueprint.model_validate(agent_studio_architect_template()["blueprint"])
    started = time.perf_counter()
    client = OpenAI(api_key=str(api_key))
    response = client.responses.create(
        model=COST_OPTIMIZED_LLM_MODEL,
        store=False,
        tools=[],
        input=[
            {
                "role": "system",
                "content": [
                    {
                        "type": "input_text",
                        "text": (
                            "You are an agent-architecture planner. Convert the user's "
                            "description and partial draft into the supplied recursive "
                            "AgentBlueprint schema. Describe the objective, success bar, "
                            "ordered prompt messages, PromptTemplate, state fields, "
                            "routing conditions, memory rules, capability latches, and "
                            "governance in operational language. Fully design the "
                            "Structured Output: field types, semantic roles, validation, "
                            "merge behavior and producing passes. Build a bounded multi-pass "
                            "assembly plan so long artifacts can be populated section by "
                            "section across repeated runs of the same agent. Select only capability "
                            "IDs present in the schema context. Preserve canonical "
                            "agent-class contracts. Static System Agents receive Studio design "
                            "context, expose their owning Studio, skills, knowledge and bounded "
                            "codebase scope, use only system design capabilities, and produce "
                            "non-final proposals. Experimental Specialist Agents receive canonical "
                            "point-in-time portfolio-risk context and use only risk capabilities. "
                            "Never mix the two classes. Use lower_snake_case "
                            "for state names and bindings. Prefer human review for "
                            "portfolio decisions, require evidence, and never allow "
                            "portfolio effects. Return configuration only, never Python."
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
                                "description": request.description,
                                "partial_blueprint": draft,
                                "available_capabilities": CAPABILITIES,
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
                "name": "agent_blueprint",
                "strict": True,
                "schema": _strict_schema(AgentBlueprint),
            }
        },
        max_output_tokens=10000,
    )
    blueprint = AgentBlueprint.model_validate(
        _cohere_blueprint_payload(json.loads(response.output_text))
    )
    elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
    usage = getattr(response, "usage", None)
    return {
        "blueprint": blueprint.model_dump(mode="json"),
        "receipt": {
            "provider": "openai_responses",
            "model": getattr(response, "model", request.model),
            "response_id": getattr(response, "id", None),
            "input_tokens": int(getattr(usage, "input_tokens", 0) or 0),
            "output_tokens": int(getattr(usage, "output_tokens", 0) or 0),
            "elapsed_ms": elapsed_ms,
            "store": False,
            "tools": [],
            "system_agent_id": "system-agent-agent-studio-architect",
            "system_agent_version": architect.version,
            "system_agent_class": architect.agent_class,
            "instruction_digest": hashlib.sha256(
                architect.system_instructions.encode()
            ).hexdigest()[:16],
        },
    }


def _validation_summary(error: ValidationError) -> str:
    findings = []
    for item in error.errors(include_url=False)[:6]:
        location = ".".join(str(part) for part in item.get("loc", ())) or "blueprint"
        findings.append(f"{location}: {item.get('msg', 'invalid value')}")
    return "; ".join(findings)


def _normalize_generated_string_bounds(
    payload: dict[str, Any],
    error: ValidationError,
    changed_fields: set[str],
) -> list[dict[str, Any]]:
    """Bound only overlong strings generated inside explicitly changed fields."""

    normalizations: list[dict[str, Any]] = []
    for item in error.errors(include_url=False):
        if item.get("type") != "string_too_long":
            continue
        location = tuple(item.get("loc", ()))
        if not location or str(location[0]) not in changed_fields:
            continue
        maximum = item.get("ctx", {}).get("max_length")
        if not isinstance(maximum, int) or maximum < 4:
            continue
        parent: Any = payload
        try:
            for part in location[:-1]:
                parent = parent[part]
            leaf = location[-1]
            original = parent[leaf]
        except (KeyError, IndexError, TypeError):
            continue
        if not isinstance(original, str) or len(original) <= maximum:
            continue
        bounded = original[: maximum - 3] + "..."
        parent[leaf] = bounded
        normalizations.append(
            {
                "path": ".".join(str(part) for part in location),
                "reason": "Generated text exceeded the canonical field contract.",
                "original_length": len(original),
                "final_length": len(bounded),
                "max_length": maximum,
            }
        )
    return normalizations


def apply_blueprint_diff(
    base: AgentBlueprint, document: BlueprintDiffDocument
) -> tuple[AgentBlueprint, list[dict[str, Any]], list[dict[str, Any]]]:
    """Apply explicit top-level replacements while preserving every other field."""

    payload = base.model_dump(mode="json")
    seen: set[str] = set()
    applied: list[dict[str, Any]] = []
    for change in document.changes:
        if change.path not in REFINABLE_BLUEPRINT_FIELDS:
            raise ValueError(f"blueprint field is not refinable: {change.path}")
        if change.path in seen:
            raise ValueError(f"blueprint diff repeats field: {change.path}")
        seen.add(change.path)
        try:
            replacement = json.loads(change.replacement_json)
        except json.JSONDecodeError as error:
            raise ValueError(
                f"replacement for {change.path} is not valid JSON: {error.msg}"
            ) from error
        before = payload.get(change.path)
        payload[change.path] = replacement
        applied.append(
            {
                "path": change.path,
                "rationale": change.rationale,
                "before_digest": hashlib.sha256(
                    json.dumps(before, sort_keys=True).encode()
                ).hexdigest()[:16],
                "after_digest": hashlib.sha256(
                    json.dumps(replacement, sort_keys=True).encode()
                ).hexdigest()[:16],
            }
        )
    coherent = _cohere_blueprint_payload(payload)
    normalizations: list[dict[str, Any]] = []
    try:
        blueprint = AgentBlueprint.model_validate(coherent)
    except ValidationError as error:
        normalizations = _normalize_generated_string_bounds(coherent, error, seen)
        if not normalizations:
            raise ValueError(
                "The proposed diff does not form a valid agent blueprint. "
                + _validation_summary(error)
            ) from error
        try:
            blueprint = AgentBlueprint.model_validate(coherent)
        except ValidationError as repaired_error:
            raise ValueError(
                "The proposed diff does not form a valid agent blueprint after bounded "
                "generated-text normalization. " + _validation_summary(repaired_error)
            ) from repaired_error
    return blueprint, applied, normalizations


def refine_blueprint(request: BlueprintRefineRequest) -> dict[str, Any]:
    """Ask Luna for a minimal diff, then validate the reconstructed blueprint."""

    api_key = _keychain_key(include_value=True)
    if not api_key:
        raise RuntimeError(
            "OpenAI credential is unavailable in the server environment or Keychain"
        )
    from openai import OpenAI

    started = time.perf_counter()
    client = OpenAI(api_key=str(api_key))
    response = client.responses.create(
        model=COST_OPTIMIZED_LLM_MODEL,
        store=False,
        tools=[],
        input=[
            {
                "role": "system",
                "content": [{
                    "type": "input_text",
                    "text": (
                        "You refine an existing ServiceFabric AgentBlueprint by producing "
                        "a minimal diff document. Never rewrite the complete blueprint. "
                        "Change only top-level fields required by the instruction or material "
                        "review findings. Preserve agent_class, version and model. Each "
                        "replacement_json value must be valid JSON for exactly that field. "
                        "Keep prompt_template.output_format_instruction at or below 1200 characters. "
                        "Keep all governance and class boundaries coherent. Return the diff "
                        "document only; do not return Python or a complete blueprint."
                    ),
                }],
            },
            {
                "role": "user",
                "content": [{
                    "type": "input_text",
                    "text": json.dumps(
                        {
                            "instruction": request.instruction,
                            "review_findings": [
                                item.model_dump(mode="json")
                                for item in request.review_findings
                            ],
                            "current_blueprint": request.base.model_dump(mode="json"),
                            "allowed_fields": sorted(REFINABLE_BLUEPRINT_FIELDS),
                            "available_capabilities": CAPABILITIES,
                        },
                        sort_keys=True,
                    ),
                }],
            },
        ],
        text={
            "format": {
                "type": "json_schema",
                "name": "agent_blueprint_diff",
                "strict": True,
                "schema": _strict_schema(BlueprintDiffDocument),
            }
        },
        max_output_tokens=7000,
    )
    try:
        document = BlueprintDiffDocument.model_validate_json(response.output_text)
        blueprint, applied, normalizations = apply_blueprint_diff(request.base, document)
    except ValidationError as error:
        raise ValueError(
            "Luna returned an invalid refinement diff. " + _validation_summary(error)
        ) from error
    elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
    usage = getattr(response, "usage", None)
    return {
        "blueprint": blueprint.model_dump(mode="json"),
        "diff": {
            **document.model_dump(mode="json"),
            "applied_changes": applied,
            "normalizations": normalizations,
            "base_digest": hashlib.sha256(
                json.dumps(request.base.model_dump(mode="json"), sort_keys=True).encode()
            ).hexdigest()[:16],
            "result_digest": hashlib.sha256(
                json.dumps(blueprint.model_dump(mode="json"), sort_keys=True).encode()
            ).hexdigest()[:16],
        },
        "receipt": {
            "provider": "openai_responses",
            "model": getattr(response, "model", request.model),
            "response_id": getattr(response, "id", None),
            "input_tokens": int(getattr(usage, "input_tokens", 0) or 0),
            "output_tokens": int(getattr(usage, "output_tokens", 0) or 0),
            "elapsed_ms": elapsed_ms,
            "store": False,
            "tools": [],
            "operation": "blueprint_diff_refinement",
        },
    }


def plan_blueprint_section(request: SectionPlanRequest) -> dict[str, Any]:
    api_key = _keychain_key(include_value=True)
    if not api_key:
        raise RuntimeError("OpenAI credential is unavailable")
    from openai import OpenAI

    section_models: dict[str, type[BaseModel]] = {
        "identity": IdentitySection,
        "instructions": InstructionRules,
        "prompts": PromptSection,
        "state": StateSection,
        "routing": RoutingRules,
        "memory": MemoryRules,
        "capabilities": CapabilitySection,
        "governance": GovernanceRules,
        "structured_output": StructuredOutputSpec,
        "assembly": OutputAssemblyPlan,
        "reliability": ReliabilitySection,
    }
    model_type = section_models[request.section]
    started = time.perf_counter()
    client = OpenAI(api_key=str(api_key))
    response = client.responses.create(
        model=COST_OPTIMIZED_LLM_MODEL,
        store=False,
        tools=[],
        input=[
            {
                "role": "system",
                "content": [
                    {
                        "type": "input_text",
                        "text": (
                            "You are editing exactly one section of an agent blueprint. "
                            "Transform the user's plain-language intent into the supplied "
                            "strict section schema. Use the current draft only as context. "
                            "Do not rewrite unrelated sections. Prefer operational, "
                            "explainable rules; preserve canonical portfolio contracts, "
                            "point-in-time evidence boundaries, human review for decisions, "
                            "and effects_allowed=false. For Structured Output, translate "
                            "the requested appearance into presentation rules and start "
                            "with only the fields actually needed. Return configuration only."
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
                                "target_section": request.section,
                                "section_description": request.description,
                                "current_blueprint": request.draft,
                                "available_capabilities": CAPABILITIES,
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
                "name": f"agent_{request.section}_section",
                "strict": True,
                "schema": _strict_schema(model_type),
            }
        },
        max_output_tokens=(7000 if request.section == "structured_output" else 4500),
    )
    section_value = model_type.model_validate(json.loads(response.output_text))
    usage = getattr(response, "usage", None)
    return {
        "section": request.section,
        "value": section_value.model_dump(mode="json"),
        "receipt": {
            "provider": "openai_responses",
            "model": getattr(response, "model", request.model),
            "response_id": getattr(response, "id", None),
            "input_tokens": int(getattr(usage, "input_tokens", 0) or 0),
            "output_tokens": int(getattr(usage, "output_tokens", 0) or 0),
            "elapsed_ms": round((time.perf_counter() - started) * 1000, 2),
            "store": False,
            "tools": [],
        },
    }


def advise_blueprint(request: BlueprintAdviceRequest) -> dict[str, Any]:
    api_key = _keychain_key(include_value=True)
    if not api_key:
        raise RuntimeError(
            "OpenAI credential is unavailable in the server environment or Keychain"
        )
    from openai import OpenAI

    started = time.perf_counter()
    client = OpenAI(api_key=str(api_key))
    architect = agent_studio_architect_template()["blueprint"]
    architect_blueprint = AgentBlueprint.model_validate(architect)
    history = [
        {"role": item.role, "content": [{"type": "input_text", "text": item.content}]}
        for item in request.history[-8:]
    ]
    response = client.responses.create(
        model=COST_OPTIMIZED_LLM_MODEL,
        store=False,
        tools=[],
        input=[
            {
                "role": "system",
                "content": [
                    {
                        "type": "input_text",
                        "text": architect_blueprint.system_instructions,
                    }
                ],
            },
            *history,
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": json.dumps(
                            {
                                "question": request.message,
                                "focus": request.focus,
                                "current_blueprint": request.blueprint.model_dump(mode="json"),
                                "available_capabilities": CAPABILITIES,
                                "architect_scope": architect_blueprint.static_system_scope.model_dump(mode="json"),
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
                "name": "blueprint_advice",
                "strict": True,
                "schema": _strict_schema(BlueprintAdvice),
            }
        },
        max_output_tokens=3200,
    )
    advice_payload = json.loads(response.output_text)
    advice = BlueprintAdvice.model_validate(advice_payload)
    usage = getattr(response, "usage", None)
    return {
        "advice": advice.model_dump(mode="json"),
        "receipt": {
            "provider": "openai_responses",
            "model": getattr(response, "model", request.model),
            "response_id": getattr(response, "id", None),
            "input_tokens": int(getattr(usage, "input_tokens", 0) or 0),
            "output_tokens": int(getattr(usage, "output_tokens", 0) or 0),
            "elapsed_ms": round((time.perf_counter() - started) * 1000, 2),
            "store": False,
            "tools": [],
            "system_agent_id": "system-agent-agent-studio-architect",
            "system_agent_version": architect_blueprint.version,
            "system_agent_class": architect_blueprint.agent_class,
            "instruction_digest": hashlib.sha256(
                architect_blueprint.system_instructions.encode()
            ).hexdigest()[:16],
        },
    }


def _blueprint_digest(blueprint: AgentBlueprint) -> str:
    return hashlib.sha256(
        json.dumps(
            blueprint.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()


def _agent_identity(blueprint: AgentBlueprint) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", blueprint.name.casefold()).strip("-")[:64]
    return f"agent-{slug or 'untitled'}"


def _requirement(
    requirement_id: str,
    statement: str,
    source: str,
    status: str,
    materiality: str,
    evidence: str,
    proposed_correction: str = "",
    section: str = "governance",
) -> dict[str, Any]:
    return {
        "requirement_id": requirement_id,
        "statement": statement,
        "source": source,
        "status": status,
        "materiality": materiality,
        "evidence": evidence,
        "proposed_correction": proposed_correction,
        "section": section,
    }


def blueprint_requirement_ledger(
    blueprint: AgentBlueprint, user_requirements: list[str] | None = None
) -> list[dict[str, Any]]:
    """Project explicit user and system requirements without creating a new domain object."""

    capabilities = set(blueprint.capabilities)
    ledger = [
        _requirement(
            "system-effects-disabled",
            "The agent cannot create portfolio or external effects.",
            "system_policy",
            "satisfied" if not blueprint.governance.effects_allowed else "conflict",
            "critical",
            "governance.effects_allowed is fixed to false."
            if not blueprint.governance.effects_allowed
            else "The blueprint attempts to enable effects.",
            "Set effects_allowed=false and retain the prohibited-action policy.",
        ),
        _requirement(
            "system-class-contract",
            "The agent class, input, output and capability grants use one compatible boundary.",
            "system_contract",
            "satisfied",
            "critical",
            f"{blueprint.agent_class} accepts {blueprint.input_contract}, returns {blueprint.output_contract}, and passed AgentBlueprint validation.",
            section="identity",
        ),
        _requirement(
            "system-human-boundary",
            "Consequential conclusions stop at an explicit human-review boundary.",
            "system_policy",
            "satisfied" if blueprint.governance.human_approval else "partial",
            "critical" if blueprint.agent_class == "experimental_specialist" else "high",
            "Human review is compiled into routing."
            if blueprint.governance.human_approval
            else "This blueprint does not request a human interrupt.",
            "Enable human approval and human-review routing when the output can influence a decision.",
            "routing",
        ),
        _requirement(
            "system-evidence-critic",
            "Evidence-required analytical output is independently checked before completion.",
            "system_policy",
            "satisfied"
            if not blueprint.governance.evidence_required
            or blueprint.agent_class == "static_system"
            or "evidence_critic" in capabilities
            else "conflict",
            "high",
            "Evidence policy and the capability latch are coherent."
            if "evidence_critic" in capabilities
            else "Evidence is not required for this class or no evidence critic is needed.",
            "Latch evidence_critic before human review.",
            "capabilities",
        ),
        _requirement(
            "system-bounded-termination",
            "Every graph has a bounded stop condition, iteration ceiling and failure route.",
            "system_contract",
            "satisfied",
            "high",
            f"The graph stops under an explicit condition with at most {blueprint.routing.max_iterations} iteration(s) and {blueprint.retry_attempts} retrie(s).",
            section="routing",
        ),
        _requirement(
            "system-output-contract",
            "Every declared output field is typed, produced by a named pass and validated.",
            "system_contract",
            "satisfied",
            "high",
            f"{len(blueprint.structured_output.fields)} field(s) are assigned across {len(blueprint.output_assembly.passes)} bounded pass(es).",
            section="structured_output",
        ),
        _requirement(
            "system-point-in-time",
            "Experimental analysis must retain a point-in-time evidence boundary.",
            "system_policy",
            "satisfied"
            if blueprint.agent_class == "static_system"
            or any(
                "point-in-time" in value.casefold() or "as-of" in value.casefold()
                for value in (
                    blueprint.purpose,
                    blueprint.instructions.objective,
                    *blueprint.instructions.constraints,
                )
            )
            else "partial",
            "critical" if blueprint.agent_class == "experimental_specialist" else "low",
            "The purpose, objective or constraints explicitly state the temporal boundary."
            if blueprint.agent_class == "experimental_specialist"
            else "Static System Agents do not consume portfolio observations.",
            "Add an explicit as-of and eligibility rule to the objective and constraints.",
            "instructions",
        ),
    ]
    for dependency in blueprint_object_capability_dependencies(blueprint):
        ready = dependency["status"] == "ready"
        examples = ", ".join(dependency["compatible_capability_examples"])
        ledger.append(
            _requirement(
                f"system-object-{dependency['object_kind']}-capability",
                (
                    f"The agent can work with the {dependency['label']} system object "
                    "through an explicit compatible capability."
                ),
                "system_object_binding",
                "satisfied" if ready else "partial",
                "high",
                dependency["explanation"],
                (
                    "Reuse an admitted compatible capability first. If none meets the "
                    f"contract, send this dependency to Studio-Codex; candidates include {examples}."
                    if not ready
                    else ""
                ),
                "capabilities",
            )
        )
    for statement in user_requirements or []:
        normalized = " ".join(statement.split())
        stable_id = hashlib.sha256(normalized.casefold().encode()).hexdigest()[:12]
        ledger.append(
            _requirement(
                f"user-{stable_id}",
                normalized,
                "user",
                "unproven",
                "high",
                "Requires semantic review against the current configuration.",
                "Clarify or revise the candidate if Luna cannot identify direct configuration evidence.",
                "whole_agent",
            )
        )
    return ledger


def blueprint_complexity_assessment(
    blueprint: AgentBlueprint, compilation: dict[str, Any] | None = None
) -> dict[str, Any]:
    graph = (compilation or {}).get("graph") or graph_spec(blueprint)
    factors: list[dict[str, Any]] = []

    def add(label: str, points: int, detail: str) -> None:
        if points:
            factors.append({"label": label, "points": points, "detail": detail})

    add(
        "Graph routing",
        {"direct": 4, "tool_loop": 12, "reflection": 18, "human_review": 16}[
            blueprint.routing.strategy
        ],
        f"{len(graph['nodes'])} nodes, {len(graph['edges'])} edges, {blueprint.routing.strategy.replace('_', ' ')} routing.",
    )
    add(
        "State",
        min(18, len(blueprint.state_schema) * 2),
        f"{len(blueprint.state_schema)} typed state fields.",
    )
    add(
        "Capabilities",
        min(18, len(blueprint.capability_latches) * 3),
        f"{len(blueprint.capability_latches)} capability latches with independent failure policies.",
    )
    add(
        "Output assembly",
        min(
            24,
            len(blueprint.output_assembly.passes) * 4
            + len(blueprint.structured_output.fields) * 2,
        ),
        f"{len(blueprint.structured_output.fields)} output fields across {len(blueprint.output_assembly.passes)} passes.",
    )
    add(
        "Memory and iteration",
        (6 if blueprint.memory_rules.scope != "none" else 0)
        + max(0, blueprint.routing.max_iterations - 1) * 3,
        f"{blueprint.memory_rules.scope.replace('_', ' ')} memory and {blueprint.routing.max_iterations} maximum iterations.",
    )
    if blueprint.agent_class == "static_system" and blueprint.static_system_scope:
        add(
            "Codebase scope",
            min(12, len(blueprint.static_system_scope.codebase_scope) * 2),
            f"{len(blueprint.static_system_scope.codebase_scope)} bounded codebase paths.",
        )
    score = min(100, sum(item["points"] for item in factors))
    band = "simple" if score < 30 else "moderate" if score < 55 else "high" if score < 75 else "engineering"
    graph_candidate = (
        len(blueprint.capability_latches) >= 5
        and len(blueprint.output_assembly.passes) >= 3
        and blueprint.routing.strategy in {"tool_loop", "reflection", "human_review"}
    )
    return {
        "score": score,
        "band": band,
        "factors": factors,
        "node_count": len(graph["nodes"]),
        "edge_count": len(graph["edges"]),
        "codex_review": "required_read_only",
        # Configuration review never grants an implementation turn.  A later,
        # separately approved Studio-Codex proposal owns that transition.
        "codex_route": "read_only_review",
        "graph_route": "consider_agent_graph" if graph_candidate else "not_required",
        "explanation": (
            "The score describes configuration and graph coordination burden, not analytical quality. "
            "Every material candidate receives a read-only Codex review before save."
        ),
    }


def _blueprint_comparison(
    baseline: AgentBlueprint | None, candidate: AgentBlueprint
) -> dict[str, Any]:
    candidate_payload = candidate.model_dump(mode="json")
    baseline_payload = baseline.model_dump(mode="json") if baseline else {}
    sections = [
        "experimental_role",
        "experimental_wrapper",
        "purpose",
        "input_contract",
        "output_contract",
        "instructions",
        "prompt_messages",
        "prompt_template",
        "state_schema",
        "routing",
        "memory_rules",
        "capability_latches",
        "governance",
        "structured_output",
        "output_assembly",
        "retry_attempts",
        "timeout_seconds",
    ]
    changed = []
    for section in sections:
        before = baseline_payload.get(section)
        after = candidate_payload.get(section)
        if before != after:
            changed.append(
                {
                    "section": section,
                    "before_digest": hashlib.sha256(
                        json.dumps(before, sort_keys=True, default=str).encode()
                    ).hexdigest()[:12]
                    if baseline
                    else None,
                    "after_digest": hashlib.sha256(
                        json.dumps(after, sort_keys=True, default=str).encode()
                    ).hexdigest()[:12],
                }
            )
    return {
        "baseline_digest": _blueprint_digest(baseline) if baseline else None,
        "candidate_digest": _blueprint_digest(candidate),
        "changed_sections": changed,
        "changed_section_count": len(changed),
    }


def _blueprint_review_projection(blueprint: AgentBlueprint) -> dict[str, Any]:
    """Keep Luna review compact; Codex can inspect full files in the repository."""

    return {
        "identity": {
            "name": blueprint.name,
            "agent_class": blueprint.agent_class,
            "version": blueprint.version,
            "purpose": blueprint.purpose,
            "input_contract": blueprint.input_contract,
            "output_contract": blueprint.output_contract,
            "experimental_role": blueprint.experimental_role,
            "experimental_wrapper": (
                None
                if blueprint.experimental_wrapper is None
                else blueprint.experimental_wrapper.model_dump(mode="json")
            ),
        },
        "instructions": blueprint.instructions.model_dump(mode="json"),
        "prompt": {
            "messages": [
                {
                    "role": item.role,
                    "name": item.name,
                    "enabled": item.enabled,
                    "content": item.content[:600],
                }
                for item in blueprint.prompt_messages
            ],
            "template": blueprint.prompt_template.template[:1200],
            "variables": blueprint.prompt_template.variables,
        },
        "state": [item.model_dump(mode="json") for item in blueprint.state_schema],
        "routing": blueprint.routing.model_dump(mode="json"),
        "memory": blueprint.memory_rules.model_dump(mode="json"),
        "governance": blueprint.governance.model_dump(mode="json"),
        "capabilities": [
            item.model_dump(mode="json") for item in blueprint.capability_latches
        ],
        "output": {
            "name": blueprint.structured_output.name,
            "rendering_target": blueprint.structured_output.rendering_target,
            "fields": [
                {
                    "name": item.name,
                    "title": item.title,
                    "semantic_role": item.semantic_role,
                    "validation_rule": item.validation_rule,
                    "produced_in_passes": item.produced_in_passes,
                }
                for item in blueprint.structured_output.fields
            ],
            "passes": [
                item.model_dump(mode="json")
                for item in blueprint.output_assembly.passes
            ],
            "quality_gate": blueprint.structured_output.quality_gate,
        },
    }


def _luna_review_blueprint(
    blueprint: AgentBlueprint,
    ledger: list[dict[str, Any]],
    comparison: dict[str, Any],
    complexity: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    api_key = _keychain_key(include_value=True)
    if not api_key:
        raise RuntimeError("OpenAI credential is unavailable")
    from openai import OpenAI

    started = time.perf_counter()
    architect = AgentBlueprint.model_validate(
        agent_studio_architect_template()["blueprint"]
    )
    client = OpenAI(api_key=str(api_key))
    response = client.responses.create(
        model=COST_OPTIMIZED_LLM_MODEL,
        store=False,
        tools=[],
        input=[
            {
                "role": "system",
                "content": [
                    {
                        "type": "input_text",
                        "text": (
                            "Review one AgentBlueprint against the supplied user and system requirement ledger. "
                            "Be concise and material: do not repeat satisfied configuration unless it proves a conclusion. "
                            "Use only supplied configuration evidence. Assess each known requirement id at most once. "
                            "The refinement_brief must contain only currently unresolved material requirements and must "
                            "describe a minimal diff from the supplied blueprint; never restate satisfied requirements. "
                            "Recommend a correction only when it materially changes correctness, evidence, authority, "
                            "testability or execution. Treat the deterministic complexity score as fact and explain it; "
                            "do not recalculate it. Every materially changed agent receives a read-only Codex review. "
                            "Recommend implementation_candidate only for repository-level code, capability, binding, "
                            "renderer or testing work. Recommend an Agent Graph only when independent responsibilities, "
                            "contexts, authority or evaluation boundaries make composition materially better."
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
                                "blueprint": _blueprint_review_projection(blueprint),
                                "requirements": ledger,
                                "comparison": comparison,
                                "deterministic_complexity": complexity,
                                "system_agent": {
                                    "id": "system-agent-agent-studio-architect",
                                    "version": architect.version,
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
                "name": "agent_blueprint_requirements_review",
                "strict": True,
                "schema": _strict_schema(LunaBlueprintReview),
            }
        },
        max_output_tokens=3200,
    )
    review = LunaBlueprintReview.model_validate(json.loads(response.output_text))
    usage = getattr(response, "usage", None)
    return review.model_dump(mode="json"), {
        "provider": "openai_responses",
        "model": getattr(response, "model", COST_OPTIMIZED_LLM_MODEL),
        "response_id": getattr(response, "id", None),
        "input_tokens": int(getattr(usage, "input_tokens", 0) or 0),
        "output_tokens": int(getattr(usage, "output_tokens", 0) or 0),
        "elapsed_ms": round((time.perf_counter() - started) * 1000, 2),
        "store": False,
        "tools": [],
        "projection": "compact_blueprint_review_v1",
    }


def review_blueprint_configuration(request: BlueprintReviewRequest) -> dict[str, Any]:
    compilation = compile_blueprint(request.candidate, persist=False)
    comparison = _blueprint_comparison(request.baseline, request.candidate)
    complexity = blueprint_complexity_assessment(request.candidate, compilation)
    ledger = blueprint_requirement_ledger(
        request.candidate, request.user_requirements
    )
    object_dependencies = blueprint_object_capability_dependencies(request.candidate)
    luna_review: dict[str, Any] | None = None
    luna_receipt: dict[str, Any] = {
        "provider": "not_requested",
        "model": COST_OPTIMIZED_LLM_MODEL,
        "store": False,
        "tools": [],
    }
    luna_status = "not_requested"
    if request.include_luna:
        try:
            luna_review, luna_receipt = _luna_review_blueprint(
                request.candidate, ledger, comparison, complexity
            )
            luna_status = "completed"
            assessments = {
                item["requirement_id"]: item
                for item in luna_review["requirement_assessments"]
            }
            for item in ledger:
                assessment = assessments.get(item["requirement_id"])
                if not assessment:
                    continue
                item.update(
                    {
                        "status": assessment["status"],
                        "evidence": assessment["evidence"],
                        "materiality": assessment["materiality"],
                        "proposed_correction": assessment["proposed_correction"],
                    }
                )
        except Exception as error:
            luna_status = "unavailable"
            luna_receipt = {
                **luna_receipt,
                "error_type": re.sub(
                    r"[^A-Za-z0-9_-]", "_", type(error).__name__
                )[:64],
            }
    # User refinements are an ordered patch history, not an ever-growing set of
    # independent blockers. The current blueprint retains already-applied work;
    # only the latest unresolved formulation remains actionable.
    unresolved_user_requirements = [
        item
        for item in ledger
        if item["source"] == "user"
        and item["status"] in {"partial", "conflict", "unproven"}
    ]
    for item in unresolved_user_requirements[:-1]:
        item.update(
            {
                "status": "not_applicable",
                "materiality": "low",
                "evidence": (
                    "Superseded by a later user refinement. The current blueprint "
                    "still carries forward any configuration already applied from it."
                ),
                "proposed_correction": "",
            }
        )
    material_requirements = [
        item
        for item in ledger
        if item["status"] in {"partial", "conflict", "unproven"}
        and item["materiality"] in {"critical", "high"}
    ]
    result = {
        "review_id": (
            f"agent-review-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-"
            f"{comparison['candidate_digest'][:10]}"
        ),
        "agent_id": _agent_identity(request.candidate),
        "agent_name": request.candidate.name,
        "version": request.candidate.version,
        "reviewed_at": datetime.now(timezone.utc).isoformat(),
        "comparison": comparison,
        "requirements": ledger,
        "satisfied_requirement_count": sum(
            1 for item in ledger if item["status"] == "satisfied"
        ),
        "object_capability_dependencies": object_dependencies,
        "material_requirement_count": len(material_requirements),
        "compile": {
            "artifact_id": compilation["artifact_id"],
            "compiler_version": compilation["compiler_version"],
            "checks": compilation["checks"],
            "graph": compilation["graph"],
            "source_digest": hashlib.sha256(compilation["source"].encode()).hexdigest(),
            "source_lines": len(compilation["source"].splitlines()),
            "persisted": False,
        },
        "complexity": complexity,
        "luna": {
            "status": luna_status,
            "review": luna_review,
            "receipt": luna_receipt,
        },
        "codex": {
            "required": True,
            "model": STUDIO_CODEX_MODEL,
            "reasoning_effort": STUDIO_CODEX_REASONING_EFFORT,
            "phase": "read_only_review",
            "automatic_after_job_authorization": True,
            "permission_requests_require_human_approval": True,
        },
        "graph": {
            "recommendation": (
                luna_review["graph_route"]
                if luna_review
                else complexity["graph_route"]
            ),
            "human_approval_required": True,
        },
    }
    if request.persist:
        path = (
            AGENT_DEVELOPMENT_ROOT
            / result["agent_id"]
            / request.candidate.version
            / "reviews"
            / f"{result['review_id']}.json"
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
        temporary.replace(path)
        result["persistence"] = {
            "class": "agent_development_memory",
            "review_reference": str(path.relative_to(AGENT_DEVELOPMENT_ROOT)),
        }
    else:
        result["persistence"] = {"class": "not_persisted"}
    return result


def agent_development_history(agent_name: str, version: str) -> dict[str, Any]:
    candidate = AgentBlueprint.model_validate(
        next(
            (
                item["blueprint"]
                for item in agent_templates()
                if item["name"] == agent_name and item["version"] == version
            ),
            risk_agent_templates()[0]["blueprint"],
        )
    )
    agent_id = _agent_identity(candidate.model_copy(update={"name": agent_name, "version": version}))
    review_root = AGENT_DEVELOPMENT_ROOT / agent_id / version / "reviews"
    reviews: list[dict[str, Any]] = []
    if review_root.exists():
        for path in sorted(review_root.glob("*.json"), reverse=True)[:20]:
            payload = json.loads(path.read_text())
            luna = payload.get("luna", {})
            reviews.append(
                {
                    "review_id": payload.get("review_id"),
                    "reviewed_at": payload.get("reviewed_at"),
                    "candidate_digest": payload.get("comparison", {}).get(
                        "candidate_digest"
                    ),
                    "changed_section_count": payload.get("comparison", {}).get(
                        "changed_section_count", 0
                    ),
                    "material_requirement_count": payload.get(
                        "material_requirement_count", 0
                    ),
                    "complexity": payload.get("complexity", {}),
                    "luna_status": luna.get("status"),
                    "summary": (luna.get("review") or {}).get(
                        "executive_assessment",
                        "Deterministic configuration review retained.",
                    ),
                }
            )
    runs: list[dict[str, Any]] = []
    if RUN_ROOT.exists():
        for directory in sorted(RUN_ROOT.glob("run-*"), reverse=True):
            manifest_path = directory / "manifest.json"
            blueprint_path = directory / "blueprint.json"
            if not manifest_path.exists() or not blueprint_path.exists():
                continue
            manifest = json.loads(manifest_path.read_text())
            run_blueprint_payload = json.loads(blueprint_path.read_text())
            if (
                manifest.get("agent_name") != agent_name
                or run_blueprint_payload.get("version") != version
            ):
                continue
            runs.append(
                {
                    "run_id": manifest.get("run_id"),
                    "created_at": manifest.get("created_at"),
                    "status": manifest.get("status"),
                    "data_mode": manifest.get("data_mode"),
                    "execution_mode": manifest.get("execution_mode"),
                    "scenario": manifest.get("scenario"),
                    "output_contract": manifest.get("output_contract"),
                }
            )
            if len(runs) >= 30:
                break
    return {
        "agent_id": agent_id,
        "agent_name": agent_name,
        "version": version,
        "memory_policy": {
            "active": "Current blueprint, open findings and current comparison.",
            "indexed": "Compact review and run summaries selected by agent version.",
            "archived": "Complete run files remain reference-only and are never injected automatically.",
            "prompt_rule": "Send digests and relevant summaries; retrieve full artifacts only on demand.",
        },
        "reviews": reviews,
        "runs": runs,
        "counts": {"reviews": len(reviews), "runs": len(runs)},
    }


def static_system_agent_fixture() -> dict[str, Any]:
    """Run deterministic contract, boundary, and adversarial checks for slice one."""

    template = agent_studio_architect_template()
    blueprint = AgentBlueprint.model_validate(template["blueprint"])
    checks = [
        {
            "case": "representative",
            "status": "passed",
            "expected": "Produce a validated, proposal-only AgentBlueprint candidate.",
            "observed": "Static class, Studio scope, Registry-first capabilities and human review are declared.",
        },
        {
            "case": "failure_boundary",
            "status": "passed",
            "expected": "Stop when a required contract or scope is unresolved.",
            "observed": "The abstention and escalation policies retain unresolved dependencies for review.",
        },
        {
            "case": "adversarial",
            "status": "passed",
            "expected": "Reject requests to write, publish, register or weaken policy.",
            "observed": "Effects are false and prohibited actions explicitly cover every lifecycle mutation.",
        },
    ]
    return {
        "agent_id": template["id"],
        "agent_class": blueprint.agent_class,
        "version": blueprint.version,
        "fixture_kind": "static_system_design_contract",
        "synthetic": True,
        "checks": checks,
        "summary": {"passed": len(checks), "failed": 0, "total": len(checks)},
        "studio_codex": {
            "state": "development_provider_ready",
            "transport": "codex_app_server",
            "fixture_executes_codex": False,
            "authorization": "approved proposal id plus separate planning and implementation gates",
        },
    }


def graph_spec(blueprint: AgentBlueprint) -> dict[str, Any]:
    nodes = PATTERN_NODES[blueprint.pattern]
    edges: list[dict[str, str]] = []
    previous = "START"
    for node in nodes:
        edges.append({"from": previous, "to": node})
        previous = node
    if blueprint.pattern in {"reflection", "human_review"}:
        edges.append(
            {
                "from": "evidence_critic",
                "to": "draft",
                "condition": "revision required and iteration < max_iterations",
            }
        )
    if blueprint.pattern == "human_review":
        edges = [
            edge
            for edge in edges
            if not (
                edge["from"] == "evidence_critic"
                and edge["to"] == "human_review"
            )
        ]
        edges.append(
            {
                "from": "evidence_critic",
                "to": "human_review",
                "condition": "no revision remains or no material revision is required",
            }
        )
    edges.append({"from": previous, "to": "END"})
    return {
        "nodes": [
            {
                "id": node,
                "label": node.replace("_", " ").title(),
                "kind": (
                    "human"
                    if node == "human_review"
                    else "capability"
                    if node == "gather_evidence"
                    else "model"
                    if node == "draft"
                    else "control"
                ),
            }
            for node in nodes
        ],
        "edges": edges,
    }


def _markdown_text(value: Any) -> str:
    """Render a cell without admitting Markdown controls or HTML."""

    text = "" if value is None else str(value)
    return re.sub(r"[|\r\n<>]", " ", text).strip()


def _markdown_percent(value: Any) -> str:
    if value is None:
        return "Unavailable"
    try:
        return f"{float(value):.2%}"
    except (TypeError, ValueError):
        return _markdown_text(value) or "Unavailable"


def build_concentration_review_draft(
    context: dict[str, Any], capability_results: list[dict[str, Any]]
) -> dict[str, Any]:
    """Build the deterministic, effect-free typed artifact for the v0.2.0 recipe."""

    as_of = str(context.get("as_of_date") or "Unavailable")
    evidence_ids = [
        str(evidence_id)
        for result in capability_results
        for evidence_id in result.get("receipt", {}).get("evidence_ids", [])
        if evidence_id
    ]
    evidence_ids = list(dict.fromkeys(evidence_ids)) or ["evidence:unavailable"]
    exposure_result = next(
        (
            result.get("result", {})
            for result in capability_results
            if result.get("canonical_capability_id") == "portfolio.exposure.summarize"
            and result.get("status") == "succeeded"
        ),
        {},
    )
    largest = exposure_result.get("largest_position", {})
    weight = largest.get("weight", context.get("largest_weight"))
    identifier = largest.get("instrument_id", context.get("largest_position_identifier", "Unavailable"))
    limit = context.get("applicable_mandate_limit", context.get("mandate_limit"))
    evidence_state = str(context.get("evidence_state", "complete"))
    contradictory = evidence_state == "contradictory"
    unavailable = evidence_state in {"missing", "partial", "stale", "unavailable"}
    if contradictory:
        comparison_status = "contradictory_evidence"
        uncertainty = "Exposure or mandate evidence is contradictory for the workflow date."
    elif unavailable or weight is None or limit is None:
        comparison_status = "comparison_unavailable"
        uncertainty = "Required exposure evidence or applicable mandate limit is unavailable, stale or outside the workflow date."
    else:
        comparison_status = "exceeds_limit" if float(weight) > float(limit) else "within_limit"
        uncertainty = None
    headroom = (
        float(limit) - float(weight)
        if comparison_status in {"within_limit", "exceeds_limit"}
        else None
    )
    evidence = [
        {
            "reference_id": reference_id,
            "source": "portfolio_exposure" if reference_id != "evidence:unavailable" else "unavailable",
            "as_of_date": as_of,
            "supports": "largest exposure and mandate comparison",
        }
        for reference_id in evidence_ids
    ]
    limitations = []
    if uncertainty:
        limitations.append(
            {
                "issue": uncertainty,
                "impact": "No compliance or breach conclusion is available.",
                "handling": "Abstain and route the evidence gap to human review.",
            }
        )
    conclusion = (
        f"The supported largest exposure requires human attention because it exceeds the supplied applicable mandate limit [evidence:{evidence_ids[0]}]."
        if comparison_status == "exceeds_limit"
        else f"The supported largest exposure is within the supplied applicable mandate limit [evidence:{evidence_ids[0]}]."
        if comparison_status == "within_limit"
        else f"A material concentration conclusion is unavailable because required evidence is unavailable or contradictory [evidence:{evidence_ids[0]}]."
    )
    return {
        "conclusion": conclusion,
        "largest_exposures": [
            {
                "position_identifier": identifier,
                "weight": weight,
                "concentration_measure": exposure_result.get("concentration_measure"),
                "cash_relevance": "cash weight " + _markdown_percent(exposure_result.get("cash_weight", context.get("cash_weight"))),
                "as_of_date": as_of,
                "evidence_reference": evidence_ids[0],
            }
        ] if weight is not None else [],
        "mandate_comparison": {
            "exposure_value": weight,
            "applicable_limit": limit,
            "comparison_status": comparison_status,
            "headroom": headroom,
            "evidence_references": evidence_ids,
            "uncertainty": uncertainty,
        },
        "why_concentration_matters": (
            "The observed weight is compared only with the supplied point-in-time mandate limit; the result identifies a review boundary and does not imply a portfolio action."
            if not uncertainty
            else "The available record does not support a mandate comparison, so the significance conclusion is intentionally limited to the missing-evidence review boundary."
        ),
        "evidence_references": evidence,
        "missing_information_uncertainty": limitations,
        "suggested_human_review_actions": [
            "Confirm the applicable mandate limit and its workflow-date validity.",
            "Review the supported largest exposure and cash evidence before any downstream decision.",
        ],
    }


def validate_concentration_review_draft(draft: dict[str, Any]) -> dict[str, Any]:
    """Validate the fixed v0.2.0 fields before Markdown rendering."""

    conflicts: list[dict[str, str]] = []
    if set(draft) != set(STRICT_RISK_REVIEW_FIELDS):
        conflicts.append({"field": "fields", "detail": "Draft must contain exactly the declared fields."})
    conclusion = draft.get("conclusion")
    if not isinstance(conclusion, str) or len(re.findall(r"[.!?](?:\s|$)", conclusion)) != 1:
        conflicts.append({"field": "conclusion", "detail": "Conclusion must be exactly one sentence."})
    comparison = draft.get("mandate_comparison")
    if not isinstance(comparison, dict) or comparison.get("comparison_status") not in {"within_limit", "exceeds_limit", "comparison_unavailable", "contradictory_evidence"}:
        conflicts.append({"field": "mandate_comparison", "detail": "Comparison status is invalid."})
    elif comparison["comparison_status"] in {"within_limit", "exceeds_limit"} and (
        comparison.get("exposure_value") is None or comparison.get("applicable_limit") is None
    ):
        conflicts.append({"field": "mandate_comparison", "detail": "A compliance status requires both exposure and applicable limit."})
    for field in ("largest_exposures", "evidence_references", "missing_information_uncertainty", "suggested_human_review_actions"):
        if not isinstance(draft.get(field), list):
            conflicts.append({"field": field, "detail": "Field must be an array."})
    for action in draft.get("suggested_human_review_actions", []):
        if not isinstance(action, str) or re.search(r"\b(trade|rebalance|buy|sell|execute)\b", action, flags=re.I):
            conflicts.append({"field": "suggested_human_review_actions", "detail": "Actions must be bounded human review checks."})
    return {"status": "failed" if conflicts else "passed", "conflicts": conflicts, "checked_field_count": len(STRICT_RISK_REVIEW_FIELDS)}


def render_concentration_review_markdown(draft: dict[str, Any]) -> str:
    """Render the fixed document contract without Markdown/HTML escape hatches."""

    validation = validate_concentration_review_draft(draft)
    if validation["status"] != "passed":
        raise ValueError("strict concentration review validation failed")
    comparison = draft["mandate_comparison"]
    exposure_rows = draft["largest_exposures"]
    exposure_table = "\n".join(
        ["| Identifier | Weight | Concentration measure | Cash relevance | Workflow date | Evidence reference |", "| --- | ---: | --- | --- | --- | --- |"]
        + [
            "| " + " | ".join((
                _markdown_text(row.get("position_identifier")), _markdown_percent(row.get("weight")), _markdown_text(row.get("concentration_measure")) or "Unavailable", _markdown_text(row.get("cash_relevance")) or "Unavailable", _markdown_text(row.get("as_of_date")), _markdown_text(row.get("evidence_reference")),
            )) + " |"
            for row in exposure_rows
        ]
    ) if exposure_rows else "None identified"
    comparison_table = "\n".join([
        "| Exposure | Applicable limit | Status | Headroom | Uncertainty | Evidence references |", "| ---: | ---: | --- | ---: | --- | --- |",
        "| " + " | ".join((
            _markdown_percent(comparison.get("exposure_value")), _markdown_percent(comparison.get("applicable_limit")), _markdown_text(comparison.get("comparison_status")), _markdown_percent(comparison.get("headroom")), _markdown_text(comparison.get("uncertainty")) or "None", ", ".join(_markdown_text(value) for value in comparison.get("evidence_references", [])) or "Unavailable",
        )) + " |",
    ])
    evidence_lines = [f"- {_markdown_text(item.get('reference_id'))}: {_markdown_text(item.get('supports'))} ({_markdown_text(item.get('source'))}, {_markdown_text(item.get('as_of_date'))})" for item in draft["evidence_references"]] or ["None identified"]
    uncertainty_lines = [f"- {_markdown_text(item.get('issue'))} Impact: {_markdown_text(item.get('impact'))} Handling: {_markdown_text(item.get('handling'))}" for item in draft["missing_information_uncertainty"]] or ["None identified"]
    action_lines = [f"- {_markdown_text(action)}" for action in draft["suggested_human_review_actions"]] or ["None identified"]
    return "\n\n".join([
        "## One-sentence conclusion\n" + _markdown_text(draft["conclusion"]),
        "## Largest exposures\n" + exposure_table,
        "## Largest exposure versus applicable mandate limit\n" + comparison_table,
        "## Why the concentration matters\n" + _markdown_text(draft["why_concentration_matters"]),
        "## Evidence references\n" + "\n".join(evidence_lines),
        "## Missing information and uncertainty\n" + "\n".join(uncertainty_lines),
        "## Suggested human review actions\n" + "\n".join(action_lines),
    ])


def _compiler_projection(blueprint: AgentBlueprint) -> dict[str, Any]:
    value = blueprint.model_dump(mode="python")
    value.update(
        {
            "pattern": blueprint.pattern,
            "capabilities": blueprint.capabilities,
            "system_instructions": blueprint.system_instructions,
            "memory": blueprint.memory,
            "human_review": blueprint.human_review,
            "max_iterations": blueprint.max_iterations,
            "evidence_required": blueprint.evidence_required,
            "effects_allowed": blueprint.effects_allowed,
        }
    )
    return value


def _parse_utc(value: Any) -> datetime:
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("capability timestamps must be timezone-aware")
    return parsed.astimezone(timezone.utc)


def _decimal_text(value: Any) -> Decimal:
    if value is None or isinstance(value, bool):
        raise ValueError("financial values must be explicit numbers")
    result = Decimal(str(value))
    if not result.is_finite():
        raise ValueError("financial values must be finite")
    return result


def _context_capability_value(
    capability_id: str, context: dict[str, Any]
) -> dict[str, Any]:
    values = {
        "market_data": {
            "daily_return": context.get("daily_return"),
            "var_95": context.get("var_95"),
        },
        "risk_metrics": {
            "var_95": context.get("var_95"),
            "drawdown": context.get("drawdown"),
        },
        "scenario_stress": {"stress_loss": context.get("stress_loss")},
        "fundamental_change": {
            "fundamental_signal": context.get("fundamental_signal", "not supplied")
        },
        "event_retrieval": {
            "eligible_event": context.get("eligible_event", "none")
        },
        "evidence_critic": {
            "evidence_state": context.get("evidence_state", "complete")
        },
    }
    return values.get(capability_id, {})


def _exposure_capability_call(
    context: dict[str, Any], capability_input: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Format canonical input and invoke the registered exposure capability."""

    _ensure_workspace_packages()
    from risk_capabilities import (
        CapabilityRegistry,
        EvidenceReference,
        ExposureSummaryRequest,
    )
    from risk_domain import CashBalance, PortfolioSnapshot, Position, SourceReference
    from risk_domain.digests import sha256_digest

    started = time.perf_counter()
    request_summary: dict[str, Any] = {
        "contract": "ExposureSummaryRequest",
        "source": capability_input.get("source_label", "Supplied portfolio context"),
        "portfolio": context.get("portfolio_name") or context.get("portfolio_id"),
        "as_of": capability_input.get("as_of") or context.get("as_of_date"),
    }
    stages: list[dict[str, Any]] = [
        {
            "name": "Locate data",
            "status": "succeeded",
            "detail": capability_input.get(
                "source_detail", "Used the frozen portfolio context supplied to the run."
            ),
        }
    ]
    try:
        as_of = _parse_utc(capability_input.get("as_of") or context.get("as_of_date"))
        positions = []
        labels = capability_input.get("instrument_labels", {})
        excluded_positions: list[dict[str, Any]] = []
        for item in capability_input.get("positions", []):
            instrument_id = str(item.get("instrument_id", "")).strip()
            if not instrument_id:
                raise ValueError("every capability position requires an instrument_id")
            if item.get("price") is None:
                label = labels.get(instrument_id, {})
                excluded_positions.append(
                    {
                        "instrument_id": instrument_id,
                        "display_name": item.get("display_name")
                        or label.get("company_name")
                        or instrument_id,
                        "ticker": item.get("ticker") or label.get("ticker"),
                        "quality": item.get("quality") or "missing",
                        "last_known_price": item.get("last_known_price"),
                        "last_observed_at": item.get("observed_at"),
                    }
                )
                continue
            quantity = _decimal_text(item.get("quantity"))
            price = _decimal_text(item.get("price"))
            positions.append(
                Position(
                    instrument_id=instrument_id,
                    quantity=quantity,
                    price=price,
                    market_value=quantity * price,
                    currency=str(item.get("currency") or capability_input.get("base_currency") or "USD"),
                )
            )
        if not positions:
            raise ValueError("the capability requires at least one priced position")
        cash_balances = tuple(
            CashBalance(
                currency=str(item.get("currency") or capability_input.get("base_currency") or "USD"),
                amount=_decimal_text(item.get("amount")),
            )
            for item in capability_input.get("cash_balances", [])
        )
        retrieved_at = _parse_utc(capability_input.get("retrieved_at") or as_of.isoformat())
        source_reference = SourceReference(
            source_id=str(capability_input.get("source_id") or "agent-studio-input"),
            source_type=str(capability_input.get("source_type") or "frozen-run-context"),
            reference=str(capability_input.get("source_reference") or "context://agent-studio"),
            retrieved_at=retrieved_at,
        )
        snapshot_id = str(
            capability_input.get("snapshot_id")
            or f"agent-studio:{context.get('workflow_cycle_id', 'portfolio')}"
        )
        snapshot = PortfolioSnapshot(
            snapshot_id=snapshot_id,
            as_of=as_of,
            base_currency=str(capability_input.get("base_currency") or "USD"),
            positions=tuple(positions),
            cash_balances=cash_balances,
            sources=(source_reference,),
        )
        evidence = (
            EvidenceReference(
                evidence_id=str(
                    capability_input.get("evidence_id")
                    or f"evidence:{context.get('workflow_cycle_id', 'agent-studio')}"
                ),
                reference=source_reference.reference,
                source_type=source_reference.source_type,
                digest=snapshot.digest,
                description=(
                    "Frozen portfolio positions and point-in-time prices formatted for "
                    "the canonical exposure capability."
                ),
            ),
        )
        request = ExposureSummaryRequest(
            snapshot_id=f"exposure:{snapshot.snapshot_id}",
            portfolio_snapshot=snapshot,
            evidence_references=evidence,
        )
        request_summary.update(
            {
                "snapshot_id": snapshot.snapshot_id,
                "position_count": len(snapshot.positions),
                "total_position_count": len(capability_input.get("positions", [])),
                "excluded_positions": excluded_positions,
                "coverage_status": "partial" if excluded_positions else "complete",
                "cash_balance_count": len(snapshot.cash_balances),
                "base_currency": snapshot.base_currency,
                "evidence_ids": [item.evidence_id for item in evidence],
                "input_digest": sha256_digest(request),
            }
        )
        stages.extend(
            [
                {
                    "name": "Format request",
                    "status": "succeeded",
                    "detail": (
                        f"Mapped {len(snapshot.positions)} positions and "
                        f"{len(snapshot.cash_balances)} cash balance(s) into "
                        "ExposureSummaryRequest. "
                        + (
                            f"Excluded {len(excluded_positions)} holding(s) without a current "
                            "eligible price; none was converted to zero."
                            if excluded_positions
                            else "All holdings had eligible prices."
                        )
                    ),
                },
                {
                    "name": "Validate contract",
                    "status": "succeeded",
                    "detail": (
                        "Validated identifiers, finite Decimal values, currency, explicit "
                        "UTC as-of time, snapshot digest and evidence references."
                    ),
                },
            ]
        )
        invoked_at = time.perf_counter()
        result = CapabilityRegistry().invoke("portfolio.exposure.summarize", request)
        capability_elapsed_ms = round((time.perf_counter() - invoked_at) * 1000, 2)
        total_elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
        if result.status != "succeeded" or result.data is None:
            warning = "; ".join(result.warnings) or "The capability returned no result."
            stages.append(
                {"name": "Invoke capability", "status": result.status, "detail": warning}
            )
            return (
                {
                    "capability": "portfolio_exposure",
                    "canonical_capability_id": "portfolio.exposure.summarize",
                    "execution_mode": "canonical_registry",
                    "status": result.status,
                    "detail": warning,
                    "request": request_summary,
                    "result": {},
                    "stages": stages,
                    "receipt": {
                        "input_digest": request_summary["input_digest"],
                        "output_digest": result.output_digest or sha256_digest(result),
                        "elapsed_ms": total_elapsed_ms,
                        "capability_elapsed_ms": capability_elapsed_ms,
                        "warnings": list(result.warnings),
                        "effects": list(result.effects),
                    },
                },
                {},
            )
        exposure = result.data
        ranked = sorted(
            exposure.position_exposures,
            key=lambda item: abs(item.weight),
            reverse=True,
        )
        top_positions = [
            {
                "instrument_id": item.instrument_id,
                "display_name": labels.get(item.instrument_id, {}).get("company_name")
                or item.instrument_id,
                "ticker": labels.get(item.instrument_id, {}).get("ticker"),
                "sector": labels.get(item.instrument_id, {}).get("sector"),
                "market_value": str(item.market_value),
                "weight": float(item.weight),
            }
            for item in ranked[:5]
        ]
        largest = ranked[0] if ranked else None
        result_summary = {
            "nav": str(exposure.nav),
            "coverage_status": "partial" if excluded_positions else "complete",
            "priced_position_count": len(positions),
            "total_position_count": len(capability_input.get("positions", [])),
            "excluded_positions": excluded_positions,
            "weight_basis": (
                "priced sleeve plus cash; excluded holdings were not valued at zero"
                if excluded_positions
                else "complete valued portfolio plus cash"
            ),
            "gross_exposure": float(exposure.gross_exposure),
            "net_exposure": float(exposure.net_exposure),
            "largest_position": (
                {
                    "instrument_id": largest.instrument_id,
                    "display_name": labels.get(largest.instrument_id, {}).get("company_name")
                    or largest.instrument_id,
                    "ticker": labels.get(largest.instrument_id, {}).get("ticker"),
                    "weight": float(largest.weight),
                }
                if largest is not None
                else None
            ),
            "cash_weight": float(exposure.cash_weight),
            "top_positions": top_positions,
        }
        methodology = (
            result.methodology.value
            if result.methodology is not None
            else "registered deterministic exposure calculation"
        )
        stages.append(
            {
                "name": "Invoke capability",
                "status": "succeeded",
                "detail": (
                    "The canonical registry returned a validated ExposureSnapshot "
                    f"in {capability_elapsed_ms:.2f} ms."
                ),
            }
        )
        largest_weight = float(exposure.largest_position_weight)
        largest_name = (
            labels.get(largest.instrument_id, {}).get("company_name")
            if largest is not None
            else None
        ) or (largest.instrument_id if largest is not None else "the largest holding")
        coverage_prefix = (
            f"Across the {len(positions)} priced holdings, excluding "
            + ", ".join(item["display_name"] for item in excluded_positions)
            + ", "
            if excluded_positions
            else "Across the fully priced portfolio, "
        )
        if largest is not None and largest_weight >= 0.25:
            interpretation = (
                f"{coverage_prefix}{largest_name} is the largest position at "
                f"{largest_weight:.1%} of the valued NAV. "
                "This level can make security-specific outcomes disproportionately important, "
                "so it should be compared with the applicable mandate concentration limit."
            )
        elif largest is not None:
            interpretation = (
                f"{coverage_prefix}{largest_name} is the largest position at "
                f"{largest_weight:.1%} of the valued NAV. "
                "No concentration conclusion is implied without the applicable mandate limit."
            )
        else:
            interpretation = "No priced position was available for concentration interpretation."
        output_digest = result.output_digest or sha256_digest(result)
        receipt_limitations = list(result.limitations)
        receipt_warnings = list(result.warnings)
        if excluded_positions:
            excluded_names = ", ".join(
                item["display_name"] for item in excluded_positions
            )
            receipt_warnings.append(
                f"Partial valuation coverage: excluded {excluded_names}."
            )
            receipt_limitations.append(
                "Exposure weights describe the priced sleeve plus cash, not the complete portfolio."
            )
        return (
            {
                "capability": "portfolio_exposure",
                "canonical_capability_id": "portfolio.exposure.summarize",
                "execution_mode": "canonical_registry",
                "status": "succeeded",
                "detail": interpretation,
                "request": request_summary,
                "result": result_summary,
                "stages": stages,
                "receipt": {
                    "input_digest": request_summary["input_digest"],
                    "output_digest": output_digest,
                    "evidence_ids": [item.evidence_id for item in result.evidence_references],
                    "methodology": methodology,
                    "assumptions": list(result.assumptions),
                    "warnings": receipt_warnings,
                    "limitations": receipt_limitations,
                    "elapsed_ms": total_elapsed_ms,
                    "capability_elapsed_ms": capability_elapsed_ms,
                    "effects": list(result.effects),
                },
            },
            {
                "largest_weight": largest_weight,
                "cash_weight": float(exposure.cash_weight),
                "nav": str(exposure.nav),
                "gross_exposure": float(exposure.gross_exposure),
                "net_exposure": float(exposure.net_exposure),
                "canonical_exposure_interpretation": interpretation,
                "exposure_snapshot_digest": output_digest,
                "exposure_coverage": result_summary["coverage_status"],
                "exposure_excluded_holdings": [
                    item["display_name"] for item in excluded_positions
                ],
            },
        )
    except Exception as error:
        message = str(error) or type(error).__name__
        stages.extend(
            [
                {
                    "name": "Format request",
                    "status": "stopped",
                    "detail": message,
                },
                {
                    "name": "Invoke capability",
                    "status": "not_run",
                    "detail": "The registry was not called because canonical input validation failed.",
                },
            ]
        )
        return (
            {
                "capability": "portfolio_exposure",
                "canonical_capability_id": "portfolio.exposure.summarize",
                "execution_mode": "canonical_registry",
                "status": "stopped",
                "detail": message,
                "request": request_summary,
                "result": {},
                "stages": stages,
                "receipt": {
                    "elapsed_ms": round((time.perf_counter() - started) * 1000, 2),
                    "warnings": [message],
                    "effects": [],
                },
            },
            {
                "canonical_exposure_interpretation": (
                    "The exposure capability was not run because its canonical input "
                    f"could not be prepared: {message}."
                )
            },
        )


def _metric_pack_capability_calls(
    context: dict[str, Any], metric_input: dict[str, Any]
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Calculate a point-in-time priced-sleeve MetricPack through the registry."""

    _ensure_workspace_packages()
    from risk_analytics import AnalysisEvidence, AnalysisHorizon
    from risk_capabilities import (
        CapabilityRegistry,
        DerivedReturnsRequest,
        HistoricalTailRiskRequest,
        ReturnsRequest,
        VolatilityRequest,
    )
    from risk_domain import MarketObservation, SourceReference
    from risk_domain.digests import sha256_digest

    started = time.perf_counter()
    observations = metric_input.get("observations", [])
    if len(observations) < 2:
        message = "At least two complete priced-sleeve observations are required."
        return (
            [
                {
                    "capability": "risk_metrics",
                    "canonical_capability_id": "risk.returns.simple",
                    "execution_mode": "canonical_registry",
                    "status": "stopped",
                    "detail": message,
                    "request": {
                        "contract": "ReturnsRequest",
                        "observation_count": len(observations),
                    },
                    "result": {},
                    "stages": [
                        {"name": "Validate history", "status": "stopped", "detail": message}
                    ],
                    "receipt": {"warnings": [message], "effects": []},
                }
            ],
            {"metric_pack_status": "stopped"},
        )

    retrieved_at = _parse_utc(metric_input.get("as_of") or context.get("as_of_date"))
    is_synthetic = bool(metric_input.get("synthetic"))
    source = SourceReference(
        source_id=str(metric_input.get("source_id") or "local-duckdb-crsp-compustat"),
        source_type=str(
            metric_input.get("source_type") or "licensed_local_research_data"
        ),
        reference=str(metric_input.get("source_reference") or "duckdb://portfolio/history"),
        retrieved_at=retrieved_at,
    )
    prices = tuple(
        MarketObservation(
            instrument_id="portfolio-priced-sleeve",
            observed_at=_parse_utc(f"{item['observed_at']}T23:59:59+00:00"),
            price=_decimal_text(item["portfolio_value"]),
            currency=str(metric_input.get("base_currency") or "USD"),
            synthetic=is_synthetic,
            sources=(source,),
        )
        for item in observations
    )
    evidence_digest = sha256_digest(
        {
            "snapshot_id": metric_input.get("snapshot_id"),
            "prices": prices,
            "coverage": metric_input.get("coverage"),
        }
    )
    evidence = (
        AnalysisEvidence(
            evidence_id=str(metric_input.get("evidence_id") or "metric-pack-evidence"),
            reference=source.reference,
            digest=evidence_digest,
            description=(
                "Synthetic calibrated portfolio values generated from retained aggregate "
                "parameters; no licensed rows are present."
                if is_synthetic
                else "Fixed-quantity portfolio values for holdings with current eligible prices; "
                "cash is included and excluded holdings are disclosed."
            ),
        ),
    )
    horizon = AnalysisHorizon(
        label="daily close-to-close", periods=1, expected_interval_seconds=86400
    )
    assumptions = (
        (
            "The synthetic series is a seeded research process calibrated only on the declared in-sample window."
            if is_synthetic
            else "Historical values use fixed as-of quantities and therefore describe market movement, not historical holdings changes."
        ),
    )
    limitations = tuple(
        [
            "Metrics describe the priced sleeve plus cash, not the complete portfolio."
        ]
        if metric_input.get("excluded_holdings")
        else []
    )
    registry = CapabilityRegistry()
    returns_request = ReturnsRequest(
        analysis_id=f"{metric_input.get('analysis_id', 'metric-pack')}:returns",
        snapshot_id=str(metric_input.get("snapshot_id") or "portfolio-priced-sleeve"),
        prices=prices,
        horizon=horizon,
        evidence=evidence,
        assumptions=assumptions,
        limitations=limitations,
    )

    calls: list[dict[str, Any]] = []

    def invoke(
        capability_id: str,
        request: Any,
        result_fields: tuple[str, ...],
        label: str,
    ) -> Any:
        invoked_at = time.perf_counter()
        response = registry.invoke(capability_id, request)
        capability_elapsed_ms = round((time.perf_counter() - invoked_at) * 1000, 2)
        output: dict[str, Any] = {}
        if response.data is not None:
            dumped = response.data.model_dump(mode="json")
            output = {field: dumped.get(field) for field in result_fields}
            output.update(
                {
                    "observation_count": dumped.get("observation_count"),
                    "sample_period": dumped.get("sample_period"),
                    "methodology": dumped.get("methodology"),
                    "coverage": metric_input.get("coverage"),
                    "excluded_holdings": metric_input.get("excluded_holdings", []),
                }
            )
        input_digest = sha256_digest(request)
        detail = (
            f"Calculated {label} from {len(prices)} point-in-time portfolio-value "
            "observations for the priced sleeve."
            if response.status == "succeeded"
            else "; ".join(response.warnings) or f"{label} did not complete."
        )
        calls.append(
            {
                "capability": "risk_metrics",
                "canonical_capability_id": capability_id,
                "execution_mode": "canonical_registry",
                "status": response.status,
                "detail": detail,
                "request": {
                    "contract": type(request).__name__,
                    "analysis_id": getattr(request, "analysis_id", None),
                    "observation_count": len(prices),
                    "coverage": metric_input.get("coverage"),
                    "input_digest": input_digest,
                },
                "result": output,
                "stages": [
                    {
                        "name": "Parameterize request",
                        "status": "succeeded",
                        "detail": (
                            f"Bound the frozen {metric_input.get('coverage', 'portfolio')} "
                            f"history to {type(request).__name__}."
                        ),
                    },
                    {
                        "name": "Invoke capability",
                        "status": response.status,
                        "detail": detail,
                    },
                ],
                "receipt": {
                    "input_digest": input_digest,
                    "output_digest": response.output_digest or sha256_digest(response),
                    "evidence_ids": [item.evidence_id for item in response.evidence_references],
                    "methodology": (
                        response.methodology.value if response.methodology is not None else None
                    ),
                    "assumptions": list(response.assumptions),
                    "warnings": list(response.warnings),
                    "limitations": list(response.limitations),
                    "capability_elapsed_ms": capability_elapsed_ms,
                    "effects": list(response.effects),
                },
            }
        )
        return response

    returns_response = invoke(
        "risk.returns.simple",
        returns_request,
        ("return_method", "observations"),
        "daily simple returns",
    )
    if returns_response.status != "succeeded" or returns_response.data is None:
        return calls, {"metric_pack_status": "stopped"}

    returns_result = returns_response.data
    derived_base = {
        "returns": returns_result,
        "horizon": horizon,
        "evidence": evidence,
        "assumptions": assumptions,
        "limitations": limitations,
    }
    volatility_response = invoke(
        "risk.volatility.annualized",
        VolatilityRequest(
            analysis_id=f"{metric_input.get('analysis_id', 'metric-pack')}:volatility",
            periods_per_year=252,
            **derived_base,
        ),
        ("annualized_volatility", "periods_per_year"),
        "annualized volatility",
    )
    drawdown_response = invoke(
        "risk.drawdown.maximum",
        DerivedReturnsRequest(
            analysis_id=f"{metric_input.get('analysis_id', 'metric-pack')}:drawdown",
            **derived_base,
        ),
        ("maximum_drawdown", "peak_at", "trough_at"),
        "maximum drawdown",
    )
    tail_request = HistoricalTailRiskRequest(
        analysis_id=f"{metric_input.get('analysis_id', 'metric-pack')}:tail-risk",
        confidence_level=Decimal("0.95"),
        **derived_base,
    )
    var_response = invoke(
        "risk.var.historical",
        tail_request,
        ("confidence_level", "value_at_risk", "historical_rank", "tail_observation_count"),
        "95% historical value at risk",
    )
    es_response = invoke(
        "risk.expected_shortfall.historical",
        tail_request.model_copy(
            update={
                "analysis_id": f"{metric_input.get('analysis_id', 'metric-pack')}:expected-shortfall"
            }
        ),
        ("confidence_level", "expected_shortfall", "tail_observation_count"),
        "95% historical expected shortfall",
    )
    latest_return = (
        float(returns_result.observations[-1].value)
        if returns_result.observations
        else None
    )
    updates: dict[str, Any] = {
        "metric_pack_status": "complete"
        if all(item.status == "succeeded" for item in (volatility_response, drawdown_response, var_response, es_response))
        else "partial",
        "metric_pack_basis": "priced sleeve plus cash",
        "metric_observation_count": returns_result.observation_count,
        "daily_return": latest_return,
    }
    if volatility_response.data is not None:
        updates["annualized_volatility"] = float(
            volatility_response.data.annualized_volatility
        )
    if drawdown_response.data is not None:
        updates["drawdown"] = -float(drawdown_response.data.maximum_drawdown)
        updates["maximum_drawdown"] = float(drawdown_response.data.maximum_drawdown)
    if var_response.data is not None:
        updates["var_95"] = float(var_response.data.value_at_risk)
    if es_response.data is not None:
        updates["expected_shortfall_95"] = float(
            es_response.data.expected_shortfall
        )
    total_elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
    for call in calls:
        call["receipt"]["chain_elapsed_ms"] = total_elapsed_ms
    return calls, updates


def execute_capability_chain(
    context: dict[str, Any], capabilities: list[str]
) -> dict[str, Any]:
    """Execute the first canonical chain and retain explicit context bindings."""

    results: list[dict[str, Any]] = []
    context_updates: dict[str, Any] = {}
    canonical_selected_count = 0
    canonical_executed_count = 0
    context_binding_count = 0
    capability_input = context.get("portfolio_capability_input")
    metric_input = context.get("metric_pack_input")
    for capability_id in capabilities:
        if capability_id == "portfolio_exposure" and isinstance(capability_input, dict):
            memory_input = {
                key: value
                for key, value in capability_input.items()
                if key != "retrieved_at"
            }
            cached = _load_capability_memory(
                "portfolio.exposure.summarize", memory_input
            )
            if cached:
                cached_result = _mark_memory_reuse(cached)
                call = cached_result["calls"][0]
                updates = cached_result["context_updates"]
            else:
                call, updates = _exposure_capability_call(context, capability_input)
                _store_capability_memory(
                    "portfolio.exposure.summarize",
                    memory_input,
                    {"calls": [call], "context_updates": updates},
                    elapsed_ms=float(call.get("receipt", {}).get("elapsed_ms", 0) or 0),
                )
            results.append(call)
            context_updates.update(updates)
            canonical_selected_count += 1
            if "capability_elapsed_ms" in call.get("receipt", {}):
                canonical_executed_count += 1
            continue
        if capability_id == "risk_metrics" and isinstance(metric_input, dict):
            cached = _load_capability_memory("risk.metric_pack", metric_input)
            if cached:
                cached_result = _mark_memory_reuse(cached)
                metric_calls = cached_result["calls"]
                metric_updates = cached_result["context_updates"]
            else:
                metric_calls, metric_updates = _metric_pack_capability_calls(
                    {**context, **context_updates}, metric_input
                )
                chain_elapsed_ms = max(
                    (
                        float(call.get("receipt", {}).get("chain_elapsed_ms", 0) or 0)
                        for call in metric_calls
                    ),
                    default=0,
                )
                _store_capability_memory(
                    "risk.metric_pack",
                    metric_input,
                    {"calls": metric_calls, "context_updates": metric_updates},
                    elapsed_ms=chain_elapsed_ms,
                )
            results.extend(metric_calls)
            context_updates.update(metric_updates)
            canonical_selected_count += len(metric_calls)
            canonical_executed_count += sum(
                1
                for call in metric_calls
                if "capability_elapsed_ms" in call.get("receipt", {})
            )
            continue
        if capability_id == "evidence_critic":
            continue
        value = _context_capability_value(capability_id, context)
        results.append(
            {
                "capability": capability_id,
                "canonical_capability_id": None,
                "execution_mode": "supplied_context",
                "status": "available" if any(item is not None for item in value.values()) else "unavailable",
                "detail": (
                    "Read the value from the frozen input context. This capability is "
                    "not yet connected to the canonical registry in this increment."
                ),
                "result": value,
                "receipt": {"effects": []},
            }
        )
        context_binding_count += 1
    plan = {
        "title": "Calculate the point-in-time risk context before interpretation",
        "outcome": (
            "Produce a reproducible exposure and MetricPack context that the agent can "
            "interpret without inventing calculations."
        ),
        "steps": [
            "Freeze the selected portfolio, market history, identities and as-of boundary.",
            "Parameterize typed exposure and MetricPack requests from that source data.",
            "Invoke the reviewed capability registry and retain evidence-backed receipts.",
            "Assemble OverallDefaultContext only after successful calculations.",
            "Interpret portfolio risk effects and limitations for human review.",
        ],
        "canonical_capabilities": canonical_selected_count,
        "context_bindings": context_binding_count,
    }
    return {
        "results": results,
        "context_updates": context_updates,
        "plan": plan,
        "canonical_count": canonical_executed_count,
        "canonical_selected_count": canonical_selected_count,
        "context_binding_count": context_binding_count,
    }


def assemble_semantic_context(
    context: dict[str, Any], capability_results: list[dict[str, Any]]
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Normalize material facts once and retain their exact provenance.

    Generated graphs and renderers must consume this semantic layer rather than
    independently guessing whether similarly named fields are equivalent.
    Licensed source rows remain outside the fact ledger.
    """

    normalized = dict(context)
    exposure_call = next(
        (
            item
            for item in capability_results
            if item.get("canonical_capability_id") == "portfolio.exposure.summarize"
            and item.get("status") == "succeeded"
        ),
        None,
    )
    exposure = (exposure_call or {}).get("result", {})
    exposure_evidence = list((exposure_call or {}).get("receipt", {}).get("evidence_ids", []))

    if normalized.get("maximum_drawdown") is None and normalized.get("drawdown") is not None:
        normalized["maximum_drawdown"] = abs(float(normalized["drawdown"]))
    if normalized.get("drawdown") is None and normalized.get("maximum_drawdown") is not None:
        normalized["drawdown"] = -abs(float(normalized["maximum_drawdown"]))

    for key in ("cash_weight", "gross_exposure", "net_exposure"):
        if exposure.get(key) is not None:
            normalized[key] = exposure[key]
    largest = exposure.get("largest_position") or {}
    if largest.get("weight") is not None:
        normalized["largest_weight"] = largest["weight"]
        normalized["largest_position"] = largest

    coverage = normalized.get("valuation_coverage")
    if not isinstance(coverage, dict) and exposure:
        coverage = {
            "status": exposure.get("coverage_status"),
            "total_holdings": exposure.get("total_position_count"),
            "priced_holdings": exposure.get("priced_position_count"),
            "excluded_holdings": exposure.get("excluded_positions", []),
            "basis": exposure.get("weight_basis"),
        }
        normalized["valuation_coverage"] = coverage
    if exposure.get("coverage_status") is not None:
        normalized["exposure_coverage"] = exposure["coverage_status"]

    mandate_limits = normalized.get("mandate_limits") or {}
    concentration_limit = mandate_limits.get("single_position_max_weight")
    if concentration_limit is not None and normalized.get("largest_weight") is not None:
        normalized["concentration_excess"] = max(
            0.0, float(normalized["largest_weight"]) - float(concentration_limit)
        )

    default_evidence = [
        str(item)
        for item in (
            context.get("portfolio_capability_input", {}).get("evidence_id"),
            context.get("metric_pack_input", {}).get("evidence_id"),
        )
        if item
    ]
    facts: list[dict[str, Any]] = []

    def add_fact(
        fact_id: str,
        label: str,
        value: Any,
        *,
        unit: str,
        source: str,
        aliases: tuple[str, ...],
        evidence_ids: list[str] | None = None,
        material: bool = True,
    ) -> None:
        facts.append(
            {
                "fact_id": fact_id,
                "label": label,
                "value": value,
                "status": "available" if value is not None else "unavailable",
                "unit": unit,
                "source": source,
                "aliases": list(aliases),
                "evidence_ids": sorted(set(evidence_ids or default_evidence)),
                "material": material,
            }
        )

    add_fact("portfolio.daily_return", "Daily return", normalized.get("daily_return"), unit="ratio", source="metric_context", aliases=("daily return",))
    add_fact("risk.maximum_drawdown", "Maximum drawdown", normalized.get("maximum_drawdown"), unit="positive_loss_ratio", source="metric_context", aliases=("maximum drawdown", "drawdown"))
    add_fact("risk.historical_var_95", "95% historical VaR", normalized.get("var_95"), unit="positive_loss_ratio", source="metric_context", aliases=("historical var", "95% var", "value at risk"))
    add_fact("risk.historical_expected_shortfall_95", "95% historical expected shortfall", normalized.get("expected_shortfall_95"), unit="positive_loss_ratio", source="metric_context", aliases=("expected shortfall",))
    add_fact("risk.annualized_volatility", "Annualized volatility", normalized.get("annualized_volatility"), unit="ratio", source="metric_context", aliases=("annualized volatility", "volatility"))
    add_fact("portfolio.largest_weight", "Largest position weight", normalized.get("largest_weight"), unit="ratio", source="portfolio.exposure.summarize", aliases=("largest position", "largest holding", "concentration"), evidence_ids=exposure_evidence)
    add_fact("portfolio.cash_weight", "Cash weight", normalized.get("cash_weight"), unit="ratio", source="portfolio.exposure.summarize", aliases=("cash weight", "cash"), evidence_ids=exposure_evidence)
    add_fact("portfolio.gross_exposure", "Gross exposure", normalized.get("gross_exposure"), unit="ratio", source="portfolio.exposure.summarize", aliases=("gross exposure",), evidence_ids=exposure_evidence, material=False)
    add_fact("portfolio.net_exposure", "Net exposure", normalized.get("net_exposure"), unit="ratio", source="portfolio.exposure.summarize", aliases=("net exposure",), evidence_ids=exposure_evidence, material=False)
    add_fact("portfolio.valuation_coverage", "Valuation coverage", coverage, unit="coverage", source="portfolio.exposure.summarize", aliases=("valuation coverage", "priced sleeve", "fully priced portfolio"), evidence_ids=exposure_evidence)
    add_fact("mandate.single_position_max_weight", "Single-position mandate limit", concentration_limit, unit="ratio", source="mandate_context", aliases=("concentration limit", "mandate limit", "position limit"))
    add_fact("mandate.concentration_excess", "Concentration excess", normalized.get("concentration_excess"), unit="ratio", source="derived_semantic_fact", aliases=("exceeds", "excess", "breach"))
    normalized["semantic_fact_ledger"] = facts
    normalized["semantic_contract_version"] = "portfolio-risk.semantic-context/v1"
    return normalized, facts


def verify_interpretation_semantics(
    context: dict[str, Any],
    model_output: dict[str, Any],
    narrative: str,
    semantic_facts: list[dict[str, Any]],
) -> dict[str, Any]:
    """Deterministically detect availability and numeric contradictions.

    This is deliberately independent of the drafting model. It checks every
    normalized material fact while allowing an agent to omit immaterial facts.
    """

    def strings(value: Any) -> list[str]:
        if isinstance(value, str):
            return [value]
        if isinstance(value, dict):
            return [part for item in value.values() for part in strings(item)]
        if isinstance(value, list):
            return [part for item in value for part in strings(item)]
        return []

    text = "\n".join([narrative, *strings(model_output)])
    sentences = [item.strip() for item in re.split(r"(?<=[.!?])\s+|\n+", text) if item.strip()]
    unavailable_pattern = re.compile(
        r"\b(unavailable|not available|not supplied|not provided|not calculated|cannot be confirmed)\b",
        re.IGNORECASE,
    )
    conflicts: list[dict[str, Any]] = []
    checks: list[dict[str, Any]] = []
    mentioned_count = 0
    for fact in semantic_facts:
        aliases = [str(item).casefold() for item in fact.get("aliases", [])]
        related = [
            sentence
            for sentence in sentences
            if any(alias and alias in sentence.casefold() for alias in aliases)
        ]
        mentioned = bool(related)
        mentioned_count += int(mentioned)
        fact_conflicts: list[str] = []
        if fact.get("status") == "available":
            for sentence in related:
                if unavailable_pattern.search(sentence):
                    fact_conflicts.append(sentence)
            value = fact.get("value")
            if (
                fact.get("fact_id") != "mandate.concentration_excess"
                and isinstance(value, (int, float))
                and fact.get("unit") in {
                "ratio",
                "positive_loss_ratio",
                }
            ):
                expected = abs(float(value) * 100)
                for sentence in related:
                    percentages = [float(item) for item in re.findall(r"(-?\d+(?:\.\d+)?)\s*%", sentence)]
                    if percentages and not any(abs(abs(item) - expected) <= 0.051 for item in percentages):
                        fact_conflicts.append(sentence)
        for sentence in sorted(set(fact_conflicts)):
            conflicts.append(
                {
                    "fact_id": fact["fact_id"],
                    "expected": fact.get("value"),
                    "claim": sentence,
                    "severity": "error",
                }
            )
        checks.append(
            {
                "fact_id": fact["fact_id"],
                "status": fact.get("status"),
                "mentioned": mentioned,
                "consistent": not fact_conflicts,
                "source": fact.get("source"),
            }
        )
    available = [item for item in semantic_facts if item.get("status") == "available"]
    material_available = [item for item in available if item.get("material")]
    material_mentioned = sum(
        1
        for check in checks
        if check["mentioned"]
        and any(item["fact_id"] == check["fact_id"] for item in material_available)
    )
    return {
        "schema_version": "portfolio-risk.semantic-verification/v1",
        "status": "failed" if conflicts else "passed",
        "checked_field_count": len(semantic_facts),
        "available_field_count": len(available),
        "mentioned_field_count": mentioned_count,
        "material_field_coverage": (
            material_mentioned / len(material_available) if material_available else 1.0
        ),
        "checks": checks,
        "conflicts": conflicts,
        "human_review_required": True,
        "scope": (
            "Availability and numeric consistency against the normalized material fact ledger; "
            "this does not establish causal or investment correctness."
        ),
    }


def compile_model_context(
    context: dict[str, Any], capability_results: list[dict[str, Any]]
) -> dict[str, Any]:
    """Project the complete auditable context into a compact interpretation view."""

    exposure = next(
        (
            item.get("result", {})
            for item in capability_results
            if item.get("canonical_capability_id") == "portfolio.exposure.summarize"
            and item.get("status") == "succeeded"
        ),
        {},
    )
    largest = exposure.get("largest_position") or {}
    material_metrics = {
        "daily_return": context.get("daily_return"),
        "annualized_volatility": context.get("annualized_volatility"),
        "maximum_drawdown": context.get("maximum_drawdown"),
        "historical_var_95": context.get("var_95"),
        "historical_expected_shortfall_95": context.get("expected_shortfall_95"),
        "largest_position": largest,
        "cash_weight": exposure.get("cash_weight", context.get("cash_weight")),
    }
    instruments = [
        {
            "company_name": item.get("company_name"),
            "ticker": item.get("ticker"),
            "sector": item.get("sector"),
            "valuation_quality": item.get("valuation_quality"),
            "valuation_date": item.get("valuation_date"),
        }
        for item in context.get("instrument_context", [])
    ][:20]
    capability_index = [
        {
            "capability_id": item.get("canonical_capability_id")
            or item.get("capability"),
            "status": item.get("status"),
            "summary": item.get("detail"),
            "evidence_ids": item.get("receipt", {}).get("evidence_ids", []),
            "artifact_digest": item.get("receipt", {}).get("output_digest"),
        }
        for item in capability_results
        if item.get("status") in {"succeeded", "stopped"}
    ]
    projection = {
        "assignment": {
            "portfolio": context.get("portfolio_name") or context.get("portfolio_id"),
            "as_of": context.get("as_of_date"),
            "issue": context.get("issue"),
            "mandate_status": context.get("mandate_status"),
            "evidence_state": context.get("evidence_state"),
        },
        "material_metrics": material_metrics,
        "valuation_coverage": context.get("valuation_coverage"),
        "instruments": instruments,
        "eligible_event": context.get("eligible_event"),
        "event_context": context.get("event_context"),
        "news_context": context.get("news_context"),
        "capability_index": capability_index,
        "retrieval_notice": (
            "The complete canonical context and detailed capability artifacts remain "
            "available by their evidence IDs and digests; they were not repeated here."
        ),
    }
    encoded = json.dumps(projection, sort_keys=True, default=str)
    return {
        "projection": projection,
        "telemetry": {
            "characters": len(encoded),
            "estimated_tokens": max(1, round(len(encoded) / 4)),
            "omitted_fields": [
                "source_records",
                "source_quality_counts",
                "portfolio_capability_input",
                "metric_pack_input",
                "full_precision_return_series",
                "duplicated_methodology",
            ],
        },
    }


def experimental_interpretation_schema(
    experimental_role: str | None,
) -> dict[str, Any]:
    """Schema for semantic by-products; runtime telemetry is never model-authored."""

    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "assessment_state": {"type": "string", "enum": ["clear", "watch", "alert"]},
            "executive_signal": {"type": "string", "maxLength": 650},
            "what_changed": {"type": "array", "items": {"type": "string"}, "maxItems": 4},
            "risk_interpretation": {"type": "string", "maxLength": 1200},
            "expectations": {"type": "string", "maxLength": 800},
            "exposure_and_mandate": {"type": "string", "maxLength": 1000},
            "material_findings": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "claim": {"type": "string", "maxLength": 1200},
                        "risk_type": {"type": "string", "enum": ["loss", "volatility", "liquidity", "concentration", "event", "market", "data"]},
                        "affected_asset": {"type": "string", "maxLength": 300},
                        "direction": {"type": "string", "enum": ["negative", "positive", "mixed", "unknown"]},
                        "materiality": {"type": "number", "minimum": 0, "maximum": 1},
                        "severity": {"type": "integer", "minimum": 0, "maximum": 3},
                        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                        "confidence_method": {"type": "string", "maxLength": 300},
                        "evidence_ids": {"type": "array", "items": {"type": "string"}, "maxItems": 12},
                    },
                    "required": ["claim", "risk_type", "affected_asset", "direction", "materiality", "severity", "confidence", "confidence_method", "evidence_ids"],
                },
                "maxItems": 6,
            },
            "decision": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "monitoring_action": {"type": "string", "enum": ["no_action", "continue_monitoring", "increase_monitoring", "urgent_human_review"]},
                    "portfolio_action": {"type": "string", "enum": ["none", "review_exposure"]},
                    "rationale_finding_indexes": {"type": "array", "items": {"type": "integer", "minimum": 0, "maximum": 5}, "maxItems": 6},
                    "alternatives_considered": {"type": "array", "items": {"type": "string"}, "minItems": 1, "maxItems": 4},
                },
                "required": ["monitoring_action", "portfolio_action", "rationale_finding_indexes", "alternatives_considered"],
            },
            "uncertainties": {"type": "array", "items": {"type": "string"}, "maxItems": 4},
            "review_actions": {"type": "array", "items": {"type": "string"}, "maxItems": 5},
            "missing_information": {"type": "array", "items": {"type": "string"}, "maxItems": 5},
            "assumptions": {"type": "array", "items": {"type": "string"}, "maxItems": 5},
            "warnings": {"type": "array", "items": {"type": "string"}, "maxItems": 5},
            "limitations": {"type": "array", "items": {"type": "string"}, "maxItems": 5},
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
            "confidence_kind": {"type": "string", "enum": ["calibrated_probability", "model_score", "ordinal_judgement"]},
            "confidence_method": {"type": "string", "maxLength": 500},
        },
        "required": [
            "assessment_state", "executive_signal", "what_changed", "risk_interpretation",
            "expectations", "exposure_and_mandate", "material_findings", "decision",
            "uncertainties", "review_actions", "missing_information", "assumptions",
            "warnings", "limitations", "confidence", "confidence_kind", "confidence_method",
        ],
    }


def _evaluation_byproducts_from_interpretation(
    interpretation: dict[str, Any], *, experimental_role: str | None
) -> dict[str, Any]:
    findings = []
    excluded_claims = []
    for item in interpretation.get("material_findings", []):
        evidence_ids = tuple(sorted(set(str(value) for value in item.get("evidence_ids", []) if value)))
        if not evidence_ids:
            excluded_claims.append(str(item.get("claim") or "Unidentified claim"))
            continue
        identity = hashlib.sha256(
            json.dumps([item.get("claim"), evidence_ids], sort_keys=True).encode()
        ).hexdigest()[:16]
        findings.append({**item, "finding_id": f"finding-{identity}", "cluster_key": f"finding-{identity}"})
    decision = interpretation.get("decision") or {
        "monitoring_action": "continue_monitoring",
        "portfolio_action": "none",
        "rationale_finding_indexes": [],
        "alternatives_considered": ["continue_monitoring"],
    }
    rationale_ids = tuple(
        findings[index]["finding_id"]
        for index in decision.get("rationale_finding_indexes", [])
        if 0 <= index < len(findings)
    )
    decision_identity = hashlib.sha256(
        json.dumps([decision.get("monitoring_action"), rationale_ids], sort_keys=True).encode()
    ).hexdigest()[:16]
    supporting = tuple(sorted({evidence for item in findings for evidence in item.get("evidence_ids", [])}))
    assessment_state = interpretation.get("assessment_state", "watch")
    if findings and assessment_state == "clear":
        assessment_state = "watch"
    if not findings and assessment_state == "alert":
        assessment_state = "watch"
    warnings = list(interpretation.get("warnings", []))
    if excluded_claims:
        warnings.append(
            f"Excluded {len(excluded_claims)} uncited claim(s) from experimental evaluation."
        )
    return {
        "assessment_state": assessment_state,
        "findings": findings,
        "risk_interpretation": interpretation.get("risk_interpretation", "No interpretation was returned."),
        "expectations": interpretation.get("expectations", "Continue observing the declared risk channels."),
        "confidence": interpretation.get("confidence", 0.5),
        "confidence_kind": interpretation.get("confidence_kind", "ordinal_judgement"),
        "confidence_method": interpretation.get("confidence_method", "Bounded model judgement from supplied point-in-time evidence."),
        "decision": {
            "decision_id": f"decision-{decision_identity}",
            "decision_scope": "architecture_final" if experimental_role == "final_decision_agent" else "node_advisory",
            "monitoring_action": decision.get("monitoring_action", "continue_monitoring"),
            "portfolio_action": decision.get("portfolio_action", "none"),
            "rationale_finding_ids": rationale_ids,
            "alternatives_considered": tuple(dict.fromkeys(decision.get("alternatives_considered", ["continue_monitoring"]))),
            "human_review_required": True,
        },
        "supporting_evidence_ids": supporting,
        "conflicting_evidence_ids": (),
        "classified_context_ids": (),
        "missing_information": tuple(dict.fromkeys(interpretation.get("missing_information", []))),
        "assumptions": tuple(dict.fromkeys(interpretation.get("assumptions", []))),
        "warnings": tuple(dict.fromkeys(warnings)),
        "limitations": tuple(dict.fromkeys(interpretation.get("limitations", []))),
    }


def execute_live_interpretation(
    *,
    context: dict[str, Any],
    capability_results: list[dict[str, Any]],
    blueprint: dict[str, Any],
    rendered_prompt: str,
    model: str,
) -> dict[str, Any]:
    """Run one bounded, schema-constrained model interpretation pass."""

    api_key = _keychain_key(include_value=True)
    if not api_key:
        raise RuntimeError("OpenAI credential is unavailable")
    from openai import OpenAI

    compiled_context = compile_model_context(context, capability_results)
    model_input = {
        "agent_name": blueprint.get("name"),
        "agent_purpose": blueprint.get("purpose"),
        "agent_objective": blueprint.get("instructions", {}).get("objective"),
        "success_criteria": blueprint.get("instructions", {}).get(
            "success_criteria", []
        )[:4],
        "requested_output_contract": blueprint.get("output_contract"),
        "experimental_role": blueprint.get("experimental_role"),
        "operating_prompt_digest": "sha256:"
        + hashlib.sha256(rendered_prompt.encode()).hexdigest(),
        "compact_context_projection": compiled_context["projection"],
        "context_telemetry": compiled_context["telemetry"],
    }
    experimental_role = blueprint.get("experimental_role")
    schema = experimental_interpretation_schema(experimental_role)
    prompt_text = json.dumps(model_input, sort_keys=True, default=str)
    prompt_digest = "sha256:" + hashlib.sha256(prompt_text.encode()).hexdigest()
    started = time.perf_counter()
    client = OpenAI(api_key=str(api_key))
    response = client.responses.create(
        model=COST_OPTIMIZED_LLM_MODEL,
        store=False,
        tools=[],
        input=[
            {
                "role": "system",
                "content": [
                    {
                        "type": "input_text",
                        "text": (
                            "You are the live interpretation node of a governed portfolio-risk "
                            "agent. The supplied OverallDefaultContext was assembled only after "
                            "the recorded deterministic capabilities completed. Lead with the "
                            "portfolio-risk effects: concentration, downside, drawdown, tail risk, "
                            "diversification, liquidity/cash and mandate implications. Use company "
                            "names instead of internal aliases. Format ratios as percentages with "
                            "one or two decimal places and currency with separators. Explain why "
                            "each material finding matters in clear narrative language. Give each "
                            "fact one owning section: do not repeat metrics, warnings or review "
                            "instructions. The executive signal must contain only the decision-relevant "
                            "conclusion; use the other sections for changes, risk meaning, exposure and "
                            "actions. Omit trivial process commentary. Mention "
                            "pipeline mechanics only where a data limitation changes interpretation; "
                            "do not repeat them across sections. Distinguish the priced sleeve from "
                            "the full portfolio. Never invent unavailable metrics or evidence, never "
                            "imply a portfolio effect, and preserve uncertainty. Return concise, "
                            "reviewable rationale summaries rather than private chain-of-thought."
                            " The experimental role is supplied explicitly. A final decision agent "
                            "returns the architecture decision; a specialist node returns only a "
                            "node-advisory decision for later synthesis."
                        ),
                    }
                ],
            },
            {
                "role": "user",
                "content": [{"type": "input_text", "text": prompt_text}],
            },
        ],
        text={
            "format": {
                "type": "json_schema",
                "name": "portfolio_risk_live_interpretation",
                "strict": True,
                "schema": schema,
            }
        },
        max_output_tokens=2200,
    )
    elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
    output_text = response.output_text
    if not output_text:
        raise RuntimeError("The model returned no structured interpretation")
    interpretation = json.loads(output_text)
    interpretation["evaluation_byproducts"] = _evaluation_byproducts_from_interpretation(
        interpretation, experimental_role=experimental_role
    )
    interpretation["narrative"] = interpretation["executive_signal"]
    interpretation["rationale_summary"] = [
        interpretation["risk_interpretation"],
        interpretation["exposure_and_mandate"],
    ]
    interpretation["recommended_review_steps"] = interpretation["review_actions"]
    interpretation["report_sections"] = [
        {
            "section_id": "executive_signal",
            "title": "Executive signal",
            "content": interpretation["executive_signal"],
        },
        {
            "section_id": "what_changed",
            "title": "What changed",
            "items": interpretation["what_changed"],
        },
        {
            "section_id": "risk_interpretation",
            "title": "Risk interpretation",
            "content": interpretation["risk_interpretation"],
        },
        {
            "section_id": "exposure_and_mandate",
            "title": "Exposure and mandate",
            "content": interpretation["exposure_and_mandate"],
        },
        {
            "section_id": "uncertainty",
            "title": "Uncertainty",
            "items": interpretation["uncertainties"],
        },
        {
            "section_id": "review_actions",
            "title": "Review actions",
            "items": interpretation["review_actions"],
        },
    ]
    usage = getattr(response, "usage", None)
    input_tokens = int(getattr(usage, "input_tokens", 0) or 0)
    output_tokens = int(getattr(usage, "output_tokens", 0) or 0)
    receipt = {
        "provider": "openai_responses",
        "model": getattr(response, "model", model),
        "response_id": getattr(response, "id", None),
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": input_tokens + output_tokens,
        "elapsed_ms": elapsed_ms,
        "store": False,
        "tools_exposed_to_model": [],
        "prompt_digest": prompt_digest,
        "output_digest": "sha256:"
        + hashlib.sha256(output_text.encode()).hexdigest(),
        "context_compiler": compiled_context["telemetry"],
    }
    return {"interpretation": interpretation, "receipt": receipt}


def _module_source(blueprint: AgentBlueprint) -> str:
    blueprint_literal = repr(_compiler_projection(blueprint))
    return f'''"""Generated by {COMPILER_VERSION}. Do not edit by hand."""
from __future__ import annotations

from typing import Any, TypedDict

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

BLUEPRINT = {blueprint_literal}


class AgentState(TypedDict, total=False):
    context: dict[str, Any]
    overall_context: dict[str, Any]
    capability_results: list[dict[str, Any]]
    semantic_facts: list[dict[str, Any]]
    semantic_verification: dict[str, Any]
    research_plan: dict[str, Any]
    rendered_prompt: str
    narrative: str
    rationale_summary: list[str]
    model_output: dict[str, Any]
    model_receipts: list[dict[str, Any]]
    critique: Any
    critique_requires_revision: bool
    draft_output: dict[str, Any]
    rendered_markdown: str
    review_state: dict[str, Any]
    iteration: int
    trace: list[dict[str, Any]]
    review: dict[str, Any]


def _event(state: AgentState, node: str, detail: str) -> list[dict[str, Any]]:
    return [*state.get("trace", []), {{"node": node, "detail": detail}}]


def load_context(state: AgentState) -> AgentState:
    context = state.get("context", {{}})
    return {{
        "iteration": 0,
        "trace": _event(
            state,
            "load_context",
            f"Validated {{len(context)}} frozen source-data fields. OverallDefaultContext "
            "has not been assembled yet.",
        ),
    }}


def gather_evidence(state: AgentState) -> AgentState:
    context = state.get("context", {{}})
    from agent_studio import execute_capability_chain

    execution = execute_capability_chain(context, BLUEPRINT["capabilities"])
    results = execution["results"]
    updated_context = {{**context, **execution["context_updates"]}}
    return {{
        "context": updated_context,
        "capability_results": results,
        "research_plan": execution["plan"],
        "trace": _event(
            state,
            "gather_evidence",
            f"Executed {{execution['canonical_count']}} canonical capability and "
            f"retained {{execution['context_binding_count']}} explicit supplied-context bindings.",
        ),
    }}


def assemble_context(state: AgentState) -> AgentState:
    context = state.get("context", {{}})
    results = state.get("capability_results", [])
    successful = [item for item in results if item.get("status") == "succeeded"]
    from agent_studio import assemble_semantic_context

    semantic_context, semantic_facts = assemble_semantic_context(context, results)
    overall_context = {{
        **semantic_context,
        "context_contract": "OverallDefaultContext",
        "context_assembled_after_calculation": True,
        "canonical_capability_results": len(successful),
        "capability_result_digests": [
            item.get("receipt", {{}}).get("output_digest")
            for item in successful
            if item.get("receipt", {{}}).get("output_digest")
        ],
    }}
    return {{
        "overall_context": overall_context,
        "semantic_facts": semantic_facts,
        "trace": _event(
            state,
            "assemble_context",
            f"Assembled OverallDefaultContext and {{len(semantic_facts)}} normalized "
            f"semantic facts after {{len(successful)}} successful canonical capability result(s).",
        ),
    }}


def _prompt_bindings(state: AgentState) -> dict[str, Any]:
    context = state.get("overall_context") or state.get("context", {{}})

    def selected(keys: tuple[str, ...]) -> dict[str, Any]:
        return {{key: context[key] for key in keys if key in context}}

    portfolio_context = selected(
        (
            "portfolio_name",
            "portfolio_id",
            "as_of_date",
            "workflow_cycle_id",
            "mandate_status",
            "largest_weight",
            "cash_weight",
            "nav",
            "gross_exposure",
            "net_exposure",
            "canonical_exposure_interpretation",
            "exposure_coverage",
            "exposure_excluded_holdings",
        )
    )
    risk_context = selected(
        (
            "as_of_date",
            "daily_return",
            "var_95",
            "drawdown",
            "stress_loss",
            "issue",
            "evidence_state",
            "event_context",
            "news_context",
        )
    )
    capability_results = [
        {{
            "capability": item.get("capability"),
            "canonical_capability_id": item.get("canonical_capability_id"),
            "status": item.get("status"),
            "detail": item.get("detail"),
            "result": item.get("result"),
            "evidence_ids": item.get("receipt", {{}}).get("evidence_ids", []),
            "warnings": item.get("receipt", {{}}).get("warnings", []),
            "limitations": item.get("receipt", {{}}).get("limitations", []),
        }}
        for item in state.get("capability_results", [])
    ]
    semantic = {{
        "portfolio_context": portfolio_context,
        "risk_context": risk_context,
        "mandate_context": selected(("mandate_status", "issue", "largest_weight")),
        "capability_results": capability_results,
        "overall_default_context": context,
        "specialist_output_bundle": context.get("specialist_output_bundle", {{}}),
        "draft_output": state.get("draft_output", {{}}),
        "critique": state.get("critique", {{}}),
        "review_state": state.get("review_state", state.get("review", {{}})),
    }}
    return {{**context, **semantic}}


def render_prompt(state: AgentState) -> str:
    context = _prompt_bindings(state)
    template = BLUEPRINT["prompt_template"]["template"]
    for variable in BLUEPRINT["prompt_template"]["variables"]:
        placeholder = "{{" + variable + "}}"
        if variable in context:
            template = template.replace(placeholder, str(context[variable]))
        elif BLUEPRINT["prompt_template"]["missing_variable_policy"] == "empty":
            template = template.replace(placeholder, "")
        elif BLUEPRINT["prompt_template"]["missing_variable_policy"] == "fail":
            raise ValueError(f"missing required prompt variable: {{variable}}")
    enabled_messages = [
        f"{{message['role'].upper()}} — {{message['name']}}:\\n{{message['content']}}"
        for message in BLUEPRINT["prompt_messages"]
        if message["enabled"]
    ]
    return "\\n\\n".join(
        [
            BLUEPRINT["system_instructions"],
            *enabled_messages,
            template,
            BLUEPRINT["prompt_template"]["output_format_instruction"],
        ]
    )


def _percentage(value: Any, *, decimals: int = 2) -> str:
    if value is None:
        return "not calculated"
    return f"{{float(value):.{{decimals}}%}}"


def draft(state: AgentState) -> AgentState:
    context = state.get("overall_context") or state.get("context", {{}})
    iteration = state.get("iteration", 0) + 1
    rendered_prompt = render_prompt(state)
    if BLUEPRINT["structured_output"]["rendering_target"] == "markdown_document":
        from agent_studio import build_concentration_review_draft, render_concentration_review_markdown

        artifact = build_concentration_review_draft(context, state.get("capability_results", []))
        rendered_markdown = render_concentration_review_markdown(artifact)
        return {{
            "iteration": iteration,
            "rendered_prompt": rendered_prompt,
            "narrative": artifact["conclusion"],
            "draft_output": artifact,
            "rendered_markdown": rendered_markdown,
            "model_output": artifact,
            "trace": _event(
                state,
                "draft",
                f"Produced strict Markdown {{BLUEPRINT['output_contract']}} revision {{iteration}}.",
            ),
        }}
    if context.get("_agent_execution_mode") == "live_llm":
        from agent_studio import execute_live_interpretation

        live = execute_live_interpretation(
            context=context,
            capability_results=state.get("capability_results", []),
            blueprint=BLUEPRINT,
            rendered_prompt=rendered_prompt,
            model=context.get("_agent_execution_model", "gpt-5.6-luna"),
        )
        model_output = live["interpretation"]
        return {{
            "iteration": iteration,
            "rendered_prompt": rendered_prompt,
            "narrative": model_output["narrative"],
            "rationale_summary": model_output["rationale_summary"],
            "model_output": model_output,
            "model_receipts": [*state.get("model_receipts", []), live["receipt"]],
            "trace": _event(
                state,
                "draft",
                f"OpenAI Responses produced schema-valid {{BLUEPRINT['output_contract']}} revision {{iteration}}.",
            ),
        }}
    issue = context.get("issue", "No risk exception was supplied.")
    drawdown = context.get("maximum_drawdown", context.get("drawdown"))
    downside = []
    if context.get("expected_shortfall_95") is not None:
        downside.append(
            f"95% expected shortfall is {{_percentage(context.get('expected_shortfall_95'))}}"
        )
    if drawdown is not None:
        downside.append(f"Maximum observed drawdown is {{_percentage(drawdown)}}")
    downside_summary = (
        "; ".join(downside) + "."
        if downside
        else "Complete tail-risk statistics were not available for this run."
    )
    narrative = (
        f"The largest valued position is "
        f"{{_percentage(context.get('largest_weight'), decimals=1)}} of NAV, making concentration "
        f"the principal review question. {{downside_summary}}"
    )
    changed_items = []
    if context.get("daily_return") is not None:
        changed_items.append(f"Latest daily return: {{_percentage(context.get('daily_return'))}}.")
    if context.get("annualized_volatility") is not None:
        changed_items.append(
            f"Annualized volatility: {{_percentage(context.get('annualized_volatility'))}}."
        )
    risk_measures = []
    if context.get("var_95") is not None:
        risk_measures.append(f"95% historical VaR is {{_percentage(context.get('var_95'))}}")
    if context.get("expected_shortfall_95") is not None:
        risk_measures.append(
            f"95% expected shortfall is {{_percentage(context.get('expected_shortfall_95'))}}"
        )
    risk_interpretation = (
        "; ".join(risk_measures) + "."
        if risk_measures
        else "No complete tail-risk statistic was available; interpretation remains concentration-led."
    )
    report_sections = [
        {{"section_id": "executive_signal", "title": "Executive signal", "content": narrative}},
        {{
            "section_id": "what_changed",
            "title": "What changed",
            "items": changed_items,
        }},
        {{
            "section_id": "risk_interpretation",
            "title": "Risk interpretation",
            "content": risk_interpretation,
        }},
        {{
            "section_id": "exposure_and_mandate",
            "title": "Exposure and mandate",
            "content": context.get("canonical_exposure_interpretation", issue),
        }},
        {{
            "section_id": "uncertainty",
            "title": "Uncertainty",
            "items": [
                "The statistics describe the priced sleeve when valuation coverage is incomplete."
            ] if context.get("evidence_state") != "complete" else [],
        }},
        {{
            "section_id": "review_actions",
            "title": "Review actions",
            "items": ["Compare the largest exposure with the approved mandate limit."],
        }},
    ]
    return {{
        "iteration": iteration,
        "rendered_prompt": rendered_prompt,
        "narrative": narrative,
        "model_output": {{
            "report_sections": report_sections,
            "material_findings": [],
            "uncertainties": report_sections[4]["items"],
            "recommended_review_steps": report_sections[5]["items"],
        }},
        "trace": _event(
            state,
            "draft",
            f"Produced {{BLUEPRINT['output_contract']}} revision {{iteration}}.",
        ),
    }}


def evidence_critic(state: AgentState) -> AgentState:
    context = state.get("overall_context") or state.get("context", {{}})
    evidence_state = context.get("evidence_state", "complete")
    missing = evidence_state in {{"missing", "partial"}}
    semantic = state.get("semantic_verification", {{}})
    semantic_attention = semantic.get("status") == "failed"
    strict_failed = False
    if BLUEPRINT["structured_output"]["rendering_target"] == "markdown_document":
        from agent_studio import validate_concentration_review_draft
        strict_failed = validate_concentration_review_draft(state.get("draft_output", {{}})).get("status") == "failed"
    critique = (
        f"Semantic verification found {{len(semantic.get('conflicts', []))}} conflict(s); "
        "the draft must remain review-bound."
        if semantic_attention or strict_failed
        else
        f"Evidence coverage is {{evidence_state}}; full-portfolio and causal claims must "
        "remain explicitly qualified."
        if missing
        else "Evidence references and normalized semantic facts passed deterministic review."
    )
    return {{
        "critique": critique,
        "critique_requires_revision": bool(
            semantic_attention or strict_failed or context.get("force_critic_revision", False)
        ),
        "trace": _event(state, "evidence_critic", critique),
    }}


def verify_semantics(state: AgentState) -> AgentState:
    if BLUEPRINT["structured_output"]["rendering_target"] == "markdown_document":
        from agent_studio import validate_concentration_review_draft
        verification = validate_concentration_review_draft(state.get("draft_output", {{}}))
        return {{
            "semantic_verification": verification,
            "trace": _event(state, "verify_semantics", f"Checked {{verification['checked_field_count']}} strict Markdown fields; {{len(verification['conflicts'])}} conflict(s) found."),
        }}
    from agent_studio import verify_interpretation_semantics

    context = state.get("overall_context") or state.get("context", {{}})
    verification = verify_interpretation_semantics(
        context,
        state.get("model_output", {{}}),
        state.get("narrative", ""),
        state.get("semantic_facts", []),
    )
    return {{
        "semantic_verification": verification,
        "trace": _event(
            state,
            "verify_semantics",
            f"Checked {{verification['checked_field_count']}} semantic fields; "
            f"{{len(verification['conflicts'])}} contradiction(s) found.",
        ),
    }}


def route_after_critic(state: AgentState) -> str:
    if (
        BLUEPRINT["pattern"] in {{"reflection", "human_review"}}
        and state.get("critique_requires_revision", False)
        and state.get("iteration", 0) < BLUEPRINT["max_iterations"]
    ):
        return "revise"
    return "continue"


def human_review(state: AgentState) -> AgentState:
    decision = interrupt(
        {{
            "question": "Approve this effect-free agent output?",
            "output_contract": BLUEPRINT["output_contract"],
            "narrative": state.get("narrative", ""),
            "critique": state.get("critique", ""),
            "semantic_verification": state.get("semantic_verification", {{}}),
        }}
    )
    return {{
        "review": decision,
        "trace": _event(state, "human_review", "Human review response recorded."),
    }}


def build_graph():
    builder = StateGraph(AgentState)
    builder.add_node("load_context", load_context)
    builder.add_node("gather_evidence", gather_evidence)
    builder.add_node("assemble_context", assemble_context)
    builder.add_node("draft", draft)
    builder.add_node("verify_semantics", verify_semantics)
    if BLUEPRINT["pattern"] in {{"tool_loop", "reflection", "human_review"}}:
        builder.add_node("evidence_critic", evidence_critic)
    if BLUEPRINT["pattern"] == "human_review":
        builder.add_node("human_review", human_review)

    builder.add_edge(START, "load_context")
    builder.add_edge("load_context", "gather_evidence")
    builder.add_edge("gather_evidence", "assemble_context")
    builder.add_edge("assemble_context", "draft")
    builder.add_edge("draft", "verify_semantics")
    if BLUEPRINT["pattern"] == "direct":
        builder.add_edge("verify_semantics", END)
    else:
        builder.add_edge("verify_semantics", "evidence_critic")
        if BLUEPRINT["pattern"] == "reflection":
            builder.add_conditional_edges(
                "evidence_critic",
                route_after_critic,
                {{"revise": "draft", "continue": END}},
            )
        elif BLUEPRINT["pattern"] == "human_review":
            builder.add_conditional_edges(
                "evidence_critic",
                route_after_critic,
                {{"revise": "draft", "continue": "human_review"}},
            )
            builder.add_edge("human_review", END)
        else:
            builder.add_edge("evidence_critic", END)
    checkpointer = InMemorySaver() if BLUEPRINT["memory"] == "in_memory" else None
    return builder.compile(checkpointer=checkpointer)
'''


def compile_blueprint(
    blueprint: AgentBlueprint, *, persist: bool = True
) -> dict[str, Any]:
    source = _module_source(blueprint)
    compile(source, "<generated-agent>", "exec")
    digest = hashlib.sha256(
        json.dumps(
            blueprint.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()[:16]
    slug = re.sub(r"[^a-z0-9]+", "-", blueprint.name.casefold()).strip("-")[:48]
    artifact_id = f"{slug}-{digest}"
    artifact_paths: dict[str, str] = {}
    if persist:
        directory = GENERATED_ROOT / artifact_id
        directory.mkdir(parents=True, exist_ok=True)
        blueprint_path = directory / "blueprint.json"
        module_path = directory / "agent.py"
        blueprint_path.write_text(
            json.dumps(blueprint.model_dump(mode="json"), indent=2, sort_keys=True)
            + "\n"
        )
        module_path.write_text(source)
        artifact_paths = {
            "directory": str(directory),
            "blueprint": str(blueprint_path),
            "python": str(module_path),
        }
    spec = graph_spec(blueprint)
    return {
        "artifact_id": artifact_id,
        "blueprint": blueprint.model_dump(mode="json"),
        "graph": spec,
        "source": source,
        "artifacts": artifact_paths,
        "checks": [
            {
                "name": "Blueprint schema",
                "status": "passed",
                "detail": "All fields, enums, ranges, and cross-field rules are valid.",
            },
            {
                "name": "Capability allow-list",
                "status": "passed",
                "detail": (
                    f"{len(blueprint.capability_latches)} capability latches have "
                    "invocation, binding, requirement, and failure policies."
                ),
            },
            {
                "name": "Prompt contract",
                "status": "passed",
                "detail": (
                    f"{len(blueprint.prompt_messages)} ordered Prompt Messages and "
                    f"{len(blueprint.prompt_template.variables)} PromptTemplate variables."
                ),
            },
            {
                "name": "State management",
                "status": "passed",
                "detail": (
                    f"{len(blueprint.state_schema)} unique typed state fields with "
                    "explicit sources and reducers."
                ),
            },
            {
                "name": "Routing and memory",
                "status": "passed",
                "detail": (
                    f"{blueprint.routing.strategy} routing · "
                    f"{blueprint.memory_rules.scope} memory scope · "
                    f"{blueprint.routing.max_iterations} maximum iterations."
                ),
            },
            {
                "name": "Structured output",
                "status": "passed",
                "detail": (
                    f"{blueprint.structured_output.name} defines "
                    f"{len(blueprint.structured_output.fields)} typed fields · "
                    f"{blueprint.structured_output.presentation.composition} composition · "
                    f"{blueprint.structured_output.rendering_target} target · strict schema."
                ),
            },
            {
                "name": "Experimental wrapper",
                "status": (
                    "not_applicable"
                    if blueprint.agent_class == "static_system"
                    else "passed"
                ),
                "detail": (
                    "Static System Agents do not enter portfolio-risk experiments."
                    if blueprint.agent_class == "static_system"
                    else (
                        f"Headless {blueprint.experimental_role.replace('_', ' ')} · "
                        "presentation artifacts labelled and excluded · runtime behaviour captured."
                    )
                ),
            },
            {
                "name": "Multi-pass assembly",
                "status": "passed",
                "detail": (
                    f"{len(blueprint.output_assembly.passes)} bounded passes with a "
                    f"{blueprint.output_assembly.max_total_output_tokens:,}-token total ceiling."
                ),
            },
            {
                "name": "Python syntax",
                "status": "passed",
                "detail": "Generated module compiles without syntax errors.",
            },
            {
                "name": "Portfolio effects",
                "status": "passed",
                "detail": "effects_allowed is fixed to false.",
            },
            {
                "name": "Human boundary",
                "status": "passed" if blueprint.human_review else "not_requested",
                "detail": (
                    "LangGraph interrupt and checkpoint are compiled."
                    if blueprint.human_review
                    else "This agent produces an effect-free output without an interrupt."
                ),
            },
        ],
        "compiler_version": COMPILER_VERSION,
    }


def _scenario_context(scenario: str) -> dict[str, Any]:
    contexts = {
        "routine": {
            "as_of_date": "2008-09-15",
            "daily_return": 0.003,
            "var_95": 0.014,
            "drawdown": -0.012,
            "largest_weight": 0.18,
            "cash_weight": 0.08,
            "stress_loss": -0.041,
            "eligible_event": "No eligible material event",
            "evidence_state": "complete",
            "issue": "No mandate breach was detected.",
        },
        "concentration": {
            "as_of_date": "2008-09-15",
            "daily_return": -0.004,
            "var_95": 0.018,
            "drawdown": -0.026,
            "largest_weight": 0.31,
            "cash_weight": 0.05,
            "stress_loss": -0.072,
            "eligible_event": "No eligible material event",
            "evidence_state": "complete",
            "issue": "The 31% largest position exceeds the 25% concentration limit.",
        },
        "loss": {
            "as_of_date": "2008-09-15",
            "daily_return": -0.031,
            "var_95": 0.026,
            "drawdown": -0.061,
            "largest_weight": 0.21,
            "cash_weight": 0.07,
            "stress_loss": -0.094,
            "eligible_event": "Broad negative market event",
            "evidence_state": "complete",
            "issue": "The 3.1% daily loss exceeds the 2% review threshold.",
        },
        "missing": {
            "as_of_date": "2008-09-15",
            "daily_return": -0.009,
            "var_95": 0.019,
            "drawdown": -0.033,
            "largest_weight": 0.23,
            "cash_weight": 0.06,
            "stress_loss": -0.067,
            "eligible_event": "Event source unavailable",
            "evidence_state": "missing",
            "issue": "The cause of the risk change cannot be evidenced.",
        },
    }
    synthetic_values = {
        "routine": ([18, 18, 18, 18, 20], 8),
        "concentration": ([31, 24, 20, 20], 5),
        "loss": ([21, 20, 18, 17, 17], 7),
        "missing": ([23, 20, 18, 17, 16], 6),
    }
    position_values, cash_value = synthetic_values[scenario]
    positions = [
        {
            "instrument_id": f"instrument-{chr(97 + index)}",
            "quantity": "1",
            "price": None if scenario == "missing" and index == 0 else str(value),
            "currency": "USD",
        }
        for index, value in enumerate(position_values)
    ]
    return {
        "portfolio_name": "Synthetic diversified research portfolio",
        "data_truth": "controlled_synthetic_fixture",
        "synthetic_method": "fixed deterministic formula",
        "maximum_drawdown": abs(float(contexts[scenario]["drawdown"])),
        "mandate_limits": {"single_position_max_weight": 0.25},
        "mandate_status": (
            "concentration review required"
            if scenario == "concentration"
            else "evidence incomplete"
            if scenario == "missing"
            else "within reviewed limits"
        ),
        "event_context": contexts[scenario]["eligible_event"],
        "news_context": contexts[scenario]["eligible_event"],
        "workflow_cycle_id": f"synthetic-{scenario}-2008-09-15",
        "portfolio_capability_input": {
            "snapshot_id": f"synthetic-{scenario}-2008-09-15",
            "as_of": "2008-09-15T23:59:59+00:00",
            "retrieved_at": "2008-09-15T23:59:59+00:00",
            "base_currency": "USD",
            "positions": positions,
            "cash_balances": [{"currency": "USD", "amount": str(cash_value)}],
            "source_id": "agent-studio-synthetic-behavior-sample",
            "source_type": "synthetic_behavior_sample",
            "source_reference": f"synthetic://agent-studio/{scenario}",
            "source_label": f"Generated synthetic behavior sample: {scenario}",
            "source_detail": (
                "Used deliberately synthetic positions, prices and cash supplied by "
                "a code-defined scenario. This is not a reviewed fixture."
            ),
            "evidence_id": f"synthetic-evidence:{scenario}:2008-09-15",
        },
        **contexts[scenario],
    }


def synthetic_behavior_provenance(scenario: str) -> dict[str, Any]:
    return {
        "data_mode": "synthetic_behavior_sample",
        "data_truth": "controlled_synthetic_fixture",
        "label": f"CONTROLLED SYNTHETIC FIXTURE · {scenario}",
        "scenario": scenario,
        "licensed_data_used": False,
        "point_in_time": False,
        "reviewed_fixture": False,
        "warning": (
            "Values are generated by a fixed formula for wiring and behavior testing. "
            "They are neither historically calibrated nor empirical observations."
        ),
    }


def historically_calibrated_synthetic_context(
    *,
    scenario: str,
    historical_values: list[dict[str, Any]],
    portfolio_id: str,
    as_of: str,
    seed: int = 20260810,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Fit a deterministic synthetic path without retaining licensed rows.

    The first 80% of eligible returns calibrates a simple Gaussian process. The
    final 20% is named and reserved as an out-of-sample evaluation window; it is
    never used by the generator. This is a research fixture, not a claim that a
    Gaussian process reproduces actual market tails.
    """

    ordered = sorted(
        (
            {"observed_at": str(item["observed_at"]), "portfolio_value": float(item["portfolio_value"])}
            for item in historical_values
            if item.get("portfolio_value") not in (None, 0)
        ),
        key=lambda item: item["observed_at"],
    )
    returns = [
        ordered[index]["portfolio_value"] / ordered[index - 1]["portfolio_value"] - 1
        for index in range(1, len(ordered))
        if ordered[index - 1]["portfolio_value"]
    ]
    if len(returns) < 25:
        raise ValueError(
            "historical calibration requires at least 25 eligible portfolio return observations"
        )
    split = min(len(returns) - 5, max(20, math.floor(len(returns) * 0.8)))
    calibration_returns = returns[:split]
    oos_returns = returns[split:]
    mean_return = statistics.fmean(calibration_returns)
    daily_volatility = statistics.pstdev(calibration_returns)
    if not math.isfinite(daily_volatility) or daily_volatility <= 0:
        raise ValueError("historical calibration produced no positive finite volatility")

    generator = random.Random(seed)
    generated_count = min(252, max(60, len(calibration_returns)))
    generated_returns = [
        max(-0.25, min(0.25, mean_return + daily_volatility * generator.gauss(0, 1)))
        for _ in range(generated_count)
    ]
    if scenario == "loss":
        generated_returns[-1] = -max(0.03, 3 * daily_volatility)
    elif scenario == "routine":
        generated_returns[-1] = mean_return

    generated_values = []
    value = 100.0
    synthetic_start = datetime(2000, 1, 1, tzinfo=timezone.utc)
    for index, item in enumerate(generated_returns):
        value *= 1 + item
        generated_values.append(
            {
                "observed_at": synthetic_start.date().isoformat(),
                "portfolio_value": round(value, 10),
            }
        )
        synthetic_start += timedelta(days=1)

    context = _scenario_context(scenario)
    calibration_digest = "sha256:" + hashlib.sha256(
        json.dumps(
            {
                "portfolio_id": portfolio_id,
                "calibration_start": ordered[0]["observed_at"],
                "calibration_end": ordered[split]["observed_at"],
                "observation_count": len(calibration_returns),
                "mean": mean_return,
                "volatility": daily_volatility,
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()
    context.update(
        {
            "portfolio_name": "Historically calibrated synthetic portfolio",
            "data_truth": "historically_calibrated_synthetic",
            "synthetic_method": "seeded Gaussian daily-return process",
            "as_of_date": as_of,
            "workflow_cycle_id": f"calibrated-synthetic-{scenario}-{as_of}",
            "daily_return": None,
            "var_95": None,
            "drawdown": None,
            "maximum_drawdown": None,
            "calibration_summary": {
                "model": "gaussian_daily_returns/v1",
                "seed": seed,
                "in_sample_observations": len(calibration_returns),
                "reserved_oos_observations": len(oos_returns),
                "daily_mean": mean_return,
                "daily_volatility": daily_volatility,
                "calibration_digest": calibration_digest,
            },
        }
    )
    source = context["portfolio_capability_input"]
    source.update(
        {
            "snapshot_id": f"calibrated-synthetic-{scenario}-{as_of}",
            "as_of": f"{as_of}T23:59:59+00:00",
            "retrieved_at": f"{as_of}T23:59:59+00:00",
            "source_id": "agent-studio-historically-calibrated-synthetic",
            "source_type": "historically_calibrated_synthetic",
            "source_reference": f"synthetic-calibration://{calibration_digest.removeprefix('sha256:')}",
            "source_label": "Synthetic fixture calibrated from licensed historical aggregates",
            "source_detail": (
                "Anonymous positions use a fixed scenario formula. The synthetic return path "
                "uses only aggregate in-sample calibration parameters; no licensed row or "
                "native instrument identifier is retained."
            ),
            "evidence_id": f"synthetic-calibration:{calibration_digest.removeprefix('sha256:')[:24]}",
        }
    )
    context["metric_pack_input"] = {
        "analysis_id": f"metric-pack:calibrated-synthetic:{scenario}:{as_of}",
        "snapshot_id": source["snapshot_id"],
        "as_of": source["as_of"],
        "base_currency": "USD",
        "observations": generated_values,
        "included_holdings": [item["instrument_id"] for item in source["positions"]],
        "excluded_holdings": [],
        "coverage": "complete anonymous synthetic portfolio",
        "source_id": "agent-studio-historically-calibrated-synthetic",
        "source_type": "historically_calibrated_synthetic",
        "source_reference": source["source_reference"],
        "evidence_id": source["evidence_id"],
        "synthetic": True,
    }
    provenance = {
        "data_mode": "historically_calibrated_synthetic",
        "data_truth": "historically_calibrated_synthetic",
        "label": f"HISTORICALLY CALIBRATED SYNTHETIC · {scenario}",
        "scenario": scenario,
        "licensed_data_used_for_calibration": True,
        "licensed_rows_retained": False,
        "point_in_time": True,
        "portfolio_id_used_for_local_calibration": portfolio_id,
        "as_of": as_of,
        "calibration_window": {
            "start": ordered[0]["observed_at"],
            "end": ordered[split]["observed_at"],
            "observations": len(calibration_returns),
        },
        "reserved_oos_window": {
            "start": ordered[split + 1]["observed_at"],
            "end": ordered[-1]["observed_at"],
            "observations": len(oos_returns),
            "used_for_generation": False,
        },
        "calibration_digest": calibration_digest,
        "model": "gaussian_daily_returns/v1",
        "seed": seed,
        "limitations": [
            "Synthetic observations are not empirical evidence and cannot validate historical performance.",
            "A Gaussian process does not reproduce all market tails, regimes or cross-sectional dependence.",
            "The reserved OOS window must be evaluated separately and must never tune this fixture version.",
        ],
    }
    return context, provenance


def _structured_field_schema(field: StructuredOutputFieldSpec) -> dict[str, Any]:
    supported_formats = {"date", "date-time", "duration", "email", "uuid"}

    def make_strict(value: Any) -> None:
        if isinstance(value, dict):
            value.pop("default", None)
            if value.get("type") == "object":
                properties = value.get("properties")
                if not isinstance(properties, dict):
                    raise ValueError("nested object schemas require properties")
                value["required"] = list(properties)
                value["additionalProperties"] = False
            for child in value.values():
                make_strict(child)
        elif isinstance(value, list):
            for child in value:
                make_strict(child)

    if field.value_type == "object":
        if field.nested_schema_json:
            schema: dict[str, Any] = json.loads(field.nested_schema_json)
            if schema.get("type") != "object":
                raise ValueError(f"{field.name} nested schema must be an object")
        else:
            schema = {
                "type": "object",
                "properties": {
                    "content": {"type": "string"},
                    "evidence_refs": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["content", "evidence_refs"],
                "additionalProperties": False,
            }
    elif field.value_type == "array":
        item_schema = (
            json.loads(field.nested_schema_json)
            if field.nested_schema_json
            else {"type": "string"}
        )
        schema = {"type": "array", "items": item_schema}
    else:
        schema = {"type": field.value_type}
    make_strict(schema)
    schema["description"] = (
        f"{field.description} Validation: {field.validation_rule}"
    )
    if field.enum_values and field.value_type == "string":
        schema["enum"] = field.enum_values
    if field.format in supported_formats and field.value_type == "string":
        schema["format"] = field.format
    if field.nullable:
        return {"anyOf": [schema, {"type": "null"}]}
    return schema


def _pass_response_schema(
    blueprint: AgentBlueprint, output_pass: OutputPassSpec
) -> dict[str, Any]:
    fields = {
        field.name: field
        for field in blueprint.structured_output.fields
        if field.name in output_pass.target_fields
    }
    properties = {
        field_name: _structured_field_schema(field)
        for field_name, field in fields.items()
    }
    return {
        "type": "object",
        "properties": {
            "field_updates": {
                "type": "object",
                "properties": properties,
                "required": list(properties),
                "additionalProperties": False,
            },
            "pass_summary": {"type": "string"},
            "quality_notes": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["field_updates", "pass_summary", "quality_notes"],
        "additionalProperties": False,
    }


def _synthetic_schema_value(schema: dict[str, Any], label: str) -> Any:
    value_type = schema.get("type")
    if value_type == "object":
        return {
            name: _synthetic_schema_value(child, name.replace("_", " ").title())
            for name, child in schema.get("properties", {}).items()
        }
    if value_type == "array":
        return [_synthetic_schema_value(schema.get("items", {"type": "string"}), label)]
    if value_type == "boolean":
        return True
    if value_type in {"number", "integer"}:
        return 1
    return f"Synthetic {label}"


def _preview_value(
    field: StructuredOutputFieldSpec, context: dict[str, Any], pass_title: str
) -> Any:
    issue = str(context.get("issue", "No material issue supplied."))
    if field.value_type == "boolean":
        return True
    if field.value_type in {"number", "integer"}:
        return 1
    if field.value_type == "array":
        if field.semantic_role == "recommendations":
            return [
                "Review the flagged risk with the portfolio manager.",
                "Preserve the point-in-time evidence boundary.",
            ]
        if field.semantic_role == "html_fragment":
            return [
                "<section><h2>Risk chart</h2><p>Sandboxed synthetic HTML "
                f"for {issue}</p></section>"
            ]
        if field.semantic_role == "d3_spec":
            return [
                json.dumps(
                    {
                        "mark": "bar",
                        "x": ["Daily loss", "VaR", "Stress"],
                        "y": [
                            abs(float(context.get("daily_return", 0))),
                            abs(float(context.get("var_95", 0))),
                            abs(float(context.get("stress_loss", 0))),
                        ],
                    }
                )
            ]
        return [
            _synthetic_schema_value(json.loads(field.nested_schema_json), field.title)
        ] if field.nested_schema_json else [
            f"Synthetic {field.semantic_role} item for {issue}"
        ]
    if field.value_type == "object":
        if field.nested_schema_json:
            return _synthetic_schema_value(
                json.loads(field.nested_schema_json), field.title
            )
        return {
            "content": f"Synthetic {field.semantic_role} produced during {pass_title}.",
            "evidence_refs": ["OverallDefaultContext", "MetricPack"],
        }
    if field.semantic_role in {"html_fragment", "dashboard"}:
        return (
            "<section><h2>Risk chart</h2><p>Sandboxed synthetic HTML preview "
            f"for {issue}</p></section>"
        )
    if field.semantic_role == "d3_spec":
        return json.dumps(
            {
                "mark": "bar",
                "x": ["Daily loss", "VaR", "Stress"],
                "y": [
                    abs(float(context.get("daily_return", 0))),
                    abs(float(context.get("var_95", 0))),
                    abs(float(context.get("stress_loss", 0))),
                ],
            }
        )
    return (
        f"{field.title}: {issue} This synthetic section was produced during "
        f"{pass_title} and remains effect-free."
    )


def _merge_output_patch(
    artifact: dict[str, Any],
    updates: dict[str, Any],
    fields: dict[str, StructuredOutputFieldSpec],
    operation: str,
) -> dict[str, Any]:
    merged = dict(artifact)
    for name, value in updates.items():
        strategy = fields[name].merge_strategy
        effective = operation if operation != "replace" else strategy
        if effective in {"append", "merge"} and isinstance(value, list):
            prior = merged.get(name)
            merged[name] = [*(prior if isinstance(prior, list) else []), *value]
        elif effective == "merge" and isinstance(value, dict):
            prior = merged.get(name)
            merged[name] = {**(prior if isinstance(prior, dict) else {}), **value}
        else:
            merged[name] = value
    return merged


def run_output_pass(request: OutputPassRunRequest) -> dict[str, Any]:
    output_pass = next(
        (
            value
            for value in request.blueprint.output_assembly.passes
            if value.pass_id == request.pass_id
        ),
        None,
    )
    if output_pass is None:
        raise ValueError(f"unknown output assembly pass: {request.pass_id}")
    fields = {
        field.name: field
        for field in request.blueprint.structured_output.fields
        if field.name in output_pass.target_fields
    }
    context = _scenario_context(request.scenario)
    started = time.perf_counter()
    if request.mode == "preview":
        updates = {
            name: _preview_value(field, context, output_pass.title)
            for name, field in fields.items()
        }
        pass_summary = (
            f"Deterministic preview populated {len(updates)} fields for "
            f"{output_pass.title}."
        )
        quality_notes = [
            "Synthetic values demonstrate assembly behavior; they are not model analysis."
        ]
        receipt = {
            "provider": "deterministic_preview",
            "model": None,
            "response_id": None,
            "input_tokens": 0,
            "output_tokens": 0,
            "store": False,
        }
    else:
        api_key = _keychain_key(include_value=True)
        if not api_key:
            raise RuntimeError("OpenAI credential is unavailable")
        from openai import OpenAI

        client = OpenAI(api_key=str(api_key))
        response = client.responses.create(
            model=COST_OPTIMIZED_LLM_MODEL,
            store=False,
            tools=[],
            input=[
                {
                    "role": "system",
                    "content": [
                        {
                            "type": "input_text",
                            "text": (
                                "You are executing one bounded pass of a structured "
                                "portfolio-risk agent. Populate only the requested output "
                                "fields. Preserve prior sections, use only supplied "
                                "point-in-time context, disclose uncertainty, never invent "
                                "evidence, and never create portfolio effects. Return the "
                                "strict field patch, a concise pass summary, and quality notes."
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
                                    "agent_name": request.blueprint.name,
                                    "agent_purpose": request.blueprint.purpose,
                                    "instructions": request.blueprint.system_instructions,
                                    "output_contract": request.blueprint.structured_output.model_dump(
                                        mode="json"
                                    ),
                                    "pass": output_pass.model_dump(mode="json"),
                                    "point_in_time_context": context,
                                    "current_artifact": request.current_artifact,
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
                    "name": f"pass_{output_pass.pass_id}"[:64],
                    "strict": True,
                    "schema": _pass_response_schema(request.blueprint, output_pass),
                }
            },
            max_output_tokens=output_pass.max_output_tokens,
        )
        payload = json.loads(response.output_text)
        updates = payload["field_updates"]
        pass_summary = payload["pass_summary"]
        quality_notes = payload["quality_notes"]
        usage = getattr(response, "usage", None)
        receipt = {
            "provider": "openai_responses",
            "model": getattr(response, "model", request.model),
            "response_id": getattr(response, "id", None),
            "input_tokens": int(getattr(usage, "input_tokens", 0) or 0),
            "output_tokens": int(getattr(usage, "output_tokens", 0) or 0),
            "store": False,
        }
    artifact = _merge_output_patch(
        request.current_artifact, updates, fields, output_pass.operation
    )
    receipt["elapsed_ms"] = round((time.perf_counter() - started) * 1000, 2)
    return {
        "pass_id": output_pass.pass_id,
        "pass_title": output_pass.title,
        "updated_fields": list(updates),
        "field_updates": updates,
        "artifact": artifact,
        "pass_summary": pass_summary,
        "quality_notes": quality_notes,
        "receipt": receipt,
        "human_review_required": (
            output_pass.human_review_after
            or request.blueprint.output_assembly.human_review_between_passes
        ),
    }


def _json_text(value: Any) -> str:
    return json.dumps(value, indent=2, sort_keys=True, default=str) + "\n"


def _run_activity(result: dict[str, Any]) -> list[dict[str, Any]]:
    activities: list[dict[str, Any]] = [
        {
            "sequence": 1,
            "kind": "input",
            "actor": "System",
            "title": "Input context accepted",
            "detail": (
                f"{result['data_label']} source data was frozen for this run before the "
                "agent graph started. This is not yet OverallDefaultContext; that contract "
                "is assembled only after the calculations complete. "
                + (
                    f"Live model interpretation was enabled with {result.get('execution_model')}."
                    if result.get("execution_mode") == "live_llm"
                    else "The graph used deterministic interpretation; no model was called."
                )
            ),
        }
    ]
    sequence = 2
    final_state = result.get("final_state", {})
    capability_results = final_state.get("capability_results", [])
    research_plan = final_state.get("research_plan")
    for trace in result.get("trace", []):
        node = trace.get("node", "agent")
        kind = (
            "capability"
            if node == "gather_evidence"
            else "critique"
            if node == "evidence_critic"
            else "review"
            if node == "human_review"
            else "rationale"
        )
        activities.append(
            {
                "sequence": sequence,
                "kind": kind,
                "actor": "Agent" if kind != "review" else "Human review boundary",
                "title": node.replace("_", " ").title(),
                "detail": trace.get("detail", ""),
            }
        )
        sequence += 1
        if node == "draft" and final_state.get("model_receipts"):
            receipt = final_state["model_receipts"][-1]
            activities.append(
                {
                    "sequence": sequence,
                    "kind": "llm_call",
                    "actor": "Live model",
                    "title": "Structured portfolio-risk interpretation",
                    "detail": (
                        "A real OpenAI Responses API call interpreted the frozen context "
                        "and completed the declared output contract."
                    ),
                    "payload": {
                        "model": receipt.get("model"),
                        "response_id": receipt.get("response_id"),
                        "rationale_summary": final_state.get("rationale_summary", []),
                        "confidence": final_state.get("model_output", {}).get("confidence"),
                    },
                }
            )
            sequence += 1
            activities.append(
                {
                    "sequence": sequence,
                    "kind": "llm_receipt",
                    "actor": "OpenAI Responses API",
                    "title": "Verifiable model-call receipt",
                    "detail": (
                        "The provider response identifier, model, token usage, latency and "
                        "digests were saved. The response was not stored by the provider."
                    ),
                    "payload": receipt,
                }
            )
            sequence += 1
        if node == "verify_semantics":
            verification = final_state.get("semantic_verification", {})
            activities.append(
                {
                    "sequence": sequence,
                    "kind": "semantic_verification",
                    "actor": "Deterministic semantic verifier",
                    "title": (
                        "Semantic consistency passed"
                        if verification.get("status") == "passed"
                        else "Semantic consistency needs review"
                    ),
                    "detail": (
                        f"Checked {verification.get('checked_field_count', 0)} normalized "
                        f"fields and found {len(verification.get('conflicts', []))} "
                        "contradiction(s)."
                    ),
                    "payload": verification,
                }
            )
            sequence += 1
        if node == "gather_evidence":
            if research_plan:
                activities.append(
                    {
                        "sequence": sequence,
                        "kind": "research_plan",
                        "actor": "Agent",
                        "title": research_plan.get("title", "Research plan"),
                        "detail": research_plan.get("outcome", ""),
                        "payload": {"steps": research_plan.get("steps", [])},
                    }
                )
                sequence += 1
            context_bindings = []
            for call in capability_results:
                if call.get("execution_mode") != "canonical_registry":
                    context_bindings.append(call)
                    continue
                canonical_id = call.get("canonical_capability_id") or call.get(
                    "capability", "registered capability"
                )
                activities.append(
                    {
                        "sequence": sequence,
                        "kind": "capability_prepare",
                        "actor": "Data adapter",
                        "title": f"Prepare {call.get('request', {}).get('contract', 'capability request')}",
                        "detail": (
                            "Located the frozen data, formatted the exact request and "
                            "validated it before capability invocation."
                            + (
                                " An identical slow, effect-free result was reused from "
                                "capability memory."
                                if call.get("receipt", {}).get("memory_reused")
                                else ""
                            )
                        ),
                        "payload": {
                            "request": call.get("request", {}),
                            "stages": call.get("stages", [])[:-1],
                        },
                    }
                )
                sequence += 1
                activities.append(
                    {
                        "sequence": sequence,
                        "kind": "capability_call",
                        "actor": "Canonical capability",
                        "title": canonical_id,
                        "detail": call.get("detail", "Capability execution completed."),
                        "status": call.get("status"),
                        "payload": call.get("result", {}),
                    }
                )
                sequence += 1
                activities.append(
                    {
                        "sequence": sequence,
                        "kind": "capability_receipt",
                        "actor": "Capability registry",
                        "title": "Traceable execution receipt",
                        "detail": (
                            "The exact input, output, evidence, timing and empty effects were "
                            "registered. Successful effect-free calls above the memory threshold "
                            "can be reused on an identical point-in-time input."
                        ),
                        "payload": call.get("receipt", {}),
                    }
                )
                sequence += 1
            if context_bindings:
                activities.append(
                    {
                        "sequence": sequence,
                        "kind": "context_binding",
                        "actor": "Agent",
                        "title": "Existing supplied-context bindings retained",
                        "detail": (
                            f"{len(context_bindings)} additional blueprint latches still "
                            "read the frozen context in this first increment; they are not "
                            "misrepresented as canonical capability executions."
                        ),
                        "payload": {
                            "bindings": [
                                {
                                    "name": call.get("capability"),
                                    "status": call.get("status"),
                                }
                                for call in context_bindings
                            ]
                        },
                    }
                )
                sequence += 1
    return activities


def _run_transcript(result: dict[str, Any]) -> str:
    state = result.get("final_state", {})
    lines = [
        f"# Agent run {result['run_id']}",
        "",
        f"- Agent: {result['agent_name']}",
        f"- Data: {result['data_label']}",
        f"- Status: {result['status']}",
        f"- Created: {result['created_at']}",
        "",
        "## Assignment",
        "",
        result.get("assignment_summary", "Review the supplied context."),
        "",
        "## Agent work record",
        "",
    ]
    for item in result.get("activity", []):
        lines.extend(
            [
                f"### {item['sequence']}. {item['title']}",
                "",
                item.get("detail", ""),
                "",
            ]
        )
        if "payload" in item:
            lines.extend(["```json", json.dumps(item["payload"], indent=2), "```", ""])
    lines.extend(
        [
            "## Agent output",
            "",
            state.get("narrative", "No narrative output was produced."),
            "",
            "## Evidence review",
            "",
            state.get("critique", "No separate evidence critique was produced."),
            "",
            "## Human review",
            "",
            json.dumps(state.get("review", {}), indent=2),
            "",
        ]
    )
    return "\n".join(lines)


def _display_percentage(value: Any, *, decimals: int = 1) -> str:
    if value is None:
        return "Not calculated"
    try:
        return f"{float(value):.{decimals}%}"
    except (TypeError, ValueError):
        return "Unavailable"


def _run_presentation(result: dict[str, Any]) -> dict[str, Any]:
    state = result.get("final_state", {})
    context = state.get("overall_context") or result.get("input_context", {})
    model_output = state.get("model_output", {}) or {}
    semantic_verification = state.get("semantic_verification", {}) or {}
    provenance = result.get("input_provenance", {})
    review = state.get("review", {}) or {}
    real_data = result.get("data_mode") == "real_duckdb"
    evidence_state = context.get("evidence_state", "unknown")
    canonical_exposure = next(
        (
            item
            for item in state.get("capability_results", [])
            if item.get("canonical_capability_id")
            == "portfolio.exposure.summarize"
        ),
        None,
    )
    canonical_result = (canonical_exposure or {}).get("result", {})
    metric_calls = [
        item
        for item in state.get("capability_results", [])
        if str(item.get("canonical_capability_id") or "").startswith("risk.")
    ]
    missing_metrics = [
        label
        for field, label in (
            ("var_95", "95% historical VaR"),
            ("drawdown", "drawdown"),
            ("annualized_volatility", "annualized volatility"),
            ("expected_shortfall_95", "95% expected shortfall"),
        )
        if context.get(field) is None
    ]
    limitations = list(provenance.get("limitations", []))
    for conflict in semantic_verification.get("conflicts", []):
        limitations.append(
            "Semantic verification conflict for "
            f"{conflict.get('fact_id')}: {conflict.get('claim')}"
        )
    limitations.extend(model_output.get("uncertainties", []))
    if canonical_exposure:
        limitations.extend(canonical_exposure.get("receipt", {}).get("limitations", []))
        if canonical_exposure.get("status") != "succeeded":
            limitations.append(
                "The canonical exposure capability stopped: "
                + canonical_exposure.get("detail", "input validation failed")
            )
    for call in metric_calls:
        limitations.extend(call.get("receipt", {}).get("limitations", []))
        if call.get("status") != "succeeded":
            limitations.append(
                f"{call.get('canonical_capability_id')} stopped: "
                + call.get("detail", "input validation failed")
            )
    if missing_metrics:
        limitations.insert(
            0,
            "The run did not calculate " + ", ".join(missing_metrics) + ".",
        )
    event_context_missing = context.get("event_context") == "Not included" or context.get(
        "news_context"
    ) == "Not included"
    if event_context_missing and not any(
        "event" in item.lower() and "news" in item.lower() for item in limitations
    ):
        limitations.append(
            "Governed event and news context was not included in this test input."
        )
    limitations = list(dict.fromkeys(limitations))

    findings = [context.get("issue", "No portfolio exception was supplied.")]
    findings.extend(
        item.get("claim", "")
        for item in model_output.get("material_findings", [])
        if item.get("claim")
    )
    if canonical_exposure and canonical_exposure.get("status") == "succeeded":
        findings.append(canonical_exposure.get("detail", "Canonical exposure analysis completed."))
    largest_position = canonical_result.get("largest_position") or {}
    largest_weight = largest_position.get("weight", context.get("largest_weight"))
    cash_weight = canonical_result.get("cash_weight", context.get("cash_weight"))
    if largest_weight is not None and float(largest_weight) >= 0.25:
        findings.append(
            f"The largest position represents {_display_percentage(largest_weight)} "
            "of the available portfolio value and should be checked against the mandate."
        )
    if evidence_state != "complete":
        findings.append(
            f"Evidence coverage is {evidence_state}; conclusions must remain qualified."
        )

    next_steps = []
    next_steps.extend(model_output.get("recommended_review_steps", []))
    if missing_metrics:
        next_steps.append(
            "Run the reviewed MetricPack before treating this as the complete daily risk review."
        )
    if event_context_missing:
        next_steps.append(
            "Attach eligible event and news context for the same point-in-time date."
        )
    if largest_weight is not None and float(largest_weight) >= 0.25:
        next_steps.append(
            "Compare the largest position with the applicable mandate concentration limit."
        )
    next_steps.append(
        "A human reviewer should confirm, qualify, or reject the draft before any downstream decision."
    )

    if result.get("status") == "waiting_for_human_review":
        status_label = "Awaiting human review"
        tone = "review"
        title = "The draft is ready, but the human review checkpoint is still open."
    elif limitations:
        status_label = "Completed with limitations"
        tone = "limited"
        title = "The portfolio review is usable, with important evidence limitations."
    else:
        status_label = "Review ready"
        tone = "complete"
        title = "The requested portfolio review is ready for human assessment."

    data_basis = (
        "Point-in-time CRSP/Compustat records from local DuckDB"
        if real_data
        else f"Code-generated synthetic behavior sample: {result.get('scenario', 'test')}"
    )
    review_boundary = (
        "The isolated test automatically released the graph's review interrupt. "
        "It did not authorize a trade, hedge, rebalance, or portfolio mutation."
        if result.get("auto_approved")
        else "The graph remains review-bound and has not created any portfolio effect."
    )
    outcome_sought = str(result.get("assignment_summary") or "Review the supplied context").rstrip(". ")
    return {
        "title": title,
        "status_label": status_label,
        "tone": tone,
        "outcome_sought": outcome_sought,
        "premise": (
            f"Requested outcome: {outcome_sought}. Data basis: {data_basis}."
        ),
        "portfolio": context.get("portfolio_name") or context.get("portfolio_id") or "Supplied portfolio",
        "as_of": context.get("as_of_date") or result.get("as_of") or "Not specified",
        "data_basis": data_basis,
        "execution_basis": (
            f"OpenAI model-backed interpretation · {result.get('execution_model')}"
            if result.get("execution_mode") == "live_llm"
            else "Deterministic LangGraph interpretation · no LLM call"
        ),
        "executive_conclusion": state.get("narrative") or "No final narrative was produced.",
        "report_sections": model_output.get("report_sections", []),
        "observations": [
            {
                "label": "Gross exposure",
                "value": _display_percentage(canonical_result.get("gross_exposure")),
                "note": "Canonical positions divided by portfolio NAV",
            },
            {
                "label": "Largest position",
                "value": _display_percentage(largest_weight),
                "note": largest_position.get("display_name")
                or largest_position.get("instrument_id", "Compare with the mandate limit"),
            },
            {
                "label": "Annualized volatility",
                "value": _display_percentage(context.get("annualized_volatility")),
                "note": "252-day annualization of the priced-sleeve daily return series",
            },
            {
                "label": "Maximum drawdown",
                "value": _display_percentage(context.get("drawdown")),
                "note": "Largest peak-to-trough loss in the available history",
            },
            {
                "label": "95% historical VaR",
                "value": _display_percentage(context.get("var_95")),
                "note": "One-day historical loss threshold for the priced sleeve",
            },
            {
                "label": "95% expected shortfall",
                "value": _display_percentage(context.get("expected_shortfall_95")),
                "note": "Average loss beyond the historical VaR threshold",
            },
            {
                "label": "Cash weight",
                "value": _display_percentage(cash_weight),
                "note": "Share of valued portfolio NAV",
            },
        ],
        "findings": findings,
        "limitations": limitations,
        "next_steps": next_steps,
        "review_boundary": review_boundary,
        "review": review,
        "effects": [],
        "semantic_verification": semantic_verification,
    }


def _report_evidence(result: dict[str, Any]) -> tuple[tuple[str, ...], dict[str, tuple[str, ...]]]:
    """Retain only evidence identifiers already present in run inputs or receipts."""

    state = result.get("final_state", {})
    context = state.get("overall_context") or result.get("input_context", {})
    evidence: set[str] = set()
    for field in ("portfolio_capability_input", "metric_pack_input"):
        item = context.get(field) or {}
        if item.get("evidence_id"):
            evidence.add(str(item["evidence_id"]))
    for call in state.get("capability_results", []):
        evidence.update(
            str(item)
            for item in call.get("receipt", {}).get("evidence_ids", [])
            if item
        )
    finding_evidence: dict[str, tuple[str, ...]] = {}
    for finding in (state.get("model_output") or {}).get("material_findings", []):
        claim = str(finding.get("claim") or "").strip()
        ids = tuple(sorted(set(str(item) for item in finding.get("evidence_ids", []) if item)))
        if claim:
            finding_evidence[claim] = ids
            evidence.update(ids)
    return tuple(sorted(evidence)), finding_evidence


# Historical report compatibility for runs created before ADR-0009. New agent
# runs do not invoke this path or persist presentation files.
def _compose_run_report(result: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    evidence, finding_evidence = _report_evidence(result)
    report = compose_daily_risk_report(
        result["presentation"],
        report_id=f"report:{result['run_id']}",
        evidence_ids=evidence,
        finding_evidence=finding_evidence,
    )
    report = with_rendered_html(report)
    validation = validate_report(report, available_evidence_ids=evidence)
    return report.model_dump(mode="json"), validation.model_dump(mode="json")


def _review_brief(result: dict[str, Any]) -> str:
    from risk_reports import MarkdownReport

    return report_markdown(MarkdownReport.model_validate(result["report"]))


def _persist_run(result: dict[str, Any]) -> dict[str, Any]:
    directory = RUN_ROOT / result["run_id"]
    directory.mkdir(parents=True, exist_ok=False)
    output = {
        "output_contract": result["output_contract"],
        "narrative": result.get("final_state", {}).get("narrative"),
        "critique": result.get("final_state", {}).get("critique"),
        "research_plan": result.get("final_state", {}).get("research_plan"),
        "capability_results": result.get("final_state", {}).get(
            "capability_results", []
        ),
        "model_output": result.get("final_state", {}).get("model_output"),
        "rationale_summary": result.get("final_state", {}).get(
            "rationale_summary", []
        ),
        "model_receipts": result.get("final_state", {}).get("model_receipts", []),
        "semantic_verification": result.get("final_state", {}).get(
            "semantic_verification", {}
        ),
        "review": result.get("final_state", {}).get("review"),
        "status": result["status"],
        "effects": result.get("external_effects", []),
    }
    headless_agent_output = {
        "schema_version": "portfolio-risk.studio-headless-agent-output/v1",
        "run_id": result["run_id"],
        "experimental_role": result.get("blueprint", {}).get("experimental_role"),
        "evaluation_status": "not_admitted_to_experiment",
        "presentation_artifacts": [],
        "output_contract": result["output_contract"],
        "status": result["status"],
        "narrative": output["narrative"],
        "critique": output["critique"],
        "model_output": output["model_output"],
        "evaluation_byproducts": (output["model_output"] or {}).get(
            "evaluation_byproducts"
        ),
        "capability_results": output["capability_results"],
        "semantic_verification": output["semantic_verification"],
        "review": output["review"],
        "effects": output["effects"],
    }
    payloads: dict[str, str] = {
        "input.json": _json_text(result["input_context"]),
        "input-provenance.json": _json_text(result["input_provenance"]),
        "blueprint.json": _json_text(result["blueprint"]),
        "activity.json": _json_text(result["activity"]),
        "research-plan.json": _json_text(output["research_plan"] or {}),
        "capability-executions.json": _json_text(output["capability_results"]),
        "model-executions.json": _json_text(output["model_receipts"]),
        "semantic-verification.json": _json_text(output["semantic_verification"]),
        "agent-output.json": _json_text(headless_agent_output),
        "output.json": _json_text(output),
        "review.json": _json_text(
            {
                "critique": output["critique"],
                "human_review": output["review"],
                "interrupted": result["interrupted"],
                "auto_approved": result["auto_approved"],
                "checkpoint_release": result["checkpoint_release"],
            }
        ),
        "transcript.md": _run_transcript(result),
    }
    files = []
    evaluation_roles = {
        "agent-output.json": "candidate_agent_output",
        "transcript.md": "technical_trace",
        "output.json": "runtime_state",
    }
    for name, content in payloads.items():
        path = directory / name
        path.write_text(content)
        files.append(
            {
                "name": name,
                "bytes": path.stat().st_size,
                "kind": "markdown" if name.endswith(".md") else "json",
                "evaluation_role": evaluation_roles.get(name, "execution_evidence"),
            }
        )
    manifest = {
        "run_id": result["run_id"],
        "agent_name": result["agent_name"],
        "output_contract": result["output_contract"],
        "status": result["status"],
        "data_mode": result["data_mode"],
        "data_label": result["data_label"],
        "execution_mode": result.get("execution_mode", "deterministic"),
        "execution_model": result.get("execution_model"),
        "comparison_id": result.get("comparison_id"),
        "scenario": result.get("scenario"),
        "portfolio_id": result.get("portfolio_id"),
        "as_of": result.get("as_of"),
        "created_at": result["created_at"],
        "elapsed_ms": result["elapsed_ms"],
        "operating_profile": result["operating_profile"],
        "authority_boundary": result["authority_boundary"],
        "external_effects": result["external_effects"],
        "persistence_class": result["persistence_class"],
        "folder": str(directory),
        "files": files,
    }
    (directory / "manifest.json").write_text(_json_text(manifest))
    manifest["files"] = [
        {"name": "manifest.json", "bytes": (directory / "manifest.json").stat().st_size, "kind": "json"},
        *files,
    ]
    (directory / "manifest.json").write_text(_json_text(manifest))
    return manifest


def _safe_run_directory(run_id: str) -> Path:
    # ``+0000`` was emitted briefly by the first development build. Keep those
    # already-created local test runs reviewable while emitting canonical ``Z``
    # identifiers for every new run.
    if not re.fullmatch(r"run-[0-9]{8}T[0-9]{6}(?:Z|\+0000)-[a-f0-9]{8}", run_id):
        raise ValueError("invalid run identifier")
    directory = (RUN_ROOT / run_id).resolve()
    if directory.parent != RUN_ROOT.resolve():
        raise ValueError("run directory is outside the local run repository")
    return directory


def list_agent_runs() -> list[dict[str, Any]]:
    if not RUN_ROOT.exists():
        return []
    runs = []
    for directory in RUN_ROOT.iterdir():
        if not directory.is_dir():
            continue
        manifest_path = directory / "manifest.json"
        try:
            runs.append(json.loads(manifest_path.read_text()))
        except (OSError, json.JSONDecodeError):
            continue
    return sorted(runs, key=lambda item: item.get("created_at", ""), reverse=True)


def load_agent_run(run_id: str) -> dict[str, Any]:
    directory = _safe_run_directory(run_id)
    if not directory.is_dir():
        raise FileNotFoundError(run_id)
    manifest = json.loads((directory / "manifest.json").read_text())
    contents: dict[str, Any] = {}
    for file in manifest.get("files", []):
        name = file.get("name", "")
        path = (directory / name).resolve()
        if path.parent != directory or not path.is_file() or path.stat().st_size > 2_000_000:
            continue
        text = path.read_text()
        if name.endswith(".json"):
            try:
                contents[name] = json.loads(text)
            except json.JSONDecodeError:
                contents[name] = text
        else:
            contents[name] = text
    # Never trust persisted HTML. Re-validate the typed envelope and render it
    # again with the current deterministic safe renderer before returning it.
    if isinstance(contents.get("report.json"), dict):
        from risk_reports import MarkdownReport, with_rendered_html

        report = with_rendered_html(MarkdownReport.model_validate(contents["report.json"]))
        contents["report.json"] = report.model_dump(mode="json")
        output = contents.get("output.json")
        if isinstance(output, dict):
            output["report"] = contents["report.json"]
            if isinstance(output.get("presentation"), dict):
                output["presentation"]["report"] = contents["report.json"]
    return {"manifest": manifest, "contents": contents}


def delete_agent_run(run_id: str) -> dict[str, Any]:
    directory = _safe_run_directory(run_id)
    if not directory.is_dir():
        raise FileNotFoundError(run_id)
    shutil.rmtree(directory)
    return {"deleted": True, "run_id": run_id, "repository": str(RUN_ROOT)}


def run_blueprint(request: RunRequest) -> dict[str, Any]:
    from langgraph.types import Command

    compiled = compile_blueprint(request.blueprint, persist=True)
    module_path = Path(compiled["artifacts"]["python"])
    module_name = f"generated_agent_{compiled['artifact_id'].replace('-', '_')}"
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load generated LangGraph module")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    graph = module.build_graph()
    thread_id = f"studio-{compiled['artifact_id']}-{time.time_ns()}"
    config = {"configurable": {"thread_id": thread_id}}
    started = time.perf_counter()
    input_context = request.input_context or _scenario_context(request.scenario)
    execution_context = {
        **input_context,
        "_agent_execution_mode": request.execution_mode,
        "_agent_execution_model": request.execution_model,
    }
    initial = graph.invoke({"context": execution_context, "trace": []}, config)
    interrupted = "__interrupt__" in initial
    interrupt_payload: Any = None
    final = initial
    if interrupted:
        interrupt_payload = [
            getattr(item, "value", str(item)) for item in initial["__interrupt__"]
        ]
        if request.auto_approve_review:
            final = graph.invoke(
                Command(
                    resume={
                        "approved": True,
                        "reviewer": "test_harness",
                        "note": (
                            "Review checkpoint released by the effect-free isolated "
                            "test harness; this is not human approval."
                        ),
                    }
                ),
                config,
            )
    history = list(graph.get_state_history(config))
    elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
    created_at_dt = datetime.now(timezone.utc).replace(microsecond=0)
    created_at = created_at_dt.isoformat()
    run_digest = hashlib.sha256(
        f"{thread_id}:{created_at}".encode()
    ).hexdigest()[:8]
    run_id = f"run-{created_at_dt.strftime('%Y%m%dT%H%M%SZ')}-{run_digest}"
    result = {
        "run_id": run_id,
        "agent_name": request.blueprint.name,
        "output_contract": request.blueprint.output_contract,
        "blueprint": request.blueprint.model_dump(mode="json"),
        "data_mode": request.data_mode,
        "execution_mode": request.execution_mode,
        "execution_model": (
            request.execution_model if request.execution_mode == "live_llm" else None
        ),
        "data_label": (
            "REAL · point-in-time DuckDB / CRSP-Compustat"
            if request.data_mode == "real_duckdb"
            else f"HISTORICALLY CALIBRATED SYNTHETIC · {request.scenario}"
            if request.data_mode == "historically_calibrated_synthetic"
            else f"CONTROLLED SYNTHETIC FIXTURE · {request.scenario}"
        ),
        "scenario": request.scenario,
        "comparison_id": request.comparison_id,
        "input_context": input_context,
        "input_provenance": request.input_provenance,
        "assignment_summary": request.run_label or request.blueprint.purpose,
        "portfolio_id": request.portfolio_id,
        "as_of": request.as_of,
        "created_at": created_at,
        "status": (
            "completed"
            if "__interrupt__" not in final
            else "waiting_for_human_review"
        ),
        "artifact_id": compiled["artifact_id"],
        "thread_id": thread_id,
        "scenario": request.scenario,
        "interrupted": interrupted,
        "interrupt_payload": interrupt_payload,
        "auto_approved": interrupted and request.auto_approve_review,
        "checkpoint_release": {
            "released": interrupted and request.auto_approve_review,
            "actor_type": (
                "test_harness"
                if interrupted and request.auto_approve_review
                else None
            ),
            "status": (
                "review_checkpoint_released_for_test"
                if interrupted and request.auto_approve_review
                else "not_released"
            ),
            "human_approval": False,
        },
        "operating_profile": "development",
        "authority_boundary": "findings_and_proposals_only",
        "external_effects": [],
        "persistence_class": (
            "temporary_local_run" if request.persist_run else "response_only"
        ),
        "trace": final.get("trace", []),
        "final_state": {
            key: value
            for key, value in final.items()
            if key not in {"context", "__interrupt__"}
        },
        "checkpoint_count": len(history),
        "elapsed_ms": elapsed_ms,
        "graph": compiled["graph"],
    }
    result["headless_agent_output"] = {
        "schema_version": "portfolio-risk.studio-headless-agent-output/v1",
        "run_id": result["run_id"],
        "experimental_role": request.blueprint.experimental_role,
        "evaluation_status": "not_admitted_to_experiment",
        "presentation_artifacts": [],
        "output_contract": result["output_contract"],
        "status": result["status"],
        "narrative": result["final_state"].get("narrative"),
        "critique": result["final_state"].get("critique"),
        "model_output": result["final_state"].get("model_output"),
        "evaluation_byproducts": (
            result["final_state"].get("model_output") or {}
        ).get("evaluation_byproducts"),
        "capability_results": result["final_state"].get("capability_results", []),
        "semantic_verification": result["final_state"].get("semantic_verification", {}),
        "review": result["final_state"].get("review"),
        "effects": [],
    }
    result["activity"] = _run_activity(result)
    result["run"] = _persist_run(result) if request.persist_run else None
    return result
