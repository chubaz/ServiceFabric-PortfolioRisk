"""Deterministic Day 1 analysis orchestration through registered capabilities."""

from __future__ import annotations

from datetime import datetime

from pydantic import Field, SerializeAsAny, field_validator, model_validator

from risk_capabilities import CAPABILITY_REQUEST_TYPES, CapabilityRegistry, CapabilityResult
from risk_capabilities.contracts import CapabilityContract
from risk_domain.common import normalize_utc
from risk_domain.digests import sha256_digest

from .active import RegisteredCapabilityAgent
from .contracts import AgentContract
from .roles import ACTIVE_AGENT_ROLE_IDS
from .timeline import AgentTimeline, AgentTimelineStep, CapabilityReceipt


class AnalysisPlanStep(AgentContract):
    sequence: int = Field(ge=1)
    role: str = Field(pattern=r"^risk\.agent\.[a-z_]+$")
    capability_id: str = Field(min_length=1, max_length=256)
    started_at: datetime
    observed_at: datetime
    request: SerializeAsAny[CapabilityContract]

    _started_at = field_validator("started_at")(normalize_utc)
    _observed_at = field_validator("observed_at")(normalize_utc)

    @model_validator(mode="before")
    @classmethod
    def deserialize_concrete_capability_request(cls, value: object) -> object:
        if not isinstance(value, dict):
            return value
        capability_id = value.get("capability_id")
        request = value.get("request")
        request_type = CAPABILITY_REQUEST_TYPES.get(capability_id)
        if request_type is None:
            raise ValueError(f"analysis plan capability is not registered: {capability_id}")
        normalized = dict(value)
        if isinstance(request, dict):
            normalized["request"] = request_type.model_validate(request)
        return normalized

    @model_validator(mode="after")
    def timestamps_and_evidence_are_present(self) -> "AnalysisPlanStep":
        if self.observed_at < self.started_at:
            raise ValueError("observed_at cannot precede started_at")
        request_type = CAPABILITY_REQUEST_TYPES.get(self.capability_id)
        if request_type is None or not isinstance(self.request, request_type):
            expected = request_type.__name__ if request_type is not None else "registered request"
            raise ValueError(f"{self.capability_id} requires {expected}")
        evidence = getattr(self.request, "evidence_references", ())
        if not evidence:
            raise ValueError("analysis workflow steps require evidence")
        return self


class Day1AnalysisRunRequest(AgentContract):
    timeline_id: str = Field(min_length=1, max_length=256)
    steps: tuple[AnalysisPlanStep, ...] = Field(min_length=4, max_length=4)

    @field_validator("steps")
    @classmethod
    def deterministic_four_role_plan(
        cls, values: tuple[AnalysisPlanStep, ...]
    ) -> tuple[AnalysisPlanStep, ...]:
        sequences = [step.sequence for step in values]
        if sequences != list(range(1, len(values) + 1)):
            raise ValueError("analysis plan steps must be supplied in contiguous sequence order")
        role_ids = [step.role for step in values]
        if len(role_ids) != len(set(role_ids)):
            raise ValueError("Day 1 analysis requires one step for each agent role")
        roles = set(role_ids)
        if roles != set(ACTIVE_AGENT_ROLE_IDS):
            raise ValueError("Day 1 analysis requires exactly the four existing agent roles")
        return values


class DeterministicAnalysisOrchestrator:
    """Invoke a caller-supplied four-role plan only through the canonical registry."""

    def __init__(self, registry: CapabilityRegistry) -> None:
        self.registry = registry

    @staticmethod
    def _receipt(
        capability_id: str,
        request: CapabilityContract,
        result: CapabilityResult[object],
    ) -> CapabilityReceipt:
        evidence = result.evidence_references
        if not evidence:
            raise ValueError("capability result omitted required evidence")
        methodology = (
            result.methodology.value
            if result.methodology is not None
            else "registered-capability"
        )
        return CapabilityReceipt(
            capability_id=capability_id,
            status=result.status,
            input_digest=sha256_digest(request),
            output_digest=result.output_digest or sha256_digest(result),
            evidence=evidence,
            methodology=methodology,
            assumptions=result.assumptions,
            warnings=result.warnings,
            limitations=result.limitations,
            effects=result.effects,
        )

    def run(self, request: Day1AnalysisRunRequest) -> AgentTimeline:
        timeline_steps: list[AgentTimelineStep] = []
        for planned in request.steps:
            agent = RegisteredCapabilityAgent(planned.role, self.registry)
            result = agent.invoke(planned.capability_id, planned.request)
            receipt = self._receipt(planned.capability_id, planned.request, result)
            timeline_steps.append(
                AgentTimelineStep(
                    sequence=planned.sequence,
                    role=planned.role,
                    capability_id=planned.capability_id,
                    started_at=planned.started_at,
                    observed_at=planned.observed_at,
                    input_digest=receipt.input_digest,
                    output_digest=receipt.output_digest,
                    evidence=receipt.evidence,
                    methodology=receipt.methodology,
                    assumptions=receipt.assumptions,
                    warnings=receipt.warnings,
                    limitations=receipt.limitations,
                    status=receipt.status,
                    effects=receipt.effects,
                    receipt=receipt,
                )
            )
            if result.status != "succeeded":
                break
        status = (
            "failed"
            if any(step.status == "failed" for step in timeline_steps)
            else "stopped"
            if any(step.status == "stopped" for step in timeline_steps)
            else "succeeded"
        )
        return AgentTimeline(
            timeline_id=request.timeline_id,
            status=status,
            steps=tuple(timeline_steps),
        )
