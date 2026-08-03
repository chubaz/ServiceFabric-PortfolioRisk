"""A deliberately small, deterministic, HTML-safe Markdown renderer."""

from __future__ import annotations

import html
import re

from .models import MarkdownReport


RENDERER_VERSION = "portfolio-risk.safe-markdown/v1"


def _inline(value: str) -> str:
    escaped = html.escape(value, quote=True)
    escaped = re.sub(r"`([^`\n]+)`", r"<code>\1</code>", escaped)
    escaped = re.sub(r"\*\*([^*\n]+)\*\*", r"<strong>\1</strong>", escaped)
    escaped = re.sub(r"(?<!\*)\*([^*\n]+)\*(?!\*)", r"<em>\1</em>", escaped)
    escaped = re.sub(
        r"\[evidence:([A-Za-z0-9._:-]{1,160})\]",
        r'<span class="report-evidence">evidence:\1</span>',
        escaped,
    )
    return escaped


def render_markdown(markdown: str) -> str:
    lines = markdown.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    output: list[str] = []
    paragraph: list[str] = []
    list_kind: str | None = None
    table: list[list[str]] = []

    def flush_paragraph() -> None:
        if paragraph:
            output.append("<p>" + " ".join(_inline(item.strip()) for item in paragraph) + "</p>")
            paragraph.clear()

    def flush_list() -> None:
        nonlocal list_kind
        if list_kind:
            output.append(f"</{list_kind}>")
            list_kind = None

    def flush_table() -> None:
        if not table:
            return
        header, *rows = table
        output.append('<div class="report-table-wrap"><table><thead><tr>')
        output.extend(f"<th>{_inline(cell.strip())}</th>" for cell in header)
        output.append("</tr></thead><tbody>")
        for row in rows:
            output.append("<tr>")
            output.extend(f"<td>{_inline(cell.strip())}</td>" for cell in row)
            output.append("</tr>")
        output.append("</tbody></table></div>")
        table.clear()

    index = 0
    while index < len(lines):
        line = lines[index]
        stripped = line.strip()
        if "|" in stripped and stripped.startswith("|") and stripped.endswith("|"):
            flush_paragraph()
            flush_list()
            cells = stripped[1:-1].split("|")
            if index + 1 < len(lines) and re.fullmatch(r"\s*\|(?:\s*:?-{3,}:?\s*\|)+\s*", lines[index + 1]):
                table.append(cells)
                index += 2
                while index < len(lines):
                    row = lines[index].strip()
                    if not (row.startswith("|") and row.endswith("|")):
                        break
                    table.append(row[1:-1].split("|"))
                    index += 1
                flush_table()
                continue
        if not stripped:
            flush_paragraph()
            flush_list()
            index += 1
            continue
        heading = re.match(r"^(#{1,4})\s+(.+)$", stripped)
        if heading:
            flush_paragraph()
            flush_list()
            level = len(heading.group(1)) + 2
            output.append(f"<h{level}>{_inline(heading.group(2))}</h{level}>")
        elif stripped.startswith("> "):
            flush_paragraph()
            flush_list()
            output.append(f"<blockquote>{_inline(stripped[2:])}</blockquote>")
        else:
            unordered = re.match(r"^[-*]\s+(.+)$", stripped)
            ordered = re.match(r"^\d+[.)]\s+(.+)$", stripped)
            if unordered or ordered:
                flush_paragraph()
                wanted = "ul" if unordered else "ol"
                if list_kind != wanted:
                    flush_list()
                    output.append(f"<{wanted}>")
                    list_kind = wanted
                output.append(f"<li>{_inline((unordered or ordered).group(1))}</li>")
            else:
                flush_list()
                paragraph.append(stripped)
        index += 1
    flush_paragraph()
    flush_list()
    flush_table()
    return "".join(output)


def report_markdown(report: MarkdownReport) -> str:
    lines = [f"# {report.title}", "", f"**As of:** {report.as_of}", ""]
    for section in report.sections:
        lines.extend([f"## {section.title}", "", section.markdown, ""])
    if report.attachments:
        lines.extend(["## Registered attachments", ""])
        for attachment in report.attachments:
            lines.append(
                f"- **{attachment.title}** — {attachment.kind}; artifact "
                f"`{attachment.artifact_id}`; file `{attachment.file_id}`"
            )
    return "\n".join(lines).rstrip() + "\n"


def render_report(report: MarkdownReport) -> str:
    sections = []
    for section in report.sections:
        sections.append(
            f'<section id="report-{html.escape(section.section_id, quote=True)}" '
            f'class="report-document-section severity-{section.severity.value}">'
            f"<header><span>{html.escape(section.title)}</span>"
            f"<small>{section.status.value} · {section.word_count} words</small></header>"
            f'<div class="report-markdown">{render_markdown(section.markdown)}</div>'
            "</section>"
        )
    attachments = ""
    if report.attachments:
        cards = "".join(
            '<li><strong>{}</strong><span>{} · artifact {} · file {}</span><small>{}</small></li>'.format(
                html.escape(item.title), html.escape(item.kind), html.escape(item.artifact_id),
                html.escape(item.file_id), html.escape(item.caption)
            )
            for item in report.attachments
        )
        attachments = f'<section class="report-attachments"><h4>Registered attachments</h4><ul>{cards}</ul></section>'
    return (
        f'<article class="report-document" data-renderer="{RENDERER_VERSION}">'
        f'<header class="report-document-header"><span>{html.escape(report.report_type)}</span>'
        f'<h3>{html.escape(report.title)}</h3><p>{html.escape(report.as_of)}</p></header>'
        + "".join(sections)
        + attachments
        + '<footer><strong>Human review required</strong><span>Effects: none</span></footer></article>'
    )


def with_rendered_html(report: MarkdownReport) -> MarkdownReport:
    payload = report.model_dump(mode="json", exclude={"report_digest"})
    payload["rendered_html"] = render_report(report)
    return MarkdownReport.model_validate(payload)
