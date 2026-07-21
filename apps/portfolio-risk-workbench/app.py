"""Local, reviewed FastAPI shell for the Portfolio Risk Workbench."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.responses import HTMLResponse


APPLICATION_STATUS = {
    "application_id": "portfolio-risk-workbench",
    "version": "0.1.0",
    "synthetic_mode": True,
    "external_providers": "disabled",
    "human_review": "required",
}

app = FastAPI(title="Portfolio Risk Workbench", version="0.1.0")


def prototype_page(section: str) -> HTMLResponse:
    return HTMLResponse(
        f"""<!doctype html>
<html lang="en">
  <head><meta charset="utf-8"><title>Portfolio Risk Workbench</title></head>
  <body>
    <main>
      <h1>Portfolio Risk Workbench</h1>
      <h2>{section}</h2>
      <p>Wave 0A is a local synthetic prototype.</p>
      <p>External providers are disabled. This application has no live data,
      live trading, broker connectivity, or investment advice.</p>
      <p>Any future consequential action requires explicit human review.</p>
    </main>
  </body>
</html>"""
    )


@app.get("/")
def home() -> HTMLResponse:
    return prototype_page("Overview")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "healthy"}


@app.get("/plan")
def plan() -> HTMLResponse:
    return prototype_page("Plan")


@app.get("/data")
def data() -> HTMLResponse:
    return prototype_page("Data")


@app.get("/portfolio")
def portfolio() -> HTMLResponse:
    return prototype_page("Portfolio")


@app.get("/findings")
def findings() -> HTMLResponse:
    return prototype_page("Findings")


@app.get("/agents")
def agents() -> HTMLResponse:
    return prototype_page("Agents")


@app.get("/api/status")
def api_status() -> dict[str, str | bool]:
    return APPLICATION_STATUS


@app.post("/actions/status")
def status_action() -> dict[str, str | bool]:
    """Expose the read-only ``risk.workbench.status`` capability."""
    return APPLICATION_STATUS
