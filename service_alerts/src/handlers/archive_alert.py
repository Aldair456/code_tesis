import json
import logging
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
    Handler para archivar una alerta específica

    Endpoint: PUT /alerts/{alert_id}/archive
    """
    request_id = getattr(context, "aws_request_id", "unknown")
    logger.info(f"=== INICIANDO ARCHIVADO DE ALERTA - Request ID: {request_id} ===")

    try:
        # Obtener servicio de alertas
        alert_service = get_alert_service()

        # Validar usuario autenticado
        user = event.get("user")
        if not user:
            logger.error("Usuario no autenticado")
            raise BadRequestError("Usuario no reconocido.")

        # Obtener alert_id de los path parameters
        path_params = event.get("pathParameters") or {}
        alert_id = path_params.get("alert_id")
        if not alert_id:
            logger.error("Falta parámetro 'alert_id' en pathParameters")
            raise BadRequestError("El parámetro 'alert_id' es requerido en la ruta.")

        logger.info(f"Archivando alerta con ID: {alert_id}")

        # Archivar la alerta
        success = alert_service.archive_alert(alert_id)

        if not success:
            logger.warning(f"No se pudo archivar la alerta {alert_id} - posiblemente no existe")
            return Response(
                status_code=404,
                body={
                    "success": False,
                    "message": f"Alerta con ID {alert_id} no encontrada o ya archivada.",
                    "data": {
                        "alert_id": alert_id,
                        "archived": False
                    }
                },
            ).to_dict()

        # Preparar respuesta exitosa
        response = {
            "statusCode": 200,
            "body": json.dumps({
                "success": True,
                "message": f"Alerta {alert_id} archivada correctamente.",
                "data": {
                    "alert_id": alert_id,
                    "archived": True
                }
            })
        }

        logger.info(f"=== ARCHIVADO COMPLETADO ===")
        logger.info(f"Alerta {alert_id} archivada exitosamente")

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
            "alert_id": "64d5cf37-a6bf-4346-a82e-682b98e2fe2a"
        }
    }

    result = lambda_handler(test_event, None)
    print(f"Resultado: {result}")
