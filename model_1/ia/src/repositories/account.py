from typing import List

from common.models.models import AccountExtract
from common.repositories.base import BaseRepository


class AccountRepository(BaseRepository[AccountExtract]):
    """Catálogo global de cuentas para extracción IA (tabla account_extracts)."""

    def __init__(self):
        super().__init__("account_extracts", AccountExtract)

    def find_all_by_filters(
        self,
        name: str = None,
        type: str = None,
        limit: int = None,
        offset: int = None,
    ) -> List[AccountExtract]:
        filters = {}

        if name:
            filters["name"] = name

        if type:
            filters["type"] = type

        if not filters:
            return []

        actual_limit = limit if limit is not None else 1000

        return self.find_by_attributes(
            filters=filters,
            limit=actual_limit,
            offset=offset or 0,
        )
