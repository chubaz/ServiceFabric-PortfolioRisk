"""Execute one reviewed Risk Analysis Package inside an isolated fixture boundary."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import time
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from agent_studio import COST_OPTIMIZED_LLM_MODEL, RUN_ROOT, _keychain_key
from risk_analytics import (
    AnalysisEvidence,
    AnalysisHorizon,
    DAILY_PORTFOLIO_DOWNSIDE_RISK_PACKAGE,
    SamplePeriod,
    ScenarioShock,
)
from risk_capabilities import (
    ContributionSummaryRequest,
    ContributionValue,
    DEFAULT_CAPABILITY_REGISTRY,
    DerivedReturnsRequest,
    EvidenceReference,
    ExposureSummaryRequest,
    HistoricalTailRiskRequest,
    ReturnsRequest,
    ScenarioRequest,
    VolatilityRequest,
)
from risk_domain import CashBalance, MarketObservation, PortfolioSnapshot, Position
from risk_domain.digests import sha256_digest


DEFAULT_RUN_ROOT = (RUN_ROOT.parent / "risk-analysis-package-runs").resolve()
RISK_PACKAGE_RUN_ROOT = Path(
    os.environ.get("PORTFOLIO_RISK_RISK_PACKAGE_RUN_ROOT", DEFAULT_RUN_ROOT)
).expanduser().resolve()
RUN_ID_PATTERN = r"^rap-run-[0-9]{8}T[0-9]{6}Z-[a-f0-9]{8}$"


class FrozenModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class PackageRunRequest(FrozenModel):
    package_id: Literal["risk.analysis.daily_portfolio_downside"] = (
        "risk.analysis.daily_portfolio_downside"
    )
    fixture_id: Literal["reviewed_synthetic"] = "reviewed_synthetic"
    narrative_mode: Literal["deterministic_preview", "live_llm"] = (
        "deterministic_preview"
    )
    model: Literal["gpt-5.6-luna"] = COST_OPTIMIZED_LLM_MODEL


class CapabilityReceipt(FrozenModel):
    sequence: int = Field(ge=1)
    role_id: str
    requested_implementation: str
    resolved_implementation: str
    resolution: Literal["default", "compatible_substitution"] = "default"
    status: Literal["succeeded", "failed", "stopped"]
    input_digest: str = Field(pattern=r"^sha256:[a-f0-9]{64}$")
    output_digest: str | None = Field(default=None, pattern=r"^sha256:[a-f0-9]{64}$")
    elapsed_ms: float = Field(ge=0)
    warnings: tuple[str, ...] = ()
    effects: tuple[()] = ()


class ValueAssessment(FrozenModel):
    portfolio_materiality: int = Field(ge=0, le=4)
    mandate_relevance: int = Field(ge=0, le=4)
    decision_relevance: int = Field(ge=0, le=4)
    novelty: int = Field(ge=0, le=4)
    evidence_strength: int = Field(ge=0, le=4)
    time_sensitivity: int = Field(ge=0, le=4)
    uncertainty_reduction: int = Field(ge=0, le=4)


class CandidateFinding(FrozenModel):
    section_id: str
    title: str
    admission_path: Literal["decision_value", "research_value"]
    claim: str
    evidence_ids: tuple[str, ...]
    value: ValueAssessment
    inclusion_reason: str

    @field_validator("evidence_ids")
    @classmethod
    def evidence_is_sorted_and_unique(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if value != tuple(sorted(set(value))):
            raise ValueError("finding evidence must be sorted and unique")
        return value


class NarrativeSection(FrozenModel):
    section_id: str
    title: str
    markdown: str = Field(min_length=1, max_length=5000)
    evidence_ids: tuple[str, ...]
    admission_path: Literal["decision_value", "research_value"]
    inclusion_reason: str = Field(min_length=3, max_length=600)
    value: ValueAssessment

    @field_validator("evidence_ids")
    @classmethod
    def evidence_is_sorted_and_unique(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if value != tuple(sorted(set(value))):
            raise ValueError("section evidence must be sorted and unique")
        return value


class NarrativeAgentOutput(FrozenModel):
    sections: tuple[NarrativeSection, ...] = Field(max_length=5)
    omitted_section_ids: tuple[str, ...]
    no_material_finding: bool

    @model_validator(mode="after")
    def silence_and_sections_are_consistent(self) -> "NarrativeAgentOutput":
        if self.no_material_finding == bool(self.sections):
            raise ValueError("no_material_finding must be true exactly when sections are empty")
        section_ids = [item.section_id for item in self.sections]
        if len(section_ids) != len(set(section_ids)):
            raise ValueError("narrative section IDs must be unique")
        if set(section_ids) & set(self.omitted_section_ids):
            raise ValueError("included sections cannot also be omitted")
        return self


def _json_text(value: Any) -> str:
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="json")
    return json.dumps(value, indent=2, sort_keys=True, default=str) + "\n"


def _percent(value: Decimal, places: int = 2) -> str:
    return f"{value * Decimal('100'):.{places}f}%"


def _money(value: Decimal) -> str:
    return f"${value:,.2f}"


def _synthetic_fixture() -> tuple[PortfolioSnapshot, tuple[MarketObservation, ...], AnalysisEvidence]:
    as_of = datetime(2024, 3, 29, 16, tzinfo=UTC)
    positions = (
        Position(instrument_id="Northstar Industries", quantity=Decimal("400"), price=Decimal("100"), market_value=Decimal("40000"), currency="USD"),
        Position(instrument_id="Harbor Utilities", quantity=Decimal("300"), price=Decimal("100"), market_value=Decimal("30000"), currency="USD"),
        Position(instrument_id="Meridian Health", quantity=Decimal("200"), price=Decimal("100"), market_value=Decimal("20000"), currency="USD"),
    )
    snapshot = PortfolioSnapshot(
        snapshot_id="fixture:daily-downside:reviewed-synthetic:v1",
        as_of=as_of,
        base_currency="USD",
        positions=positions,
        cash_balances=(CashBalance(currency="USD", amount=Decimal("10000")),),
    )
    base_pattern = (
        Decimal("0.004"), Decimal("-0.003"), Decimal("0.002"), Decimal("0.001"),
        Decimal("-0.005"), Decimal("0.003"), Decimal("0.002"), Decimal("-0.004"),
        Decimal("0.005"), Decimal("-0.002"), Decimal("0.001"), Decimal("0.003"),
    )
    price = Decimal("100")
    observations: list[MarketObservation] = []
    start = as_of - timedelta(days=240)
    for index in range(241):
        if index:
            daily_return = base_pattern[(index - 1) % len(base_pattern)]
            daily_return = {
                58: Decimal("-0.034"),
                117: Decimal("-0.046"),
                176: Decimal("-0.029"),
                177: Decimal("-0.018"),
                178: Decimal("0.021"),
            }.get(index, daily_return)
            price *= Decimal("1") + daily_return
        observations.append(
            MarketObservation(
                instrument_id="Reviewed synthetic portfolio index",
                observed_at=start + timedelta(days=index),
                price=price.quantize(Decimal("0.000001")),
                currency="USD",
                synthetic=True,
            )
        )
    evidence = AnalysisEvidence(
        evidence_id="fixture.daily-downside.market-series",
        reference="fixture://risk-analysis/daily-downside/reviewed-synthetic/v1",
        digest=sha256_digest(tuple(observations)),
        description="Reviewed deterministic portfolio-index fixture with 240 daily returns and explicit downside episodes.",
    )
    return snapshot, tuple(observations), evidence


def _invoke(
    receipts: list[CapabilityReceipt], role_id: str, capability_id: str, request: Any
) -> Any:
    started = time.perf_counter()
    result = DEFAULT_CAPABILITY_REGISTRY.invoke(capability_id, request)
    elapsed_ms = round((time.perf_counter() - started) * 1000, 3)
    receipts.append(
        CapabilityReceipt(
            sequence=len(receipts) + 1,
            role_id=role_id,
            requested_implementation=capability_id,
            resolved_implementation=capability_id,
            status=result.status,
            input_digest=sha256_digest(request),
            output_digest=result.output_digest,
            elapsed_ms=elapsed_ms,
            warnings=result.warnings,
        )
    )
    if result.status != "succeeded" or result.data is None:
        raise ValueError(f"capability {capability_id} did not produce a result")
    return result.data


def _deterministic_findings(results: dict[str, Any]) -> tuple[CandidateFinding, ...]:
    tail = results["tail_risk"]
    drawdown = results["drawdown"]
    exposure = results["exposure"]
    scenario = results["scenario"]
    nav = sum((item.market_value for item in results["snapshot"].positions), Decimal("0")) + sum(
        (item.amount for item in results["snapshot"].cash_balances), Decimal("0")
    )
    top = max(exposure.position_exposures, key=lambda item: item.weight)
    findings: list[CandidateFinding] = []
    if drawdown.maximum_drawdown >= Decimal("0.03") or tail.value_at_risk >= Decimal("0.015"):
        findings.append(
            CandidateFinding(
                section_id="material_signal",
                title="Material downside signal",
                admission_path="decision_value",
                claim=(
                    f"Maximum drawdown reached {_percent(drawdown.maximum_drawdown)}; "
                    f"95% historical VaR is {_percent(tail.value_at_risk)} and Expected Shortfall is {_percent(tail.expected_shortfall)}."
                ),
                evidence_ids=("fixture.daily-downside.market-series",),
                value=ValueAssessment(portfolio_materiality=4, mandate_relevance=2, decision_relevance=4, novelty=3, evidence_strength=4, time_sensitivity=3, uncertainty_reduction=3),
                inclusion_reason="The observed loss path and tail severity can change the required depth of portfolio review.",
            )
        )
    if top.weight >= Decimal("0.35"):
        findings.append(
            CandidateFinding(
                section_id="drivers_and_exposure",
                title="Concentration amplifies the downside",
                admission_path="decision_value",
                claim=f"{top.instrument_id} represents {_percent(top.weight, 1)} of portfolio NAV, making the downside profile sensitive to one holding.",
                evidence_ids=("fixture.daily-downside.market-series",),
                value=ValueAssessment(portfolio_materiality=4, mandate_relevance=4, decision_relevance=4, novelty=3, evidence_strength=4, time_sensitivity=2, uncertainty_reduction=3),
                inclusion_reason="The concentration is large enough to affect scenario severity and mandate review.",
            )
        )
    scenario_ratio = abs(scenario.portfolio_profit_and_loss) / nav
    if scenario_ratio >= Decimal("0.05"):
        findings.append(
            CandidateFinding(
                section_id="scenario_sensitivity",
                title="Reviewed downside scenario",
                admission_path="research_value",
                claim=f"The reviewed 10% position shock produces {_money(scenario.portfolio_profit_and_loss)} of portfolio P&L, equal to {_percent(scenario_ratio)} of NAV.",
                evidence_ids=("fixture.daily-downside.market-series",),
                value=ValueAssessment(portfolio_materiality=4, mandate_relevance=3, decision_relevance=3, novelty=3, evidence_strength=4, time_sensitivity=2, uncertainty_reduction=4),
                inclusion_reason="The scenario connects the observed risk profile to a transparent portfolio-level loss mechanism.",
            )
        )
    return tuple(findings)


def _deterministic_narrative(
    candidates: tuple[CandidateFinding, ...], all_section_ids: tuple[str, ...]
) -> NarrativeAgentOutput:
    sections = tuple(
        NarrativeSection(
            section_id=item.section_id,
            title=item.title,
            markdown=f"**Finding.** {item.claim}\n\n**Why it is included.** {item.inclusion_reason} [evidence:{item.evidence_ids[0]}]",
            evidence_ids=item.evidence_ids,
            admission_path=item.admission_path,
            inclusion_reason=item.inclusion_reason,
            value=item.value,
        )
        for item in candidates
    )
    included = {item.section_id for item in sections}
    return NarrativeAgentOutput(
        sections=sections,
        omitted_section_ids=tuple(item for item in all_section_ids if item not in included),
        no_material_finding=not sections,
    )


def _strict_schema(model: type[BaseModel]) -> dict[str, Any]:
    schema = model.model_json_schema()

    def normalize(value: Any) -> None:
        if isinstance(value, dict):
            if value.get("type") == "object" or "properties" in value:
                value["additionalProperties"] = False
            for child in value.values():
                normalize(child)
        elif isinstance(value, list):
            for child in value:
                normalize(child)

    normalize(schema)
    return schema


def _live_narrative(
    *, candidates: tuple[CandidateFinding, ...], packet: dict[str, Any], model: str
) -> tuple[NarrativeAgentOutput, dict[str, Any]]:
    api_key = _keychain_key(include_value=True)
    if not api_key:
        raise RuntimeError("OpenAI credential is unavailable")
    from openai import OpenAI

    started = time.perf_counter()
    client = OpenAI(api_key=str(api_key))
    response = client.responses.create(
        model=COST_OPTIMIZED_LLM_MODEL,
        store=False,
        tools=[],
        input=[
            {
                "role": "system",
                "content": [{
                    "type": "input_text",
                    "text": (
                        "You are a bounded portfolio-risk narrative specialist. Write only "
                        "sections supported by the admitted candidate findings. Omit trivial, "
                        "repetitive, procedural or weakly evidenced commentary. Preserve every "
                        "number exactly, cite only supplied evidence IDs using [evidence:ID], and "
                        "state why each included section has decision or research value. Empty "
                        "output is correct when nothing is valuable. Do not propose or imply a "
                        "portfolio effect. Return only the strict schema."
                    ),
                }],
            },
            {
                "role": "user",
                "content": [{
                    "type": "input_text",
                    "text": json.dumps(
                        {
                            "risk_question": DAILY_PORTFOLIO_DOWNSIDE_RISK_PACKAGE.risk_question,
                            "compact_evidence_packet": packet,
                            "admitted_candidates": [item.model_dump(mode="json") for item in candidates],
                        },
                        sort_keys=True,
                    ),
                }],
            },
        ],
        text={"format": {"type": "json_schema", "name": "risk_analysis_architecture_output", "strict": True, "schema": _strict_schema(NarrativeAgentOutput)}},
        max_output_tokens=1800,
    )
    output = NarrativeAgentOutput.model_validate(json.loads(response.output_text))
    candidates_by_id = {item.section_id: item for item in candidates}
    available_evidence = {evidence for item in candidates for evidence in item.evidence_ids}
    for section in output.sections:
        candidate = candidates_by_id.get(section.section_id)
        if candidate is None:
            raise ValueError("narrative agent introduced a section outside the admitted candidates")
        if not set(section.evidence_ids).issubset(available_evidence):
            raise ValueError("narrative agent referenced evidence outside the compact packet")
    usage = getattr(response, "usage", None)
    receipt = {
        "provider": "openai_responses",
        "model": getattr(response, "model", model),
        "response_id": getattr(response, "id", None),
        "input_tokens": int(getattr(usage, "input_tokens", 0) or 0),
        "output_tokens": int(getattr(usage, "output_tokens", 0) or 0),
        "elapsed_ms": round((time.perf_counter() - started) * 1000, 2),
        "store": False,
        "tools": [],
    }
    return output, receipt


def _safe_run_directory(run_id: str) -> Path:
    if not re.fullmatch(RUN_ID_PATTERN, run_id):
        raise ValueError("invalid package run identifier")
    directory = (RISK_PACKAGE_RUN_ROOT / run_id).resolve()
    if directory.parent != RISK_PACKAGE_RUN_ROOT.resolve():
        raise ValueError("package run is outside the run repository")
    return directory


def execute_package(request: PackageRunRequest) -> dict[str, Any]:
    package = DAILY_PORTFOLIO_DOWNSIDE_RISK_PACKAGE
    snapshot, prices, evidence = _synthetic_fixture()
    horizon = AnalysisHorizon(label="daily", periods=1, expected_interval_seconds=86_400)
    evidence_tuple = (evidence,)
    receipts: list[CapabilityReceipt] = []
    common_limitations = ("Reviewed synthetic fixture results are descriptive and are not investment advice.",)
    returns = _invoke(
        receipts,
        "calculate_returns",
        "risk.returns.simple",
        ReturnsRequest(analysis_id="daily-downside:returns", snapshot_id=snapshot.snapshot_id, prices=prices, horizon=horizon, evidence=evidence_tuple, limitations=common_limitations),
    )
    common = {"returns": returns, "evidence": evidence_tuple, "limitations": common_limitations}
    volatility = _invoke(receipts, "estimate_volatility", "risk.volatility.annualized", VolatilityRequest(analysis_id="daily-downside:volatility", periods_per_year=252, **common))
    drawdown = _invoke(receipts, "measure_drawdown", "risk.drawdown.maximum", DerivedReturnsRequest(analysis_id="daily-downside:drawdown", **common))
    tail_request = HistoricalTailRiskRequest(analysis_id="daily-downside:tail", confidence_level=Decimal("0.95"), **common)
    tail_var = _invoke(receipts, "estimate_var", "risk.var.historical", tail_request)
    tail_es = _invoke(receipts, "estimate_expected_shortfall", "risk.expected_shortfall.historical", tail_request)
    evidence_reference = EvidenceReference(evidence_id=evidence.evidence_id, reference=evidence.reference, source_type="reviewed_synthetic_fixture", digest=evidence.digest, description=evidence.description)
    exposure = _invoke(receipts, "summarize_exposure", "portfolio.exposure.summarize", ExposureSummaryRequest(snapshot_id="daily-downside:exposure", portfolio_snapshot=snapshot, evidence_references=(evidence_reference,)))
    sample_period = SamplePeriod(start=returns.sample_period.start, end=returns.sample_period.end)
    contribution_values = (
        ContributionValue(instrument_id="Harbor Utilities", weight=Decimal("0.30"), instrument_return=Decimal("-0.001")),
        ContributionValue(instrument_id="Meridian Health", weight=Decimal("0.20"), instrument_return=Decimal("0.002")),
        ContributionValue(instrument_id="Northstar Industries", weight=Decimal("0.40"), instrument_return=Decimal("-0.006")),
    )
    contribution = _invoke(receipts, "attribute_return", "risk.contribution.summarize", ContributionSummaryRequest(analysis_id="daily-downside:contribution", snapshot_id=snapshot.snapshot_id, values=contribution_values, portfolio_return=Decimal("-0.0023"), horizon=horizon, sample_period=sample_period, evidence=evidence_tuple, limitations=common_limitations))
    shocks = tuple(ScenarioShock(instrument_id=item.instrument_id, percentage_shock=Decimal("-0.10")) for item in snapshot.positions)
    scenario = _invoke(receipts, "evaluate_scenario", "risk.scenario.evaluate", ScenarioRequest(analysis_id="daily-downside:scenario", portfolio=snapshot, shocks=shocks, horizon=AnalysisHorizon(label="instantaneous", periods=1), evidence=evidence_tuple, limitations=("The reviewed scenario is linear, descriptive and effect-free.",)))
    results = {"snapshot": snapshot, "returns": returns, "volatility": volatility, "drawdown": drawdown, "tail_risk": tail_es, "tail_var_receipt_result": tail_var, "exposure": exposure, "contribution": contribution, "scenario": scenario}
    candidates = _deterministic_findings(results)
    packet = {
        "data_truth": "reviewed_synthetic",
        "as_of": snapshot.as_of.isoformat(),
        "snapshot_id": snapshot.snapshot_id,
        "observation_count": returns.observation_count,
        "metrics": {"annualized_volatility": str(volatility.annualized_volatility), "maximum_drawdown": str(drawdown.maximum_drawdown), "historical_var_95": str(tail_es.value_at_risk), "historical_expected_shortfall_95": str(tail_es.expected_shortfall)},
        "top_exposure": {"instrument_id": max(exposure.position_exposures, key=lambda item: item.weight).instrument_id, "weight": str(max(item.weight for item in exposure.position_exposures))},
        "scenario": {"portfolio_profit_and_loss": str(scenario.portfolio_profit_and_loss), "currency": scenario.currency},
        "warnings": [item.message for item in tail_es.warnings],
        "evidence_ids": [evidence.evidence_id],
    }
    model_receipt = None
    if request.narrative_mode == "live_llm":
        narrative, model_receipt = _live_narrative(candidates=candidates, packet=packet, model=request.model)
    else:
        narrative = _deterministic_narrative(candidates, tuple(item.section_id for item in package.output_fields))
    created_at_dt = datetime.now(UTC).replace(microsecond=0)
    digest = hashlib.sha256(
        f"{snapshot.digest}:{created_at_dt.isoformat()}:{request.narrative_mode}:{time.time_ns()}".encode()
    ).hexdigest()[:8]
    run_id = f"rap-run-{created_at_dt.strftime('%Y%m%dT%H%M%SZ')}-{digest}"
    available_evidence_ids = {evidence.evidence_id}
    output_errors = [
        f"{item.section_id} references unavailable evidence"
        for item in narrative.sections
        if not set(item.evidence_ids).issubset(available_evidence_ids)
    ]
    architecture_output = {
        "schema_version": "portfolio-risk.architecture-output/v1",
        "output_id": f"architecture-output:{run_id}",
        "run_id": run_id,
        "package_id": package.package_id,
        "package_version": package.version,
        "as_of": snapshot.as_of.isoformat(),
        "data_truth": "reviewed_synthetic",
        "assessment": {
            "no_material_finding": narrative.no_material_finding,
            "finding_count": len(narrative.sections),
        },
        "findings": [item.model_dump(mode="json") for item in narrative.sections],
        "omitted_output_fields": list(narrative.omitted_section_ids),
        "metrics": packet["metrics"],
        "top_exposure": packet["top_exposure"],
        "scenario": packet["scenario"],
        "evidence_ids": packet["evidence_ids"],
        "warnings": packet["warnings"],
        "limitations": list(common_limitations),
        "effects": [],
    }
    validation = {
        "schema_version": "portfolio-risk.architecture-output-validation/v1",
        "valid": not output_errors,
        "errors": output_errors,
        "available_evidence_ids": sorted(available_evidence_ids),
        "checked_finding_count": len(narrative.sections),
    }
    directory = _safe_run_directory(run_id)
    directory.mkdir(parents=True, exist_ok=False)
    payloads: dict[str, Any] = {
        "input.json": {"package": package.model_dump(mode="json"), "request": request.model_dump(mode="json"), "fixture": {"data_truth": "reviewed_synthetic", "snapshot": snapshot.model_dump(mode="json"), "evidence_packet": packet}},
        "execution-plan.json": {"resolution_mode": package.resolution_mode, "stable_core": True, "capability_roles": [item.model_dump(mode="json") for item in package.capability_roles], "supplemental_roles": []},
        "capability-receipts.json": [item.model_dump(mode="json") for item in receipts],
        "analysis-results.json": {key: value.model_dump(mode="json") for key, value in results.items()},
        "candidate-findings.json": [item.model_dump(mode="json") for item in candidates],
        "architecture-output.json": architecture_output,
        "output-validation.json": validation,
        "model-receipt.json": model_receipt or {"provider": "none", "input_tokens": 0, "output_tokens": 0, "reason": "deterministic preview selected"},
    }
    for name, payload in payloads.items():
        (directory / name).write_text(_json_text(payload), encoding="utf-8")
    files = tuple(
        {"name": path.name, "bytes": path.stat().st_size, "kind": path.suffix.removeprefix(".")}
        for path in sorted(directory.iterdir())
    )
    manifest = {
        "schema_version": "portfolio-risk.risk-analysis-package-run/v1",
        "run_id": run_id,
        "package_id": package.package_id,
        "package_version": package.version,
        "created_at": created_at_dt.isoformat(),
        "status": "completed" if validation["valid"] else "completed_with_validation_warning",
        "data_truth": "reviewed_synthetic",
        "narrative_mode": request.narrative_mode,
        "model": model_receipt.get("model") if model_receipt else None,
        "capability_call_count": len(receipts),
        "finding_count": len(narrative.sections),
        "human_review_required": True,
        "effects": [],
        "folder": str(directory),
        "files": files,
    }
    (directory / "manifest.json").write_text(_json_text(manifest), encoding="utf-8")
    manifest["files"] = (
        {"name": "manifest.json", "bytes": (directory / "manifest.json").stat().st_size, "kind": "json"},
        *files,
    )
    (directory / "manifest.json").write_text(_json_text(manifest), encoding="utf-8")
    return load_package_run(run_id)


def list_package_runs() -> list[dict[str, Any]]:
    if not RISK_PACKAGE_RUN_ROOT.exists():
        return []
    records = []
    for directory in RISK_PACKAGE_RUN_ROOT.iterdir():
        if not directory.is_dir() or not re.fullmatch(RUN_ID_PATTERN, directory.name):
            continue
        try:
            records.append(json.loads((directory / "manifest.json").read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError):
            continue
    return sorted(records, key=lambda item: item.get("created_at", ""), reverse=True)


def load_package_run(run_id: str) -> dict[str, Any]:
    directory = _safe_run_directory(run_id)
    if not directory.is_dir():
        raise FileNotFoundError(run_id)
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    contents: dict[str, Any] = {}
    for item in manifest.get("files", []):
        name = item.get("name", "")
        path = (directory / name).resolve()
        if path.parent != directory or not path.is_file() or path.stat().st_size > 2_000_000:
            continue
        raw = path.read_text(encoding="utf-8")
        if name.endswith(".json"):
            try:
                contents[name] = json.loads(raw)
            except json.JSONDecodeError:
                contents[name] = raw
        else:
            contents[name] = raw
    # Historical pre-incubator runs remain readable without making their
    # presentation files part of new executions.
    if isinstance(contents.get("report.json"), dict):
        from risk_reports import MarkdownReport, with_rendered_html

        report = with_rendered_html(MarkdownReport.model_validate(contents["report.json"]))
        contents["report.json"] = report.model_dump(mode="json")
        contents["dossier.html"] = report.rendered_html
    return {"manifest": manifest, "contents": contents}


def delete_package_run(run_id: str) -> dict[str, Any]:
    directory = _safe_run_directory(run_id)
    if not directory.is_dir():
        raise FileNotFoundError(run_id)
    manifest_path = directory / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    shutil.rmtree(directory)
    return {
        "deleted": True,
        "run_id": run_id,
        "folder": manifest.get("folder", str(directory)),
        "recoverable": False,
    }
