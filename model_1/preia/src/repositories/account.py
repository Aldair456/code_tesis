from common.repositories.base import BaseRepository
from common.models.models import Account
from typing import List

class AccountRepository(BaseRepository[Account]):
    def __init__(self):
        super().__init__("accounts", Account)

    def find_all_by_filters(self,
                            name: str = None,
                            type: str = None,
                            limit: int = None,
                            offset: int = None) -> List[Account]:
        """
        Obtiene cuentas filtradas por nombre y/o tipo
        Devuelve una lista de objetos Account
        """
        filters = {}

        if name:
            filters['name'] = name

        if type:
            filters['type'] = type

        # Si no hay filtros, devolver lista vacía por seguridad
        if not filters:
            return []

        # Para limit=None, usar un límite razonable por defecto (ej: 1000)
        # O mejor aún, requerir que siempre se especifique un límite
        if limit is None:
            actual_limit = 1000  # Límite más seguro
        else:
            actual_limit = limit

        accounts = self.find_by_attributes(
            filters=filters,
            limit=actual_limit,
            offset=offset or 0
        )

        return accounts






