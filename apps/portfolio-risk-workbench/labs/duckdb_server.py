"""Local read-only CRSP/Compustat query service for the thesis prototype."""

from __future__ import annotations

import argparse
import json
import os
import re
import threading
import time
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Literal

import duckdb
import uvicorn
import yaml
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from agent_studio import (
    AgentBlueprint,
    BlueprintAdviceRequest,
    BlueprintPlanRequest,
    CompileRequest,
    OutputPassRunRequest,
    RunRequest,
    SectionPlanRequest,
    advise_blueprint,
    compile_blueprint,
    plan_blueprint,
    plan_blueprint_section,
    run_blueprint,
    run_output_pass,
    risk_agent_templates,
    runtime_status,
)


def find_private_root(start: Path) -> Path:
    configured_root = os.environ.get("PORTFOLIO_RISK_PRIVATE_DATA_ROOT")
    if configured_root:
        private_root = Path(configured_root).expanduser().resolve()
        if (private_root / "raw").is_dir():
            return private_root
        raise RuntimeError(
            "PORTFOLIO_RISK_PRIVATE_DATA_ROOT must contain a raw directory"
        )
    for candidate in (start, *start.parents):
        private_root = candidate / "private-data" / "crsp-compustat"
        if (private_root / "raw").is_dir():
            return private_root.resolve()
    raise RuntimeError("could not locate the private CRSP/Compustat data root")


PROTOTYPE_ROOT = Path(__file__).resolve().parent
PRIVATE_ROOT = find_private_root(PROTOTYPE_ROOT)
RAW_ROOT = PRIVATE_ROOT / "raw"
SELECTION_ROOT = (
    PRIVATE_ROOT
    / "portfolio-definitions"
    / "portfolio-definitions"
    / "thesis-real-portfolios-day4-v1"
)
SELECTION_PATH = PRIVATE_ROOT / "config" / "portfolio-selection-day4.yaml"
INSTRUMENT_MAP_PATH = SELECTION_ROOT / "private-instrument-map.json"

DATASETS: dict[str, dict[str, Any]] = {
    "stocknames": {
        "file": "stocknames.parquet",
        "date_column": "namedt",
        "description": "CRSP security names and listing metadata",
    },
    "dsf": {
        "file": "dsf.parquet",
        "date_column": "date",
        "description": "CRSP daily security observations",
    },
    "msf": {
        "file": "msf.parquet",
        "date_column": "date",
        "description": "CRSP monthly security observations",
    },
    "funda": {
        "file": "funda.parquet",
        "date_column": "datadate",
        "description": "Compustat annual fundamentals",
    },
    "fundq": {
        "file": "fundq.parquet",
        "date_column": "datadate",
        "description": "Compustat quarterly fundamentals",
    },
    "ccm_lookup": {
        "file": "ccm_lookup.parquet",
        "date_column": "linkdt",
        "description": "CRSP–Compustat company lookup",
    },
    "ccmxpf_linktable": {
        "file": "ccmxpf_linktable.parquet",
        "date_column": "linkdt",
        "description": "CRSP–Compustat point-in-time link table",
    },
    "dsedelist": {
        "file": "dsedelist.parquet",
        "date_column": "dlstdt",
        "description": "CRSP delisting observations",
    },
}


class PortfolioQueryRequest(BaseModel):
    portfolio_id: str = Field(min_length=1, max_length=64)
    as_of: date
    datasets: list[Literal["market", "fundamental", "identity", "links"]] = Field(
        min_length=1, max_length=4
    )
    market_source: Literal["dsf", "msf"] = "dsf"
    include_native_ids: bool = False


def json_safe(value: Any) -> Any:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, dict):
        return {key: json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(item) for item in value]
    return value


class ReadOnlyDataPlane:
    def __init__(self) -> None:
        self.connection = duckdb.connect(":memory:")
        self.connection.execute("SET threads=4")
        self.connection.execute("SET memory_limit='4GB'")
        self.lock = threading.Lock()
        self.selection = yaml.safe_load(SELECTION_PATH.read_text())
        instrument_map = json.loads(INSTRUMENT_MAP_PATH.read_text())
        self.alias_to_permno = {
            item["instrument_alias"]: int(item["permno"])
            for item in instrument_map["instruments"]
        }
        self.permno_to_alias = {
            permno: alias for alias, permno in self.alias_to_permno.items()
        }
        self.portfolios = {
            item["portfolio_id"]: item for item in self.selection["portfolios"]
        }
        self.catalog = self._build_catalog()

    def path(self, dataset: str) -> str:
        definition = DATASETS.get(dataset)
        if not definition:
            raise KeyError(dataset)
        path = (RAW_ROOT / definition["file"]).resolve()
        if path.parent != RAW_ROOT.resolve() or not path.is_file():
            raise RuntimeError(f"dataset file unavailable: {dataset}")
        return str(path)

    def _execute(self, sql: str, parameters: list[Any]) -> tuple[list[str], list[tuple[Any, ...]]]:
        with self.lock:
            relation = self.connection.execute(sql, parameters)
            columns = [item[0] for item in relation.description]
            rows = relation.fetchall()
        return columns, rows

    def _dict_rows(self, sql: str, parameters: list[Any]) -> list[dict[str, Any]]:
        columns, rows = self._execute(sql, parameters)
        return [dict(zip(columns, row, strict=True)) for row in rows]

    def _build_catalog(self) -> list[dict[str, Any]]:
        catalog = []
        for dataset, definition in DATASETS.items():
            path = self.path(dataset)
            date_column = definition["date_column"]
            columns, rows = self._execute(
                f"""
                SELECT
                    count(*) AS row_count,
                    min({date_column}) AS minimum_date,
                    max({date_column}) AS maximum_date
                FROM read_parquet(?)
                """,
                [path],
            )
            summary = dict(zip(columns, rows[0], strict=True))
            schema = self._dict_rows(
                "SELECT column_name, column_type FROM (DESCRIBE SELECT * FROM read_parquet(?))",
                [path],
            )
            catalog.append(
                {
                    "dataset": dataset,
                    "description": definition["description"],
                    "file": definition["file"],
                    "bytes": Path(path).stat().st_size,
                    "row_count": summary["row_count"],
                    "minimum_date": summary["minimum_date"],
                    "maximum_date": summary["maximum_date"],
                    "column_count": len(schema),
                    "columns": schema,
                }
            )
        return json_safe(catalog)

    def public_portfolios(self) -> list[dict[str, Any]]:
        values = []
        for portfolio in self.portfolios.values():
            values.append(
                {
                    "portfolio_id": portfolio["portfolio_id"],
                    "title": portfolio["title"],
                    "base_currency": portfolio["base_currency"],
                    "cash": portfolio["cash"],
                    "positions": [
                        {
                            "instrument_alias": position["instrument_alias"],
                            "quantity": position["quantity"],
                        }
                        for position in portfolio["positions"]
                    ],
                }
            )
        return values

    def portfolio_bindings(self, portfolio_id: str) -> list[dict[str, Any]]:
        portfolio = self.portfolios.get(portfolio_id)
        if not portfolio:
            raise HTTPException(status_code=404, detail="unknown reviewed portfolio")
        bindings = []
        for position in portfolio["positions"]:
            alias = position["instrument_alias"]
            permno = self.alias_to_permno.get(alias)
            if permno is None:
                raise HTTPException(
                    status_code=409,
                    detail=f"approved alias has no private CRSP binding: {alias}",
                )
            bindings.append(
                {
                    "instrument_alias": alias,
                    "quantity": position["quantity"],
                    "permno": permno,
                }
            )
        return bindings

    @staticmethod
    def placeholders(values: list[Any]) -> str:
        return ",".join("?" for _ in values)

    def latest_market(
        self,
        bindings: list[dict[str, Any]],
        as_of: date,
        source: str,
    ) -> dict[int, dict[str, Any]]:
        permnos = [item["permno"] for item in bindings]
        markers = self.placeholders(permnos)
        rows = self._dict_rows(
            f"""
            SELECT permno, date, prc, ret, vol, shrout, cfacpr, cfacshr
            FROM read_parquet(?)
            WHERE permno IN ({markers}) AND date <= ?
            QUALIFY row_number() OVER (
                PARTITION BY permno ORDER BY date DESC
            ) = 1
            """,
            [self.path(source), *permnos, as_of],
        )
        return {int(item["permno"]): item for item in rows}

    def latest_identity(
        self,
        bindings: list[dict[str, Any]],
        as_of: date,
    ) -> dict[int, dict[str, Any]]:
        permnos = [item["permno"] for item in bindings]
        markers = self.placeholders(permnos)
        rows = self._dict_rows(
            f"""
            SELECT permno, ticker, comnam, exchcd, shrcd, siccd, namedt, nameenddt
            FROM read_parquet(?)
            WHERE permno IN ({markers})
              AND namedt <= ?
              AND (nameenddt IS NULL OR nameenddt >= ?)
            QUALIFY row_number() OVER (
                PARTITION BY permno ORDER BY namedt DESC
            ) = 1
            """,
            [self.path("stocknames"), *permnos, as_of, as_of],
        )
        return {int(item["permno"]): item for item in rows}

    def active_links(
        self,
        bindings: list[dict[str, Any]],
        as_of: date,
    ) -> dict[int, dict[str, Any]]:
        permnos = [item["permno"] for item in bindings]
        markers = self.placeholders(permnos)
        rows = self._dict_rows(
            f"""
            SELECT
                CAST(lpermno AS INTEGER) AS permno,
                gvkey,
                linkprim,
                linktype,
                linkdt,
                linkenddt
            FROM read_parquet(?)
            WHERE CAST(lpermno AS INTEGER) IN ({markers})
              AND linkdt <= ?
              AND (linkenddt IS NULL OR linkenddt >= ?)
              AND linktype IN ('LC', 'LU', 'LS')
            QUALIFY row_number() OVER (
                PARTITION BY CAST(lpermno AS INTEGER)
                ORDER BY
                    CASE linkprim WHEN 'P' THEN 0 WHEN 'C' THEN 1 ELSE 2 END,
                    linkdt DESC,
                    gvkey
            ) = 1
            """,
            [self.path("ccmxpf_linktable"), *permnos, as_of, as_of],
        )
        return {int(item["permno"]): item for item in rows}

    def latest_fundamentals(
        self,
        links: dict[int, dict[str, Any]],
        as_of: date,
    ) -> dict[str, dict[str, Any]]:
        gvkeys = sorted({str(item["gvkey"]) for item in links.values()})
        if not gvkeys:
            return {}
        markers = self.placeholders(gvkeys)
        rows = self._dict_rows(
            f"""
            SELECT
                gvkey,
                datadate,
                rdq,
                fdateq,
                COALESCE(rdq, fdateq, datadate) AS available_date,
                fqtr,
                fyearq,
                atq,
                ltq,
                saleq,
                revtq,
                niq,
                oiadpq,
                cheq,
                dlttq,
                dlcq,
                cshoq
            FROM read_parquet(?)
            WHERE gvkey IN ({markers})
              AND COALESCE(rdq, fdateq, datadate) <= ?
              AND datafmt = 'STD'
              AND consol = 'C'
              AND popsrc = 'D'
            QUALIFY row_number() OVER (
                PARTITION BY gvkey
                ORDER BY COALESCE(rdq, fdateq, datadate) DESC, datadate DESC
            ) = 1
            """,
            [self.path("fundq"), *gvkeys, as_of],
        )
        return {str(item["gvkey"]): item for item in rows}

    def query_portfolio(self, request: PortfolioQueryRequest) -> dict[str, Any]:
        started = time.perf_counter()
        bindings = self.portfolio_bindings(request.portfolio_id)
        records: list[dict[str, Any]] = []
        links: dict[int, dict[str, Any]] | None = None

        if "market" in request.datasets:
            market = self.latest_market(bindings, request.as_of, request.market_source)
            for binding in bindings:
                item = market.get(binding["permno"])
                record = {
                    "instrument_alias": binding["instrument_alias"],
                    "dataset": f"crsp_{request.market_source}",
                    "observed_at": item["date"] if item else None,
                    "available_at": None,
                    "values": {
                        "price": abs(item["prc"]) if item and item["prc"] is not None else None,
                        "return": item["ret"] if item else None,
                        "volume": item["vol"] if item else None,
                        "shares_outstanding": item["shrout"] if item else None,
                    },
                    "quality": "eligible" if item else "missing",
                    "point_in_time_note": (
                        "record date is on or before as-of; CRSP source has no publication timestamp"
                        if item
                        else "no eligible CRSP observation"
                    ),
                }
                if request.include_native_ids:
                    record["native_id"] = {"permno": binding["permno"]}
                records.append(record)

        if "identity" in request.datasets:
            identities = self.latest_identity(bindings, request.as_of)
            for binding in bindings:
                item = identities.get(binding["permno"])
                record = {
                    "instrument_alias": binding["instrument_alias"],
                    "dataset": "crsp_stocknames",
                    "observed_at": item["namedt"] if item else None,
                    "available_at": None,
                    "values": {
                        "ticker": item["ticker"] if item else None,
                        "company_name": item["comnam"] if item else None,
                        "exchange_code": item["exchcd"] if item else None,
                        "share_code": item["shrcd"] if item else None,
                        "sic_code": item["siccd"] if item else None,
                        "name_end_date": item["nameenddt"] if item else None,
                    },
                    "quality": "eligible" if item else "missing",
                    "point_in_time_note": "name interval contains as-of date" if item else "no active name interval",
                }
                if request.include_native_ids:
                    record["native_id"] = {"permno": binding["permno"]}
                records.append(record)

        if "links" in request.datasets or "fundamental" in request.datasets:
            links = self.active_links(bindings, request.as_of)

        if "links" in request.datasets:
            for binding in bindings:
                item = links.get(binding["permno"]) if links else None
                record = {
                    "instrument_alias": binding["instrument_alias"],
                    "dataset": "ccmxpf_linktable",
                    "observed_at": item["linkdt"] if item else None,
                    "available_at": None,
                    "values": {
                        "link_primary": item["linkprim"] if item else None,
                        "link_type": item["linktype"] if item else None,
                        "link_end_date": item["linkenddt"] if item else None,
                    },
                    "quality": "eligible" if item else "missing",
                    "point_in_time_note": "link interval contains as-of date" if item else "no eligible CCM link",
                }
                if request.include_native_ids:
                    record["native_id"] = {
                        "permno": binding["permno"],
                        "gvkey": item["gvkey"] if item else None,
                    }
                records.append(record)

        if "fundamental" in request.datasets:
            fundamentals = self.latest_fundamentals(links or {}, request.as_of)
            for binding in bindings:
                link = links.get(binding["permno"]) if links else None
                item = fundamentals.get(str(link["gvkey"])) if link else None
                used_fallback = bool(item and item["rdq"] is None)
                record = {
                    "instrument_alias": binding["instrument_alias"],
                    "dataset": "compustat_fundq",
                    "observed_at": item["datadate"] if item else None,
                    "available_at": item["available_date"] if item else None,
                    "values": {
                        "fiscal_year": item["fyearq"] if item else None,
                        "fiscal_quarter": item["fqtr"] if item else None,
                        "assets": item["atq"] if item else None,
                        "liabilities": item["ltq"] if item else None,
                        "revenue": item["revtq"] if item else None,
                        "sales": item["saleq"] if item else None,
                        "net_income": item["niq"] if item else None,
                        "operating_income": item["oiadpq"] if item else None,
                        "cash": item["cheq"] if item else None,
                        "long_term_debt": item["dlttq"] if item else None,
                        "current_debt": item["dlcq"] if item else None,
                        "shares_outstanding": item["cshoq"] if item else None,
                    },
                    "quality": "fallback_date" if used_fallback else ("eligible" if item else "missing"),
                    "point_in_time_note": (
                        "report date used as availability fallback because rdq is missing"
                        if used_fallback
                        else ("earnings report date is on or before as-of" if item else "no eligible quarterly fundamental")
                    ),
                }
                if request.include_native_ids:
                    record["native_id"] = {
                        "permno": binding["permno"],
                        "gvkey": link["gvkey"] if link else None,
                    }
                records.append(record)

        quality_counts: dict[str, int] = {}
        for record in records:
            quality_counts[record["quality"]] = quality_counts.get(record["quality"], 0) + 1
        elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
        return json_safe(
            {
                "mode": "live_duckdb",
                "portfolio_id": request.portfolio_id,
                "as_of": request.as_of,
                "datasets": request.datasets,
                "position_count": len(bindings),
                "record_count": len(records),
                "quality_counts": quality_counts,
                "elapsed_ms": elapsed_ms,
                "point_in_time_rule": "source observation and known availability date <= as_of",
                "records": records,
            }
        )


data_plane = ReadOnlyDataPlane()
app = FastAPI(
    title="Portfolio Replay Lab — CRSP/Compustat DuckDB API",
    version="0.1.0",
)


@app.get("/api/health")
def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "engine": "duckdb",
        "access": "read_only",
        "bind": "localhost",
        "raw_root": str(RAW_ROOT),
        "datasets": len(data_plane.catalog),
        "reviewed_portfolios": len(data_plane.portfolios),
    }


@app.get("/api/catalog")
def catalog() -> dict[str, Any]:
    return {
        "engine": "duckdb",
        "datasets": data_plane.catalog,
    }


@app.get("/api/portfolios")
def portfolios() -> dict[str, Any]:
    return {
        "selection_id": data_plane.selection["selection_id"],
        "reviewed": data_plane.selection["reviewed"],
        "portfolios": data_plane.public_portfolios(),
    }


@app.post("/api/query/portfolio")
def query_portfolio(request: PortfolioQueryRequest) -> dict[str, Any]:
    try:
        return data_plane.query_portfolio(request)
    except HTTPException:
        raise
    except duckdb.Error as error:
        raise HTTPException(status_code=422, detail=f"DuckDB query failed: {error}") from error


@app.get("/api/agents/runtime")
def agent_runtime() -> dict[str, Any]:
    return runtime_status()


@app.get("/api/agents/templates")
def agent_templates() -> dict[str, Any]:
    return {"agents": risk_agent_templates()}


@app.post("/api/agents/blueprint/validate")
def validate_agent_blueprint(blueprint: AgentBlueprint) -> dict[str, Any]:
    result = compile_blueprint(blueprint, persist=False)
    return {
        "valid": True,
        "blueprint": result["blueprint"],
        "graph": result["graph"],
        "checks": result["checks"],
    }


@app.post("/api/agents/blueprint/plan")
def create_agent_blueprint(request: BlueprintPlanRequest) -> dict[str, Any]:
    try:
        return plan_blueprint(request)
    except Exception as error:
        safe_type = re.sub(r"[^A-Za-z0-9_-]", "_", type(error).__name__)[:64]
        raise HTTPException(
            status_code=502,
            detail=f"OpenAI blueprint planning failed: {safe_type}",
        ) from error


@app.post("/api/agents/blueprint/plan-section")
def create_agent_blueprint_section(request: SectionPlanRequest) -> dict[str, Any]:
    try:
        return plan_blueprint_section(request)
    except Exception as error:
        safe_type = re.sub(r"[^A-Za-z0-9_-]", "_", type(error).__name__)[:64]
        raise HTTPException(
            status_code=502,
            detail=f"OpenAI section planning failed: {safe_type}",
        ) from error


@app.post("/api/agents/advisor")
def review_agent_blueprint(request: BlueprintAdviceRequest) -> dict[str, Any]:
    try:
        return advise_blueprint(request)
    except Exception as error:
        safe_type = re.sub(r"[^A-Za-z0-9_-]", "_", type(error).__name__)[:64]
        raise HTTPException(
            status_code=502,
            detail=f"OpenAI design advisor failed: {safe_type}",
        ) from error


@app.post("/api/agents/compile")
def compile_agent(request: CompileRequest) -> dict[str, Any]:
    try:
        return compile_blueprint(request.blueprint, persist=request.persist)
    except Exception as error:
        raise HTTPException(
            status_code=422,
            detail=f"LangGraph compilation failed: {type(error).__name__}",
        ) from error


@app.post("/api/agents/run")
def run_agent(request: RunRequest) -> dict[str, Any]:
    try:
        return run_blueprint(request)
    except Exception as error:
        raise HTTPException(
            status_code=422,
            detail=f"LangGraph execution failed: {type(error).__name__}: {error}",
        ) from error


@app.post("/api/agents/output-pass")
def run_agent_output_pass(request: OutputPassRunRequest) -> dict[str, Any]:
    try:
        return run_output_pass(request)
    except Exception as error:
        safe_type = re.sub(r"[^A-Za-z0-9_-]", "_", type(error).__name__)[:64]
        raise HTTPException(
            status_code=422,
            detail=f"Structured output pass failed: {safe_type}: {error}",
        ) from error


app.mount("/", StaticFiles(directory=PROTOTYPE_ROOT, html=True), name="prototype")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    arguments = parser.parse_args()
    if arguments.host not in {"127.0.0.1", "localhost"}:
        raise SystemExit("licensed-data service may bind only to localhost")
    uvicorn.run(app, host=arguments.host, port=arguments.port, log_level="info")


if __name__ == "__main__":
    main()
