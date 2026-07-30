from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from portfolio_risk_thesis.day3.contracts import ModelConfiguration, digest
from portfolio_risk_thesis.day4.contracts import (
    Day4ExperimentManifest,
    Day4InputBindings,
    Day4LabelPolicy,
    Day4RepeatabilityPolicy,
    Day4WindowSet,
    ExternalArtifactBinding,
    HistoricalWindow,
    PortfolioDayKey,
    ProviderPricingSnapshot,
)
from portfolio_risk_thesis.day4.manifest import (
    Day4ManifestError,
    build_execution_plan,
    estimate_model_calls,
    init_day4_experiment,
    load_day4_manifest,
    sha256_file,
    sha256_tree,
    validate_authorized_model_calls,
    validate_day4_manifest,
)


PORTFOLIOS = ("portfolio-a", "portfolio-b", "portfolio-c")


def _dates(start: datetime) -> tuple[datetime, ...]:
    return tuple(start + timedelta(days=index) for index in range(5))


def _manifest(tmp_path: Path) -> Day4ExperimentManifest:
    model = ModelConfiguration(
        provider_id="fixture",
        model_id="fixture-structured-v1",
        model_snapshot="fixture-structured-v1",
        prompt_manifest_digest=digest("prompts"),
        maximum_output_tokens=1600,
        timeout_seconds=30,
        retry_count=0,
    )
    pricing = ProviderPricingSnapshot(
        provider_id="fixture",
        model_snapshot="fixture-structured-v1",
        currency="usd",
        input_price_per_million_tokens="0",
        output_price_per_million_tokens="0",
        effective_at=datetime(2024, 1, 1, tzinfo=UTC),
        source_reference="reviewed-fixture-pricing",
        reviewer="research-reviewer",
    )
    files = {}
    for name in (
        "coverage",
        "day2",
        "events-manifest",
        "events",
        "model",
        "pricing",
    ):
        path = tmp_path / f"{name}.json"
        value = (
            model.model_dump(mode="json")
            if name == "model"
            else pricing.model_dump(mode="json")
            if name == "pricing"
            else {}
        )
        path.write_text(yaml.safe_dump(value), encoding="utf-8")
        files[name] = path
    acceptance = tmp_path / "day3-acceptance"
    acceptance.mkdir()
    (acceptance / "evidence.json").write_text("{}\n", encoding="utf-8")
    binding = lambda path: ExternalArtifactBinding(
        path=str(path), digest=sha256_file(path)
    )
    inputs = Day4InputBindings(
        coverage_profile=binding(files["coverage"]),
        day2_experiment_manifest=binding(files["day2"]),
        day3_event_manifest=binding(files["events-manifest"]),
        day3_event_dataset=binding(files["events"]),
        day3_model_config=binding(files["model"]),
        day3_acceptance_run=ExternalArtifactBinding(
            path=str(acceptance),
            digest=sha256_tree(acceptance),
            kind="tree",
        ),
        pricing_manifest=binding(files["pricing"]),
    )
    starts = (
        datetime(2024, 1, 2, 21, tzinfo=UTC),
        datetime(2024, 2, 1, 21, tzinfo=UTC),
        datetime(2024, 3, 1, 21, tzinfo=UTC),
    )
    windows = Day4WindowSet(
        windows=tuple(
            HistoricalWindow(
                window_id=window_id,
                kind="control" if window_id == "control" else "stress",
                rationale=f"Reviewed rationale for {window_id}.",
                review_dates=_dates(start),
                trigger_available_at=None if window_id == "control" else start,
                relevant_portfolios=()
                if window_id == "control"
                else PORTFOLIOS[:2],
            )
            for window_id, start in zip(
                ("stress_a", "stress_b", "control"), starts, strict=True
            )
        )
    )
    anchors = tuple(
        PortfolioDayKey(
            portfolio_id=portfolio,
            window_id=window.window_id,
            as_of=window.review_dates[0],
        )
        for portfolio in PORTFOLIOS
        for window in windows.windows
    )
    return Day4ExperimentManifest(
        profile="real",
        experiment_id="portfolio-risk-architecture-comparison-v1",
        reviewed=True,
        reviewer="research-reviewer",
        portfolios=PORTFOLIOS,
        inputs=inputs,
        window_set=windows,
        label_policy=Day4LabelPolicy(
            future_portfolio_drawdown_threshold="-0.05",
            future_realized_volatility_threshold="0.30",
            worst_position_loss_threshold="-0.10",
            material_event_enabled=True,
            matching_lookback_business_days=5,
        ),
        repeatability=Day4RepeatabilityPolicy(anchors=anchors),
        model=model,
        pricing=pricing,
        maximum_authorized_model_calls=270,
    )


def _coverage(manifest: Day4ExperimentManifest) -> dict[str, object]:
    return {
        "portfolios": [
            {
                "portfolio_id": portfolio,
                "eligible_window_candidates": [
                    {"as_of": key.as_of.isoformat().replace("+00:00", "Z")}
                    for key in manifest.portfolio_day_keys()
                    if key.portfolio_id == portfolio
                ],
            }
            for portfolio in manifest.portfolios
        ]
    }


def test_reviewed_manifest_enforces_exact_panel_anchors_and_budget(tmp_path):
    manifest = _manifest(tmp_path)
    assert len(manifest.portfolio_day_keys()) == 45
    assert len(manifest.repeatability.anchors) == 9
    assert estimate_model_calls(manifest) == 270
    assert validate_authorized_model_calls(manifest, 270) == 270
    with pytest.raises(Day4ManifestError):
        validate_authorized_model_calls(manifest, 269)
    with pytest.raises(ValidationError):
        Day4ExperimentManifest.model_validate(
            manifest.model_dump(mode="python")
            | {"maximum_authorized_model_calls": 271}
        )
    with pytest.raises(ValidationError):
        Day4ExperimentManifest.model_validate(
            manifest.model_dump(mode="python") | {"reviewed": False}
        )


def test_manifest_coverage_validation_requires_prior_and_future_eligible_dates(tmp_path):
    manifest = _manifest(tmp_path)
    validate_day4_manifest(manifest, coverage=_coverage(manifest))
    missing = _coverage(manifest)
    missing["portfolios"][0]["eligible_window_candidates"].pop()
    with pytest.raises(Day4ManifestError, match="required prior/future coverage"):
        validate_day4_manifest(manifest, coverage=missing)


def test_manifest_loader_verifies_every_external_digest(tmp_path):
    manifest = _manifest(tmp_path)
    coverage_path = Path(manifest.inputs.coverage_profile.path)
    coverage_path.write_text(yaml.safe_dump(_coverage(manifest)), encoding="utf-8")
    raw = manifest.model_dump(mode="json")
    raw["inputs"]["coverage_profile"]["digest"] = sha256_file(coverage_path)
    refreshed = Day4ExperimentManifest.model_validate(
        raw | {"manifest_digest": ""}
    )
    path = tmp_path / "experiment.yaml"
    path.write_text(
        yaml.safe_dump(refreshed.model_dump(mode="json"), sort_keys=False),
        encoding="utf-8",
    )
    loaded = load_day4_manifest(path)
    assert loaded.manifest_digest == refreshed.manifest_digest
    Path(loaded.inputs.day3_event_dataset.path).write_text(
        '{"changed": true}\n', encoding="utf-8"
    )
    with pytest.raises(Day4ManifestError, match="digest mismatch"):
        load_day4_manifest(path)


def test_execution_plan_is_stable_and_has_135_plus_18_tasks(tmp_path):
    manifest = _manifest(tmp_path)
    context_digests = {
        key.key_digest: digest({"context": key.key_digest})
        for key in manifest.portfolio_day_keys()
    }
    first = build_execution_plan(manifest, context_digests)
    second = build_execution_plan(manifest, context_digests)
    assert first == second
    assert first.plan_digest == second.plan_digest
    assert len([task for task in first.tasks if task.repetition == 0]) == 135
    assert len([task for task in first.tasks if task.repetition == 1]) == 18
    assert sum(task.expected_model_calls for task in first.tasks) == 270


def test_initializer_is_unreviewed_immutable_and_selects_no_dates_or_thresholds(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    files = []
    for index in range(6):
        path = source / f"input-{index}.json"
        path.write_text("{}\n", encoding="utf-8")
        files.append(path)
    accepted = source / "accepted"
    accepted.mkdir()
    (accepted / "evidence.json").write_text("{}\n", encoding="utf-8")
    output = tmp_path / "day4-experiment.yaml"
    arguments = {
        "output": output,
        "experiment_id": "portfolio-risk-architecture-comparison-v1",
        "portfolios": PORTFOLIOS,
        "coverage_profile": files[0],
        "day2_experiment_manifest": files[1],
        "day3_event_manifest": files[2],
        "day3_event_dataset": files[3],
        "day3_model_config": files[4],
        "day3_acceptance_run": accepted,
        "pricing_manifest": files[5],
    }
    assert init_day4_experiment(**arguments) == output
    assert init_day4_experiment(**arguments) == output
    template = yaml.safe_load(output.read_text(encoding="utf-8"))
    assert template["reviewed"] is False
    assert template["reviewer"] is None
    assert template["maximum_authorized_model_calls"] == 270
    assert all(
        date.startswith("TODO:")
        for window in template["window_set"]["windows"]
        for date in window["review_dates"]
    )
    assert template["label_policy"]["future_portfolio_drawdown_threshold"] == "TODO"
    with pytest.raises(Day4ManifestError, match="different content"):
        init_day4_experiment(**(arguments | {"experiment_id": "different"}))
