from __future__ import annotations

import json
from pathlib import Path

import pytest

from portfolio_risk_thesis.day4.report import (
    CHART_FILENAMES,
    aggregate_architecture_summary,
    render_charts,
    render_dashboard,
    render_preliminary_results,
    sanitize_public_data,
    select_worked_examples,
    write_day4_reports,
)


def _summary() -> list[dict[str, object]]:
    return [
        {
            "architecture": architecture,
            "label_view": "event_window",
            "total_portfolio_days": 45,
            "alerts": alerts,
            "abstentions": index,
            "execution_failures": 0,
            "tp": 7 + index,
            "fp": 2,
            "tn": 30 - index,
            "fn": 6,
            "evidence_reference_coverage": 0.90 + index * 0.01,
            "unsupported_claim_rate": 0.02,
            "critic_pass_rate": 0.96,
            "evaluated_coverage": 1.0,
            "median_latency_ms": 10 + index * 50,
            "p95_latency_ms": 20 + index * 60,
            "input_tokens": index * 100,
            "output_tokens": index * 50,
            "provider_cost": None if architecture == "B0" else index / 100,
            "warnings": [],
        }
        for index, (architecture, alerts) in enumerate(
            (("B0", 9), ("B1", 10), ("A1", 11))
        )
    ]


def _repeatability() -> list[dict[str, object]]:
    return [
        {
            "architecture": architecture,
            "status_agreement": 1.0,
            "severity_agreement": 0.9,
            "exact_output_digest_agreement": 0.8,
            "affected_position_jaccard_agreement": 0.85,
            "evidence_reference_jaccard_agreement": 0.88,
        }
        for architecture in ("B0", "B1", "A1")
    ]


def _results() -> list[dict[str, object]]:
    return [
        {
            "observation_id": "stress-a-alert",
            "architecture": "B1",
            "portfolio_alias": "portfolio_alpha",
            "window": "stress_a",
            "review_date": "2020-03-02T21:00:00+00:00",
            "evaluation_class": "alert",
            "label_positive": True,
            "severity": "MEDIUM",
            "evidence_references": ["evidence:a"],
        },
        {
            "observation_id": "stress-b-alert",
            "architecture": "A1",
            "portfolio_alias": "portfolio_beta",
            "window": "stress_b",
            "review_date": "2022-02-01T21:00:00+00:00",
            "evaluation_class": "alert",
            "label_positive": True,
            "severity": "HIGH",
            "evidence_references": ["evidence:b"],
        },
        {
            "observation_id": "third-alert",
            "architecture": "B0",
            "portfolio_alias": "portfolio_gamma",
            "window": "stress_a",
            "review_date": "2020-03-03T21:00:00+00:00",
            "evaluation_class": "alert",
            "label_positive": True,
            "severity": "URGENT",
            "evidence_references": ["evidence:c"],
        },
        {
            "observation_id": "false-positive",
            "architecture": "B0",
            "portfolio_alias": "portfolio_alpha",
            "window": "control",
            "review_date": "2021-06-01T20:00:00+00:00",
            "evaluation_class": "alert",
            "label_positive": False,
            "severity": "LOW",
        },
        {
            "observation_id": "abstention",
            "architecture": "A1",
            "portfolio_alias": "portfolio_beta",
            "window": "control",
            "review_date": "2021-06-02T20:00:00+00:00",
            "evaluation_class": "abstention",
            "label_positive": False,
        },
    ]


def _dashboard_data() -> dict[str, object]:
    return {
        "methodology": "Labels are loaded after architecture execution.",
        "assumptions": ["Reviewed synthetic fixture."],
        "warnings": [],
        "limitations": ["Preliminary descriptive panel."],
        "provider": "must-not-appear",
        "contexts": [
            {
                "portfolio_alias": "portfolio_alpha",
                "window": "stress_a",
                "review_date": "2020-03-02",
                "nav_drawdown_context": {"nav": 98.0, "drawdown": -0.02},
                "metric_pack": {"gross_exposure": 1.1},
                "eligible_events": [{"evidence_id": "event:1"}],
                "deterministic_findings": [{"status": "REVIEW"}],
                "architecture_results": [
                    {
                        "architecture": architecture,
                        "status": "REVIEW",
                        "severity": "MEDIUM",
                        "classification": "alert",
                        "critic": {"passed": True},
                        "evidence_references": ["event:1"],
                        "input_tokens": 10,
                        "output_tokens": 5,
                        "latency_ms": 20,
                        "provider_cost": None,
                    }
                    for architecture in ("B0", "B1", "A1")
                ],
            }
        ],
    }


def test_public_sanitizer_removes_execution_details_and_redacts_paths() -> None:
    sanitized = sanitize_public_data(
        {
            "provider": "private-provider-id",
            "raw_response": {"secret": "value"},
            "winner": "A1",
            "ranking": ["A1", "B1", "B0"],
            "notes": "loaded from /Users/researcher/private/results.json",
            "input_tokens": 12,
        }
    )

    assert sanitized == {
        "input_tokens": 12,
        "notes": "loaded from [redacted-path]",
    }


def test_preliminary_markdown_is_aggregate_public_safe_and_cautious() -> None:
    markdown = render_preliminary_results(
        _summary(),
        _repeatability(),
        {
            "primary_context_count": 45,
            "primary_observation_count": 135,
            "repeat_observation_count": 18,
            "total_observation_count": 153,
            "label_count": 45,
            "model_call_count": 270,
            "provider": "private-provider-id",
            "private_path": "/Users/researcher/private",
        },
    )
    lowered = markdown.casefold()

    assert "45" in markdown
    assert "270" in markdown
    assert "not investment advice" in lowered
    assert "human review is required" in lowered
    assert "comparative conclusion" in lowered
    assert "private-provider-id" not in markdown
    assert "/users/" not in lowered
    assert "portfolio_alpha" not in markdown
    assert "## assumptions" in lowered
    assert "## warnings" in lowered
    assert "## limitations" in lowered


def test_aggregate_summary_preserves_null_cost_and_null_ratio_semantics() -> None:
    rows = aggregate_architecture_summary(
        [
            {
                "architecture": "B0",
                "label_view": "event_window",
                "total_portfolio_days": 1,
                "alerts": 0,
                "tp": 0,
                "fp": 0,
                "fn": 0,
                "provider_cost": None,
            }
        ]
    )

    assert rows[0]["precision"] is None
    assert rows[0]["recall"] is None
    assert rows[0]["provider_cost"] is None
    assert rows[0]["warnings"] == ["pricing_unavailable"]


def test_aggregate_summary_accepts_contract_timeliness_field_names() -> None:
    rows = aggregate_architecture_summary(
        [
            {
                "architecture_id": "B1",
                "label_view": "event_window",
                "total_portfolio_days": 1,
                "alerts": 1,
                "true_positives": 1,
                "false_positives": 0,
                "false_negatives": 0,
                "median_event_detection_delay_seconds": 120,
                "median_outcome_lead_time_seconds": 3600,
                "provider_cost": 0.01,
            }
        ]
    )

    assert rows[0]["median_event_detection_delay"] == 120
    assert rows[0]["median_outcome_lead_time"] == 3600


def test_worked_example_selection_is_rule_based_and_input_order_independent() -> None:
    forward = select_worked_examples(_results())
    reverse = select_worked_examples(reversed(_results()))

    assert forward == reverse
    assert [item["selection_rule"] for item in forward] == [
        "earliest_true_positive_stress_a",
        "earliest_true_positive_stress_b",
        "highest_severity_true_positive_different_portfolio",
        "earliest_false_positive_or_failure",
        "earliest_abstention",
    ]
    assert forward[2]["observation"]["observation_id"] == "third-alert"
    assert forward[3]["observation"]["observation_id"] == "false-positive"


def test_worked_example_selection_accepts_portfolio_day_result_shape() -> None:
    nested = []
    for row in _results():
        nested.append(
            {
                "key": {
                    "portfolio_id": row["portfolio_alias"],
                    "window_id": row["window"],
                    "as_of": row["review_date"],
                },
                "label": {
                    "label_digest": f"digest:{row['observation_id']}",
                    "event_window": {"positive": row["label_positive"]},
                },
                "observations": [
                    {
                        "task_id": row["observation_id"],
                        "architecture_id": row["architecture"],
                        "status": (
                            "ABSTAIN"
                            if row["evaluation_class"] == "abstention"
                            else "REVIEW"
                        ),
                        "severity": (
                            {"LOW": 1, "MEDIUM": 2, "HIGH": 3, "URGENT": 3}.get(
                                str(row.get("severity")), 0
                            )
                        ),
                        "critic_passed": True,
                    }
                ],
            }
        )

    selected = select_worked_examples(nested)
    assert len(selected) == 5
    assert selected[2]["observation"]["portfolio_id"] == "portfolio_gamma"


def test_worked_example_selection_falls_back_to_critic_failure() -> None:
    results = [
        row for row in _results() if row["observation_id"] != "false-positive"
    ]
    results.append(
        {
            "observation_id": "critic-failure",
            "architecture": "B1",
            "portfolio_alias": "portfolio_alpha",
            "window": "control",
            "review_date": "2021-05-01",
            "evaluation_class": "no_alert",
            "critic_pass": False,
        }
    )

    selected = select_worked_examples(results)
    assert selected[3]["observation"]["observation_id"] == "critic-failure"


def test_insufficient_alert_examples_fail_acceptance() -> None:
    with pytest.raises(ValueError, match="fewer than three alert cases"):
        select_worked_examples(_results()[:2])


def test_missing_failure_or_abstention_case_fails_acceptance() -> None:
    only_alerts = _results()[:3]

    with pytest.raises(ValueError, match="required cases unavailable"):
        select_worked_examples(only_alerts)


def test_charts_are_deterministic_accessible_and_idempotent(tmp_path: Path) -> None:
    first = render_charts(_summary(), tmp_path)
    contents = {path.name: path.read_text(encoding="utf-8") for path in first}
    second = render_charts(list(reversed(_summary())), tmp_path)

    assert tuple(path.name for path in first) == CHART_FILENAMES
    assert first == second
    assert all(path.read_text(encoding="utf-8") == contents[path.name] for path in second)
    assert all('role="img"' in content for content in contents.values())
    assert all("<title" in content and "<desc" in content for content in contents.values())


def test_chart_refuses_to_mutate_an_existing_artifact(tmp_path: Path) -> None:
    render_charts(_summary(), tmp_path)
    changed = _summary()
    changed[0]["tp"] = 40

    with pytest.raises(FileExistsError, match="immutable artifact"):
        render_charts(changed, tmp_path)


def test_dashboard_is_self_contained_semantic_offline_and_sanitized(
    tmp_path: Path,
) -> None:
    dashboard = render_dashboard(_dashboard_data(), tmp_path)
    html = dashboard.read_text(encoding="utf-8")
    data = json.loads((tmp_path / "dashboard-data.json").read_text(encoding="utf-8"))

    assert dashboard.name == "index.html"
    assert "<style>" in html
    assert "<script>" in html
    assert "<section" in html
    assert all(
        control in html
        for control in ('id="portfolio"', 'id="window"', 'id="review-date"', 'id="architecture"')
    )
    assert all(
        section in html
        for section in (
            "NAV and drawdown context",
            "MetricPack",
            "Eligible events",
            "Deterministic findings",
            "Architecture comparison",
            "Critic and evidence detail",
            "Tokens, latency, and cost",
            "Human decision options",
            "Export preliminary Markdown",
        )
    )
    assert "cdn" not in html.casefold()
    assert "private-provider-id" not in html
    assert "provider" not in data
    assert "portfolio_alpha" in html
    assert "../charts/alert-quality.svg" in html


def test_dashboard_escapes_embedded_script_content(tmp_path: Path) -> None:
    data = _dashboard_data()
    data["warnings"] = ["</script><script>alert('unsafe')</script>"]
    html = render_dashboard(data, tmp_path).read_text(encoding="utf-8")

    assert "</script><script>alert" not in html
    assert "\\u003c/script\\u003e" in html


def test_complete_reporting_layer_writes_required_artifacts_idempotently(
    tmp_path: Path,
) -> None:
    kwargs = {
        "summary": _summary(),
        "repeatability": _repeatability(),
        "results": _results(),
        "dashboard_data": _dashboard_data(),
        "metadata": {
            "context_count": 45,
            "primary_observation_count": 135,
            "repeat_observation_count": 18,
            "label_count": 45,
            "model_call_receipt_count": 270,
        },
    }
    first = write_day4_reports(tmp_path, **kwargs)
    second = write_day4_reports(tmp_path, **kwargs)

    assert first == second
    assert (tmp_path / "preliminary-results.md").is_file()
    assert (tmp_path / "dashboard" / "index.html").is_file()
    assert (tmp_path / "dashboard" / "dashboard-data.json").is_file()
    assert {path.name for path in (tmp_path / "charts").iterdir()} == set(
        CHART_FILENAMES
    )
    assert len(list((tmp_path / "worked-examples").glob("*.json"))) == 5
