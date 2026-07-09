"""
Módulo común para funcionalidades WebSocket.
Incluye helpers para facilitar el uso desde otros servicios.
"""
from common_aws_clients.websocket_client import WebSocketClient
from common.repositories.websocket_connection import WebSocketConnectionRepository
from typing import Dict, Any, List

__all__ = ['WebSocketClient', 'WebSocketConnectionRepository', 'notify_watching']


def notify_watching(watch_type: str, watch_id: str = None, message: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Helper para notificar a todas las conexiones que están viendo un recurso específico.
    
    Esta función combina el repositorio (para buscar conexiones) y el cliente (para enviar mensajes).
    
    Args:
        watch_type: Tipo de recurso (ej: "business", "draft")
        watch_id: ID del recurso. Si es None, notifica a conexiones viendo cualquier recurso de ese tipo.
        message: Mensaje a enviar
        
    Returns:
        Dict con estadísticas: {"sent": int, "failed": int, "total": int}
        
    Ejemplos:
        # Notificar a conexiones viendo un draft específico
        notify_watching("draft", "draft_123", {"event": "updated"})
        
        # Notificar a conexiones viendo cualquier draft (lista)
        notify_watching("draft", None, {"event": "updated"})
    """
    if message is None:
        message = {}
    
    client = WebSocketClient()
    repo = WebSocketConnectionRepository()
    
    # Buscar conexiones
    connections = repo.find_by_watching(watch_type, watch_id)
    
    if not connections:
        return {"sent": 0, "failed": 0, "total": 0}
    
    # Enviar mensajes
    connection_ids = [conn.connection_id for conn in connections]
    return client.send_to_connections(connection_ids, message)

