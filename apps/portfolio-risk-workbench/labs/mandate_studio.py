"""Mandate Studio services over immutable reference-informed design fixtures."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator
from risk_capabilities.catalog import CAPABILITY_BY_ID
from risk_experiments import (
    MandateVersion,
    RiskPolicySet,
    load_synthetic_mandate_fixture,
    validate_mandate_policy_binding,
)


def _repository_root(start: Path) -> Path:
    for candidate in (start, *start.parents):
        if (candidate / ".git").exists():
            return candidate
    raise RuntimeError("repository root is unavailable")


REPOSITORY_ROOT = _repository_root(Path(__file__).resolve())
MANDATE_FIXTURE_ROOT = REPOSITORY_ROOT / "data" / "fixtures" / "synthetic" / "mandates"
MANDATE_FIXTURES = tuple(
    path for path in sorted(MANDATE_FIXTURE_ROOT.glob("*.json")) if path.is_file()
)


# This registry is deliberately semantic: a capability ID existing is not proof that
# its output constructs a specific policy metric. Only reviewed exact bindings belong
# here. Missing entries become capability proposal candidates.
METRIC_CONSTRUCTION_REGISTRY: dict[str, dict[str, Any]] = {
    "metric:risk:cash-weight@1.0.0": {
        "capability_chain": ("portfolio.snapshot.create", "portfolio.exposure.summarize"),
        "native_data_roles": ("eligible_prices", "portfolio_positions"),
        "note": "ExposureSnapshot exposes cash value and portfolio NAV for an exact ratio.",
    },
    "metric:risk:scenario-loss-nav@1.0.0": {
        "capability_chain": ("risk.scenario.evaluate",),
        "native_data_roles": ("portfolio_snapshot", "scenario_definition"),
        "note": "ScenarioResult exposes deterministic scenario loss against portfolio NAV.",
    },
    "metric:risk:credit-rate-scenario-loss-nav@1.0.0": {
        "capability_chain": ("risk.scenario.evaluate",),
        "native_data_roles": ("portfolio_snapshot", "scenario_definition"),
        "note": "The reviewed scenario capability can evaluate declared credit and rate shocks.",
    },
}


def _metric_gap_candidate(rule: Any, declared_data_roles: tuple[str, ...]) -> dict[str, Any]:
    digest = hashlib.sha256(rule.metric_reference.encode("utf-8")).hexdigest()[:10]
    return {
        "proposal_key": f"mandate-metric-gap-{digest}",
        "status": "identified_requires_human_design",
        "decision": "compose_or_create",
        "rule_id": rule.rule_id,
        "metric_reference": rule.metric_reference,
        "declared_capability_id": capability_id(rule.capability_reference),
        "required_data_roles": list(declared_data_roles),
        "requirement": (
            f"Construct and validate {rule.metric_reference} for mandate rule {rule.rule_id}; "
            f"produce unit {rule.unit or 'declared by contract'}, denominator "
            f"{rule.denominator or 'not applicable'}, temporal basis {rule.evaluation_basis}, "
            "typed evidence, missing-data abstention and no financial or external effects. "
            "Assess reuse and composition before proposing a new atomic capability."
        ),
        "backlog_effect": "not_saved_until_human_review",
    }


class StudioModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)


class MandateDesignPreviewRequest(StudioModel):
    base_mandate_id: str = Field(min_length=3, max_length=160)
    name: str = Field(min_length=3, max_length=200)
    objective: str = Field(min_length=10, max_length=1200)
    change_request: str = Field(min_length=10, max_length=4000)

    @field_validator("base_mandate_id")
    @classmethod
    def safe_identifier(cls, value: str) -> str:
        if not re.fullmatch(r"[a-z0-9][a-z0-9._-]{1,159}", value):
            raise ValueError("base mandate ID is invalid")
        return value


class MandateRegistrationRequest(StudioModel):
    mandate_id: str = Field(min_length=3, max_length=160)
    actor: str = Field(min_length=3, max_length=128)


class MandateValidationRequest(StudioModel):
    mandate_id: str = Field(min_length=3, max_length=160)


def capability_id(reference: str) -> str:
    """Resolve the native capability ID from a Registry-style reference."""

    match = re.fullmatch(r"capability:[^:]+:(?P<capability>[^@]+)@[^#]+(?:#.*)?", reference)
    if not match:
        raise ValueError(f"invalid capability reference: {reference}")
    return match.group("capability")


def _fixtures() -> dict[str, tuple[Path, MandateVersion, RiskPolicySet]]:
    records: dict[str, tuple[Path, MandateVersion, RiskPolicySet]] = {}
    for path in MANDATE_FIXTURES:
        mandate, policy = load_synthetic_mandate_fixture(path)
        if mandate.object_id in records:
            raise ValueError(f"duplicate mandate fixture: {mandate.object_id}")
        records[mandate.object_id] = (path, mandate, policy)
    return records


def mandate_bundle(mandate_id: str) -> tuple[Path, MandateVersion, RiskPolicySet]:
    try:
        return _fixtures()[mandate_id]
    except KeyError as error:
        raise KeyError("mandate fixture not found") from error


def validate_bundle(mandate: MandateVersion, policy: RiskPolicySet) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    try:
        validate_mandate_policy_binding(mandate, policy)
    except ValueError as error:
        errors.append(str(error))

    rules_by_constraint = {item.mandate_constraint_id: item for item in policy.rules}
    missing_rules = [
        item.constraint_id
        for item in mandate.constraints
        if item.constraint_id not in rules_by_constraint
    ]
    if missing_rules:
        errors.append("constraints without reviewed policy rules: " + ", ".join(missing_rules))

    data_roles_by_constraint: dict[str, list[str]] = {}
    for requirement in mandate.data_requirements:
        for constraint_id in requirement.constraint_ids:
            data_roles_by_constraint.setdefault(constraint_id, []).append(requirement.data_role)

    bindings = []
    proposal_candidates = []
    for rule in policy.rules:
        native_id = capability_id(rule.capability_reference)
        available = native_id in CAPABILITY_BY_ID
        if not available:
            errors.append(f"registered capability is unavailable: {native_id}")
        construction = METRIC_CONSTRUCTION_REGISTRY.get(rule.metric_reference)
        construction_chain = tuple(construction["capability_chain"]) if construction else ()
        chain_available = bool(construction_chain) and all(
            item in CAPABILITY_BY_ID for item in construction_chain
        )
        evaluator_matches = bool(construction_chain) and native_id == construction_chain[-1]
        constructible = available and chain_available and evaluator_matches
        declared_data_roles = tuple(sorted(data_roles_by_constraint.get(rule.mandate_constraint_id, ())))
        if not constructible:
            proposal = _metric_gap_candidate(rule, declared_data_roles)
            proposal_candidates.append(proposal)
            warnings.append(
                f"metric construction is not validated for {rule.metric_reference}; "
                f"proposal candidate {proposal['proposal_key']} was identified"
            )
        bindings.append(
            {
                "constraint_id": rule.mandate_constraint_id,
                "rule_id": rule.rule_id,
                "system_treatment": rule.system_treatment,
                "metric_reference": rule.metric_reference,
                "capability_id": native_id,
                "capability_status": "runtime_available" if available else "unavailable",
                "metric_status": "constructible" if constructible else "capability_gap",
                "capability_chain": list(construction_chain),
                "required_data_roles": [
                    *(construction.get("native_data_roles", ()) if construction else ()),
                    *declared_data_roles,
                ],
                "experiment_data_binding": "required" if declared_data_roles else "portfolio_context",
                "construction_note": construction.get("note") if construction else "No reviewed metric implementation is registered.",
                "evaluation_basis": rule.evaluation_basis,
                "governance_outcome": rule.governance_route.outcome,
                "governance_level": rule.governance_route.governance_level,
                "effects": [],
            }
        )

    if any(source.authority_effect != "reference_only" for source in mandate.sources):
        errors.append("public and synthetic sources must remain reference_only")
    if not mandate.applicable_law_notes:
        warnings.append("No non-operative applicable-law note is recorded.")
    return {
        "valid": not errors,
        "executable": not errors and not proposal_candidates,
        "errors": errors,
        "warnings": warnings,
        "constraint_count": len(mandate.constraints),
        "rule_count": len(policy.rules),
        "capability_count": len({item["capability_id"] for item in bindings}),
        "constructible_metric_count": sum(item["metric_status"] == "constructible" for item in bindings),
        "capability_gap_count": len(proposal_candidates),
        "data_requirement_count": len(mandate.data_requirements),
        "bindings": bindings,
        "capability_proposal_candidates": proposal_candidates,
        "checks": [
            {"label": "Exact mandate version", "passed": policy.mandate_reference == mandate.reference},
            {"label": "Clause coverage", "passed": not missing_rules},
            {"label": "Capability availability", "passed": all(item["capability_status"] == "runtime_available" for item in bindings)},
            {"label": "Metric construction", "passed": not proposal_candidates},
            {"label": "External data roles declared", "passed": all(requirement.binding_scope == "experiment_assignment" for requirement in mandate.data_requirements)},
            {"label": "Reference-only sources", "passed": all(source.authority_effect == "reference_only" for source in mandate.sources)},
            {"label": "No financial or external effects", "passed": all(item["effects"] == [] for item in bindings)},
        ],
    }


def catalogue() -> dict[str, Any]:
    records = []
    for path, mandate, policy in _fixtures().values():
        validation = validate_bundle(mandate, policy)
        records.append(
            {
                "mandate": mandate.model_dump(mode="json"),
                "risk_policy": policy.model_dump(mode="json"),
                "validation": validation,
                "source_file": str(path.relative_to(REPOSITORY_ROOT)),
                "design_state": "compiled_and_reviewed",
                "experiment_ready": validation["executable"],
            }
        )
    return {
        "schema_version": "portfolio-risk.mandate-studio/v1",
        "records": sorted(records, key=lambda item: item["mandate"]["name"]),
        "workflow": [
            "describe_intent",
            "extract_and_classify_clauses",
            "bind_capabilities_and_data",
            "review_policy_and_governance",
            "validate_fixture",
            "register_exact_versions",
        ],
        "authority": "design_time_only",
        "applicable_law": "reference_metadata_only",
        "effects": [],
    }


def design_preview(request: MandateDesignPreviewRequest) -> dict[str, Any]:
    _, base, policy = mandate_bundle(request.base_mandate_id)
    return {
        "status": "design_brief_ready",
        "based_on": base.reference,
        "name": request.name,
        "objective": request.objective,
        "requested_diff": request.change_request,
        "preserved": {
            "source_authority": "reference_only",
            "effects": [],
            "missing_data": policy.missing_metric_rule,
            "existing_constraint_ids": [item.constraint_id for item in base.constraints],
        },
        "required_review": [
            "Classify each requested clause before making it executable.",
            "Reuse an existing capability before proposing a new one.",
            "Define semantic metric, units, denominator and temporal basis.",
            "Select the governance level and decision policy for every material result.",
            "Run deterministic normal, missing-data and boundary fixtures before Registry admission.",
        ],
        "open_questions": [
            "Which requested terms are hard constraints, objectives, preferences or monitoring triggers?",
            "Which portfolio or sleeve is governed and from what effective date?",
            "Which values must be current, historical, proposed-state, scenario or forecast measures?",
        ],
        "studio_codex_brief": (
            "Use the servicefabric-portfolio-mandate-builder skill. Work from the exact "
            f"base mandate {base.reference}. Apply only this requested diff: {request.change_request} "
            "Preserve satisfied clauses and immutable source provenance. Reuse current risk_experiments "
            "MandateVersion, RiskPolicySet, Registry and capability contracts. Add or modify reviewed-"
            "synthetic fixtures and tests. Do not interpret law, create financial effects, register, "
            "publish or merge without a separate human review."
        ),
    }
