import json
import logging
from uuid import UUID
from datetime import datetime, date
from decimal import Decimal
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
    Handler para obtener alertas archivadas de un business específico

    Endpoint: GET /businesses/{business_id}/alerts/archived
    """
    request_id = getattr(context, "aws_request_id", "unknown")
    logger.info(f"=== INICIANDO OBTENCIÓN DE ALERTAS ARCHIVADAS POR BUSINESS - Request ID: {request_id} ===")

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
            logger.error("business_id no proporcionado en path parameters")
            raise BadRequestError("business_id es requerido.")

        logger.info(f"Obteniendo alertas archivadas para business_id: {business_id}")

        # Obtener parámetros de paginación de query parameters
        query_params = event.get("queryStringParameters") or {}
        limit = int(query_params.get("limit", 100))
        offset = int(query_params.get("offset", 0))

        # Validar parámetros de paginación
        if limit < 1 or limit > 1000:
            raise BadRequestError("El parámetro 'limit' debe estar entre 1 y 1000.")
        if offset < 0:
            raise BadRequestError("El parámetro 'offset' debe ser mayor o igual a 0.")

        logger.info(f"Obteniendo alertas archivadas para business {business_id} (limit: {limit}, offset: {offset})")

        # Obtener alertas archivadas por business_id con paginación
        alerts = alert_service.get_archived_alerts_by_business(business_id, limit, offset)

        # Serializar los datos para manejar UUIDs, datetime, etc.

        # Console.log para ver todas las alertas archivadas del business
        logger.info(f"=== ALERTAS ARCHIVADAS ENCONTRADAS PARA BUSINESS {business_id} ===")
        logger.info(f"Total de alertas archivadas encontradas: {len(alerts) if alerts else 0}")

        # Preparar respuesta
        response_data = {
            "success": True,
            "message": f"Alertas archivadas para business {business_id} obtenidas correctamente.",
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

        response = {
            "statusCode": 200,
            "body": json.dumps(response_data, default=str)
        }

        logger.info(f"=== PROCESAMIENTO COMPLETADO ===")
        logger.info(f"Total de alertas archivadas encontradas para business {business_id}: {len(alerts)}")

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
            "business_id": "9279f069-e142-4ba3-82a7-9e2406c1388e"
        },
        "queryStringParameters": {
            "limit": 50,
            "offset": 0
        }
    }

    result = lambda_handler(test_event, None)
    print(f"Resultado: {result}")