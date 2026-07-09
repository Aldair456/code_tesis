"""
DTO para el handler extract PL (payload directo desde Step Function).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from models.model_1V2.src.schemas.reducto_extractor_payload import (
    resolve_object_key_json_output,
)


@dataclass(frozen=True)
class ExtractPlRequest:
    """Entrada ya normalizada para extraer Estado de Resultados (PL) con IA."""

    tables: str
    years: List[Any]
    object_key_json_output: Optional[str]
    statement_kind: Any
    periodicity: Optional[str]
    job_id: Optional[str]
    financial_statement_id: Optional[str]

    @property
    def base_response_fields(self) -> Dict[str, Any]:
        return {
            "object_key_json_output": self.object_key_json_output,
            "type": self.statement_kind,
            "periodicity": self.periodicity,
            "job_id": self.job_id,
            "financial_statement_id": self.financial_statement_id,
        }

    @classmethod
    def from_direct_payload(cls, payload: Dict[str, Any]) -> "ExtractPlRequest":
        """
        Recibe el payload completo desde Step Function (sin envoltorio SQS).
        Extrae solo la key 'pl' de tables y years.
        """
        tables_map = payload.get("tables") or {}
        if not isinstance(tables_map, dict):
            tables_map = {}
        years_map = payload.get("years") or {}
        if not isinstance(years_map, dict):
            years_map = {}

        raw_tables = tables_map.get("pl", "")
        tables = raw_tables if isinstance(raw_tables, str) else (str(raw_tables) if raw_tables is not None else "")

        years = years_map.get("pl", [])
        if not isinstance(years, list):
            years = []

        return cls(
            tables=tables,
            years=years,
            object_key_json_output=resolve_object_key_json_output(payload),
            statement_kind=payload.get("type"),
            periodicity=(payload.get("periodicity") or payload.get("periodicity_type")),
            job_id=payload.get("job_id"),
            financial_statement_id=payload.get("financial_statement_id"),
        )
