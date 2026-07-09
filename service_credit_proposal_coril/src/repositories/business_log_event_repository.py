import logging
from typing import Any, Dict, List

from common.models.models import BusinessLogEvent
from common.repositories.base import BaseRepository

logger = logging.getLogger(__name__)


class BusinessLogEventRepository(BaseRepository[BusinessLogEvent]):
    def __init__(self):
        super().__init__("business_log_events", BusinessLogEvent)

    def find_by_business_id(self, business_id: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Logs del timeline del business (todos los deals), más recientes primero."""
        converted_id = self._convert_value_for_sql(business_id)
        query = """
            SELECT id, business_id, deal_id, user_id, title, date, data, created_at
            FROM business_log_events
            WHERE business_id = %s
            ORDER BY COALESCE(date, created_at) DESC
            LIMIT %s
        """
        records = self._execute_query(query, (converted_id, limit))
        logger.info("Business logs para %s: %s eventos", business_id, len(records or []))
        return records or []
