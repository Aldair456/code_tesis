"""
Cliente genérico para AWS AppSync (GraphQL sobre HTTP con x-api-key).

Diseñado para uso interno Lambda → AppSync (notificaciones en tiempo real).
El frontend se conecta directamente con Cognito JWT via WebSocket (subscripciones).

Uso básico:
    client = AppSyncClient(endpoint=os.environ['APPSYNC_ENDPOINT'],
                           api_key=os.environ['APPSYNC_API_KEY'])

    # Fire-and-forget (no lanza excepciones, solo loguea)
    client.notify(NOTIFY_MESSAGE_MUTATION, {"input": {...}})

    # Con respuesta completa
    success, data, errors = client.execute_and_get(MUTATION, variables)
"""
import json
import logging
from typing import Any, Dict, List, Optional, Tuple
from urllib import error as urllib_error
from urllib import request as urllib_request

logger = logging.getLogger(__name__)


class AppSyncClient:
    """
    Cliente HTTP para AppSync. Ejecuta mutaciones y queries via API Key.

    Métodos:
        execute(mutation, variables)           → bool  (backward-compat)
        execute_and_get(mutation, variables)   → (bool, data, errors)
        notify(mutation, variables)            → bool  (fire-and-forget, sin excepciones)
    """

    def __init__(self, endpoint: str, api_key: str):
        """
        Args:
            endpoint: URL GraphQL del API AppSync.
                      Ej: https://xxxx.appsync-api.us-east-1.amazonaws.com/graphql
            api_key:  API Key para el header x-api-key.
                      Ej: da2-xxxxxxxxxxxxxxxxxxxxxxxx
        """
        self.endpoint = endpoint
        self.api_key = api_key
        self._configured = bool(endpoint and api_key)

        if not self._configured:
            logger.warning(
                "AppSyncClient inicializado sin endpoint o api_key. "
                "Las llamadas serán ignoradas (útil en entorno local)."
            )

    # ─────────────────────────────────────────────────────────────────────────
    # API pública
    # ─────────────────────────────────────────────────────────────────────────

    def execute(
        self,
        mutation: str,
        variables: Dict[str, Any],
        timeout: int = 10,
    ) -> bool:
        """
        Ejecuta una operación GraphQL.
        Retorna True si la respuesta no contiene errores.
        Lanza excepción en errores de red/HTTP.

        Backward-compatible con la versión anterior.
        """
        success, _, _ = self._call(mutation, variables, timeout)
        return success

    def execute_and_get(
        self,
        mutation: str,
        variables: Dict[str, Any],
        timeout: int = 10,
    ) -> Tuple[bool, Optional[Dict[str, Any]], Optional[List[Dict]]]:
        """
        Ejecuta una operación GraphQL y retorna la respuesta completa.

        Returns:
            (success, data, errors)
            - success : True si no hubo errores GraphQL
            - data    : contenido de response['data'], o None
            - errors  : lista de errores AppSync, o None
        """
        return self._call(mutation, variables, timeout)

    def notify(
        self,
        mutation: str,
        variables: Dict[str, Any],
        timeout: int = 10,
    ) -> bool:
        """
        Fire-and-forget: ejecuta la mutación absorbiendo cualquier excepción.
        Ideal para notificaciones opcionales (nunca rompe el flujo principal).

        Returns:
            True si la mutación se ejecutó sin errores, False en cualquier fallo.
        """
        if not self._configured:
            logger.debug("AppSync notify omitido: cliente no configurado.")
            return False

        try:
            success, _data, errors = self._call(mutation, variables, timeout)
            if not success:
                logger.warning(
                    "AppSync notify: la mutación devolvió errores: %s",
                    json.dumps(errors),
                )
            return success
        except Exception as exc:
            logger.error(
                "AppSync notify: error inesperado (ignorado): %s", exc, exc_info=True
            )
            return False

    # ─────────────────────────────────────────────────────────────────────────
    # Internals
    # ─────────────────────────────────────────────────────────────────────────

    def _call(
        self,
        query: str,
        variables: Dict[str, Any],
        timeout: int,
    ) -> Tuple[bool, Optional[Dict[str, Any]], Optional[List[Dict]]]:
        """
        Realiza la petición HTTP a AppSync.

        Returns:
            (success, data, errors)

        Raises:
            Exception: en errores de red o HTTP inesperados.
        """
        if not self._configured:
            logger.warning("AppSync no configurado: llamada ignorada.")
            return False, None, None

        payload = json.dumps({"query": query, "variables": variables}).encode("utf-8")
        req = urllib_request.Request(
            self.endpoint,
            data=payload,
            headers={
                "Content-Type": "application/json",
                "x-api-key": self.api_key,
            },
            method="POST",
        )

        try:
            with urllib_request.urlopen(req, timeout=timeout) as response:
                body = json.loads(response.read().decode("utf-8"))

                errors = body.get("errors")
                data = body.get("data")

                if errors:
                    logger.error(
                        "AppSync devolvió errores GraphQL: %s", json.dumps(errors)
                    )
                    return False, data, errors

                return True, data, None

        except urllib_error.HTTPError as exc:
            body_text = ""
            try:
                body_text = exc.read().decode("utf-8") if exc.fp else ""
            except Exception:
                pass
            logger.error(
                "AppSync HTTP %s al llamar a %s: %s", exc.code, self.endpoint, body_text
            )
            return False, None, [{"message": f"HTTP {exc.code}", "detail": body_text}]

        except urllib_error.URLError as exc:
            logger.error("AppSync URLError: %s", exc.reason, exc_info=True)
            return False, None, [{"message": str(exc.reason)}]

        except Exception as exc:
            logger.error("AppSync error inesperado: %s", exc, exc_info=True)
            return False, None, [{"message": str(exc)}]
