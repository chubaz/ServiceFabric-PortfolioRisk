"""Manifest-driven, resumable Day 4 historical evaluation runner."""

from __future__ import annotations

import csv
import io
import json
import math
import os
import shutil
import tempfile
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Callable, Mapping

import pyarrow as pa
import pyarrow.parquet as pq

from portfolio_risk_thesis.contracts import Day2ExperimentManifest
from portfolio_risk_thesis.day2 import (
    Day2AsOfEvaluation,
    evaluate_day2_portfolio_series,
    evaluate_validated_day2_portfolio_as_of,
    validate_day2_experiment,
)
from portfolio_risk_thesis.day3.contracts import (
    ArchitectureInputBundle,
    ArchitectureRun,
    PositionExposure,
    bytes_digest,
    canonical,
    digest,
)
from portfolio_risk_thesis.day3.events import read_events
from portfolio_risk_thesis.day3.providers.fixture import (
    FixtureStructuredModelProvider,
)
from portfolio_risk_thesis.day3.providers.openai_responses import (
    OpenAIResponsesProvider,
)
from portfolio_risk_thesis.day3.treatments import a1, b0, b1
from portfolio_risk_thesis.portfolio import load_portfolios

from .contracts import (
    ARCHITECTURES,
    AUTHORIZED_MODEL_CALLS,
    ArchitectureObservation,
    Day4ExperimentManifest,
    Day4RunManifest,
    Day4Task,
    Day4TaskReceipt,
    PortfolioDayKey,
    PortfolioDayResult,
)
from .evaluation import (
    classify_observation,
    evaluate_architectures,
    evaluate_repeatability,
)
from .manifest import (
    build_execution_plan,
    load_day4_manifest,
    sha256_file,
    sha256_tree,
    validate_authorized_model_calls,
    validate_input_bindings,
)
from .report import write_day4_reports


REPOSITORY_ROOT = Path(__file__).resolve().parents[5]
MARKET_FIXTURE = REPOSITORY_ROOT / "data/fixtures/synthetic/thesis-day1/market.parquet"
PORTFOLIO_FIXTURES = REPOSITORY_ROOT / "examples/portfolio-risk-thesis/portfolios"
PROVIDER_FAILURE_WARNINGS = {"provider_error", "invalid_structured_output"}


def _json_bytes(value: object) -> bytes:
    return (
        json.dumps(canonical(value), indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def _secure_write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if path.exists():
        if path.read_bytes() == payload:
            return
        raise ValueError(f"immutable Day 4 artifact differs: {path}")
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(payload)


def _external_root(path: Path | str) -> Path:
    value = Path(path)
    if not value.is_absolute():
        raise ValueError("Day 4 output root must be an explicit absolute path")
    resolved = value.resolve(strict=False)
    configured_value = os.environ.get("THESIS_DATA_ROOT")
    if not configured_value:
        raise ValueError("THESIS_DATA_ROOT must be configured")
    configured = Path(configured_value)
    if not configured.is_absolute():
        raise ValueError("THESIS_DATA_ROOT must be absolute")
    configured = configured.resolve(strict=False)
    if configured == REPOSITORY_ROOT or REPOSITORY_ROOT in configured.parents:
        raise ValueError("THESIS_DATA_ROOT must remain outside Git")
    if resolved != configured and configured not in resolved.parents:
        raise ValueError("Day 4 output root must be beneath THESIS_DATA_ROOT")
    return resolved


def _bundle(evaluation: Day2AsOfEvaluation, events: tuple[object, ...]) -> ArchitectureInputBundle:
    pack = evaluation.metric_pack
    metrics = {item.metric_id: item.value for item in pack.metrics}
    if any(value is None for value in metrics.values()):
        raise ValueError("Day 4 requires defined Day 2 metrics")
    evidence = tuple(sorted(set(pack.evidence) | set(evaluation.finding.evidence)))
    aliases = {alias for alias, _ in evaluation.position_weights}
    eligible = tuple(
        event
        for event in events
        if event.available_at <= pack.as_of
        and set(event.instrument_aliases).issubset(aliases)
    )
    return ArchitectureInputBundle(
        portfolio_id=pack.portfolio_id,
        as_of=pack.as_of,
        metrics=metrics,
        deterministic_finding=evaluation.finding.outcome,
        review_item=evaluation.review_item.summary,
        decision_point=evaluation.decision.decision,
        exposures=tuple(
            PositionExposure(
                position_alias=alias,
                weight=weight,
                evidence_refs=(pack.output_digest,),
            )
            for alias, weight in evaluation.position_weights
        ),
        events=eligible,
        evidence_refs=evidence,
        warnings=tuple(sorted(set(pack.warnings) | set(evaluation.finding.warnings))),
        limitations=pack.limitations,
    )


def _synthetic_day2_manifest(as_of: datetime) -> Day2ExperimentManifest:
    market_digest = sha256_file(MARKET_FIXTURE)
    return Day2ExperimentManifest(
        experiment_id="portfolio-risk-day4-synthetic-fixture",
        reviewed=True,
        reviewer_id="synthetic-fixture-reviewer",
        reviewed_at=datetime(2026, 7, 30, tzinfo=UTC),
        as_of=as_of,
        dataset_mode="daily_primary",
        source_manifest={"path": MARKET_FIXTURE, "sha256": market_digest},
        data_root=REPOSITORY_ROOT,
        dataset_snapshot_id="synthetic-thesis-day1",
        dataset_receipt_sha256=market_digest,
        portfolios_directory=PORTFOLIO_FIXTURES,
        portfolio_receipt_sha256=market_digest,
        thresholds={
            "review_daily_loss": "0.03",
            "urgent_daily_loss": "0.07",
            "review_annualized_volatility": "0.30",
            "urgent_annualized_volatility": "0.50",
            "review_maximum_drawdown": "0.15",
            "urgent_maximum_drawdown": "0.25",
        },
    )


def _synthetic_contexts(
    manifest: Day4ExperimentManifest,
) -> tuple[
    dict[str, ArchitectureInputBundle],
    dict[str, Day2AsOfEvaluation],
    Callable[[], dict[object, object]],
]:
    rows = pq.read_table(MARKET_FIXTURE).to_pylist()
    by_instrument: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in rows:
        by_instrument[str(row["instrument_id"])].append(row)
    portfolios = {item.portfolio_id: item for item in load_portfolios(PORTFOLIO_FIXTURES)}
    contexts: dict[str, ArchitectureInputBundle] = {}
    evaluations: dict[str, Day2AsOfEvaluation] = {}
    for key in manifest.portfolio_day_keys():
        portfolio = portfolios[key.portfolio_id]
        available = {
            position.instrument_id: {
                row["timestamp"]: Decimal(str(row["adjusted_close"]))
                for row in by_instrument[position.instrument_id]
                if row["available_at"] <= key.as_of
                and row["adjusted_close"] is not None
            }
            for position in portfolio.positions
        }
        common_dates = sorted(
            set.intersection(*(set(values) for values in available.values()))
        )
        selected = common_dates[-61:]
        if len(selected) != 61:
            raise ValueError("synthetic Day 4 context lacks the 60-return lookback")
        cash = sum((item.amount for item in portfolio.cash), Decimal("0"))
        nav = tuple(
            (
                timestamp,
                cash
                + sum(
                    position.quantity
                    * available[position.instrument_id][timestamp]
                    for position in portfolio.positions
                ),
            )
            for timestamp in selected
        )
        nav = nav[:-1] + ((key.as_of, nav[-1][1]),)
        current_prices = {
            position.instrument_id: available[position.instrument_id][selected[-1]]
            for position in portfolio.positions
        }
        current_nav = nav[-1][1]
        weights = tuple(
            sorted(
                (
                    position.instrument_id,
                    position.quantity * current_prices[position.instrument_id] / current_nav,
                )
                for position in portfolio.positions
            )
        )
        evaluation = evaluate_day2_portfolio_series(
            manifest=_synthetic_day2_manifest(key.as_of),
            portfolio=portfolio,
            portfolio_receipt_id="synthetic-day4-portfolio-receipt",
            nav_history=nav,
            position_weights=weights,
        )
        evaluations[key.key_digest] = evaluation
        contexts[key.key_digest] = _bundle(evaluation, ())

    bindings = validate_input_bindings(
        manifest,
        REPOSITORY_ROOT / "examples/portfolio-risk-thesis/experiments/day4_fixture.yaml",
    )

    def future_outcomes() -> dict[object, object]:
        rows = pq.read_table(bindings["coverage_profile"].parent / "labels.parquet").to_pylist()
        outcomes: dict[object, object] = {}
        for row in rows:
            key = next(
                item
                for item in manifest.portfolio_day_keys()
                if item.portfolio_id == row["portfolio_id"]
                and item.window_id == row["window_id"]
                and item.as_of == row["as_of"]
            )
            outcomes[key.key_digest] = row
        return outcomes

    return contexts, evaluations, future_outcomes


def _real_contexts(
    manifest: Day4ExperimentManifest,
    manifest_path: Path,
) -> tuple[
    dict[str, ArchitectureInputBundle],
    dict[str, Day2AsOfEvaluation],
    Callable[[], dict[object, object]],
]:
    bindings = validate_input_bindings(manifest, manifest_path)
    base, receipt, catalogue = validate_day2_experiment(
        bindings["day2_experiment_manifest"]
    )
    reviewed_events = read_events(bindings["day3_event_dataset"])
    contexts: dict[str, ArchitectureInputBundle] = {}
    evaluations: dict[str, Day2AsOfEvaluation] = {}
    for key in manifest.portfolio_day_keys():
        evaluation = evaluate_validated_day2_portfolio_as_of(
            manifest=base,
            portfolio_receipt=receipt,
            catalogue=catalogue,
            portfolio_id=key.portfolio_id,
            as_of=key.as_of,
        )
        evaluations[key.key_digest] = evaluation
        contexts[key.key_digest] = _bundle(evaluation, reviewed_events)

    def future_outcomes() -> dict[object, object]:
        outcomes: dict[object, object] = {}
        for key in manifest.portfolio_day_keys():
            future = evaluate_validated_day2_portfolio_as_of(
                manifest=base,
                portfolio_receipt=receipt,
                catalogue=catalogue,
                portfolio_id=key.portfolio_id,
                as_of=key.as_of + timedelta(days=21),
            )
            future_nav = [
                (timestamp, nav)
                for timestamp, nav in future.nav_history
                if timestamp > key.as_of
            ][:5]
            if len(future_nav) != 5:
                raise ValueError(
                    f"five future business sessions unavailable for {key.key_digest}"
                )
            start = evaluations[key.key_digest].nav_history[-1][1]
            navs = [start, *(value for _, value in future_nav)]
            returns = [
                navs[index] / navs[index - 1] - Decimal("1")
                for index in range(1, len(navs))
            ]
            mean = sum(returns) / Decimal(len(returns))
            variance = sum((value - mean) ** 2 for value in returns) / Decimal(
                max(1, len(returns) - 1)
            )
            volatility = Decimal(str(math.sqrt(float(variance)) * math.sqrt(252)))
            drawdown = min(value / start - Decimal("1") for value in navs)
            realized_at = future_nav[-1][0]
            evidence_ref = digest(
                {
                    "key": key.key_digest,
                    "realized_at": realized_at,
                    "navs": navs,
                }
            )
            outcomes[key.key_digest] = {
                "future_business_sessions": 5,
                "portfolio_drawdown": drawdown,
                "realized_volatility": volatility,
                "worst_position_loss": None,
                "material_event": False,
                "realized_at": realized_at,
                "evidence_refs": (evidence_ref,),
            }
        return outcomes

    return contexts, evaluations, future_outcomes


def build_contexts(
    manifest: Day4ExperimentManifest,
    manifest_path: Path,
) -> tuple[
    dict[str, ArchitectureInputBundle],
    dict[str, Day2AsOfEvaluation],
    Callable[[], dict[object, object]],
]:
    """Build authoritative point-in-time contexts without importing labels."""

    if manifest.profile == "synthetic_fixture":
        return _synthetic_contexts(manifest)
    return _real_contexts(manifest, manifest_path)


def _fixture_output(
    architecture_id: str,
    role_id: str,
    bundle: ArchitectureInputBundle,
    key: PortfolioDayKey,
) -> dict[str, object]:
    final_role = role_id == "risk.agent.alert_recommendation"
    stress = key.window_id in {"stress_a", "stress_b"}
    control_first = key.window_id == "control" and key.as_of.day == 10
    control_abstain = key.window_id == "control" and key.as_of.day == 11
    final_alert = stress or (architecture_id == "B1" and control_first)
    status = "REVIEW" if final_alert and (architecture_id == "B1" or final_role) else "NO_ISSUE"
    affected: list[str] = []
    if status == "REVIEW":
        affected = [bundle.exposures[0].position_alias]
    if architecture_id == "B1" and control_abstain:
        status = "REVIEW"
        affected = ["unreviewed-position"]
    return {
        "architecture_id": architecture_id,
        "status": status,
        "severity": 2 if status == "REVIEW" else 0,
        "summary": "Synthetic fixture output for deterministic historical testing.",
        "affected_positions": affected,
        "metric_refs": [],
        "event_refs": [],
        "evidence_refs": list(bundle.evidence_refs) if status == "REVIEW" else [],
        "supporting_claims": [],
        "contradictory_claims": [],
        "uncertainties": ["Synthetic fixture only."],
        "recommended_next_steps": [
            "continue_monitoring" if status == "REVIEW" else "record_no_action"
        ],
        "human_review_required": True,
        "effects": [],
    }


def _fixture_provider(
    tasks: tuple[Day4Task, ...],
    contexts: Mapping[str, ArchitectureInputBundle],
) -> FixtureStructuredModelProvider:
    from portfolio_risk_thesis.day3.prompts import prompt_reference

    roles = {
        "B1": ("risk.agent.alert_recommendation",),
        "A1": (
            "risk.agent.market_data",
            "risk.agent.portfolio_exposure",
            "risk.agent.news_sentiment",
            "risk.agent.alert_recommendation",
        ),
    }
    prompt_ids = {
        ("B1", "risk.agent.alert_recommendation"): "b1-synthesizer",
        ("A1", "risk.agent.market_data"): "a1-market-data",
        ("A1", "risk.agent.portfolio_exposure"): "a1-portfolio-exposure",
        ("A1", "risk.agent.news_sentiment"): "a1-news-sentiment",
        ("A1", "risk.agent.alert_recommendation"): "a1-alert-synthesis",
    }
    responses: dict[tuple[str, str, str, str], dict[str, object]] = {}
    for task in tasks:
        if task.architecture_id == "B0":
            continue
        bundle = contexts[task.key.key_digest]
        for role_id in roles[task.architecture_id]:
            prompt = prompt_reference(prompt_ids[(task.architecture_id, role_id)])
            responses[
                (
                    task.architecture_id,
                    role_id,
                    prompt.digest,
                    bundle.context_digest,
                )
            ] = _fixture_output(
                task.architecture_id, role_id, bundle, task.key
            )
    return FixtureStructuredModelProvider(responses)


def _to_observation(task: Day4Task, run: ArchitectureRun) -> ArchitectureObservation:
    warnings = tuple(
        sorted(
            {
                warning
                for receipt in run.receipts
                for warning in receipt.warnings
            }
        )
    )
    provider_errors = sorted(PROVIDER_FAILURE_WARNINGS.intersection(warnings))
    violations = tuple(item.code for item in run.critic.violations)
    claims = run.output.supporting_claims + run.output.contradictory_claims
    unsupported = sum(code in {"evidence", "numeric_claim"} for code in violations)
    return ArchitectureObservation(
        task_id=task.task_id,
        key=task.key,
        architecture_id=task.architecture_id,
        repetition=task.repetition,
        context_digest=task.context_digest,
        semantic_output_digest=run.output.output_digest,
        status=run.output.status,
        severity=run.output.severity,
        critic_passed=run.critic.passed,
        critic_violations=violations,
        claim_count=max(len(claims), unsupported),
        unsupported_claim_count=unsupported,
        evidence_refs=run.output.evidence_refs,
        affected_positions=run.output.affected_positions,
        provider_receipts=run.receipts,
        latency_ms=sum(item.elapsed_ms for item in run.receipts),
        input_tokens=sum(item.input_tokens for item in run.receipts),
        output_tokens=sum(item.output_tokens for item in run.receipts),
        warnings=warnings,
        limitations=tuple(
            sorted(
                {
                    limitation
                    for receipt in run.receipts
                    for limitation in receipt.limitations
                }
            )
        ),
        execution_failure=bool(provider_errors),
        provider_error=":".join(provider_errors) if provider_errors else None,
    )


def _execute_task(task: Day4Task, bundle: ArchitectureInputBundle, provider: object) -> ArchitectureRun:
    if task.architecture_id == "B0":
        return b0(bundle)
    if task.architecture_id == "B1":
        return b1(bundle, provider)  # type: ignore[arg-type]
    return a1(bundle, provider)  # type: ignore[arg-type]


def _task_paths(run_root: Path, task: Day4Task) -> tuple[Path, Path]:
    directory = run_root / "raw-runs" / task.task_id.removeprefix("sha256:")
    return directory / "architecture-run.json", directory / "task-receipt.json"


def _load_or_execute(
    run_root: Path,
    task: Day4Task,
    bundle: ArchitectureInputBundle,
    provider: object,
    *,
    resume: bool,
) -> tuple[ArchitectureObservation, Day4TaskReceipt]:
    run_path, receipt_path = _task_paths(run_root, task)
    if run_path.exists() or receipt_path.exists():
        if not resume or not (run_path.is_file() and receipt_path.is_file()):
            raise ValueError(f"incomplete or non-resumable Day 4 task: {task.task_id}")
        payload = json.loads(run_path.read_text(encoding="utf-8"))
        if payload["task_id"] != task.task_id:
            raise ValueError("resumed task identity differs from the execution plan")
        observation = ArchitectureObservation.model_validate(payload["observation"])
        receipt = Day4TaskReceipt.model_validate_json(
            receipt_path.read_text(encoding="utf-8")
        )
        if receipt.state != "completed" or receipt.task_id != task.task_id:
            raise ValueError("only completed immutable tasks may be skipped")
        return observation, receipt

    attempted_at = task.key.as_of + timedelta(seconds=task.repetition)
    try:
        architecture_run = _execute_task(task, bundle, provider)
        observation = _to_observation(task, architecture_run)
        state = "failed" if observation.execution_failure else "completed"
        receipt = Day4TaskReceipt(
            task_id=task.task_id,
            state=state,
            attempted_at=attempted_at,
            completed_at=attempted_at,
            model_call_receipts=architecture_run.receipts,
            provider_error=observation.provider_error,
        )
        _secure_write(
            run_path,
            _json_bytes(
                {
                    "task_id": task.task_id,
                    "task": task,
                    "architecture_run": architecture_run,
                    "observation": observation,
                }
            ),
        )
        _secure_write(receipt_path, _json_bytes(receipt))
        if observation.execution_failure:
            raise ValueError(
                f"provider task failure; evidence preserved at {run_path.parent}"
            )
        return observation, receipt
    except Exception as error:
        if run_path.exists():
            raise
        receipt = Day4TaskReceipt(
            task_id=task.task_id,
            state="failed",
            attempted_at=attempted_at,
            completed_at=attempted_at,
            provider_error=type(error).__name__,
        )
        _secure_write(receipt_path, _json_bytes(receipt))
        raise ValueError(
            f"Day 4 task failed; evidence preserved at {receipt_path.parent}: "
            f"{type(error).__name__}"
        ) from error


def _parquet(path: Path, values: list[object]) -> None:
    rows = [{"payload_json": json.dumps(canonical(value), sort_keys=True)} for value in values]
    table = pa.Table.from_pylist(rows)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    descriptor, staging_name = tempfile.mkstemp(
        prefix=f".{path.name}.", dir=path.parent
    )
    os.close(descriptor)
    staging = Path(staging_name)
    try:
        pq.write_table(table, staging, compression="zstd")
        payload = staging.read_bytes()
        if path.exists():
            if path.read_bytes() != payload:
                raise ValueError(f"immutable Day 4 Parquet differs: {path}")
        else:
            staging.chmod(0o600)
            staging.rename(path)
    finally:
        if staging.exists():
            staging.unlink()


def _csv(path: Path, values: list[object]) -> None:
    rows = [canonical(value) for value in values]
    fields = sorted({key for row in rows for key in row})
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=fields)
    writer.writeheader()
    for row in rows:
        writer.writerow(
            {
                key: (
                    json.dumps(value, sort_keys=True)
                    if isinstance(value, (dict, list))
                    else value
                )
                for key, value in row.items()
            }
        )
    _secure_write(path, stream.getvalue().encode("utf-8"))


def _dashboard_data(
    results: tuple[PortfolioDayResult, ...],
    evaluations: Mapping[str, Day2AsOfEvaluation],
) -> dict[str, object]:
    return {
        "methodology": (
            "All architecture outputs were sealed before five-session outcomes "
            "and labels were loaded."
        ),
        "assumptions": ["Reviewed fixed-quantity portfolios and point-in-time data."],
        "warnings": [],
        "limitations": ["Preliminary descriptive panel; human review required."],
        "portfolio_days": [
            {
                "key": result.key,
                "nav_drawdown_context": {
                    "nav": evaluations[result.key.key_digest].nav_history[-1][1],
                    "maximum_drawdown": next(
                        item.value
                        for item in evaluations[
                            result.key.key_digest
                        ].metric_pack.metrics
                        if item.metric_id == "maximum_drawdown"
                    ),
                },
                "metric_pack": evaluations[result.key.key_digest].metric_pack,
                "eligible_events": [],
                "deterministic_findings": [
                    evaluations[result.key.key_digest].finding
                ],
                "observations": result.observations,
                "label": result.label,
            }
            for result in results
        ],
    }


def _artifact_digests(root: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for path in sorted(root.iterdir()):
        if path.name in {"evidence-manifest.json", "run-manifest.json"}:
            continue
        values[path.name] = sha256_tree(path) if path.is_dir() else sha256_file(path)
    return values


def run_day4(
    experiment_manifest: Path | str,
    output_root: Path | str,
    *,
    provider_id: str,
    authorized_model_calls: int,
    allow_fixture_provider: bool = False,
    resume: bool = False,
) -> Path:
    """Execute, seal, label, evaluate, and render the reviewed Day 4 plan."""

    manifest_path = Path(experiment_manifest).resolve(strict=True)
    manifest = load_day4_manifest(manifest_path)
    validate_authorized_model_calls(manifest, authorized_model_calls)
    if provider_id != manifest.model.provider_id:
        raise ValueError("selected provider differs from the reviewed manifest")
    if provider_id == "fixture" and not allow_fixture_provider:
        raise ValueError("fixture provider requires explicit --allow-fixture-provider")
    if provider_id not in {"fixture", "openai_responses"}:
        raise ValueError("unsupported Day 4 provider")

    output = _external_root(output_root)
    run_id = "day4_" + manifest.manifest_digest.removeprefix("sha256:")[:24]
    root = output / run_id
    if root.exists() and not resume:
        raise ValueError("Day 4 run exists; use --resume to continue it")
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(root, 0o700)

    contexts, day2_evaluations, outcome_loader = build_contexts(
        manifest, manifest_path
    )
    plan = build_execution_plan(
        manifest,
        {key: value.context_digest for key, value in contexts.items()},
    )
    _secure_write(root / "execution-plan.json", _json_bytes(plan))
    _secure_write(root / "windows.json", _json_bytes(manifest.window_set))
    _parquet(
        root / "architecture-input-index.parquet",
        [
            {
                "key": key,
                "context_digest": bundle.context_digest,
                "bundle": bundle,
            }
            for key, bundle in sorted(contexts.items())
        ],
    )

    provider = (
        _fixture_provider(plan.tasks, contexts)
        if provider_id == "fixture"
        else OpenAIResponsesProvider(manifest.model)
    )
    observations: list[ArchitectureObservation] = []
    receipts: list[Day4TaskReceipt] = []
    calls = 0
    for task in plan.tasks:
        if calls + task.expected_model_calls > AUTHORIZED_MODEL_CALLS:
            raise ValueError("Day 4 provider-call budget would be exceeded")
        observation, receipt = _load_or_execute(
            root,
            task,
            contexts[task.key.key_digest],
            provider,
            resume=resume,
        )
        observations.append(observation)
        receipts.append(receipt)
        calls += len(receipt.model_call_receipts)
    if calls != AUTHORIZED_MODEL_CALLS:
        raise ValueError(f"sealed model-call ledger has {calls} calls, expected 270")

    # Label imports are intentionally delayed until every architecture task is sealed.
    from .labels import construct_labels_after_sealed_execution

    outcomes = outcome_loader()
    labels = construct_labels_after_sealed_execution(
        plan.contexts,
        manifest.window_set.windows,
        outcomes,
        manifest.label_policy,
        architecture_execution_sealed=True,
    )
    label_by_key = {item.key.key_digest: item for item in labels}
    primary_by_key: dict[str, list[ArchitectureObservation]] = defaultdict(list)
    for observation in observations:
        if observation.repetition == 0:
            primary_by_key[observation.key.key_digest].append(observation)
    results = tuple(
        PortfolioDayResult(
            key=key,
            context_digest=contexts[key.key_digest].context_digest,
            observations=tuple(primary_by_key[key.key_digest]),
            label=label_by_key[key.key_digest],
        )
        for key in plan.contexts
    )
    architecture_summary = evaluate_architectures(
        observations,
        labels,
        manifest.label_policy,
        pricing=manifest.pricing,
    )
    repeatability = evaluate_repeatability(observations)

    _parquet(root / "architecture-results.parquet", list(observations))
    _parquet(root / "labels.parquet", list(labels))
    _parquet(root / "portfolio-day-results.parquet", list(results))
    _parquet(
        root / "model-call-ledger.parquet",
        [
            receipt
            for task_receipt in receipts
            for receipt in task_receipt.model_call_receipts
        ],
    )
    _parquet(root / "repeatability-results.parquet", list(repeatability))
    _csv(root / "architecture-summary.csv", list(architecture_summary))
    _csv(root / "repeatability-summary.csv", list(repeatability))
    write_day4_reports(
        root,
        summary=architecture_summary,
        repeatability=repeatability,
        results=results,
        dashboard_data=_dashboard_data(results, day2_evaluations),
        metadata={
            "primary_context_count": 45,
            "primary_observation_count": 135,
            "repeat_observation_count": 18,
            "total_observation_count": 153,
            "label_count": 45,
            "model_call_count": 270,
            "assumptions": ["Reviewed point-in-time inputs."],
            "warnings": [],
            "limitations": list(manifest.limitations),
        },
        worked_example_rules=manifest.worked_example_rules,
    )
    public = root / "public" / "preliminary-results.md"
    _secure_write(public, (root / "preliminary-results.md").read_bytes())

    artifact_digests = _artifact_digests(root)
    created = min(key.as_of for key in plan.contexts)
    sealed = max(key.as_of for key in plan.contexts) + timedelta(seconds=1)
    run_manifest = Day4RunManifest(
        run_id=run_id,
        experiment_digest=manifest.manifest_digest,
        execution_plan_digest=plan.plan_digest,
        created_at=created,
        architecture_execution_sealed_at=sealed,
        artifact_digests=artifact_digests,
        provider_error_count=sum(item.execution_failure for item in observations),
        warnings=(),
        limitations=manifest.limitations,
    )
    _secure_write(root / "run-manifest.json", _json_bytes(run_manifest))
    evidence = artifact_digests | {
        "run-manifest.json": sha256_file(root / "run-manifest.json")
    }
    _secure_write(root / "evidence-manifest.json", _json_bytes(evidence))
    return root


def _read_payloads(path: Path, model: object) -> tuple[object, ...]:
    values = pq.read_table(path).column("payload_json").to_pylist()
    return tuple(model.model_validate(json.loads(value)) for value in values)


def validate_day4_run(
    run_directory: Path | str,
    *,
    require_successful_provider: bool = False,
    require_exit_criteria: bool = False,
) -> Day4RunManifest:
    root = Path(run_directory)
    if not root.is_absolute() or not root.is_dir():
        raise ValueError("Day 4 run directory must be an existing absolute directory")
    evidence = json.loads(
        (root / "evidence-manifest.json").read_text(encoding="utf-8")
    )
    siblings = {
        path.name
        for path in root.iterdir()
        if path.name != "evidence-manifest.json"
    }
    if siblings != set(evidence):
        raise ValueError("Day 4 evidence manifest does not cover every artifact")
    for name, expected in evidence.items():
        path = root / name
        actual = sha256_tree(path) if path.is_dir() else sha256_file(path)
        if actual != expected:
            raise ValueError(f"Day 4 artifact digest mismatch: {name}")
    run_manifest = Day4RunManifest.model_validate_json(
        (root / "run-manifest.json").read_text(encoding="utf-8")
    )
    observations = _read_payloads(
        root / "architecture-results.parquet", ArchitectureObservation
    )
    labels = pq.read_table(root / "labels.parquet").num_rows
    ledger = pq.read_table(root / "model-call-ledger.parquet").num_rows
    primary = sum(item.repetition == 0 for item in observations)
    repeats = sum(item.repetition == 1 for item in observations)
    if (primary, repeats, len(observations), labels, ledger) != (
        135,
        18,
        153,
        45,
        270,
    ):
        raise ValueError("Day 4 frozen acceptance counts differ")
    failures = sum(item.execution_failure for item in observations)
    if require_successful_provider and failures:
        raise ValueError("Day 4 run contains provider execution failures")
    if require_exit_criteria:
        if len(tuple((root / "charts").glob("*.svg"))) != 3:
            raise ValueError("Day 4 requires exactly three charts")
        if len(tuple((root / "worked-examples").glob("*.json"))) != 5:
            raise ValueError("Day 4 worked-example exit criterion failed")
        if not (root / "dashboard/index.html").is_file():
            raise ValueError("Day 4 dashboard is absent")
    return run_manifest


def inspect_day4_results(run_directory: Path | str) -> tuple[dict[str, object], ...]:
    """Return architecture-ordered primary-view aggregate rows."""

    path = Path(run_directory) / "architecture-summary.csv"
    with path.open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    output: list[dict[str, object]] = []
    for architecture in ARCHITECTURES:
        selected = [
            row
            for row in rows
            if row["architecture_id"] == architecture
            and row["label_view"] == "event_window"
        ]
        output.append(
            {
                "architecture_id": architecture,
                "groups": len(selected),
                "portfolio_days": sum(int(row["total_portfolio_days"]) for row in selected),
                "alerts": sum(int(row["alerts"]) for row in selected),
                "abstentions": sum(int(row["abstentions"]) for row in selected),
                "execution_failures": sum(
                    int(row["execution_failures"]) for row in selected
                ),
                "effects": 0,
            }
        )
    return tuple(output)
