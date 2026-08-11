"""Loader for reviewed-synthetic mandate and policy design fixtures."""

from __future__ import annotations

import json
from pathlib import Path

from .experiment_objects import (
    MandateVersion,
    RiskPolicySet,
    validate_mandate_policy_binding,
)


def load_synthetic_mandate_fixture(path: Path) -> tuple[MandateVersion, RiskPolicySet]:
    """Resolve one fixture into exact immutable mandate and policy versions."""

    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("fixture_kind") != "synthetic-mandate-and-policy/v1":
        raise ValueError("unsupported synthetic mandate fixture kind")
    if payload.get("truth") != "reviewed_synthetic":
        raise ValueError("mandate fixture must be explicitly reviewed_synthetic")
    mandate = MandateVersion.model_validate(payload["mandate"])
    policy_payload = dict(payload["risk_policy"])
    policy_payload["mandate_reference"] = mandate.reference
    risk_policy = RiskPolicySet.model_validate(policy_payload)
    validate_mandate_policy_binding(mandate, risk_policy)
    return mandate, risk_policy
