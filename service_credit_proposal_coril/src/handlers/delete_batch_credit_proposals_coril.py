"""
Handler Lambda para eliminar varias propuestas de crédito coril en lote.
Recibe una lista de proposal_ids en el body y las elimina; notifica por AppSync.
"""
import logging
import json
from typing import Dict, Any, List
from common.response import Response
from common.exceptions.handler_exception import handle_exception
from common.exceptions.exceptions import BadRequestError
from common.auth.auth_proxy import authorize
from common.auth.strategies import RoleHierarchyStrategy
from services.service_credit_proposal_coril.src.config.dependencies import get_credit_proposal_coril_service

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

credit_proposal_coril_service = get_credit_proposal_coril_service()


@authorize(required_permission="ANALYST", strategy_cls=RoleHierarchyStrategy)
def lambda_handler(event: Dict[str, Any], context) -> Dict[str, Any]:
    """
    Elimina varias propuestas de crédito coril por IDs.

    Body:
    - proposal_ids: Lista de IDs de propuestas a eliminar (requerido)
    """
    request_id = getattr(context, "aws_request_id", "unknown") if context else "unknown"
    logger.info(f"Inicio eliminación en lote - Request ID: {request_id}")

    try:
        user = event.get("user")
        if not user:
            logger.error("Error: usuario no autenticado")
            raise BadRequestError("Usuario no reconocido.")

        if not user.get("evaluator_id"):
            raise BadRequestError("El usuario no tiene un evaluator_id asignado.")

        body = event.get("body")
        if not body:
            raise BadRequestError("El body es requerido.")
        if isinstance(body, str):
            body = json.loads(body)

        proposal_ids = body.get("proposal_ids")
        if not isinstance(proposal_ids, list):
            raise BadRequestError("El campo 'proposal_ids' debe ser una lista.")
        if not proposal_ids:
            return Response(
                status_code=200,
                body={
                    "success": True,
                    "message": "No hay propuestas para eliminar",
                    "data": {"deleted": [], "failed": []},
                    "request_id": request_id,
                },
            ).to_dict()

        result = credit_proposal_coril_service.delete_credit_proposals_coril_batch(proposal_ids)
        deleted = result.get("deleted", [])
        failed = result.get("failed", [])

        return Response(
            status_code=200,
            body={
                "success": True,
                "message": f"Eliminadas {len(deleted)} propuesta(s); {len(failed)} fallida(s).",
                "data": result,
                "request_id": request_id,
            },
        ).to_dict()

    except BadRequestError:
        raise
    except Exception as err:
        logger.error(f"Error en lambda_handler batch delete: {str(err)} - Request ID: {request_id}", exc_info=True)
        return handle_exception(err, request_id)


if __name__ == "__main__":
    event = {
        "user": {
            "sub": "6438c468-1091-701d-6dc5-b6a04fbd33aa",
            "roles": ["ANALYST"],
            "evaluator_id": "9ca49e78-dec4-4046-a48a-8fc661110b28",
        },
        "body": json.dumps({"proposal_ids": ["399c68a2-7df7-40e5-b102-5367f5af112c"]}),
    }
    print("\nEjecutando lambda_handler batch delete...\n")
    result = lambda_handler(event, None)
    print("\nResultado:")
    print(json.dumps(result, indent=2, ensure_ascii=False))
