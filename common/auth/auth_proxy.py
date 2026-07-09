import logging
from typing import Type
from functools import wraps

from common.auth.strategies import AuthorizationStrategy, RoleHierarchyStrategy
from common.auth.user_context import (
    enrich_user_from_database,
    parse_evaluator_id_from_claims,
    parse_roles_from_claims,
)
from common.response import Response

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def get_user_from_event(event: dict) -> dict:
    """
    Extrae los datos del usuario desde el evento Lambda utilizando los claims del token de autorización (Cognito).
    Si el campo 'user' ya está presente (por ejemplo, en pruebas), lo devuelve directamente.
    """

    if "user" in event:
        return enrich_user_from_database(event["user"])

    try:
        claims = event["requestContext"]["authorizer"]["claims"]

        user = {
            "email": claims.get("email"),
            "sub": claims.get("sub"),
            "name": claims.get("name", "unidentified"),
            "roles": parse_roles_from_claims(claims),
            "evaluator_id": parse_evaluator_id_from_claims(claims),
            "created_by": claims.get("custom:created_by"),
        }

        user = enrich_user_from_database(user)

        logger.info(
            "Claims resueltos sub=%s roles=%s evaluator_id=%s country=%s",
            user.get("sub"),
            user.get("roles"),
            user.get("evaluator_id"),
            user.get("evaluator_country"),
        )
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
            required = str(required_permission).strip().upper()

            if not user.get("sub"):
                return Response(
                    status_code=401,
                    body={
                        "success": False,
                        "code": "UNAUTHORIZED",
                        "message": "Token inválido o sin identidad de usuario.",
                    },
                ).to_dict()

            if not strategy.is_authorized(user, required):
                roles = user.get("roles") or []
                missing_parts = [
                    f"se requiere rol {required} o superior; roles efectivos: {', '.join(roles) or 'ninguno'}"
                ]
                if not user.get("evaluator_id"):
                    missing_parts.append(
                        "falta evaluator_id (claim custom:organization_id o users.evaluator_id)"
                    )
                logger.warning(
                    "403 auth sub=%s email=%s required=%s roles=%s evaluator_id=%s",
                    user.get("sub"),
                    user.get("email"),
                    required,
                    roles,
                    user.get("evaluator_id"),
                )
                return Response(
                    status_code=403,
                    body={
                        "success": False,
                        "code": "FORBIDDEN",
                        "message": "Acceso denegado. " + ". ".join(missing_parts),
                    },
                ).to_dict()

            event["user"] = user
            return handler(event, context)

        return wrapper

    return decorator
