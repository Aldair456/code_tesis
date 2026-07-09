from typing import Any, Dict

from common.exceptions.exceptions import BadRequestError
from services.service_credit_proposal_coril.src.repositories.evaluator_routes_repository import (
    EvaluatorRoutesRepository,
)


class EvaluatorRouteService:
    """Obtiene la ruta (proposal_type) configurada para un evaluator."""

    def __init__(self, evaluator_routes_repository: EvaluatorRoutesRepository):
        self._evaluator_routes_repository = evaluator_routes_repository

    def get_route_for_evaluator(self, evaluator_id: str) -> Dict[str, Any]:
        if not evaluator_id or not str(evaluator_id).strip():
            raise BadRequestError("El usuario no tiene un evaluator_id asignado.")

        route = self._evaluator_routes_repository.get_evaluator_route(evaluator_id)
        return route if route is not None else {}
