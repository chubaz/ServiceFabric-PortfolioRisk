from __future__ import annotations

from risk_reports import compose_daily_risk_report, render_markdown, render_report, with_rendered_html


def test_restricted_markdown_renders_hierarchy_and_evidence() -> None:
    rendered = render_markdown(
        "**Primary:** material change. [evidence:event-1]\n\n- first\n- second\n\n> Human review."
    )
    assert "<strong>Primary:</strong>" in rendered
    assert 'class="report-evidence"' in rendered
    assert "<ul>" in rendered
    assert "<blockquote>" in rendered


def test_html_links_scripts_and_event_handlers_are_never_executable() -> None:
    malicious = '<script>alert(1)</script> [click](javascript:alert(2)) <img src=x onerror="alert(3)">'
    rendered = render_markdown(malicious)
    assert "<script" not in rendered
    assert "<img" not in rendered
    assert "javascript:alert" in rendered  # visible inert text, not a link
    assert "&lt;script&gt;" in rendered
    report = compose_daily_risk_report(
        {
            "title": malicious,
            "outcome_sought": malicious,
            "executive_conclusion": malicious,
            "as_of": "2026-08-03",
            "findings": [],
            "limitations": [],
            "next_steps": [],
            "review_boundary": malicious,
        },
        report_id="report:xss-test",
    )
    safe = with_rendered_html(report)
    output = render_report(safe)
    assert "<script" not in output
    assert "<img" not in output
    assert 'onerror=&quot;alert(3)&quot;' in output
