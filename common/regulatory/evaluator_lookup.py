from typing import Optional

from common.models.models import Evaluator
from common.repositories.base import BaseRepository


def get_evaluator(evaluator_id: str) -> Optional[Evaluator]:
    if not evaluator_id or not str(evaluator_id).strip():
        return None
    repo = BaseRepository("evaluators", Evaluator)
    return repo.find_by_id(str(evaluator_id).strip())
