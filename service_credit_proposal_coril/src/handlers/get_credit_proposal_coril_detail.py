import logging
from typing import Dict, Any

from common.response import Response
from common.exceptions.handler_exception import handle_exception
from common.exceptions.exceptions import BadRequestError
from common.auth.auth_proxy import authorize
from common.auth.strategies import RoleHierarchyStrategy
from services.service_credit_proposal_coril.src.config.dependencies import (
    get_credit_proposal_coril_service,
)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

credit_proposal_coril_service = get_credit_proposal_coril_service()


@authorize(required_permission="ANALYST", strategy_cls=RoleHierarchyStrategy)
def lambda_handler(event: Dict[str, Any], context) -> Dict[str, Any]:
    """
    Obtiene el detalle completo de una propuesta de crédito coril por ID,
    incluyendo el proposal_data almacenado en la BD.

    Path:
      - proposal_id: ID de la propuesta (UUID)
    """
    request_id = getattr(context, "aws_request_id", "unknown")
    logger.info(
        f"Inicio obtención detalle propuesta crédito coril - Request ID: {request_id}"
    )

    try:
        user = event.get("user")
        if not user:
            logger.error("Error: usuario no autenticado")
            raise BadRequestError("Usuario no reconocido.")

        evaluator_id = user.get("evaluator_id")
        if not evaluator_id:
            raise BadRequestError("El usuario no tiene un evaluator_id asignado.")

        path_params = event.get("pathParameters") or {}
        proposal_id = path_params.get("proposal_id")

        if not proposal_id:
            raise BadRequestError("El parámetro 'proposal_id' es requerido en la ruta.")

        if not str(proposal_id).strip():
            raise BadRequestError("El parámetro 'proposal_id' no puede estar vacío.")

        logger.info(
            f"Obteniendo detalle de propuesta coril {proposal_id} para evaluator_id {evaluator_id}"
        )

        proposal_detail = credit_proposal_coril_service.get_detail_by_id(
            proposal_id=proposal_id,
            evaluator_id=evaluator_id,
        )

        response = Response(
            status_code=200,
            body={
                "success": True,
                "message": "Detalle de propuesta de crédito coril obtenido exitosamente",
                "data": {"credit_proposal_coril": proposal_detail},
                "request_id": request_id,
            },
        )

        return response.to_dict()

    except BadRequestError:
        raise
    except Exception as err:
        logger.error(
            f"Error en lambda_handler detalle propuesta coril: {str(err)} - Request ID: {request_id}",
            exc_info=True,
        )
        return handle_exception(err, request_id)


if __name__ == "__main__":
    import json

    event = {
        "user": {
            "sub": "6438c468-1091-701d-6dc5-b6a04fbd33aa",
            "roles": ["ANALYST"],
            "evaluator_id": "9ca49e78-dec4-4046-a48a-8fc661110b28",
        },
        "pathParameters": {
            "proposal_id": "a8b42fb7-1b43-4d9a-b72a-fe311eb40d94",
        },
    }

    print("\nEjecutando lambda_handler detalle...\n")
    result = lambda_handler(event, type("ctx", (), {"aws_request_id": "local-test"})())
    print("\nResultado:")
    print(json.dumps(result, indent=2, ensure_ascii=False))
