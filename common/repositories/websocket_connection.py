from common.repositories.base import BaseRepository
from common.models.models import WebSocketConnection
from typing import Optional, List
import logging

logger = logging.getLogger(__name__)


class WebSocketConnectionRepository(BaseRepository[WebSocketConnection]):
    """
    Repositorio para manejar conexiones WebSocket en PostgreSQL.
    
    La primary key es 'connection_id' (VARCHAR(255)), no 'id'.
    Por eso sobrescribimos los métodos que usan 'id' para usar 'connection_id'.
    
    Este repositorio está en common/repositories para que todos los servicios puedan usarlo.
    """
    def __init__(self):
        super().__init__("websocket_connections", WebSocketConnection)
    
    def find_by_id(self, connection_id: str) -> Optional[WebSocketConnection]:
        """
        Busca una conexión por connection_id (primary key).
        
        Args:
            connection_id: ID de la conexión WebSocket
            
        Returns:
            WebSocketConnection o None si no existe
        """
        if not connection_id or not str(connection_id).strip():
            raise ValueError("connection_id no puede estar vacío")
        
        query = f"SELECT * FROM {self.table_name} WHERE connection_id = %s"
        record = self._execute_query_one(query, (connection_id,))
        return self.model_class(**record) if record else None
    
    def update(self, connection_id: str, data: dict) -> Optional[WebSocketConnection]:
        """
        Actualiza una conexión por connection_id.
        
        Args:
            connection_id: ID de la conexión WebSocket
            data: Datos a actualizar
            
        Returns:
            WebSocketConnection actualizado o None si no existe
        """
        if not connection_id or not str(connection_id).strip():
            raise ValueError("connection_id no puede estar vacío")
        
        self._validate_fields(data, "update")
        prepared_data = self._prepare_data(data)
        
        if not prepared_data:
            raise ValueError("No hay datos para actualizar")
        
        set_clause = ', '.join([f"{key} = %s" for key in prepared_data.keys()])
        values = list(prepared_data.values())
        values.append(connection_id)
        
        query = f"""
            UPDATE {self.table_name}
            SET {set_clause}
            WHERE connection_id = %s
            RETURNING *
        """
        record = self._execute_command_return(query, tuple(values))
        return self.model_class(**record) if record else None
    
    def delete(self, connection_id: str) -> bool:
        """
        Elimina una conexión por connection_id.
        
        Args:
            connection_id: ID de la conexión WebSocket
            
        Returns:
            True si se eliminó, False si no existía
        """
        if not connection_id or not str(connection_id).strip():
            raise ValueError("connection_id no puede estar vacío")
        
        query = f"DELETE FROM {self.table_name} WHERE connection_id = %s RETURNING connection_id"
        result = self._execute_command_return(query, (connection_id,))
        return result is not None
    
    def find_by_user_id(self, user_id: str) -> List[WebSocketConnection]:
        """
        Busca todas las conexiones de un usuario.
        
        Args:
            user_id: UUID del usuario
            
        Returns:
            Lista de conexiones del usuario
        """
        query = f"SELECT * FROM {self.table_name} WHERE user_id = %s"
        records = self._execute_query(query, (user_id,))
        return [self.model_class(**r) for r in records]
    
    def find_by_watching(self, watch_type: str, watch_id: str = None) -> List[WebSocketConnection]:
        """
        Busca conexiones que están viendo un recurso específico.
        
        Args:
            watch_type: Tipo de recurso (ej: "business", "draft")
            watch_id: ID del recurso. Si es None o vacío, busca conexiones que están viendo
                     cualquier recurso de ese tipo (sin id específico).
            
        Returns:
            Lista de conexiones que están viendo ese recurso
            
        Ejemplos:
            - find_by_watching("draft", "draft_123") → Solo conexiones viendo ese draft específico
            - find_by_watching("draft", None) → Conexiones viendo CUALQUIER draft (sin id)
        """
        if not watch_id:
            # Buscar conexiones donde watching contiene un objeto con ese type (sin id)
            # Ejemplo: [{"type": "draft"}] o [{"type": "draft"}, {"type": "business", "id": "123"}]
            from psycopg2.extras import Json
            query = f"""
                SELECT * FROM {self.table_name}
                WHERE watching @> %s::jsonb
            """
            watch_json = Json([{"type": watch_type}])
            records = self._execute_query(query, (watch_json,))
        else:
            # Buscar conexiones donde watching contiene ese objeto específico
            # Ejemplo: [{"type": "draft", "id": "draft_123"}]
            from psycopg2.extras import Json
            query = f"""
                SELECT * FROM {self.table_name}
                WHERE watching @> %s::jsonb
            """
            watch_json = Json([{"type": watch_type, "id": watch_id}])
            records = self._execute_query(query, (watch_json,))
        
        return [self.model_class(**r) for r in records]

