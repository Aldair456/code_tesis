"""
Utilidades genéricas para eventos SQS → Lambda.

Reutilizable en cualquier handler con BatchSize=1 que espere JSON en body.
"""

from __future__ import annotations

import json
from typing import Any, Dict


def get_single_sqs_record_json_body(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Devuelve el body del único record SQS ya parseado como dict.

    No interpreta el significado del JSON (eso va en un DTO / unwrap aparte).

    Compatibilidad extra:
    - Si el input NO tiene `Records`, se asume que `event` ya es el body/payload directo
      (por ejemplo, cuando Step Functions invoca los extractors con el payload directo).
    """
    records = event.get("Records")
    if records is None:
        # Step Functions invocando con payload directo (sin envoltorio SQS).
        if not isinstance(event, dict):
            raise ValueError(f"Evento debe ser dict si no trae Records; recibido: {type(event).__name__}")
        return event

    records = records or []
    if len(records) != 1:
        raise ValueError(f"BatchSize debe ser 1, pero llegaron {len(records)} mensajes")

    if "body" not in records[0]:
        raise ValueError("Record sin body")

    raw = records[0]["body"]
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as e:
            raise ValueError(f"body no es JSON válido: {e}") from e
    elif isinstance(raw, dict):
        parsed = raw
    else:
        raise ValueError(f"body con formato inválido: {type(raw).__name__}")

    if not isinstance(parsed, dict):
        raise ValueError(f"El body JSON debe ser un objeto, recibido: {type(parsed).__name__}")

    return parsed
