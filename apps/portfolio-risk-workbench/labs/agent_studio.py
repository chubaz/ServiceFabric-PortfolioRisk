"""Validated LangGraph blueprint compiler and isolated execution runtime."""

from __future__ import annotations

import hashlib
import importlib.metadata
import importlib.util
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator


COMPILER_VERSION = "agent-blueprint-compiler/0.4.0"
GENERATED_ROOT = Path(
    os.environ.get(
        "PORTFOLIO_RISK_AGENT_OUTPUT_ROOT",
        Path(__file__).resolve().parent / "generated_agents",
    )
).expanduser().resolve()

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
    "direct": ["load_context", "gather_evidence", "draft"],
    "tool_loop": ["load_context", "gather_evidence", "draft", "evidence_critic"],
    "reflection": ["load_context", "gather_evidence", "draft", "evidence_critic"],
    "human_review": [
        "load_context",
        "gather_evidence",
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
    auto_approve_review: bool = True


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
    capability_results: list[dict[str, Any]]
    rendered_prompt: str
    narrative: str
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
            f"Validated {{BLUEPRINT['input_contract']}} with {{len(context)}} fields.",
        ),
    }}


def gather_evidence(state: AgentState) -> AgentState:
    context = state.get("context", {{}})
    values = {{
        "market_data": {{"daily_return": context.get("daily_return"), "var_95": context.get("var_95")}},
        "risk_metrics": {{"var_95": context.get("var_95"), "drawdown": context.get("drawdown")}},
        "portfolio_exposure": {{"largest_weight": context.get("largest_weight"), "cash_weight": context.get("cash_weight")}},
        "scenario_stress": {{"stress_loss": context.get("stress_loss")}},
        "fundamental_change": {{"fundamental_signal": context.get("fundamental_signal", "not supplied")}},
        "event_retrieval": {{"eligible_event": context.get("eligible_event", "none")}},
        "evidence_critic": {{"evidence_state": context.get("evidence_state", "complete")}},
    }}
    results = [
        {{"capability": capability, "result": values[capability]}}
        for capability in BLUEPRINT["capabilities"]
    ]
    return {{
        "capability_results": results,
        "trace": _event(
            state,
            "gather_evidence",
            f"Executed {{len(results)}} allow-listed, effect-free capabilities.",
        ),
    }}


def render_prompt(state: AgentState) -> str:
    context = state.get("context", {{}})
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


def draft(state: AgentState) -> AgentState:
    context = state.get("context", {{}})
    iteration = state.get("iteration", 0) + 1
    rendered_prompt = render_prompt(state)
    issue = context.get("issue", "No risk exception was supplied.")
    narrative = (
        f"Portfolio review: {{issue}} "
        f"The portfolio returned {{context.get('daily_return', 0):.2%}}; "
        f"95% historical VaR is {{context.get('var_95', 0):.2%}} and the "
        f"largest position is {{context.get('largest_weight', 0):.1%}}. "
        f"Evidence status: {{context.get('evidence_state', 'complete')}}. "
        "This is an interpretation of supplied deterministic context and creates no portfolio effect."
    )
    return {{
        "iteration": iteration,
        "rendered_prompt": rendered_prompt,
        "narrative": narrative,
        "trace": _event(
            state,
            "draft",
            f"Produced {{BLUEPRINT['output_contract']}} revision {{iteration}}.",
        ),
    }}


def evidence_critic(state: AgentState) -> AgentState:
    missing = state.get("context", {{}}).get("evidence_state") == "missing"
    critique = (
        "Evidence is incomplete; causal claims must remain explicitly uncertain."
        if missing
        else "Every material claim is grounded in the supplied deterministic context."
    )
    return {{
        "critique": critique,
        "trace": _event(state, "evidence_critic", critique),
    }}


def route_after_critic(state: AgentState) -> str:
    missing = state.get("context", {{}}).get("evidence_state") == "missing"
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
    builder.add_node("draft", draft)
    if BLUEPRINT["pattern"] in {{"tool_loop", "reflection", "human_review"}}:
        builder.add_node("evidence_critic", evidence_critic)
    if BLUEPRINT["pattern"] == "human_review":
        builder.add_node("human_review", human_review)

    builder.add_edge(START, "load_context")
    builder.add_edge("load_context", "gather_evidence")
    builder.add_edge("gather_evidence", "draft")
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
    return contexts[scenario]


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
    initial = graph.invoke(
        {"context": _scenario_context(request.scenario), "trace": []},
        config,
    )
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
                        "reviewer": "Agent Studio synthetic test",
                        "note": "Automatically approved for isolated execution only.",
                    }
                ),
                config,
            )
    history = list(graph.get_state_history(config))
    elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
    return {
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
