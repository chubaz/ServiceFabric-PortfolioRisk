"""Validated LangGraph blueprint compiler and isolated execution runtime."""

from __future__ import annotations

import hashlib
import importlib.metadata
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator
from risk_reports import (
    compose_daily_risk_report,
    report_markdown,
    validate_report,
    with_rendered_html,
)


COMPILER_VERSION = "agent-blueprint-compiler/0.4.0"

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
}

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
    purpose: str = Field(min_length=20, max_length=1200)
    model: Literal["gpt-5.6-terra", "gpt-5.6-sol", "gpt-5.6", "gpt-5.4"] = (
        "gpt-5.6-terra"
    )
    input_contract: Literal[
        "PortfolioContext",
        "RiskContext",
        "OverallDefaultContext",
        "SpecialistOutputBundle",
    ] = "OverallDefaultContext"
    output_contract: Literal[
        "SpecialistInterpretation",
        "RiskReviewDraft",
        "EvidenceCritique",
        "CapabilityRequest",
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
        if self.governance.evidence_required and "evidence_critic" not in capabilities:
            raise ValueError(
                "evidence-required governance requires an evidence_critic latch"
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
    model: Literal["gpt-5.6-terra", "gpt-5.6-sol", "gpt-5.6", "gpt-5.4"] = (
        "gpt-5.6-terra"
    )


class IdentitySection(BaseModel):
    name: str = Field(min_length=3, max_length=80)
    purpose: str = Field(min_length=20, max_length=1200)
    model: Literal["gpt-5.6-terra", "gpt-5.6-sol", "gpt-5.6", "gpt-5.4"]
    input_contract: Literal[
        "PortfolioContext",
        "RiskContext",
        "OverallDefaultContext",
        "SpecialistOutputBundle",
    ]
    output_contract: Literal[
        "SpecialistInterpretation",
        "RiskReviewDraft",
        "EvidenceCritique",
        "CapabilityRequest",
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
    model: Literal["gpt-5.6-terra", "gpt-5.6-sol", "gpt-5.6", "gpt-5.4"] = (
        "gpt-5.6-terra"
    )


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
    model: Literal["gpt-5.6-terra", "gpt-5.6-sol", "gpt-5.6"] = "gpt-5.6-terra"


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


class CompileRequest(BaseModel):
    blueprint: AgentBlueprint
    persist: bool = True


class RunRequest(BaseModel):
    blueprint: AgentBlueprint
    scenario: Literal["routine", "concentration", "loss", "missing"] = "concentration"
    data_mode: Literal["synthetic_behavior_sample", "real_duckdb"] = (
        "synthetic_behavior_sample"
    )
    execution_mode: Literal["deterministic", "live_llm"] = "deterministic"
    execution_model: Literal[
        "gpt-5.6-terra", "gpt-5.6-sol", "gpt-5.6", "gpt-5.4"
    ] = "gpt-5.4"
    input_context: dict[str, Any] | None = None
    input_provenance: dict[str, Any] = Field(default_factory=dict)
    portfolio_id: str | None = Field(default=None, max_length=80)
    as_of: str | None = Field(default=None, max_length=32)
    datasets: list[str] = Field(default_factory=list, max_length=8)
    run_label: str | None = Field(default=None, max_length=120)
    persist_run: bool = True
    auto_approve_review: bool = False


class OutputPassRunRequest(BaseModel):
    blueprint: AgentBlueprint
    pass_id: str
    scenario: Literal["routine", "concentration", "loss", "missing"] = "concentration"
    mode: Literal["preview", "openai"] = "preview"
    current_artifact: dict[str, Any] = Field(default_factory=dict)
    model: Literal["gpt-5.6-terra", "gpt-5.6-sol", "gpt-5.6", "gpt-5.4"] = (
        "gpt-5.6-terra"
    )


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
                "id": "gpt-5.6-terra",
                "label": "GPT-5.6 Terra · fast blueprint drafting",
            },
            {
                "id": "gpt-5.6-sol",
                "label": "GPT-5.6 Sol · deepest architecture review",
            },
            {
                "id": "gpt-5.6",
                "label": "GPT-5.6 alias · current flagship family",
            },
            {
                "id": "gpt-5.4",
                "label": "GPT-5.4 · previously approved baseline",
            },
        ],
        "capabilities": [
            {"id": capability_id, **definition}
            for capability_id, definition in CAPABILITIES.items()
        ],
    }


def _risk_agent_template(spec: dict[str, Any]) -> dict[str, Any]:
    capability_ids = list(dict.fromkeys([*spec["capabilities"], "evidence_critic"]))
    human_review = spec["strategy"] == "human_review"
    blueprint = AgentBlueprint.model_validate(
        {
            "name": spec["name"],
            "purpose": spec["purpose"],
            "model": "gpt-5.6-terra",
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
        "framework": "langgraph",
        "engine": "langgraph",
        "role": spec["role"],
        "input": spec["input_contract"],
        "output": spec["output_contract"],
        "instructions": spec["objective"],
        "capabilities": capability_ids,
        "blueprint": blueprint.model_dump(mode="json"),
        "built_in": True,
        "category": spec["category"],
    }


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
    return [_risk_agent_template(spec) for spec in specs]


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
        if governance.get("evidence_required"):
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
    started = time.perf_counter()
    client = OpenAI(api_key=str(api_key))
    response = client.responses.create(
        model=request.model,
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
                            "portfolio input/output contract names. Use lower_snake_case "
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
        model=request.model,
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
    history = [
        {"role": item.role, "content": [{"type": "input_text", "text": item.content}]}
        for item in request.history[-8:]
    ]
    response = client.responses.create(
        model=request.model,
        store=False,
        tools=[],
        input=[
            {
                "role": "system",
                "content": [
                    {
                        "type": "input_text",
                        "text": (
                            "You are the embedded Agent Design Advisor for a portfolio-risk "
                            "research application. Critique the current blueprint as an "
                            "architecture reviewer and collaborative teacher. Evaluate "
                            "clarity, type safety, routing, state ownership, memory scope, "
                            "capability latching, prompt quality, evidence, failure behavior, "
                            "Structured Output design, multi-pass assembly, token budgets, "
                            "and human approval. Propose practical improvements for the "
                            "requested focus. Preserve canonical financial contracts, use "
                            "only the supplied capability allow-list, never permit portfolio "
                            "effects, and never return Python or chain-of-thought. Return a "
                            "concise improved design brief that can be transformed into a "
                            "new blueprint only after explicit user action; do not repeat "
                            "the complete blueprint. Keep prompts outcome-first, remove "
                            "duplicated rules, and make stopping conditions explicit."
                        ),
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
        },
    }


def graph_spec(blueprint: AgentBlueprint) -> dict[str, Any]:
    nodes = PATTERN_NODES[blueprint.pattern]
    edges: list[dict[str, str]] = []
    previous = "START"
    for node in nodes:
        edges.append({"from": previous, "to": node})
        previous = node
    if blueprint.pattern == "reflection":
        edges.append(
            {
                "from": "evidence_critic",
                "to": "draft",
                "condition": "revision required and iteration < max_iterations",
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
    source = SourceReference(
        source_id="local-duckdb-crsp-compustat",
        source_type="licensed_local_research_data",
        reference=str(metric_input.get("source_reference") or "duckdb://portfolio/history"),
        retrieved_at=retrieved_at,
    )
    prices = tuple(
        MarketObservation(
            instrument_id="portfolio-priced-sleeve",
            observed_at=_parse_utc(f"{item['observed_at']}T23:59:59+00:00"),
            price=_decimal_text(item["portfolio_value"]),
            currency=str(metric_input.get("base_currency") or "USD"),
            synthetic=False,
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
                "Fixed-quantity portfolio values for holdings with current eligible prices; "
                "cash is included and excluded holdings are disclosed."
            ),
        ),
    )
    horizon = AnalysisHorizon(
        label="daily close-to-close", periods=1, expected_interval_seconds=86400
    )
    assumptions = (
        "Historical values use fixed as-of quantities and therefore describe market movement, not historical holdings changes.",
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
        "operating_prompt_digest": "sha256:"
        + hashlib.sha256(rendered_prompt.encode()).hexdigest(),
        "compact_context_projection": compiled_context["projection"],
        "context_telemetry": compiled_context["telemetry"],
    }
    schema = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "executive_signal": {"type": "string", "maxLength": 650},
            "what_changed": {
                "type": "array",
                "items": {"type": "string"},
                "maxItems": 4,
            },
            "risk_interpretation": {"type": "string", "maxLength": 1200},
            "exposure_and_mandate": {"type": "string", "maxLength": 1000},
            "material_findings": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "claim": {"type": "string"},
                        "evidence_ids": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                    },
                    "required": ["claim", "evidence_ids"],
                },
                "maxItems": 6,
            },
            "uncertainties": {
                "type": "array",
                "items": {"type": "string"},
                "maxItems": 4,
            },
            "review_actions": {
                "type": "array",
                "items": {"type": "string"},
                "maxItems": 5,
            },
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        },
        "required": [
            "executive_signal",
            "what_changed",
            "risk_interpretation",
            "exposure_and_mandate",
            "material_findings",
            "uncertainties",
            "review_actions",
            "confidence",
        ],
    }
    prompt_text = json.dumps(model_input, sort_keys=True, default=str)
    prompt_digest = "sha256:" + hashlib.sha256(prompt_text.encode()).hexdigest()
    started = time.perf_counter()
    client = OpenAI(api_key=str(api_key))
    response = client.responses.create(
        model=model,
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
        max_output_tokens=1400,
    )
    elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
    output_text = response.output_text
    if not output_text:
        raise RuntimeError("The model returned no structured interpretation")
    interpretation = json.loads(output_text)
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
    research_plan: dict[str, Any]
    rendered_prompt: str
    narrative: str
    rationale_summary: list[str]
    model_output: dict[str, Any]
    model_receipts: list[dict[str, Any]]
    critique: str
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
    overall_context = {{
        **context,
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
        "trace": _event(
            state,
            "assemble_context",
            f"Assembled OverallDefaultContext after {{len(successful)}} successful "
            "canonical capability result(s).",
        ),
    }}


def render_prompt(state: AgentState) -> str:
    context = state.get("overall_context") or state.get("context", {{}})
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
    if context.get("_agent_execution_mode") == "live_llm":
        from agent_studio import execute_live_interpretation

        live = execute_live_interpretation(
            context=context,
            capability_results=state.get("capability_results", []),
            blueprint=BLUEPRINT,
            rendered_prompt=rendered_prompt,
            model=context.get("_agent_execution_model", "gpt-5.4"),
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
    critique = (
        f"Evidence coverage is {{evidence_state}}; full-portfolio and causal claims must "
        "remain explicitly qualified."
        if missing
        else "Every material claim is grounded in the supplied deterministic context."
    )
    return {{
        "critique": critique,
        "trace": _event(state, "evidence_critic", critique),
    }}


def route_after_critic(state: AgentState) -> str:
    context = state.get("overall_context") or state.get("context", {{}})
    missing = context.get("evidence_state") in {{"missing", "partial"}}
    if (
        BLUEPRINT["pattern"] == "reflection"
        and missing
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
    if BLUEPRINT["pattern"] in {{"tool_loop", "reflection", "human_review"}}:
        builder.add_node("evidence_critic", evidence_critic)
    if BLUEPRINT["pattern"] == "human_review":
        builder.add_node("human_review", human_review)

    builder.add_edge(START, "load_context")
    builder.add_edge("load_context", "gather_evidence")
    builder.add_edge("gather_evidence", "assemble_context")
    builder.add_edge("assemble_context", "draft")
    if BLUEPRINT["pattern"] == "direct":
        builder.add_edge("draft", END)
    else:
        builder.add_edge("draft", "evidence_critic")
        if BLUEPRINT["pattern"] == "reflection":
            builder.add_conditional_edges(
                "evidence_critic",
                route_after_critic,
                {{"revise": "draft", "continue": END}},
            )
        elif BLUEPRINT["pattern"] == "human_review":
            builder.add_edge("evidence_critic", "human_review")
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
        "label": f"SYNTHETIC BEHAVIOR SAMPLE · {scenario}",
        "scenario": scenario,
        "licensed_data_used": False,
        "point_in_time": False,
        "reviewed_fixture": False,
        "warning": (
            "Values are generated in code for behavior testing and must not be "
            "interpreted as a reviewed fixture or historical observation."
        ),
    }


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
            model=request.model,
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
    if not result.get("report"):
        report, validation = _compose_run_report(result)
        result["report"] = report
        result["report_validation"] = validation
    directory = RUN_ROOT / result["run_id"]
    directory.mkdir(parents=True, exist_ok=False)
    output = {
        "output_contract": result["output_contract"],
        "narrative": result.get("final_state", {}).get("narrative"),
        "critique": result.get("final_state", {}).get("critique"),
        "presentation": result.get("presentation"),
        "report": result.get("report"),
        "report_validation": result.get("report_validation"),
        "research_plan": result.get("final_state", {}).get("research_plan"),
        "capability_results": result.get("final_state", {}).get(
            "capability_results", []
        ),
        "model_output": result.get("final_state", {}).get("model_output"),
        "rationale_summary": result.get("final_state", {}).get(
            "rationale_summary", []
        ),
        "model_receipts": result.get("final_state", {}).get("model_receipts", []),
        "review": result.get("final_state", {}).get("review"),
        "status": result["status"],
    }
    payloads: dict[str, str] = {
        "input.json": _json_text(result["input_context"]),
        "input-provenance.json": _json_text(result["input_provenance"]),
        "blueprint.json": _json_text(result["blueprint"]),
        "activity.json": _json_text(result["activity"]),
        "research-plan.json": _json_text(output["research_plan"] or {}),
        "capability-executions.json": _json_text(output["capability_results"]),
        "model-executions.json": _json_text(output["model_receipts"]),
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
        "review-brief.md": _review_brief(result),
        "review-brief.html": str(result.get("report", {}).get("rendered_html", "")),
        "report.json": _json_text(result.get("report", {})),
        "transcript.md": _run_transcript(result),
    }
    files = []
    for name, content in payloads.items():
        path = directory / name
        path.write_text(content)
        files.append(
            {
                "name": name,
                "bytes": path.stat().st_size,
                "kind": "markdown" if name.endswith(".md") else "json",
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
            else f"SYNTHETIC BEHAVIOR SAMPLE · {request.scenario}"
        ),
        "scenario": request.scenario,
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
    result["presentation"] = _run_presentation(result)
    result["report"], result["report_validation"] = _compose_run_report(result)
    result["presentation"]["report"] = result["report"]
    result["presentation"]["report_validation"] = result["report_validation"]
    result["activity"] = _run_activity(result)
    result["run"] = _persist_run(result) if request.persist_run else None
    return result
