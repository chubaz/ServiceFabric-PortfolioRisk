from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]
MANIFEST = (
    ROOT
    / "config"
    / "agent"
    / "thesis-risk-episodes"
    / "initial-case-sampling-manifest.yaml"
)
LANGUAGE = ROOT / "docs" / "thesis" / "risk-episode-case-framework-language.md"


def test_initial_case_sampling_manifest_is_bounded_and_private_neutral() -> None:
    source = MANIFEST.read_text(encoding="utf-8")
    value = yaml.safe_load(source)

    assert value["period"] == {
        "start": "2013-01-01",
        "end": "2017-12-31",
        "reason": "exact common RavenPack coverage within the larger CRSP/Compustat history",
    }
    assert value["universe"]["expected_unique_securities"] == 18
    assert value["universe"]["ravenpack_linked_securities"] == 16
    assert (
        value["data_revisions"]["crsp_compustat"]["snapshot_id"]
        == value["data_revisions"]["portfolios"]["source_snapshot_id"]
    )
    assert value["data_revisions"]["ravenpack"]["scope"] == "reviewed_portfolios"
    assert value["locator_policy"]["licensed_bytes_in_git"] is False
    assert value["truth_boundaries"]["population_recall_claim"] == "prohibited"
    assert "/Users/" not in source
    assert "/home/" not in source


def test_framework_language_assigns_one_owner_without_a_parallel_catalogue() -> None:
    source = LANGUAGE.read_text(encoding="utf-8")

    for payload in (
        "DetectorDefinition",
        "DetectorRun",
        "AnomalySignal",
        "RiskEpisodeCandidate",
        "SilverCaseLabel",
        "GoldCaseBundle",
        "CaseLabelBundleReference",
        "FrozenForecastModelManifest",
    ):
        assert source.count(f"`{payload}`") == 1
    assert "No new general finding, alert, evidence, decision, run, evaluation" in source
    assert "not rendered in the research interface" in source
