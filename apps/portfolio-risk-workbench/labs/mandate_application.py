"""Effect-free application of a registered mandate to one resolved portfolio fixture."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Literal

import pyarrow.parquet as parquet
import yaml
from pydantic import BaseModel, ConfigDict, Field
from risk_capabilities import (
    CapabilityRegistry,
    EvidenceReference,
    ExposureSummaryRequest,
    PortfolioSnapshotRequest,
    PositionSpecification,
)
from risk_data import NormalizedMarketRecord
from risk_decisions import DecisionOutcome, DecisionProposal, canonical_digest
from risk_domain import ArtifactReference, CashBalance, InstrumentIdentifier, RiskFinding
from risk_experiments import build_calibration_pilot
from risk_registry import LifecycleState, RegistryNotFound

from mandate_studio import capability_id, mandate_bundle
from registry_sources import discover_registry_projections


LABS_ROOT = Path(__file__).resolve().parent
REPOSITORY_ROOT = LABS_ROOT.parents[2]
PORTFOLIO_PATH = REPOSITORY_ROOT / "examples" / "portfolio-risk-thesis" / "portfolios" / "diversified.yaml"
INSTRUMENT_MAP_PATH = REPOSITORY_ROOT / "examples" / "portfolio-risk-thesis" / "data" / "instrument_map.yaml"
MARKET_PATH = REPOSITORY_ROOT / "data" / "fixtures" / "synthetic" / "thesis-day1" / "market.parquet"
SUPPORTED_MANDATE_ID = "institutional-diversified-growth"
ELIGIBLE_STATES = {LifecycleState.CANDIDATE, LifecycleState.VALIDATED, LifecycleState.PUBLISHED}


class ApplicationModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)


class MandateApplicationRequest(ApplicationModel):
    mandate_id: str = Field(default=SUPPORTED_MANDATE_ID, min_length=3, max_length=160)
    scenario_id: Literal["reviewed_snapshot", "missing_price"] = "reviewed_snapshot"


def _registry_projection(kind: str, asset_id: str) -> Any:
    return next(
        item
        for item in discover_registry_projections()
        if item.identity.kind.value == kind and item.identity.asset_id == asset_id
    )


def _registry_binding(registry: Any, mandate_id: str) -> dict[str, Any]:
    _, mandate, policy = mandate_bundle(mandate_id)
    bindings: dict[str, Any] = {}
    for label, kind, asset_id in (
        ("mandate", "mandate", mandate.object_id),
        ("risk_policy", "risk_policy", policy.object_id),
    ):
        projection = _registry_projection(kind, asset_id)
        try:
            document = registry.get(projection.identity)
        except RegistryNotFound:
            bindings[label] = {
                "reference": projection.identity.reference,
                "state": "not_registered",
                "eligible": False,
            }
            continue
        bindings[label] = {
            "reference": projection.identity.reference,
            "state": document.state.value,
            "eligible": document.state in ELIGIBLE_STATES,
            "revision": document.receipts[-1].receipt_digest,
        }
    bindings["ready"] = all(item["eligible"] for item in bindings.values())
    return bindings


def catalogue(registry: Any) -> dict[str, Any]:
    _, mandate, policy = mandate_bundle(SUPPORTED_MANDATE_ID)
    portfolio = build_calibration_pilot().portfolio_governance.portfolio
    return {
        "schema_version": "portfolio-risk.mandate-application-catalogue/v1",
        "title": "Institutional mandate application",
        "premise": "Apply one exact registered mandate and policy to the accepted reviewed-synthetic diversified portfolio at its point-in-time boundary.",
        "mandate": {
            "object_id": mandate.object_id,
            "name": mandate.name,
            "reference": mandate.reference,
            "policy_name": policy.name,
            "policy_reference": policy.reference,
        },
        "portfolio": {
            "name": portfolio.name,
            "reference": portfolio.reference,
            "snapshot_reference": portfolio.snapshot_reference,
            "as_of": portfolio.as_of.isoformat(),
            "data_truth": portfolio.data_truth,
        },
        "registry": _registry_binding(registry, mandate.object_id),
        "scenarios": [
            {
                "scenario_id": "reviewed_snapshot",
                "label": "Reviewed portfolio snapshot",
                "description": "All eligible synthetic marks are present. Cash and issuer concentration are evaluated; the unsupported real-return semantic remains unavailable.",
            },
            {
                "scenario_id": "missing_price",
                "label": "Missing eligible price",
                "description": "One price is withheld to verify that missing data stops valuation and never becomes zero or false compliance.",
            },
        ],
        "effects": [],
        "llm_called": False,
    }


def _portfolio_source() -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    portfolio = yaml.safe_load(PORTFOLIO_PATH.read_text(encoding="utf-8"))
    mapping = yaml.safe_load(INSTRUMENT_MAP_PATH.read_text(encoding="utf-8"))
    instruments = {item["instrument_id"]: item for item in mapping["instruments"]}
    return portfolio, instruments


def _eligible_market_records(as_of: datetime) -> dict[str, dict[str, Any]]:
    rows = parquet.read_table(MARKET_PATH).to_pylist()
    eligible: dict[str, dict[str, Any]] = {}
    for row in rows:
        if row["timestamp"] > as_of or row["available_at"] > as_of:
            continue
        current = eligible.get(row["instrument_id"])
        if current is None or row["timestamp"] > current["timestamp"]:
            eligible[row["instrument_id"]] = row
    return eligible


def _capability_receipt(capability: str, request: Any, result: Any) -> dict[str, Any]:
    return {
        "receipt_id": f"receipt-{capability.replace('.', '-')}",
        "capability_id": capability,
        "execution_mode": "canonical_registry",
        "input_contract": request.__class__.__name__,
        "output_contract": result.data.__class__.__name__ if result.data is not None else None,
        "status": result.status,
        "input_digest": canonical_digest(request.model_dump(mode="json")),
        "output_digest": result.output_digest or canonical_digest(result.model_dump(mode="json")),
        "warnings": list(result.warnings),
        "effects": list(result.effects),
    }


def _criterion(rule: Any) -> str:
    if rule.operator in {"in", "not_in"}:
        return f"{rule.operator} {', '.join(rule.allowed_values)}"
    return f"{rule.operator} {rule.threshold}"


def _passes(operator: str, value: Decimal, threshold: Decimal) -> bool:
    return {
        "gt": value > threshold,
        "gte": value >= threshold,
        "lt": value < threshold,
        "lte": value <= threshold,
        "eq": value == threshold,
    }[operator]


def _finding(
    *, rule: Any, status: str, summary: str, portfolio: Any, receipt: dict[str, Any]
) -> RiskFinding:
    severity = "high" if status == "breach" else "medium"
    snapshot = ArtifactReference(
        artifact_id="portfolio-version-diversified-synthetic",
        digest=portfolio.object_digest,
        media_type="application/yaml",
        reference=portfolio.snapshot_reference,
    )
    evidence = ArtifactReference(
        artifact_id=receipt["receipt_id"],
        digest=receipt["output_digest"],
        media_type="application/json",
        reference=f"capability://{receipt['capability_id']}",
    )
    return RiskFinding(
        finding_type=f"mandate_{status}",
        severity=severity,
        title=f"{rule.mandate_constraint_id.replace('-', ' ').title()}: {status.replace('_', ' ')}",
        summary=summary,
        snapshot_references=(snapshot,),
        evidence_references=(evidence,),
        assumptions=("This application uses a reviewed-synthetic portfolio and fictional issuers.",),
        warnings=("This is an effect-free research finding, not investment advice.",),
    )


def _decision_proposal(
    *, rule: Any, finding: RiskFinding, assessment: dict[str, Any], receipts: list[dict[str, Any]], mandate: Any, policy: Any, portfolio: Any
) -> DecisionProposal:
    as_of = portfolio.as_of
    finding_key = f"mandate-{mandate.object_id}-{rule.rule_id}-{as_of.date().isoformat()}"
    receipt_ids = tuple(sorted(item["receipt_id"] for item in receipts if item["status"] == "succeeded"))
    return DecisionProposal(
        proposal_id=f"proposal-{finding_key}",
        finding_id=finding_key,
        finding_digest=finding.finding_id,
        question=f"How should the human reviewer respond to the {rule.mandate_constraint_id.replace('-', ' ')} breach?",
        why_now=assessment["explanation"],
        proposing_agent_id="risk.agent.deterministic-mandate-reviewer",
        proposing_workflow_id="risk.workflow.mandate-application-fixture",
        recommendation=DecisionOutcome.INVESTIGATE,
        mandate_relevance=f"Rule {rule.rule_id} is the reviewed machine-evaluable interpretation of mandate clause {rule.mandate_constraint_id}.",
        portfolio_relevance=f"The result was calculated from {portfolio.name} at {as_of.isoformat()}.",
        risk_environment_relevance="No macro, meso, event or issuer narrative was supplied in this first controlled slice.",
        evidence_ids=(finding_key,),
        capability_receipt_ids=receipt_ids,
        policy_ids=(policy.object_id,),
        uncertainties=("The portfolio, prices and issuers are reviewed synthetic research inputs.",),
        missing_information=("A specialist interpretation agent has not been invoked in this deterministic first slice.",),
        as_of=as_of,
        available_at=as_of,
        created_at=as_of,
        expires_at=as_of + timedelta(hours=4),
        downstream_workflow_preview="Investigate may run effect-free evidence review. Any portfolio action remains unavailable.",
    )


def run(request: MandateApplicationRequest, registry: Any) -> dict[str, Any]:
    if request.mandate_id != SUPPORTED_MANDATE_ID:
        raise ValueError("the first vertical slice supports only the institutional diversified growth mandate")
    bindings = _registry_binding(registry, request.mandate_id)
    if not bindings["ready"]:
        raise PermissionError("register the exact MandateVersion and RiskPolicySet in Mandate Studio before application")

    _, mandate, policy = mandate_bundle(request.mandate_id)
    portfolio = build_calibration_pilot().portfolio_governance.portfolio
    portfolio_input, instrument_map = _portfolio_source()
    eligible = _eligible_market_records(portfolio.as_of)
    held_ids = [item["instrument_id"] for item in portfolio_input["positions"]]
    if request.scenario_id == "missing_price":
        eligible.pop(held_ids[0], None)

    evidence = (
        EvidenceReference(
            evidence_id="evidence-reviewed-synthetic-diversified-portfolio",
            reference=portfolio.snapshot_reference,
            source_type="reviewed_synthetic_fixture",
            digest=portfolio.snapshot_digest,
            description="Immutable quantities, cash and point-in-time eligible fictional market marks.",
        ),
    )
    observations = tuple(
        NormalizedMarketRecord(
            instrument_id=instrument_id,
            identifier=InstrumentIdentifier(identifier_type="ticker", value=instrument_map[instrument_id]["label"]),
            observed_at=eligible[instrument_id]["timestamp"],
            price=eligible[instrument_id]["adjusted_close"] or eligible[instrument_id]["close"],
            currency=eligible[instrument_id]["currency"],
            source_id=eligible[instrument_id]["source_id"],
        )
        for instrument_id in held_ids
        if instrument_id in eligible
    )
    registry_runtime = CapabilityRegistry()
    snapshot_request = PortfolioSnapshotRequest(
        snapshot_id="mandate-application-diversified-20240614",
        as_of=portfolio.as_of,
        positions=tuple(
            PositionSpecification(instrument_id=item["instrument_id"], quantity=Decimal(item["quantity"]))
            for item in portfolio_input["positions"]
        ),
        cash_balances=tuple(
            CashBalance(currency=item["currency"], amount=Decimal(item["amount"]))
            for item in portfolio_input["cash"]
        ),
        normalized_observations=observations,
        evidence_references=evidence,
    )
    snapshot_result = registry_runtime.invoke("portfolio.snapshot.create", snapshot_request)
    receipts = [_capability_receipt("portfolio.snapshot.create", snapshot_request, snapshot_result)]
    exposure = None
    if snapshot_result.status == "succeeded" and snapshot_result.data is not None:
        exposure_request = ExposureSummaryRequest(
            snapshot_id="mandate-application-exposure-20240614",
            portfolio_snapshot=snapshot_result.data,
            evidence_references=evidence,
        )
        exposure_result = registry_runtime.invoke("portfolio.exposure.summarize", exposure_request)
        receipts.append(_capability_receipt("portfolio.exposure.summarize", exposure_request, exposure_result))
        if exposure_result.status == "succeeded":
            exposure = exposure_result.data

    assessments: list[dict[str, Any]] = []
    findings: list[RiskFinding] = []
    proposals: list[DecisionProposal] = []
    receipt_by_capability = {item["capability_id"]: item for item in receipts}
    entities = [instrument_map[item]["entity_id"] for item in held_ids]
    one_instrument_per_issuer = len(entities) == len(set(entities))

    for rule in policy.rules:
        native_capability = capability_id(rule.capability_reference)
        value: Decimal | None = None
        semantic_state = "resolved"
        reason = ""
        if rule.metric_reference.endswith("cash-weight@1.0.0") and exposure is not None:
            value = exposure.cash_weight
            reason = "Cash weight comes directly from the canonical exposure result."
        elif rule.metric_reference.endswith("consolidated-issuer-weight@1.0.0") and exposure is not None and one_instrument_per_issuer:
            value = exposure.largest_position_weight
            reason = "The reviewed fixture maps each held instrument to one distinct consolidated issuer, so largest position weight is semantically equivalent here."
        elif rule.metric_reference.endswith("annualized-real-return-five-year@1.0.0"):
            semantic_state = "unavailable"
            reason = "risk.returns.simple does not supply an inflation-adjusted five-year portfolio return; the capability was not invoked with an invalid substitute."
        else:
            semantic_state = "unavailable"
            reason = "The required semantic metric could not be resolved from a successful capability result."

        if value is None:
            status = "unable_to_assess"
            explanation = f"Unable to assess {rule.mandate_constraint_id.replace('-', ' ')}. {reason}"
        else:
            passed = _passes(rule.operator, value, rule.threshold)
            status = "compliant" if passed else "breach" if rule.system_treatment == "compliance_test" else "attention"
            formatted_value = f"{value:.2%}" if rule.unit in {"portfolio_weight", "annualized_return"} else str(value)
            formatted_threshold = f"{rule.threshold:.2%}" if rule.unit in {"portfolio_weight", "annualized_return"} else str(rule.threshold)
            explanation = f"Observed {formatted_value} against {_criterion(rule).split(' ', 1)[0]} {formatted_threshold}. {reason}"

        assessment = {
            "rule_id": rule.rule_id,
            "constraint_id": rule.mandate_constraint_id,
            "statement": next(item.statement for item in mandate.constraints if item.constraint_id == rule.mandate_constraint_id),
            "status": status,
            "observed_value": str(value) if value is not None else None,
            "criterion": _criterion(rule),
            "unit": rule.unit,
            "semantic_state": semantic_state,
            "capability_id": native_capability,
            "capability_status": receipt_by_capability.get(native_capability, {}).get("status", "not_invoked"),
            "evaluation_basis": rule.evaluation_basis,
            "explanation": explanation,
            "governance": rule.governance_route.model_dump(mode="json"),
            "effects": [],
        }
        assessments.append(assessment)
        if status in {"breach", "unable_to_assess", "attention"}:
            supporting_receipt = receipt_by_capability.get(native_capability) or receipts[0]
            finding = _finding(rule=rule, status=status, summary=explanation, portfolio=portfolio, receipt=supporting_receipt)
            findings.append(finding)
            if status == "breach" and rule.governance_route.outcome == "require_decision":
                proposals.append(
                    _decision_proposal(
                        rule=rule,
                        finding=finding,
                        assessment=assessment,
                        receipts=receipts,
                        mandate=mandate,
                        policy=policy,
                        portfolio=portfolio,
                    )
                )

    counts = {key: sum(item["status"] == key for item in assessments) for key in ("compliant", "attention", "breach", "unable_to_assess")}
    return {
        "schema_version": "portfolio-risk.mandate-application-run/v1",
        "run_id": f"mandate-application-{request.mandate_id}-{request.scenario_id}-20240614",
        "status": "review_required" if proposals or counts["unable_to_assess"] else "complete",
        "premise": "Determine what the registered mandate says about the exact portfolio state, distinguish calculation from interpretation, and route only material results to human review.",
        "input": {
            "scenario_id": request.scenario_id,
            "data_truth": "reviewed_synthetic",
            "portfolio": {**portfolio.model_dump(mode="json"), "reference": portfolio.reference},
            "mandate": {**mandate.model_dump(mode="json"), "reference": mandate.reference},
            "risk_policy": {**policy.model_dump(mode="json"), "reference": policy.reference},
            "registry": bindings,
            "eligible_market_observations": len(observations),
            "required_positions": len(held_ids),
            "point_in_time_rule": "timestamp_lte_as_of_and_available_at_lte_as_of",
        },
        "capability_receipts": receipts,
        "assessments": assessments,
        "summary": counts,
        "findings": [item.model_dump(mode="json") for item in findings],
        "decision_proposals": [item.model_dump(mode="json") for item in proposals],
        "interpretation": {
            "mode": "deterministic_plain_language",
            "llm_called": False,
            "message": f"{counts['breach']} breach, {counts['compliant']} compliant rule and {counts['unable_to_assess']} rule unable to assess. The system calculated only metrics supported by valid semantic bindings.",
        },
        "persistence": "temporary_application_work_product",
        "effects": [],
    }
