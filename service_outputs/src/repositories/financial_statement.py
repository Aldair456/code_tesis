from common.repositories.base import BaseRepository
from common.models.models import FinancialStatement

class FinancialStatementRepository(BaseRepository[FinancialStatement]):
    def __init__(self):
        super().__init__("financial_statements", FinancialStatement)

