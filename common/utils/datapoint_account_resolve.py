"""
Resolución account_id (evaluador) + account_extract_id (catálogo) para inserts/upserts
de financial_datapoints (modelo post-migración 006).
"""
import json
from typing import Any, Callable, Dict, List, Optional, Tuple

DATAPOINT_UPSERT_CONFLICT_COLUMNS = [
    "account_id",
    "financial_statement_id",
    "year",
    "period",
]


def resolve_bank_account_ids(
    datapoints: List[Dict[str, Any]],
    evaluator_id: Optional[str],
    find_bank_account_id_for_extract: Callable[[str, str], Optional[str]],
    on_warning: Optional[Callable[[str], None]] = None,
    on_error: Optional[Callable[[str], None]] = None,
) -> List[Dict[str, Any]]:
    """
    Convierte filas con _catalog_extract_id / account_extract_id en
    (account_id evaluador, account_extract_id catálogo).
    """
    if not datapoints:
        return []
    if not evaluator_id:
        if on_error:
            on_error(
                "Sin evaluator_id: no se puede resolver account_id para financial_datapoints"
            )
        return []

    insertable: List[Dict[str, Any]] = []
    unresolved = 0
    sample_extract: Optional[str] = None
    resolved_cache: Dict[str, Optional[str]] = {}

    for dp in datapoints:
        row = dict(dp)
        catalog_id = row.pop("_catalog_extract_id", None) or row.pop("account_extract_id", None)

        if not catalog_id:
            unresolved += 1
            continue

        catalog_str = str(catalog_id)
        if catalog_str not in resolved_cache:
            resolved_cache[catalog_str] = find_bank_account_id_for_extract(
                catalog_str, evaluator_id
            )

        bank_id = resolved_cache[catalog_str]
        if not bank_id:
            unresolved += 1
            if sample_extract is None:
                sample_extract = catalog_str
            continue

        row["account_id"] = bank_id
        row["account_extract_id"] = catalog_str
        insertable.append(row)

    if unresolved and on_warning:
        on_warning(
            f"{unresolved} datapoint(s) omitidos: sin match en match_account_extracts para "
            f"evaluator_id={evaluator_id}"
            + (f" (ej. catalog_extract_id={sample_extract})" if sample_extract else "")
        )

    return insertable


def _details_to_list(details: Any) -> List[Any]:
    if isinstance(details, list):
        return details
    if isinstance(details, str):
        try:
            parsed = json.loads(details) if details else []
            return parsed if isinstance(parsed, list) else []
        except (json.JSONDecodeError, TypeError):
            return []
    return []


def consolidate_datapoints_by_account_period(
    datapoints: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Une filas que comparten (account_id, financial_statement_id, year, period).
    Alineado con financial_datapoints_account_period_unique en Postgres.
    """
    consolidated: Dict[Tuple[str, str, Any, Any], Dict[str, Any]] = {}

    for dp in datapoints:
        account_key = dp.get("account_id") or dp.get("account_extract_id")
        key = (
            str(account_key),
            str(dp.get("financial_statement_id")),
            dp.get("year"),
            dp.get("period"),
        )
        if key not in consolidated:
            consolidated[key] = dp.copy()
            continue

        existing = consolidated[key]
        try:
            existing["value"] = float(existing.get("value", 0) or 0) + float(
                dp.get("value", 0) or 0
            )
        except (TypeError, ValueError):
            pass

        merged_details = _details_to_list(existing.get("details")) + _details_to_list(
            dp.get("details")
        )
        existing["details"] = json.dumps(merged_details)

    return list(consolidated.values())
