import json
import logging
from uuid import UUID
from datetime import datetime
from common.response import Response
from services.service_alerts.src.config.dependencies import get_alert_service
from common.exceptions.handler_exception import handle_exception
from common.exceptions.exceptions import BadRequestError
from common.auth.auth_proxy import authorize
from common.auth.strategies import RoleHierarchyStrategy

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


@authorize(required_permission="ANALYST", strategy_cls=RoleHierarchyStrategy)
def lambda_handler(event, context):
    """
    Handler para obtener las alertas activas de un business específico

    Endpoint: GET /alerts/business/{business_id}
    """
    request_id = getattr(context, "aws_request_id", "unknown")
    logger.info(f"=== INICIANDO OBTENCIÓN DE ALERTAS POR BUSINESS - Request ID: {request_id} ===")

    try:
        # Obtener servicio de alertas
        alert_service = get_alert_service()

        # Validar usuario autenticado
        user = event.get("user")
        if not user:
            logger.error("Usuario no autenticado")
            raise BadRequestError("Usuario no reconocido.")

        # Obtener business_id de los path parameters
        path_params = event.get("pathParameters") or {}
        business_id = path_params.get("business_id")
        if not business_id:
            logger.error("Falta parámetro 'business_id' en pathParameters")
            raise BadRequestError("El parámetro 'business_id' es requerido en la ruta.")

        # Obtener parámetros de paginación de query parameters
        query_params = event.get("queryStringParameters") or {}
        limit = int(query_params.get("limit", 100))
        offset = int(query_params.get("offset", 0))

        # Validar parámetros de paginación
        if limit < 1 or limit > 1000:
            raise BadRequestError("El parámetro 'limit' debe estar entre 1 y 1000.")
        if offset < 0:
            raise BadRequestError("El parámetro 'offset' debe ser mayor o igual a 0.")

        logger.info(f"Obteniendo alertas activas para business_id: {business_id} (limit: {limit}, offset: {offset})")

        alerts = alert_service.get_active_alerts_by_business_id(business_id, limit, offset)

        response_data = {
            "success": True,
            "message": f"Alertas activas obtenidas correctamente para business_id: {business_id}",
            "data": {
                "business_id": business_id,
                "pagination": {
                    "limit": limit,
                    "offset": offset,
                    "returned_count": len(alerts)
                },
                "alerts": alerts
            }
        }

        # Limpiar UUIDs y datetimes antes de serializar

        # Preparar respuesta
        response = {
            "statusCode": 200,
            "body": json.dumps(response_data, default=str)
        }

        logger.info(f"=== PROCESAMIENTO COMPLETADO ===")
        logger.info(f"Total de alertas encontradas: {len(alerts)}")

        return response

    except BadRequestError as e:
        logger.error(f"Error de validación: {e}")
        return handle_exception(e, request_id)
    except Exception as e:
        logger.error(f"Error inesperado en handler: {e}")
        return handle_exception(e, request_id)


if __name__ == '__main__':
    # Ejemplo de evento para testing
    test_event = {
        "user": {
            "roles": ["ANALYST"],
            "evaluator_id": "9ca49e78-dec4-4046-a48a-8fc661110b28"
        },
        "pathParameters": {
            "business_id": "5f24082a-c293-4e6c-ad5a-c934a8a97837"
        },

    }

    result = lambda_handler(test_event, None)
    print(f"Resultado: {result}")