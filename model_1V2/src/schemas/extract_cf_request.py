"""
DTO para el handler extract CF (payload directo desde Step Function).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from models.model_1V2.src.schemas.reducto_extractor_payload import (
    resolve_object_key_json_output,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ExtractCfRequest:
    """Entrada ya normalizada para extraer Flujo de Efectivo (CF) con IA."""

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
    def from_direct_payload(cls, payload: Dict[str, Any]) -> "ExtractCfRequest":
        """
        Recibe el payload completo desde Step Function (sin envoltorio SQS).
        Extrae la key 'cf' (o 'CF') de tables, y 'cf' de years.
        """
        tables_map = payload.get("tables") or {}
        if not isinstance(tables_map, dict):
            tables_map = {}

        raw_cf = tables_map.get("CF")
        tables = ""
        if isinstance(raw_cf, str) and raw_cf.strip():
            tables = raw_cf
        else:
            raw_lower = tables_map.get("cf")
            if isinstance(raw_lower, str):
                tables = raw_lower

        years_map = payload.get("years") or {}
        years: List[Any] = []
        if isinstance(years_map, dict):
            cf_years = years_map.get("cf") or years_map.get("CF")
            if isinstance(cf_years, list):
                years = cf_years
            elif years_map:
                for key in years_map:
                    candidate = years_map[key]
                    logger.info("Usando años de '%s' para CF: %s", key, candidate)
                    years = candidate if isinstance(candidate, list) else []
                    break

        return cls(
            tables=tables,
            years=years,
            object_key_json_output=resolve_object_key_json_output(payload),
            statement_kind=payload.get("type"),
            periodicity=(payload.get("periodicity") or payload.get("periodicity_type")),
            job_id=payload.get("job_id"),
            financial_statement_id=payload.get("financial_statement_id"),
        )
