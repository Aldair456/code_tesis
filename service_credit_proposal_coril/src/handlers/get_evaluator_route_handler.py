"""
Handler Lambda: obtiene la ruta (proposal_type) configurada para un evaluator.

GET /credit-proposals-coril/evaluator-route
  - evaluator_id desde JWT (event["user"]["evaluator_id"])
  - Respuesta: {"proposal_type": "GC"|"CORIL"|..., "target_queue_url": null} o {}
"""
from typing import Dict, Any
import logging
import json

from common.response import Response
from common.exceptions.handler_exception import handle_exception
from common.exceptions.exceptions import BadRequestError
from common.auth.auth_proxy import authorize
from common.auth.strategies import RoleHierarchyStrategy
from services.service_credit_proposal_coril.src.config.dependencies import get_evaluator_route_service

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

evaluator_route_service = get_evaluator_route_service()


@authorize(required_permission="ANALYST", strategy_cls=RoleHierarchyStrategy)
def lambda_handler(event: Dict[str, Any], context) -> Dict[str, Any]:
    request_id = getattr(context, "aws_request_id", "unknown") if context else "unknown"
    logger.info("Inicio obtención ruta evaluator - Request ID: %s", request_id)

    try:
        user = event.get("user")
        if not user:
            logger.error("Error: usuario no autenticado")
            raise BadRequestError("Usuario no reconocido.")

        evaluator_id = user.get("evaluator_id")
        logger.info(
            "Buscando ruta para evaluator_id=%s (obtenido del token)", evaluator_id
        )

        route = evaluator_route_service.get_route_for_evaluator(evaluator_id)

        response = Response(status_code=200, body=route)
        return {
            "statusCode": response.status_code,
            "headers": response.headers,
            "body": json.dumps(response.body, ensure_ascii=False),
        }

    except BadRequestError:
        raise
    except Exception as e:
        logger.error(
            "Error en GetEvaluatorRoute: %s - Request ID: %s",
            str(e),
            request_id,
            exc_info=True,
        )
        return handle_exception(e, request_id)


if __name__ == "__main__":
    event = {
        "user": {
            "sub": "6438c468-1091-701d-6dc5-b6a04fbd33aa",
            "roles": ["ANALYST"],
            "evaluator_id": "9ca49e78-dec4-4046-a48a-8fc661110b28",
        },
    }
    result = lambda_handler(event, type("ctx", (), {"aws_request_id": "local-test"})())
    print(json.dumps(result, indent=2, ensure_ascii=False))
