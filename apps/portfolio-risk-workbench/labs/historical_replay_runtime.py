"""Licensed-data historical replay used by the simplified Experiment page.

B0, B1 and A1 consume the same deterministic point-in-time context. B0 applies
fixed rules, B1 makes one bounded synthesis call per cycle, and A1 executes the
frozen four-role graph. Licensed databases are always read-only.
"""

from __future__ import annotations

import json
import hashlib
import math
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from time import perf_counter
from typing import Any

import duckdb
import yaml
from risk_experiments import (
    ArchitectureConfig,
    ArchitectureDecision,
    ArchitectureFinding,
    ArchitectureOutput,
    CaseEvaluationState,
    DecisionBranch,
    EvaluationDimensionRecord,
    EvaluationRecord,
    ExperimentalCapabilityConfig,
    ExperimentalCase,
    ExperimentalRun,
    FindingEpisode,
    MandateVersion,
    MetricSpecification,
    ObservableCaseState,
    RegimeLabel,
    ResearchExperimentDefinition,
    ReplayProcessingReceipt,
    RiskPolicySet,
    RunInput,
    RunClassification,
    RunTraceRecord,
    RuntimeObservation,
    StudyDefinition,
    canonical_digest,
    validate_mandate_policy_binding,
)

from agent_treatment_runtime import (
    ARCHITECTURE_IDS as AGENT_ARCHITECTURE_IDS,
    MODEL_ID as AGENT_MODEL_ID,
    execute_agent_cycle,
)
from portfolio_risk_thesis.day3.prompts import prompt_manifest_digest


CATALOG_RELATIVE = Path("portfolio-risk/catalog/crsp-compustat.duckdb")
PORTFOLIO_RELATIVES = (
    Path("portfolio-definitions/portfolio-definitions/thesis-real-portfolios-day4-v1"),
    Path("portfolio-definitions/portfolio-definitions/thesis-real-portfolios-v2"),
)
CONFIG_RELATIVE = Path("config/thesis-experiment-day4.yaml")
PROFESSOR_DEMO_CONFIG = (
    Path(__file__).resolve().parents[3]
    / "config/agent/thesis-sprint/professor-demo-v0.1.yaml"
)
COMMON_START = date(2013, 1, 1)
COMMON_END = date(2017, 12, 31)
MAX_CALENDAR_DAYS = 62
RULES_WORKFLOW_ID = "B0"
AGENT_WORKFLOW_IDS = ("B1", "A1")
RUNNABLE_WORKFLOW_IDS = (RULES_WORKFLOW_ID, *AGENT_WORKFLOW_IDS)
MAX_AGENT_MODEL_CALLS = 20
EVALUATION_ID = "thesis_evaluation_v1"
STUDY_ID = "study-portfolio-risk-01"
EXPERIMENT_ID = "experiment-deterministic-reference-01"
ARCHITECTURE_ID = "b0-deterministic-reference"
RULE_RISK_TYPES = {
    "daily-loss": "loss",
    "drawdown": "loss",
    "volatility": "volatility",
    "cash-minimum": "liquidity",
    "issuer-concentration": "concentration",
    "sector-concentration": "concentration",
}


PRECONFIGURED_CAPABILITIES = (
    ExperimentalCapabilityConfig(
        capability_id="historical-replay-context",
        version="1.0.0",
        implementation_class="deterministic",
        parameterization="preconfigured",
        evaluation_roles=("architecture_input", "measurement"),
        parameter_digest="sha256:" + hashlib.sha256(b"historical-replay-context@1.0.0").hexdigest(),
    ),
    ExperimentalCapabilityConfig(
        capability_id="portfolio-risk-metric-pack",
        version="1.0.0",
        implementation_class="deterministic",
        parameterization="preconfigured",
        evaluation_roles=("architecture_input", "measurement"),
        parameter_digest="sha256:" + hashlib.sha256(b"portfolio-risk-metric-pack@1.0.0").hexdigest(),
    ),
    ExperimentalCapabilityConfig(
        capability_id="event-relevance-classifier",
        version="1.0.0",
        implementation_class="statistical",
        parameterization="preconfigured",
        evaluation_roles=("architecture_input",),
        parameter_digest="sha256:" + hashlib.sha256(b"provider-relevance-baseline@1.0.0").hexdigest(),
    ),
    ExperimentalCapabilityConfig(
        capability_id="fundamental-state-classifier",
        version="1.0.0",
        implementation_class="deterministic",
        parameterization="preconfigured",
        evaluation_roles=("architecture_input",),
        parameter_digest="sha256:" + hashlib.sha256(b"fundamental-state-baseline@1.0.0").hexdigest(),
    ),
    ExperimentalCapabilityConfig(
        capability_id="mandate-policy-evaluator",
        version="1.0.0",
        implementation_class="deterministic",
        parameterization="preconfigured",
        evaluation_roles=("architecture_input", "measurement"),
        parameter_digest="sha256:" + hashlib.sha256(b"mandate-policy-evaluator@1.0.0").hexdigest(),
    ),
    ExperimentalCapabilityConfig(
        capability_id="mandate-rule-reference-label",
        version="1.0.0",
        implementation_class="deterministic",
        parameterization="preconfigured",
        evaluation_roles=("reference_label",),
        parameter_digest="sha256:" + hashlib.sha256(b"mandate-rule-reference-label@1.0.0").hexdigest(),
    ),
    ExperimentalCapabilityConfig(
        capability_id="daily-session-timeliness",
        version="1.0.0",
        implementation_class="deterministic",
        parameterization="preconfigured",
        evaluation_roles=("measurement",),
        parameter_digest="sha256:" + hashlib.sha256(b"daily-session-timeliness@1.0.0").hexdigest(),
    ),
    ExperimentalCapabilityConfig(
        capability_id="evidence-structural-audit",
        version="1.0.0",
        implementation_class="deterministic",
        parameterization="preconfigured",
        evaluation_roles=("measurement",),
        parameter_digest="sha256:" + hashlib.sha256(b"evidence-structural-audit@1.0.0").hexdigest(),
    ),
    ExperimentalCapabilityConfig(
        capability_id="execution-telemetry-collector",
        version="1.0.0",
        implementation_class="deterministic",
        parameterization="preconfigured",
        evaluation_roles=("measurement",),
        parameter_digest="sha256:" + hashlib.sha256(b"execution-telemetry-collector@1.0.0").hexdigest(),
    ),
)


EVALUATION_CAPABILITY_REQUIREMENTS = (
    {"dimension": "detection_quality", "capability_id": "event-relevance-reference-label", "class": "statistical", "parameterization": "preconfigured", "status": "required", "separation": "held out from every architecture"},
    {"dimension": "severity_understanding", "capability_id": "severity-reference-label", "class": "statistical", "parameterization": "preconfigured", "status": "required", "separation": "held out from every architecture"},
    {"dimension": "timeliness", "capability_id": "daily-session-timeliness", "class": "deterministic", "parameterization": "preconfigured", "status": "ready", "separation": "measurement only"},
    {"dimension": "timeliness", "capability_id": "daily-close-alpha-persistence", "class": "statistical", "parameterization": "preconfigured", "status": "required", "separation": "post-run close-to-close outcomes; never represented as intraday alpha decay"},
    {"dimension": "evidence_quality", "capability_id": "evidence-structural-audit", "class": "deterministic", "parameterization": "preconfigured", "status": "ready", "separation": "measurement only"},
    {"dimension": "confidence_calibration", "capability_id": "confidence-outcome-calibration", "class": "statistical", "parameterization": "preconfigured", "status": "required", "separation": "post-run evaluation"},
    {"dimension": "decision_quality", "capability_id": "counterfactual-branch-outcome", "class": "statistical", "parameterization": "preconfigured", "status": "required", "separation": "post-horizon evaluation"},
    {"dimension": "robustness", "capability_id": "controlled-case-perturbation", "class": "deterministic", "parameterization": "preconfigured", "status": "required", "separation": "same perturbations for every architecture"},
    {"dimension": "stability", "capability_id": "repetition-digest-comparison", "class": "deterministic", "parameterization": "preconfigured", "status": "ready", "separation": "measurement only"},
    {"dimension": "efficiency", "capability_id": "execution-telemetry-collector", "class": "deterministic", "parameterization": "preconfigured", "status": "ready", "separation": "wrapper telemetry"},
)


METRIC_SPECIFICATIONS = (
    MetricSpecification(metric_id="daily-return", label="Daily total return", formula="Sum of prior-day portfolio weights multiplied by CRSP security total returns; cash return is zero. A missing curated total return uses the price return and carries a quality warning.", unit="return", history_policy="instrument_lifetime_to_as_of", adjustment_policy="CRSP total return is preferred because it includes distributions and corporate-action adjustments. Price-only fallback is explicit and never represented as equivalent quality.", missing_data_policy="partial_with_warning", required_observation_kinds=("crsp-total-return", "prior-day-position-value")),
    MetricSpecification(metric_id="annualised-volatility", label="Lifetime annualised volatility", formula="Sample standard deviation of every available portfolio total return from common instrument-history inception through the as-of date, multiplied by sqrt(252).", unit="annualised-volatility", history_policy="instrument_lifetime_to_as_of", adjustment_policy="Uses the total-return portfolio series and never resets at the experiment start date.", missing_data_policy="unavailable", required_observation_kinds=("daily-return",)),
    MetricSpecification(metric_id="drawdown", label="Lifetime drawdown", formula="One minus current total-return NAV index divided by its maximum since common instrument-history inception.", unit="drawdown", history_policy="instrument_lifetime_to_as_of", adjustment_policy="High-water mark is established before the experiment window and never reset by the selected start date.", missing_data_policy="unavailable", required_observation_kinds=("daily-return",)),
    MetricSpecification(metric_id="cash-weight", label="Cash weight", formula="Constant accepted USD cash divided by marked portfolio NAV including cash.", unit="portfolio-weight", history_policy="point_in_time", adjustment_policy="Cash is constant in this counterfactual and earns zero; this assumption is disclosed in every run.", missing_data_policy="partial_with_warning", required_observation_kinds=("cash-balance", "valuation-price")),
    MetricSpecification(metric_id="largest-issuer-weight", label="Largest issuer weight", formula="Maximum marked issuer position divided by portfolio NAV including cash.", unit="portfolio-weight", history_policy="point_in_time", adjustment_policy="Uses accepted fixed quantities and point-in-time valuation prices; therefore remains a disclosed portfolio counterfactual.", missing_data_policy="unavailable", required_observation_kinds=("position-quantity", "valuation-price")),
    MetricSpecification(metric_id="largest-sector-weight", label="Largest sector weight", formula="Maximum sum of marked positions sharing a current classified sector divided by portfolio NAV including cash.", unit="portfolio-weight", history_policy="point_in_time", adjustment_policy="Current sector labels are presentation metadata and not used as historical issuer facts outside this mandate calculation.", missing_data_policy="unavailable", required_observation_kinds=("position-quantity", "valuation-price", "sector-classification")),
)


ARCHITECTURE_EXECUTION_PROFILES = {
    "deterministic": {"interpretation_mode": "fixed_rules", "rules_are_fixed": True},
    "single_agent": {"interpretation_mode": "single_agent", "rules_are_fixed": False},
    "agent_graph": {"interpretation_mode": "agent_graph", "rules_are_fixed": False},
}


# These are research mandates created for the three current portfolio
# definitions. They are explicit pre-run rules, not inferred after seeing a
# replay result and not represented as legal or client documents.
PORTFOLIO_MANDATES: dict[str, dict[str, Any]] = {
    "defensive_multi_asset": {
        "mandate_id": "capital-preservation-liquidity",
        "version": "1.0.0",
        "name": "Capital Preservation and Liquidity Mandate",
        "objective": "Limit short-horizon losses and preserve a substantial cash reserve while monitoring issuer concentration.",
        "rules": (
            {"rule_id": "daily-loss", "label": "Daily loss", "metric": "daily_return", "operator": "gte", "threshold": -0.02, "urgent_threshold": -0.04, "unit": "return", "clause": "A daily portfolio loss above 2% requires review; above 4% is urgent."},
            {"rule_id": "volatility", "label": "Annualised volatility", "metric": "annualised_volatility", "operator": "lte", "threshold": 0.20, "urgent_threshold": 0.30, "unit": "annualised_volatility", "clause": "Annualised volatility above 20% requires review; above 30% is urgent."},
            {"rule_id": "drawdown", "label": "Drawdown", "metric": "drawdown", "operator": "lte", "threshold": 0.10, "urgent_threshold": 0.18, "unit": "drawdown", "clause": "Drawdown above 10% requires review; above 18% is urgent."},
            {"rule_id": "cash-minimum", "label": "Cash reserve", "metric": "cash_weight", "operator": "gte", "threshold": 0.15, "unit": "portfolio_weight", "clause": "Cash must remain at or above 15% of portfolio value."},
            {"rule_id": "issuer-concentration", "label": "Largest issuer", "metric": "largest_issuer_weight", "operator": "lte", "threshold": 0.30, "unit": "portfolio_weight", "clause": "One issuer must not exceed 30% of portfolio value."},
        ),
    },
    "diversified": {
        "mandate_id": "diversified-growth-liquidity",
        "version": "1.0.0",
        "name": "Diversified Growth and Liquidity Mandate",
        "objective": "Maintain diversified listed exposure, adequate liquidity and bounded downside risk.",
        "rules": (
            {"rule_id": "daily-loss", "label": "Daily loss", "metric": "daily_return", "operator": "gte", "threshold": -0.03, "urgent_threshold": -0.07, "unit": "return", "clause": "A daily portfolio loss above 3% requires review; above 7% is urgent."},
            {"rule_id": "volatility", "label": "Annualised volatility", "metric": "annualised_volatility", "operator": "lte", "threshold": 0.30, "urgent_threshold": 0.50, "unit": "annualised_volatility", "clause": "Annualised volatility above 30% requires review; above 50% is urgent."},
            {"rule_id": "drawdown", "label": "Drawdown", "metric": "drawdown", "operator": "lte", "threshold": 0.15, "urgent_threshold": 0.25, "unit": "drawdown", "clause": "Drawdown above 15% requires review; above 25% is urgent."},
            {"rule_id": "cash-minimum", "label": "Cash reserve", "metric": "cash_weight", "operator": "gte", "threshold": 0.05, "unit": "portfolio_weight", "clause": "Cash must remain at or above 5% of portfolio value."},
            {"rule_id": "issuer-concentration", "label": "Largest issuer", "metric": "largest_issuer_weight", "operator": "lte", "threshold": 0.25, "unit": "portfolio_weight", "clause": "One issuer must not exceed 25% of portfolio value."},
        ),
    },
    "technology_concentrated": {
        "mandate_id": "technology-concentration-research",
        "version": "1.0.0",
        "name": "Technology Concentration Research Mandate",
        "objective": "Permit intentional technology concentration while bounding issuer, liquidity and downside risk.",
        "rules": (
            {"rule_id": "daily-loss", "label": "Daily loss", "metric": "daily_return", "operator": "gte", "threshold": -0.04, "urgent_threshold": -0.08, "unit": "return", "clause": "A daily portfolio loss above 4% requires review; above 8% is urgent."},
            {"rule_id": "volatility", "label": "Annualised volatility", "metric": "annualised_volatility", "operator": "lte", "threshold": 0.40, "urgent_threshold": 0.55, "unit": "annualised_volatility", "clause": "Annualised volatility above 40% requires review; above 55% is urgent."},
            {"rule_id": "drawdown", "label": "Drawdown", "metric": "drawdown", "operator": "lte", "threshold": 0.20, "urgent_threshold": 0.30, "unit": "drawdown", "clause": "Drawdown above 20% requires review; above 30% is urgent."},
            {"rule_id": "cash-minimum", "label": "Cash reserve", "metric": "cash_weight", "operator": "gte", "threshold": 0.05, "unit": "portfolio_weight", "clause": "Cash must remain at or above 5% of portfolio value."},
            {"rule_id": "issuer-concentration", "label": "Largest issuer", "metric": "largest_issuer_weight", "operator": "lte", "threshold": 0.35, "unit": "portfolio_weight", "clause": "One issuer must not exceed 35% of portfolio value."},
            {"rule_id": "sector-concentration", "label": "Largest sector", "metric": "largest_sector_weight", "operator": "lte", "threshold": 0.80, "unit": "portfolio_weight", "clause": "One sector must not exceed 80% of portfolio value."},
        ),
    },
}


class HistoricalReplayError(ValueError):
    """A user-correctable replay setup or data error."""


@dataclass(frozen=True)
class Position:
    alias: str
    permno: int
    quantity: Decimal


def _database(private_root: Path) -> Path:
    return private_root / CATALOG_RELATIVE


def _portfolio_root(private_root: Path) -> Path:
    for relative in PORTFOLIO_RELATIVES:
        candidate = private_root / relative
        if candidate.is_dir():
            return candidate
    return private_root / PORTFOLIO_RELATIVES[0]


def _load_inputs(private_root: Path) -> tuple[dict[str, Any], dict[str, int], list[dict[str, Any]]]:
    config_path = private_root / CONFIG_RELATIVE
    map_path = _portfolio_root(private_root) / "private-instrument-map.json"
    if not config_path.is_file() or not map_path.is_file():
        raise HistoricalReplayError("reviewed portfolio inputs are unavailable")
    config = yaml.safe_load(config_path.read_text())
    mapping = json.loads(map_path.read_text())
    aliases = {
        row["instrument_alias"]: int(row["permno"])
        for row in mapping["instruments"]
    }
    portfolios = []
    for path in sorted(_portfolio_root(private_root).glob("*.yaml")):
        value = yaml.safe_load(path.read_text())
        portfolios.append(value)
    return config, aliases, portfolios


def _dataset_status(connection: duckdb.DuckDBPyConnection) -> list[dict[str, Any]]:
    definitions = (
        ("crsp", "CRSP daily prices", "crsp_daily", "observed_at"),
        ("compustat", "Compustat quarterly accounts", "compustat_quarterly", "observed_at"),
        ("ravenpack", "RavenPack events", "ravenpack_events_linked", "event_time"),
    )
    result = []
    for dataset_id, label, table, field in definitions:
        minimum, maximum, rows = connection.execute(
            f"SELECT min({field})::DATE, max({field})::DATE, count(*) FROM {table}"
        ).fetchone()
        result.append(
            {
                "id": dataset_id,
                "label": label,
                "available": rows > 0,
                "start_date": minimum.isoformat() if minimum else None,
                "end_date": maximum.isoformat() if maximum else None,
                "rows": int(rows),
            }
        )
    return result


def _current_security_context(
    connection: duckdb.DuckDBPyConnection, aliases: dict[str, int]
) -> dict[int, dict[str, str]]:
    """Resolve current readable identities without changing licensed source data."""

    ids = sorted(set(aliases.values()))
    placeholders = ",".join("?" for _ in ids)
    rows = connection.execute(
        f"""
        SELECT permno,
               arg_max(company_name, coalesce(valid_to, DATE '9999-12-31')) AS company_name,
               arg_max(ticker, coalesce(valid_to, DATE '9999-12-31')) AS ticker,
               arg_max(sector, coalesce(valid_to, DATE '9999-12-31')) AS sector,
               arg_max(industry, coalesce(valid_to, DATE '9999-12-31')) AS industry
        FROM agent_security_context
        WHERE permno IN ({placeholders})
        GROUP BY permno
        """,
        ids,
    ).fetchall()
    return {
        int(permno): {
            "company_name": company_name or f"Security {permno}",
            "ticker": ticker or "—",
            "sector": sector or "Unclassified",
            "industry": industry or "Unclassified",
        }
        for permno, company_name, ticker, sector, industry in rows
    }


def _mandate_payload(portfolio_id: str) -> dict[str, Any]:
    mandate = PORTFOLIO_MANDATES.get(portfolio_id)
    if mandate is None:
        raise HistoricalReplayError(f"portfolio {portfolio_id} has no reviewed research mandate")
    rules = sorted((dict(item) for item in mandate["rules"]), key=lambda item: item["rule_id"])
    constraint_ids = tuple(item["rule_id"] for item in rules)
    categories = {
        "daily-loss": "loss",
        "drawdown": "loss",
        "volatility": "risk_budget",
        "cash-minimum": "liquidity",
        "issuer-concentration": "concentration",
        "sector-concentration": "concentration",
    }
    canonical_mandate = MandateVersion.model_validate({
        "namespace": "portfolio-risk.research",
        "object_id": mandate["mandate_id"],
        "version": mandate["version"],
        "name": mandate["name"],
        "objective": mandate["objective"],
        "horizon_seconds": 31_557_600,
        "eligible_universe_reference": "universe:portfolio-risk.research:listed-us-research@1.0.0",
        "constraints": [
            {
                "constraint_id": item["rule_id"],
                "category": categories[item["rule_id"]],
                "statement": item["clause"],
                "clause_type": "monitoring_trigger" if item["rule_id"] in {"daily-loss", "drawdown", "volatility"} else "hard_constraint",
                "system_treatment": "alert_trigger" if item["rule_id"] in {"daily-loss", "drawdown", "volatility"} else "compliance_test",
                "source_clause_reference": f"research-design#{item['rule_id']}",
            }
            for item in rules
        ],
        "sources": [{
            "source_id": "research-design",
            "title": "ServiceFabric portfolio research mandate design",
            "source_kind": "synthetic_design",
            "reference": "docs/thesis/experiment-evaluation-framework.md",
            "authority_effect": "reference_only",
            "note": "Created as a research monitoring mandate for the named portfolio; it is not a client or legal document.",
        }],
        "capability_requirements": [{
            "capability_reference": "capability:risk:historical-replay.deterministic@1.0.0",
            "purpose": "evaluate_compliance",
            "constraint_ids": constraint_ids,
        }],
        "applicable_law_notes": ["No applicable-law rule is interpreted or enforced."],
        "effective_from": "2026-08-11T00:00:00Z",
    })
    policy = RiskPolicySet.model_validate({
        "namespace": "portfolio-risk.research",
        "object_id": f"{mandate['mandate_id']}-policy",
        "version": mandate["version"],
        "name": f"{mandate['name']} rules",
        "mandate_reference": canonical_mandate.reference,
        "rules": [
            {
                "rule_id": item["rule_id"],
                "mandate_constraint_id": item["rule_id"],
                "system_treatment": "alert_trigger" if item["rule_id"] in {"daily-loss", "drawdown", "volatility"} else "compliance_test",
                "capability_reference": "capability:risk:historical-replay.deterministic@1.0.0",
                "metric_reference": f"metric:risk:{item['metric'].replace('_', '-')}@1.0.0",
                "operator": item["operator"],
                "threshold": str(item["threshold"]),
                "unit": item["unit"],
                "evaluation_basis": "trailing_historical" if item["metric"] in {"daily_return", "annualised_volatility", "drawdown"} else "current",
                "severity": "breach",
                "escalation": "human_review",
            }
            for item in rules
        ],
    })
    validate_mandate_policy_binding(canonical_mandate, policy)
    return {
        **canonical_mandate.model_dump(mode="json"),
        "reference": canonical_mandate.reference,
        "design_basis": "Research mandate created for the current named portfolio before this experiment run.",
        "created_for_experiment": True,
        "authority": "research monitoring rules; no portfolio effects",
        "risk_policy": {**policy.model_dump(mode="json"), "reference": policy.reference},
        "rules": rules,
    }


def setup_payload(private_root: Path, workflows: list[dict[str, Any]]) -> dict[str, Any]:
    database = _database(private_root)
    if not database.is_file():
        raise HistoricalReplayError("licensed CRSP, Compustat and RavenPack database is unavailable")
    config, aliases, portfolios = _load_inputs(private_root)
    with duckdb.connect(str(database), read_only=True) as connection:
        datasets = _dataset_status(connection)
        security_context = _current_security_context(connection, aliases)

    workflow_options = []
    seen: set[str] = set()
    for workflow in workflows:
        workflow_id = str(workflow.get("asset_id") or workflow.get("native_id") or "")
        if not workflow_id or workflow_id in seen:
            continue
        seen.add(workflow_id)
        kind = {"B0": "Rules", "B1": "Agent", "A1": "Graph"}.get(workflow_id, "Fixed workflow")
        runnable = workflow_id in RUNNABLE_WORKFLOW_IDS
        workflow_options.append(
            {
                "id": workflow_id,
                "label": workflow.get("display_name") or workflow_id,
                "type": kind,
                "runnable": runnable,
                "note": (
                    "Runs locally with fixed calculations and no model call."
                    if workflow_id == RULES_WORKFLOW_ID
                    else "Runs the live bounded treatment on the same point-in-time context. B1 uses one call per cycle; A1 uses four."
                    if runnable
                    else "Visible from the Registry, but not yet qualified for this licensed-data replay."
                ),
            }
        )
    if RULES_WORKFLOW_ID not in seen:
        workflow_options.insert(
            0,
            {
                "id": RULES_WORKFLOW_ID,
                "label": "Deterministic Reference Treatment",
                "type": "Rules",
                "runnable": True,
                "note": "Runs locally with fixed calculations and no model call.",
            },
        )
    for workflow_id, label, kind in (
        ("B1", "Single-Agent Treatment", "Agent"),
        ("A1", "Four-Agent Graph Treatment", "Graph"),
    ):
        if workflow_id not in seen:
            workflow_options.append({
                "id": workflow_id,
                "label": label,
                "type": kind,
                "runnable": True,
                "note": "Live bounded treatment. B1 uses one model call per cycle; A1 uses four; maximum 20 calls per run.",
            })
    architecture_order = {"B0": 0, "B1": 1, "A1": 2}
    workflow_options.sort(
        key=lambda item: (
            not item["runnable"],
            architecture_order.get(item["id"], 99),
            item["label"],
        )
    )

    portfolio_options = []
    for value in portfolios:
        mandate = _mandate_payload(value["portfolio_id"])
        holdings = []
        for position in value.get("positions", []):
            permno = aliases[position["instrument_id"]]
            identity = security_context.get(
                permno,
                {"company_name": f"Security {permno}", "ticker": "—", "sector": "Unclassified", "industry": "Unclassified"},
            )
            holdings.append({
                "instrument_id": position["instrument_id"],
                "company_name": identity["company_name"],
                "ticker": identity["ticker"],
                "sector": identity["sector"],
                "industry": identity["industry"],
                "quantity": position["quantity"],
            })
        portfolio_options.append(
            {
                "id": value["portfolio_id"],
                "label": value["title"],
                "positions": len(value.get("positions", [])),
                "holdings": holdings,
                "mandate": mandate,
                "composition_date": datetime.now(timezone.utc).date().isoformat(),
                "identity_basis": "current company names resolved from the licensed security master",
                "quantity_basis": "quantities carried forward from the accepted real-data portfolio selection",
                "historical_use": "fixed_holdings_counterfactual",
            }
        )

    return {
        "ready": all(item["available"] for item in datasets) and bool(portfolio_options),
        "datasets": datasets,
        "data_boundary": {
            "inputs": "licensed_real_read_only",
            "portfolio": "reviewed_current_selection_fixed_holdings_counterfactual",
            "architecture_view": "point_in_time_ex_ante",
            "reference_labels": "pre_run_deterministic_mandate_rules_only",
            "retrospective_case_labels": "not_admitted",
            "synthetic_additions": "none",
            "development_fixtures_in_results": False,
        },
        "workflows": workflow_options,
        "portfolio_mandates": portfolio_options,
        "period": {
            "minimum": COMMON_START.isoformat(),
            "maximum": COMMON_END.isoformat(),
            "default_start": "2017-12-01",
            "default_end": "2017-12-29",
            "maximum_calendar_days": MAX_CALENDAR_DAYS,
            "reason": "This is the period shared by CRSP, Compustat and the local RavenPack history.",
        },
        "evaluations": [
            {
                "id": EVALUATION_ID,
                "label": "Nine-dimension dry-run evaluation",
                "note": "Evaluates every dimension that can be measured without outcome labels and clearly marks the others unavailable.",
            }
        ],
        "evaluation_dimensions": [
            "Detection quality", "Severity and risk understanding", "Timeliness",
            "Evidence quality", "Confidence and calibration", "Decision quality",
            "Robustness", "Stability", "Efficiency",
        ],
        "evaluation_capabilities": list(EVALUATION_CAPABILITY_REQUIREMENTS),
        "capability_rules": {
            "preconfigured": "Frozen before execution and identical for every comparable architecture.",
            "adaptive": "Selected during execution and recorded by the wrapper; unavailable to B0.",
            "deterministic": "Same input and frozen parameters produce the same output.",
            "statistical": "A versioned fitted model with frozen training data, parameters and threshold policy.",
            "generative": "Model-generated output; available only to admitted agent and graph architectures, never B0.",
        },
        "methodology_note": (
            "These portfolios were selected in 2026. Replaying their fixed holdings in 2013–2017 is a "
            "technical counterfactual, not yet a thesis-valid historical portfolio construction rule."
        ),
    }


def _positions(private_root: Path, portfolio_id: str) -> tuple[list[Position], Decimal, dict[str, Any]]:
    config, aliases, portfolios = _load_inputs(private_root)
    portfolio = next((item for item in portfolios if item["portfolio_id"] == portfolio_id), None)
    if portfolio is None:
        raise HistoricalReplayError("unknown portfolio and mandate selection")
    positions = []
    for item in portfolio.get("positions", []):
        alias = item["instrument_id"]
        if alias not in aliases:
            raise HistoricalReplayError(f"portfolio instrument {alias} has no licensed-data mapping")
        positions.append(Position(alias, aliases[alias], Decimal(str(item["quantity"]))))
    cash = sum(
        (Decimal(str(item["amount"])) for item in portfolio.get("cash", []) if item["currency"] == "USD"),
        Decimal("0"),
    )
    return positions, cash, config


def _severity(value: float, review: float, urgent: float, *, negative: bool = False) -> str | None:
    magnitude = -value if negative else value
    if magnitude >= urgent:
        return "urgent"
    if magnitude >= review:
        return "review"
    return None


def _regime_labels(rows: list[dict[str, Any]]) -> tuple[RegimeLabel, ...]:
    volatilities = [item["annualised_volatility"] for item in rows if item["annualised_volatility"] is not None]
    maximum_volatility = max(volatilities, default=0.0)
    volatility = "low" if maximum_volatility < 0.15 else "normal" if maximum_volatility < 0.30 else "high"
    first_value, last_value = rows[0]["portfolio_value"], rows[-1]["portfolio_value"]
    period_return = 0.0 if first_value == 0 else last_value / first_value - 1
    direction = "drawdown" if period_return <= -0.05 else "bull" if period_return >= 0.05 else "sideways"
    event_count = sum(item["ravenpack_events"]["high_relevance"] for item in rows)
    event = "material-events" if event_count else "quiet"
    return tuple(sorted((
        RegimeLabel(dimension="event", value=event, evidence_ids=("derived:eligible-high-relevance-event-count",)),
        RegimeLabel(dimension="market_direction", value=direction, evidence_ids=("derived:period-portfolio-return",)),
        RegimeLabel(dimension="volatility", value=volatility, evidence_ids=("derived:maximum-annualised-volatility",)),
    ), key=lambda item: item.dimension))


def _observation_ledger(
    rows: list[dict[str, Any]], *, start_date: date, mandate_reference: str,
    mandate_rules: list[dict[str, Any]],
) -> tuple[RuntimeObservation, ...]:
    start_time = datetime.combine(start_date, time.min, tzinfo=timezone.utc)
    observations: list[RuntimeObservation] = [
        RuntimeObservation(observation_id="input-portfolio", kind="input", name="portfolio", value="versioned fixed holdings", observed_at=start_time, available_at=start_time, evidence_ids=("input:portfolio",)),
        RuntimeObservation(observation_id="input-mandate", kind="input", name="mandate", value=mandate_reference, observed_at=start_time, available_at=start_time, evidence_ids=(mandate_reference,)),
        RuntimeObservation(observation_id="input-crsp", kind="input", name="crsp", value="licensed point-in-time prices", observed_at=start_time, available_at=start_time, evidence_ids=("dataset:crsp-daily",)),
        RuntimeObservation(observation_id="input-compustat", kind="input", name="compustat", value="licensed available fundamentals", observed_at=start_time, available_at=start_time, evidence_ids=("dataset:compustat-quarterly",)),
        RuntimeObservation(observation_id="input-ravenpack", kind="input", name="ravenpack", value="licensed eligible events", observed_at=start_time, available_at=start_time, evidence_ids=("dataset:ravenpack-events",)),
    ]
    unit_by_rule = {item["rule_id"]: item["unit"] for item in mandate_rules}
    for row in rows:
        observed_at = datetime.combine(date.fromisoformat(row["date"]), time.min, tzinfo=timezone.utc)
        available_at = datetime.fromisoformat(row["data_available_at"]) if row.get("data_available_at") else observed_at
        if available_at.tzinfo is None:
            available_at = available_at.replace(tzinfo=timezone.utc)
        for item in row["rule_results"]:
            if item["value"] is None:
                continue
            observation_id = f"obs-{row['date']}-{item['metric'].replace('_', '-')}"
            observations.append(RuntimeObservation(
                observation_id=observation_id,
                kind="derived",
                name=item["metric"].replace("_", "-"),
                value=item["value"],
                unit=unit_by_rule[item["rule_id"]],
                observed_at=observed_at,
                available_at=available_at,
                evidence_ids=tuple(item["evidence_ids"]),
            ))
        observations.append(RuntimeObservation(
            observation_id=f"obs-{row['date']}-eligible-events",
            kind="event",
            name="eligible-events",
            value=row["ravenpack_events"]["count"],
            unit="events",
            observed_at=observed_at,
            available_at=available_at,
            evidence_ids=(f"event-count:{row['date']}",),
        ))
        observations.append(RuntimeObservation(
            observation_id=row["classified_context"]["context_id"],
            kind="derived",
            name="classified-event-state",
            value=row["classified_context"]["event_state"],
            unit="classification",
            observed_at=observed_at,
            available_at=available_at,
            evidence_ids=(f"event-count:{row['date']}",),
        ))
        fundamental_context = row["classified_context"]["fundamentals"]
        observations.append(RuntimeObservation(
            observation_id=fundamental_context["context_id"],
            kind="derived",
            name="classified-fundamental-state",
            value=f"coverage:{fundamental_context['companies_covered']};negative-earnings:{fundamental_context['negative_earnings_companies']};high-leverage:{fundamental_context['high_leverage_companies']}",
            unit="classification",
            observed_at=observed_at,
            available_at=available_at,
            evidence_ids=(f"fundamental-context:{row['date']}",),
        ))
    return tuple(observations)


def _metric_key(value: str | None) -> str:
    return str(value or "unclassified").replace("_", "-")


def _deterministic_reference_cycles(rows: list[dict[str, Any]]) -> tuple[dict[str, Any], ...]:
    """Freeze mandate-rule labels independently from an architecture's output."""

    references = []
    for row in rows:
        available_at = datetime.fromisoformat(row["data_available_at"])
        if available_at.tzinfo is None:
            available_at = available_at.replace(tzinfo=timezone.utc)
        findings = tuple(
            {
                "key": f"cycle-{row['date']}:{_metric_key(item['metric'])}",
                "metric_id": _metric_key(item["metric"]),
                "risk_type": RULE_RISK_TYPES[item["rule_id"]],
                "severity": 3 if item["level"] == "urgent" else 2,
                "available_at": available_at,
            }
            for item in row["warnings"]
        )
        maximum_severity = max((item["severity"] for item in findings), default=0)
        references.append({
            "cycle_id": f"cycle-{row['date']}",
            "available_at": available_at,
            "findings": findings,
            "monitoring_action": (
                "urgent_human_review" if maximum_severity == 3
                else "increase_monitoring" if findings
                else "continue_monitoring"
            ),
            "portfolio_action": "review_exposure" if findings else "none",
        })
    return tuple(references)


def _rate(numerator: int, denominator: int) -> float | None:
    return None if denominator == 0 else numerator / denominator


EVALUATION_METHODS: dict[str, dict[str, str]] = {
    "detection_quality": {
        "formula": "precision = TP/(TP+FP); recall = TP/(TP+FN); F1 = 2PR/(P+R)",
        "scope": "Mandate-rule findings per workflow cycle against the frozen pre-run reference labels.",
    },
    "severity_understanding": {
        "formula": "score = max(0, 1 - mean absolute severity error / 3)",
        "scope": "Severity and risk-channel agreement for matched mandate findings only.",
    },
    "timeliness": {
        "formula": "same-cycle detection rate = reference findings detected in their workflow cycle / reference findings",
        "scope": "Trading-session detection plus real wall-clock processing; daily prices cannot identify intraday market reaction.",
    },
    "evidence_quality": {
        "formula": "score = findings whose citations resolve in the output evidence index / all findings",
        "scope": "Structural citation coverage; it does not independently judge whether a source is substantively correct.",
    },
    "confidence_calibration": {
        "formula": "score = 1 - mean((forecast probability - observed outcome)^2)",
        "scope": "Only outputs explicitly declared as calibrated probabilities; ordinal confidence is retained but not scored.",
    },
    "decision_quality": {
        "formula": "current score = mean(monitoring-action agreement, portfolio-action agreement)",
        "scope": "Agreement with the frozen mandate-response policy; financial regret requires matured decision branches.",
    },
    "robustness": {
        "formula": "requires performance deltas across declared perturbations or comparable regime cases",
        "scope": "Not inferred from input completeness; no score is produced without admitted perturbation cases.",
    },
    "stability": {
        "formula": "identical-output rate across repeated runs with the same frozen case and controls",
        "scope": "Calculated by the batch evaluator, never from a single run.",
    },
    "efficiency": {
        "formula": "reported vector: wall time, calls, tokens, validation failures and priced cost",
        "scope": "Observed resource use is kept disaggregated; no arbitrary composite efficiency score is applied.",
    },
}


def _evaluate_architecture_outputs(
    outputs: tuple[ArchitectureOutput, ...],
    episodes: tuple[FindingEpisode, ...],
    *,
    position_observation_completeness: float,
    wall_clock_ms: float,
    query_receipts: tuple[str, ...],
    repetitions: int,
    label_state: str,
    capability_configs: tuple[ExperimentalCapabilityConfig, ...] = (),
    reference_cycles: tuple[dict[str, Any], ...] = (),
    processing_receipts: tuple[ReplayProcessingReceipt, ...] = (),
) -> list[dict[str, Any]]:
    """Calculate observable metrics against the frozen mandate-rule reference."""

    findings = tuple(item for output in outputs for item in output.findings)
    architecture_type = outputs[0].architecture_type if outputs else "deterministic"
    labels_admitted = label_state == "admitted" and bool(reference_cycles)
    output_by_cycle = {item.cycle_id: item for item in outputs if item.cycle_id}
    reference_by_cycle = {item["cycle_id"]: item for item in reference_cycles}
    predicted_by_key: dict[str, Any] = {}
    for output in outputs:
        for finding in output.findings:
            key = f"{output.cycle_id}:{_metric_key(finding.metric_id)}"
            current = predicted_by_key.get(key)
            if current is None or finding.severity > current.severity:
                predicted_by_key[key] = finding
    reference_by_key = {
        item["key"]: item
        for cycle in reference_cycles
        for item in cycle["findings"]
    }
    predicted_keys = set(predicted_by_key)
    reference_keys = set(reference_by_key)
    true_positive_keys = predicted_keys & reference_keys
    false_positive_keys = predicted_keys - reference_keys
    false_negative_keys = reference_keys - predicted_keys
    true_positives = len(true_positive_keys)
    false_positives = len(false_positive_keys)
    false_negatives = len(false_negative_keys)
    precision = _rate(true_positives, true_positives + false_positives)
    recall = _rate(true_positives, true_positives + false_negatives)
    if reference_keys and not predicted_keys:
        precision = 0.0
    f1 = (
        None if precision is None or recall is None or precision + recall == 0
        else 2 * precision * recall / (precision + recall)
    )
    if reference_keys and precision == 0 and recall == 0:
        f1 = 0.0
    labelled_cycle_count = len(reference_cycles)
    cycle_classification_correct = sum(
        bool(output_by_cycle.get(cycle_id) and output_by_cycle[cycle_id].findings)
        == bool(reference["findings"])
        for cycle_id, reference in reference_by_cycle.items()
    )
    cycle_accuracy = _rate(cycle_classification_correct, labelled_cycle_count)

    severity_errors = [
        abs(predicted_by_key[key].severity - reference_by_key[key]["severity"])
        for key in true_positive_keys
    ]
    severity_mae = None if not severity_errors else sum(severity_errors) / len(severity_errors)
    exact_severity = _rate(sum(value == 0 for value in severity_errors), len(severity_errors))
    risk_type_accuracy = _rate(
        sum(predicted_by_key[key].risk_type == reference_by_key[key]["risk_type"] for key in true_positive_keys),
        len(true_positive_keys),
    )

    event_cycle_delays = [
        max(0.0, (item.as_of - item.trigger_available_at).total_seconds() / 3600)
        for item in outputs
        if item.as_of is not None and item.trigger_available_at is not None
    ]
    execution_summaries = [item.execution_summary for item in outputs if item.execution_summary is not None]
    first_finding_latencies = [
        (item.first_finding_at - item.started_at).total_seconds() * 1000
        for item in execution_summaries
        if item.first_finding_at is not None
    ]
    same_cycle_detection_rate = _rate(true_positives, len(reference_keys))

    evidenced_findings = sum(bool(item.evidence_ids) for item in findings)
    indexed_findings = sum(
        set(finding.evidence_ids).issubset(
            set(output.supporting_evidence_ids) | set(output.conflicting_evidence_ids)
        )
        for output in outputs
        for finding in output.findings
    )
    evidence_coverage = _rate(evidenced_findings, len(findings))
    evidence_index_coverage = _rate(indexed_findings, len(findings))
    mean_evidence_per_finding = (
        None if not findings else sum(len(item.evidence_ids) for item in findings) / len(findings)
    )

    calibrated_outputs = [item for item in outputs if item.confidence_kind == "calibrated_probability"]
    ordinal_outputs = [item for item in outputs if item.confidence_kind == "ordinal_judgement"]
    brier_values = []
    for output in calibrated_outputs:
        reference = reference_by_cycle.get(output.cycle_id)
        if reference is None:
            continue
        event_probability = output.confidence if output.assessment_state != "clear" else 1 - output.confidence
        outcome = 1.0 if reference["findings"] else 0.0
        brier_values.append((event_probability - outcome) ** 2)
    brier_score = None if not brier_values else sum(brier_values) / len(brier_values)

    monitoring_matches = 0
    portfolio_matches = 0
    comparable_decisions = 0
    monitoring_distance = []
    action_rank = {"continue_monitoring": 0, "increase_monitoring": 1, "urgent_human_review": 2, "no_action": 0}
    for cycle_id, reference in reference_by_cycle.items():
        output = output_by_cycle.get(cycle_id)
        if output is None:
            continue
        comparable_decisions += 1
        actual = output.decision.monitoring_action
        expected = reference["monitoring_action"]
        monitoring_matches += actual == expected
        portfolio_matches += output.decision.portfolio_action == reference["portfolio_action"]
        monitoring_distance.append(abs(action_rank[actual] - action_rank[expected]))
    monitoring_agreement = _rate(monitoring_matches, comparable_decisions)
    portfolio_agreement = _rate(portfolio_matches, comparable_decisions)
    mean_monitoring_distance = None if not monitoring_distance else sum(monitoring_distance) / len(monitoring_distance)

    if processing_receipts:
        measured_wall_ms = sum(item.processing_wall_ms for item in processing_receipts)
        capability_calls = sum(item.capability_calls for item in processing_receipts)
        model_calls = sum(item.model_calls for item in processing_receipts)
        input_tokens = sum(item.input_tokens for item in processing_receipts)
        cached_input_tokens = sum(item.cached_input_tokens for item in processing_receipts)
        output_tokens = sum(item.output_tokens for item in processing_receipts)
        estimated_cost = (
            None if any(item.estimated_cost_usd is None for item in processing_receipts)
            else sum(item.estimated_cost_usd or 0.0 for item in processing_receipts)
        )
    else:
        measured_wall_ms = wall_clock_ms
        capability_calls = sum(item.capability_calls for item in execution_summaries)
        model_calls = sum(item.model_calls for item in execution_summaries)
        input_tokens = sum(item.input_tokens for item in execution_summaries)
        cached_input_tokens = sum(item.cached_input_tokens for item in execution_summaries)
        output_tokens = sum(item.output_tokens for item in execution_summaries)
        estimated_cost = sum(item.cost_usd for item in execution_summaries) if execution_summaries else 0.0
    schema_failures = sum(item.schema_validation_failures for item in execution_summaries)
    semantic_failures = sum(item.semantic_verification_failures for item in execution_summaries)
    execution_errors = sum(len(item.errors) for item in execution_summaries)
    capability_by_role = {
        role: tuple(item.capability_id for item in capability_configs if role in item.evaluation_roles)
        for role in ("architecture_input", "reference_label", "measurement")
    }
    detection_status = "measured" if labels_admitted else "not_measurable"
    detection_score = f1 if reference_keys else cycle_accuracy if labels_admitted else None
    decision_score = (
        None if monitoring_agreement is None or portfolio_agreement is None
        else (monitoring_agreement + portfolio_agreement) / 2
    )
    dimensions = [
        {"id": "detection_quality", "label": "Detection quality", "status": detection_status, "score": detection_score, "summary": "Positive cycles use precision, recall and F1; all labelled cycles use breach/no-breach classification accuracy against the pre-run deterministic mandate reference. Unlabelled event relevance is outside this score." if detection_status == "measured" else "Detection requires an admitted reference label set.", "metrics": {"true_positives": true_positives, "false_positives": false_positives, "false_negatives": false_negatives, "precision": precision, "recall": recall, "f1": f1, "cycle_classification_accuracy": cycle_accuracy, "labelled_cycles": labelled_cycle_count, "finding_episodes": len(episodes), "reference_scope": "deterministic_mandate_breaches", "reference_capabilities": ",".join(capability_by_role["reference_label"]) or "none"}},
        {"id": "severity_understanding", "label": "Severity and risk understanding", "status": "measured" if severity_mae is not None else "not_applicable", "score": None if severity_mae is None else max(0.0, 1 - severity_mae / 3), "summary": "Matched mandate findings are compared with the frozen reference severity and risk channel; unmatched findings remain detection errors." if severity_mae is not None else "No matched positive mandate finding is available for severity comparison.", "metrics": {"matched_findings": len(true_positive_keys), "severity_mae": severity_mae, "exact_severity_rate": exact_severity, "risk_type_accuracy": risk_type_accuracy, "review_findings": sum(item.severity == 2 for item in findings), "urgent_findings": sum(item.severity == 3 for item in findings)}},
        {"id": "timeliness", "label": "Timeliness", "status": "measured" if reference_keys else "not_applicable", "score": same_cycle_detection_rate, "summary": "Detection is scored in trading-session units; workflow and model processing retain wall-clock milliseconds. Intraday market reaction remains unidentifiable from daily prices.", "metrics": {"cycle_outputs": len(outputs), "reference_findings": len(reference_keys), "same_cycle_detection_rate": same_cycle_detection_rate, "mean_trigger_to_cycle_hours": None if not event_cycle_delays else sum(event_cycle_delays) / len(event_cycle_delays), "maximum_trigger_to_cycle_hours": None if not event_cycle_delays else max(event_cycle_delays), "mean_processing_to_first_finding_ms": None if not first_finding_latencies else sum(first_finding_latencies) / len(first_finding_latencies), "market_response_unit": "trading_session", "minimum_market_horizon_sessions": 1, "within_session_market_reaction_identifiable": False, "measurement_capabilities": ",".join(capability_by_role["measurement"]) or "none"}},
        {"id": "evidence_quality", "label": "Evidence quality", "status": "not_applicable" if not findings else "measured", "score": evidence_index_coverage, "summary": "The score measures structural citation and evidence-index coverage only; source correctness and substantive sufficiency require an independent evidence review.", "metrics": {"finding_citation_coverage": evidence_coverage, "evidence_index_coverage": evidence_index_coverage, "mean_evidence_references_per_finding": mean_evidence_per_finding, "unsupported_findings": len(findings) - evidenced_findings, "unindexed_findings": len(findings) - indexed_findings, "unique_supporting_evidence": len({value for item in outputs for value in item.supporting_evidence_ids}), "quality_scope": "structural_not_substantive"}},
        {"id": "confidence_calibration", "label": "Confidence and calibration", "status": "measured" if brier_score is not None else "not_applicable" if architecture_type == "deterministic" else "not_measurable", "score": None if brier_score is None else max(0.0, 1 - brier_score), "summary": "Brier score is calculated only for outputs explicitly declaring calibrated probabilities." if brier_score is not None else "The deterministic baseline reports calculation confidence, not a probabilistic forecast." if architecture_type == "deterministic" else "Ordinal agent confidence is retained but is not misrepresented as calibrated probability.", "metrics": {"probabilistic_confidence_outputs": len(calibrated_outputs), "ordinal_confidence_outputs": len(ordinal_outputs), "calibration_cases": len(brier_values), "brier_score": brier_score, "mean_ordinal_confidence": None if not ordinal_outputs else sum(item.confidence for item in ordinal_outputs) / len(ordinal_outputs)}},
        {"id": "decision_quality", "label": "Decision quality", "status": "partial" if comparable_decisions else "not_measurable", "score": decision_score, "summary": "Current scoring measures agreement with the predeclared mandate-response policy. Financial regret remains unavailable until counterfactual branch outcomes mature.", "metrics": {"decision_points": len(outputs), "comparable_decisions": comparable_decisions, "monitoring_action_agreement": monitoring_agreement, "portfolio_action_agreement": portfolio_agreement, "mean_monitoring_action_distance": mean_monitoring_distance, "branches": len(outputs) * 2, "regret": None}},
        {"id": "robustness", "label": "Robustness", "status": "not_measurable", "score": None, "summary": "Input completeness is reported as runtime quality, not robustness. Robustness requires perturbations or comparable cases across regimes.", "metrics": {"position_observation_completeness": round(position_observation_completeness, 6), "perturbation_cases": 0}},
        {"id": "stability", "label": "Stability", "status": "partial", "score": None, "summary": "A repetition index is not a stability calculation. Output-digest agreement is computed only by the batch evaluator across completed identical repetitions.", "metrics": {"deterministic_execution": architecture_type == "deterministic", "current_repetition": repetitions, "compared_repetitions": 0, "unique_output_signatures": None}},
        {"id": "efficiency", "label": "Efficiency", "status": "measured", "score": None, "summary": "Observed processing, calls, tokens, failures and priced cost are reported separately without an arbitrary composite score.", "metrics": {"processing_wall_ms": round(measured_wall_ms, 3), "mean_processing_ms_per_cycle": _rate(round(measured_wall_ms, 3), len(outputs)), "mean_processing_ms_per_finding": _rate(round(measured_wall_ms, 3), len(findings)), "capability_calls": capability_calls, "model_calls": model_calls, "input_tokens": input_tokens, "cached_input_tokens": cached_input_tokens, "output_tokens": output_tokens, "schema_validation_failures": schema_failures, "semantic_verification_failures": semantic_failures, "execution_errors": execution_errors, "database_queries": len(query_receipts), "estimated_cost_usd": None if estimated_cost is None else round(estimated_cost, 8)}},
    ]
    for dimension in dimensions:
        method = EVALUATION_METHODS[dimension["id"]]
        dimension["formula"] = method["formula"]
        dimension["measurement_scope"] = method["scope"]
    return dimensions


def _build_run_diagnostics(
    *,
    workflow_id: str,
    evaluation_dimensions: list[dict[str, Any]],
    outputs: tuple[ArchitectureOutput, ...],
    missing_position_observations: int,
    missing_position_names: tuple[str, ...] = (),
) -> dict[str, Any]:
    """Create a concise, deterministic run-shortcoming log for review and Codex handoff."""

    issues: dict[str, dict[str, Any]] = {}

    def add(
        code: str,
        *,
        category: str,
        severity: str,
        summary: str,
        detail: str,
        remediation: str,
        dimensions: tuple[str, ...] = (),
    ) -> None:
        issues.setdefault(code, {
            "code": code,
            "category": category,
            "severity": severity,
            "summary": summary,
            "detail": detail,
            "affected_dimensions": list(dimensions),
            "remediation": remediation,
            "codex_actionable": True,
        })

    if missing_position_observations:
        named_gap = (
            f" Affected holdings: {', '.join(missing_position_names)}."
            if missing_position_names else ""
        )
        add(
            "DATA-MISSING-POSITION-OBSERVATIONS",
            category="data",
            severity="high",
            summary="Some portfolio positions had no eligible market observation.",
            detail=(
                f"The run recorded {missing_position_observations} missing position observations."
                f"{named_gap} No eligible valuation price was silently imputed."
            ),
            remediation="Inspect identifier coverage and point-in-time market-data eligibility before relying on the affected cycles.",
            dimensions=("robustness", "detection_quality"),
        )

    for dimension in evaluation_dimensions:
        status = dimension["status"]
        if status in {"measured", "not_applicable"}:
            continue
        severity = "high" if dimension["id"] == "decision_quality" else "medium"
        add(
            f"EVAL-{dimension['id'].upper().replace('_', '-')}-{status.upper().replace('_', '-')}",
            category="evaluation",
            severity=severity,
            summary=f"{dimension['label']} is {status.replace('_', ' ')}.",
            detail=dimension["summary"],
            remediation=(
                "Admit the missing labels, matured outcomes, repetitions or perturbation cases described by this dimension before thesis comparison."
            ),
            dimensions=(dimension["id"],),
        )

    execution_errors = sum(
        len(output.execution_summary.errors)
        for output in outputs
        if output.execution_summary is not None
    )
    schema_failures = sum(
        output.execution_summary.schema_validation_failures
        for output in outputs
        if output.execution_summary is not None
    )
    semantic_failures = sum(
        output.execution_summary.semantic_verification_failures
        for output in outputs
        if output.execution_summary is not None
    )
    if execution_errors or schema_failures or semantic_failures:
        add(
            "EXECUTION-VALIDATION-FAILURES",
            category="execution",
            severity="high",
            summary="The architecture recorded execution or output-validation failures.",
            detail=(
                f"errors={execution_errors}; schema_failures={schema_failures}; "
                f"semantic_failures={semantic_failures}."
            ),
            remediation="Inspect processing receipts and the affected structured outputs; fix the architecture before comparing its scores.",
            dimensions=("efficiency", "evidence_quality"),
        )

    missing_information = sorted({value for output in outputs for value in output.missing_information})
    limitations = sorted({value for output in outputs for value in output.limitations})
    warnings = sorted({value for output in outputs for value in output.warnings})
    if missing_information or limitations or warnings:
        add(
            "OUTPUT-DECLARED-LIMITATIONS",
            category="architecture_output",
            severity="medium",
            summary="The architecture declared unresolved information or limitations.",
            detail=" | ".join((missing_information + limitations + warnings)[:12]),
            remediation="Review the declared gaps and add only the data, capability or output-contract changes that materially affect the research question.",
            dimensions=("evidence_quality", "decision_quality"),
        )

    add(
        "METHOD-FIXED-HOLDINGS-RETROJECTION",
        category="methodology",
        severity="high",
        summary="Current accepted holdings are retrojected into the historical period.",
        detail="This run validates the apparatus but is not clean thesis evidence for a historically constructed portfolio.",
        remediation="Freeze a point-in-time portfolio-construction rule before the test period and rerun the case.",
        dimensions=("detection_quality", "decision_quality", "robustness"),
    )
    add(
        "METHOD-SHARED-DETERMINISTIC-REFERENCE",
        category="methodology",
        severity="medium",
        summary="All architectures receive the same deterministic calculations used by the reference treatment.",
        detail="Agreement scores verify preservation of the mandate baseline; they cannot alone demonstrate that an agent is superior.",
        remediation="Add independently labelled event relevance, severity and matured outcome cases for discriminating architecture comparisons.",
        dimensions=("detection_quality", "severity_understanding", "decision_quality"),
    )
    add(
        "METHOD-DAILY-PRICE-INTERVAL-CENSORING",
        category="methodology",
        severity="medium",
        summary="Daily prices cannot identify intraday market reaction or exact alpha decay.",
        detail="Events are processed chronologically, but tradable response is evaluated no earlier than the eligible daily close.",
        remediation="Keep session-level timeliness separate from processing latency; admit intraday prices only in a later data regime.",
        dimensions=("timeliness", "decision_quality"),
    )

    severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    ordered = sorted(issues.values(), key=lambda item: (severity_order[item["severity"]], item["code"]))
    counts = {level: sum(item["severity"] == level for item in ordered) for level in severity_order}
    return {
        "schema_version": "portfolio-risk.run-diagnostics/v1",
        "workflow_id": workflow_id,
        "status": "attention_required" if counts["critical"] or counts["high"] else "review",
        "counts": counts,
        "shortcomings": ordered,
        "risk_criticalities": [
            {
                "cycle_id": output.cycle_id,
                "assessment_state": output.assessment_state,
                "severity": output.severity,
                "summary": output.risk_interpretation,
                "finding_ids": [finding.finding_id for finding in output.findings],
            }
            for output in outputs
            if output.findings or output.assessment_state != "clear"
        ],
        "codex_handoff": {
            "purpose": "Debug and improve the experimental apparatus without confusing portfolio-risk findings with system defects.",
            "priority_issue_codes": [item["code"] for item in ordered if item["severity"] in {"critical", "high"}],
            "inspect_files": ["run-diagnostics.json", "processing-receipts.json", "evaluation-record.json", "architecture-outputs.json"],
        },
    }


def run_replay(
    private_root: Path,
    *,
    workflow_id: str,
    portfolio_id: str,
    start_date: date,
    end_date: date,
    evaluation_id: str,
    study_id: str = STUDY_ID,
    experiment_id: str = EXPERIMENT_ID,
    study_title: str = "Agentic portfolio-risk architecture study",
    research_question: str = "How does the selected architecture interpret the same mandate-linked point-in-time portfolio-risk context?",
    hypothesis: str = "Agent treatments may improve semantic risk understanding over the deterministic reference while preserving evidence, temporal and effect-free constraints.",
    repetition: int = 1,
) -> dict[str, Any]:
    started_at = datetime.now(timezone.utc)
    started = perf_counter()
    if workflow_id not in RUNNABLE_WORKFLOW_IDS:
        raise HistoricalReplayError("the selected Registry workflow is not runnable on this replay")
    if evaluation_id != EVALUATION_ID:
        raise HistoricalReplayError("unknown evaluation method")
    if start_date < COMMON_START or end_date > COMMON_END or start_date > end_date:
        raise HistoricalReplayError("dates must fall inside the shared 2013–2017 data period")
    if (end_date - start_date).days > MAX_CALENDAR_DAYS:
        raise HistoricalReplayError(f"the first runnable slice is limited to {MAX_CALENDAR_DAYS} calendar days")

    positions, cash, config = _positions(private_root, portfolio_id)
    mandate = _mandate_payload(portfolio_id)
    ids = [item.permno for item in positions]
    quantity_by_id = {item.permno: item.quantity for item in positions}
    database = _database(private_root)
    query_receipts: list[str] = []
    with duckdb.connect(str(database), read_only=True) as connection:
        placeholders = ",".join("?" for _ in ids)
        market_rows = connection.execute(
            f"""
            SELECT observed_at::DATE AS replay_date, permno, valuation_price, total_return, available_at::VARCHAR
            FROM crsp_daily
            WHERE permno IN ({placeholders})
              AND observed_at::DATE <= ?
            ORDER BY replay_date, permno
            """,
            [*ids, end_date],
        ).fetchall()
        query_receipts.append("crsp-instrument-lifetime-through-as-of")
        event_rows = connection.execute(
            f"""
            WITH sessions AS (
              SELECT observed_at::DATE AS replay_date, max(available_at) AS clock_time
              FROM crsp_daily
              WHERE permno IN ({placeholders})
                AND observed_at::DATE BETWEEN ? AND ?
              GROUP BY replay_date
            )
            SELECT s.replay_date,
                   e.permno,
                   coalesce(
                     e.event_similarity_key,
                     concat_ws('|', e.event_type, e.topic, e.event_group, e.event_sub_type, e.category)
                   ) AS cluster_key,
                   min(e.event_time)::VARCHAR AS event_time,
                   min(e.available_at)::VARCHAR AS first_available_at,
                   max(e.available_at)::VARCHAR AS last_available_at,
                   count(*) AS event_count,
                   count(*) FILTER (WHERE sentiment < -0.2) AS negative_count,
                   avg(e.sentiment) AS average_sentiment,
                   max(e.relevance) AS maximum_relevance,
                   avg(e.novelty) AS average_novelty
            FROM sessions s
            JOIN ravenpack_events_linked e
              ON e.permno IN ({placeholders})
             AND e.event_time::DATE = s.replay_date
             AND e.available_at <= s.clock_time
             AND e.relevance >= 0.8
            GROUP BY s.replay_date, e.permno, cluster_key
            ORDER BY s.replay_date, first_available_at, cluster_key
            """,
            [*ids, start_date, end_date, *ids],
        ).fetchall()
        query_receipts.append("ravenpack-point-in-time-event-classification-input")
        fundamentals = connection.execute(
            f"""
            WITH linked AS (
              SELECT DISTINCT gvkey
              FROM ccm_links
              WHERE permno IN ({placeholders})
                AND link_start <= ?
                AND (link_end IS NULL OR link_end >= ?)
            )
            SELECT count(DISTINCT q.gvkey), max(q.available_at)::DATE
            FROM compustat_quarterly q
            JOIN linked l USING (gvkey)
            WHERE q.available_at <= (
              SELECT max(available_at) FROM crsp_daily
              WHERE permno IN ({placeholders}) AND observed_at::DATE BETWEEN ? AND ?
            )
            """,
            [*ids, end_date, start_date, *ids, start_date, end_date],
        ).fetchone()
        query_receipts.append("compustat-point-in-time-coverage")
        fundamental_rows = connection.execute(
            f"""
            SELECT DISTINCT l.permno, q.gvkey, q.available_at::VARCHAR,
                   q.total_assets, q.total_liabilities, q.common_equity,
                   q.revenue, q.net_income
            FROM ccm_links l
            JOIN compustat_quarterly q USING (gvkey)
            WHERE l.permno IN ({placeholders})
              AND q.available_at <= (
                SELECT max(available_at) FROM crsp_daily
                WHERE permno IN ({placeholders}) AND observed_at::DATE BETWEEN ? AND ?
              )
              AND l.link_start <= q.observed_at
              AND (l.link_end IS NULL OR l.link_end >= q.observed_at)
            ORDER BY l.permno, q.available_at
            """,
            [*ids, *ids, start_date, end_date],
        ).fetchall()
        query_receipts.append("compustat-point-in-time-fundamental-classification-input")
        security_context = _current_security_context(
            connection, {item.alias: item.permno for item in positions}
        )
        query_receipts.append("security-master-display-context")

    by_date: dict[date, list[tuple[int, Decimal, Decimal | None]]] = {}
    clock_times: dict[date, str] = {}
    for replay_date, permno, price, total_return, available_at in market_rows:
        if available_at is not None:
            clock_times[replay_date] = max(clock_times.get(replay_date, available_at), available_at)
        if price is not None:
            by_date.setdefault(replay_date, []).append((int(permno), Decimal(price), total_return))
    event_clusters: dict[date, list[dict[str, Any]]] = {}
    for row in event_rows:
        replay_date, permno = row[0], int(row[1])
        stream = event_clusters.setdefault(replay_date, [])
        stream.append({
            "event_id": f"event-cluster-{replay_date.isoformat()}-{len(stream) + 1:03d}",
            "event_time": row[3],
            "information_available_at": row[4],
            "last_information_available_at": row[5],
            "relevance_identified_at": row[4],
            "company_name": security_context.get(permno, {}).get("company_name", f"Security {permno}"),
            "source_records": int(row[6]),
            "negative_records": int(row[7]),
            "average_sentiment": float(row[8]) if row[8] is not None else None,
            "maximum_relevance": float(row[9]) if row[9] is not None else None,
            "average_novelty": float(row[10]) if row[10] is not None else None,
            "relevance_method": "provider-relevance-baseline@1.0.0",
        })
    events: dict[date, dict[str, Any]] = {}
    for replay_date, stream in event_clusters.items():
        source_count = sum(item["source_records"] for item in stream)
        events[replay_date] = {
            "count": source_count,
            "high_relevance": source_count,
            "high_relevance_negative": sum(item["negative_records"] for item in stream),
            "average_sentiment": None if not source_count else sum((item["average_sentiment"] or 0) * item["source_records"] for item in stream) / source_count,
            "maximum_relevance": max((item["maximum_relevance"] or 0) for item in stream),
            "average_novelty": None if not source_count else sum((item["average_novelty"] or 0) * item["source_records"] for item in stream) / source_count,
            "first_available_at": stream[0]["information_available_at"],
            "last_available_at": max(item["last_information_available_at"] for item in stream),
            "classifier": "provider-relevance-baseline@1.0.0",
            "event_stream": stream,
        }
    fundamental_history: dict[int, list[dict[str, Any]]] = {}
    for permno, _gvkey, available_at, assets, liabilities, equity, revenue, net_income in fundamental_rows:
        if available_at is None:
            continue
        available = datetime.fromisoformat(available_at)
        if available.tzinfo is None:
            available = available.replace(tzinfo=timezone.utc)
        fundamental_history.setdefault(int(permno), []).append({
            "available_at": available,
            "assets": float(assets) if assets is not None else None,
            "liabilities": float(liabilities) if liabilities is not None else None,
            "equity": float(equity) if equity is not None else None,
            "revenue": float(revenue) if revenue is not None else None,
            "net_income": float(net_income) if net_income is not None else None,
        })

    def classify_fundamentals(as_of: datetime) -> dict[str, Any]:
        latest_records = []
        for permno in ids:
            eligible = [item for item in fundamental_history.get(permno, ()) if item["available_at"] <= as_of]
            if eligible:
                latest_records.append(max(eligible, key=lambda item: item["available_at"]))
        negative_earnings = sum(item["net_income"] is not None and item["net_income"] < 0 for item in latest_records)
        high_leverage = sum(
            item["assets"] not in (None, 0) and item["liabilities"] is not None
            and item["liabilities"] / item["assets"] >= 0.8
            for item in latest_records
        )
        return {
            "context_id": f"fundamental-context-{as_of.date().isoformat()}",
            "classifier": "fundamental-state-baseline@1.0.0",
            "companies_covered": len(latest_records),
            "negative_earnings_companies": negative_earnings,
            "high_leverage_companies": high_leverage,
            "quality": "complete" if len(latest_records) == len(ids) else "partial",
        }
    if not by_date:
        raise HistoricalReplayError("CRSP has no observations for the selected portfolio and dates")

    instrument_lifetime_summaries = []
    for position in positions:
        history = [
            (replay_date, price, total_return)
            for replay_date, permno, price, total_return, _available_at in market_rows
            if int(permno) == position.permno
        ]
        usable_returns: list[float] = []
        price_fallbacks = 0
        previous_price: Decimal | None = None
        nav, peak, maximum_drawdown = 1.0, 1.0, 0.0
        for _observed_date, price, total_return in history:
            instrument_return = None
            if total_return is not None:
                instrument_return = float(total_return)
            elif price is not None and previous_price not in (None, 0):
                instrument_return = float(Decimal(price) / previous_price - 1)
                price_fallbacks += 1
            if price is not None:
                previous_price = Decimal(price)
            if instrument_return is not None:
                usable_returns.append(instrument_return)
                nav *= 1 + instrument_return
                peak = max(peak, nav)
                maximum_drawdown = max(maximum_drawdown, 1 - nav / peak)
        lifetime_volatility = None
        if len(usable_returns) >= 2:
            mean = sum(usable_returns) / len(usable_returns)
            variance = sum((item - mean) ** 2 for item in usable_returns) / (len(usable_returns) - 1)
            lifetime_volatility = math.sqrt(variance) * math.sqrt(252)
        observed_dates = [item[0] for item in history]
        instrument_lifetime_summaries.append({
            "instrument": security_context.get(position.permno, {}).get("company_name", position.alias),
            "history_start": min(observed_dates).isoformat() if observed_dates else None,
            "history_end": max(observed_dates).isoformat() if observed_dates else None,
            "return_observations": len(usable_returns),
            "price_return_fallbacks": price_fallbacks,
            "annualised_volatility": round(lifetime_volatility, 6) if lifetime_volatility is not None else None,
            "maximum_drawdown": round(maximum_drawdown, 6),
            "quality": "complete" if usable_returns and price_fallbacks == 0 else "partial",
        })

    minimum_volatility_observations = int(config["minimum_daily_observations"])
    instrument_first_dates = {
        permno: min(replay_date for replay_date, observations in by_date.items() if any(item[0] == permno for item in observations))
        for permno in ids
    }
    history_start = max(instrument_first_dates.values())
    lifetime_returns: list[float] = []
    lifetime_price_fallbacks = 0
    rows: list[dict[str, Any]] = []
    total_return_nav = 1.0
    peak_total_return_nav = 1.0
    previous_position_values: dict[int, float] | None = None
    warnings = 0
    missing_inputs = 0
    rule_counts = {
        item["rule_id"]: {"passed": 0, "breached": 0, "unable_to_assess": 0}
        for item in mandate["rules"]
    }

    for replay_date, observations in sorted(by_date.items()):
        if replay_date < history_start:
            continue
        position_values_by_id = {
            # CRSP encodes a negative PRC when it reports a bid/ask midpoint;
            # the sign is metadata, not a negative security value.
            permno: float(quantity_by_id[permno] * abs(price))
            for permno, price, _ in observations
        }
        position_values = list(position_values_by_id.values())
        portfolio_value = float(cash) + sum(position_values)
        total_returns_by_id = {
            permno: float(total_return)
            for permno, _price, total_return in observations
            if total_return is not None
        }
        daily_return = None
        price_fallback_ids: list[int] = []
        common_return_ids = set(previous_position_values or {}) & set(position_values_by_id)
        if previous_position_values is not None and common_return_ids:
            previous_nav = float(cash) + sum(previous_position_values[permno] for permno in common_return_ids)
            if previous_nav:
                constituent_returns = {}
                for permno in common_return_ids:
                    if permno in total_returns_by_id:
                        constituent_returns[permno] = total_returns_by_id[permno]
                    elif previous_position_values[permno]:
                        constituent_returns[permno] = position_values_by_id[permno] / previous_position_values[permno] - 1
                        price_fallback_ids.append(permno)
                daily_return = sum(
                    previous_position_values[permno] / previous_nav * constituent_returns[permno]
                    for permno in common_return_ids
                )
                lifetime_price_fallbacks += len(price_fallback_ids)
        if daily_return is not None:
            lifetime_returns.append(daily_return)
            total_return_nav *= 1 + daily_return
            peak_total_return_nav = max(peak_total_return_nav, total_return_nav)
        drawdown = 1 - total_return_nav / peak_total_return_nav
        volatility = None
        if len(lifetime_returns) >= minimum_volatility_observations:
            mean = sum(lifetime_returns) / len(lifetime_returns)
            variance = sum((item - mean) ** 2 for item in lifetime_returns) / (len(lifetime_returns) - 1)
            volatility = math.sqrt(variance) * math.sqrt(252)
        cash_weight = 0.0 if portfolio_value == 0 else float(cash) / portfolio_value
        largest_issuer_weight = (
            0.0 if portfolio_value == 0 or not position_values
            else max(position_values) / portfolio_value
        )
        sector_values: dict[str, float] = {}
        for permno, value in position_values_by_id.items():
            sector = security_context.get(permno, {}).get("sector", "Unclassified")
            sector_values[sector] = sector_values.get(sector, 0.0) + value
        largest_sector_weight = (
            0.0 if portfolio_value == 0 or not sector_values
            else max(sector_values.values()) / portfolio_value
        )
        metric_values = {
            "daily_return": daily_return,
            "annualised_volatility": volatility,
            "drawdown": drawdown,
            "cash_weight": cash_weight,
            "largest_issuer_weight": largest_issuer_weight,
            "largest_sector_weight": largest_sector_weight,
        }
        previous_position_values = position_values_by_id
        if replay_date < start_date or replay_date > end_date:
            continue
        missing = len(positions) - len(observations)
        missing_position_names = tuple(
            security_context.get(permno, {}).get("company_name", f"Security {permno}")
            for permno in sorted(set(ids) - set(position_values_by_id))
        )
        metric_quality = "complete" if missing == 0 and not price_fallback_ids else "partial"
        rule_results = []
        warning_items = []
        for rule in mandate["rules"]:
            value = metric_values.get(rule["metric"])
            if value is None:
                status = "unable_to_assess"
                level = None
            else:
                passed = value >= rule["threshold"] if rule["operator"] == "gte" else value <= rule["threshold"]
                status = "passed" if passed else "breached"
                level = None
                if not passed:
                    urgent = rule.get("urgent_threshold")
                    if urgent is None:
                        level = "review"
                    elif rule["operator"] == "gte":
                        level = "urgent" if value < urgent else "review"
                    else:
                        level = "urgent" if value > urgent else "review"
                    warning_items.append({
                        "level": level,
                        "reason": rule["label"],
                        "rule_id": rule["rule_id"],
                        "metric": rule["metric"],
                        "observed_value": value,
                        "threshold": rule["threshold"],
                        "threshold_distance": abs(value - rule["threshold"]) / max(abs(rule["threshold"]), 0.01),
                        "metric_quality": metric_quality,
                        "evidence_ids": [f"metric:{rule['metric']}:{replay_date.isoformat()}", mandate["reference"]],
                    })
            rule_counts[rule["rule_id"]][status] += 1
            rule_results.append({
                "rule_id": rule["rule_id"],
                "label": rule["label"],
                "metric": rule["metric"],
                "value": round(value, 6) if value is not None else None,
                "operator": rule["operator"],
                "threshold": rule["threshold"],
                "threshold_distance": None if value is None else round(abs(value - rule["threshold"]) / max(abs(rule["threshold"]), 0.01), 6),
                "status": status,
                "metric_quality": metric_quality,
                "evidence_ids": [] if value is None else [f"metric:{rule['metric']}:{replay_date.isoformat()}"],
            })
        warnings += len(warning_items)
        missing_inputs += missing
        event = events.get(replay_date, {
            "count": 0, "high_relevance": 0, "high_relevance_negative": 0,
            "average_sentiment": None, "maximum_relevance": None,
            "average_novelty": None, "first_available_at": None, "last_available_at": None,
            "classifier": "provider-relevance-baseline@1.0.0", "event_stream": [],
        })
        available_at = datetime.fromisoformat(clock_times[replay_date]) if clock_times.get(replay_date) else datetime.combine(replay_date, time.max, tzinfo=timezone.utc)
        if available_at.tzinfo is None:
            available_at = available_at.replace(tzinfo=timezone.utc)
        fundamental_context = classify_fundamentals(available_at)
        rows.append(
            {
                "date": replay_date.isoformat(),
                "data_available_at": clock_times.get(replay_date),
                "workflow_cycle_at": clock_times.get(replay_date),
                "market_observation_session": replay_date.isoformat(),
                "portfolio_value": round(portfolio_value, 2),
                "daily_return": round(daily_return, 6) if daily_return is not None else None,
                "annualised_volatility": round(volatility, 6) if volatility is not None else None,
                "drawdown": round(drawdown, 6),
                "cash_weight": round(cash_weight, 6),
                "largest_issuer_weight": round(largest_issuer_weight, 6),
                "largest_sector_weight": round(largest_sector_weight, 6),
                "position_values": [
                    {
                        "company_name": security_context.get(permno, {}).get("company_name", f"Security {permno}"),
                        "market_value": round(value, 2),
                    }
                    for permno, value in sorted(position_values_by_id.items())
                ],
                "metric_history": {
                    "common_inception": history_start.isoformat(),
                    "daily_returns_available": len(lifetime_returns),
                    "policy": "instrument_lifetime_to_as_of",
                    "return_source": "crsp_total_return_with_disclosed_price_fallback",
                    "constituent_coverage": round(len(position_values_by_id) / len(ids), 6),
                    "price_return_fallbacks_to_date": lifetime_price_fallbacks,
                    "cycle_price_return_fallbacks": len(price_fallback_ids),
                },
                "ravenpack_events": event,
                "temporal_measurement": {
                    "event_clock": "intraday_available_at",
                    "workflow_clock": "point_in_time_context_available_at",
                    "market_clock": "daily_close",
                    "market_response_unit": "trading_session",
                    "response_time_identification": "interval_censored_between_daily_closes",
                    "minimum_market_horizon_sessions": 1,
                    "within_session_market_reaction_not_identifiable": True,
                },
                "classified_context": {
                    "context_id": f"classified-context-{replay_date.isoformat()}",
                    "event_state": "material-negative" if event["high_relevance_negative"] else "material" if event["high_relevance"] else "quiet",
                    "event_classifier": event["classifier"],
                    "fundamentals": fundamental_context,
                },
                "positions_observed": len(observations),
                "positions_missing": missing,
                "position_observations_missing": [
                    {
                        "company_name": company_name,
                        "status": "unavailable",
                        "reason": "No eligible CRSP valuation price was available for this trading session.",
                    }
                    for company_name in missing_position_names
                ],
                "warnings": warning_items,
                "rule_results": rule_results,
            }
        )

    calls_per_cycle = {"B0": 0, "B1": 1, "A1": 4}[workflow_id]
    projected_model_calls = len(rows) * calls_per_cycle
    if projected_model_calls > MAX_AGENT_MODEL_CALLS:
        maximum_cycles = MAX_AGENT_MODEL_CALLS // calls_per_cycle
        raise HistoricalReplayError(
            f"{workflow_id} would make {projected_model_calls} model calls. "
            f"The pilot limit is {MAX_AGENT_MODEL_CALLS}; select at most {maximum_cycles} trading sessions."
        )
    run_id = "replay-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    case_id = f"case-{portfolio_id.replace('_', '-')}-{start_date.isoformat()}-{end_date.isoformat()}"
    elapsed_ms = round((perf_counter() - started) * 1000, 2)
    completeness = 0.0 if len(rows) * len(positions) == 0 else 1 - missing_inputs / (len(rows) * len(positions))
    reference_cycles = _deterministic_reference_cycles(rows)
    reference_label_digest = canonical_digest(reference_cycles)
    active_episodes: dict[str, dict[str, Any]] = {}
    completed_episodes: list[dict[str, Any]] = []
    architecture_outputs: list[ArchitectureOutput] = []
    decision_branches: list[DecisionBranch] = []
    agent_cycle_receipts: list[dict[str, Any]] = []
    processing_receipts: list[ReplayProcessingReceipt] = []
    prior_rule_ids: set[str] = set()
    prior_severity = 0
    for cycle_index, row in enumerate(rows, start=1):
        cycle_wall_started = datetime.now(timezone.utc)
        cycle_wall_timer = perf_counter()
        cycle_at = datetime.fromisoformat(row["data_available_at"]) if row.get("data_available_at") else datetime.combine(date.fromisoformat(row["date"]), time.max, tzinfo=timezone.utc)
        if cycle_at.tzinfo is None:
            cycle_at = cycle_at.replace(tzinfo=timezone.utc)
        else:
            cycle_at = cycle_at.astimezone(timezone.utc)
        current_rule_ids = {item["rule_id"] for item in row["warnings"]}
        for rule_id in tuple(active_episodes):
            if rule_id not in current_rule_ids:
                episode = active_episodes.pop(rule_id)
                episode["state"] = "resolved"
                completed_episodes.append(episode)
        cycle_findings: list[ArchitectureFinding] = []
        for warning in row["warnings"]:
            rule_id = warning["rule_id"]
            episode = active_episodes.get(rule_id)
            if episode is None:
                episode = {
                    "episode_id": f"episode-{rule_id}-{cycle_index:04d}",
                    "risk_type": RULE_RISK_TYPES[rule_id],
                    "rule_id": rule_id,
                    "first_detected_at": cycle_at,
                    "last_detected_at": cycle_at,
                    "observation_count": 0,
                    "maximum_severity": 0,
                    "maximum_threshold_distance": 0.0,
                    "state": "open",
                    "evidence_ids": set(),
                }
                active_episodes[rule_id] = episode
            severity = 3 if warning["level"] == "urgent" else 2
            threshold_distance = float(warning["threshold_distance"])
            episode["last_detected_at"] = cycle_at
            episode["observation_count"] += 1
            episode["maximum_severity"] = max(episode["maximum_severity"], severity)
            episode["maximum_threshold_distance"] = max(episode["maximum_threshold_distance"], threshold_distance)
            episode["evidence_ids"].update(warning["evidence_ids"])
            cycle_findings.append(ArchitectureFinding(
                finding_id=f"finding-{row['date']}-{rule_id}",
                episode_id=episode["episode_id"],
                risk_type=RULE_RISK_TYPES[rule_id],
                affected_asset=portfolio_id,
                direction="negative",
                materiality=min(1.0, threshold_distance),
                severity=severity,
                evidence_ids=tuple(warning["evidence_ids"]),
                metric_id=warning["metric"].replace("_", "-"),
                observed_value=warning["observed_value"],
                threshold_value=warning["threshold"],
                observed_at=cycle_at,
            ))
        highest_severity = max((item.severity for item in cycle_findings), default=0)
        assessable_rules = sum(item["status"] != "unable_to_assess" for item in row["rule_results"])
        calculation_confidence = completeness * assessable_rules / max(len(row["rule_results"]), 1)
        if cycle_index == 1:
            change = "initial"
        elif current_rule_ids == prior_rule_ids and highest_severity == prior_severity:
            change = "unchanged"
        elif highest_severity > prior_severity or current_rule_ids - prior_rule_ids:
            change = "deteriorated"
        elif highest_severity < prior_severity or prior_rule_ids - current_rule_ids:
            change = "improved"
        else:
            change = "mixed"
        cycle_id = f"cycle-{row['date']}"
        decision_id = f"decision-{row['date']}"
        selected_branch_id = f"branch-{row['date']}-selected"
        counterfactual_branch_id = f"branch-{row['date']}-counterfactual"
        monitoring_action = "urgent_human_review" if highest_severity == 3 else "increase_monitoring" if cycle_findings else "continue_monitoring"
        portfolio_action = "review_exposure" if cycle_findings else "none"
        horizon_end = cycle_at + timedelta(days=20)
        if workflow_id == RULES_WORKFLOW_ID:
            decision_branches.extend((
                DecisionBranch(branch_id=selected_branch_id, decision_id=decision_id, action="review_exposure" if cycle_findings else "continue_monitoring", created_at=cycle_at, outcome_horizon_end=horizon_end),
                DecisionBranch(branch_id=counterfactual_branch_id, decision_id=decision_id, action="continue_monitoring" if cycle_findings else "increase_monitoring", created_at=cycle_at, outcome_horizon_end=horizon_end),
            ))
            architecture_outputs.append(ArchitectureOutput(
            output_id=f"output-{run_id.lower()}-{row['date']}",
            run_id=run_id,
            architecture_type="deterministic",
            cycle_id=cycle_id,
            as_of=cycle_at,
            assessment_state="alert" if cycle_findings else "clear",
            severity=highest_severity,
            confidence=round(calculation_confidence, 6),
            confidence_method="Deterministic calculation confidence from input completeness and rule assessability; not a probability of risk materialisation.",
            findings=tuple(cycle_findings),
            supporting_evidence_ids=tuple(sorted({evidence for item in cycle_findings for evidence in item.evidence_ids})),
            risk_interpretation=(
                f"At {row['date']}, {len(cycle_findings)} mandate condition(s) were breached. "
                f"The classified context contained {row['ravenpack_events']['high_relevance']} high-relevance event(s), "
                f"including {row['ravenpack_events']['high_relevance_negative']} negative event(s), and current fundamentals for "
                f"{row['classified_context']['fundamentals']['companies_covered']} of {len(positions)} holdings. "
                "The fixed-rule baseline reports these facts without inferring causality."
            ),
            expectations="No market forecast is produced; the decision branches are retained for later outcome and regret evaluation.",
            decision=ArchitectureDecision(
                decision_id=decision_id,
                monitoring_action=monitoring_action,
                portfolio_action=portfolio_action,
                alternatives_considered=("continue_monitoring", "increase_monitoring", "review_exposure"),
                human_review_required=bool(cycle_findings),
                rationale_finding_ids=tuple(item.finding_id for item in cycle_findings),
                branch_id=selected_branch_id,
                counterfactual_branch_ids=(counterfactual_branch_id,),
            ),
            missing_information=("independently reviewed outcome labels", "branch outcomes at the evaluation horizon"),
            assumptions=("Accepted quantities and USD cash remain fixed throughout the historical counterfactual.",),
            architecture_id=ARCHITECTURE_ID,
            capabilities_used=("capability:risk:historical-replay.deterministic@1.0.0", "classifier:event:provider-relevance-baseline@1.0.0", "classifier:fundamental-state-baseline@1.0.0"),
            change_since_previous=change,
            classified_context_ids=(row["classified_context"]["context_id"], row["classified_context"]["fundamentals"]["context_id"]),
            ))
            cycle_wall_completed = datetime.now(timezone.utc)
            cycle_processing_ms = round((perf_counter() - cycle_wall_timer) * 1000, 3)
            processing_receipts.append(ReplayProcessingReceipt(
                receipt_id=f"processing-{run_id.lower()}-{cycle_index:04d}",
                trigger_id=f"trigger-{run_id.lower()}-{cycle_index:04d}",
                trigger_kind="scheduled_cycle",
                replay_triggered_at=cycle_at,
                replay_paused_at=cycle_at,
                replay_resumed_at=cycle_at,
                wall_started_at=cycle_wall_started,
                wall_completed_at=cycle_wall_completed,
                processing_wall_ms=cycle_processing_ms,
                output_id=architecture_outputs[-1].output_id,
                capability_calls=3,
                model_calls=0,
                capability_processing_ms=cycle_processing_ms,
                model_processing_ms=0.0,
                validation_processing_ms=0.0,
                input_tokens=0,
                cached_input_tokens=0,
                output_tokens=0,
                estimated_cost_usd=0.0,
                pricing_reference="no_model_calls",
                metadata={
                    "event_timing": {
                        "event_count": len(row["ravenpack_events"].get("event_stream", ())),
                        "ordered_by": "information_available_at",
                        "analysis_triggered_at": cycle_at.isoformat(),
                    },
                    "execution_timing": {
                        "price_policy": "first eligible end-of-day close after information availability",
                        "intraday_alpha_decay": "not_identifiable_from_daily_prices",
                    },
                    "measurement_scope": "deterministic cycle interpretation, rule evaluation and ArchitectureOutput construction",
                },
            ))
            execution_close = cycle_at.replace(hour=21, minute=0, second=0, microsecond=0)
            if execution_close < cycle_at:
                execution_close += timedelta(days=1)
                while execution_close.weekday() >= 5:
                    execution_close += timedelta(days=1)
            for event_record in row["ravenpack_events"].get("event_stream", ()):
                available = datetime.fromisoformat(event_record["information_available_at"])
                if available.tzinfo is None:
                    available = available.replace(tzinfo=timezone.utc)
                available = available.astimezone(timezone.utc)
                event_record.update({
                    "analysis_triggered_at": cycle_at.isoformat(),
                    "analysis_output_at": cycle_at.isoformat(),
                    "analysis_wall_started_at": cycle_wall_started.isoformat(),
                    "analysis_wall_completed_at": cycle_wall_completed.isoformat(),
                    "analysis_processing_ms": cycle_processing_ms,
                    "queued_before_analysis_ms": max(0.0, (cycle_at - available).total_seconds() * 1000),
                    "replay_clock_blocked": True,
                    "earliest_end_of_day_execution_at": execution_close.isoformat(),
                    "execution_price_policy": "first_eligible_end_of_day_close",
                })
        else:
            trigger_at = cycle_at
            if row["ravenpack_events"].get("first_available_at"):
                trigger_at = datetime.fromisoformat(row["ravenpack_events"]["first_available_at"])
                if trigger_at.tzinfo is None:
                    trigger_at = trigger_at.replace(tzinfo=timezone.utc)
            try:
                mapped, receipt = execute_agent_cycle(
                    workflow_id=workflow_id,
                    run_id=run_id,
                    case_id=case_id,
                    portfolio_id=portfolio_id,
                    row=row,
                    holdings=tuple(row["position_values"]),
                    cycle_at=cycle_at,
                    trigger_available_at=trigger_at,
                    previous_assessment_state=None if not architecture_outputs else architecture_outputs[-1].assessment_state,
                    previous_severity=None if not architecture_outputs else architecture_outputs[-1].severity,
                )
            except ValueError as error:
                raise HistoricalReplayError(str(error)) from error
            architecture_outputs.append(mapped)
            agent_cycle_receipts.append({"cycle_id": cycle_id, **receipt})
            processing_clock = receipt["processing_clock"]
            processing_receipts.append(ReplayProcessingReceipt(
                receipt_id=f"processing-{run_id.lower()}-{cycle_index:04d}",
                trigger_id=f"trigger-{run_id.lower()}-{cycle_index:04d}",
                trigger_kind="scheduled_cycle",
                replay_triggered_at=cycle_at,
                replay_paused_at=cycle_at,
                replay_resumed_at=cycle_at,
                wall_started_at=datetime.fromisoformat(processing_clock["wall_started_at"]),
                wall_completed_at=datetime.fromisoformat(processing_clock["wall_completed_at"]),
                processing_wall_ms=processing_clock["processing_wall_ms"],
                output_id=mapped.output_id,
                capability_calls=1,
                model_calls=receipt["model_calls"],
                capability_processing_ms=processing_clock["context_and_capability_processing_ms"],
                model_processing_ms=processing_clock["model_processing_ms"],
                validation_processing_ms=processing_clock["validation_and_mapping_ms"],
                input_tokens=receipt["input_tokens"],
                cached_input_tokens=0,
                output_tokens=receipt["output_tokens"],
                estimated_cost_usd=receipt["estimated_cost_usd"],
                pricing_reference=receipt["pricing_reference"],
                metadata={
                    "event_timing": receipt["event_timing"],
                    "execution_timing": receipt["execution_timing"],
                },
            ))
            for event_record in row["ravenpack_events"].get("event_stream", ()):
                available = datetime.fromisoformat(event_record["information_available_at"])
                if available.tzinfo is None:
                    available = available.replace(tzinfo=timezone.utc)
                available = available.astimezone(timezone.utc)
                event_record.update({
                    "analysis_triggered_at": cycle_at.isoformat(),
                    "analysis_output_at": cycle_at.isoformat(),
                    "analysis_wall_started_at": receipt["processing_clock"]["wall_started_at"],
                    "analysis_wall_completed_at": receipt["processing_clock"]["wall_completed_at"],
                    "analysis_processing_ms": receipt["processing_clock"]["processing_wall_ms"],
                    "queued_before_analysis_ms": max(0.0, (cycle_at - available).total_seconds() * 1000),
                    "replay_clock_blocked": True,
                    "earliest_end_of_day_execution_at": receipt["execution_timing"]["earliest_execution_at"],
                    "execution_price_policy": receipt["execution_timing"]["price_policy"],
                })
            mapped_decision = mapped.decision
            decision_branches.extend((
                DecisionBranch(
                    branch_id=mapped_decision.branch_id,
                    decision_id=mapped_decision.decision_id,
                    action=mapped_decision.portfolio_action if mapped_decision.portfolio_action != "none" else mapped_decision.monitoring_action,
                    created_at=mapped.produced_at or cycle_at,
                    outcome_horizon_end=horizon_end,
                ),
                DecisionBranch(
                    branch_id=mapped_decision.counterfactual_branch_ids[0],
                    decision_id=mapped_decision.decision_id,
                    action="continue_monitoring",
                    created_at=mapped.produced_at or cycle_at,
                    outcome_horizon_end=horizon_end,
                ),
            ))
        prior_rule_ids = current_rule_ids
        prior_severity = highest_severity
    completed_episodes.extend(active_episodes.values())
    finding_episodes = tuple(FindingEpisode(**{
        **item,
        "maximum_threshold_distance": round(item["maximum_threshold_distance"], 6),
        "evidence_ids": tuple(sorted(item["evidence_ids"])),
    }) for item in completed_episodes)
    if not architecture_outputs:
        raise HistoricalReplayError("the selected period produced no workflow cycles")
    completed_at = datetime.now(timezone.utc)
    elapsed_ms = (completed_at - started_at).total_seconds() * 1000
    architecture_output = architecture_outputs[-1]
    evaluation_dimensions = _evaluate_architecture_outputs(
        tuple(architecture_outputs), finding_episodes,
        position_observation_completeness=completeness,
        wall_clock_ms=elapsed_ms,
        query_receipts=tuple(query_receipts),
        repetitions=1,
        label_state="admitted",
        capability_configs=PRECONFIGURED_CAPABILITIES,
        reference_cycles=reference_cycles,
        processing_receipts=tuple(processing_receipts),
    )
    regimes = _regime_labels(rows)
    observations = _observation_ledger(
        rows,
        start_date=start_date,
        mandate_reference=mandate["reference"],
        mandate_rules=mandate["rules"],
    )
    study = StudyDefinition(
        study_id=study_id,
        title=study_title,
        research_programme="Compare deterministic, single-agent and agent-graph portfolio-risk monitoring across cases, information regimes and market regimes.",
    )
    experiment = ResearchExperimentDefinition(
        experiment_id=experiment_id,
        study_id=study_id,
        research_question=research_question,
        hypothesis=hypothesis,
        controlled_factors=tuple(sorted(("data-revision", "mandate-version", "portfolio-quantities", "temporal-policy"))),
        variable_factors=("architecture",),
        evaluation_dimensions=tuple(sorted(item["id"] for item in evaluation_dimensions)),
    )
    input_observation_ids = ("input-compustat", "input-crsp", "input-mandate", "input-portfolio", "input-ravenpack")
    case = ExperimentalCase(
        case_id=case_id,
        experiment_id=experiment_id,
        observable_state=ObservableCaseState(
            portfolio_reference=f"portfolio:portfolio-risk.research:{portfolio_id}@2026-08-11",
            mandate_reference=mandate["reference"],
            risk_policy_reference=mandate["risk_policy"]["reference"],
            data_references=(
                f"dataset:crsp-compustat:{config['dataset_snapshot_id']}",
                "dataset:compustat-quarterly",
                "dataset:crsp-daily",
                "dataset:ravenpack-events",
            ),
            observation_ids=input_observation_ids,
            as_of=datetime.combine(end_date, time.max, tzinfo=timezone.utc),
        ),
        evaluation_state=CaseEvaluationState(
            evaluation_horizon_end=datetime.combine(end_date + timedelta(days=20), time.max, tzinfo=timezone.utc),
            label_state="admitted",
            regimes=regimes,
        ),
    )
    dimension_records = tuple(
        EvaluationDimensionRecord(
            dimension_id=item["id"], status=item["status"], score=item["score"],
            summary=item["summary"], metric_values=item["metrics"],
        )
        for item in evaluation_dimensions
    )
    evaluation_record = EvaluationRecord(
        evaluation_id=f"evaluation-{run_id.lower()}",
        run_id=run_id,
        evaluator="deterministic_evaluator",
        evaluated_output_id=architecture_output.output_id,
        label_state="admitted",
        dimensions=dimension_records,
        created_at=completed_at,
        evaluator_version="3.0.0",
        evaluated_output_ids=tuple(item.output_id for item in architecture_outputs),
        metric_specification_ids=tuple(item.metric_id for item in METRIC_SPECIFICATIONS),
        label_set_digest=reference_label_digest,
    )
    run_record = ExperimentalRun(
        run_id=run_id,
        study_id=study_id,
        experiment_id=experiment_id,
        case_id=case_id,
        regime_labels=regimes,
        run_input=RunInput(
            case_id=case_id,
            architecture_id=ARCHITECTURE_ID if workflow_id == "B0" else AGENT_ARCHITECTURE_IDS[workflow_id],
            information_regime="licensed-market-fundamentals-events",
            capability_references=tuple(item.capability_id for item in PRECONFIGURED_CAPABILITIES),
            capability_configurations=PRECONFIGURED_CAPABILITIES,
            repetition=repetition,
            observation_ids=input_observation_ids,
        ),
        architecture_config=ArchitectureConfig(
            architecture_id=ARCHITECTURE_ID if workflow_id == "B0" else AGENT_ARCHITECTURE_IDS[workflow_id],
            architecture_type={"B0": "deterministic", "B1": "single_agent", "A1": "agent_graph"}[workflow_id],
            version="1.0.0",
            deterministic=workflow_id == "B0",
            model_reference=None if workflow_id == "B0" else AGENT_MODEL_ID,
            interpretation_mode=ARCHITECTURE_EXECUTION_PROFILES[{"B0": "deterministic", "B1": "single_agent", "A1": "agent_graph"}[workflow_id]]["interpretation_mode"],
            context_contract_version="2.0.0",
        ),
        architecture_output=architecture_output,
        run_trace=RunTraceRecord(
            started_at=started_at,
            completed_at=completed_at,
            wall_clock_ms=elapsed_ms,
            model_calls=sum(item["model_calls"] for item in agent_cycle_receipts),
            tool_calls=3,
        ),
        runtime_observations=observations,
        evaluation_record=evaluation_record,
        metric_specifications=METRIC_SPECIFICATIONS,
        architecture_outputs=tuple(architecture_outputs),
        finding_episodes=finding_episodes,
        decision_branches=tuple(decision_branches),
        processing_receipts=tuple(processing_receipts),
        agent_output_ids=tuple(item.source_output_id for item in architecture_outputs if item.source_output_id),
        architecture_output_ids=tuple(item.output_id for item in architecture_outputs),
    )
    programme_classification = RunClassification(
        study_id=study_id,
        experiment_id=experiment_id,
        fixture_context_digest=canonical_digest({
            "portfolio_mandate": {
                "portfolio": case.observable_state.portfolio_reference,
                "mandate": case.observable_state.mandate_reference,
                "risk_policy": case.observable_state.risk_policy_reference,
            },
            "data": case.observable_state.data_references,
            "information_regime": run_record.run_input.information_regime,
            "capability_environment": [item.model_dump(mode="json") for item in PRECONFIGURED_CAPABILITIES],
            "scenario": "scenario:historical-replay@1.0.0",
            "evaluation": evaluation_id,
        }),
        case_id=case_id,
        baseline_id=workflow_id.lower(),
        architecture_reference=run_record.architecture_config.architecture_id,
        portfolio_mandate_reference=(
            f"{case.observable_state.portfolio_reference} | "
            f"{case.observable_state.mandate_reference}"
        ),
        information_regime_reference=(
            "information-regime:licensed-market-fundamentals-events@1.0.0"
        ),
        scenario_reference="scenario:historical-replay@1.0.0",
        evaluation_reference=f"evaluation:{evaluation_id}@1.0.0",
        repetition=repetition,
        market_regime_labels=tuple(sorted(
            f"{item.dimension}:{item.value}" for item in regimes
        )),
        run_id=run_id,
    )
    resource_days: dict[str, dict[str, Any]] = {}
    for item in processing_receipts:
        replay_day = item.replay_triggered_at.date().isoformat()
        daily = resource_days.setdefault(replay_day, {
            "replay_date": replay_day,
            "processing_wall_ms": 0.0,
            "capability_calls": 0,
            "model_calls": 0,
            "input_tokens": 0,
            "cached_input_tokens": 0,
            "output_tokens": 0,
            "estimated_cost_usd": 0.0,
            "cost_status": "priced",
        })
        daily["processing_wall_ms"] += item.processing_wall_ms
        daily["capability_calls"] += item.capability_calls
        daily["model_calls"] += item.model_calls
        daily["input_tokens"] += item.input_tokens
        daily["cached_input_tokens"] += item.cached_input_tokens
        daily["output_tokens"] += item.output_tokens
        if item.estimated_cost_usd is None:
            daily["estimated_cost_usd"] = None
            daily["cost_status"] = "unpriced"
        elif daily["estimated_cost_usd"] is not None:
            daily["estimated_cost_usd"] += item.estimated_cost_usd
    for daily in resource_days.values():
        daily["processing_wall_ms"] = round(daily["processing_wall_ms"], 3)
        if daily["estimated_cost_usd"] is not None:
            daily["estimated_cost_usd"] = round(daily["estimated_cost_usd"], 8)
    total_cost = (
        None if any(item.estimated_cost_usd is None for item in processing_receipts)
        else round(sum(item.estimated_cost_usd or 0.0 for item in processing_receipts), 8)
    )
    resource_usage = {
        "processing_wall_ms": round(sum(item.processing_wall_ms for item in processing_receipts), 3),
        "capability_calls": sum(item.capability_calls for item in processing_receipts),
        "model_calls": sum(item.model_calls for item in processing_receipts),
        "input_tokens": sum(item.input_tokens for item in processing_receipts),
        "cached_input_tokens": sum(item.cached_input_tokens for item in processing_receipts),
        "output_tokens": sum(item.output_tokens for item in processing_receipts),
        "estimated_cost_usd": total_cost,
        "cost_status": "unpriced" if total_cost is None else "priced",
        "by_replay_date": [resource_days[key] for key in sorted(resource_days)],
    }
    diagnostics = _build_run_diagnostics(
        workflow_id=workflow_id,
        evaluation_dimensions=evaluation_dimensions,
        outputs=tuple(architecture_outputs),
        missing_position_observations=missing_inputs,
        missing_position_names=tuple(sorted({
            item["company_name"]
            for row in rows
            for item in row.get("position_observations_missing", ())
        })),
    )
    return {
        "run_id": run_id,
        "status": "completed",
        "workflow": {
            "id": workflow_id,
            "type": {"B0": "Rules", "B1": "Agent", "A1": "Graph"}[workflow_id],
            "model_calls": sum(item["model_calls"] for item in agent_cycle_receipts),
            "model": None if workflow_id == "B0" else AGENT_MODEL_ID,
            "interpretation_mode": ARCHITECTURE_EXECUTION_PROFILES[{"B0": "deterministic", "B1": "single_agent", "A1": "agent_graph"}[workflow_id]]["interpretation_mode"],
            "rules_are_fixed": workflow_id == "B0",
            "cycle_outputs": len(architecture_outputs),
            "call_budget": MAX_AGENT_MODEL_CALLS,
            "prompt_manifest_digest": (
                None if workflow_id == "B0" else prompt_manifest_digest()
            ),
            "cycle_receipts": agent_cycle_receipts,
        },
        "execution_regime": {
            "id": "compressed_replay_v1",
            "processing_time_policy": "real_wall_clock_with_replay_time_blocked",
            "idle_time_policy": "accelerated_between_triggers",
            "maximum_model_calls": MAX_AGENT_MODEL_CALLS,
            "maximum_output_tokens_per_call": 2400,
            "model_timeout_seconds": 90,
            "cost_policy": "retain_tokens_and_cost_when_a_reviewed_pricing_snapshot_matches; otherwise cost_is_null",
            "continuous_operations_comparator": "parked_for_later_real_time_apparatus",
            "resource_usage": resource_usage,
        },
        "hierarchy": {
            "study": study.model_dump(mode="json"),
            "experiment": experiment.model_dump(mode="json"),
            "case": case.model_dump(mode="json"),
            "run": {"run_id": run_id, "repetition": repetition},
            "regimes": [item.model_dump(mode="json") for item in regimes],
        },
        "run_record": run_record.model_dump(mode="json"),
        "programme_classification": {
            **programme_classification.model_dump(mode="json"),
            "cell_key": programme_classification.cell_key,
        },
        "diagnostics": diagnostics,
        "portfolio": {
            "id": portfolio_id,
            "definition_date": "2026-08-11",
            "identity_basis": "current company names resolved from the licensed security master",
            "quantity_basis": "quantities carried forward from the accepted real-data portfolio selection",
            "holdings": [
                {"company_name": security_context.get(item.permno, {}).get("company_name", item.alias), "ticker": security_context.get(item.permno, {}).get("ticker", "—"), "sector": security_context.get(item.permno, {}).get("sector", "Unclassified"), "quantity": str(item.quantity)}
                for item in positions
            ],
            "instrument_lifetime_metrics": instrument_lifetime_summaries,
        },
        "data_revision": {
            "snapshot_id": config["dataset_snapshot_id"],
            "snapshot_receipt_sha256": config["dataset_receipt_sha256"],
            "portfolio_receipt_sha256": config["portfolio_receipt_sha256"],
            "access": "licensed_read_only",
        },
        "mandate": mandate,
        "period": {"start": start_date.isoformat(), "end": end_date.isoformat()},
        "evaluation": {
            "id": evaluation_id,
            "reference_treatment": {
                "scope": "deterministic_mandate_breaches",
                "label_state": "admitted",
                "label_set_digest": reference_label_digest,
                "cycles": len(reference_cycles),
                "positive_findings": sum(len(item["findings"]) for item in reference_cycles),
                "limitation": "This reference scores mandate-rule preservation and response, not unlabelled event relevance or future market outcomes. Because the same deterministic calculations are supplied to B1 and A1, these scores verify apparatus integrity and do not by themselves demonstrate agent superiority.",
            },
            "trading_days": len(rows),
            "warnings": warnings,
            "missing_position_observations": missing_inputs,
            "workflow_failures": 0,
            "ravenpack_events": sum(item["ravenpack_events"]["count"] for item in rows),
            "high_relevance_events": sum(item["ravenpack_events"]["high_relevance"] for item in rows),
            "compustat_companies_available": int(fundamentals[0] or 0),
            "latest_compustat_available_date": fundamentals[1].isoformat() if fundamentals[1] else None,
            "volatility_observations_required": minimum_volatility_observations,
            "metric_history_start": history_start.isoformat(),
            "metric_specifications": [item.model_dump(mode="json") for item in METRIC_SPECIFICATIONS],
            "finding_episodes": [item.model_dump(mode="json") for item in finding_episodes],
            "decision_branches": len(decision_branches),
            "query_receipts": query_receipts,
            "capability_configurations": [item.model_dump(mode="json") for item in PRECONFIGURED_CAPABILITIES],
            "capability_policy": {
                "preconfigured": "Parameters are frozen before the run and shared across architectures.",
                "adaptive": "Parameters are selected during execution by an admitted agent or graph; unavailable to B0.",
                "B0_boundary": "Deterministic B0 rejects adaptive and generative capabilities.",
            },
            "end_of_day_execution_effect": {
                "status": "structurally_defined_not_yet_scored",
                "tradable_price": "first eligible end-of-day close after the event becomes available",
                "intraday_alpha_decay": "not_identifiable_from_daily_prices",
                "measurable_with_current_data": "post-execution close-to-close signal persistence and branch regret",
                "required_capability": "capability:evaluation:daily-close-alpha-persistence@1.0.0",
                "interpretation": (
                    "Daily prices cannot reveal how much information value decayed between the event and the close. "
                    "The experiment therefore records the waiting interval, executes only at the first eligible close, "
                    "and leaves exact intraday alpha decay unscored until an admitted intraday market-data source exists."
                ),
            },
            "interpretation": "Mandate-rule detection and response are scored against the frozen deterministic reference. Predictive event accuracy, probability calibration, robustness and financial regret require separate admitted labels or matured outcomes.",
            "dimensions": evaluation_dimensions,
            "rule_summary": [
                {"rule_id": rule["rule_id"], "label": rule["label"], "clause": rule["clause"], **rule_counts[rule["rule_id"]]}
                for rule in mandate["rules"]
            ],
        },
        "clock": rows,
        "methodology_note": (
            "Accepted quantities were retained and company names were refreshed from the current licensed security master. "
            "Those fixed holdings were applied to earlier dates. Treat this run as an apparatus test, "
            "not as thesis evidence until the portfolio construction rule is fixed before the test period."
        ),
    }


def professor_demo_definition() -> dict[str, Any]:
    """Load the versioned, private-neutral Professor Demo definition."""

    if not PROFESSOR_DEMO_CONFIG.is_file():
        raise HistoricalReplayError("Professor Demo v0.1 configuration is unavailable")
    value = yaml.safe_load(PROFESSOR_DEMO_CONFIG.read_text(encoding="utf-8"))
    if value.get("schema_version") != "portfolio-risk.professor-demo/v1":
        raise HistoricalReplayError("Professor Demo v0.1 has an unsupported schema")
    return value


def professor_demo_preflight(private_root: Path) -> dict[str, Any]:
    """Qualify the exact demo Case without saving a Run or calling a model.

    This workflow deliberately executes B0 once because B0 is the deterministic
    reference implementation of the same metrics and mandate checks used by the
    treatments.  It is a preflight observation, not a retained research result.
    """

    definition = professor_demo_definition()
    case_definition = definition["case"]
    expected = definition["expected_preflight"]
    setup = setup_payload(private_root, [])
    portfolio = next(
        (
            item for item in setup["portfolio_mandates"]
            if item["id"] == case_definition["portfolio_id"]
        ),
        None,
    )
    if portfolio is None:
        raise HistoricalReplayError("the Professor Demo portfolio is unavailable")

    start_date = date.fromisoformat(case_definition["start_date"])
    end_date = date.fromisoformat(case_definition["end_date"])
    audit = run_replay(
        private_root,
        workflow_id="B0",
        portfolio_id=case_definition["portfolio_id"],
        start_date=start_date,
        end_date=end_date,
        evaluation_id=definition["evaluation_id"],
        study_id=definition["study"]["study_id"],
        experiment_id=definition["experiment"]["experiment_id"],
        study_title=definition["study"]["title"],
        research_question=definition["experiment"]["research_question"],
        hypothesis=definition["experiment"]["hypothesis"],
    )
    row = audit["clock"][0]
    final_output = audit["run_record"]["architecture_output"]
    evaluation = audit["evaluation"]
    data_revision = audit["data_revision"]
    configured_capabilities = {
        item.capability_id for item in PRECONFIGURED_CAPABILITIES
    }
    required_capabilities = set(definition["capabilities"])
    portfolio_count = len(portfolio["holdings"])
    price_coverage = (
        0.0 if portfolio_count == 0
        else row["positions_observed"] / portfolio_count
    )
    fundamental_coverage = (
        0.0 if portfolio_count == 0
        else evaluation["compustat_companies_available"] / portfolio_count
    )
    material_findings = len(final_output["findings"])
    absolute_daily_return = abs(float(row["daily_return"] or 0.0))

    database = _database(private_root)
    with duckdb.connect(str(database), read_only=True) as connection:
        catalog_snapshot = connection.execute(
            "SELECT snapshot_id FROM catalogue_snapshot_metadata LIMIT 1"
        ).fetchone()[0]
        ravenpack = connection.execute(
            """
            SELECT inventory_signature, admission_ready, readiness
            FROM ravenpack_integration_status
            WHERE provider_id = 'ravenpack'
            """
        ).fetchone()

    checks: list[dict[str, Any]] = []

    def add_check(
        check_id: str,
        label: str,
        passed: bool,
        observed: str,
        *,
        required: bool = True,
        limitation: str | None = None,
    ) -> None:
        checks.append({
            "check_id": check_id,
            "label": label,
            "status": "pass" if passed else "fail" if required else "warning",
            "required": required,
            "observed": observed,
            "limitation": limitation,
        })

    add_check(
        "data-revision",
        "The licensed data revision matches the frozen demo",
        catalog_snapshot == definition["data"]["snapshot_id"]
        and data_revision["snapshot_receipt_sha256"]
        == definition["data"]["snapshot_receipt_sha256"],
        f"{catalog_snapshot} · read only",
    )
    add_check(
        "ravenpack-revision",
        "The RavenPack inventory is admitted and unchanged",
        bool(ravenpack)
        and ravenpack[0] == definition["data"]["ravenpack_inventory_signature"]
        and bool(ravenpack[1]),
        "Unavailable" if not ravenpack else f"{ravenpack[2]} · {ravenpack[0]}",
    )
    add_check(
        "portfolio-binding",
        "The selected portfolio is bound to the intended mandate",
        portfolio["mandate"]["object_id"] == case_definition["mandate_id"]
        and portfolio_count == int(expected["position_count"]),
        f"{portfolio_count} named holdings · {portfolio['mandate']['name']}",
    )
    add_check(
        "market-coverage",
        "Every holding has an eligible valuation",
        price_coverage >= float(expected["minimum_price_coverage"]),
        f"{row['positions_observed']}/{portfolio_count} holdings ({price_coverage:.0%})",
    )
    add_check(
        "fundamental-coverage",
        "Every holding has point-in-time fundamentals",
        fundamental_coverage >= float(expected["minimum_fundamental_coverage"]),
        f"{evaluation['compustat_companies_available']}/{portfolio_count} holdings ({fundamental_coverage:.0%})",
    )
    add_check(
        "event-context",
        "The date contains eligible portfolio events",
        evaluation["ravenpack_events"]
        >= int(expected["minimum_eligible_event_records"]),
        f"{evaluation['ravenpack_events']} records · {len(row['ravenpack_events'].get('event_stream', []))} event clusters",
    )
    add_check(
        "capability-environment",
        "Every demo capability is versioned and configured",
        required_capabilities.issubset(configured_capabilities),
        f"{len(required_capabilities & configured_capabilities)}/{len(required_capabilities)} capabilities",
    )
    add_check(
        "architecture-environment",
        "B0, B1 and A1 are runnable on the same Case",
        set(definition["architectures"]).issubset(
            {item["id"] for item in setup["workflows"] if item["runnable"]}
        ),
        "B0 deterministic · B1 single agent · A1 specialist graph",
    )
    add_check(
        "nontrivial-case",
        "The Case contains a material risk question",
        material_findings >= int(expected["minimum_material_findings"])
        and absolute_daily_return >= float(expected["minimum_absolute_daily_return"]),
        f"{material_findings} mandate findings · {absolute_daily_return:.1%} absolute daily return",
    )
    add_check(
        "historical-construction",
        "The portfolio was formed before the historical observation date",
        False,
        "Quantities were approved in 2026 and retrojected to 2016",
        required=False,
        limitation=case_definition["selection_limitation"],
    )
    add_check(
        "independent-outcomes",
        "Independent event and future-outcome labels are available",
        False,
        "Mandate-rule reference labels only",
        required=False,
        limitation=(
            "This demo validates execution, mapping and presentation. It cannot "
            "establish predictive accuracy, calibration, robustness or financial regret."
        ),
    )

    required_failures = [
        item for item in checks if item["required"] and item["status"] == "fail"
    ]
    manifest = {
        "schema_version": definition["schema_version"],
        "demo_id": definition["demo_id"],
        "study": definition["study"],
        "experiment": definition["experiment"],
        "case": definition["case"],
        "data": definition["data"],
        "architectures": definition["architectures"],
        "evaluation_id": definition["evaluation_id"],
        "capabilities": definition["capabilities"],
        "seed": definition["seed"],
        "effects": [],
    }
    manifest["manifest_digest"] = canonical_digest(manifest)

    immediate_capabilities = [
        {
            "capability_id": item.capability_id,
            "version": item.version,
            "implementation_class": item.implementation_class,
            "role": (
                "Input and calculation"
                if "architecture_input" in item.evaluation_roles
                else "Evaluation measurement"
            ),
            "status": "ready",
        }
        for item in PRECONFIGURED_CAPABILITIES
    ]
    deferred_capabilities = [
        {
            **item,
            "status": "deferred_scientific_dependency",
            "needed_for_demo": False,
        }
        for item in EVALUATION_CAPABILITY_REQUIREMENTS
        if item["status"] != "ready"
    ]
    return {
        "schema_version": "portfolio-risk.professor-demo-preflight/v1",
        "status": "ready_with_limitations" if not required_failures else "blocked",
        "demo_ready": not required_failures,
        "thesis_ready": False,
        "manifest": manifest,
        "checks": checks,
        "case_preview": {
            "display_name": case_definition["display_name"],
            "source_portfolio_id": case_definition["portfolio_id"],
            "date": case_definition["start_date"],
            "mandate": portfolio["mandate"]["name"],
            "mandate_objective": portfolio["mandate"]["objective"],
            "holdings": portfolio["holdings"],
            "data_truth": "Licensed CRSP, Compustat and RavenPack · read only",
            "selection_policy": case_definition["selection_policy"],
            "selection_limitation": case_definition["selection_limitation"],
        },
        "interesting_evidence": {
            "daily_return": row["daily_return"],
            "annualised_volatility": row["annualised_volatility"],
            "drawdown": row["drawdown"],
            "cash_weight": row["cash_weight"],
            "largest_issuer_weight": row["largest_issuer_weight"],
            "eligible_event_records": evaluation["ravenpack_events"],
            "event_clusters": len(row["ravenpack_events"].get("event_stream", [])),
            "material_findings": material_findings,
            "maximum_severity": final_output["severity"],
            "assessment_state": final_output["assessment_state"],
            "finding_types": sorted({
                item["risk_type"] for item in final_output["findings"]
            }),
        },
        "architectures": [
            {
                "id": "B0",
                "name": "Deterministic reference",
                "strength": "Transparent, repeatable policy and metric baseline.",
                "limitation": "Cannot add semantic interpretation beyond programmed rules.",
                "model_calls": 0,
            },
            {
                "id": "B1",
                "name": "Single structured agent",
                "strength": "One bounded synthesis step with the lowest generative cost.",
                "limitation": "One agent must combine all evidence and can still omit useful connections.",
                "model_calls": 1,
            },
            {
                "id": "A1",
                "name": "Specialist-agent graph",
                "strength": "Separates market, event, exposure and synthesis work.",
                "limitation": "Higher token, latency and coordination overhead; richer structure does not guarantee a better decision.",
                "model_calls": 4,
            },
        ],
        "capabilities": {
            "ready": immediate_capabilities,
            "deferred": deferred_capabilities,
            "conclusion": (
                "The Case has every capability required for a fair apparatus comparison. "
                "Deferred capabilities depend on independent labels, perturbations or matured outcomes and must not be simulated for the meeting."
            ),
        },
        "preflight_run": {
            "saved": False,
            "model_calls": 0,
            "purpose": "Deterministic validation only; not a retained research Run.",
        },
    }
