import logging
from functools import wraps
from common_auth_api_keys.src.config.dependencies import get_api_key_auth_service
from common.response import Response

logger = logging.getLogger(__name__)


auth_service = get_api_key_auth_service()

def require_api_key():
    """
    Decorador para proteger handlers de Lambda con validación de API Key.

    Args:
        repository_getter: Función que retorna el repositorio de api_keys

    Usage:
        @require_api_key(lambda: ApiKeyRepository(get_db_session()))
        def handler(event, context):
            api_key_data = event["api_key_data"]
            evaluator_id = api_key_data["evaluator_id"]
            ...
    """

    def decorator(handler):
        @wraps(handler)
        def wrapper(event, context):



            # Validar acceso
            is_valid, api_key_data, error_message = auth_service.validate_access(event)

            if not is_valid:
                logger.warning(
                    f"Acceso denegado a {handler.__name__}. "
                    f"Razón: {error_message}"
                )
                return Response(
                    status_code=403,
                    body={
                        "message": error_message or "Acceso denegado",
                        "error": "invalid_api_key"
                    }
                ).to_dict()

            # Inyectar datos del API key en el evento
            event["api_key_data"] = {
                "key_id": api_key_data.key_id,
                "evaluator_id": api_key_data.evaluator_id,
                "key_name": api_key_data.name
            }

            logger.info(
                f"Acceso autorizado vía API Key. "
                f"Evaluator ID: {api_key_data.evaluator_id}"
            )

            # Llamar al handler original
            return handler(event, context)

        return wrapper

    return decorator