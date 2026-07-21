"""Wave 0B active agents that delegate all calculations to registered capabilities."""

from typing import Any

from risk_capabilities import CapabilityRegistry, CapabilityResult

from .roles import ACTIVE_AGENT_ROLE_IDS, ROLE_BY_ID


class RegisteredCapabilityAgent:
    """An active role that only delegates to its explicitly granted registry IDs."""

    def __init__(self, role_id: str, registry: CapabilityRegistry) -> None:
        if role_id not in ACTIVE_AGENT_ROLE_IDS:
            raise ValueError(f"agent role is not active in Wave 0B: {role_id}")
        self.role = ROLE_BY_ID[role_id]
        self.registry = registry

    def invoke(self, capability_id: str, request: Any) -> CapabilityResult[Any]:
        if capability_id not in self.role.allowed_capability_ids:
            raise ValueError(f"capability is not granted to {self.role.role_id}: {capability_id}")
        return self.registry.invoke(capability_id, request)
