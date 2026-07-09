"""
Handler para inicializar una propuesta de crédito coril.
Crea el registro en BD SIN proposal_data (ese se llena después por otro lambda).
Retorna el credit_memo_id para usar en el Step Function.
"""
import logging
import json
from typing import Dict, Any
from common.response import Response
from common.exceptions.handler_exception import handle_exception
from common.exceptions.exceptions import BadRequestError
from common.auth.auth_proxy import authorize
from common.auth.strategies import RoleHierarchyStrategy
from services.service_credit_proposal_coril.src.config.dependencies import get_credit_proposal_coril_service

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

credit_proposal_service = get_credit_proposal_coril_service()


@authorize(required_permission="ANALYST", strategy_cls=RoleHierarchyStrategy)
def lambda_handler(event: Dict[str, Any], context) -> Dict[str, Any]:
    """
    Handler Lambda para inicializar una propuesta de crédito coril.
    Crea el registro en BD sin proposal_data (se llena después).

    Body:
    - business_id: ID del negocio (requerido)
    - deal_id: ID del deal (opcional)

    Returns:
        credit_memo_id y proposal_number para usar en Step Function
    """
    request_id = getattr(context, "aws_request_id", "unknown") if context else "unknown"
    logger.info(f"Inicio inicialización de credit proposal coril - Request ID: {request_id}")

    try:
        user = event.get('user')
        if not user:
            logger.error("Error: usuario no autenticado")
            raise BadRequestError("Usuario no reconocido.")
        # Guardamos user_name (nombre del usuario), no user_id
        user_name = (user.get('name') or user.get('email') or str(user.get('sub', '')) or '').strip()
        if not user_name:
            raise BadRequestError("No se pudo obtener el nombre del usuario.")

        body = event.get('body')
        if not body:
            raise BadRequestError("El body es requerido.")
        if isinstance(body, str):
            body = json.loads(body)

        business_id = body.get('business_id')
        if not business_id:
            raise BadRequestError("business_id es requerido.")
        deal_id = body.get('deal_id')

       
        logger.info(f"Inicializando credit proposal para business_id: {business_id}")

        result = credit_proposal_service.init_proposal(
            business_id=business_id,
            user_name=user_name,
            deal_id=deal_id,
        )
        logger.info(
            "Credit proposal inicializado: %s, proposal_number: %s",
            result["credit_memo_id"],
            result["proposal_number"],
        )

        response = Response(
            status_code=201,
            body={
                "success": True,
                "message": "Propuesta de crédito inicializada exitosamente",
                "data": result,
                "request_id": request_id
            }
        )
        return {
            "statusCode": response.status_code,
            "headers": response.headers,
            "body": json.dumps(response.body, ensure_ascii=False)
        }
    except BadRequestError:
        raise
    except Exception as err:
        logger.error(f"Error en lambda_handler init: {str(err)} - Request ID: {request_id}", exc_info=True)
        return handle_exception(err, request_id)
