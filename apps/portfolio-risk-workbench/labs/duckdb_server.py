"""Local read-only CRSP/Compustat query service for the thesis prototype."""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import statistics
import threading
import time
from datetime import date, datetime, timedelta, timezone
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
    capability_platform_manifest,
    compile_blueprint,
    delete_agent_run,
    _keychain_key,
    _scenario_context,
    list_agent_runs,
    load_agent_run,
    plan_blueprint,
    plan_blueprint_section,
    run_blueprint,
    run_output_pass,
    risk_agent_templates,
    runtime_status,
)
from workflow_cycle_runtime import workflow_cycle_manager


SQL_AGENT_MODEL = "gpt-5.6-luna"
SQL_AGENT_REASONING_EFFORT = "low"
MAX_QUERY_ROWS = 10_000
MAX_QUERY_COLUMNS = 200
QUERY_TIMEOUT_SECONDS = 20

LAB_RUNTIME_BOUNDARY: dict[str, Any] = {
    "profile": {
        "id": "development",
        "label": "Development",
        "development_controls": True,
    },
    "external_effects": "disabled",
    "views": {
        "dataset.live": {
            "data": "Licensed local historical data · query-specific point-in-time checks",
            "authority": "Read-only · no synthetic fallback · external effects prohibited",
            "persistence": "Unsaved browser result · CSV export is not published",
        },
        "dataset.synthetic": {
            "data": "Synthetic behavior fixture · not empirical evidence",
            "authority": "Read-only test path · external effects prohibited",
            "persistence": "Unsaved browser result · not a registry asset",
        },
        "portfolio": {
            "data": "Instrument origin shown in the builder · verify before use",
            "authority": "Prototype constraints only · no mandate authority",
            "persistence": "Browser-local draft · not published",
        },
        "agent.synthetic_fixture": {
            "data": "Synthetic behavior fixture · exact input preview required",
            "authority": "Findings and proposals only · effects none",
            "persistence": "Temporary local run · deletable · not published",
        },
        "agent.real_duckdb": {
            "data": "Licensed local historical data · point-in-time qualified per run",
            "authority": "Model interpretation is effect-free · review required",
            "persistence": "Temporary local run · deletable · rights restricted",
        },
        "graph": {
            "data": "Browser-local agent drafts and registered catalogue previews",
            "authority": "Compiled plan preview · not registered or executable",
            "persistence": "Browser-local draft · not published",
        },
        "cycle": {
            "data": "Mixed · licensed daily anchors + simulated seeded intraday",
            "authority": "Findings and decision proposals only · effects none",
            "persistence": "In-memory session · lost when the service restarts",
        },
        "full": {
            "data": "Synthetic browser experiment · selected inputs must be inspected",
            "authority": "Simulated PortfolioEvents only · external effects prohibited",
            "persistence": "Unsaved browser state · not persistent",
        },
    },
}

# Luna receives a deliberately small, question-specific projection of the physical
# catalog.  The Parquet files remain fully queryable by DuckDB, while routine model
# calls avoid sending the 1,500+ mostly cryptic Compustat field names on every turn.
SQL_TABLE_HINTS: dict[str, tuple[str, ...]] = {
    "stocknames": (
        "company", "companies", "company name", "security name", "ticker",
        "listing", "exchange", "cusip", "sic", "share class", "identity",
    ),
    "dsf": (
        "daily", "day", "price", "return", "volume", "bid", "ask", "trade",
        "market data", "shares outstanding",
    ),
    "msf": (
        "monthly", "month", "monthly price", "monthly return", "monthly volume",
    ),
    "funda": (
        "annual", "yearly", "fiscal year", "fundamental", "fundamentals",
        "financial statement", "assets", "liabilities", "revenue", "sales",
        "income", "profit", "cash", "debt", "ebit", "ebitda", "capex",
        "research and development", "compustat",
    ),
    "fundq": (
        "quarter", "quarterly", "earnings", "fiscal quarter", "report date",
        "assets", "liabilities", "revenue", "sales", "income", "cash", "debt",
    ),
    "ccm_lookup": (
        "sector", "industry", "gics", "naics", "classification", "map", "mapping",
        "company lookup", "gvkey", "permno", "crsp compustat",
    ),
    "ccmxpf_linktable": (
        "link history", "link table", "link type", "link primary", "point in time link",
    ),
    "dsedelist": (
        "delist", "delisted", "delisting", "delisting return", "delisting code",
    ),
}

SQL_BASE_COLUMNS: dict[str, tuple[str, ...]] = {
    "stocknames": (
        "permno", "permco", "namedt", "nameenddt", "ticker", "comnam", "cusip",
        "ncusip", "exchcd", "shrcd", "siccd",
    ),
    "dsf": (
        "permno", "permco", "date", "prc", "openprc", "ret", "retx", "vol",
        "shrout", "bid", "ask", "bidlo", "askhi", "numtrd", "cfacpr", "cfacshr",
    ),
    "msf": (
        "permno", "permco", "date", "prc", "altprc", "ret", "retx", "vol",
        "shrout", "bid", "ask", "bidlo", "askhi", "spread", "cfacpr", "cfacshr",
    ),
    "funda": (
        "gvkey", "datadate", "fyear", "fyr", "tic", "cusip", "conm", "indfmt",
        "consol", "popsrc", "datafmt", "curcd", "costat",
    ),
    "fundq": (
        "gvkey", "datadate", "fyearq", "fqtr", "fyr", "tic", "cusip", "conm",
        "rdq", "fdateq", "indfmt", "consol", "popsrc", "datafmt", "curcdq",
    ),
    "ccm_lookup": (
        "gvkey", "lpermno", "lpermco", "linkdt", "linkenddt", "conm", "tic",
        "cusip", "cik", "sic", "naics", "gind", "gsubind", "year1", "year2",
    ),
    "ccmxpf_linktable": (
        "gvkey", "lpermno", "lpermco", "linkdt", "linkenddt", "linkprim",
        "linktype", "usedflag", "liid",
    ),
    "dsedelist": (
        "permno", "permco", "dlstdt", "dlstcd", "dlret", "dlretx", "dlprc",
        "dlamt", "nwperm", "nwcomp", "nextdt", "cusip",
    ),
}

SQL_METRIC_COLUMNS: dict[str, tuple[str, str]] = {
    "assets": ("at", "atq"),
    "total assets": ("at", "atq"),
    "liabilities": ("lt", "ltq"),
    "total liabilities": ("lt", "ltq"),
    "revenue": ("revt", "revtq"),
    "sales": ("sale", "saleq"),
    "net income": ("ni", "niq"),
    "operating income": ("oiadp", "oiadpq"),
    "ebitda": ("ebitda", "oibdpq"),
    "ebit": ("ebit", "oiadpq"),
    "cash": ("che", "cheq"),
    "long term debt": ("dltt", "dlttq"),
    "long-term debt": ("dltt", "dlttq"),
    "current debt": ("dlc", "dlcq"),
    "capital expenditure": ("capx", "capxy"),
    "capex": ("capx", "capxy"),
    "research and development": ("xrd", "xrdq"),
    "r&d": ("xrd", "xrdq"),
    "shareholders equity": ("seq", "seqq"),
    "book equity": ("ceq", "ceqq"),
    "shares outstanding": ("csho", "cshoq"),
    "market value": ("mkvalt", "mkvaltq"),
    "earnings per share": ("epspx", "epspxq"),
    "eps": ("epspx", "epspxq"),
    "operating cash flow": ("oancf", "oancfy"),
    "cash flow": ("oancf", "oancfy"),
    "gross profit": ("gp", "gpy"),
    "cost of goods sold": ("cogs", "cogsq"),
    "working capital": ("wcap", "wcapq"),
    "receivables": ("rect", "rectq"),
    "inventory": ("invt", "invtq"),
    "goodwill": ("gdwl", "gdwlq"),
    "intangibles": ("intan", "intanq"),
    "employees": ("emp", "emp"),
}

DISALLOWED_SQL_PATTERNS = (
    r"\b(attach|call|copy|create|delete|detach|drop|export|import|insert|install|load|merge|pragma|replace|reset|set|truncate|update|vacuum)\b",
    r"\b(read_[a-z0-9_]*|scan_[a-z0-9_]*|glob|query|query_table|parquet_scan|sqlite_scan|postgres_scan)\s*\(",
    r"\b(duckdb_[a-z0-9_]*|pragma_[a-z0-9_]*)\s*\(",
    r"https?://|s3://|\\|\.\./|\.parquet\b|\.csv\b|\.duckdb\b",
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

GICS_SECTOR_NAMES = {
    "10": "Energy",
    "15": "Materials",
    "20": "Industrials",
    "25": "Consumer Discretionary",
    "30": "Consumer Staples",
    "35": "Health Care",
    "40": "Financials",
    "45": "Information Technology",
    "50": "Communication Services",
    "55": "Utilities",
    "60": "Real Estate",
}


class PortfolioQueryRequest(BaseModel):
    portfolio_id: str = Field(min_length=1, max_length=64)
    as_of: date
    datasets: list[Literal["market", "fundamental", "identity", "links"]] = Field(
        min_length=1, max_length=4
    )
    market_source: Literal["dsf", "msf"] = "dsf"
    include_native_ids: bool = False


class NaturalLanguageQueryRequest(BaseModel):
    question: str = Field(min_length=3, max_length=1000)


class SqlOnlyPlan(BaseModel):
    sql: str = Field(min_length=8, max_length=20_000)


class AgentInputPreviewRequest(BaseModel):
    data_mode: Literal["synthetic_fixture", "real_duckdb"] = "synthetic_fixture"
    scenario: Literal["routine", "concentration", "loss", "missing"] = "concentration"
    portfolio_id: str | None = Field(default=None, max_length=80)
    as_of: date | None = None
    datasets: list[Literal["market", "fundamental", "identity", "links"]] = Field(
        default_factory=lambda: ["market", "fundamental", "identity", "links"],
        min_length=1,
        max_length=4,
    )


class WorkflowCycleCreateRequest(BaseModel):
    portfolio_id: str = Field(min_length=1, max_length=80)
    start_date: date
    end_date: date
    seed: int = Field(default=20260802, ge=0, le=2_147_483_647)
    speed: float = Field(default=60, ge=1, le=3600)
    daily_loss_limit: float = Field(default=0.02, gt=0, le=0.25)


class WorkflowCycleControlRequest(BaseModel):
    action: Literal["start", "pause", "set_speed"]
    speed: float | None = Field(default=None, ge=1, le=3600)


class WorkflowCycleDecisionRequest(BaseModel):
    outcome: Literal["accepted", "investigate", "rejected"]


class WorkflowCycleAgentAttachRequest(BaseModel):
    page_id: str = Field(min_length=1, max_length=80)
    agent_id: str = Field(min_length=1, max_length=120)


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
        self.parser_connection = duckdb.connect(":memory:")
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
        self._register_query_views()

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

    def _register_query_views(self) -> None:
        with self.lock:
            for dataset in DATASETS:
                path_literal = self.path(dataset).replace("'", "''")
                self.connection.execute(
                    f"CREATE VIEW {dataset} AS "
                    f"SELECT * FROM read_parquet('{path_literal}')"
                )

    def sql_agent_catalog(self, question: str) -> tuple[str, dict[str, Any]]:
        """Return a deterministic, question-specific catalog projection for Luna."""

        normalized = re.sub(r"\s+", " ", question.casefold()).strip()
        tokens = set(re.findall(r"[a-z][a-z0-9_]{1,}", normalized))
        catalog_by_name = {item["dataset"]: item for item in self.catalog}
        scores: dict[str, int] = {name: 0 for name in DATASETS}
        matched_hints: dict[str, list[str]] = {name: [] for name in DATASETS}

        for dataset, hints in SQL_TABLE_HINTS.items():
            if dataset.casefold() in tokens or dataset.casefold() in normalized:
                scores[dataset] += 20
                matched_hints[dataset].append(dataset)
            for hint in hints:
                if hint in normalized:
                    scores[dataset] += 5 if " " in hint else 2
                    matched_hints[dataset].append(hint)

        quarterly = any(term in normalized for term in ("quarter", "quarterly", "fqtr"))
        annual = any(term in normalized for term in ("annual", "yearly", "fiscal year", "fyear"))
        monthly = any(term in normalized for term in ("monthly", "month", "msf"))
        daily = any(term in normalized for term in ("daily", "day", "dsf"))
        if quarterly and not annual:
            scores["fundq"] += 12
            scores["funda"] = 0
        elif annual and not quarterly:
            scores["funda"] += 12
            scores["fundq"] = 0
        elif scores["funda"] and scores["fundq"]:
            # Annual is the less ambiguous default for an unqualified fiscal year.
            scores["funda"] += 3
            scores["fundq"] = max(0, scores["fundq"] - 2)
        if monthly and not daily:
            scores["msf"] += 12
            scores["dsf"] = 0
        elif daily and not monthly:
            scores["dsf"] += 12
            scores["msf"] = 0

        ranked = sorted(scores, key=lambda name: (-scores[name], name))
        selected = [name for name in ranked if scores[name] > 0][:3]
        if not selected:
            selected = ["stocknames", "dsf", "funda", "ccm_lookup"]

        market_selected = any(name in selected for name in ("dsf", "msf"))
        fundamental_selected = any(name in selected for name in ("funda", "fundq"))
        classification_requested = any(
            term in normalized for term in ("sector", "industry", "gics", "naics", "classification")
        )
        if fundamental_selected and not market_selected and "stocknames" in selected:
            # Compustat already carries company name, ticker and CUSIP.
            selected.remove("stocknames")
        companions: list[str] = []
        if market_selected:
            companions.append("stocknames")
        if classification_requested or (market_selected and fundamental_selected):
            companions.append("ccm_lookup")
        for companion in companions:
            if companion not in selected:
                selected.append(companion)
        selected = selected[:4]

        table_blocks: list[str] = []
        routed_columns: dict[str, list[str]] = {}
        for dataset in selected:
            item = catalog_by_name[dataset]
            available = {
                str(column["column_name"]): str(column["column_type"])
                for column in item["columns"]
            }
            requested = list(SQL_BASE_COLUMNS.get(dataset, ()))
            for column_name in available:
                lowered = column_name.casefold()
                explicitly_named = (
                    (len(lowered) >= 3 and lowered in tokens)
                    or f'"{lowered}"' in normalized
                    or f"`{lowered}`" in normalized
                    or f"column {lowered}" in normalized
                )
                if explicitly_named:
                    requested.append(column_name)
            for phrase, (annual_column, quarterly_column) in SQL_METRIC_COLUMNS.items():
                if phrase in normalized:
                    if dataset == "funda":
                        requested.append(annual_column)
                    elif dataset == "fundq":
                        requested.append(quarterly_column)
            if dataset == "funda" and not any(
                phrase in normalized for phrase in SQL_METRIC_COLUMNS
            ):
                requested.extend(("at", "lt", "sale", "revt", "ni", "oiadp", "che", "dltt"))
            if dataset == "fundq" and not any(
                phrase in normalized for phrase in SQL_METRIC_COLUMNS
            ):
                requested.extend(("atq", "ltq", "saleq", "revtq", "niq", "oiadpq", "cheq", "dlttq"))
            columns = list(dict.fromkeys(name for name in requested if name in available))
            routed_columns[dataset] = columns
            rendered_columns = ", ".join(
                f'"{name}" {available[name]}' for name in columns
            )
            guidance = ""
            if dataset == "funda":
                guidance = (
                    "\nDEFAULT COMPANY FILTERS: \"datafmt\" = 'STD', \"consol\" = 'C', "
                    "\"popsrc\" = 'D', \"indfmt\" = 'INDL'. When comparing monetary "
                    "levels across companies, also use one currency such as \"curcd\" = 'USD'."
                )
            elif dataset == "fundq":
                guidance = (
                    "\nDEFAULT COMPANY FILTERS: \"datafmt\" = 'STD', \"consol\" = 'C', "
                    "\"popsrc\" = 'D', \"indfmt\" = 'INDL'. When comparing monetary "
                    "levels across companies, also use one currency such as \"curcdq\" = 'USD'. "
                    "For point-in-time questions, filter COALESCE(\"rdq\", \"fdateq\", "
                    "\"datadate\") to the requested as-of date."
                )
            table_blocks.append(
                f'TABLE "{dataset}" — {item["description"]}\nCOLUMNS {rendered_columns}{guidance}'
            )

        joins = (
            'COMMON JOINS: stocknames.permno = dsf.permno = msf.permno; '
            'ccm_lookup.lpermno = dsf.permno; '
            'ccm_lookup.gvkey = funda.gvkey = fundq.gvkey. '
            'Use date-effective link conditions when the question requires point-in-time mapping.'
        )
        rendered = "\n\n".join((*table_blocks, joins))
        routing = {
            "strategy": "deterministic_question_specific_schema_v1",
            "model_calls": 0,
            "selected_tables": selected,
            "selected_columns": routed_columns,
            "selected_column_count": sum(len(value) for value in routed_columns.values()),
            "physical_column_count": sum(
                int(catalog_by_name[name]["column_count"]) for name in selected
            ),
            "catalog_characters": len(rendered),
            "matched_hints": {
                name: list(dict.fromkeys(matched_hints[name]))
                for name in selected
                if matched_hints[name]
            },
        }
        return rendered, routing

    def validate_generated_sql(self, sql: str) -> str:
        cleaned = sql.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:sql)?\s*", "", cleaned, flags=re.IGNORECASE)
            cleaned = re.sub(r"\s*```$", "", cleaned)
        cleaned = cleaned.strip().rstrip(";").strip()
        if not cleaned:
            raise ValueError("Luna returned an empty query")
        for pattern in DISALLOWED_SQL_PATTERNS:
            if re.search(pattern, cleaned, flags=re.IGNORECASE):
                raise ValueError("query contains an operation outside the read-only boundary")
        with self.lock:
            statements = self.connection.extract_statements(cleaned)
            table_names = self.parser_connection.get_table_names(cleaned)
        if len(statements) != 1 or statements[0].type != duckdb.StatementType.SELECT:
            raise ValueError("exactly one read-only SELECT statement is required")
        unknown_tables = table_names.difference(DATASETS)
        if not table_names or unknown_tables:
            names = ", ".join(sorted(unknown_tables)) or "none"
            raise ValueError(
                f"query must use only the allow-listed datasets; unknown tables: {names}"
            )
        return cleaned

    def execute_generated_sql(self, sql: str) -> dict[str, Any]:
        cleaned = self.validate_generated_sql(sql)
        bounded_sql = (
            "SELECT * FROM (" + cleaned + ") AS luna_query "
            f"LIMIT {MAX_QUERY_ROWS + 1}"
        )
        started = time.perf_counter()
        timer = threading.Timer(QUERY_TIMEOUT_SECONDS, self.connection.interrupt)
        timer.daemon = True
        with self.lock:
            timer.start()
            try:
                relation = self.connection.execute(bounded_sql)
                columns = [item[0] for item in relation.description]
                if len(columns) > MAX_QUERY_COLUMNS:
                    raise ValueError(
                        f"query returned {len(columns)} columns; the maximum is {MAX_QUERY_COLUMNS}"
                    )
                rows = relation.fetchmany(MAX_QUERY_ROWS + 1)
            finally:
                timer.cancel()
        truncated = len(rows) > MAX_QUERY_ROWS
        rows = rows[:MAX_QUERY_ROWS]
        return json_safe(
            {
                "sql": cleaned,
                "columns": columns,
                "rows": rows,
                "row_count": len(rows),
                "column_count": len(columns),
                "truncated": truncated,
                "elapsed_ms": round((time.perf_counter() - started) * 1000, 2),
                "limits": {
                    "rows": MAX_QUERY_ROWS,
                    "columns": MAX_QUERY_COLUMNS,
                    "seconds": QUERY_TIMEOUT_SECONDS,
                },
            }
        )

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
            WHERE permno IN ({markers}) AND date <= ? AND prc IS NOT NULL
            QUALIFY row_number() OVER (
                PARTITION BY permno ORDER BY date DESC
            ) = 1
            """,
            [self.path(source), *permnos, as_of],
        )
        return {int(item["permno"]): item for item in rows}

    def latest_classification(
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
                conm,
                tic,
                sic,
                naics,
                gind,
                gsubind,
                year1,
                year2,
                linkdt,
                linkenddt
            FROM read_parquet(?)
            WHERE CAST(lpermno AS INTEGER) IN ({markers})
              AND linkdt <= ?
              AND (linkenddt IS NULL OR linkenddt >= ?)
              AND (year1 IS NULL OR year1 <= year(?))
              AND (year2 IS NULL OR year2 >= year(?))
            QUALIFY row_number() OVER (
                PARTITION BY CAST(lpermno AS INTEGER)
                ORDER BY year2 DESC NULLS LAST, linkdt DESC
            ) = 1
            """,
            [self.path("ccm_lookup"), *permnos, as_of, as_of, as_of, as_of],
        )
        return {int(item["permno"]): item for item in rows}

    def historical_portfolio_values(
        self,
        bindings: list[dict[str, Any]],
        quantities: dict[str, float],
        included_aliases: set[str],
        cash_total: float,
        as_of: date,
        lookback_days: int = 550,
    ) -> list[dict[str, Any]]:
        included = [
            item for item in bindings if item["instrument_alias"] in included_aliases
        ]
        if not included:
            return []
        permnos = [item["permno"] for item in included]
        alias_by_permno = {
            int(item["permno"]): item["instrument_alias"] for item in included
        }
        rows = self._dict_rows(
            f"""
            SELECT permno, date, abs(prc) AS price
            FROM read_parquet(?)
            WHERE permno IN ({self.placeholders(permnos)})
              AND date BETWEEN ? AND ?
              AND prc IS NOT NULL
            ORDER BY date, permno
            """,
            [
                self.path("dsf"),
                *permnos,
                as_of - timedelta(days=lookback_days),
                as_of,
            ],
        )
        prices_by_date: dict[date, dict[str, float]] = {}
        for row in rows:
            alias = alias_by_permno[int(row["permno"])]
            prices_by_date.setdefault(row["date"], {})[alias] = float(row["price"])
        observations = []
        for observed_at, prices in prices_by_date.items():
            if set(prices) != included_aliases:
                continue
            nav = cash_total + sum(
                quantities[alias] * prices[alias] for alias in included_aliases
            )
            observations.append(
                {"observed_at": observed_at, "portfolio_value": nav}
            )
        return observations[-253:]

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
                age_days = (request.as_of - item["date"]).days if item else None
                quality = (
                    "missing"
                    if item is None
                    else "stale"
                    if age_days is not None and age_days > 10
                    else "eligible"
                )
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
                    "quality": quality,
                    "point_in_time_note": (
                        f"latest non-missing CRSP price is {age_days} calendar days before as-of"
                        if quality == "stale"
                        else "record date is on or before as-of; CRSP source has no publication timestamp"
                        if quality == "eligible"
                        else "no eligible CRSP observation"
                    ),
                }
                if request.include_native_ids:
                    record["native_id"] = {"permno": binding["permno"]}
                records.append(record)

        if "identity" in request.datasets:
            identities = self.latest_identity(bindings, request.as_of)
            classifications = self.latest_classification(bindings, request.as_of)
            for binding in bindings:
                item = identities.get(binding["permno"])
                classification = classifications.get(binding["permno"])
                gics_industry = str(classification.get("gind") or "") if classification else ""
                gics_subindustry = str(classification.get("gsubind") or "") if classification else ""
                sector_code = (gics_subindustry or gics_industry)[:2] or None
                record = {
                    "instrument_alias": binding["instrument_alias"],
                    "dataset": "crsp_stocknames",
                    "observed_at": item["namedt"] if item else classification["linkdt"] if classification else None,
                    "available_at": None,
                    "values": {
                        "ticker": (item["ticker"] if item else None) or (classification["tic"] if classification else None),
                        "company_name": (item["comnam"] if item else None) or (classification["conm"] if classification else None),
                        "exchange_code": item["exchcd"] if item else None,
                        "share_code": item["shrcd"] if item else None,
                        "sic_code": (item["siccd"] if item else None) or (classification["sic"] if classification else None),
                        "naics_code": classification["naics"] if classification else None,
                        "gics_sector_code": sector_code,
                        "gics_sector_name": GICS_SECTOR_NAMES.get(sector_code),
                        "gics_industry_code": gics_industry or None,
                        "gics_subindustry_code": gics_subindustry or None,
                        "name_end_date": item["nameenddt"] if item else None,
                    },
                    "quality": "eligible" if item or classification else "missing",
                    "point_in_time_note": "name/classification interval contains as-of date" if item or classification else "no active name or classification interval",
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


def plan_sql(question: str) -> tuple[str, dict[str, Any]]:
    api_key = _keychain_key(include_value=True)
    if not api_key:
        raise RuntimeError("OpenAI credential is unavailable")
    from openai import OpenAI

    started = time.perf_counter()
    routed_catalog, catalog_routing = data_plane.sql_agent_catalog(question)
    client = OpenAI(api_key=str(api_key))
    response = client.responses.create(
        model=SQL_AGENT_MODEL,
        reasoning={"effort": SQL_AGENT_REASONING_EFFORT},
        store=False,
        tools=[],
        input=[
            {
                "role": "system",
                "content": [
                    {
                        "type": "input_text",
                        "text": (
                            "You are Luna, a narrow DuckDB SQL generator. Your only job is "
                            "to create one read-only SELECT statement answering the user's "
                            "question. Use only the supplied tables and columns. Never use "
                            "file paths, URLs, table functions, external scans, system tables, "
                            "DDL, DML, PRAGMA, COPY, ATTACH, INSTALL, LOAD, or multiple "
                            "statements. Select only useful columns, never more than 200. "
                            "Double-quote every table and column identifier because names "
                            "such as at may be DuckDB keywords. "
                            "Always include a LIMIT no greater than 10000, including for "
                            "aggregate queries. Prefer clear aliases and deterministic ordering "
                            "when ranking. Return only the SQL field required by the schema; "
                            "do not explain, narrate, or interpret results."
                        ),
                    }
                ],
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": json.dumps(
                            {
                                "question": question,
                                "duckdb_catalog": routed_catalog,
                                "hard_limits": {
                                    "rows": MAX_QUERY_ROWS,
                                    "columns": MAX_QUERY_COLUMNS,
                                },
                            },
                            sort_keys=True,
                        ),
                    }
                ],
            },
        ],
        text={
            "format": {
                "type": "json_schema",
                "name": "duckdb_sql_only",
                "strict": True,
                "schema": {
                    "type": "object",
                    "properties": {"sql": {"type": "string"}},
                    "required": ["sql"],
                    "additionalProperties": False,
                },
            }
        },
        max_output_tokens=1200,
    )
    plan = SqlOnlyPlan.model_validate(json.loads(response.output_text))
    usage = getattr(response, "usage", None)
    receipt = {
        "provider": "openai_responses",
        "model": getattr(response, "model", SQL_AGENT_MODEL),
        "reasoning_effort": SQL_AGENT_REASONING_EFFORT,
        "response_id": getattr(response, "id", None),
        "input_tokens": int(getattr(usage, "input_tokens", 0) or 0),
        "output_tokens": int(getattr(usage, "output_tokens", 0) or 0),
        "elapsed_ms": round((time.perf_counter() - started) * 1000, 2),
        "store": False,
        "tools": [],
        "data_shared": "question-specific catalog projection only; no licensed rows",
        "catalog_routing": catalog_routing,
    }
    return plan.sql, receipt


data_plane = ReadOnlyDataPlane()
app = FastAPI(
    title="Portfolio Replay Lab — CRSP/Compustat DuckDB API",
    version="0.1.0",
)


def prepare_agent_input(
    request: AgentInputPreviewRequest,
) -> tuple[dict[str, Any], dict[str, Any]]:
    if request.data_mode == "synthetic_fixture":
        context = _scenario_context(request.scenario)
        return context, {
            "data_mode": "synthetic_fixture",
            "label": f"SYNTHETIC FIXTURE · {request.scenario}",
            "fixture": request.scenario,
            "licensed_data_used": False,
            "point_in_time": False,
            "warning": "Values are deliberately synthetic and must not be interpreted as historical observations.",
        }

    if not request.portfolio_id or not request.as_of:
        raise HTTPException(
            status_code=422,
            detail="real-data testing requires a reviewed portfolio and an as-of date",
        )
    datasets = request.datasets or ["market", "fundamental", "identity", "links"]
    query = data_plane.query_portfolio(
        PortfolioQueryRequest(
            portfolio_id=request.portfolio_id,
            as_of=request.as_of,
            datasets=datasets,
            market_source="dsf",
            include_native_ids=False,
        )
    )
    portfolio = data_plane.portfolios.get(request.portfolio_id)
    if not portfolio:
        raise HTTPException(status_code=404, detail="unknown reviewed portfolio")
    positions = {
        item["instrument_alias"]: float(item["quantity"])
        for item in portfolio["positions"]
    }
    market_records = {
        item["instrument_alias"]: item
        for item in query["records"]
        if item["dataset"] == "crsp_dsf"
    }
    identity_records = {
        item["instrument_alias"]: item
        for item in query["records"]
        if item["dataset"] == "crsp_stocknames"
    }
    base_currency = str(portfolio.get("base_currency") or "USD")
    instrument_labels: dict[str, dict[str, Any]] = {}
    capability_positions = []
    for item in portfolio["positions"]:
        alias = item["instrument_alias"]
        market_record = market_records.get(alias, {})
        identity = identity_records.get(alias, {}).get("values", {})
        company_name = identity.get("company_name") or alias
        instrument_labels[alias] = {
            "company_name": company_name,
            "ticker": identity.get("ticker"),
            "sector": identity.get("gics_sector_name"),
            "sector_code": identity.get("gics_sector_code"),
            "industry_code": identity.get("gics_industry_code"),
            "subindustry_code": identity.get("gics_subindustry_code"),
            "sic_code": identity.get("sic_code"),
            "naics_code": identity.get("naics_code"),
        }
        eligible_price = market_record.get("quality") == "eligible"
        capability_positions.append(
            {
                "instrument_id": alias,
                "display_name": company_name,
                "ticker": identity.get("ticker"),
                "sector": identity.get("gics_sector_name"),
                "quantity": str(item["quantity"]),
                "price": market_record.get("values", {}).get("price") if eligible_price else None,
                "last_known_price": market_record.get("values", {}).get("price"),
                "currency": str(item.get("currency") or base_currency),
                "observed_at": market_record.get("observed_at"),
                "quality": market_record.get("quality", "missing"),
            }
        )
    capability_cash = [
        {
            "currency": str(item.get("currency") or base_currency),
            "amount": str(item.get("amount", 0)),
        }
        for item in portfolio.get("cash", [])
    ]
    position_values: dict[str, float] = {}
    for alias, quantity in positions.items():
        price = market_records.get(alias, {}).get("values", {}).get("price")
        if price is not None and market_records.get(alias, {}).get("quality") == "eligible":
            position_values[alias] = abs(float(price)) * quantity
    cash_total = sum(float(item.get("amount", 0)) for item in portfolio.get("cash", []))
    total_value = cash_total + sum(position_values.values())
    largest_weight = (
        max(position_values.values(), default=0.0) / total_value
        if total_value
        else 0.0
    )
    cash_weight = cash_total / total_value if total_value else 0.0
    eligible_aliases = set(position_values)
    bindings = data_plane.portfolio_bindings(request.portfolio_id)
    historical_values = data_plane.historical_portfolio_values(
        bindings,
        positions,
        eligible_aliases,
        cash_total,
        request.as_of,
    )
    daily_return = None
    if len(historical_values) >= 2:
        previous = historical_values[-2]["portfolio_value"]
        current = historical_values[-1]["portfolio_value"]
        daily_return = current / previous - 1 if previous else None
    excluded_aliases = sorted(set(positions) - eligible_aliases)
    excluded_names = [
        instrument_labels[alias]["company_name"] for alias in excluded_aliases
    ]
    missing_count = len(excluded_aliases)
    context = {
        "as_of_date": request.as_of.isoformat(),
        "portfolio_name": portfolio["title"],
        "portfolio_id": request.portfolio_id,
        "daily_return": daily_return,
        "var_95": None,
        "drawdown": None,
        "largest_weight": largest_weight,
        "cash_weight": cash_weight,
        "stress_loss": None,
        "mandate_status": "requires reviewed MetricPack evaluation",
        "evidence_state": "partial" if missing_count else "complete",
        "issue": (
            f"{len(eligible_aliases)} of {len(positions)} holdings have a current eligible "
            "valuation price. The priced sleeve requires concentration and downside-risk review."
        ),
        "eligible_event": "No governed event/news source was included in this real-data test.",
        "event_context": "Not included",
        "news_context": "Not included",
        "workflow_cycle_id": f"real-{request.portfolio_id}-{request.as_of.isoformat()}",
        "source_mode": "real_duckdb",
        "source_records": query["records"],
        "source_quality_counts": query["quality_counts"],
        "instrument_context": [
            {
                "instrument_id": alias,
                **instrument_labels[alias],
                "valuation_quality": market_records.get(alias, {}).get("quality", "missing"),
                "valuation_date": market_records.get(alias, {}).get("observed_at"),
            }
            for alias in positions
        ],
        "valuation_coverage": {
            "total_holdings": len(positions),
            "priced_holdings": len(eligible_aliases),
            "excluded_holdings": excluded_names,
            "basis": "priced sleeve; excluded holdings were not converted to zero",
        },
        "portfolio_capability_input": {
            "snapshot_id": f"real-{request.portfolio_id}-{request.as_of.isoformat()}",
            "as_of": f"{request.as_of.isoformat()}T23:59:59+00:00",
            "retrieved_at": datetime.now(timezone.utc)
            .replace(microsecond=0)
            .isoformat(),
            "base_currency": base_currency,
            "positions": capability_positions,
            "instrument_labels": instrument_labels,
            "cash_balances": capability_cash,
            "source_id": "local-duckdb-crsp-compustat",
            "source_type": "licensed_local_research_data",
            "source_reference": (
                f"duckdb://portfolio/{request.portfolio_id}?as_of={request.as_of.isoformat()}"
            ),
            "source_label": "Local DuckDB · CRSP/Compustat point-in-time query",
            "source_detail": (
                "Fetched reviewed portfolio quantities and each latest non-missing CRSP "
                "price on or before the selected as-of date, then excluded stale or missing "
                "valuations from canonical calculations."
            ),
            "evidence_id": (
                f"duckdb-evidence:{request.portfolio_id}:{request.as_of.isoformat()}"
            ),
        },
        "metric_pack_input": {
            "analysis_id": f"metric-pack:{request.portfolio_id}:{request.as_of.isoformat()}",
            "snapshot_id": f"priced-sleeve:{request.portfolio_id}:{request.as_of.isoformat()}",
            "as_of": f"{request.as_of.isoformat()}T23:59:59+00:00",
            "base_currency": base_currency,
            "observations": historical_values,
            "included_holdings": [instrument_labels[alias]["company_name"] for alias in sorted(eligible_aliases)],
            "excluded_holdings": excluded_names,
            "coverage": f"{len(eligible_aliases)}/{len(positions)} holdings",
            "source_reference": f"duckdb://portfolio/{request.portfolio_id}/historical-values?as_of={request.as_of.isoformat()}",
            "evidence_id": f"metric-evidence:{request.portfolio_id}:{request.as_of.isoformat()}",
        },
    }
    provenance = {
        "data_mode": "real_duckdb",
        "label": "REAL · point-in-time DuckDB / CRSP-Compustat",
        "licensed_data_used": True,
        "point_in_time": True,
        "portfolio_id": request.portfolio_id,
        "as_of": request.as_of.isoformat(),
        "datasets": datasets,
        "record_count": query["record_count"],
        "position_count": query["position_count"],
        "quality_counts": query["quality_counts"],
        "point_in_time_rule": query["point_in_time_rule"],
        "limitations": [
            "This source-data step does not itself create OverallDefaultContext; the agent runtime assembles it after capability calculation.",
            "CRSP observations do not provide a publication timestamp.",
            "No event or news context is included in this test mode yet.",
        ],
    }
    return json_safe(context), provenance


def prepare_workflow_cycle_configuration(
    request: WorkflowCycleCreateRequest,
) -> dict[str, Any]:
    """Bind reviewed positions to real closes and seal future anchors for simulation."""

    if request.end_date < request.start_date:
        raise HTTPException(status_code=422, detail="end date cannot precede start date")
    if (request.end_date - request.start_date).days > 40:
        raise HTTPException(
            status_code=422,
            detail="the first live-console increment is limited to 40 calendar days",
        )
    portfolio = data_plane.portfolios.get(request.portfolio_id)
    if not portfolio:
        raise HTTPException(status_code=404, detail="unknown reviewed portfolio")
    bindings = data_plane.portfolio_bindings(request.portfolio_id)
    permnos = [item["permno"] for item in bindings]
    rows = data_plane._dict_rows(
        f"""
        SELECT permno, date, abs(prc) AS price
        FROM read_parquet(?)
        WHERE permno IN ({data_plane.placeholders(permnos)})
          AND date BETWEEN ? AND ?
          AND prc IS NOT NULL
        ORDER BY date, permno
        """,
        [
            data_plane.path("dsf"),
            *permnos,
            request.start_date - timedelta(days=120),
            request.end_date,
        ],
    )
    alias_by_permno = {
        int(item["permno"]): item["instrument_alias"] for item in bindings
    }
    prices_by_date: dict[date, dict[str, float]] = {}
    history_by_alias: dict[str, list[tuple[date, float]]] = {
        item["instrument_alias"]: [] for item in bindings
    }
    for row in rows:
        alias = alias_by_permno[int(row["permno"])]
        price = float(row["price"])
        prices_by_date.setdefault(row["date"], {})[alias] = price
        history_by_alias[alias].append((row["date"], price))
    all_dates = sorted(prices_by_date)
    candidate_dates = [
        item for item in all_dates if request.start_date <= item <= request.end_date
    ]
    interval_pairs: list[tuple[date, date]] = []
    for current in candidate_dates:
        prior = next((item for item in reversed(all_dates) if item < current), None)
        if prior is not None:
            interval_pairs.append((prior, current))
    if not interval_pairs:
        raise HTTPException(
            status_code=422,
            detail="the selected range contains no eligible close-to-close interval",
        )
    included_aliases = set(alias_by_permno.values())
    for prior, current in interval_pairs:
        included_aliases &= set(prices_by_date[prior])
        included_aliases &= set(prices_by_date[current])
    if not included_aliases:
        raise HTTPException(
            status_code=422,
            detail="no holding has complete real close anchors across the selected range",
        )
    quantities = {
        item["instrument_alias"]: float(item["quantity"])
        for item in portfolio["positions"]
        if item["instrument_alias"] in included_aliases
    }
    end_bindings = [
        item for item in bindings if item["instrument_alias"] in included_aliases
    ]
    identities = data_plane.latest_identity(end_bindings, request.end_date)
    classifications = data_plane.latest_classification(end_bindings, request.end_date)
    instruments = []
    daily_volatility: dict[str, float] = {}
    for binding in end_bindings:
        alias = binding["instrument_alias"]
        identity = identities.get(binding["permno"], {})
        classification = classifications.get(binding["permno"], {})
        history = history_by_alias[alias]
        returns = [
            math.log(current / prior)
            for (_, prior), (_, current) in zip(history, history[1:])
            if prior > 0 and current > 0
        ]
        estimated = statistics.stdev(returns[-60:]) if len(returns) >= 2 else 0.02
        daily_volatility[alias] = min(max(estimated, 0.005), 0.08)
        instruments.append(
            {
                "instrument_id": alias,
                "display_name": identity.get("comnam")
                or classification.get("conm")
                or alias,
                "ticker": identity.get("ticker") or classification.get("tic"),
                "sector": GICS_SECTOR_NAMES.get(
                    str(classification.get("gsubind") or classification.get("gind") or "")[:2]
                ),
            }
        )
    intervals = [
        {
            "date": current.isoformat(),
            "prior_close_date": prior.isoformat(),
            "open_prices": {
                alias: prices_by_date[prior][alias] for alias in sorted(included_aliases)
            },
            "close_prices": {
                alias: prices_by_date[current][alias] for alias in sorted(included_aliases)
            },
            "daily_volatility": daily_volatility,
            "future_close_sealed": True,
        }
        for prior, current in interval_pairs
    ]
    excluded_aliases = sorted(set(alias_by_permno.values()) - included_aliases)
    return {
        "portfolio_id": request.portfolio_id,
        "portfolio_name": portfolio["title"],
        "base_currency": portfolio.get("base_currency", "USD"),
        "cash": sum(float(item.get("amount", 0)) for item in portfolio.get("cash", [])),
        "quantities": quantities,
        "instruments": instruments,
        "intervals": intervals,
        "seed": request.seed,
        "speed": request.speed,
        "daily_loss_limit": request.daily_loss_limit,
        "excluded_holdings": excluded_aliases,
        "generation_method": "seeded log-price Brownian bridge with real daily close anchors",
        "synthetic_intraday": True,
        "empirical_intraday": False,
    }


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
        "runtime_boundary": LAB_RUNTIME_BOUNDARY,
        "sql_agent": {
            "model": SQL_AGENT_MODEL,
            "reasoning_effort": SQL_AGENT_REASONING_EFFORT,
            "available": bool(_keychain_key()),
            "max_rows": MAX_QUERY_ROWS,
            "max_columns": MAX_QUERY_COLUMNS,
        },
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


@app.post("/api/query/ask")
def ask_database(request: NaturalLanguageQueryRequest) -> dict[str, Any]:
    try:
        sql, receipt = plan_sql(request.question)
        result = data_plane.execute_generated_sql(sql)
        return {
            "question": request.question,
            **result,
            "receipt": receipt,
        }
    except (ValueError, json.JSONDecodeError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except duckdb.Error as error:
        raise HTTPException(
            status_code=422,
            detail=f"DuckDB could not execute the generated query: {error}",
        ) from error
    except Exception as error:
        safe_type = re.sub(r"[^A-Za-z0-9_-]", "_", type(error).__name__)[:64]
        raise HTTPException(
            status_code=502,
            detail=f"Luna SQL generation failed: {safe_type}",
        ) from error


@app.get("/api/agents/runtime")
def agent_runtime() -> dict[str, Any]:
    return runtime_status()


@app.post("/api/workflow-cycle/sessions")
def create_workflow_cycle_session(
    request: WorkflowCycleCreateRequest,
) -> dict[str, Any]:
    configuration = prepare_workflow_cycle_configuration(request)
    session = workflow_cycle_manager.create(configuration)
    return session.snapshot()


@app.get("/api/workflow-cycle/sessions/{session_id}")
def workflow_cycle_session(session_id: str) -> dict[str, Any]:
    try:
        return workflow_cycle_manager.get(session_id).snapshot()
    except KeyError as error:
        raise HTTPException(status_code=404, detail="workflow cycle not found") from error


@app.post("/api/workflow-cycle/sessions/{session_id}/control")
def control_workflow_cycle_session(
    session_id: str, request: WorkflowCycleControlRequest
) -> dict[str, Any]:
    try:
        session = workflow_cycle_manager.get(session_id)
        if request.action == "start":
            session.start()
        elif request.action == "pause":
            session.pause()
        elif request.action == "set_speed":
            if request.speed is None:
                raise HTTPException(status_code=422, detail="set_speed requires speed")
            session.set_speed(request.speed)
        return session.snapshot()
    except KeyError as error:
        raise HTTPException(status_code=404, detail="workflow cycle not found") from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.post("/api/workflow-cycle/sessions/{session_id}/decisions/{decision_id}")
def resolve_workflow_cycle_decision(
    session_id: str,
    decision_id: str,
    request: WorkflowCycleDecisionRequest,
) -> dict[str, Any]:
    try:
        session = workflow_cycle_manager.get(session_id)
        session.resolve_decision(decision_id, request.outcome)
        return session.snapshot()
    except KeyError as error:
        raise HTTPException(status_code=404, detail="session or decision not found") from error


@app.post("/api/workflow-cycle/sessions/{session_id}/agents")
def attach_workflow_cycle_agent(
    session_id: str,
    request: WorkflowCycleAgentAttachRequest,
) -> dict[str, Any]:
    try:
        session = workflow_cycle_manager.get(session_id)
        session.attach_agent(request.page_id, request.agent_id)
        return session.snapshot()
    except KeyError as error:
        raise HTTPException(status_code=404, detail="session or dashboard page not found") from error


@app.delete("/api/workflow-cycle/sessions/{session_id}")
def delete_workflow_cycle_session(session_id: str) -> dict[str, Any]:
    try:
        workflow_cycle_manager.delete(session_id)
        return {"deleted": True, "session_id": session_id}
    except KeyError as error:
        raise HTTPException(status_code=404, detail="workflow cycle not found") from error


@app.get("/api/agents/capability-platform")
def agent_capability_platform() -> dict[str, Any]:
    return capability_platform_manifest()


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


@app.post("/api/agents/input-preview")
def preview_agent_input(request: AgentInputPreviewRequest) -> dict[str, Any]:
    context, provenance = prepare_agent_input(request)
    return {"context": context, "provenance": provenance}


@app.post("/api/agents/run")
def run_agent(request: RunRequest) -> dict[str, Any]:
    try:
        preview_request = AgentInputPreviewRequest(
            data_mode=request.data_mode,
            scenario=request.scenario,
            portfolio_id=request.portfolio_id,
            as_of=date.fromisoformat(request.as_of) if request.as_of else None,
            datasets=request.datasets or ["market", "fundamental", "identity", "links"],
        )
        context, provenance = prepare_agent_input(preview_request)
        hydrated = request.model_copy(
            update={"input_context": context, "input_provenance": provenance}
        )
        return run_blueprint(hydrated)
    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(
            status_code=422,
            detail=f"LangGraph execution failed: {type(error).__name__}: {error}",
        ) from error


@app.get("/api/agents/runs")
def agent_runs() -> dict[str, Any]:
    return {"runs": list_agent_runs()}


@app.get("/api/agents/runs/{run_id}")
def agent_run_detail(run_id: str) -> dict[str, Any]:
    try:
        return load_agent_run(run_id)
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail="agent run not found") from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.delete("/api/agents/runs/{run_id}")
def remove_agent_run(run_id: str) -> dict[str, Any]:
    try:
        return delete_agent_run(run_id)
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail="agent run not found") from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


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
