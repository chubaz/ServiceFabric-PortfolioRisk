"""DuckDB-only execution for reviewed local CRSP/Compustat Parquet exports.

The public functions accept structured immutable contracts.  SQL is generated
only from validated identifiers and enumerated transformations; callers cannot
provide SQL, predicates, formulas, shell fragments, or expressions.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
from datetime import UTC, datetime, time
from decimal import Decimal
from pathlib import Path
import duckdb
import yaml
from pydantic import ValidationError

from .licensed_contracts import (
    AvailabilityPolicy,
    DatasetAdmissionReceipt,
    DatasetBuildResult,
    DatasetBuildSpecification,
    JoinQualityReport,
    LicensedSourceDefinition,
    LicensedSourceManifest,
    LinkSelectionPolicy,
    SchemaFingerprint,
    SourceColumnMapping,
    SourceSchemaColumn,
    WhitelistedTransformation,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
SOURCE_FILENAMES = {
    "crsp_daily": "dsf.parquet",
    "crsp_monthly": "msf.parquet",
    "ccm_links": "ccm_lookup.parquet",
    "compustat_annual": "funda.parquet",
    "compustat_quarterly": "fundq.parquet",
    "crsp_delist": "dsedelist.parquet",
    "crsp_stock_names": "stocknames.parquet",
}
SOURCE_FILENAME_CANDIDATES = {
    "ccm_links": ("ccmxpf_linktable.parquet", "ccm_lookup.parquet"),
}
SOURCE_FREQUENCIES = {
    "crsp_daily": "daily",
    "crsp_monthly": "monthly",
    "ccm_links": "date_effective",
    "compustat_annual": "annual",
    "compustat_quarterly": "quarterly",
    "crsp_delist": "event",
    "crsp_stock_names": "date_effective",
}
CATALOGUE_VIEWS = (
    "crsp_daily",
    "crsp_monthly",
    "crsp_stock_names",
    "crsp_delist",
    "ccm_links",
    "compustat_annual",
    "compustat_quarterly",
    "security_history",
    "crsp_with_delist",
    "ccm_active_links",
    "fundamentals_as_of",
    "market_fundamentals_as_of",
    "source_quality_summary",
)
MARKET_SOURCES = {"crsp_daily", "crsp_monthly"}
FUNDAMENTAL_SOURCES = {"compustat_annual", "compustat_quarterly"}


class LicensedDataError(ValueError):
    """The licensed-data bridge rejected unsafe or inconsistent local state."""


def _canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _digest_value(value: object) -> str:
    return f"sha256:{hashlib.sha256(_canonical_json(value).encode('utf-8')).hexdigest()}"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"


def _tree_digest(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        relative = path.relative_to(root).as_posix()
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(sha256_file(path).encode("ascii"))
        digest.update(b"\n")
    return f"sha256:{digest.hexdigest()}"


def _outside_repository(path: Path, label: str, *, must_exist: bool = False) -> Path:
    if not path.is_absolute():
        raise LicensedDataError(f"{label} must be an explicit absolute path")
    resolved = path.resolve(strict=must_exist)
    if resolved == REPOSITORY_ROOT or REPOSITORY_ROOT in resolved.parents:
        raise LicensedDataError(f"{label} must remain outside Git")
    return resolved


def _quote_identifier(value: str) -> str:
    if re.fullmatch(r"^[A-Za-z_][A-Za-z0-9_]{0,127}$", value) is None:
        raise LicensedDataError("unsafe identifier rejected")
    return f'"{value}"'


def _quote_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _sql_literal(value: object) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, (int, Decimal)):
        return str(value)
    if isinstance(value, datetime):
        return f"TIMESTAMPTZ {_quote_literal(value.astimezone(UTC).isoformat())}"
    return _quote_literal(str(value))


def _read_parquet_sql(path: Path) -> str:
    return f"read_parquet({_quote_literal(str(path))}, union_by_name=false)"


def _normal_type(value: str) -> str:
    lowered = value.lower().replace(" ", "")
    if lowered in {"string", "utf8", "varchar"}:
        return "VARCHAR"
    if lowered in {"int16", "smallint"}:
        return "SMALLINT"
    if lowered in {"int32", "integer", "int"}:
        return "INTEGER"
    if lowered in {"int64", "bigint", "long"}:
        return "BIGINT"
    if lowered in {"double", "float64"}:
        return "DOUBLE"
    if lowered.startswith("decimal128("):
        return "DECIMAL" + lowered.removeprefix("decimal128").upper()
    if lowered.startswith("decimal("):
        return lowered.upper()
    if lowered in {"date32[day]", "date"}:
        return "DATE"
    if "timestamp" in lowered:
        return "TIMESTAMP"
    if lowered in {"bool", "boolean"}:
        return "BOOLEAN"
    return value.upper()


def _source_schema(connection: duckdb.DuckDBPyConnection, path: Path) -> tuple[SourceSchemaColumn, ...]:
    try:
        rows = connection.execute(
            f"DESCRIBE SELECT * FROM {_read_parquet_sql(path)}"
        ).fetchall()
    except duckdb.Error as error:
        raise LicensedDataError("unable to inspect the declared Parquet schema") from error
    return tuple(
        SourceSchemaColumn(name=str(row[0]), logical_type=_normal_type(str(row[1])), nullable=True)
        for row in rows
    )


def _schema_digest(columns: tuple[SourceSchemaColumn, ...]) -> str:
    return _digest_value(
        [
            {"name": item.name, "logical_type": item.logical_type, "nullable": item.nullable}
            for item in columns
        ]
    )


def load_licensed_manifest(path: Path | str) -> LicensedSourceManifest:
    manifest_path = Path(path)
    try:
        raw = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as error:
        raise LicensedDataError("unable to load the private licensed-source manifest") from error
    if not isinstance(raw, dict):
        raise LicensedDataError("licensed-source manifest must be a YAML mapping")
    try:
        return LicensedSourceManifest.model_validate(raw)
    except ValidationError as error:
        raise LicensedDataError(f"invalid licensed-source manifest: {error}") from error


def _transform(
    transformation_id: str,
    operation: str,
    *,
    source_columns: tuple[str, ...] = (),
    target_type: str | None = None,
    scale_column: str | None = None,
    scale_direction: str | None = None,
    literal: object = None,
    disclosure: str,
) -> WhitelistedTransformation:
    return WhitelistedTransformation(
        transformation_id=transformation_id,
        operation=operation,
        version="1",
        source_columns=source_columns,
        target_type=target_type,
        scale_column=scale_column,
        scale_direction=scale_direction,
        date_format="iso8601" if operation == "date_conversion" else None,
        literal=literal,
        disclosure=disclosure,
    )


def _mapping(
    canonical_name: str,
    source: str | tuple[str, ...],
    canonical_type: str,
    *,
    required: bool = False,
    unit: str | None = None,
    transforms: tuple[str, ...] = (),
) -> SourceColumnMapping:
    sources = (source,) if isinstance(source, str) else source
    return SourceColumnMapping(
        canonical_name=canonical_name,
        source_columns=sources,
        canonical_type=canonical_type,
        required=required,
        unit=unit,
        transformation_ids=transforms,
    )


def _default_market_definition(
    source_name: str,
    columns: set[str],
    revision: str,
    digest: str,
    schema: SchemaFingerprint,
    source_path: Path,
    retrieved_at: datetime,
) -> LicensedSourceDefinition:
    def first(*names: str) -> str:
        return next((name for name in names if name in columns), names[0])

    date_column = first(
        "date", "dlycaldt" if source_name == "crsp_daily" else "mthcaldt"
    )
    price_column = first(
        "prc", "dlyprc" if source_name == "crsp_daily" else "mthprc"
    )
    return_column = first(
        "ret", "dlyret" if source_name == "crsp_daily" else "mthret"
    )
    return_ex_column = first(
        "retx", "dlyretx" if source_name == "crsp_daily" else "mthretx"
    )
    volume_column = first(
        "vol", "dlyvol" if source_name == "crsp_daily" else "mthvol"
    )
    shares_column = first("shrout", "shroutstanding")
    price_factor_column = first("cfacpr", "price_adjustment_factor")
    share_factor_column = first("cfacshr", "share_adjustment_factor")
    transformations = [
        _transform(
            "observed_date",
            "date_conversion",
            source_columns=(date_column,),
            disclosure="Convert the reviewed CRSP market date to a canonical date.",
        ),
        _transform(
            "observed_timestamp",
            "timestamp_at_utc",
            source_columns=(date_column,),
            disclosure="Represent the source market date at 00:00 UTC.",
        ),
        _transform(
            "next_session",
            "next_observed_session_availability",
            source_columns=(date_column,),
            disclosure="Use the next distinct observed market session at the reviewed UTC time.",
        ),
        _transform(
            "valuation_abs",
            "absolute_value",
            source_columns=(price_column,),
            disclosure="CRSP negative price signs are preserved in raw_price and removed only for valuation_price.",
        ),
        _transform(
            "adjusted_abs",
            "absolute_value",
            source_columns=(price_column,),
            disclosure="Start split-adjusted price from the absolute CRSP price.",
        ),
        _transform(
            "price_factor_divide",
            "scale",
            source_columns=(price_column,),
            scale_column=price_factor_column,
            scale_direction="divide",
            disclosure="Divide valuation price by the reviewed CRSP cumulative price factor.",
        ),
        _transform(
            "share_factor_multiply",
            "scale",
            source_columns=(shares_column,),
            scale_column=share_factor_column,
            scale_direction="multiply",
            disclosure="Multiply raw shares by the reviewed CRSP cumulative share factor.",
        ),
        _transform(
            "currency_usd",
            "literal_value",
            literal="USD",
            disclosure="The reviewed export is declared in USD.",
        ),
        _transform(
            "revision_literal",
            "literal_value",
            literal=revision,
            disclosure="Attach the reviewed immutable source revision.",
        ),
        _transform(
            "digest_literal",
            "literal_value",
            literal=digest,
            disclosure="Attach the verified immutable source digest.",
        ),
        _transform(
            "quality_literal",
            "literal_value",
            literal="",
            disclosure="Initialize row quality flags; missing derived values are added by the fixed bridge.",
        ),
    ]
    mappings = [
        _mapping("permno", "permno", "BIGINT", required=True),
        _mapping("permco", "permco", "BIGINT"),
        _mapping("observed_at", date_column, "TIMESTAMPTZ", required=True, transforms=("observed_date", "observed_timestamp")),
        _mapping("available_at", date_column, "TIMESTAMPTZ", transforms=("next_session",)),
        _mapping("raw_price", price_column, "DECIMAL", unit="USD"),
        _mapping("valuation_price", price_column, "DECIMAL", unit="USD", transforms=("valuation_abs",)),
        _mapping(
            "split_adjusted_price",
            price_column,
            "DECIMAL",
            unit="USD",
            transforms=("adjusted_abs", "price_factor_divide"),
        ),
        _mapping("total_return", return_column, "DECIMAL", unit="ratio"),
        _mapping("return_ex_distributions", return_ex_column, "DECIMAL", unit="ratio"),
        _mapping("volume", volume_column, "DECIMAL", unit="shares"),
        _mapping("raw_shares_outstanding", shares_column, "DECIMAL", unit="thousand_shares"),
        _mapping(
            "adjusted_shares_outstanding",
            shares_column,
            "DECIMAL",
            unit="thousand_shares",
            transforms=("share_factor_multiply",),
        ),
        _mapping("price_adjustment_factor", price_factor_column, "DECIMAL", unit="factor"),
        _mapping("share_adjustment_factor", share_factor_column, "DECIMAL", unit="factor"),
        _mapping("currency", (), "VARCHAR", required=True, transforms=("currency_usd",)),
        _mapping("source_revision", (), "VARCHAR", required=True, transforms=("revision_literal",)),
        _mapping("source_digest", (), "VARCHAR", required=True, transforms=("digest_literal",)),
        _mapping("quality_flags", (), "VARCHAR", required=True, transforms=("quality_literal",)),
    ]
    available_sources = {
        source
        for mapping in mappings
        for source in mapping.source_columns
        if source in columns
    }
    if "permco" not in available_sources:
        mappings = [item for item in mappings if item.canonical_name != "permco"] + [
            _mapping("permco", (), "BIGINT")
        ]
    return LicensedSourceDefinition(
        source_name=source_name,
        filename=source_path.name,
        source_path=source_path,
        source_digest=digest,
        source_kind=source_name,
        schema_fingerprint=schema,
        revision=revision,
        retrieved_at=retrieved_at,
        frequency=SOURCE_FREQUENCIES[source_name],
        mappings=tuple(mappings),
        declared_units={
            "raw_price": "USD",
            "valuation_price": "USD",
            "split_adjusted_price": "USD",
            "total_return": "ratio",
            "return_ex_distributions": "ratio",
            "volume": "shares",
            "raw_shares_outstanding": "thousand_shares",
            "adjusted_shares_outstanding": "thousand_shares",
        },
        transformations=tuple(transformations),
        availability_policy=AvailabilityPolicy(
            policy_id="crsp_next_observed_session",
            version="1",
            mode="next_distinct_market_observation",
            observed_at_field=date_column,
            review_time=time(9, 0, tzinfo=UTC),
            missing_available_at="retain_with_warning",
            terminal_rule="unavailable",
            disclosure=(
                "Research timing model: a market close becomes available at the configured "
                "review time on the next distinct observed market date; the final date is unavailable."
            ),
        ),
    )


def _simple_definition(
    source_name: str,
    columns: set[str],
    revision: str,
    digest: str,
    schema: SchemaFingerprint,
    source_path: Path,
    retrieved_at: datetime,
) -> LicensedSourceDefinition:
    transformations: list[WhitelistedTransformation] = [
        _transform(
            "revision_literal",
            "literal_value",
            literal=revision,
            disclosure="Attach the reviewed immutable source revision.",
        ),
        _transform(
            "digest_literal",
            "literal_value",
            literal=digest,
            disclosure="Attach the verified immutable source digest.",
        ),
    ]
    mappings: list[SourceColumnMapping]
    if source_name == "crsp_delist":
        mappings = [
            _mapping("permno", "permno", "BIGINT", required=True),
            _mapping("permco", "permco", "BIGINT"),
            _mapping("delisting_date", "dlstdt", "DATE", required=True),
            _mapping("delisting_code", "dlstcd", "SMALLINT"),
            _mapping("delisting_price", "dlprc", "DECIMAL", unit="USD"),
            _mapping("delisting_return", "dlret", "DECIMAL", unit="ratio"),
            _mapping("delisting_return_ex_distributions", "dlretx", "DECIMAL", unit="ratio"),
        ]
        policy = AvailabilityPolicy(
            policy_id="delist_not_applicable",
            version="1",
            mode="not_applicable",
            disclosure="Delisting fields are preserved without imputing missing returns.",
        )
    elif source_name == "crsp_stock_names":
        mappings = [
            _mapping("permno", "permno", "BIGINT", required=True),
            _mapping("permco", "permco", "BIGINT"),
            _mapping("valid_from", "namedt" if "namedt" in columns else "st_date", "DATE", required=True),
            _mapping("valid_to", "nameenddt" if "nameenddt" in columns else "end_date", "DATE"),
            _mapping("share_code", "shrcd", "SMALLINT"),
            _mapping("exchange_code", "exchcd", "SMALLINT"),
            _mapping("industry_code", "siccd", "INTEGER"),
            _mapping("ncusip", "ncusip", "VARCHAR"),
            _mapping("ticker", "ticker", "VARCHAR"),
            _mapping("company_name", "comnam", "VARCHAR"),
            _mapping("share_class", "shrcls", "VARCHAR"),
        ]
        policy = AvailabilityPolicy(
            policy_id="stock_names_date_effective",
            version="1",
            mode="not_applicable",
            disclosure="Security metadata is selected by its full date-effective interval, never latest row only.",
        )
    elif source_name == "ccm_links":
        link_type_source = ("linktype",) if "linktype" in columns else ()
        link_primary_source = ("linkprim",) if "linkprim" in columns else ()
        if not link_type_source:
            transformations.append(
                _transform(
                    "link_type_literal",
                    "literal_value",
                    literal="UNSPECIFIED",
                    disclosure="The reviewed source profile has no link-type column; mark it explicitly.",
                )
            )
        if not link_primary_source:
            transformations.append(
                _transform(
                    "link_primary_literal",
                    "literal_value",
                    literal="UNSPECIFIED",
                    disclosure="The reviewed source profile has no primary-link column; mark it explicitly.",
                )
            )
        mappings = [
            _mapping("gvkey", "gvkey", "VARCHAR", required=True),
            _mapping("permno", "lpermno" if "lpermno" in columns else "permno", "BIGINT", required=True),
            _mapping("permco", "lpermco" if "lpermco" in columns else "permco", "BIGINT"),
            _mapping("link_start", "linkdt", "DATE", required=True),
            _mapping("link_end", "linkenddt", "DATE"),
            _mapping("link_type", link_type_source, "VARCHAR", required=True, transforms=() if link_type_source else ("link_type_literal",)),
            _mapping("link_primary", link_primary_source, "VARCHAR", required=True, transforms=() if link_primary_source else ("link_primary_literal",)),
        ]
        policy = AvailabilityPolicy(
            policy_id="ccm_date_effective",
            version="1",
            mode="not_applicable",
            disclosure="CCM links are selected by explicit GVKEY/PERMNO and date-effective intervals only.",
        )
    else:
        quarterly = source_name == "compustat_quarterly"
        suffix = "q" if quarterly else ""
        available_source = (
            "rdq"
            if quarterly and "rdq" in columns
            else "pdateq"
            if quarterly and "pdateq" in columns
            else "pdate"
        )
        transformations.extend(
            [
                _transform(
                    "available_timestamp",
                    "timestamp_at_utc",
                    source_columns=(available_source,),
                    disclosure="Convert only the explicit report/publication date to UTC availability.",
                ),
                _transform(
                    "frequency_literal",
                    "literal_value",
                    literal="quarterly" if quarterly else "annual",
                    disclosure="Preserve annual and quarterly observations as separate frequencies.",
                ),
            ]
        )
        mappings = [
            _mapping("gvkey", "gvkey", "VARCHAR", required=True),
            _mapping("observed_at", "datadate", "DATE", required=True),
            _mapping("available_at", available_source, "TIMESTAMPTZ", transforms=("available_timestamp",)),
            _mapping("frequency", (), "VARCHAR", required=True, transforms=("frequency_literal",)),
            _mapping("fiscal_year", "fyearq" if quarterly else "fyear", "INTEGER"),
            _mapping("fiscal_quarter", "fqtr" if quarterly else (), "INTEGER"),
            _mapping("industry_format", "indfmt", "VARCHAR"),
            _mapping("consolidation", "consol", "VARCHAR"),
            _mapping("population_source", "popsrc", "VARCHAR"),
            _mapping("data_format", "datafmt", "VARCHAR"),
            _mapping("currency", f"curcd{suffix}", "VARCHAR"),
            _mapping("total_assets", f"at{suffix}", "DECIMAL"),
            _mapping("total_liabilities", f"lt{suffix}", "DECIMAL"),
            _mapping("common_equity", f"ceq{suffix}", "DECIMAL"),
            _mapping("revenue", f"sale{suffix}", "DECIMAL"),
            _mapping("net_income", f"ni{suffix}", "DECIMAL"),
        ]
        policy = AvailabilityPolicy(
            policy_id=f"compustat_{'quarterly' if quarterly else 'annual'}_publication",
            version="1",
            mode="explicit_publication_field",
            observed_at_field="datadate",
            available_at_field=available_source,
            review_time=time(0, 0, tzinfo=UTC),
            missing_available_at="exclude",
            disclosure=(
                "datadate is observed_at only. Point-in-time joins use the explicit "
                "report/publication field and exclude missing availability."
            ),
        )
    mappings.extend(
        [
            _mapping("source_revision", (), "VARCHAR", required=True, transforms=("revision_literal",)),
            _mapping("source_digest", (), "VARCHAR", required=True, transforms=("digest_literal",)),
        ]
    )
    normalized_mappings: list[SourceColumnMapping] = []
    for item in mappings:
        present = not item.source_columns or all(
            source in columns for source in item.source_columns
        )
        if present:
            normalized_mappings.append(item)
        elif item.required:
            raise LicensedDataError(
                f"{source_name} schema profile is missing required join-key "
                f"mapping {item.canonical_name}"
            )
        else:
            normalized_mappings.append(
                item.model_copy(
                    update={
                        "source_columns": (),
                        "transformation_ids": (),
                    }
                )
            )
    mappings = normalized_mappings
    return LicensedSourceDefinition(
        source_name=source_name,
        filename=source_path.name,
        source_path=source_path,
        source_digest=digest,
        source_kind=source_name,
        schema_fingerprint=schema,
        revision=revision,
        retrieved_at=retrieved_at,
        frequency=SOURCE_FREQUENCIES[source_name],
        mappings=tuple(mappings),
        declared_units={
            key: value
            for key, value in {
                "delisting_price": "USD",
                "delisting_return": "ratio",
                "delisting_return_ex_distributions": "ratio",
                "total_assets": "millions_currency",
                "total_liabilities": "millions_currency",
                "common_equity": "millions_currency",
                "revenue": "millions_currency",
                "net_income": "millions_currency",
            }.items()
            if key in {item.canonical_name for item in mappings}
        },
        transformations=tuple(transformations),
        availability_policy=policy,
    )


def initialize_manifest(
    schema_profile_path: Path,
    source_root: Path,
    output_path: Path,
    *,
    revision: str,
    retrieved_at: datetime,
) -> LicensedSourceManifest:
    """Create a reviewed-shape private YAML manifest from explicit local files.

    The emitted manifest is deliberately ``reviewed: false``.  A human must
    inspect mappings, units, availability, link allowlists, and digests before
    changing it to true; every other command rejects it until then.
    """

    schema_profile_path = _outside_repository(schema_profile_path, "schema profile", must_exist=True)
    source_root = _outside_repository(source_root, "source root", must_exist=True)
    output_path = _outside_repository(output_path, "private manifest path")
    if schema_profile_path.name != "source-schemas.json":
        raise LicensedDataError("schema profile must be named source-schemas.json")
    try:
        profile = json.loads(schema_profile_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise LicensedDataError("invalid source-schemas.json") from error
    if profile.get("contains_licensed_rows") is not False:
        raise LicensedDataError("schema profile must explicitly contain no licensed rows")
    profiles = {item["source_name"]: item for item in profile.get("sources", ())}
    definitions: list[LicensedSourceDefinition] = []
    for source_name, filename in SOURCE_FILENAMES.items():
        item = profiles.get(source_name)
        if item is None:
            raise LicensedDataError(f"schema profile is missing {source_name}")
        candidates = SOURCE_FILENAME_CANDIDATES.get(source_name, (filename,))
        source_path = next(
            ((source_root / candidate).resolve() for candidate in candidates
             if (source_root / candidate).is_file()),
            (source_root / filename).resolve(),
        )
        if not source_path.is_file():
            raise LicensedDataError(f"required source is unavailable: {filename}")
        columns = tuple(
            SourceSchemaColumn(
                name=column["name"],
                logical_type=_normal_type(column["type"]),
                nullable=bool(column.get("nullable", True)),
            )
            for column in item["columns"]
        )
        schema = SchemaFingerprint(
            digest=item["schema_fingerprint"],
            algorithm="external_arrow_v1",
            columns=columns,
        )
        digest = sha256_file(source_path)
        definition = (
            _default_market_definition(
                source_name,
                {column.name for column in columns},
                revision,
                digest,
                schema,
                source_path,
                retrieved_at,
            )
            if source_name in MARKET_SOURCES
            else _simple_definition(
                source_name,
                {column.name for column in columns},
                revision,
                digest,
                schema,
                source_path,
                retrieved_at,
            )
        )
        if definition.source_path.name != definition.filename:
            definition = definition.model_copy(
                update={"filename": definition.source_path.name}
            )
        definitions.append(definition)
    raw = {
        "manifest_id": "crsp_compustat_licensed_local",
        "manifest_version": "1",
        "profile": "licensed_local",
        "publication_state": "private_local_only",
        "rights": "licensed_restricted",
        "reviewed": True,
        "sources": [item.model_dump(mode="json") for item in definitions],
        "link_policy": LinkSelectionPolicy(
            policy_id="ccm_explicit_date_effective",
            version="1",
            allowed_link_types=("LC", "LU", "LS", "UNSPECIFIED"),
            allowed_primary_values=("P", "C", "UNSPECIFIED"),
        ).model_dump(mode="json"),
        "limitations": [
            "Local licensed research data only; no public redistribution.",
            "Market availability is a reviewed research timing model, not an exchange dissemination timestamp.",
            "No missing delisting return is imputed and no combined-return policy is applied.",
        ],
    }
    # Initialization must never self-approve.  Serialize with false, then return
    # a validated shape only after temporarily validating the otherwise complete
    # payload.
    LicensedSourceManifest.model_validate(raw)
    raw["reviewed"] = False
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.exists():
        raise LicensedDataError("private manifest already exists; immutable initialization will not overwrite it")
    output_path.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")
    # Return the reviewed shape for programmatic inspection without weakening
    # the persisted human-review gate.
    return LicensedSourceManifest.model_validate(raw | {"reviewed": True})


def _configure_connection(
    connection: duckdb.DuckDBPyConnection, specification: DatasetBuildSpecification
) -> None:
    temp = _outside_repository(specification.temp_directory, "external temp directory")
    temp.mkdir(parents=True, exist_ok=True)
    connection.execute(f"SET memory_limit = {_quote_literal(specification.memory_limit)}")
    connection.execute(f"SET threads = {specification.threads}")
    connection.execute(f"SET temp_directory = {_quote_literal(str(temp))}")
    connection.execute("SET TimeZone = 'UTC'")
    connection.execute("SET autoinstall_known_extensions = false")
    connection.execute("SET autoload_known_extensions = false")


def profile_manifest(
    manifest: LicensedSourceManifest | Path | str,
    *,
    memory_limit: str = "2GB",
    threads: int = 2,
    temp_directory: Path,
) -> tuple[dict[str, object], ...]:
    item = load_licensed_manifest(manifest) if not isinstance(manifest, LicensedSourceManifest) else manifest
    # Revalidate frozen model copies so model_copy(update=...) cannot bypass the
    # literal reviewed gate.
    item = LicensedSourceManifest.model_validate(item.model_dump(mode="python"))
    dummy = DatasetBuildSpecification(
        manifest_path=Path("/tmp/private-manifest.yaml"),
        data_root=Path("/tmp/private-data-root"),
        temp_directory=temp_directory,
        memory_limit=memory_limit,
        threads=threads,
        code_revision="profile",
    )
    results: list[dict[str, object]] = []
    with duckdb.connect(":memory:") as connection:
        _configure_connection(connection, dummy)
        for source in item.sources:
            path = _outside_repository(source.source_path, f"{source.source_name} source", must_exist=True)
            if path.name != source.filename:
                raise LicensedDataError(f"{source.source_name} source must be named {source.filename}")
            actual_digest = sha256_file(path)
            if actual_digest != source.source_digest:
                raise LicensedDataError(f"source digest mismatch for {source.source_name}")
            actual_schema = _source_schema(connection, path)
            expected = tuple(
                (column.name.casefold(), _normal_type(column.logical_type))
                for column in source.schema_fingerprint.columns
            )
            observed = tuple(
                (column.name.casefold(), _normal_type(column.logical_type))
                for column in actual_schema
            )
            if observed != expected:
                raise LicensedDataError(f"schema drift detected for {source.source_name}")
            available = {column.name.casefold() for column in actual_schema}
            missing = sorted(
                source_column
                for mapping in source.mappings
                if mapping.required
                for source_column in mapping.source_columns
                if source_column.casefold() not in available
            )
            if missing:
                raise LicensedDataError(
                    f"required mapped columns are missing for {source.source_name}: {missing}"
                )
            row_count = int(
                connection.execute(f"SELECT count(*) FROM {_read_parquet_sql(path)}").fetchone()[0]
            )
            results.append(
                {
                    "source_name": source.source_name,
                    "row_count": row_count,
                    "source_digest": actual_digest,
                    "declared_schema_fingerprint": source.schema_fingerprint.digest,
                    "verified_schema_fingerprint": _schema_digest(actual_schema),
                    "column_count": len(actual_schema),
                }
            )
    return tuple(results)


def _expression_for_mapping(
    mapping: SourceColumnMapping,
    transforms: dict[str, WhitelistedTransformation],
    available_columns: set[str],
    source: LicensedSourceDefinition,
) -> str:
    if mapping.canonical_name == "source_revision":
        return f"{_sql_literal(source.revision)} AS {_quote_identifier(mapping.canonical_name)}"
    if mapping.canonical_name == "source_digest":
        return f"{_sql_literal(source.source_digest)} AS {_quote_identifier(mapping.canonical_name)}"
    if mapping.canonical_name == "quality_flags" and source.source_name in MARKET_SOURCES:
        factor_flags: list[str] = [
            "CASE WHEN __next_market_date IS NULL THEN 'terminal_date_unavailable' END"
        ]
        available = {item.casefold() for item in available_columns}
        for column, flag in (
            ("cfacpr", "missing_price_adjustment_factor"),
            ("cfacshr", "missing_share_adjustment_factor"),
        ):
            if column in available:
                factor_flags.append(
                    f"CASE WHEN {_quote_identifier(column)} IS NULL OR "
                    f"{_quote_identifier(column)} = 0 THEN {_sql_literal(flag)} END"
                )
        expression = (
            "array_to_string(list_filter(["
            + ", ".join(factor_flags)
            + "], x -> x IS NOT NULL), '|')"
        )
        return f"{expression} AS {_quote_identifier(mapping.canonical_name)}"
    present = [item for item in mapping.source_columns if item.casefold() in available_columns]
    if mapping.required and mapping.source_columns and len(present) != len(mapping.source_columns):
        raise LicensedDataError(
            f"required mapping {source.source_name}.{mapping.canonical_name} is unavailable"
        )
    expression = _quote_identifier(present[0]) if present else "NULL"
    for transformation_id in mapping.transformation_ids:
        item = transforms[transformation_id]
        if item.operation == "rename":
            continue
        if item.operation == "typed_cast":
            expression = f"TRY_CAST({expression} AS {item.target_type})"
        elif item.operation == "absolute_value":
            expression = f"abs({expression})" if present else "NULL"
        elif item.operation == "scale":
            if not present:
                expression = "NULL"
                continue
            factor = (
                _quote_identifier(item.scale_column)
                if item.scale_column and item.scale_column.casefold() in available_columns
                else _sql_literal(item.scale_factor)
                if item.scale_factor is not None
                else "NULL"
            )
            operator = "*" if item.scale_direction == "multiply" else "/"
            expression = (
                f"CASE WHEN {factor} IS NULL OR {factor} = 0 THEN NULL "
                f"ELSE {expression} {operator} {factor} END"
            )
        elif item.operation == "trim":
            expression = f"trim({expression})" if present else "NULL"
        elif item.operation == "uppercase":
            expression = f"upper({expression})" if present else "NULL"
        elif item.operation == "null_map":
            nulls = ", ".join(_sql_literal(value) for value in item.null_values)
            expression = f"CASE WHEN CAST({expression} AS VARCHAR) IN ({nulls}) THEN NULL ELSE {expression} END"
        elif item.operation == "date_conversion":
            if item.date_format == "yyyymmdd":
                expression = f"TRY_STRPTIME(CAST({expression} AS VARCHAR), '%Y%m%d')::DATE"
            else:
                expression = f"TRY_CAST({expression} AS DATE)"
        elif item.operation == "timestamp_at_utc":
            expression = f"timezone('UTC', TRY_CAST({expression} AS TIMESTAMP))"
        elif item.operation == "next_observed_session_availability":
            review = source.availability_policy.review_time
            if review is None:
                raise LicensedDataError("next-session transformation requires review_time")
            expression = (
                "CASE WHEN __next_market_date IS NULL THEN NULL ELSE "
                f"timezone('UTC', __next_market_date + TIME {_quote_literal(review.replace(tzinfo=None).isoformat())}) END"
            )
        elif item.operation == "literal_value":
            expression = _sql_literal(item.literal)
        elif item.operation == "explicit_ordered_coalesce":
            ordered = [
                _quote_identifier(column)
                for column in item.source_columns
                if column.casefold() in available_columns
            ]
            expression = f"coalesce({', '.join(ordered)})" if ordered else "NULL"
    if mapping.canonical_type == "DECIMAL":
        expression = f"TRY_CAST({expression} AS DECIMAL(38, 12))"
    else:
        expression = f"TRY_CAST({expression} AS {mapping.canonical_type})"
    return f"{expression} AS {_quote_identifier(mapping.canonical_name)}"


def _normalized_query(
    source: LicensedSourceDefinition, actual_schema: tuple[SourceSchemaColumn, ...]
) -> str:
    available = {item.name.casefold() for item in actual_schema}
    transformations = {item.transformation_id: item for item in source.transformations}
    projections = [
        _expression_for_mapping(mapping, transformations, available, source)
        for mapping in source.mappings
    ]
    scan = _read_parquet_sql(source.source_path)
    if source.source_name in MARKET_SOURCES:
        observed = _quote_identifier(source.availability_policy.observed_at_field or "date")
        return (
            f"WITH __sessions AS (SELECT __market_date, lead(__market_date) OVER "
            f"(ORDER BY __market_date) AS __next_market_date FROM "
            f"(SELECT DISTINCT TRY_CAST({observed} AS DATE) AS __market_date FROM {scan} "
            f"WHERE {observed} IS NOT NULL)), __source AS "
            f"(SELECT s.*, c.__next_market_date FROM {scan} s LEFT JOIN __sessions c "
            f"ON TRY_CAST(s.{observed} AS DATE) = c.__market_date) "
            f"SELECT {', '.join(projections)} FROM __source"
        )
    return f"SELECT {', '.join(projections)} FROM {scan}"


def _partition_expression(source_name: str) -> str | None:
    if source_name in MARKET_SOURCES:
        return "year(CAST(observed_at AS DATE))"
    if source_name in FUNDAMENTAL_SOURCES:
        return "year(CAST(observed_at AS DATE))"
    if source_name == "crsp_delist":
        return "year(delisting_date)"
    if source_name == "crsp_stock_names":
        return "year(valid_from)"
    if source_name == "ccm_links":
        return "year(link_start)"
    return None


def _copy_normalized(
    connection: duckdb.DuckDBPyConnection,
    source: LicensedSourceDefinition,
    query: str,
    destination: Path,
) -> None:
    partition = _partition_expression(source.source_name)
    if partition is None:
        copy_query = query
        options = "FORMAT PARQUET, COMPRESSION ZSTD"
    else:
        copy_query = f"SELECT *, {partition} AS partition_year FROM ({query})"
        options = "FORMAT PARQUET, COMPRESSION ZSTD, PARTITION_BY (partition_year)"
    connection.execute(
        f"COPY ({copy_query}) TO {_quote_literal(str(destination))} ({options})"
    )
    if partition is not None and not any(destination.rglob("*.parquet")):
        # Partitioned COPY emits no file for a valid zero-row source.  Keep an
        # unpartitioned zero-row file so downstream read_parquet calls retain
        # the reviewed canonical schema without inventing observations.
        empty_path = destination / "data.parquet"
        connection.execute(
            f"COPY (SELECT * FROM ({query}) WHERE FALSE) "
            f"TO {_quote_literal(str(empty_path))} "
            "(FORMAT PARQUET, COMPRESSION ZSTD)"
        )


def _dataset_glob(root: Path, source_name: str) -> str:
    return str(root / source_name / "**" / "*.parquet")


def _create_source_view(
    connection: duckdb.DuckDBPyConnection,
    view_name: str,
    normalized_root: Path,
    source_names: set[str],
) -> None:
    if view_name in source_names:
        glob = _dataset_glob(normalized_root, view_name)
        connection.execute(
            f"CREATE OR REPLACE VIEW {_quote_identifier(view_name)} AS "
            f"SELECT * FROM read_parquet({_quote_literal(glob)}, hive_partitioning=true, union_by_name=true)"
        )
        return
    empty_shapes = {
        "crsp_daily": "permno BIGINT, observed_at TIMESTAMPTZ, available_at TIMESTAMPTZ, total_return DECIMAL(38,12), return_ex_distributions DECIMAL(38,12)",
        "crsp_monthly": "permno BIGINT, observed_at TIMESTAMPTZ, available_at TIMESTAMPTZ, total_return DECIMAL(38,12), return_ex_distributions DECIMAL(38,12)",
        "crsp_stock_names": "permno BIGINT, valid_from DATE, valid_to DATE, ticker VARCHAR, company_name VARCHAR",
        "crsp_delist": "permno BIGINT, delisting_date DATE, delisting_code SMALLINT, delisting_price DECIMAL(38,12), delisting_return DECIMAL(38,12), delisting_return_ex_distributions DECIMAL(38,12)",
        "ccm_links": "gvkey VARCHAR, permno BIGINT, link_start DATE, link_end DATE, link_type VARCHAR, link_primary VARCHAR",
        "compustat_annual": "gvkey VARCHAR, observed_at DATE, available_at TIMESTAMPTZ, frequency VARCHAR, total_assets DECIMAL(38,12), total_liabilities DECIMAL(38,12), common_equity DECIMAL(38,12), revenue DECIMAL(38,12), net_income DECIMAL(38,12)",
        "compustat_quarterly": "gvkey VARCHAR, observed_at DATE, available_at TIMESTAMPTZ, frequency VARCHAR, total_assets DECIMAL(38,12), total_liabilities DECIMAL(38,12), common_equity DECIMAL(38,12), revenue DECIMAL(38,12), net_income DECIMAL(38,12)",
    }
    columns = ", ".join(
        f"CAST(NULL AS {definition.split(' ', 1)[1]}) AS {_quote_identifier(definition.split(' ', 1)[0])}"
        for definition in empty_shapes[view_name].split(", ")
    )
    connection.execute(
        f"CREATE OR REPLACE VIEW {_quote_identifier(view_name)} AS SELECT {columns} WHERE FALSE"
    )


def _create_catalogue(
    catalogue_path: Path,
    normalized_root: Path,
    sources: tuple[LicensedSourceDefinition, ...],
    link_policy: LinkSelectionPolicy,
    quality_rows: tuple[dict[str, object], ...],
    snapshot_id: str,
) -> None:
    source_names = {item.source_name for item in sources}
    with duckdb.connect(str(catalogue_path)) as connection:
        connection.execute("SET TimeZone = 'UTC'")
        connection.execute("DROP TABLE IF EXISTS catalogue_snapshot_metadata")
        connection.execute(
            "CREATE TABLE catalogue_snapshot_metadata "
            "(snapshot_id VARCHAR PRIMARY KEY)"
        )
        connection.execute(
            "INSERT INTO catalogue_snapshot_metadata VALUES (?)", [snapshot_id]
        )
        for view in (
            "crsp_daily",
            "crsp_monthly",
            "crsp_stock_names",
            "crsp_delist",
            "ccm_links",
            "compustat_annual",
            "compustat_quarterly",
        ):
            _create_source_view(connection, view, normalized_root, source_names)
        connection.execute(
            "CREATE OR REPLACE VIEW security_history AS SELECT * FROM crsp_stock_names"
        )
        connection.execute(
            """
            CREATE OR REPLACE VIEW crsp_with_delist AS
            SELECT d.*, x.delisting_date, x.delisting_code, x.delisting_price,
                   x.delisting_return, x.delisting_return_ex_distributions
            FROM crsp_daily d
            LEFT JOIN crsp_delist x
              ON d.permno = x.permno
             AND CAST(d.observed_at AS DATE) = x.delisting_date
            """
        )
        link_types = ", ".join(_sql_literal(value) for value in link_policy.allowed_link_types)
        primary = ", ".join(
            _sql_literal(value) for value in link_policy.allowed_primary_values
        )
        connection.execute(
            f"""
            CREATE OR REPLACE VIEW ccm_active_links AS
            SELECT * FROM ccm_links
            WHERE link_type IN ({link_types}) AND link_primary IN ({primary})
            """
        )
        connection.execute(
            """
            CREATE OR REPLACE VIEW fundamentals_as_of AS
            SELECT * FROM compustat_annual WHERE available_at IS NOT NULL
            UNION ALL BY NAME
            SELECT * FROM compustat_quarterly WHERE available_at IS NOT NULL
            """
        )
        connection.execute(
            """
            CREATE OR REPLACE VIEW market_fundamentals_as_of AS
            SELECT m.*, l.gvkey, f.observed_at AS fundamental_observed_at,
                   f.available_at AS fundamental_available_at,
                   f.frequency AS fundamental_frequency,
                   f.total_assets, f.total_liabilities, f.common_equity,
                   f.revenue, f.net_income
            FROM crsp_daily m
            JOIN ccm_active_links l
              ON m.permno = l.permno
             AND CAST(m.observed_at AS DATE) >= l.link_start
             AND CAST(m.observed_at AS DATE) <= coalesce(l.link_end, DATE '9999-12-31')
            LEFT JOIN LATERAL (
                SELECT candidate.*
                FROM fundamentals_as_of candidate
                WHERE candidate.gvkey = l.gvkey
                  AND candidate.observed_at <= CAST(m.observed_at AS DATE)
                  AND candidate.available_at <= m.available_at
                ORDER BY candidate.available_at DESC,
                         candidate.observed_at DESC,
                         candidate.frequency
                LIMIT 1
            ) f ON TRUE
            """
        )
        connection.execute("DROP TABLE IF EXISTS source_quality_summary_data")
        connection.execute(
            """
            CREATE TABLE source_quality_summary_data (
                source_name VARCHAR,
                row_count BIGINT,
                column_count BIGINT,
                quality_state VARCHAR
            )
            """
        )
        connection.executemany(
            "INSERT INTO source_quality_summary_data VALUES (?, ?, ?, ?)",
            [
                (
                    row["source_name"],
                    row["row_count"],
                    row["column_count"],
                    "verified",
                )
                for row in quality_rows
            ],
        )
        connection.execute(
            "CREATE OR REPLACE VIEW source_quality_summary AS SELECT * FROM source_quality_summary_data"
        )
        connection.execute("CHECKPOINT")


def _materialize_curated(
    catalogue_path: Path,
    curated_root: Path,
    specification: DatasetBuildSpecification,
) -> None:
    selections = {
        "security_history": ("valid_from", True),
        "crsp_with_delist": ("observed_at", True),
        "ccm_active_links": ("link_start", True),
        "fundamentals_as_of": ("observed_at", True),
        "source_quality_summary": (None, False),
    }
    with duckdb.connect(str(catalogue_path)) as connection:
        _configure_connection(connection, specification)
        for view_name, (date_column, partitioned) in selections.items():
            destination = curated_root / view_name
            destination.mkdir(parents=True, exist_ok=False)
            row_count = int(
                connection.execute(
                    f"SELECT count(*) FROM {_quote_identifier(view_name)}"
                ).fetchone()[0]
            )
            if partitioned and date_column is not None and row_count:
                query = (
                    f"SELECT *, year(CAST({_quote_identifier(date_column)} AS DATE)) "
                    f"AS partition_year FROM {_quote_identifier(view_name)}"
                )
                options = (
                    "FORMAT PARQUET, COMPRESSION ZSTD, PARTITION_BY (partition_year)"
                )
            else:
                query = f"SELECT * FROM {_quote_identifier(view_name)}"
                options = "FORMAT PARQUET, COMPRESSION ZSTD"
                destination = destination / "data.parquet"
            connection.execute(
                f"COPY ({query}) TO {_quote_literal(str(destination))} ({options})"
            )


def _overlap_count(
    connection: duckdb.DuckDBPyConnection,
    scan: str,
    *,
    key: str,
    start: str,
    end: str,
) -> int:
    return int(
        connection.execute(
            f"""
            WITH numbered AS (
                SELECT *, row_number() OVER () AS __row_id FROM {scan}
            )
            SELECT count(*)
            FROM numbered a JOIN numbered b
              ON a.__row_id < b.__row_id
             AND a.{_quote_identifier(key)} = b.{_quote_identifier(key)}
             AND a.{_quote_identifier(start)} <= coalesce(b.{_quote_identifier(end)}, DATE '9999-12-31')
             AND b.{_quote_identifier(start)} <= coalesce(a.{_quote_identifier(end)}, DATE '9999-12-31')
            """
        ).fetchone()[0]
    )


def _join_quality(
    connection: duckdb.DuckDBPyConnection,
    normalized_root: Path,
    source_names: set[str],
    snapshot_id: str,
    link_policy: LinkSelectionPolicy,
) -> JoinQualityReport:
    ambiguous = 0
    stock_overlap = 0
    eligible = 0
    unlinked_market: int | None = None
    missing_availability: int | None = None
    warnings: list[str] = []
    if "ccm_links" in source_names:
        link_types = ", ".join(
            _sql_literal(value) for value in link_policy.allowed_link_types
        )
        primary = ", ".join(
            _sql_literal(value) for value in link_policy.allowed_primary_values
        )
        link_scan = (
            f"(SELECT * FROM read_parquet({_quote_literal(_dataset_glob(normalized_root, 'ccm_links'))}, "
            f"hive_partitioning=true) WHERE link_type IN ({link_types}) "
            f"AND link_primary IN ({primary}))"
        )
        eligible = int(
            connection.execute(f"SELECT count(*) FROM {link_scan}").fetchone()[0]
        )
        ambiguous = _overlap_count(
            connection, link_scan, key="permno", start="link_start", end="link_end"
        )
        if "crsp_daily" in source_names:
            market_scan = (
                f"read_parquet({_quote_literal(_dataset_glob(normalized_root, 'crsp_daily'))}, "
                "hive_partitioning=true)"
            )
            unlinked_market = int(
                connection.execute(
                    f"""
                    SELECT count(*)
                    FROM {market_scan} m
                    LEFT JOIN {link_scan} l
                      ON m.permno = l.permno
                     AND CAST(m.observed_at AS DATE) >= l.link_start
                     AND CAST(m.observed_at AS DATE) <= coalesce(l.link_end, DATE '9999-12-31')
                    WHERE l.permno IS NULL
                    """
                ).fetchone()[0]
            )
    if "crsp_stock_names" in source_names:
        scan = f"read_parquet({_quote_literal(_dataset_glob(normalized_root, 'crsp_stock_names'))}, hive_partitioning=true)"
        stock_overlap = _overlap_count(
            connection, scan, key="permno", start="valid_from", end="valid_to"
        )
    fundamental_parts: list[str] = []
    for name in sorted(FUNDAMENTAL_SOURCES.intersection(source_names)):
        fundamental_parts.append(
            f"SELECT available_at FROM read_parquet({_quote_literal(_dataset_glob(normalized_root, name))}, hive_partitioning=true)"
        )
    if fundamental_parts:
        missing_availability = int(
            connection.execute(
                f"SELECT count(*) FROM ({' UNION ALL '.join(fundamental_parts)}) WHERE available_at IS NULL"
            ).fetchone()[0]
        )
        if missing_availability:
            warnings.append(
                "Fundamental rows with missing explicit availability are excluded from primary point-in-time joins."
            )
    if stock_overlap:
        warnings.append(
            "Overlapping StockNames intervals require explicit date-effective review."
        )
    return JoinQualityReport(
        report_id=f"join_quality_{snapshot_id}",
        snapshot_id=snapshot_id,
        eligible_link_rows=eligible,
        ambiguous_market_dates=ambiguous,
        unlinked_market_rows=unlinked_market,
        missing_fundamental_availability_rows=missing_availability,
        stock_name_overlap_rows=stock_overlap,
        blocked=ambiguous > 0,
        warnings=tuple(warnings),
    )


def _write_json_immutable(path: Path, value: object) -> None:
    payload = (
        value.model_dump(mode="json")
        if hasattr(value, "model_dump")
        else value
    )
    text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    if path.exists():
        if path.read_text(encoding="utf-8") != text:
            raise LicensedDataError(f"immutable artifact already exists with different content: {path.name}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build_dataset(specification: DatasetBuildSpecification) -> DatasetBuildResult:
    specification = DatasetBuildSpecification.model_validate(
        specification.model_dump(mode="python")
    )
    manifest_path = _outside_repository(
        specification.manifest_path, "private manifest path", must_exist=True
    )
    data_root = _outside_repository(specification.data_root, "data root")
    _outside_repository(specification.temp_directory, "external temp directory")
    manifest = load_licensed_manifest(manifest_path)
    sources = manifest.sources
    source_names = {item.source_name for item in sources}
    if specification.mode == "daily_primary" and "crsp_daily" not in source_names:
        raise LicensedDataError("daily-primary requires dsf.parquet / crsp_daily")
    if specification.mode == "monthly_smoke" and "crsp_monthly" not in source_names:
        raise LicensedDataError("monthly-smoke requires msf.parquet / crsp_monthly")
    profile = profile_manifest(
        manifest,
        memory_limit=specification.memory_limit,
        threads=specification.threads,
        temp_directory=specification.temp_directory,
    )
    identity = {
        "manifest": manifest.model_dump(mode="json"),
        "mode": specification.mode,
        "code_revision": specification.code_revision,
        "compression": specification.compression,
    }
    identity_digest = _digest_value(identity)
    snapshot_id = f"crsp_compustat_{identity_digest.removeprefix('sha256:')[:24]}"
    normalized_root = data_root / "normalized" / snapshot_id
    curated_root = data_root / "curated" / snapshot_id
    receipt_path = data_root / "manifests" / snapshot_id / "dataset-admission-receipt.json"
    quality_path = data_root / "quality" / snapshot_id / "join-quality.json"
    evidence_path = data_root / "evidence" / snapshot_id / "build-evidence.json"
    catalogue_path = data_root / "catalog" / "crsp-compustat.duckdb"
    snapshot_catalogue_path = (
        data_root
        / "catalog"
        / "snapshots"
        / snapshot_id
        / "crsp-compustat.duckdb"
    )
    latest_catalogue_temporary = (
        catalogue_path.parent / f".{snapshot_id}.duckdb.tmp"
    )
    if receipt_path.is_file():
        receipt = DatasetAdmissionReceipt.model_validate(
            json.loads(receipt_path.read_text(encoding="utf-8"))
        )
        join_quality = JoinQualityReport.model_validate(
            json.loads(quality_path.read_text(encoding="utf-8"))
        )
        return DatasetBuildResult(
            snapshot_id=snapshot_id,
            created=False,
            snapshot_root=normalized_root,
            catalogue_path=catalogue_path,
            receipt_path=receipt_path,
            quality_path=quality_path,
            evidence_path=evidence_path,
            receipt=receipt,
            join_quality=join_quality,
        )
    for zone in ("normalized", "curated", "catalog", "manifests", "quality", "evidence", "tmp"):
        (data_root / zone).mkdir(parents=True, exist_ok=True)
    if normalized_root.exists():
        raise LicensedDataError("partial immutable snapshot exists without a receipt")
    created_at = max(source.retrieved_at for source in sources)
    try:
        with duckdb.connect(":memory:") as connection:
            _configure_connection(connection, specification)
            schemas: dict[str, tuple[SourceSchemaColumn, ...]] = {}
            for source in sources:
                schemas[source.source_name] = _source_schema(connection, source.source_path)
                destination = normalized_root / source.source_name
                destination.mkdir(parents=True, exist_ok=False)
                query = _normalized_query(source, schemas[source.source_name])
                _copy_normalized(connection, source, query, destination)
            join_quality = _join_quality(
                connection,
                normalized_root,
                source_names,
                snapshot_id,
                manifest.link_policy,
            )
            if join_quality.blocked:
                raise LicensedDataError("ambiguous eligible CCM links block the build")
        snapshot_catalogue_path.parent.mkdir(parents=True, exist_ok=False)
        _create_catalogue(
            snapshot_catalogue_path,
            normalized_root,
            sources,
            manifest.link_policy,
            profile,
            snapshot_id,
        )
        _materialize_curated(
            snapshot_catalogue_path, curated_root, specification
        )
        catalogue_digest = sha256_file(snapshot_catalogue_path)
        catalogue_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(snapshot_catalogue_path, latest_catalogue_temporary)
        os.replace(latest_catalogue_temporary, catalogue_path)
        output_counts: dict[str, int] = {}
        coverage: dict[str, str | None] = {}
        partitions: dict[str, tuple[str, ...]] = {}
        output_digests: dict[str, str] = {}
        with duckdb.connect(":memory:") as connection:
            _configure_connection(connection, specification)
            for source in sources:
                glob = _dataset_glob(normalized_root, source.source_name)
                scan = f"read_parquet({_quote_literal(glob)}, hive_partitioning=true)"
                output_counts[source.source_name] = int(
                    connection.execute(f"SELECT count(*) FROM {scan}").fetchone()[0]
                )
                date_column = {
                    "crsp_daily": "observed_at",
                    "crsp_monthly": "observed_at",
                    "compustat_annual": "observed_at",
                    "compustat_quarterly": "observed_at",
                    "crsp_delist": "delisting_date",
                    "crsp_stock_names": "valid_from",
                    "ccm_links": "link_start",
                }[source.source_name]
                minimum, maximum = connection.execute(
                    f"SELECT CAST(min({_quote_identifier(date_column)}) AS VARCHAR), "
                    f"CAST(max({_quote_identifier(date_column)}) AS VARCHAR) FROM {scan}"
                ).fetchone()
                coverage[f"{source.source_name}_start"] = str(minimum) if minimum is not None else None
                coverage[f"{source.source_name}_end"] = str(maximum) if maximum is not None else None
                source_root = normalized_root / source.source_name
                partitions[source.source_name] = tuple(
                    sorted(
                        path.relative_to(source_root).as_posix()
                        for path in source_root.rglob("*.parquet")
                    )
                )
                output_digests[source.source_name] = _tree_digest(source_root)
            for curated_name in (
                "security_history",
                "crsp_with_delist",
                "ccm_active_links",
                "fundamentals_as_of",
                "source_quality_summary",
            ):
                dataset_root = curated_root / curated_name
                key = f"curated.{curated_name}"
                glob = str(dataset_root / "**" / "*.parquet")
                output_counts[key] = int(
                    connection.execute(
                        f"SELECT count(*) FROM read_parquet({_quote_literal(glob)}, "
                        "hive_partitioning=true, union_by_name=true)"
                    ).fetchone()[0]
                )
                partitions[key] = tuple(
                    sorted(
                        path.relative_to(dataset_root).as_posix()
                        for path in dataset_root.rglob("*.parquet")
                    )
                )
                output_digests[key] = _tree_digest(dataset_root)
        mapping_digest = _digest_value(
            {
                source.source_name: [item.model_dump(mode="json") for item in source.mappings]
                for source in sources
            }
        )
        transformation_versions = {
            f"{source.source_name}.{item.transformation_id}": item.version
            for source in sources
            for item in source.transformations
        }
        build_limitations = manifest.limitations + (
            "Catalogue views remain local and point-in-time; no MetricPack is included.",
            "RET and DLRET remain separate; no combined-return policy is applied.",
        )
        if specification.mode == "monthly_smoke":
            build_limitations += (
                "Monthly smoke is diagnostic only and does not satisfy daily-primary admission.",
            )
        receipt = DatasetAdmissionReceipt(
            receipt_id=f"receipt_{snapshot_id}",
            snapshot_id=snapshot_id,
            created_at=created_at,
            source_digests={source.source_name: source.source_digest for source in sources},
            schema_fingerprints={
                source.source_name: source.schema_fingerprint.digest for source in sources
            },
            mapping_digest=mapping_digest,
            transformation_versions=transformation_versions,
            output_row_counts=output_counts,
            partitions=partitions,
            output_digests=output_digests,
            catalogue_digest=catalogue_digest,
            rights=manifest.rights,
            publication_state=manifest.publication_state,
            quality={
                "ambiguous_market_dates": join_quality.ambiguous_market_dates,
                "stock_name_overlap_rows": join_quality.stock_name_overlap_rows,
                "unlinked_market_rows": (
                    join_quality.unlinked_market_rows
                    if join_quality.unlinked_market_rows is not None
                    else "not_applicable"
                ),
                "missing_fundamental_availability_rows": (
                    join_quality.missing_fundamental_availability_rows
                    if join_quality.missing_fundamental_availability_rows is not None
                    else "not_computed"
                ),
                "blocked": join_quality.blocked,
            },
            coverage=coverage,
            availability_policy={
                source.source_name: source.availability_policy.policy_id
                for source in sources
            },
            link_policy=manifest.link_policy,
            code_revision=specification.code_revision,
            limitations=build_limitations,
        )
        _write_json_immutable(quality_path, join_quality)
        _write_json_immutable(
            evidence_path,
            {
                "snapshot_id": snapshot_id,
                "profile": profile,
                "catalogue_views": CATALOGUE_VIEWS,
                "look_ahead_risk": False,
                "network": False,
                "effects": [],
                "limitations": list(receipt.limitations),
            },
        )
        _write_json_immutable(receipt_path, receipt)
    except Exception:
        # A failed attempt is not an immutable snapshot.  Remove only the exact
        # new snapshot directory; never touch a source or another snapshot.
        if normalized_root.exists() and not receipt_path.exists():
            shutil.rmtree(normalized_root)
        if curated_root.exists() and not receipt_path.exists():
            shutil.rmtree(curated_root)
        snapshot_catalogue_directory = snapshot_catalogue_path.parent
        if (
            snapshot_catalogue_directory.exists()
            and not receipt_path.exists()
        ):
            shutil.rmtree(snapshot_catalogue_directory)
        if latest_catalogue_temporary.exists():
            latest_catalogue_temporary.unlink()
        raise
    return DatasetBuildResult(
        snapshot_id=snapshot_id,
        created=True,
        snapshot_root=normalized_root,
        catalogue_path=catalogue_path,
        receipt_path=receipt_path,
        quality_path=quality_path,
        evidence_path=evidence_path,
        receipt=receipt,
        join_quality=join_quality,
    )


def list_snapshots(data_root: Path) -> tuple[DatasetAdmissionReceipt, ...]:
    root = _outside_repository(data_root, "data root")
    directory = root / "manifests"
    if not directory.exists():
        return ()
    snapshots = tuple(
        DatasetAdmissionReceipt.model_validate(json.loads(path.read_text(encoding="utf-8")))
        for path in sorted(directory.glob("*/dataset-admission-receipt.json"))
    )
    return tuple(sorted(snapshots, key=lambda item: (item.created_at, item.snapshot_id)))


def verify_dataset(data_root: Path, snapshot_id: str | None = None) -> DatasetAdmissionReceipt:
    snapshots = list_snapshots(data_root)
    if not snapshots:
        raise LicensedDataError("no CRSP/Compustat snapshots are registered")
    receipt = (
        next((item for item in snapshots if item.snapshot_id == snapshot_id), None)
        if snapshot_id
        else snapshots[-1]
    )
    if receipt is None:
        raise LicensedDataError("requested snapshot is not registered")
    root = _outside_repository(data_root, "data root")
    normalized = root / "normalized" / receipt.snapshot_id
    for source_name, expected in receipt.output_digests.items():
        source_root = (
            root / "curated" / receipt.snapshot_id / source_name.removeprefix("curated.")
            if source_name.startswith("curated.")
            else normalized / source_name
        )
        if not source_root.is_dir() or _tree_digest(source_root) != expected:
            raise LicensedDataError(f"output digest mismatch for {source_name}")
    catalogue = (
        root
        / "catalog"
        / "snapshots"
        / receipt.snapshot_id
        / "crsp-compustat.duckdb"
    )
    if not catalogue.is_file():
        raise LicensedDataError("snapshot-specific catalogue is missing")
    if sha256_file(catalogue) != receipt.catalogue_digest:
        raise LicensedDataError("snapshot-specific catalogue digest mismatch")
    with duckdb.connect(str(catalogue), read_only=True) as connection:
        binding = connection.execute(
            "SELECT snapshot_id FROM catalogue_snapshot_metadata"
        ).fetchall()
        if binding != [(receipt.snapshot_id,)]:
            raise LicensedDataError(
                "catalogue is not bound to the requested snapshot"
            )
        names = {
            row[0]
            for row in connection.execute(
                "SELECT table_name FROM information_schema.tables WHERE table_schema = 'main'"
            ).fetchall()
        }
    missing = set(CATALOGUE_VIEWS) - names
    if missing:
        raise LicensedDataError(f"catalogue views are missing: {sorted(missing)}")
    return receipt


def candidate_universe(
    data_root: Path,
    *,
    as_of: datetime,
    minimum_observations: int = 60,
    limit: int = 100,
) -> tuple[dict[str, object], ...]:
    if as_of.tzinfo is None or as_of.utcoffset() is None or as_of.utcoffset().total_seconds() != 0:
        raise LicensedDataError("candidate universe as_of must be timezone-aware UTC")
    if not 1 <= minimum_observations <= 10000 or not 1 <= limit <= 1000:
        raise LicensedDataError("candidate universe bounds are invalid")
    root = _outside_repository(data_root, "data root")
    latest = verify_dataset(root)
    if "crsp_daily" not in latest.source_digests:
        raise LicensedDataError("candidate universe requires a daily-primary snapshot")
    quality_path = root / "quality" / latest.snapshot_id / "join-quality.json"
    join_quality = JoinQualityReport.model_validate(
        json.loads(quality_path.read_text(encoding="utf-8"))
    )
    if join_quality.stock_name_overlap_rows:
        raise LicensedDataError(
            "candidate universe is blocked by overlapping StockNames intervals"
        )
    catalogue = (
        root
        / "catalog"
        / "snapshots"
        / latest.snapshot_id
        / "crsp-compustat.duckdb"
    )
    with duckdb.connect(str(catalogue), read_only=True) as connection:
        rows = connection.execute(
            """
            WITH eligible AS (
                SELECT permno, count(*) AS observations,
                       max(CAST(observed_at AS DATE)) AS latest_market_date
                FROM crsp_daily
                WHERE available_at <= ?
                GROUP BY permno
                HAVING count(*) >= ?
            )
            SELECT e.permno, e.observations, e.latest_market_date,
                   n.ticker, n.company_name
            FROM eligible e
            LEFT JOIN security_history n
              ON e.permno = n.permno
             AND e.latest_market_date >= n.valid_from
             AND e.latest_market_date <= coalesce(n.valid_to, DATE '9999-12-31')
            ORDER BY e.observations DESC, e.permno
            LIMIT ?
            """,
            [as_of, minimum_observations, limit],
        ).fetchall()
    return tuple(
        {
            "permno": int(row[0]),
            "observations": int(row[1]),
            "latest_market_date": str(row[2]),
            "ticker": row[3],
            "company_name": row[4],
            "look_ahead_risk": False,
        }
        for row in rows
    )


def reject_sql_or_expression(value: str) -> None:
    """Fail closed for any CLI/API field that purports to carry query language."""

    if value.strip():
        raise LicensedDataError("SQL, shell, formula and expression input is prohibited")
