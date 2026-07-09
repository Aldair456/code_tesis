import boto3
import json
import logging
from typing import Dict, Any, Optional, Union, List
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


class LambdaClient:
    """
    Cliente Lambda optimizado para usar dentro de funciones Lambda.
    Inicializa el cliente una sola vez y lo reutiliza.
    """

    _client_cache = None

    def __init__(self, region_name: Optional[str] = None):
        """
        Inicializa el cliente Lambda.

        Args:
            region_name: Región AWS. Por defecto usa us-east-1 (Virginia).
        """
        self.region_name = region_name or 'us-east-1'

    @property
    def client(self):
        """
        Property para obtener el cliente de forma lazy.
        Solo se crea cuando se usa por primera vez.
        """
        if self._client_cache is None:
            self._client_cache = boto3.client('lambda', region_name=self.region_name)

        return self._client_cache

    def invoke_async(self, function_name: str,
                     payload: Optional[Dict[str, Any]] = None,
                     log_errors: bool = True) -> bool:
        """
        Invoca una Lambda de forma asíncrona (fire and forget).

        Args:
            function_name: Nombre de la función Lambda
            payload: Datos a enviar (se convertirán a JSON)
            log_errors: Si loggear errores o fallar silenciosamente

        Returns:
            bool: True si la invocación fue exitosa, False en caso contrario
        """
        try:
            response = self.client.invoke(
                FunctionName=function_name,
                InvocationType='Event',
                Payload=json.dumps(payload or {})
            )

            # StatusCode 202 = invocación asíncrona exitosa
            if response['StatusCode'] == 202:
                logger.info(f"Lambda {function_name} invocada exitosamente")
                return True
            else:
                if log_errors:
                    logger.warning(f"Lambda {function_name} respondió con código {response['StatusCode']}")
                return False

        except ClientError as e:
            if log_errors:
                logger.error(f"Error invocando Lambda {function_name}: {e}")
            return False
        except Exception as e:
            if log_errors:
                logger.error(f"Error inesperado invocando Lambda {function_name}: {e}")
            return False

    def invoke_sync(self,
                    function_name: str,
                    payload: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        """
        Invoca una Lambda de forma síncrona y espera la respuesta.

        Args:
            function_name: Nombre de la función Lambda
            payload: Datos a enviar (se convertirán a JSON)

        Returns:
            Dict con la respuesta de la Lambda o None si hubo error
        """
        try:
            response = self.client.invoke(
                FunctionName=function_name,
                InvocationType='RequestResponse',
                Payload=json.dumps(payload or {})
            )

            if response['StatusCode'] == 200:
                payload_response = json.loads(response['Payload'].read().decode('utf-8'))
                return payload_response
            else:
                logger.error(f"Lambda {function_name} falló con código {response['StatusCode']}")
                return None

        except Exception as e:
            logger.error(f"Error en invocación síncrona de {function_name}: {e}")
            return None

    def batch_invoke_async(self,
                           invocations: List[Dict[str, Union[str, Dict]]],
                           log_errors: bool = True) -> Dict[str, bool]:
        """
        Invoca múltiples Lambdas de forma asíncrona.

        Args:
            invocations: Lista de diccionarios con 'function_name' y opcionalmente 'payload'
            log_errors: Si loggear errores

        Returns:
            Dict con el resultado de cada invocación {function_name: success}
        """
        results = {}

        for invocation in invocations:
            function_name = invocation['function_name']
            payload = invocation.get('payload', {})

            success = self.invoke_async(function_name, payload, log_errors)
            results[function_name] = success

        return results

