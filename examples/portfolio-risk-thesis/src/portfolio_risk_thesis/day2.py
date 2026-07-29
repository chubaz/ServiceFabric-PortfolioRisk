"""Deterministic, local-only Thesis Day 2 metrics and decision kernel."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import duckdb
import yaml
from pydantic import ValidationError

from risk_analytics import AnalysisEvidence, AnalysisHorizon
from risk_capabilities import (
    CapabilityRegistry,
    DerivedReturnsRequest,
    HistoricalTailRiskRequest,
    ReturnsRequest,
    VolatilityRequest,
)
from risk_data import load_licensed_manifest, verify_crsp_compustat
from risk_domain import MarketObservation, QualityFlag, SourceReference

from .contracts import (
    DataReadiness,
    Day2ExperimentManifest,
    DeterministicFinding,
    KernelDecisionPoint,
    MetricValue,
    MorningMetricPack,
    PortfolioMaterializationReceipt,
    ReviewItem,
    canonical_record_digest,
)
from .manifests import load_portfolio, load_yaml, sha256_file
from .portfolio.materialization import (
    INSTRUMENT_MAP_NAME,
    RECEIPT_NAME,
    validate_materialized_real_portfolios,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
METRIC_FILE = "morning-metric-packs.json"
FINDING_FILE = "deterministic-findings.json"
DECISION_FILE = "kernel-decisions.json"
EVIDENCE_FILE = "evidence-manifest.json"


class Day2ExperimentError(ValueError):
    """The reviewed experiment or its private immutable evidence is invalid."""


def _external_path(value: Path | str, label: str, *, must_exist: bool) -> Path:
    path = Path(value)
    if not path.is_absolute():
        raise Day2ExperimentError(f"{label} must be an absolute path")
    resolved = path.resolve(strict=must_exist)
    if resolved == REPOSITORY_ROOT or REPOSITORY_ROOT in resolved.parents:
        raise Day2ExperimentError(f"{label} must remain outside Git")
    configured = os.environ.get("THESIS_DATA_ROOT")
    if not configured:
        raise Day2ExperimentError("THESIS_DATA_ROOT must be configured")
    root = Path(configured)
    if not root.is_absolute():
        raise Day2ExperimentError("THESIS_DATA_ROOT must be absolute")
    root = root.resolve(strict=False)
    if resolved != root and root not in resolved.parents:
        raise Day2ExperimentError(f"{label} must be beneath THESIS_DATA_ROOT")
    return resolved


def _json_bytes(value: object) -> bytes:
    return (
        json.dumps(value, indent=2, sort_keys=True, default=str) + "\n"
    ).encode("utf-8")


def _digest_bytes(value: bytes) -> str:
    return f"sha256:{hashlib.sha256(value).hexdigest()}"


def _identifier(prefix: str, value: object) -> str:
    digest = canonical_record_digest({"value": value}).removeprefix("sha256:")
    return f"{prefix}_{digest[:24]}"


def _write_immutable_directory(target: Path, files: dict[str, bytes]) -> None:
    if target.exists():
        actual = {item.name for item in target.iterdir() if item.is_file()}
        if actual == set(files) and all(
            (target / name).read_bytes() == payload
            for name, payload in files.items()
        ):
            return
        raise Day2ExperimentError(
            "immutable Day 2 output already exists with different content"
        )
    target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    staging = Path(tempfile.mkdtemp(prefix=f".{target.name}.", dir=target.parent))
    try:
        os.chmod(staging, 0o700)
        for name, payload in files.items():
            descriptor = os.open(
                staging / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600
            )
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(payload)
        staging.rename(target)
    finally:
        if staging.exists():
            shutil.rmtree(staging)


def load_day2_experiment(path: Path | str) -> Day2ExperimentManifest:
    manifest_path = _external_path(path, "experiment manifest", must_exist=True)
    try:
        manifest = Day2ExperimentManifest.model_validate(load_yaml(manifest_path))
    except (KeyError, ValidationError, ValueError) as error:
        raise Day2ExperimentError(f"invalid Day 2 experiment: {error}") from error
    _external_path(manifest.source_manifest.path, "source manifest", must_exist=True)
    _external_path(manifest.data_root, "data root", must_exist=True)
    _external_path(
        manifest.portfolios_directory, "portfolios directory", must_exist=True
    )
    return manifest


def prepare_day2_experiment(
    *,
    source_manifest_path: Path | str,
    data_root: Path | str,
    portfolios_directory: Path | str,
    experiment_manifest_path: Path | str,
    reviewer_id: str | None = None,
    reviewed_at: datetime | None = None,
    as_of: datetime | None = None,
) -> Path:
    """Bind already reviewed sources and portfolios; never choose investments."""

    source_path = _external_path(
        source_manifest_path, "source manifest", must_exist=True
    )
    root = _external_path(data_root, "data root", must_exist=True)
    portfolios = _external_path(
        portfolios_directory, "portfolios directory", must_exist=True
    )
    target = _external_path(
        experiment_manifest_path, "experiment manifest", must_exist=False
    )
    load_licensed_manifest(source_path)
    dataset_receipt = verify_crsp_compustat(root)
    if "crsp_daily" not in dataset_receipt.source_digests:
        raise Day2ExperimentError("Day 2 requires a daily-primary dataset")
    portfolio_receipt = validate_materialized_real_portfolios(
        portfolios_directory=portfolios,
        receipt_path=portfolios / RECEIPT_NAME,
    )
    reviewer_id = reviewer_id or portfolio_receipt.reviewer_id
    reviewed_at = reviewed_at or portfolio_receipt.reviewed_at
    as_of = as_of or portfolio_receipt.as_of
    dataset_receipt_path = (
        root
        / "manifests"
        / dataset_receipt.snapshot_id
        / "dataset-admission-receipt.json"
    )
    document = Day2ExperimentManifest(
        experiment_id="portfolio-risk-architecture-comparison-v1-day2",
        reviewed=True,
        reviewer_id=reviewer_id,
        reviewed_at=reviewed_at,
        as_of=as_of,
        dataset_mode="daily_primary",
        source_manifest={
            "path": source_path,
            "sha256": sha256_file(source_path),
        },
        data_root=root,
        dataset_snapshot_id=dataset_receipt.snapshot_id,
        dataset_receipt_sha256=sha256_file(dataset_receipt_path),
        portfolios_directory=portfolios,
        portfolio_receipt_sha256=sha256_file(portfolios / RECEIPT_NAME),
        thresholds={
            "review_daily_loss": "0.03",
            "urgent_daily_loss": "0.07",
            "review_annualized_volatility": "0.30",
            "urgent_annualized_volatility": "0.50",
            "review_maximum_drawdown": "0.15",
            "urgent_maximum_drawdown": "0.25",
        },
    )
    if target.exists():
        raise Day2ExperimentError("reviewed experiment manifest already exists")
    target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    target.write_text(
        yaml.safe_dump(document.model_dump(mode="json"), sort_keys=False),
        encoding="utf-8",
    )
    os.chmod(target, 0o600)
    return target


def validate_day2_experiment(
    path: Path | str,
) -> tuple[Day2ExperimentManifest, PortfolioMaterializationReceipt, Path]:
    manifest = load_day2_experiment(path)
    if sha256_file(manifest.source_manifest.path) != manifest.source_manifest.sha256:
        raise Day2ExperimentError("source manifest digest mismatch")
    load_licensed_manifest(manifest.source_manifest.path)
    dataset_receipt = verify_crsp_compustat(
        manifest.data_root, manifest.dataset_snapshot_id
    )
    if "crsp_daily" not in dataset_receipt.source_digests:
        raise Day2ExperimentError("selected dataset is not daily-primary")
    receipt_path = (
        manifest.data_root
        / "manifests"
        / dataset_receipt.snapshot_id
        / "dataset-admission-receipt.json"
    )
    if sha256_file(receipt_path) != manifest.dataset_receipt_sha256:
        raise Day2ExperimentError("dataset receipt digest mismatch")
    quality_path = (
        manifest.data_root
        / "quality"
        / dataset_receipt.snapshot_id
        / "join-quality.json"
    )
    quality = json.loads(quality_path.read_text(encoding="utf-8"))
    if quality.get("blocked") or int(quality.get("ambiguous_market_dates", 0)):
        raise Day2ExperimentError("ambiguous CCM link remains")
    portfolio_receipt_path = manifest.portfolios_directory / RECEIPT_NAME
    if sha256_file(portfolio_receipt_path) != manifest.portfolio_receipt_sha256:
        raise Day2ExperimentError("portfolio receipt digest mismatch")
    portfolio_receipt = validate_materialized_real_portfolios(
        portfolios_directory=manifest.portfolios_directory,
        receipt_path=portfolio_receipt_path,
    )
    catalogue = (
        manifest.data_root
        / "catalog"
        / "snapshots"
        / dataset_receipt.snapshot_id
        / "crsp-compustat.duckdb"
    )
    bindings, portfolios = _load_private_bindings(
        manifest.portfolios_directory
    )
    with duckdb.connect(str(catalogue), read_only=True) as connection:
        connection.execute("SET enable_progress_bar = false")
        for portfolio in portfolios:
            _portfolio_prices(
                connection,
                portfolio=portfolio,
                bindings=bindings,
                as_of=manifest.as_of,
                required_returns=max(
                    manifest.lookback_returns,
                    manifest.minimum_daily_observations,
                ),
            )
    return manifest, portfolio_receipt, catalogue


def _load_private_bindings(
    portfolios_directory: Path,
) -> tuple[dict[str, int], tuple[Any, ...]]:
    value = json.loads(
        (portfolios_directory / INSTRUMENT_MAP_NAME).read_text(encoding="utf-8")
    )
    bindings = {
        item["instrument_alias"]: int(item["permno"])
        for item in value["instruments"]
    }
    portfolio_names = sorted(
        path
        for path in portfolios_directory.glob("*.yaml")
        if path.is_file()
    )
    portfolios = tuple(load_portfolio(path) for path in portfolio_names)
    if not portfolios:
        raise Day2ExperimentError("no reviewed portfolio definitions are present")
    return bindings, portfolios


def _portfolio_prices(
    connection: duckdb.DuckDBPyConnection,
    *,
    portfolio: Any,
    bindings: dict[str, int],
    as_of: datetime,
    required_returns: int,
) -> tuple[tuple[datetime, Decimal], ...]:
    permnos = [bindings[position.instrument_id] for position in portfolio.positions]
    placeholders = ",".join("?" for _ in permnos)
    rows = connection.execute(
        f"""
        SELECT permno, CAST(observed_at AS VARCHAR), valuation_price
        FROM crsp_daily
        WHERE permno IN ({placeholders}) AND available_at <= ?
        ORDER BY permno, observed_at
        """,
        [*permnos, as_of],
    ).fetchall()
    by_permno: dict[int, dict[datetime, Decimal]] = {item: {} for item in permnos}
    latest: dict[int, object] = {}
    for permno, observed_at, price in rows:
        observed = datetime.fromisoformat(
            str(observed_at).replace("Z", "+00:00")
        ).astimezone(UTC)
        latest[int(permno)] = price
        if price is not None:
            by_permno[int(permno)][observed] = Decimal(str(price))
    if set(latest) != set(permnos) or any(item is None for item in latest.values()):
        raise Day2ExperimentError(
            f"required latest prices are unavailable for portfolio {portfolio.portfolio_id}"
        )
    common_dates = sorted(set.intersection(*(set(item) for item in by_permno.values())))
    required_prices = required_returns + 1
    if len(common_dates) < required_prices:
        raise Day2ExperimentError(
            f"portfolio {portfolio.portfolio_id} has fewer than "
            f"{required_returns} eligible daily observations"
        )
    selected_dates = common_dates[-required_prices:]
    quantity_by_permno = {
        bindings[position.instrument_id]: position.quantity
        for position in portfolio.positions
    }
    cash = sum((item.amount for item in portfolio.cash), Decimal("0"))
    return tuple(
        (
            observed_at,
            cash
            + sum(
                (
                    quantity_by_permno[permno]
                    * by_permno[permno][observed_at]
                    for permno in permnos
                ),
                Decimal("0"),
            ),
        )
        for observed_at in selected_dates
    )


def _invoke(registry: CapabilityRegistry, capability: str, request: object) -> Any:
    result = registry.invoke(capability, request)
    if result.status != "succeeded" or result.data is None or result.effects:
        raise Day2ExperimentError(f"canonical capability failed: {capability}")
    return result.data


def _metric_pack(
    *,
    manifest: Day2ExperimentManifest,
    portfolio: Any,
    portfolio_receipt: PortfolioMaterializationReceipt,
    prices: tuple[tuple[datetime, Decimal], ...],
    registry: CapabilityRegistry,
) -> MorningMetricPack:
    evidence_digest = manifest.dataset_receipt_sha256
    evidence = (
        AnalysisEvidence(
            evidence_id=f"dataset:{manifest.dataset_snapshot_id}",
            reference=f"private-snapshot:{manifest.dataset_snapshot_id}",
            digest=evidence_digest,
            description="Verified private daily-primary dataset receipt.",
        ),
    )
    source = SourceReference(
        source_id="licensed-crsp-daily",
        source_type="licensed_local",
        reference=f"snapshot:{manifest.dataset_snapshot_id}",
        retrieved_at=manifest.as_of,
    )
    observations = tuple(
        MarketObservation(
            instrument_id=f"portfolio-{portfolio.portfolio_id}",
            observed_at=observed_at,
            price=value,
            currency=portfolio.base_currency,
            synthetic=False,
            quality_flags=(QualityFlag.COMPLETE,),
            sources=(source,),
        )
        for observed_at, value in prices
    )
    horizon = AnalysisHorizon(
        label=f"{manifest.lookback_returns}-daily-return-lookback",
        periods=manifest.lookback_returns,
        expected_interval_seconds=None,
    )
    assumptions = (
        "Portfolio quantities and cash remain fixed for the reviewed lookback.",
        "Portfolio value is fixed cash plus quantity multiplied by valuation price.",
        "Only observations with available_at less than or equal to as_of are eligible.",
    )
    limitations = (
        "Licensed local research evidence; not investment advice.",
        "No event source is configured for this experiment.",
        "No network, broker, order, trade, rebalance or portfolio mutation effect.",
    )
    identity = {
        "experiment_id": manifest.experiment_id,
        "portfolio_id": portfolio.portfolio_id,
        "snapshot_id": manifest.dataset_snapshot_id,
        "as_of": manifest.as_of,
        "prices": prices,
    }
    analysis_root = _identifier("analysis", identity)
    returns = _invoke(
        registry,
        "risk.returns.simple",
        ReturnsRequest(
            analysis_id=f"{analysis_root}-returns",
            snapshot_id=f"portfolio-series-{portfolio.portfolio_id}",
            prices=observations,
            horizon=horizon,
            evidence=evidence,
            assumptions=assumptions,
            limitations=limitations,
        ),
    )
    volatility = _invoke(
        registry,
        "risk.volatility.annualized",
        VolatilityRequest(
            analysis_id=f"{analysis_root}-volatility",
            returns=returns,
            evidence=evidence,
            periods_per_year=252,
            assumptions=assumptions,
            limitations=limitations,
        ),
    )
    drawdown = _invoke(
        registry,
        "risk.drawdown.maximum",
        DerivedReturnsRequest(
            analysis_id=f"{analysis_root}-drawdown",
            returns=returns,
            evidence=evidence,
            assumptions=assumptions,
            limitations=limitations,
        ),
    )
    tail = _invoke(
        registry,
        "risk.var.historical",
        HistoricalTailRiskRequest(
            analysis_id=f"{analysis_root}-tail",
            returns=returns,
            evidence=evidence,
            confidence_level=manifest.confidence_level,
            assumptions=assumptions,
            limitations=limitations,
        ),
    )
    warnings = ("event_source_not_configured",)
    readiness = DataReadiness(
        state="QUALIFIED",
        observation_count=len(returns.observations),
        required_observation_count=manifest.minimum_daily_observations,
        warnings=warnings,
        limitations=limitations,
    )
    metrics = (
        MetricValue(
            metric_id="daily_return",
            value=returns.observations[-1].value,
            unit="ratio",
            observation_count=1,
        ),
        MetricValue(
            metric_id="annualized_volatility",
            value=volatility.annualized_volatility,
            unit="ratio",
            observation_count=volatility.observation_count,
        ),
        MetricValue(
            metric_id="maximum_drawdown",
            value=drawdown.maximum_drawdown,
            unit="ratio",
            observation_count=drawdown.observation_count,
        ),
        MetricValue(
            metric_id="historical_var_95",
            value=tail.value_at_risk,
            unit="ratio",
            observation_count=tail.observation_count,
        ),
        MetricValue(
            metric_id="historical_expected_shortfall_95",
            value=tail.expected_shortfall,
            unit="ratio",
            observation_count=tail.observation_count,
        ),
    )
    body: dict[str, object] = {
        "experiment_id": manifest.experiment_id,
        "portfolio_id": portfolio.portfolio_id,
        "source_snapshot_id": manifest.dataset_snapshot_id,
        "portfolio_receipt_id": portfolio_receipt.receipt_id,
        "as_of": manifest.as_of,
        "readiness": readiness.model_dump(mode="python"),
        "metrics": tuple(item.model_dump(mode="python") for item in metrics),
        "evidence": (
            f"dataset-receipt:{manifest.dataset_receipt_sha256}",
            f"portfolio-receipt:{manifest.portfolio_receipt_sha256}",
        ),
        "assumptions": assumptions,
        "warnings": warnings,
        "limitations": limitations,
        "effects": (),
    }
    digest = canonical_record_digest(body)
    return MorningMetricPack(
        metric_pack_id=f"metric_pack_{digest.removeprefix('sha256:')[:24]}",
        output_digest=digest,
        **body,
    )


def deterministic_decision(
    pack: MorningMetricPack,
    manifest: Day2ExperimentManifest,
) -> tuple[DeterministicFinding, ReviewItem, KernelDecisionPoint]:
    metrics = {item.metric_id: item.value for item in pack.metrics}
    triggered: list[str] = []
    if pack.readiness.state == "BLOCKED" or any(value is None for value in metrics.values()):
        outcome = "ABSTAIN"
        materiality = "undefined"
        priority = "blocked"
    else:
        daily_loss = -metrics["daily_return"]  # type: ignore[operator]
        volatility = metrics["annualized_volatility"]
        drawdown = metrics["maximum_drawdown"]
        urgent = (
            daily_loss >= manifest.thresholds.urgent_daily_loss
            or volatility >= manifest.thresholds.urgent_annualized_volatility  # type: ignore[operator]
            or drawdown >= manifest.thresholds.urgent_maximum_drawdown  # type: ignore[operator]
        )
        review = (
            daily_loss >= manifest.thresholds.review_daily_loss
            or volatility >= manifest.thresholds.review_annualized_volatility  # type: ignore[operator]
            or drawdown >= manifest.thresholds.review_maximum_drawdown  # type: ignore[operator]
        )
        checks = (
            ("daily_return", daily_loss, manifest.thresholds.review_daily_loss),
            (
                "annualized_volatility",
                volatility,
                manifest.thresholds.review_annualized_volatility,
            ),
            (
                "maximum_drawdown",
                drawdown,
                manifest.thresholds.review_maximum_drawdown,
            ),
        )
        triggered = [name for name, value, threshold in checks if value >= threshold]  # type: ignore[operator]
        if urgent:
            outcome, materiality, priority = "URGENT_REVIEW", "urgent", "urgent"
        elif review:
            outcome, materiality, priority = "REVIEW", "review", "review"
        else:
            outcome, materiality, priority = "NO_ISSUE", "none", "none"
    finding_body = {
        "portfolio_id": pack.portfolio_id,
        "outcome": outcome,
        "materiality": materiality,
        "triggered_metrics": tuple(sorted(triggered)),
        "evidence": (pack.output_digest,),
        "warnings": pack.warnings,
    }
    finding = DeterministicFinding(
        finding_id=_identifier("finding", finding_body), **finding_body
    )
    review_body = {
        "portfolio_id": pack.portfolio_id,
        "priority": priority,
        "human_review_required": True,
        "summary": (
            f"Deterministic kernel outcome {outcome}; no action or recommendation "
            "is generated."
        ),
        "finding_id": finding.finding_id,
    }
    review_item = ReviewItem(
        review_item_id=_identifier("review_item", review_body), **review_body
    )
    decision_body = {
        "portfolio_id": pack.portfolio_id,
        "decision": outcome,
        "finding_id": finding.finding_id,
        "review_item_id": review_item.review_item_id,
        "deterministic": True,
        "human_review_required": True,
        "effects": (),
    }
    decision = KernelDecisionPoint(
        decision_id=_identifier("kernel_decision", decision_body),
        **decision_body,
    )
    return finding, review_item, decision


def run_day2_experiment(
    *,
    experiment_manifest_path: Path | str,
    output_root: Path | str,
) -> Path:
    manifest, portfolio_receipt, catalogue = validate_day2_experiment(
        experiment_manifest_path
    )
    output = _external_path(output_root, "Day 2 output root", must_exist=False)
    bindings, portfolios = _load_private_bindings(manifest.portfolios_directory)
    registry = CapabilityRegistry()
    packs: list[MorningMetricPack] = []
    findings: list[DeterministicFinding] = []
    review_items: list[ReviewItem] = []
    decisions: list[KernelDecisionPoint] = []
    with duckdb.connect(str(catalogue), read_only=True) as connection:
        connection.execute("SET enable_progress_bar = false")
        for portfolio in portfolios:
            prices = _portfolio_prices(
                connection,
                portfolio=portfolio,
                bindings=bindings,
                as_of=manifest.as_of,
                required_returns=max(
                    manifest.lookback_returns,
                    manifest.minimum_daily_observations,
                ),
            )
            pack = _metric_pack(
                manifest=manifest,
                portfolio=portfolio,
                portfolio_receipt=portfolio_receipt,
                prices=prices,
                registry=registry,
            )
            finding, review_item, decision = deterministic_decision(pack, manifest)
            packs.append(pack)
            findings.append(finding)
            review_items.append(review_item)
            decisions.append(decision)
    run_identity = canonical_record_digest(
        {
            "manifest": manifest.model_dump(mode="python"),
            "metric_digests": tuple(item.output_digest for item in packs),
        }
    ).removeprefix("sha256:")[:24]
    target = output / f"day2_{run_identity}"
    files = {
        METRIC_FILE: _json_bytes([item.model_dump(mode="json") for item in packs]),
        FINDING_FILE: _json_bytes(
            {
                "findings": [item.model_dump(mode="json") for item in findings],
                "review_items": [
                    item.model_dump(mode="json") for item in review_items
                ],
            }
        ),
        DECISION_FILE: _json_bytes(
            [item.model_dump(mode="json") for item in decisions]
        ),
    }
    files[EVIDENCE_FILE] = _json_bytes(
        {
            "experiment_id": manifest.experiment_id,
            "run_id": f"day2_{run_identity}",
            "source_snapshot_id": manifest.dataset_snapshot_id,
            "portfolio_receipt_id": portfolio_receipt.receipt_id,
            "artifacts": {
                name: _digest_bytes(payload)
                for name, payload in sorted(files.items())
            },
            "effects": [],
            "limitations": [
                "Private licensed research evidence; not investment advice.",
                "No LLM, provider call, broker action, trade or portfolio mutation.",
            ],
        }
    )
    _write_immutable_directory(target, files)
    return target
