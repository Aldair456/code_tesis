import logging
from typing import Type
from functools import wraps
from common_auth_api_keys.strategies import AuthorizationStrategy, RoleHierarchyStrategy
from common.response import Response

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def get_user_from_event(event: dict) -> dict:
    """
    Extrae los datos del usuario desde el evento Lambda utilizando los claims del token de autorización (Cognito).
    Si el campo 'user' ya está presente (por ejemplo, en pruebas), lo devuelve directamente.
    """

    # solo test
    if "user" in event:
        return event["user"]

    try:
        claims = event["requestContext"]["authorizer"]["claims"]

        user = {
            "email": claims.get("email"),
            "sub": claims.get("sub"),
            "name": claims.get("name", "unidentified"),
            "roles": claims.get("cognito:groups", "").split(",") if claims.get("cognito:groups") else [],
            "evaluator_id": claims.get("custom:organization_id"),# aca cambie a organizacion solo test nuevo
            "created_by": claims.get("custom:created_by"),
        }

        logger.info("Claims extraídos: %s", user)
        return user

    except (KeyError, TypeError) as e:
        logger.warning("No se pudo extraer el usuario del evento: %s", e)
        return {}

def authorize(required_permission, strategy_cls: Type[AuthorizationStrategy] = RoleHierarchyStrategy):
    def decorator(handler):
        @wraps(handler)
        def wrapper(event, context):
            user = get_user_from_event(event)
            strategy = strategy_cls()

            if not strategy.is_authorized(user, required_permission):
                return Response(status_code=403, body={
                    "message": f"Acceso denegado según estrategia {strategy_cls.__name__}"
                }).to_dict()
            event["user"] = user
            return handler(event, context)
        return wrapper
    return decorator
