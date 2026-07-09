import logging
from typing import Dict, Any
from common.response import Response
from common.exceptions.handler_exception import handle_exception
from common.exceptions.exceptions import BadRequestError
from common.auth.auth_proxy import authorize
from common.auth.strategies import RoleHierarchyStrategy
from services.service_credit_proposal_coril.src.config.dependencies import get_credit_proposal_coril_service
from services.service_credit_proposal_coril.src.utils.appsync_status import notify_eliminado

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

credit_proposal_coril_service = get_credit_proposal_coril_service()


@authorize(required_permission="ANALYST", strategy_cls=RoleHierarchyStrategy)
def lambda_handler(event: Dict[str, Any], context) -> Dict[str, Any]:
    """
    Handler Lambda para eliminar una propuesta de crédito coril.
    
    Path Parameters:
    - proposal_id: ID de la propuesta de crédito coril a eliminar
    """
    request_id = getattr(context, "aws_request_id", "unknown")
    logger.info(f"Inicio eliminación propuesta crédito coril - Request ID: {request_id}")

    try:
        # Validar usuario autenticado
        user = event.get('user')
        if not user:
            logger.error("Error: usuario no autenticado")
            raise BadRequestError("Usuario no reconocido.")
        
        evaluator_id = user.get('evaluator_id')
        if not evaluator_id:
            raise BadRequestError("El usuario no tiene un evaluator_id asignado.")
        
        # Obtener proposal_id del path
        path_params = event.get('pathParameters') or {}
        proposal_id = path_params.get('proposal_id')
        
        if not proposal_id:
            logger.error("Falta parámetro 'proposal_id' en pathParameters")
            raise BadRequestError("El parámetro 'proposal_id' es requerido en la ruta.")
        
        # Validación básica del formato
        if not proposal_id.strip():
            logger.error("El parámetro 'proposal_id' está vacío")
            raise BadRequestError("El parámetro 'proposal_id' no puede estar vacío.")
        
        logger.info(f"Eliminando propuesta coril: {proposal_id}")
        
        # Eliminar propuesta (con validación de acceso y eliminación de S3)
        success = credit_proposal_coril_service.delete_credit_proposal_coril(proposal_id)
        
        if success:
            return Response(
                status_code=200,
                body={
                    "success": True,
                    "message": "Propuesta de crédito coril eliminada exitosamente",
                    "data": {
                        "proposal_id": proposal_id
                    },
                    "request_id": request_id
                }
            ).to_dict()
        else:
            raise BadRequestError("No se pudo eliminar la propuesta")
        
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
        "pathParameters": {
            "proposal_id": "399c68a2-7df7-40e5-b102-5367f5af112c"
        }
    }
    
    print("\nEjecutando lambda_handler...\n")
    result = lambda_handler(event, None)
    print("\nResultado:")
    print(json.dumps(result, indent=2, ensure_ascii=False))
