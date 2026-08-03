from __future__ import annotations

import ast
import json
from pathlib import Path

import pyarrow.parquet as pq
import pytest

from portfolio_risk_thesis.day4.manifest import (
    build_execution_plan,
    load_day4_manifest,
    validate_authorized_model_calls,
)
from portfolio_risk_thesis.day4.runner import (
    build_contexts,
    run_day4,
    validate_day4_run,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_MANIFEST = (
    REPOSITORY_ROOT
    / "examples/portfolio-risk-thesis/experiments/day4_fixture.yaml"
)
RUNNER_SOURCE = (
    REPOSITORY_ROOT
    / "examples/portfolio-risk-thesis/src/portfolio_risk_thesis/day4/runner.py"
)


def test_runner_has_no_eager_label_import() -> None:
    tree = ast.parse(RUNNER_SOURCE.read_text(encoding="utf-8"))
    imports = [
        node
        for node in tree.body
        if isinstance(node, (ast.Import, ast.ImportFrom))
    ]

    assert not any(
        isinstance(node, ast.ImportFrom)
        and node.module
        and node.module.endswith("labels")
        for node in imports
    )


def test_contexts_reuse_day2_and_share_one_digest_across_architectures() -> None:
    manifest = load_day4_manifest(FIXTURE_MANIFEST)
    contexts, evaluations, _ = build_contexts(manifest, FIXTURE_MANIFEST)
    plan = build_execution_plan(
        manifest,
        {key: value.context_digest for key, value in contexts.items()},
    )

    assert len(contexts) == len(evaluations) == 45
    for key in manifest.portfolio_day_keys():
        assert contexts[key.key_digest].as_of == key.as_of
        assert (
            contexts[key.key_digest].metrics
            == {
                item.metric_id: item.value
                for item in evaluations[key.key_digest].metric_pack.metrics
            }
        )
        assert {
            task.context_digest
            for task in plan.tasks
            if task.key.key_digest == key.key_digest
        } == {contexts[key.key_digest].context_digest}


def test_authorization_mismatch_is_rejected() -> None:
    manifest = load_day4_manifest(FIXTURE_MANIFEST)

    with pytest.raises(ValueError, match="exactly equal"):
        validate_authorized_model_calls(manifest, 269)


def test_full_fixture_matrix_is_complete_resumable_and_effect_free(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("THESIS_DATA_ROOT", str(tmp_path))
    output = tmp_path / "runs"
    first = run_day4(
        FIXTURE_MANIFEST,
        output,
        provider_id="fixture",
        authorized_model_calls=270,
        allow_fixture_provider=True,
    )
    raw_before = {
        path.relative_to(first): path.read_bytes()
        for path in (first / "raw-runs").rglob("*.json")
    }
    second = run_day4(
        FIXTURE_MANIFEST,
        output,
        provider_id="fixture",
        authorized_model_calls=270,
        allow_fixture_provider=True,
        resume=True,
    )

    assert second == first
    assert raw_before == {
        path.relative_to(second): path.read_bytes()
        for path in (second / "raw-runs").rglob("*.json")
    }
    run_manifest = validate_day4_run(
        second,
        require_successful_provider=True,
        require_exit_criteria=True,
    )
    assert run_manifest.effects == ()
    assert run_manifest.provider_error_count == 0
    assert pq.read_table(second / "architecture-results.parquet").num_rows == 153
    assert pq.read_table(second / "labels.parquet").num_rows == 45
    assert pq.read_table(second / "model-call-ledger.parquet").num_rows == 270
    evidence = json.loads(
        (second / "evidence-manifest.json").read_text(encoding="utf-8")
    )
    assert "raw-runs" in evidence
    assert "dashboard" in evidence
    assert "public" in evidence


def test_fixture_provider_requires_explicit_allowance(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("THESIS_DATA_ROOT", str(tmp_path))

    with pytest.raises(ValueError, match="explicit"):
        run_day4(
            FIXTURE_MANIFEST,
            tmp_path / "runs",
            provider_id="fixture",
            authorized_model_calls=270,
        )
