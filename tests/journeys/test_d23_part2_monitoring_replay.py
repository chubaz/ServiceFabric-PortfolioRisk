from __future__ import annotations

import hashlib
import json
from pathlib import Path

from scripts.day23.run_part2_demo import (
    ARTIFACT_NAMES,
    PROHIBITED_EFFECTS,
    execute_part2_journey,
    write_part2_artifacts,
)


def _digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _effects(value: object) -> list[object]:
    found: list[object] = []
    if isinstance(value, dict):
        for key, item in value.items():
            if key == "effects":
                found.append(item)
            found.extend(_effects(item))
    elif isinstance(value, list):
        for item in value:
            found.extend(_effects(item))
    return found


def test_complete_part2_monitoring_replay_journey(tmp_path: Path) -> None:
    result = execute_part2_journey(tmp_path)
    paths = write_part2_artifacts(result)
    artifacts = result["artifacts"]

    assert set(paths) == {*ARTIFACT_NAMES, "evidence-manifest.json"}
    assert all(path.is_file() for path in paths.values())
    assert write_part2_artifacts(result) == paths

    context = artifacts["data-context.json"]
    assert context["exact_date_effective_mapping"] is True
    assert context["mapping_rule"] == "exact_date_effective"
    assert context["mapping_effective_start"] == "2020-01-01"
    assert context["context"]["mapping_coverage"]["complete"] is True
    assert context["selected_dataset_revisions"]["market"]["dataset_id"] == (
        "synthetic-crsp-like-daily"
    )
    assert context["selected_dataset_revisions"]["fundamental"]["dataset_id"] == (
        "synthetic-compustat-like-annual"
    )
    assert context["selected_crosswalk_revision"].startswith("sha256:")
    assert context["ticker_fallback_used"] is False
    assert context["ticker_probe_blocked"] is True
    assert "missing_mapping" in context["ticker_probe_issue_codes"]
    assert context["point_in_time_rule"] == "available_at <= as_of"

    preview = artifacts["event-import-preview.json"]["preview"]
    snapshot = artifacts["event-snapshot.json"]
    assert preview["row_count"] == 5
    assert artifacts["event-import-preview.json"]["confirmable"] is True
    assert snapshot["snapshot"]["synthetic"] is True
    assert snapshot["query"]["records"]
    assert snapshot["only_available_as_of_monitoring_time"] is True
    assert snapshot["missing_availability_excluded"] is True
    assert all(
        item["available_at"] <= snapshot["query"]["as_of"]
        for item in snapshot["query"]["records"]
    )
    assert "fictional-rp-005" not in {
        item["source_event_id"] for item in snapshot["query"]["records"]
    }

    policy = artifacts["monitoring-policy.json"]
    assert policy["policy"]["revision"] == policy["immutable_revision"]
    assert policy["policy"]["human_review_required"] is True
    assert policy["scheduler_created"] is False
    assert policy["arbitrary_expression_available"] is False

    run = artifacts["monitoring-run.json"]["run"]
    timeline = artifacts["agent-timeline.json"]
    assert run["status"] == "succeeded"
    assert run["findings"]["findings"]
    assert artifacts["findings.json"]["findings"]["digest"].startswith("sha256:")
    assert artifacts["alert-draft.json"]["alert"]["state"] == "draft"
    assert artifacts["alert-draft.json"]["alert"]["investment_advice"] is False
    assert timeline["all_four_existing_agents_ran"] is True
    assert timeline["roles"] == [
        "risk.agent.market_data",
        "risk.agent.portfolio_exposure",
        "risk.agent.news_sentiment",
        "risk.agent.alert_recommendation",
    ]
    assert len(timeline["timeline"]) == 4
    assert all(item["receipt"]["output_digest"].startswith("sha256:") for item in timeline["timeline"])

    specification = artifacts["replay-specification.json"]["specification"]
    replay = artifacts["replay-runs.json"]
    assert specification["point_in_time_rule"] == "available_at_lte_step_as_of"
    assert len(replay["replay"]["steps"]) == 3
    assert replay["abstentions_preserved"] is True
    assert replay["replay"]["steps"][-1]["abstained"] is True
    assert replay["no_look_ahead"] is True
    assert [item["as_of"] for item in replay["replay"]["steps"]] == replay[
        "deterministic_step_times"
    ]
    for step in replay["replay"]["steps"]:
        assert all(
            item["available_at"] <= step["as_of"]
            for item in step["data_context"]["latest_market_observations"]
        )

    evaluation = artifacts["monitoring-evaluation.json"]
    metrics = evaluation["evaluation"]
    assert (
        metrics["true_positive"],
        metrics["false_positive"],
        metrics["false_negative"],
    ) == (1, 1, 1)
    assert metrics["precision"] == "0.5"
    assert metrics["recall"] == "0.5"
    assert metrics["median_lead_time_seconds"] is not None
    assert metrics["median_detection_delay_seconds"] is not None
    assert evaluation["one_to_one_matching"] is True
    assert len({item["alert_id"] for item in metrics["matches"]}) == len(
        metrics["matches"]
    )
    assert len({item["outcome_id"] for item in metrics["matches"]}) == len(
        metrics["matches"]
    )
    undefined = evaluation["undefined_metric_example"]
    assert undefined["recall"] is None
    assert "undefined_recall" in {item["code"] for item in undefined["warnings"]}

    markdown = artifacts["monitoring-report.md"]
    html = artifacts["monitoring-report.html"]
    assert "# Synthetic Day 2–3 Part 2 Monitoring and Replay Review" in markdown
    assert "## Replay metrics" in markdown
    assert "Effects: empty" in markdown
    assert "<article" in html and "<h2 id=" in html

    manifest = json.loads(paths["evidence-manifest.json"].read_text(encoding="utf-8"))
    assert {item["path"] for item in manifest["artifacts"]} == set(ARTIFACT_NAMES)
    assert {
        item["path"]: item["digest"] for item in manifest["artifacts"]
    } == {name: _digest(paths[name]) for name in ARTIFACT_NAMES}
    assert set(manifest["profiles"]) == {"research", "personal_portfolio"}
    assert manifest["point_in_time_rule"] == "available_at <= as_of"
    assert manifest["human_review_pending"] is True
    assert manifest["effects"] == []
    assert set(manifest["prohibited_effects"]) == set(PROHIBITED_EFFECTS)
    assert "one-to-one" in manifest["evaluation_methodology"].lower()
    assert manifest["accepted_limitations"]
    assert manifest["boundary_proofs"] == {
        "network": {"blocked_during_journey": True, "attempts": 0},
        "external_llm": {
            "invoked": False,
            "denied_effect": "external_llm_call",
        },
        "sql": {
            "arbitrary_sql_available": False,
            "rejection": "Value error, SQL and expression input are prohibited",
            "fixed_query_manifests_only": True,
        },
        "notebook_execution": False,
        "broker_connectivity": False,
        "orders": False,
        "trades": False,
        "automatic_rebalancing": False,
        "optimization": False,
    }
    assert manifest["evidence_digests"]
    assert all(
        item["digest"].startswith("sha256:")
        for item in manifest["evidence_digests"]
    )
    assert all(item == [] for artifact in artifacts.values() for item in _effects(artifact))
