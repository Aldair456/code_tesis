import logging
from typing import Dict, Any
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
    Handler Lambda para obtener propuestas de crédito coril.
    
    Query Parameters:
    - business_id: ID del negocio (requerido)
    - limit: Límite de resultados (opcional, default: 100)
    - offset: Offset para paginación (opcional, default: 0)
    """
    request_id = getattr(context, "aws_request_id", "unknown")
    logger.info(f"Inicio obtención propuestas crédito coril - Request ID: {request_id}")

    try:
        # Validar usuario autenticado
        user = event.get('user')
        if not user:
            logger.error("Error: usuario no autenticado")
            raise BadRequestError("Usuario no reconocido.")
        
        evaluator_id = user.get('evaluator_id')
        if not evaluator_id:
            raise BadRequestError("El usuario no tiene un evaluator_id asignado.")
        
        # Obtener query parameters
        query_params = event.get('queryStringParameters') or {}
        
        # Obtener business_id (requerido)
        business_id = query_params.get('business_id')
        if not business_id:
            raise BadRequestError("business_id es requerido.")
        
        # Parsear limit y offset
        limit_str = query_params.get('limit', '100')
        offset_str = query_params.get('offset', '0')
        
        try:
            limit = min(int(str(limit_str).strip()), 1000)  # Máximo 1000
            offset = max(int(str(offset_str).strip()), 0)   # Mínimo 0
        except (ValueError, AttributeError):
            logger.warning("Parámetros limit/offset inválidos, usando defaults")
            limit = 100
            offset = 0
        
        logger.info(f"Obteniendo propuestas coril para evaluator_id: {evaluator_id}, business_id: {business_id} (limit: {limit}, offset: {offset})")
        
        # Obtener propuestas
        proposals = credit_proposal_coril_service.get_by_evaluator_id(
            evaluator_id=evaluator_id,
            business_id=business_id,
            limit=limit,
            offset=offset
        )
        
        return Response(
            status_code=200,
            body={
                "success": True,
                "message": "Propuestas de crédito coril obtenidas exitosamente",
                "data": {
                    "proposals": proposals,
                    "pagination": {
                        "limit": limit,
                        "offset": offset,
                        "count": len(proposals)
                    }
                },
                "request_id": request_id
            }
        ).to_dict()
        
    except BadRequestError:
        raise
    except Exception as err:
        logger.error(f"Error en lambda_handler: {str(err)} - Request ID: {request_id}", exc_info=True)
        return handle_exception(err, request_id)


if __name__ == "__main__":
    import json
    
    event = {
        "user": {
            "sub": "6438c468-1091-701d-6dc5-b6a04fbd33aa",
            "roles": ["ANALYST"],
            "evaluator_id": "9ca49e78-dec4-4046-a48a-8fc661110b28"
        },
        "queryStringParameters": {
            "business_id": "833bb9fa-9213-46b7-b0f8-f170b8aa1023",
            "limit": "50",
            "offset": "0"
        }
    }
    
    print("\nEjecutando lambda_handler...\n")
    result = lambda_handler(event, None)
    print("\nResultado:")
    print(json.dumps(result, indent=2, ensure_ascii=False))


