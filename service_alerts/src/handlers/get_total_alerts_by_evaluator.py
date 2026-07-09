import logging
from common.response import Response
from services.service_alerts.src.config.dependencies import get_alert_service
from common.exceptions.handler_exception import handle_exception
from common.exceptions.exceptions import BadRequestError
from common.auth.auth_proxy import authorize
from common.auth.strategies import RoleHierarchyStrategy
import json

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


@authorize(required_permission="ANALYST", strategy_cls=RoleHierarchyStrategy)
def lambda_handler(event, context):
    """
    Handler para obtener el total de alertas activas por evaluator_id

    Endpoint: GET /alerts/total/{evaluator_id}
    """
    request_id = getattr(context, "aws_request_id", "unknown")
    logger.info(f"=== INICIANDO OBTENCIÓN DE TOTAL DE ALERTAS - Request ID: {request_id} ===")

    try:
        # Obtener servicio de alertas
        alert_service = get_alert_service()

        # Validar usuario autenticado
        user = event.get("user")
        if not user:
            logger.error("Usuario no autenticado")
            raise BadRequestError("Usuario no reconocido.")

        # Obtener evaluator_id del usuario
        evaluator_id = user.get("evaluator_id")
        if not evaluator_id:
            logger.error("Usuario sin evaluator_id")
            raise BadRequestError("El usuario no tiene un evaluator_id asignado.")

        logger.info(f"Obteniendo total de alertas para evaluator_id: {evaluator_id}")

        # Obtener total de alertas activas
        total_alerts = alert_service.get_total_active_alerts_by_evaluator(evaluator_id)

        # Preparar respuesta
        response = {
            "statusCode": 200,
            "body": json.dumps({
                "success": True,
                "message": f"Total de alertas activas obtenido correctamente para evaluator_id: {evaluator_id}",
                "data": {
                    "total_alertas_activas": total_alerts
                }
            })
        }

        logger.info(f"=== PROCESAMIENTO COMPLETADO ===")
        logger.info(f"Total de alertas activas: {total_alerts}")

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
        }
    }

    result = lambda_handler(test_event, None)
    print(f"Resultado: {result}")
