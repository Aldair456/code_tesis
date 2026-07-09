from common.repositories.base import BaseRepository
from common.models.models import Output
from typing import List, Dict, Any

class OutputRepository(BaseRepository[Output]):
    def __init__(self):
        super().__init__("outputs", Output)
    
    def find_distinct_outputs(self, category: str = None, evaluator_id: str = None) -> List[Output]:
        """
        Obtiene outputs distintos ordenados por categoría y nombre

        Args:
            category: Categoría específica para filtrar (opcional)
            evaluator_id: ID del evaluador para filtrar (opcional)

        Returns:
            Lista de outputs completos (Output objects) ordenados
        """
        filters = {}
        if category:
            filters['category'] = category
        if evaluator_id:
            filters['evaluator_id'] = evaluator_id
        if filters:
            return self.find_by_attributes(filters=filters, limit=1000, order_by=['name'])
        return self.find_all(limit=1000)

