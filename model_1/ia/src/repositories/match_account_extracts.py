from typing import Optional

from common.repositories.base import BaseRepository
from common.models.models import MatchAccountExtract


class MatchAccountExtractsRepository(BaseRepository[MatchAccountExtract]):
    """Resuelve account_id (evaluador) a partir de account_extract_id."""

    def __init__(self):
        super().__init__("match_account_extracts", MatchAccountExtract)

    def find_bank_account_id_for_extract(
        self, account_extract_id: str, evaluator_id: str
    ) -> Optional[str]:
        if not account_extract_id or not evaluator_id:
            return None
        query = """
            SELECT mae.account_id::text AS account_id
            FROM match_account_extracts mae
            INNER JOIN accounts a ON a.id = mae.account_id
            WHERE mae.account_extract_id = %s::uuid AND a.evaluator_id = %s::uuid
            ORDER BY mae.created_at ASC
            LIMIT 1
        """
        row = self._execute_query_one(query, (account_extract_id, evaluator_id))
        if not row:
            return None
        return row.get("account_id")
