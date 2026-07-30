"""Explicit local-only Responses API adapter; it never falls back to fixtures."""
from __future__ import annotations

import json
import os
import re
import time
from typing import Callable

from pydantic import ValidationError

from ..contracts import (
    ArchitectureReviewOutput,
    ModelCallReceipt,
    ModelConfiguration,
    ModelRequest,
    NEXT_STEPS,
    bytes_digest,
    canonical,
    digest,
)
from ..prompts import prompt_text
from .base import StructuredModelProvider


def _strict_response_schema(architecture_id: str) -> dict[str, object]:
    schema = ArchitectureReviewOutput.model_json_schema()
    schema["properties"].pop("output_digest", None)
    schema["required"] = list(schema["properties"])

    def normalize(value: object) -> None:
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
    properties = schema["properties"]
    properties["architecture_id"].pop("enum", None)
    properties["architecture_id"]["const"] = architecture_id
    properties["recommended_next_steps"]["items"]["enum"] = list(NEXT_STEPS)
    properties["effects"]["maxItems"] = 0
    claim_properties = schema["$defs"]["StructuredClaim"]["properties"]
    claim_properties["evidence_refs"]["minItems"] = 1
    return schema


def _safe_error_detail(error: Exception) -> str | None:
    """Return only non-sensitive provider metadata suitable for receipts and CLI output."""
    values = [
        type(error).__name__,
        str(getattr(error, "code", "") or ""),
        str(getattr(error, "status_code", "") or ""),
    ]
    normalized = [
        re.sub(r"[^A-Za-z0-9_-]", "_", value)[:64]
        for value in values
        if value
    ]
    return "provider_error:" + ":".join(normalized) if normalized else None


def _is_terminal_provider_error(error: Exception) -> bool:
    code = str(getattr(error, "code", "") or "").casefold()
    status_code = getattr(error, "status_code", None)
    return code in {
        "insufficient_quota",
        "invalid_api_key",
        "model_not_found",
        "permission_denied",
    } or status_code in {401, 403}


def _safe_validation_detail(error: Exception) -> str:
    """Identify invalid fields without retaining model text or validation inputs."""
    if not isinstance(error, ValidationError):
        return re.sub(r"[^A-Za-z0-9_-]", "_", type(error).__name__)[:64]
    details: list[str] = []
    for item in error.errors(
        include_url=False,
        include_context=False,
        include_input=False,
    ):
        location = ".".join(str(value) for value in item.get("loc", ())) or "root"
        error_type = str(item.get("type", "validation_error"))
        safe_location = re.sub(r"[^A-Za-z0-9_.-]", "_", location)[:96]
        safe_type = re.sub(r"[^A-Za-z0-9_.-]", "_", error_type)[:64]
        detail = f"{safe_location}:{safe_type}"
        if detail not in details:
            details.append(detail)
        if len(details) == 3:
            break
    return "ValidationError:" + ",".join(details or ("unknown",))


class OpenAIResponsesProvider(StructuredModelProvider):
    provider_id = "openai_responses"

    def __init__(
        self,
        configuration: ModelConfiguration,
        client_factory: Callable[..., object] | None = None,
    ):
        if not os.environ.get("OPENAI_API_KEY"):
            raise ValueError("OPENAI_API_KEY is required")
        if configuration.provider_id != self.provider_id:
            raise ValueError("model configuration selects a different provider")
        if configuration.store or configuration.tools:
            raise ValueError("unsafe model configuration")
        self.configuration = configuration
        self._client_factory = client_factory
        self._terminal_error_code: str | None = None
        self._terminal_error_detail: str | None = None

    def prepare_request(self, request: ModelRequest) -> dict[str, object]:
        body: dict[str, object] = {
            "model": self.configuration.model_snapshot,
            "input": [
                {
                    "role": "system",
                    "content": [
                        {
                            "type": "input_text",
                            "text": prompt_text(request.system_prompt),
                        }
                    ],
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": (
                                prompt_text(request.prompt)
                                + "\n\nGOVERNED_CONTEXT_JSON:\n"
                                + json.dumps(
                                    canonical(request.payload),
                                    sort_keys=True,
                                    separators=(",", ":"),
                                )
                            ),
                        }
                    ],
                },
            ],
            "max_output_tokens": self.configuration.maximum_output_tokens,
            "store": False,
            "tools": [],
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "architecture_review",
                    "strict": True,
                    "schema": _strict_response_schema(request.architecture_id),
                }
            },
        }
        if self.configuration.temperature_supported:
            body["temperature"] = float(self.configuration.temperature)
        return body

    def parse(
        self,
        request: ModelRequest,
        raw_output: str,
    ) -> ArchitectureReviewOutput:
        return ArchitectureReviewOutput.model_validate_json(raw_output)

    def receipt(
        self,
        request: ModelRequest,
        raw_output: str,
        output: ArchitectureReviewOutput,
        **metadata: object,
    ) -> ModelCallReceipt:
        usage = metadata.get("usage")
        return ModelCallReceipt(
            provider_id=self.provider_id,
            model_id=str(metadata.get("model_id") or self.configuration.model_snapshot),
            architecture_id=request.architecture_id,
            role_id=request.role_id,
            prompt_digest=request.prompt.digest,
            request_digest=digest(request),
            raw_response_digest=bytes_digest(raw_output.encode("utf-8")),
            parsed_output_digest=output.output_digest,
            input_tokens=int(getattr(usage, "input_tokens", 0) or 0),
            output_tokens=int(getattr(usage, "output_tokens", 0) or 0),
            elapsed_ms=int(metadata.get("elapsed_ms") or 0),
            response_id=(
                str(metadata["response_id"])
                if metadata.get("response_id") is not None
                else None
            ),
            warnings=tuple(metadata.get("warnings") or ()),
            limitations=(
                "Structured research synthesis only; not investment advice.",
                "No tools, outside knowledge, execution effects, or chain-of-thought.",
            ),
        )

    def _abstention(
        self,
        request: ModelRequest,
        *,
        code: str,
        elapsed_ms: int,
        detail: str | None = None,
        raw_output: str | None = None,
        **metadata: object,
    ) -> tuple[ArchitectureReviewOutput, ModelCallReceipt]:
        uncertainty = detail or code
        output = ArchitectureReviewOutput(
            architecture_id=request.architecture_id,
            status="ABSTAINED_AGENT_OUTPUT",
            severity=0,
            summary="Model output was unavailable or invalid; deterministic abstention applied.",
            uncertainties=(uncertainty,),
            human_review_required=True,
            effects=(),
        )
        if raw_output is None:
            raw_output = json.dumps(
                {"status": "unavailable", "code": uncertainty},
                sort_keys=True,
                separators=(",", ":"),
            )
        warnings = (code, detail) if detail else (code,)
        return output, self.receipt(
            request,
            raw_output,
            output,
            elapsed_ms=elapsed_ms,
            warnings=warnings,
            **metadata,
        )

    def generate(
        self,
        request: ModelRequest,
    ) -> tuple[ArchitectureReviewOutput, ModelCallReceipt]:
        if self._terminal_error_detail is not None:
            return self._abstention(
                request,
                code=self._terminal_error_code or "provider_error",
                detail=(
                    "skipped_after_terminal_error:"
                    + self._terminal_error_detail.split(":", 1)[-1]
                ),
                elapsed_ms=0,
            )
        started = time.monotonic()
        try:
            if self._client_factory is None:
                from openai import OpenAI

                client_factory: Callable[..., object] = OpenAI
            else:
                client_factory = self._client_factory
            client = client_factory(
                api_key=os.environ["OPENAI_API_KEY"],
                timeout=self.configuration.timeout_seconds,
                max_retries=self.configuration.retry_count,
            )
            response = client.responses.create(**self.prepare_request(request))
        except Exception as error:
            elapsed_ms = max(0, int((time.monotonic() - started) * 1000))
            detail = _safe_error_detail(error)
            if _is_terminal_provider_error(error):
                self._terminal_error_code = "provider_error"
                self._terminal_error_detail = detail or "provider_error:terminal"
            return self._abstention(
                request,
                code="provider_error",
                detail=detail,
                elapsed_ms=elapsed_ms,
            )

        elapsed_ms = max(0, int((time.monotonic() - started) * 1000))
        raw_output = str(getattr(response, "output_text", "") or "")
        response_status = str(getattr(response, "status", "completed") or "completed")
        if response_status != "completed":
            incomplete = getattr(response, "incomplete_details", None)
            reason = re.sub(
                r"[^A-Za-z0-9_-]",
                "_",
                str(getattr(incomplete, "reason", "") or "unknown"),
            )[:64]
            detail = f"invalid_structured_output:{response_status}:{reason}"
            self._terminal_error_code = "invalid_structured_output"
            self._terminal_error_detail = detail
            return self._abstention(
                request,
                code="invalid_structured_output",
                detail=detail,
                elapsed_ms=elapsed_ms,
                raw_output=raw_output,
                usage=getattr(response, "usage", None),
                response_id=getattr(response, "id", None),
                model_id=getattr(response, "model", None),
            )
        try:
            output = self.parse(request, raw_output)
        except Exception as error:
            detail = "invalid_structured_output:" + _safe_validation_detail(error)
            self._terminal_error_code = "invalid_structured_output"
            self._terminal_error_detail = detail
            return self._abstention(
                request,
                code="invalid_structured_output",
                detail=detail,
                elapsed_ms=elapsed_ms,
                raw_output=raw_output,
                usage=getattr(response, "usage", None),
                response_id=getattr(response, "id", None),
                model_id=getattr(response, "model", None),
            )
        return output, self.receipt(
            request,
            raw_output,
            output,
            usage=getattr(response, "usage", None),
            elapsed_ms=elapsed_ms,
            response_id=getattr(response, "id", None),
            model_id=getattr(response, "model", None),
        )
