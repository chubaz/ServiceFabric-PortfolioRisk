"""Headless instrumentation wrapper for agents used in experiments.

The wrapper observes and records execution. It does not judge, revise, or
approve agent content. Human-facing presentation files are referenced only as
explicitly excluded material and never become evaluation inputs.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field, field_validator, model_validator

from risk_domain.common import normalize_utc
from risk_domain.digests import sha256_digest

from .artifacts import DIGEST, IDENTIFIER, AgentStructuredOutput
from .contracts import AgentContract


class AgentRuntimeTelemetry(AgentContract):
    agent_id: str = Field(pattern=IDENTIFIER)
    agent_version: str = Field(min_length=1, max_length=128)
    started_at: datetime
    completed_at: datetime
    first_finding_at: datetime | None = None
    model_calls: int = Field(default=0, ge=0)
    input_tokens: int = Field(default=0, ge=0)
    cached_input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)
    cost_usd: float = Field(default=0, ge=0)
    capability_calls: int = Field(default=0, ge=0)
    retries: int = Field(default=0, ge=0)
    timeouts: int = Field(default=0, ge=0)
    schema_validation_failures: int = Field(default=0, ge=0)
    semantic_verification_failures: int = Field(default=0, ge=0)
    route: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()

    _started_at = field_validator("started_at")(normalize_utc)
    _completed_at = field_validator("completed_at")(normalize_utc)

    @field_validator("first_finding_at")
    @classmethod
    def optional_timestamp_is_utc(cls, value: datetime | None) -> datetime | None:
        return None if value is None else normalize_utc(value)

    @model_validator(mode="after")
    def timing_is_ordered(self) -> "AgentRuntimeTelemetry":
        if self.completed_at < self.started_at:
            raise ValueError("agent completion cannot precede its start")
        if self.first_finding_at is not None and not (
            self.started_at <= self.first_finding_at <= self.completed_at
        ):
            raise ValueError("first finding time must fall inside agent execution")
        if self.cached_input_tokens > self.input_tokens:
            raise ValueError("cached input tokens cannot exceed total input tokens")
        return self


class AgentExecutionEnvelope(AgentContract):
    """One wrapped, headless agent execution."""

    schema_version: Literal["portfolio-risk.agent-execution-envelope/v1"] = "portfolio-risk.agent-execution-envelope/v1"
    envelope_id: str = Field(pattern=IDENTIFIER)
    envelope_digest: str | None = Field(default=None, pattern=DIGEST)
    output: AgentStructuredOutput
    telemetry: AgentRuntimeTelemetry

    @model_validator(mode="after")
    def bind_execution(self) -> "AgentExecutionEnvelope":
        if self.output.execution_mode != "headless":
            raise ValueError("experimental agent execution must be headless")
        if self.telemetry.agent_id not in self.output.agent_ids:
            raise ValueError("telemetry agent must be named by the structured output")
        if not self.telemetry.started_at <= self.output.produced_at <= self.telemetry.completed_at:
            raise ValueError("output production must occur inside wrapped execution")
        for use in self.output.capability_uses:
            if use.completed_at > self.output.produced_at:
                raise ValueError("capability result must exist before output production")
        expected = sha256_digest(self.model_dump(mode="python", exclude={"envelope_digest"}))
        if self.envelope_digest is not None and self.envelope_digest != expected:
            raise ValueError("envelope_digest does not match canonical content")
        object.__setattr__(self, "envelope_digest", expected)
        return self


def wrap_agent_execution(
    output: AgentStructuredOutput,
    telemetry: AgentRuntimeTelemetry,
) -> AgentExecutionEnvelope:
    """Create the canonical headless wrapper without changing the output."""

    return AgentExecutionEnvelope(
        envelope_id=f"agent-execution-{output.output_digest[7:23]}",
        output=output,
        telemetry=telemetry,
    )
