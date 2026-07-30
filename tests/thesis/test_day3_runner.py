import json
import stat

import pytest

from portfolio_risk_thesis.day3.contracts import bytes_digest
from portfolio_risk_thesis.day3.providers import FixtureStructuredModelProvider
from portfolio_risk_thesis.day3.runner import run, validate_run, write_run

from day3_helpers import bundle, fixture_responses


ARTIFACTS = {
    "architecture-input.json",
    "treatment-definitions.json",
    "b0-output.json",
    "b1-output.json",
    "a1-market-output.json",
    "a1-exposure-output.json",
    "a1-news-output.json",
    "a1-synthesis-output.json",
    "critic-reports.json",
    "model-call-receipts.json",
    "agent-timeline.json",
    "architecture-results.json",
    "architecture-comparison.json",
    "run-manifest.json",
    "evidence-manifest.json",
}


def test_runner_writes_complete_immutable_external_evidence_bundle(tmp_path):
    context = bundle()
    comparison = run(
        context,
        FixtureStructuredModelProvider(fixture_responses(context)),
    )
    output = write_run(tmp_path.resolve(), context, comparison)
    assert {path.name for path in output.iterdir()} == ARTIFACTS
    assert write_run(tmp_path.resolve(), context, comparison) == output
    assert stat.S_IMODE(output.stat().st_mode) == 0o700
    assert all(
        stat.S_IMODE(path.stat().st_mode) == 0o600
        for path in output.iterdir()
    )
    assert validate_run(output) == comparison


def test_evidence_manifest_digests_every_sibling_and_comparison_is_complete(tmp_path):
    context = bundle()
    comparison = run(
        context,
        FixtureStructuredModelProvider(fixture_responses(context)),
    )
    output = write_run(tmp_path.resolve(), context, comparison)
    evidence = json.loads((output / "evidence-manifest.json").read_text())
    siblings = ARTIFACTS - {"evidence-manifest.json"}
    assert set(evidence) == siblings
    for name, expected in evidence.items():
        assert bytes_digest((output / name).read_bytes()) == expected
    compact = json.loads((output / "architecture-comparison.json").read_text())
    assert [item["model_calls"] for item in compact["architectures"]] == [0, 1, 4]
    assert compact["context_digest"] == context.context_digest
    assert all("unsupported_claim_count" in item for item in compact["architectures"])
    assert all("evidence_reference_coverage" in item for item in compact["architectures"])
    assert compact["effects"] == 0


def test_tampered_artifact_fails_validation(tmp_path):
    context = bundle()
    output = write_run(
        tmp_path.resolve(),
        context,
        run(context, FixtureStructuredModelProvider(fixture_responses(context))),
    )
    (output / "b1-output.json").write_text("{}\n", encoding="utf-8")
    with pytest.raises(ValueError, match="digest mismatch"):
        validate_run(output)
