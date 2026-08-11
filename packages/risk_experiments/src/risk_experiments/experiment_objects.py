"""Versioned pre-Fixture objects and their reproducible composition boundary."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Literal

from pydantic import Field, field_validator, model_validator
from risk_registry import AssetKind, RegistryIdentity

from .models import DIGEST, IDENTIFIER, DataTruth, FrozenModel, canonical_digest
from .scientific_design import ScientificDesignPack


VERSION = r"^[A-Za-z0-9][A-Za-z0-9._+-]{0,127}$"


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError("timestamps must be timezone-aware")
    return value.astimezone(timezone.utc)


class VersionedExperimentObject(FrozenModel):
    kind: str
    namespace: str = Field(pattern=IDENTIFIER)
    object_id: str = Field(pattern=IDENTIFIER)
    version: str = Field(pattern=VERSION)
    name: str = Field(min_length=3, max_length=200)
    object_digest: str | None = Field(default=None, pattern=DIGEST)

    @property
    def reference(self) -> str:
        return (
            f"{self.kind}:{self.namespace}:{self.object_id}@{self.version}"
            f"#{self.object_digest}"
        )

    @model_validator(mode="after")
    def bind_object_digest(self) -> "VersionedExperimentObject":
        payload = self.model_dump(mode="json", exclude={"object_digest"})
        # An empty optional data-requirement collection is schema evolution, not a
        # semantic change to an existing immutable mandate or governance pack.
        if self.kind == "mandate" and not payload.get("data_requirements"):
            payload.pop("data_requirements", None)
        if self.kind == "portfolio_governance" and not payload.get("mandate", {}).get("data_requirements"):
            payload.get("mandate", {}).pop("data_requirements", None)
        expected = canonical_digest(payload)
        accepted = {expected}
        if self.kind == "mandate" and not payload.get("sources") and not payload.get("capability_requirements"):
            legacy = dict(payload)
            legacy.pop("sources", None)
            legacy.pop("capability_requirements", None)
            legacy.pop("data_requirements", None)
            legacy.pop("applicable_law_notes", None)
            legacy["constraints"] = [
                {key: value for key, value in item.items() if key not in {"clause_type", "system_treatment", "source_clause_reference"}}
                for item in payload.get("constraints", [])
            ]
            accepted.add(canonical_digest(legacy))
        if self.kind == "risk_policy" and all(not item.get("mandate_constraint_id") for item in payload.get("rules", [])):
            legacy = dict(payload)
            strip = {"mandate_constraint_id", "system_treatment", "capability_reference", "allowed_values", "unit", "denominator", "evaluation_basis", "governance_route", "missing_data_rule"}
            legacy["rules"] = [{key: value for key, value in item.items() if key not in strip} for item in payload.get("rules", [])]
            accepted.add(canonical_digest(legacy))
        if self.kind == "portfolio_governance" and not payload.get("mandate", {}).get("sources"):
            legacy = deepcopy(payload)
            mandate = legacy["mandate"]
            mandate.pop("sources", None)
            mandate.pop("capability_requirements", None)
            mandate.pop("data_requirements", None)
            mandate.pop("applicable_law_notes", None)
            mandate["constraints"] = [
                {key: value for key, value in item.items() if key not in {"clause_type", "system_treatment", "source_clause_reference"}}
                for item in mandate.get("constraints", [])
            ]
            policy = legacy["risk_policy"]
            strip = {"mandate_constraint_id", "system_treatment", "capability_reference", "allowed_values", "unit", "denominator", "evaluation_basis", "governance_route", "missing_data_rule"}
            policy["rules"] = [{key: value for key, value in item.items() if key not in strip} for item in policy.get("rules", [])]
            accepted.add(canonical_digest(legacy))
        if self.object_digest is not None and self.object_digest not in accepted:
            raise ValueError("object_digest does not match canonical content")
        object.__setattr__(self, "object_digest", self.object_digest or expected)
        return self


class PortfolioVersion(VersionedExperimentObject):
    kind: Literal["portfolio"] = "portfolio"
    snapshot_reference: str = Field(min_length=3, max_length=1000)
    snapshot_digest: str = Field(pattern=DIGEST)
    as_of: datetime
    base_currency: str = Field(pattern=r"^[A-Z]{3}$")
    data_truth: DataTruth

    _as_of = field_validator("as_of")(_utc)


class MandateConstraint(FrozenModel):
    constraint_id: str = Field(pattern=IDENTIFIER)
    category: Literal[
        "objective",
        "universe",
        "concentration",
        "liquidity",
        "loss",
        "risk_budget",
        "other",
    ]
    statement: str = Field(min_length=3, max_length=800)
    clause_type: Literal[
        "hard_constraint",
        "eligibility_rule",
        "soft_preference",
        "objective",
        "monitoring_trigger",
        "governance_rule",
        "reporting_obligation",
        "prospective_tolerance",
        "prohibition",
    ] = "hard_constraint"
    system_treatment: Literal[
        "compliance_test",
        "universe_filter",
        "scored_finding",
        "objective_evaluation",
        "alert_trigger",
        "decision_gate",
        "scheduled_obligation",
        "prospective_assessment",
        "hard_block",
    ] = "compliance_test"
    source_clause_reference: str | None = Field(default=None, min_length=3, max_length=1000)


class MandateSource(FrozenModel):
    source_id: str = Field(pattern=IDENTIFIER)
    title: str = Field(min_length=3, max_length=300)
    source_kind: Literal[
        "public_reference",
        "synthetic_design",
        "governing_document",
    ]
    reference: str = Field(min_length=3, max_length=1500)
    authority_effect: Literal["reference_only"] = "reference_only"
    note: str = Field(min_length=3, max_length=1000)


class MandateCapabilityRequirement(FrozenModel):
    capability_reference: str = Field(min_length=3, max_length=1000)
    purpose: Literal[
        "extract_rules",
        "validate_rules",
        "resolve_data",
        "evaluate_compliance",
        "evaluate_universe",
        "evaluate_proposed_state",
        "evaluate_scenario",
        "explain_assessment",
        "route_governance",
    ]
    constraint_ids: tuple[str, ...] = Field(min_length=1, max_length=100)

    @field_validator("constraint_ids")
    @classmethod
    def constraints_are_unique_and_sorted(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if value != tuple(sorted(set(value))):
            raise ValueError("capability constraint IDs must be unique and sorted")
        return value


class MandateDataRequirement(FrozenModel):
    """A semantic input role whose value is bound by an experiment, never embedded in a mandate."""

    data_role: str = Field(pattern=IDENTIFIER)
    description: str = Field(min_length=3, max_length=800)
    value_kind: Literal["scalar", "time_series", "schedule", "curve", "table", "document"]
    unit: str | None = Field(default=None, min_length=1, max_length=80)
    temporal_basis: Literal["current", "historical", "forecast", "scenario"]
    confidentiality: Literal["public", "internal", "confidential", "restricted"]
    constraint_ids: tuple[str, ...] = Field(min_length=1, max_length=100)
    binding_scope: Literal["experiment_assignment"] = "experiment_assignment"
    missing_data_rule: Literal["unable_to_assess_and_escalate"] = (
        "unable_to_assess_and_escalate"
    )

    @field_validator("constraint_ids")
    @classmethod
    def constraints_are_unique_and_sorted(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if value != tuple(sorted(set(value))):
            raise ValueError("data-requirement constraint IDs must be unique and sorted")
        return value


class MandateVersion(VersionedExperimentObject):
    kind: Literal["mandate"] = "mandate"
    objective: str = Field(min_length=3, max_length=1000)
    horizon_seconds: int = Field(ge=1, le=1_577_880_000)
    eligible_universe_reference: str = Field(min_length=3, max_length=1000)
    constraints: tuple[MandateConstraint, ...] = Field(min_length=1, max_length=100)
    sources: tuple[MandateSource, ...] = Field(default=(), max_length=100)
    capability_requirements: tuple[MandateCapabilityRequirement, ...] = Field(
        default=(),
        max_length=500,
    )
    data_requirements: tuple[MandateDataRequirement, ...] = Field(default=(), max_length=500)
    applicable_law_notes: tuple[str, ...] = ()
    effective_from: datetime
    effective_until: datetime | None = None

    _effective_from = field_validator("effective_from")(_utc)
    _effective_until = field_validator("effective_until")(
        lambda value: _utc(value) if value is not None else None
    )

    @property
    def registry_identity(self) -> RegistryIdentity:
        return RegistryIdentity(
            kind=AssetKind.MANDATE,
            namespace=self.namespace,
            asset_id=self.object_id,
            version=self.version,
        )

    @model_validator(mode="after")
    def validate_mandate(self) -> "MandateVersion":
        ids = [item.constraint_id for item in self.constraints]
        if ids != sorted(set(ids)):
            raise ValueError("mandate constraints must be unique and sorted")
        source_ids = [item.source_id for item in self.sources]
        if source_ids != sorted(set(source_ids)):
            raise ValueError("mandate sources must be unique and sorted")
        legacy = not self.sources and not self.capability_requirements and all(item.source_clause_reference is None for item in self.constraints)
        if legacy:
            if self.effective_until is not None and self.effective_until <= self.effective_from:
                raise ValueError("mandate effective_until must follow effective_from")
            return self
        if not self.sources or not self.capability_requirements or any(item.source_clause_reference is None for item in self.constraints):
            raise ValueError("new mandates require sources, capability requirements and clause references")
        known_sources = set(source_ids)
        if any(
            (item.source_clause_reference or "").split("#", 1)[0] not in known_sources
            for item in self.constraints
        ):
            raise ValueError("every mandate constraint must cite a declared source ID")
        capability_keys = [
            (item.capability_reference, item.purpose)
            for item in self.capability_requirements
        ]
        if capability_keys != sorted(set(capability_keys)):
            raise ValueError("mandate capability requirements must be unique and sorted")
        known_constraints = set(ids)
        if any(
            constraint_id not in known_constraints
            for item in self.capability_requirements
            for constraint_id in item.constraint_ids
        ):
            raise ValueError("mandate capabilities may reference only declared constraints")
        data_roles = [item.data_role for item in self.data_requirements]
        if data_roles != sorted(set(data_roles)):
            raise ValueError("mandate data requirements must be unique and sorted")
        if any(
            constraint_id not in known_constraints
            for item in self.data_requirements
            for constraint_id in item.constraint_ids
        ):
            raise ValueError("mandate data requirements may reference only declared constraints")
        if tuple(self.applicable_law_notes) != tuple(sorted(set(self.applicable_law_notes))):
            raise ValueError("applicable-law notes must be unique and sorted")
        if self.effective_until is not None and self.effective_until <= self.effective_from:
            raise ValueError("mandate effective_until must follow effective_from")
        return self


class GovernanceRoute(FrozenModel):
    outcome: Literal[
        "record_finding",
        "raise_alert",
        "request_review",
        "require_decision",
    ]
    governance_level: Literal[
        "portfolio_manager",
        "risk_officer",
        "investment_committee",
        "human_reviewer",
        "experimental_supra_agent",
    ]
    decision_policy_reference: str = Field(min_length=3, max_length=1000)
    portfolio_effects: tuple[()] = ()
    external_effects: tuple[()] = ()


class RiskPolicyRule(FrozenModel):
    rule_id: str = Field(pattern=IDENTIFIER)
    mandate_constraint_id: str | None = Field(default=None, pattern=IDENTIFIER)
    system_treatment: Literal[
        "compliance_test",
        "universe_filter",
        "scored_finding",
        "objective_evaluation",
        "alert_trigger",
        "decision_gate",
        "scheduled_obligation",
        "prospective_assessment",
        "hard_block",
    ] | None = None
    capability_reference: str | None = Field(default=None, min_length=3, max_length=1000)
    metric_reference: str = Field(min_length=3, max_length=1000)
    operator: Literal["gt", "gte", "lt", "lte", "eq", "in", "not_in"]
    threshold: Decimal | bool | str | None = None
    allowed_values: tuple[str, ...] = ()
    unit: str | None = Field(default=None, min_length=1, max_length=80)
    denominator: str | None = Field(default=None, max_length=200)
    evaluation_basis: Literal[
        "current",
        "trailing_historical",
        "proposed_state",
        "scenario",
        "forecast",
    ] | None = None
    severity: Literal["information", "warning", "breach", "critical"]
    escalation: Literal["record", "human_review", "decision_required"]
    governance_route: GovernanceRoute | None = None
    missing_data_rule: Literal["unable_to_assess_and_escalate"] = (
        "unable_to_assess_and_escalate"
    )

    @field_validator("threshold", mode="before")
    @classmethod
    def numeric_strings_become_decimals(cls, value: object) -> object:
        if isinstance(value, str):
            try:
                return Decimal(value)
            except InvalidOperation:
                return value
        return value

    @field_validator("threshold")
    @classmethod
    def threshold_is_finite(
        cls,
        value: Decimal | bool | str | None,
    ) -> Decimal | bool | str | None:
        if isinstance(value, Decimal) and not value.is_finite():
            raise ValueError("risk-policy thresholds must be finite")
        return value

    @model_validator(mode="after")
    def criterion_matches_operator(self) -> "RiskPolicyRule":
        categorical = self.operator in {"in", "not_in"}
        if categorical != bool(self.allowed_values):
            raise ValueError("in/not_in rules require allowed_values and scalar rules forbid them")
        if categorical == (self.threshold is not None):
            raise ValueError("categorical rules forbid threshold; scalar rules require threshold")
        if self.allowed_values != tuple(sorted(set(self.allowed_values))):
            raise ValueError("allowed values must be unique and sorted")
        return self


class RiskPolicySet(VersionedExperimentObject):
    kind: Literal["risk_policy"] = "risk_policy"
    mandate_reference: str = Field(min_length=20, max_length=1000)
    rules: tuple[RiskPolicyRule, ...] = Field(min_length=1, max_length=200)
    conflict_rule: Literal["most_restrictive_wins"] = "most_restrictive_wins"
    missing_metric_rule: Literal["abstain_and_escalate"] = "abstain_and_escalate"

    @property
    def registry_identity(self) -> RegistryIdentity:
        return RegistryIdentity(
            kind=AssetKind.RISK_POLICY,
            namespace=self.namespace,
            asset_id=self.object_id,
            version=self.version,
        )

    @field_validator("rules")
    @classmethod
    def rules_are_unique_and_sorted(
        cls, value: tuple[RiskPolicyRule, ...]
    ) -> tuple[RiskPolicyRule, ...]:
        ids = [item.rule_id for item in value]
        if ids != sorted(set(ids)):
            raise ValueError("risk-policy rules must be unique and sorted")
        return value


def validate_mandate_policy_binding(
    mandate: MandateVersion,
    risk_policy: RiskPolicySet,
) -> None:
    """Reject policy rules that are not traceable to the exact mandate design."""

    if risk_policy.mandate_reference != mandate.reference:
        raise ValueError("risk policy must reference the exact mandate version")
    legacy = (
        not mandate.sources
        and not mandate.capability_requirements
        and all(item.mandate_constraint_id is None for item in risk_policy.rules)
    )
    if legacy:
        return
    constraints = {item.constraint_id: item for item in mandate.constraints}
    requirements = {
        (item.capability_reference, constraint_id)
        for item in mandate.capability_requirements
        for constraint_id in item.constraint_ids
    }
    for rule in risk_policy.rules:
        constraint = constraints.get(rule.mandate_constraint_id)
        if constraint is None:
            raise ValueError("risk-policy rules must reference a mandate constraint")
        if rule.system_treatment != constraint.system_treatment:
            raise ValueError("risk-policy treatment must match its mandate constraint")
        if (rule.capability_reference, rule.mandate_constraint_id) not in requirements:
            raise ValueError("risk-policy capability must be declared by the mandate")


class PortfolioGovernancePack(VersionedExperimentObject):
    kind: Literal["portfolio_governance"] = "portfolio_governance"
    portfolio: PortfolioVersion
    mandate: MandateVersion
    risk_policy: RiskPolicySet

    @property
    def registry_identity(self) -> RegistryIdentity:
        return RegistryIdentity(
            kind=AssetKind.PORTFOLIO_GOVERNANCE,
            namespace=self.namespace,
            asset_id=self.object_id,
            version=self.version,
        )

    @model_validator(mode="after")
    def policy_uses_exact_mandate(self) -> "PortfolioGovernancePack":
        validate_mandate_policy_binding(self.mandate, self.risk_policy)
        return self


class DatasetRevisionBinding(FrozenModel):
    dataset_id: str = Field(pattern=IDENTIFIER)
    reference: str = Field(min_length=3, max_length=1000)
    revision: str = Field(min_length=1, max_length=200)
    content_digest: str = Field(pattern=DIGEST)
    data_truth: DataTruth
    rights_policy_reference: str = Field(min_length=3, max_length=1000)
    available_at: datetime

    _available_at = field_validator("available_at")(_utc)


class DataSnapshotManifest(VersionedExperimentObject):
    kind: Literal["data_snapshot_manifest"] = "data_snapshot_manifest"
    as_of: datetime
    datasets: tuple[DatasetRevisionBinding, ...] = Field(min_length=1, max_length=200)
    point_in_time_rule: Literal["available_at_lte_as_of"] = "available_at_lte_as_of"

    _as_of = field_validator("as_of")(_utc)

    @model_validator(mode="after")
    def datasets_are_eligible(self) -> "DataSnapshotManifest":
        ids = [item.dataset_id for item in self.datasets]
        if ids != sorted(set(ids)):
            raise ValueError("dataset bindings must be unique and sorted")
        if any(item.available_at > self.as_of for item in self.datasets):
            raise ValueError("data available after the manifest as_of is ineligible")
        return self


class MarketEnvironmentSnapshot(VersionedExperimentObject):
    kind: Literal["market_environment"] = "market_environment"
    as_of: datetime
    data_manifest_reference: str = Field(min_length=20, max_length=1000)
    observation_roles: tuple[str, ...] = Field(min_length=1, max_length=100)
    unavailable_observation_rule: Literal["remain_missing"] = "remain_missing"

    _as_of = field_validator("as_of")(_utc)

    @field_validator("observation_roles")
    @classmethod
    def roles_are_unique_and_sorted(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if value != tuple(sorted(set(value))):
            raise ValueError("environment observation roles must be unique and sorted")
        return value


class ScenarioDefinition(VersionedExperimentObject):
    kind: Literal["scenario"] = "scenario"
    scenario_kind: Literal["observed", "historical", "synthetic", "simulated"]
    base_environment_reference: str = Field(min_length=20, max_length=1000)
    transformation: str = Field(min_length=3, max_length=1200)
    calibration_reference: str | None = Field(default=None, max_length=1000)
    seed: int | None = Field(default=None, ge=0, le=2_147_483_647)

    @model_validator(mode="after")
    def generated_scenarios_have_a_seed(self) -> "ScenarioDefinition":
        generated = self.scenario_kind in {"synthetic", "simulated"}
        if generated != (self.seed is not None):
            raise ValueError("synthetic and simulated scenarios require exactly one seed")
        return self


class PortfolioEnvironmentView(VersionedExperimentObject):
    kind: Literal["portfolio_environment_view"] = "portfolio_environment_view"
    portfolio_reference: str = Field(min_length=20, max_length=1000)
    environment_reference: str = Field(min_length=20, max_length=1000)
    scenario_reference: str = Field(min_length=20, max_length=1000)
    resolver_version: str = Field(pattern=VERSION)


class ContextGraphEdge(FrozenModel):
    source_reference: str = Field(min_length=3, max_length=1000)
    relationship: str = Field(pattern=IDENTIFIER)
    target_reference: str = Field(min_length=3, max_length=1000)


class ContextGraphSnapshot(VersionedExperimentObject):
    kind: Literal["context_graph"] = "context_graph"
    as_of: datetime
    node_references: tuple[str, ...] = Field(min_length=1, max_length=10_000)
    edges: tuple[ContextGraphEdge, ...] = Field(default=(), max_length=50_000)

    _as_of = field_validator("as_of")(_utc)

    @model_validator(mode="after")
    def graph_is_closed_and_deterministic(self) -> "ContextGraphSnapshot":
        if self.node_references != tuple(sorted(set(self.node_references))):
            raise ValueError("context graph nodes must be unique and sorted")
        edge_keys = [
            (item.source_reference, item.relationship, item.target_reference)
            for item in self.edges
        ]
        if edge_keys != sorted(set(edge_keys)):
            raise ValueError("context graph edges must be unique and sorted")
        nodes = set(self.node_references)
        if any(item.source_reference not in nodes or item.target_reference not in nodes for item in self.edges):
            raise ValueError("context graph edges must remain inside the declared node set")
        return self


class WorldContextPack(VersionedExperimentObject):
    kind: Literal["world_context"] = "world_context"
    data_manifest: DataSnapshotManifest
    environment: MarketEnvironmentSnapshot
    scenario: ScenarioDefinition
    portfolio_view: PortfolioEnvironmentView
    context_graph: ContextGraphSnapshot

    @property
    def registry_identity(self) -> RegistryIdentity:
        return RegistryIdentity(
            kind=AssetKind.WORLD_CONTEXT,
            namespace=self.namespace,
            asset_id=self.object_id,
            version=self.version,
        )

    @model_validator(mode="after")
    def world_links_are_exact(self) -> "WorldContextPack":
        if self.environment.data_manifest_reference != self.data_manifest.reference:
            raise ValueError("environment must reference the pack data manifest")
        if self.scenario.base_environment_reference != self.environment.reference:
            raise ValueError("scenario must reference the pack environment")
        if self.portfolio_view.environment_reference != self.environment.reference:
            raise ValueError("portfolio view must reference the pack environment")
        if self.portfolio_view.scenario_reference != self.scenario.reference:
            raise ValueError("portfolio view must reference the pack scenario")
        as_of_values = {
            self.data_manifest.as_of,
            self.environment.as_of,
            self.context_graph.as_of,
        }
        if len(as_of_values) != 1:
            raise ValueError("world-context components must share one as_of boundary")
        return self


class CapabilityPack(VersionedExperimentObject):
    kind: Literal["capability_pack"] = "capability_pack"
    capabilities: tuple[RegistryIdentity, ...] = Field(min_length=1, max_length=500)
    selection_rule: Literal["agent_selects_within_pack"] = "agent_selects_within_pack"

    @field_validator("capabilities")
    @classmethod
    def capabilities_are_exact_and_sorted(
        cls, value: tuple[RegistryIdentity, ...]
    ) -> tuple[RegistryIdentity, ...]:
        if any(item.kind is not AssetKind.CAPABILITY for item in value):
            raise ValueError("capability pack may contain only capability identities")
        references = [item.reference for item in value]
        if references != sorted(set(references)):
            raise ValueError("capability identities must be unique and sorted")
        return value


class DatasetAccessGrant(FrozenModel):
    grant_id: str = Field(pattern=IDENTIFIER)
    capability_reference: str = Field(min_length=3, max_length=1000)
    dataset_reference: str = Field(min_length=3, max_length=1000)
    allowed_operations: tuple[Literal["read", "aggregate", "filter", "join"], ...] = (
        "read",
    )
    temporal_rule: Literal["respect_fixture_as_of"] = "respect_fixture_as_of"

    @field_validator("allowed_operations")
    @classmethod
    def operations_are_unique_and_sorted(
        cls, value: tuple[str, ...]
    ) -> tuple[str, ...]:
        if value != tuple(sorted(set(value))):
            raise ValueError("allowed operations must be unique and sorted")
        return value


class ConnectorDefinition(VersionedExperimentObject):
    kind: Literal["connector"] = "connector"
    adapter_reference: str = Field(min_length=3, max_length=1000)
    source_type: Literal["duckdb", "http_api", "mcp", "file"]
    rights_policy_reference: str = Field(min_length=3, max_length=1000)
    freshness_rule: str = Field(min_length=3, max_length=500)
    temporal_semantics: str = Field(min_length=3, max_length=500)
    credential_reference: str | None = Field(default=None, pattern=r"^opaque:[A-Za-z0-9._-]+$")
    allowed_effects: tuple[()] = ()


class ModelRoutePolicy(VersionedExperimentObject):
    kind: Literal["model_route"] = "model_route"
    route_references: tuple[str, ...] = Field(min_length=1, max_length=20)
    fallback_rule: Literal["fail_closed", "deterministic_fixture_only"]
    max_calls: int = Field(ge=0, le=10_000)

    @field_validator("route_references")
    @classmethod
    def routes_are_unique_and_sorted(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if value != tuple(sorted(set(value))):
            raise ValueError("model routes must be unique and sorted")
        return value


class ResourceEnvelope(VersionedExperimentObject):
    kind: Literal["resource_envelope"] = "resource_envelope"
    capability_pack: CapabilityPack
    dataset_access_grants: tuple[DatasetAccessGrant, ...] = ()
    connectors: tuple[ConnectorDefinition, ...] = ()
    model_route: ModelRoutePolicy
    undeclared_resource_rule: Literal["deny"] = "deny"

    @property
    def registry_identity(self) -> RegistryIdentity:
        return RegistryIdentity(
            kind=AssetKind.RESOURCE_ENVELOPE,
            namespace=self.namespace,
            asset_id=self.object_id,
            version=self.version,
        )

    def allows_capability(self, reference: str) -> bool:
        return any(
            identity.reference == reference
            for identity in self.capability_pack.capabilities
        )

    def allows_dataset(self, capability_reference: str, dataset_reference: str) -> bool:
        return any(
            grant.capability_reference == capability_reference
            and grant.dataset_reference == dataset_reference
            for grant in self.dataset_access_grants
        )

    @model_validator(mode="after")
    def grants_use_reachable_capabilities(self) -> "ResourceEnvelope":
        capabilities = {item.reference for item in self.capability_pack.capabilities}
        grant_ids = [item.grant_id for item in self.dataset_access_grants]
        if grant_ids != sorted(set(grant_ids)):
            raise ValueError("dataset access grants must be unique and sorted")
        if any(item.capability_reference not in capabilities for item in self.dataset_access_grants):
            raise ValueError("dataset grants must name a capability in the pack")
        connector_refs = [item.reference for item in self.connectors]
        if connector_refs != sorted(set(connector_refs)):
            raise ValueError("connectors must be unique and sorted")
        return self


class ProcessingDefinition(VersionedExperimentObject):
    kind: Literal["processing_definition"] = "processing_definition"
    agent: RegistryIdentity
    graph: RegistryIdentity
    workflow: RegistryIdentity
    stop_rule: str = Field(min_length=3, max_length=800)

    @model_validator(mode="after")
    def identities_have_expected_kinds(self) -> "ProcessingDefinition":
        expected = (
            (self.agent, AssetKind.AGENT),
            (self.graph, AssetKind.AGENT_GRAPH),
            (self.workflow, AssetKind.WORKFLOW),
        )
        if any(identity.kind is not kind for identity, kind in expected):
            raise ValueError("processing identities have incompatible Registry kinds")
        return self


class AutonomyPolicy(VersionedExperimentObject):
    kind: Literal["autonomy_policy"] = "autonomy_policy"
    mode: Literal["human_only", "supra_agent_allowed"]
    proposal_actor_types: tuple[Literal["agent", "human"], ...]
    resolution_actor_types: tuple[Literal["human", "supra_agent"], ...]

    @field_validator("proposal_actor_types", "resolution_actor_types")
    @classmethod
    def actor_types_are_unique_and_sorted(
        cls, value: tuple[str, ...]
    ) -> tuple[str, ...]:
        if value != tuple(sorted(set(value))):
            raise ValueError("autonomy actor types must be unique and sorted")
        return value

    @model_validator(mode="after")
    def human_only_means_human_only(self) -> "AutonomyPolicy":
        if self.mode == "human_only" and self.resolution_actor_types != ("human",):
            raise ValueError("human-only autonomy permits only human resolution")
        return self


class SupraAgentPolicy(VersionedExperimentObject):
    kind: Literal["supra_agent_policy"] = "supra_agent_policy"
    enabled: bool = False
    agent_reference: str | None = Field(default=None, max_length=1000)
    allowed_decision_classes: tuple[str, ...] = ()
    minimum_evidence_coverage: Decimal = Field(default=Decimal("1"), ge=0, le=1)
    abstain_on: tuple[str, ...] = ("missing_evidence", "policy_conflict")
    max_resolutions_per_run: int = Field(default=0, ge=0, le=10_000)

    @field_validator("allowed_decision_classes", "abstain_on")
    @classmethod
    def policy_values_are_unique_and_sorted(
        cls, value: tuple[str, ...]
    ) -> tuple[str, ...]:
        if value != tuple(sorted(set(value))):
            raise ValueError("supra-agent policy values must be unique and sorted")
        return value

    @model_validator(mode="after")
    def disabled_policy_has_no_authority(self) -> "SupraAgentPolicy":
        if not self.enabled and (
            self.agent_reference is not None
            or self.allowed_decision_classes
            or self.max_resolutions_per_run != 0
        ):
            raise ValueError("disabled supra-agent policy cannot grant resolution authority")
        if self.enabled and (
            self.agent_reference is None
            or not self.allowed_decision_classes
            or self.max_resolutions_per_run < 1
        ):
            raise ValueError("enabled supra-agent policy requires bounded explicit authority")
        return self


class EffectPolicy(VersionedExperimentObject):
    kind: Literal["effect_policy"] = "effect_policy"
    external_effects: Literal["disabled"] = "disabled"
    allowed_simulated_effects: tuple[str, ...] = ()
    prohibited_effects: tuple[str, ...] = Field(min_length=1)

    @field_validator("allowed_simulated_effects", "prohibited_effects")
    @classmethod
    def effects_are_unique_and_sorted(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if value != tuple(sorted(set(value))):
            raise ValueError("effect names must be unique and sorted")
        return value


class AuthorityEnvelope(VersionedExperimentObject):
    kind: Literal["authority_envelope"] = "authority_envelope"
    mandate_reference: str = Field(min_length=20, max_length=1000)
    risk_policy_reference: str = Field(min_length=20, max_length=1000)
    processing: ProcessingDefinition
    autonomy: AutonomyPolicy
    supra_agent: SupraAgentPolicy
    effects: EffectPolicy

    @property
    def registry_identity(self) -> RegistryIdentity:
        return RegistryIdentity(
            kind=AssetKind.AUTHORITY_ENVELOPE,
            namespace=self.namespace,
            asset_id=self.object_id,
            version=self.version,
        )

    @model_validator(mode="after")
    def supra_authority_matches_autonomy(self) -> "AuthorityEnvelope":
        if self.supra_agent.enabled != (self.autonomy.mode == "supra_agent_allowed"):
            raise ValueError("supra-agent enablement must match the autonomy mode")
        if self.supra_agent.enabled and "supra_agent" not in self.autonomy.resolution_actor_types:
            raise ValueError("enabled supra-agent must be an allowed resolution actor")
        return self


class EvaluationThreshold(FrozenModel):
    metric_reference: str = Field(min_length=20, max_length=1000)
    operator: Literal["gt", "gte", "lt", "lte", "eq"]
    value: Decimal


class EvaluationSuiteDefinition(VersionedExperimentObject):
    kind: Literal["evaluation_suite"] = "evaluation_suite"
    scientific_design_reference: str = Field(min_length=20, max_length=1000)
    case_set_reference: str = Field(min_length=3, max_length=1000)
    seeds: tuple[int, ...] = Field(min_length=1, max_length=100)
    repeat_count: int = Field(ge=1, le=100)
    thresholds: tuple[EvaluationThreshold, ...] = ()
    out_of_sample_policy: Literal["sealed_until_versions_frozen"] = (
        "sealed_until_versions_frozen"
    )

    @field_validator("seeds")
    @classmethod
    def seeds_are_unique_and_sorted(cls, value: tuple[int, ...]) -> tuple[int, ...]:
        if value != tuple(sorted(set(value))):
            raise ValueError("evaluation seeds must be unique and sorted")
        return value

    @field_validator("thresholds")
    @classmethod
    def thresholds_are_unique_and_sorted(
        cls, value: tuple[EvaluationThreshold, ...]
    ) -> tuple[EvaluationThreshold, ...]:
        keys = [(item.metric_reference, item.operator, str(item.value)) for item in value]
        if keys != sorted(set(keys)):
            raise ValueError("evaluation thresholds must be unique and sorted")
        return value


class ReportTemplateDefinition(VersionedExperimentObject):
    kind: Literal["report_template"] = "report_template"
    sections: tuple[str, ...] = Field(min_length=1, max_length=100)
    required_evidence_roles: tuple[str, ...] = Field(min_length=1, max_length=100)
    hidden_calculations: Literal[False] = False

    @field_validator("sections")
    @classmethod
    def sections_are_unique(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(value) != len(set(value)):
            raise ValueError("report sections must be unique")
        return value

    @field_validator("required_evidence_roles")
    @classmethod
    def evidence_roles_are_unique_and_sorted(
        cls, value: tuple[str, ...]
    ) -> tuple[str, ...]:
        if value != tuple(sorted(set(value))):
            raise ValueError("required evidence roles must be unique and sorted")
        return value


class DashboardPackageDefinition(VersionedExperimentObject):
    kind: Literal["dashboard_package"] = "dashboard_package"
    views: tuple[str, ...] = Field(min_length=1, max_length=100)
    metric_references: tuple[str, ...] = Field(min_length=1, max_length=100)
    hidden_calculations: Literal[False] = False

    @field_validator("views")
    @classmethod
    def views_are_unique(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(value) != len(set(value)):
            raise ValueError("dashboard views must be unique")
        return value

    @field_validator("metric_references")
    @classmethod
    def metrics_are_unique_and_sorted(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if value != tuple(sorted(set(value))):
            raise ValueError("dashboard metrics must be unique and sorted")
        return value


class OutputEvaluationPack(VersionedExperimentObject):
    kind: Literal["output_evaluation"] = "output_evaluation"
    evaluation_suite: EvaluationSuiteDefinition
    report_template: ReportTemplateDefinition
    dashboard: DashboardPackageDefinition

    @property
    def registry_identity(self) -> RegistryIdentity:
        return RegistryIdentity(
            kind=AssetKind.OUTPUT_EVALUATION,
            namespace=self.namespace,
            asset_id=self.object_id,
            version=self.version,
        )


class ExperimentObjectSet(FrozenModel):
    schema_version: Literal["portfolio-risk.experiment-object-set/v1"] = (
        "portfolio-risk.experiment-object-set/v1"
    )
    namespace: str = Field(pattern=IDENTIFIER)
    object_set_id: str = Field(pattern=IDENTIFIER)
    version: str = Field(pattern=VERSION)
    scientific_design: ScientificDesignPack
    portfolio_governance: PortfolioGovernancePack
    world_context: WorldContextPack
    resource_envelope: ResourceEnvelope
    authority_envelope: AuthorityEnvelope
    output_evaluation: OutputEvaluationPack
    resolver_version: str = Field(pattern=VERSION)
    world_context_digest: str | None = Field(default=None, pattern=DIGEST)
    resource_envelope_digest: str | None = Field(default=None, pattern=DIGEST)
    authority_envelope_digest: str | None = Field(default=None, pattern=DIGEST)
    evaluation_envelope_digest: str | None = Field(default=None, pattern=DIGEST)
    fixture_context_digest: str | None = Field(default=None, pattern=DIGEST)

    @property
    def registry_identity(self) -> RegistryIdentity:
        return RegistryIdentity(
            kind=AssetKind.EXPERIMENT_OBJECT_SET,
            namespace=self.namespace,
            asset_id=self.object_set_id,
            version=self.version,
        )

    @model_validator(mode="after")
    def bind_composition(self) -> "ExperimentObjectSet":
        if (
            self.world_context.portfolio_view.portfolio_reference
            != self.portfolio_governance.portfolio.reference
        ):
            raise ValueError("world context must use the governed portfolio")
        dataset_references = {
            item.reference for item in self.world_context.data_manifest.datasets
        }
        if any(
            grant.dataset_reference not in dataset_references
            for grant in self.resource_envelope.dataset_access_grants
        ):
            raise ValueError("dataset grants must remain inside the world data manifest")
        if self.authority_envelope.mandate_reference != self.portfolio_governance.mandate.reference:
            raise ValueError("authority envelope must use the governed mandate")
        if self.authority_envelope.risk_policy_reference != self.portfolio_governance.risk_policy.reference:
            raise ValueError("authority envelope must use the governed risk policy")
        if (
            self.output_evaluation.evaluation_suite.scientific_design_reference
            != self.scientific_design.reference
        ):
            raise ValueError("evaluation suite must reference the scientific design pack")
        metric_reference = self.scientific_design.metric.reference
        if any(
            item.metric_reference != metric_reference
            for item in self.output_evaluation.evaluation_suite.thresholds
        ):
            raise ValueError("evaluation thresholds must use the scientific-design metric")
        if tuple(self.output_evaluation.dashboard.metric_references) != (metric_reference,):
            raise ValueError("dashboard must project the scientific-design metric")

        expected = {
            "world_context_digest": canonical_digest(
                {
                    "portfolio_governance": self.portfolio_governance.object_digest,
                    "world_context": self.world_context.object_digest,
                }
            ),
            "resource_envelope_digest": self.resource_envelope.object_digest,
            "authority_envelope_digest": canonical_digest(
                {
                    "portfolio_governance": self.portfolio_governance.object_digest,
                    "authority_envelope": self.authority_envelope.object_digest,
                }
            ),
            "evaluation_envelope_digest": canonical_digest(
                {
                    "scientific_design": self.scientific_design.pack_digest,
                    "output_evaluation": self.output_evaluation.object_digest,
                }
            ),
        }
        expected["fixture_context_digest"] = canonical_digest(
            {
                **expected,
                "resolver_version": self.resolver_version,
            }
        )
        for field_name, digest in expected.items():
            current = getattr(self, field_name)
            if current is not None and current != digest:
                raise ValueError(f"{field_name} does not match canonical content")
            object.__setattr__(self, field_name, digest)
        return self
