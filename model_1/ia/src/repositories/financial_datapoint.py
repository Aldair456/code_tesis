from common.repositories.base import BaseRepository
from common.models.models import FinancialDataPoint


class FinancialDataPointRepository(BaseRepository[FinancialDataPoint]):
    def __init__(self):
        super().__init__("financial_datapoints", FinancialDataPoint)
