"""
Repositorio de solo lectura para la tabla evaluator_routes.
Tabla: id, evaluator_id, proposal_type.
Usado para decidir el título por defecto del memo (TS → informe general; otro → informe estándar).
"""
import logging
from typing import Optional, Dict, Any

from common.repositories.base import BaseRepository

logger = logging.getLogger(__name__)


class EvaluatorRoutesRepository(BaseRepository):
    """Consulta evaluator_routes por evaluator_id. Sin modelo Pydantic (solo lectura)."""

    def __init__(self):
        super().__init__("evaluator_routes", None)

    def get_evaluator_route(self, evaluator_id: str) -> Optional[Dict[str, Any]]:
        """
        Obtiene la ruta configurada para un evaluator.
        Returns dict con proposal_type y target_queue_url, o None si no hay fila.
        """
        if not evaluator_id or not str(evaluator_id).strip():
            return None
        try:
            query = """
                SELECT proposal_type
                FROM evaluator_routes
                WHERE evaluator_id = %s
                LIMIT 1
            """
            row = self._execute_query_one(query, (str(evaluator_id).strip(),))
            if not row:
                return None
            return {
                "proposal_type": row.get("proposal_type"),
                "target_queue_url": None,
            }
        except Exception as e:
            logger.warning(
                "Error obteniendo ruta para evaluator_id=%s: %s", evaluator_id, e
            )
            return None

    def get_proposal_type(self, evaluator_id: str) -> Optional[str]:
        """
        Obtiene el proposal_type del evaluator en evaluator_routes.
        Returns proposal_type (ej. 'TS', 'CORIL') o None si no hay fila.
        """
        route = self.get_evaluator_route(evaluator_id)
        if not route:
            return None
        return (route.get("proposal_type") or "").strip() or None
