"""Dependency-free deterministic Markdown and semantic HTML reports."""

from __future__ import annotations

from decimal import Decimal
from html import escape

from .contracts import AnalysisMethod, AnalysisResult, ContributionSummary, DrawdownResult, HistoricalTailRiskResult, ReturnSeriesResult, RiskReport, ScenarioResult, VolatilityResult


def _markdown_list(values: tuple[str, ...]) -> str:
    return "\n".join(f"- {value}" for value in values) if values else "- None recorded."


def _html_list(values: tuple[str, ...]) -> str:
    return "<ul>" + "".join(f"<li>{escape(value)}</li>" for value in values) + "</ul>" if values else "<p>None recorded.</p>"


def _decimal(value: Decimal) -> str:
    return format(value, "f")


def _outcome_values(result: AnalysisResult) -> tuple[tuple[str, str], ...]:
    """Return stable, human-readable result payload without falling back to JSON."""
    if isinstance(result, ReturnSeriesResult):
        observations = "; ".join(
            f"{item.observed_at.isoformat()} = {_decimal(item.value)}" for item in result.observations
        ) or "None"
        return (
            ("Return method", result.return_method.value),
            ("Return observations", observations),
        )
    if isinstance(result, VolatilityResult):
        return (
            ("Annualized volatility", _decimal(result.annualized_volatility)),
            ("Periods per year", str(result.periods_per_year)),
        )
    if isinstance(result, DrawdownResult):
        return (
            ("Maximum drawdown", _decimal(result.maximum_drawdown)),
            ("Peak timestamp", result.peak_at.isoformat()),
            ("Trough timestamp", result.trough_at.isoformat()),
            ("Wealth-path return method", result.wealth_path_method.value),
        )
    if isinstance(result, HistoricalTailRiskResult):
        return (
            ("Confidence level", _decimal(result.confidence_level)),
            ("Historical value at risk", _decimal(result.value_at_risk)),
            ("Historical expected shortfall", _decimal(result.expected_shortfall)),
            ("Historical rank", str(result.historical_rank)),
            ("Tail observation count", str(result.tail_observation_count)),
            ("Reviewed minimum observation count", str(result.reviewed_minimum_observation_count)),
        )
    if isinstance(result, ScenarioResult):
        positions = "; ".join(
            (
                f"{item.instrument_id}: market value {_decimal(item.market_value)}, "
                f"shock {_decimal(item.percentage_shock)}, P&L {_decimal(item.profit_and_loss)}"
            )
            for item in result.positions
        ) or "None"
        return (
            ("Portfolio profit and loss", f"{_decimal(result.portfolio_profit_and_loss)} {result.currency}"),
            ("Position outcomes", positions),
        )
    if isinstance(result, ContributionSummary):
        items = "; ".join(
            (
                f"{item.instrument_id}: weight {_decimal(item.weight)}, "
                + (
                    "return missing, contribution missing"
                    if item.instrument_return is None
                    else (
                        f"return {_decimal(item.instrument_return)}, contribution "
                        f"{_decimal(item.contribution) if item.contribution is not None else 'missing'}"
                    )
                )
            )
            for item in result.items
        ) or "None"
        return (
            ("Contribution sum", _decimal(result.contribution_sum)),
            ("Portfolio return", _decimal(result.portfolio_return) if result.portfolio_return is not None else "Not provided"),
            ("Reconciliation difference", _decimal(result.reconciliation_difference) if result.reconciliation_difference is not None else "Not available"),
            ("Constituent contributions", items),
        )
    if isinstance(result, RiskReport):
        return (("Source report digest", result.source_output_digest),)
    raise TypeError(f"unsupported analysis result type: {type(result).__name__}")


def _markdown_outcomes(values: tuple[tuple[str, str], ...]) -> str:
    return "\n".join(f"- {label}: {value}" for label, value in values)


def _html_outcomes(values: tuple[tuple[str, str], ...]) -> str:
    return "<dl>" + "".join(
        f"<dt>{escape(label)}</dt><dd>{escape(value)}</dd>" for label, value in values
    ) + "</dl>"


def render_report(*, analysis_id: str, title: str, result: AnalysisResult) -> RiskReport:
    """Render stable review material; no PDF, notebook, or external renderer is involved."""
    warning_text = tuple(f"{item.code}: {item.message}" for item in result.warnings)
    evidence_text = tuple(
        f"{item.evidence_id} — {item.description} ({item.reference}; {item.digest})"
        for item in result.evidence
    )
    outcome_values = _outcome_values(result)
    summary = (
        f"Analysis ID: {result.analysis_id}\n"
        f"Snapshot ID: {result.snapshot_id}\n"
        f"Methodology: {result.methodology.value}\n"
        f"Horizon: {result.horizon.label} ({result.horizon.periods} period(s))\n"
        f"Sample period: {result.sample_period.start.isoformat()} to {result.sample_period.end.isoformat()}\n"
        f"Observation count: {result.observation_count}\n"
        f"Output digest: {result.output_digest}"
    )
    markdown = (
        f"# {title}\n\n"
        "## Analysis summary\n\n"
        f"{summary}\n\n"
        "## Methodology and assumptions\n\n"
        f"{_markdown_list(result.assumptions)}\n\n"
        "## Analysis outcome\n\n"
        f"{_markdown_outcomes(outcome_values)}\n\n"
        "## Evidence\n\n"
        f"{_markdown_list(evidence_text)}\n\n"
        "## Warnings\n\n"
        f"{_markdown_list(warning_text)}\n\n"
        "## Limitations\n\n"
        f"{_markdown_list(result.limitations)}\n"
    )
    summary_html = "".join(
        f"<dt>{escape(key)}</dt><dd>{escape(value)}</dd>"
        for key, value in (
            ("Analysis ID", result.analysis_id),
            ("Snapshot ID", result.snapshot_id),
            ("Methodology", result.methodology.value),
            ("Horizon", f"{result.horizon.label} ({result.horizon.periods} period(s))"),
            ("Sample period", f"{result.sample_period.start.isoformat()} to {result.sample_period.end.isoformat()}"),
            ("Observation count", str(result.observation_count)),
            ("Output digest", result.output_digest or ""),
        )
    )
    html = (
        f'<article class="risk-report" data-analysis-id="{escape(result.analysis_id)}">'
        f"<header><h1>{escape(title)}</h1></header>"
        f"<section><h2>Analysis summary</h2><dl>{summary_html}</dl></section>"
        f"<section><h2>Methodology and assumptions</h2>{_html_list(result.assumptions)}</section>"
        f"<section><h2>Analysis outcome</h2>{_html_outcomes(outcome_values)}</section>"
        f"<section><h2>Evidence</h2>{_html_list(evidence_text)}</section>"
        f"<section><h2>Warnings</h2>{_html_list(warning_text)}</section>"
        f"<section><h2>Limitations</h2>{_html_list(result.limitations)}</section>"
        "</article>"
    )
    return RiskReport(
        analysis_id=analysis_id,
        snapshot_id=result.snapshot_id,
        methodology=AnalysisMethod.RISK_REPORT,
        horizon=result.horizon,
        sample_period=result.sample_period,
        observation_count=result.observation_count,
        assumptions=result.assumptions,
        warnings=result.warnings,
        limitations=result.limitations,
        evidence=result.evidence,
        title=title,
        source_output_digest=result.output_digest or "",
        markdown=markdown,
        html=html,
    )
