"""Private local Day 3 manifest validation and execution entry points."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import yaml

from portfolio_risk_thesis.contracts import DeterministicFinding, KernelDecisionPoint, MorningMetricPack, ReviewItem

from .contracts import ArchitectureInputBundle, ModelConfiguration, PositionExposure
from .events import eligible_events, read_events, validate_event_manifest
from .prompts import prompt_manifest_digest
from .providers.fixture import FixtureStructuredModelProvider
from .providers.openai_responses import OpenAIResponsesProvider
from .runner import run, validate_run, write_run

DAY2_ARTIFACTS = (
    "morning-metric-packs.json",
    "deterministic-findings.json",
    "kernel-decisions.json",
    "evidence-manifest.json",
)
DAY2_METRICS = {
    "daily_return",
    "annualized_volatility",
    "maximum_drawdown",
    "historical_var_95",
    "historical_expected_shortfall_95",
}


def _digest_file(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _absolute(path: Path | str, label: str, exists: bool = True) -> Path:
    value = Path(path)
    if not value.is_absolute():
        raise ValueError(f"{label} must be absolute")
    return value.resolve(strict=exists)


def _document(path: Path) -> dict[str, object]:
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("Day 3 experiment manifest must be an object")
    return value


def _verify_day2_run(run: Path) -> None:
    if any(not (run / name).is_file() for name in DAY2_ARTIFACTS):
        raise ValueError("Day 2 run directory is incomplete")
    evidence = json.loads(
        (run / "evidence-manifest.json").read_text(encoding="utf-8")
    )
    if evidence.get("effects") != [] or not isinstance(evidence.get("artifacts"), dict):
        raise ValueError("Day 2 evidence manifest is invalid")
    for name in DAY2_ARTIFACTS[:-1]:
        if evidence["artifacts"].get(name) != _digest_file(run / name):
            raise ValueError(f"Day 2 evidence digest mismatch: {name}")


def _load_configuration(path: Path) -> ModelConfiguration:
    configuration = ModelConfiguration.model_validate(
        yaml.safe_load(path.read_text(encoding="utf-8"))
    )
    if configuration.prompt_manifest_digest != prompt_manifest_digest():
        raise ValueError("model configuration prompt manifest digest mismatch")
    if configuration.provider_id == "openai_responses" and not re.search(
        r"-\d{4}-\d{2}-\d{2}$", configuration.model_snapshot
    ):
        raise ValueError("OpenAI model must be an explicit dated snapshot")
    return configuration


def prepare_experiment(*, day2_run_directory: Path | str, event_manifest: Path | str, event_dataset: Path | str, model_config: Path | str, portfolio_id: str, exposures: tuple[PositionExposure, ...], output: Path | str) -> Path:
    run = _absolute(day2_run_directory, "Day 2 run directory")
    event_manifest_path = _absolute(event_manifest, "event manifest")
    dataset = _absolute(event_dataset, "event dataset")
    config = _absolute(model_config, "model config")
    target = _absolute(output, "Day 3 experiment manifest", exists=False)
    manifest_events = validate_event_manifest(event_manifest_path)
    if read_events(dataset) != manifest_events:
        raise ValueError("event dataset differs from reviewed event manifest")
    _verify_day2_run(run)
    _load_configuration(config)
    target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    payload = yaml.safe_dump({"version": "1", "portfolio_id": portfolio_id, "day2_run_directory": str(run), "day2_artifact_digests": {name: _digest_file(run / name) for name in DAY2_ARTIFACTS}, "event_manifest": str(event_manifest_path), "event_manifest_digest": _digest_file(event_manifest_path), "event_dataset": str(dataset), "event_dataset_digest": _digest_file(dataset), "model_config": str(config), "model_config_digest": _digest_file(config), "exposures": [item.model_dump(mode="json") for item in exposures], "effects": []}, sort_keys=True)
    if target.exists():
        if target.read_text(encoding="utf-8") == payload:
            return target
        raise ValueError("immutable Day 3 experiment manifest already exists with different content")
    target.write_text(payload, encoding="utf-8")
    target.chmod(0o600)
    return target


def load_bundle(experiment_manifest: Path | str) -> tuple[ArchitectureInputBundle, ModelConfiguration]:
    document = _document(_absolute(experiment_manifest, "Day 3 experiment manifest"))
    if document.get("effects") != []:
        raise ValueError("Day 3 manifest must be effect-free")
    run = _absolute(str(document["day2_run_directory"]), "Day 2 run directory")
    _verify_day2_run(run)
    expected = document["day2_artifact_digests"]
    if not isinstance(expected, dict) or any(_digest_file(run / name) != value for name, value in expected.items()):
        raise ValueError("Day 2 artifact digest mismatch")
    event_manifest = _absolute(str(document["event_manifest"]), "event manifest")
    event_dataset = _absolute(str(document["event_dataset"]), "event dataset")
    model_config = _absolute(str(document["model_config"]), "model config")
    for path, field in (
        (event_manifest, "event_manifest_digest"),
        (event_dataset, "event_dataset_digest"),
        (model_config, "model_config_digest"),
    ):
        if _digest_file(path) != document.get(field):
            raise ValueError(f"{field.removesuffix('_digest')} digest mismatch")
    if read_events(event_dataset) != validate_event_manifest(event_manifest):
        raise ValueError("event dataset differs from reviewed event manifest")
    portfolio_id = str(document["portfolio_id"])
    packs = [MorningMetricPack.model_validate(value) for value in json.loads((run / "morning-metric-packs.json").read_text())]
    finding_document = json.loads((run / "deterministic-findings.json").read_text())
    findings = [DeterministicFinding.model_validate(value) for value in finding_document["findings"]]
    reviews = [ReviewItem.model_validate(value) for value in finding_document["review_items"]]
    decisions = [KernelDecisionPoint.model_validate(value) for value in json.loads((run / "kernel-decisions.json").read_text())]
    try:
        pack = next(value for value in packs if value.portfolio_id == portfolio_id)
        finding = next(value for value in findings if value.portfolio_id == portfolio_id)
        review = next(value for value in reviews if value.portfolio_id == portfolio_id)
        decision = next(value for value in decisions if value.portfolio_id == portfolio_id)
    except StopIteration as error:
        raise ValueError("portfolio is not present in every Day 2 artifact") from error
    if not (finding.finding_id == review.finding_id == decision.finding_id and decision.review_item_id == review.review_item_id):
        raise ValueError("Day 2 finding/review/decision mismatch")
    if not (
        finding.outcome == decision.decision
        and finding.portfolio_id == review.portfolio_id == decision.portfolio_id
    ):
        raise ValueError("Day 2 portfolio or decision alignment mismatch")
    events = eligible_events(read_events(event_dataset), pack.as_of)
    exposures = tuple(PositionExposure.model_validate(value) for value in document["exposures"])
    metrics = {value.metric_id: value.value for value in pack.metrics}
    if set(metrics) != DAY2_METRICS:
        raise ValueError("Day 3 requires exactly the five accepted Day 2 metrics")
    if any(value is None for value in metrics.values()):
        raise ValueError("undefined metric requires a Day 3 abstention context, not a model request")
    authoritative_evidence = set(pack.evidence) | set(finding.evidence)
    if any(
        set(exposure.evidence_refs).difference(authoritative_evidence)
        for exposure in exposures
    ):
        raise ValueError("exposure references evidence outside the accepted Day 2 bundle")
    bundle = ArchitectureInputBundle(portfolio_id=portfolio_id, as_of=pack.as_of, metrics=metrics, deterministic_finding=finding.outcome, review_item=review.summary, decision_point=decision.decision, exposures=exposures, events=events, evidence_refs=tuple(sorted(authoritative_evidence)), warnings=tuple(sorted(set(pack.warnings) | set(finding.warnings))), limitations=pack.limitations)
    config = _load_configuration(model_config)
    return bundle, config


def run_openai_experiment(experiment_manifest: Path | str, output_root: Path | str) -> Path:
    bundle, configuration = load_bundle(experiment_manifest)
    if configuration.provider_id != "openai_responses":
        raise ValueError("real gate requires the explicit openai_responses provider")
    output = write_run(
        _absolute(output_root, "Day 3 output root", exists=False),
        bundle,
        run(bundle, OpenAIResponsesProvider(configuration)),
    )
    try:
        validate_run(output, require_successful_provider=True)
    except ValueError as error:
        raise ValueError(f"{error}; evidence preserved at {output}") from error
    return output


def run_fixture_experiment(
    experiment_manifest: Path | str,
    output_root: Path | str,
    responses: dict[tuple[str, str, str, str], dict[str, object]],
) -> Path:
    bundle, configuration = load_bundle(experiment_manifest)
    if configuration.provider_id != "fixture":
        raise ValueError("fixture run requires an explicit fixture model configuration")
    output = write_run(
        _absolute(output_root, "Day 3 output root", exists=False),
        bundle,
        run(bundle, FixtureStructuredModelProvider(responses)),
    )
    validate_run(output)
    return output
