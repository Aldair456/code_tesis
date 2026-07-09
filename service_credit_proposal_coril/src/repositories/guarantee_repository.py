import logging
from typing import Any, Dict, List

from common.repositories.base import BaseRepository

logger = logging.getLogger(__name__)


class GuaranteeRepository(BaseRepository):
    """Consultas de garantías vinculadas a un business vía deals."""

    def __init__(self):
        super().__init__("guarantees", None)

    def find_by_business_id(self, business_id: str, limit: int = 30) -> List[Dict[str, Any]]:
        converted_id = self._convert_value_for_sql(business_id)
        query = """
            SELECT
                g.guarantee_type,
                g.description,
                g.appraisal_value,
                g.haircut_percentage,
                g.adjusted_value,
                g.currency,
                g.status,
                g.notes,
                d.id AS deal_id,
                d.title AS deal_title
            FROM guarantees g
            INNER JOIN deals d ON d.id = g.deal_id
            WHERE d.business_id = %s
            ORDER BY g.created_at DESC
            LIMIT %s
        """
        records = self._execute_query(query, (converted_id, limit))
        logger.info("Garantías para business %s: %s registros", business_id, len(records or []))
        return records or []
