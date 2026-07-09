"""
Normaliza el body que puede llegar desde Step Functions / builder SQS en varias formas.

Reutilizable en extract_bs / extract_pl / extract_cf handlers.
"""

from __future__ import annotations

from typing import Any, Dict


def unwrap_reducto_extractor_payload(body: Dict[str, Any]) -> Dict[str, Any]:
    """
    El mensaje puede venir:
    - Directo (el payload es el root)
    - Con wrapper ``{ "payload": { ... } }``
    - Con lista ``{ "payloads": [ { ... }, ... ] }`` (se toma el primero)
    """
    if isinstance(body.get("payload"), dict):
        return body["payload"]

    payloads = body.get("payloads")
    if isinstance(payloads, list) and payloads and isinstance(payloads[0], dict):
        return payloads[0]

    return body


def resolve_object_key_json_output(payload: Dict[str, Any]) -> str | None:
    """Compat PREIA + fallback por financial_statement_id."""
    key = payload.get("object_key_json_output")
    if isinstance(key, str) and key.strip():
        return key.strip()

    statement_id = payload.get("financial_statement_id")
    if isinstance(statement_id, str) and statement_id.strip():
        return f"FinancialStatementJson/{statement_id.strip()}.json"

    return None
