import logging
import json as json_module
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
    reemplazando el proposal_data y regenerando PDF y Word en S3.

    Path:
      - proposal_id: ID de la propuesta

    Body:
      - proposal_data: JSON completo de la propuesta (requerido)
      - total_amount: Monto total (opcional)
      - currency: Moneda (opcional)
    """
    request_id = getattr(context, "aws_request_id", "unknown")
    logger.info(
        f"Inicio actualización propuesta crédito coril - Request ID: {request_id}"
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

        body = event.get("body")
        if not body:
            raise BadRequestError("El body es requerido.")

        if isinstance(body, str):
            body = json_module.loads(body)

        proposal_data = body.get("proposal_data")
        if not proposal_data:
            raise BadRequestError("proposal_data es requerido.")

        total_amount = body.get("total_amount")
        currency = body.get("currency")

        logger.info(f"Actualizando propuesta coril {proposal_id}")

        result = credit_proposal_coril_service.update_credit_proposal_coril(
            proposal_id=proposal_id,
            evaluator_id=evaluator_id,
            proposal_data=proposal_data,
            total_amount=total_amount,
            currency=currency,
        )

        response = Response(
            status_code=200,
            body={
                "success": True,
                "message": "Propuesta de crédito coril actualizada exitosamente",
                "data": result,
                "request_id": request_id,
            },
        )

        return {
            "statusCode": response.status_code,
            "headers": response.headers,
            "body": json_module.dumps(response.body, ensure_ascii=False),
        }

    except BadRequestError:
        raise
    except Exception as err:
        logger.error(
            f"Error en lambda_handler actualización propuesta coril: {str(err)} - Request ID: {request_id}",
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
        "body": {
            "proposal_data": {
                "use_template_design": 1,
                "header": {"economicGroup": "GE XXXX"},
            },
            "total_amount": 2000000,
            "currency": "PEN",
        },
    }

    print("\nEjecutando lambda_handler update...\n")
    result = lambda_handler(event, type("ctx", (), {"aws_request_id": "local-test"})())
    print("\nResultado:")
    print(json.dumps(result, indent=2, ensure_ascii=False))


