"""
Cliente básico para enviar mensajes a conexiones WebSocket.
NO depende del servicio websocket, solo usa AWS API Gateway directamente.
"""
import json
import logging
import boto3
import os
from botocore.exceptions import ClientError
from typing import Dict, Any, List

logger = logging.getLogger(__name__)


class WebSocketClient:
    """
    Cliente para enviar mensajes a conexiones WebSocket a través de AWS API Gateway Management API.
    
    Este cliente NO requiere el servicio websocket deployado.
    Solo necesita el endpoint de API Gateway.
    
    Uso:
        from common_aws_clients.websocket_client import WebSocketClient
        
        client = WebSocketClient()  # Usa WS_ENDPOINT de env vars
        client.send_to_connection(connection_id, {"event": "updated"})
        client.send_to_connections(["conn1", "conn2"], {"event": "updated"})
    """
    
    def __init__(self, websocket_api_endpoint: str = None):
        """
        Inicializa el cliente WebSocket.
        
        Args:
            websocket_api_endpoint: URL del endpoint de API Gateway WebSocket
                Ejemplo: "https://abc123.execute-api.us-east-1.amazonaws.com/dev"
                Si no se proporciona, se intenta obtener de la variable de entorno WS_ENDPOINT
        """
        self.websocket_api_endpoint = websocket_api_endpoint or os.environ.get('WS_ENDPOINT')
        if not self.websocket_api_endpoint:
            raise ValueError(
                "websocket_api_endpoint es requerido. "
                "Proporciónalo como parámetro o configura la variable de entorno WS_ENDPOINT"
            )
        
        logger.info(f"🔌 Usando WebSocket endpoint: {self.websocket_api_endpoint}")
        
        # Crear cliente de boto3 para API Gateway Management API
        self.apigateway_client = boto3.client(
            'apigatewaymanagementapi', 
            endpoint_url=self.websocket_api_endpoint
        )
    
    def send_to_connection(self, connection_id: str, message: Dict[str, Any]) -> bool:
        """
        Envía un mensaje a una conexión WebSocket específica.
        
        Args:
            connection_id: ID de la conexión WebSocket
            message: Mensaje a enviar (será convertido a JSON)
            
        Returns:
            True si se envió exitosamente, False si la conexión no existe o está desconectada
        """
        try:
            message_str = json.dumps(message) if isinstance(message, dict) else str(message)
            
            self.apigateway_client.post_to_connection(
                ConnectionId=connection_id,
                Data=message_str.encode('utf-8')
            )
            
            return True
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'GoneException':
                logger.warning(f"⚠️  Conexión {connection_id} desconectada")
                return False
            else:
                logger.error(f"❌ Error enviando a {connection_id}: {error_code} | Endpoint: {self.websocket_api_endpoint}")
                raise
        
        except Exception as e:
            logger.error(f"❌ Error conectando a endpoint {self.websocket_api_endpoint}/@connections/{connection_id}: {e}")
            raise
    
    def send_to_connections(self, connection_ids: List[str], message: Dict[str, Any]) -> Dict[str, Any]:
        """
        Envía un mensaje a múltiples conexiones WebSocket.
        
        Args:
            connection_ids: Lista de IDs de conexiones WebSocket
            message: Mensaje a enviar
            
        Returns:
            Dict con estadísticas: {"sent": int, "failed": int, "total": int}
        """
        if not connection_ids:
            return {"sent": 0, "failed": 0, "total": 0}
        
        sent = 0
        failed = 0
        
        for connection_id in connection_ids:
            try:
                success = self.send_to_connection(connection_id, message)
                if success:
                    sent += 1
                else:
                    failed += 1
            except Exception as e:
                logger.error(f"Error enviando a conexión {connection_id}: {e}")
                failed += 1
        
        result = {
            "sent": sent,
            "failed": failed,
            "total": len(connection_ids)
        }
        
        logger.info(
            f"Mensaje enviado a múltiples conexiones - "
            f"Enviados: {sent}, Fallidos: {failed}, Total: {result['total']}"
        )
        
        return result

