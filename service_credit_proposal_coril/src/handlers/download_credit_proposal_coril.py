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
    Handler Lambda para obtener URL de descarga del PDF de una propuesta de crédito coril.
    Verifica que el usuario tenga acceso a la propuesta antes de generar la URL.
    
    Path Parameters:
    - proposal_id: ID de la propuesta de crédito coril
    
    Query Parameters:
    - expiration: Tiempo de expiración de la URL en segundos (opcional, default: 3600 = 1 hora)
    """
    request_id = getattr(context, "aws_request_id", "unknown")
    logger.info(f"Inicio generación de URL de descarga coril - Request ID: {request_id}")

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
        
        # Obtener parámetro de expiración (opcional)
        query_params = event.get('queryStringParameters') or {}
        expiration_str = query_params.get('expiration', '3600')
        
        # Limpiar y convertir a int de forma segura
        try:
            expiration_clean = str(expiration_str).strip().rstrip('\\').rstrip()
            expiration = int(expiration_clean)
            logger.info(f"Expiración parseada correctamente: {expiration} segundos")
        except (ValueError, AttributeError) as e:
            logger.warning(f"Valor inválido para expiration: '{expiration_str}'. Usando default 3600. Error: {e}")
            expiration = 3600
        
        # Validar expiración (mínimo 60 segundos, máximo 7 días)
        if expiration < 60:
            logger.warning(f"Expiración {expiration}s menor al mínimo (60s), ajustando a 60s")
            expiration = 60
        elif expiration > 604800:  # 7 días
            logger.warning(f"Expiración {expiration}s mayor al máximo (604800s/7 días), ajustando a 604800s")
            expiration = 604800
        
        logger.info(f"Generando URL de descarga para propuesta coril: {proposal_id} (expiración: {expiration}s)")
        
        # Obtener URL de descarga (con verificación de acceso)
        download_info = credit_proposal_coril_service.get_download_url(
            proposal_id=proposal_id,
            evaluator_id=evaluator_id,
            expiration=expiration
        )
        
        return Response(
            status_code=200,
            body={
                "success": True,
                "message": "URL de descarga coril generada exitosamente",
                "data": download_info,
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
        "pathParameters": {
            "proposal_id": "5f05349f-808b-4ea8-a433-b1443d8f11c9"
        },
        "queryStringParameters": {
            "expiration": "3600"
        }
    }
    
    print("\nEjecutando lambda_handler...\n")
    result = lambda_handler(event, None)
    print("\nResultado:")
    print(json.dumps(result, indent=2, ensure_ascii=False))
