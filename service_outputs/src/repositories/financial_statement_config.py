from common.repositories.base import BaseRepository
from services.service_outputs.src.models.models import FinancialStatementConfig


class FinancialStatementConfigRepository(BaseRepository):
    def __init__(self):
        super().__init__("financial_statement_configs", FinancialStatementConfig)
