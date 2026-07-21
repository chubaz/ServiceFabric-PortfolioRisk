"""A deterministic, no-LLM Day 0 provider implementation."""

from __future__ import annotations

import hashlib

from risk_capabilities import CapabilityInvocation

from .contracts import AgentRunContext, DeterministicProviderDraft
from .roles import ROLE_BY_ID


class DeterministicAgentProvider:
    """Prepare stable, evidence-preserving drafts without network access."""

    provider_id = "risk.provider.deterministic_no_llm"

    def prepare(self, context: AgentRunContext, invocation: CapabilityInvocation) -> DeterministicProviderDraft:
        """Prepare only; ServiceFabric's canonical runtime owns invocation and results."""
        if context.provider_id != self.provider_id:
            return self._failure(invocation, "The run context provider ID does not match this deterministic provider.")
        role = ROLE_BY_ID.get(context.role_id)
        if role is None:
            return self._failure(invocation, "The requested agent role is not registered.")
        if invocation.capability_id not in role.allowed_capability_ids:
            return self._failure(invocation, "The requested capability is not granted to this agent role.")
        if not invocation.evidence_references:
            return self._failure(invocation, "Evidence is required; no evidence references were supplied.")

        input_digest = hashlib.sha256(
            "\n".join(f"{item.name}={item.value!r}" for item in invocation.inputs).encode("utf-8")
        ).hexdigest()
        return DeterministicProviderDraft(
            invocation_id=invocation.invocation_id,
            capability_id=invocation.capability_id,
            status="prepared",
            summary=f"Deterministic review draft for {invocation.capability_id} (input sha256:{input_digest}).",
            evidence_references=invocation.evidence_references,
            disclosures=("This draft was produced by a deterministic no-LLM provider.", "No trade was executed.", "Submit only through the canonical ServiceFabric runtime."),
            assumptions=("Only the supplied input and evidence references were considered.",),
            warnings=("This output is not investment advice.",),
            limitations=("No network, market-data provider, broker, external LLM, or direct capability invocation was used.",),
            human_review_required=True,
        )

    @staticmethod
    def _failure(invocation: CapabilityInvocation, warning: str) -> DeterministicProviderDraft:
        return DeterministicProviderDraft(
            invocation_id=invocation.invocation_id,
            capability_id=invocation.capability_id,
            status="blocked",
            summary="Deterministic provider could not produce a review draft.",
            evidence_references=invocation.evidence_references,
            disclosures=("This draft was produced by a deterministic no-LLM provider.", "No trade was executed.", "Submit only through the canonical ServiceFabric runtime."),
            warnings=(warning,),
            limitations=("No network, broker, external LLM, or direct capability invocation was used.",),
            human_review_required=True,
        )
