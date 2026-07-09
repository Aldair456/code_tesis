from common.repositories.base import BaseRepository
from common.models.models import DerivedCashflow
from typing import List


class DerivedCashflowRepository(BaseRepository[DerivedCashflow]):
    def __init__(self):
        super().__init__("derived_cashflows", DerivedCashflow)

    def find_by_evaluator(self, evaluator_id: str) -> List[DerivedCashflow]:
        return self.find_by_attributes(
            filters={"evaluator_id": evaluator_id},
            limit=1000,
            order_by=["priority", "name"]
        )
