from common.repositories.base import BaseRepository
from common.models.models import FinancialCashflowDatapoint
from typing import List, Dict, Any


class FinancialCashflowDatapointRepository(BaseRepository):
    def __init__(self):
        super().__init__("financial_cashflow_datapoints", FinancialCashflowDatapoint)

    def bulk_create_for_statement(self, statement_id: str, datapoints_data: List[Dict[str, Any]]) -> int:
        enriched_data = []
        for data in datapoints_data:
            enriched_data.append({**data, "financial_statement_id": statement_id})
        return self.create_many(enriched_data)
