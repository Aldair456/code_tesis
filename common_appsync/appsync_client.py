"""
Cliente para ejecutar mutaciones GraphQL contra AWS AppSync (HTTP con x-api-key).
Cualquier servicio/Lambda puede instanciarlo con endpoint y api_key y usar execute().
"""
import json
import logging
from typing import Dict, Any, Optional
from urllib import request as urllib_request

logger = logging.getLogger(__name__)


class AppSyncClient:
    """
    Cliente HTTP para AppSync. Ejecuta mutaciones (o queries) y devuelve éxito/error.
    No conoce el dominio (status, financial analysis, etc.); solo envía mutation + variables.
    """

    def __init__(self, endpoint: str, api_key: str):
        """
        Args:
            endpoint: URL del endpoint AppSync (GraphQL).
            api_key: API Key para el header x-api-key.
        """
        self.endpoint = endpoint
        self.api_key = api_key

    def execute(
        self,
        mutation: str,
        variables: Dict[str, Any],
        timeout: int = 10,
    ) -> bool:
        """
        Ejecuta una mutación (o query) GraphQL contra AppSync.

        Args:
            mutation: String con la operación GraphQL (mutation X { ... } o query X { ... }).
            variables: Diccionario de variables para la operación.
            timeout: Timeout en segundos para la petición HTTP.

        Returns:
            True si la respuesta no contiene 'errors', False en caso contrario o si falla la petición.
        """
        if not self.endpoint or not self.api_key:
            logger.warning("AppSync no configurado: endpoint o api_key faltantes.")
            return False

        payload = {"query": mutation, "variables": variables}
        try:
            body = json.dumps(payload).encode("utf-8")
            req = urllib_request.Request(
                self.endpoint,
                data=body,
                headers={
                    "Content-Type": "application/json",
                    "x-api-key": self.api_key,
                },
                method="POST",
            )
            with urllib_request.urlopen(req, timeout=timeout) as response:
                result_data = json.loads(response.read().decode("utf-8"))
                if "errors" in result_data:
                    logger.error("AppSync devolvió errores: %s", json.dumps(result_data["errors"]))
                    return False
                return True
        except Exception as e:
            logger.error("Error llamando a AppSync: %s", str(e), exc_info=True)
            return False
