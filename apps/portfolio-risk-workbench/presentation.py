"""Bounded Jinja2 presentation helpers for the local Workbench."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

from fastapi.responses import HTMLResponse
from jinja2 import Environment, FileSystemLoader, select_autoescape


APPLICATION_ROOT = Path(__file__).resolve().parent
MISSING_VALUE = "Not available"


@dataclass(frozen=True)
class ProfileView:
    profile_id: str
    label: str
    data_state: str
    description: str
    publication_state: str


PROFILES = {
    "research": ProfileView(
        profile_id="research",
        label="Research profile",
        data_state="Synthetic · reviewed public fixture",
        description="Reproducible research using synthetic or reviewed public evidence only.",
        publication_state="Personal account data is excluded by default.",
    ),
    "personal_portfolio": ProfileView(
        profile_id="personal_portfolio",
        label="Personal portfolio",
        data_state="Private · local · no publication",
        description="Local personal holdings are for monitoring and human review only.",
        publication_state="Private data is never published and no broker is connected.",
    ),
}

NAVIGATION = (
    ("dashboard", "Dashboard", "/"),
    ("portfolio", "Portfolio", "/portfolio"),
    ("risk", "Risk", "/risk"),
    ("findings", "Findings", "/findings"),
    ("alerts", "Alerts", "/alerts"),
    ("data", "Data", "/data"),
    ("providers", "Providers", "/providers"),
    ("research", "Research", "/research"),
    ("notebooks", "Notebooks", "/notebooks"),
    ("agents", "Agents", "/agents"),
    ("plan", "Plan", "/plan"),
    ("settings", "Settings", "/settings"),
)


def profile_view(profile: str) -> ProfileView:
    """Resolve an allowed presentation profile without changing application state."""
    return PROFILES.get(profile, PROFILES["research"])


def display_value(value: object) -> str:
    if value is None or value == "":
        return MISSING_VALUE
    return str(value)


def _decimal(value: object) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def currency(value: object, code: str = "USD") -> str:
    number = _decimal(value)
    if number is None:
        return MISSING_VALUE
    sign = "−" if number < 0 else ""
    return f"{sign}{code} {abs(number):,.2f}"


def percentage(value: object, digits: int = 1) -> str:
    number = _decimal(value)
    if number is None:
        return MISSING_VALUE
    return f"{number * Decimal('100'):.{digits}f}%"


def number(value: object, digits: int = 2) -> str:
    numeric = _decimal(value)
    if numeric is None:
        return MISSING_VALUE
    return f"{numeric:,.{digits}f}"


def bar_width(value: object) -> str:
    """Convert a portfolio weight into a bounded presentation-only CSS width."""
    numeric = _decimal(value)
    if numeric is None:
        return ""
    width = min(Decimal("100"), max(Decimal("0"), abs(numeric) * Decimal("100")))
    return f"{width:f}"


def timestamp(value: object) -> str:
    if value is None or value == "":
        return MISSING_VALUE
    if isinstance(value, datetime):
        parsed = value
    else:
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError:
            return str(value)
    return parsed.strftime("%d %b %Y, %H:%M UTC")


def humanize(value: object) -> str:
    if value is None or value == "":
        return MISSING_VALUE
    return str(value).replace("_", " ").replace(".", " ").title()


environment = Environment(
    loader=FileSystemLoader(APPLICATION_ROOT / "templates"),
    autoescape=select_autoescape(("html", "xml")),
    trim_blocks=True,
    lstrip_blocks=True,
)
environment.filters.update(
    bar_width=bar_width,
    currency=currency,
    display=display_value,
    humanize=humanize,
    number=number,
    percentage=percentage,
    timestamp=timestamp,
)


def render_page(template_name: str, *, active_page: str, profile: str = "research", status_code: int = 200, **context: Any) -> HTMLResponse:
    """Render one semantic page with the persistent profile and safety shell."""
    selected = profile_view(profile)
    common = {
        "active_page": active_page,
        "navigation": NAVIGATION,
        "profile": selected,
        "profile_query": "?" + urlencode({"profile": selected.profile_id}),
    }
    common.update(context)
    return HTMLResponse(environment.get_template(template_name).render(**common), status_code=status_code)
