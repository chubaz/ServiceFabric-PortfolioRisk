"""Human-reviewed real-portfolio validation and immutable materialization."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from ..contracts import (
    PortfolioDefinition,
    PortfolioMaterializationReceipt,
    RealPortfolioSelectionManifest,
    canonical_record_digest,
)
from ..manifests import ManifestError, load_portfolio, load_yaml, sha256_file


REPOSITORY_ROOT = Path(__file__).resolve().parents[5]
RECEIPT_NAME = "portfolio-selection-receipt.json"
INSTRUMENT_MAP_NAME = "private-instrument-map.json"
EVIDENCE_NAME = "evidence-manifest.json"


class PortfolioMaterializationError(ValueError):
    """A reviewed selection or immutable private output is invalid."""


def prepare_real_selection_interactive(
    *,
    candidate_artifact_path: Path | str,
    selection_path: Path | str,
    input_fn=input,
    print_fn=print,
    show_all_candidates: bool = False,
    uniform_quantity: str | None = None,
    uniform_cash_amount: str | None = None,
) -> Path:
    """Interactively author the reviewed thesis selection without choosing for the user."""

    artifact_path = _private_external_path(
        candidate_artifact_path, "candidate artifact", must_exist=True
    )
    selection_target = _private_external_path(
        selection_path, "selection manifest", must_exist=False
    )
    artifact = _load_candidate_artifact(artifact_path)
    candidates = artifact["candidates"]
    latest_eligible_date = max(
        str(candidate["latest_eligible_date"]) for candidate in candidates
    )
    day2_candidate_numbers = {
        number
        for number, candidate in enumerate(candidates, 1)
        if str(candidate["latest_eligible_date"]) == latest_eligible_date
    }
    print_fn(
        f"Candidate artifact {artifact['artifact_id']} contains "
        f"{len(candidates)} candidates; snapshot {artifact['snapshot_id']}"
    )
    print_fn(
        f"Day 2 latest-data cohort: {len(day2_candidate_numbers)} candidates "
        f"with latest eligible date {latest_eligible_date}."
    )
    print_fn("Enter candidate numbers from this local artifact; no choice is automatic.")
    for number, candidate in enumerate(candidates, 1):
        if not show_all_candidates and number not in day2_candidate_numbers:
            continue
        print_fn(
            f"{number:03} {candidate['candidate_id']} "
            f"SIC={candidate.get('sic_code')} "
            f"observations={candidate['observation_count']} "
            f"latest={candidate['latest_eligible_date']} "
            f"day2_eligible={'yes' if number in day2_candidate_numbers else 'no'} "
            f"warnings={candidate['quality_warnings']}"
        )

    reviewer_id = input_fn("Reviewer ID: ").strip()
    if not reviewer_id:
        raise PortfolioMaterializationError("reviewer ID is required")
    selection_id = input_fn(
        "Selection ID [thesis-real-portfolios-v1]: "
    ).strip() or "thesis-real-portfolios-v1"
    reviewed_at = input_fn("Reviewed at (UTC ISO timestamp): ").strip()
    effective_at = input_fn("Effective at (UTC ISO timestamp): ").strip()
    rationale = input_fn("Research rationale: ").strip()
    if not reviewed_at or not effective_at or not rationale:
        raise PortfolioMaterializationError(
            "reviewed_at, effective_at, and rationale are required"
        )

    portfolios: list[dict[str, object]] = []
    used_candidates: set[str] = set()
    portfolio_specs = (
        ("diversified", "Diversified real-data research portfolio"),
        ("technology_concentrated", "Technology-concentrated real-data research portfolio"),
        ("defensive_multi_asset", "Defensive real-data research portfolio"),
    )
    for portfolio_id, title in portfolio_specs:
        print_fn(f"\n{portfolio_id}: {title}")
        raw_numbers = input_fn("Candidate numbers (5-8, comma separated): ").strip()
        try:
            numbers = [int(item.strip()) for item in raw_numbers.split(",")]
        except ValueError as error:
            raise PortfolioMaterializationError(
                "candidate numbers must be comma-separated integers"
            ) from error
        if not 5 <= len(numbers) <= 8 or len(set(numbers)) != len(numbers):
            raise PortfolioMaterializationError(
                "each portfolio requires 5-8 distinct candidate numbers"
            )
        if any(number < 1 or number > len(candidates) for number in numbers):
            raise PortfolioMaterializationError("candidate number is outside the artifact")
        if any(number not in day2_candidate_numbers for number in numbers):
            raise PortfolioMaterializationError(
                "Day 2 selections require candidates from the displayed "
                "latest-data cohort"
            )
        selected = [candidates[number - 1] for number in numbers]
        selected_ids = [item["candidate_id"] for item in selected]
        if used_candidates.intersection(selected_ids):
            raise PortfolioMaterializationError(
                "a candidate may only appear once in the interactive thesis selection"
            )
        used_candidates.update(selected_ids)
        cash = (
            uniform_cash_amount
            if uniform_cash_amount is not None
            else input_fn("Explicit USD cash amount: ").strip()
        )
        if not cash:
            raise PortfolioMaterializationError("cash amount is required")
        positions = []
        portfolio_alias = portfolio_id.replace("_", "-")
        for position_number, candidate in enumerate(selected, 1):
            quantity = (
                uniform_quantity
                if uniform_quantity is not None
                else input_fn(
                    f"Quantity for {candidate['candidate_id']} "
                    "(positive integer): "
                ).strip()
            )
            if not quantity.isdigit() or int(quantity) <= 0:
                raise PortfolioMaterializationError(
                    "quantities must be positive integers"
                )
            positions.append(
                {
                    "candidate_id": candidate["candidate_id"],
                    "instrument_alias": f"real-{portfolio_alias}-{position_number:02}",
                    "quantity": quantity,
                }
            )
        portfolios.append(
            {
                "portfolio_id": portfolio_id,
                "title": title,
                "base_currency": "USD",
                "benchmark_unavailable": True,
                "cash": [{"currency": "USD", "amount": cash}],
                "positions": positions,
            }
        )

    confirmation = input_fn(
        "Type REVIEWED to write this private selection manifest: "
    ).strip()
    if confirmation != "REVIEWED":
        raise PortfolioMaterializationError("selection was not confirmed")
    document = {
        "selection_version": "1.0",
        "selection_id": selection_id,
        "reviewed": True,
        "reviewer_id": reviewer_id,
        "reviewed_at": reviewed_at,
        "candidate_artifact": {
            "path": str(artifact_path),
            "sha256": f"sha256:{hashlib.sha256(artifact_path.read_bytes()).hexdigest()}",
            "artifact_id": artifact["artifact_id"],
        },
        "source_snapshot_id": artifact["snapshot_id"],
        "as_of": artifact["as_of"],
        "effective_at": effective_at,
        "rationale": rationale,
        "warnings": [
            "Private licensed evidence; not investment advice.",
            "All securities and quantities were explicitly human reviewed.",
        ],
        "portfolios": portfolios,
    }
    try:
        RealPortfolioSelectionManifest.model_validate(document)
    except ValidationError as error:
        raise PortfolioMaterializationError(
            f"interactive selection failed contract validation: {error}"
        ) from error
    selection_target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    selection_target.write_text(
        yaml.safe_dump(document, sort_keys=False), encoding="utf-8"
    )
    os.chmod(selection_target, 0o600)
    print_fn(f"Wrote reviewed private selection: {selection_target}")
    return selection_target


def _configured_data_root() -> Path:
    configured = os.environ.get("THESIS_DATA_ROOT")
    if not configured:
        raise PortfolioMaterializationError(
            "THESIS_DATA_ROOT must be configured for private portfolio materialization"
        )
    root = Path(configured)
    if not root.is_absolute():
        raise PortfolioMaterializationError("THESIS_DATA_ROOT must be absolute")
    root = root.resolve(strict=False)
    if root == REPOSITORY_ROOT or REPOSITORY_ROOT in root.parents:
        raise PortfolioMaterializationError("THESIS_DATA_ROOT must remain outside Git")
    return root


def _private_external_path(
    value: Path | str,
    label: str,
    *,
    must_exist: bool,
) -> Path:
    path = Path(value)
    if not path.is_absolute():
        raise PortfolioMaterializationError(f"{label} must be an absolute path")
    resolved = path.resolve(strict=must_exist)
    if resolved == REPOSITORY_ROOT or REPOSITORY_ROOT in resolved.parents:
        raise PortfolioMaterializationError(f"{label} must remain outside Git")
    data_root = _configured_data_root()
    if resolved != data_root and data_root not in resolved.parents:
        raise PortfolioMaterializationError(
            f"{label} must be equal to or beneath THESIS_DATA_ROOT"
        )
    return resolved


def _json_bytes(value: object) -> bytes:
    return (
        json.dumps(value, indent=2, sort_keys=True, default=str) + "\n"
    ).encode("utf-8")


def _yaml_bytes(value: object) -> bytes:
    return yaml.safe_dump(
        value,
        sort_keys=False,
        default_flow_style=False,
        allow_unicode=False,
    ).encode("utf-8")


def _digest_bytes(value: bytes) -> str:
    return f"sha256:{hashlib.sha256(value).hexdigest()}"


def _candidate_artifact_identity(value: dict[str, Any]) -> str:
    body = {key: item for key, item in value.items() if key != "artifact_id"}
    payload = json.dumps(
        body,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return f"candidate_artifact_{hashlib.sha256(payload).hexdigest()[:24]}"


def _artifact_as_of(value: object) -> datetime:
    if not isinstance(value, str):
        raise PortfolioMaterializationError(
            "candidate artifact as_of must be an explicit UTC timestamp"
        )
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise PortfolioMaterializationError(
            "candidate artifact as_of must be an explicit UTC timestamp"
        ) from error
    if (
        parsed.tzinfo is None
        or parsed.utcoffset() is None
        or parsed.utcoffset().total_seconds() != 0
    ):
        raise PortfolioMaterializationError(
            "candidate artifact as_of must be an explicit UTC timestamp"
        )
    return parsed.astimezone(UTC)


def _load_candidate_artifact(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise PortfolioMaterializationError(
            "unable to load candidate artifact"
        ) from error
    if not isinstance(value, dict):
        raise PortfolioMaterializationError(
            "candidate artifact must contain a JSON object"
        )
    required = {
        "artifact_version",
        "artifact_id",
        "snapshot_id",
        "as_of",
        "minimum_observations",
        "created_from",
        "candidates",
    }
    if set(value) != required or value.get("artifact_version") != "2.0":
        raise PortfolioMaterializationError(
            "candidate artifact must use the exact version 2 shape"
        )
    if not isinstance(value["candidates"], list):
        raise PortfolioMaterializationError("candidate artifact candidates must be a list")
    if value["artifact_id"] != _candidate_artifact_identity(value):
        raise PortfolioMaterializationError("candidate artifact identity mismatch")
    _artifact_as_of(value["as_of"])
    return value


def load_real_portfolio_selection(
    path: Path | str,
) -> RealPortfolioSelectionManifest:
    selection_path = _private_external_path(
        path, "selection manifest", must_exist=True
    )
    try:
        return RealPortfolioSelectionManifest.model_validate(
            load_yaml(selection_path)
        )
    except (ManifestError, ValidationError, KeyError) as error:
        raise PortfolioMaterializationError(
            f"invalid reviewed portfolio selection: {error}"
        ) from error


def _candidate_index(
    artifact: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    required_candidate_fields = {
        "candidate_id",
        "permno",
        "observation_count",
        "latest_eligible_date",
        "missing_total_return_count",
        "missing_valuation_price_count",
        "active_stock_names_coverage",
        "sector",
        "sic_code",
        "ccm_eligible_link_count",
        "fundamental_availability_coverage",
        "quality_warnings",
    }
    result: dict[str, dict[str, Any]] = {}
    for raw in artifact["candidates"]:
        if not isinstance(raw, dict) or set(raw) != required_candidate_fields:
            raise PortfolioMaterializationError(
                "candidate artifact contains an invalid candidate record"
            )
        candidate_id = raw.get("candidate_id")
        if not isinstance(candidate_id, str) or not candidate_id:
            raise PortfolioMaterializationError("candidate_id must be explicit")
        if candidate_id in result:
            raise PortfolioMaterializationError(
                "candidate artifact contains duplicate candidate IDs"
            )
        if isinstance(raw.get("permno"), bool) or not isinstance(
            raw.get("permno"), int
        ):
            raise PortfolioMaterializationError(
                "candidate artifact PERMNO must remain a private integer"
            )
        result[candidate_id] = raw
    return result


def _portfolio_definition(
    selection: RealPortfolioSelectionManifest,
    portfolio_index: int,
) -> PortfolioDefinition:
    reviewed = selection.portfolios[portfolio_index]
    return PortfolioDefinition(
        portfolio_id=reviewed.portfolio_id,
        title=reviewed.title,
        base_currency=reviewed.base_currency,
        start_date=selection.effective_at.date(),
        positions=tuple(
            {
                "instrument_id": position.instrument_alias,
                "quantity": position.quantity,
            }
            for position in reviewed.positions
        ),
        cash=reviewed.cash,
        benchmark_id=reviewed.benchmark_id,
        benchmark_unavailable=reviewed.benchmark_unavailable,
    )


def _definition_document(definition: PortfolioDefinition) -> dict[str, object]:
    value: dict[str, object] = {
        "portfolio_id": definition.portfolio_id,
        "title": definition.title,
        "base_currency": definition.base_currency,
        "start_date": definition.start_date.isoformat(),
        "positions": [
            {
                "instrument_id": item.instrument_id,
                "quantity": format(item.quantity, "f"),
            }
            for item in definition.positions
        ],
        "cash": [
            {"currency": item.currency, "amount": format(item.amount, "f")}
            for item in definition.cash
        ],
    }
    if definition.benchmark_id is not None:
        value["benchmark_id"] = definition.benchmark_id
    else:
        value["benchmark_unavailable"] = True
    return value


def _receipt_id(value: dict[str, object]) -> str:
    digest = canonical_record_digest(value).removeprefix("sha256:")
    return f"portfolio_receipt_{digest[:24]}"


def _validate_alias_bindings(
    selection: RealPortfolioSelectionManifest,
    candidates: dict[str, dict[str, Any]],
) -> tuple[dict[str, object], ...]:
    aliases: dict[str, str] = {}
    candidate_aliases: dict[str, str] = {}
    for portfolio in selection.portfolios:
        for position in portfolio.positions:
            if position.candidate_id not in candidates:
                raise PortfolioMaterializationError(
                    f"unknown candidate_id: {position.candidate_id}"
                )
            prior_candidate = aliases.get(position.instrument_alias)
            if prior_candidate is not None and prior_candidate != position.candidate_id:
                raise PortfolioMaterializationError(
                    "duplicate instrument alias maps to different candidates"
                )
            prior_alias = candidate_aliases.get(position.candidate_id)
            if prior_alias is not None and prior_alias != position.instrument_alias:
                raise PortfolioMaterializationError(
                    "one candidate cannot use multiple private aliases"
                )
            aliases[position.instrument_alias] = position.candidate_id
            candidate_aliases[position.candidate_id] = position.instrument_alias
    return tuple(
        {
            "instrument_alias": alias,
            "candidate_id": candidate_id,
            "permno": candidates[candidate_id]["permno"],
        }
        for alias, candidate_id in sorted(aliases.items())
    )


def _expected_files_match(root: Path, files: dict[str, bytes]) -> bool:
    if not root.is_dir():
        return False
    children = tuple(root.iterdir())
    if any(not item.is_file() for item in children):
        return False
    actual = {item.name for item in children}
    if actual != set(files):
        return False
    return all((root / name).read_bytes() == payload for name, payload in files.items())


def _write_private_immutable_directory(
    target: Path, files: dict[str, bytes]
) -> None:
    parent_existed = target.parent.exists()
    target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if not parent_existed:
        os.chmod(target.parent, 0o700)
    if target.exists():
        if _expected_files_match(target, files):
            return
        raise PortfolioMaterializationError(
            "immutable portfolio output already exists with different content"
        )
    staging = Path(
        tempfile.mkdtemp(
            prefix=f".{target.name}.",
            dir=target.parent,
        )
    )
    try:
        os.chmod(staging, 0o700)
        for name, payload in files.items():
            path = staging / name
            descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(payload)
        try:
            staging.rename(target)
        except FileExistsError:
            if not _expected_files_match(target, files):
                raise PortfolioMaterializationError(
                    "immutable portfolio output appeared with different content"
                )
    finally:
        if staging.exists():
            shutil.rmtree(staging)


def materialize_real_portfolios(
    *,
    candidate_artifact_path: Path | str,
    selection_path: Path | str,
    output_directory: Path | str,
) -> PortfolioMaterializationReceipt:
    """Materialize only explicit, reviewed choices; never initialize choices."""

    artifact_path = _private_external_path(
        candidate_artifact_path, "candidate artifact", must_exist=True
    )
    selection = load_real_portfolio_selection(selection_path)
    output_root = _private_external_path(
        output_directory, "portfolio output directory", must_exist=False
    )
    output_root_existed = output_root.exists()
    output_root.mkdir(parents=True, exist_ok=True, mode=0o700)
    if not output_root_existed:
        os.chmod(output_root, 0o700)
    declared_artifact_path = selection.candidate_artifact.path.resolve(strict=True)
    if declared_artifact_path != artifact_path:
        raise PortfolioMaterializationError(
            "selection candidate artifact path does not match the supplied artifact"
        )
    actual_digest = sha256_file(artifact_path)
    if actual_digest != selection.candidate_artifact.sha256:
        raise PortfolioMaterializationError("candidate artifact digest mismatch")
    artifact = _load_candidate_artifact(artifact_path)
    if artifact["artifact_id"] != selection.candidate_artifact.artifact_id:
        raise PortfolioMaterializationError("candidate artifact ID mismatch")
    if artifact["snapshot_id"] != selection.source_snapshot_id:
        raise PortfolioMaterializationError(
            "candidate artifact snapshot does not match the reviewed source snapshot"
        )
    artifact_as_of = _artifact_as_of(artifact["as_of"])
    if artifact_as_of != selection.as_of:
        raise PortfolioMaterializationError(
            "candidate artifact as_of does not match the reviewed selection as_of"
        )
    if artifact_as_of > selection.effective_at:
        raise PortfolioMaterializationError(
            "candidate artifact as_of must not be later than selection effective_at"
        )
    candidates = _candidate_index(artifact)
    instrument_bindings = _validate_alias_bindings(selection, candidates)

    target = _private_external_path(
        output_root / "portfolio-definitions" / selection.selection_id,
        "selection output directory",
        must_exist=False,
    )
    definitions = tuple(
        _portfolio_definition(selection, index)
        for index in range(len(selection.portfolios))
    )
    files: dict[str, bytes] = {}
    definition_digests: dict[str, str] = {}
    for definition in definitions:
        name = f"{definition.portfolio_id}.yaml"
        payload = _yaml_bytes(_definition_document(definition))
        files[name] = payload
        definition_digests[name] = _digest_bytes(payload)

    instrument_map = {
        "map_version": "1.0",
        "selection_id": selection.selection_id,
        "candidate_artifact_id": selection.candidate_artifact.artifact_id,
        "instruments": instrument_bindings,
        "publication_state": "private_local_only",
    }
    map_payload = _json_bytes(instrument_map)
    files[INSTRUMENT_MAP_NAME] = map_payload
    selection_digest = canonical_record_digest(
        selection.model_dump(mode="python")
    )
    receipt_body: dict[str, object] = {
        "receipt_version": "1.0",
        "selection_id": selection.selection_id,
        "selection_digest": selection_digest,
        "reviewer_id": selection.reviewer_id,
        "reviewed_at": selection.reviewed_at,
        "effective_at": selection.effective_at,
        "candidate_artifact": selection.candidate_artifact.model_dump(mode="python"),
        "source_snapshot_id": selection.source_snapshot_id,
        "as_of": selection.as_of,
        "rationale": selection.rationale,
        "warnings": selection.warnings,
        "output_directory": target,
        "portfolio_definition_digests": definition_digests,
        "private_instrument_map_digest": _digest_bytes(map_payload),
        "portfolio_count": len(definitions),
        "effects": (),
        "limitations": (
            "Human-reviewed fixed quantities only; not investment advice.",
            "No network, broker, order, trade, rebalance, optimization or portfolio mutation effect.",
        ),
    }
    receipt = PortfolioMaterializationReceipt(
        receipt_id=_receipt_id(receipt_body),
        **receipt_body,
    )
    receipt_payload = _json_bytes(receipt.model_dump(mode="json"))
    files[RECEIPT_NAME] = receipt_payload
    evidence = {
        "manifest_version": "1.0",
        "selection_id": selection.selection_id,
        "receipt_id": receipt.receipt_id,
        "publication_state": "private_local_only",
        "artifacts": {
            name: _digest_bytes(payload)
            for name, payload in sorted(files.items())
        },
        "effects": [],
        "limitations": list(receipt.limitations),
    }
    files[EVIDENCE_NAME] = _json_bytes(evidence)
    _write_private_immutable_directory(target, files)
    return receipt


def validate_materialized_real_portfolios(
    *,
    portfolios_directory: Path | str,
    receipt_path: Path | str,
) -> PortfolioMaterializationReceipt:
    root = _private_external_path(
        portfolios_directory, "portfolios directory", must_exist=True
    )
    receipt_file = _private_external_path(
        receipt_path, "portfolio receipt", must_exist=True
    )
    if receipt_file != root / RECEIPT_NAME:
        raise PortfolioMaterializationError(
            "receipt must be the immutable receipt inside the portfolios directory"
        )
    try:
        receipt = PortfolioMaterializationReceipt.model_validate_json(
            receipt_file.read_text(encoding="utf-8")
        )
    except (OSError, ValidationError) as error:
        raise PortfolioMaterializationError("invalid materialization receipt") from error
    if receipt.output_directory.resolve() != root:
        raise PortfolioMaterializationError("receipt output directory mismatch")
    receipt_body = receipt.model_dump(mode="python", exclude={"receipt_id"})
    if receipt.receipt_id != _receipt_id(receipt_body):
        raise PortfolioMaterializationError("receipt identity mismatch")
    artifact_path = _private_external_path(
        receipt.candidate_artifact.path,
        "receipt candidate artifact",
        must_exist=True,
    )
    if sha256_file(artifact_path) != receipt.candidate_artifact.sha256:
        raise PortfolioMaterializationError("receipt candidate artifact digest mismatch")
    artifact = _load_candidate_artifact(artifact_path)
    if artifact["artifact_id"] != receipt.candidate_artifact.artifact_id:
        raise PortfolioMaterializationError("receipt candidate artifact ID mismatch")
    if artifact["snapshot_id"] != receipt.source_snapshot_id:
        raise PortfolioMaterializationError(
            "receipt candidate artifact snapshot mismatch"
        )
    if _artifact_as_of(artifact["as_of"]) != receipt.as_of:
        raise PortfolioMaterializationError(
            "receipt candidate artifact as_of mismatch"
        )

    expected_names = set(receipt.portfolio_definition_digests) | {
        INSTRUMENT_MAP_NAME,
        RECEIPT_NAME,
        EVIDENCE_NAME,
    }
    children = tuple(root.iterdir())
    if any(not item.is_file() for item in children):
        raise PortfolioMaterializationError("immutable output contains a non-file")
    actual_names = {item.name for item in children}
    if actual_names != expected_names:
        raise PortfolioMaterializationError("immutable output file set mismatch")
    for name, expected in receipt.portfolio_definition_digests.items():
        if sha256_file(root / name) != expected:
            raise PortfolioMaterializationError(
                f"portfolio definition digest mismatch: {name}"
            )
        text = (root / name).read_text(encoding="utf-8")
        if any(field in text.casefold() for field in ("permno", "gvkey", "candidate_id")):
            raise PortfolioMaterializationError(
                "portfolio YAML contains a private source identifier"
            )
        load_portfolio(root / name)
    if sha256_file(root / INSTRUMENT_MAP_NAME) != receipt.private_instrument_map_digest:
        raise PortfolioMaterializationError("private instrument map digest mismatch")

    try:
        evidence = json.loads((root / EVIDENCE_NAME).read_text(encoding="utf-8"))
        instrument_map = json.loads(
            (root / INSTRUMENT_MAP_NAME).read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError) as error:
        raise PortfolioMaterializationError("invalid private output JSON") from error
    expected_evidence_artifacts = {
        name: sha256_file(root / name)
        for name in sorted(expected_names - {EVIDENCE_NAME})
    }
    if (
        instrument_map.get("map_version") != "1.0"
        or instrument_map.get("selection_id") != receipt.selection_id
        or instrument_map.get("candidate_artifact_id")
        != receipt.candidate_artifact.artifact_id
        or instrument_map.get("publication_state") != "private_local_only"
        or not isinstance(instrument_map.get("instruments"), list)
    ):
        raise PortfolioMaterializationError("private instrument map mismatch")
    expected_evidence = {
        "manifest_version": "1.0",
        "selection_id": receipt.selection_id,
        "receipt_id": receipt.receipt_id,
        "publication_state": "private_local_only",
        "artifacts": expected_evidence_artifacts,
        "effects": [],
        "limitations": list(receipt.limitations),
    }
    if evidence != expected_evidence:
        raise PortfolioMaterializationError("evidence manifest mismatch")
    aliases = {
        item["instrument_alias"]
        for item in instrument_map.get("instruments", ())
        if isinstance(item, dict) and "instrument_alias" in item
    }
    definition_aliases = {
        position.instrument_id
        for name in receipt.portfolio_definition_digests
        for position in load_portfolio(root / name).positions
    }
    if aliases != definition_aliases:
        raise PortfolioMaterializationError(
            "private instrument map and portfolio aliases do not match"
        )
    return receipt
