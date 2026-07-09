# services/service_alerts/src/repositories/alert_repository.py
from common.repositories.base import BaseRepository
from ..models.alert import Alert
from typing import List, Optional, Dict, Any
from uuid import UUID


class AlertRepository(BaseRepository[Alert]):
    def __init__(self):
        super().__init__("alerts", Alert)

    def archive_alert(self, alert_id: UUID) -> bool:
        """Archivar una alerta específica usando el método del BaseRepository"""
        result = self.update(str(alert_id), {"is_archived": True})
        return result is not None

    def create_alert(self, alert_data: dict) -> Alert:
        """Crear nueva alerta usando el método del BaseRepository"""
        return self.create(alert_data)

    def get_calculated_outputs_with_names(self, financial_statement_id: UUID) -> List[Dict[str, Any]]:
        """
        Obtiene los outputs calculados con sus nombres haciendo join con la tabla outputs
        """
        query = """
        SELECT 
            co.id,
            co.value,
            co.year,
            o.name,
            o.category
        FROM calculated_outputs co
        JOIN outputs o ON co.output_id = o.id
        WHERE co.financial_statement_id = %s
        ORDER BY o.name, co.year
        """

        try:
            results = self._execute_query(query, (str(financial_statement_id),))
            return results
        except Exception as e:
            raise Exception(f"Error obteniendo outputs calculados: {str(e)}")

    def get_business_id_from_financial_statement(self, financial_statement_id: UUID) -> str:
        """
        Obtiene el business_id desde el financial_statement_id
        """
        query = """
        SELECT business_id 
        FROM financial_statements 
        WHERE id = %s
        """

        try:
            results = self._execute_query(query, (str(financial_statement_id),))
            if not results:
                raise Exception(f"No se encontró el estado financiero con ID: {financial_statement_id}")
            return str(results[0]['business_id'])
        except Exception as e:
            raise Exception(f"Error obteniendo business_id del estado financiero: {str(e)}")

    def get_financial_statement_years(self, financial_statement_id: UUID) -> List[int]:
        """
        Obtiene los años disponibles para un estado financiero específico
        """
        query = """
        SELECT DISTINCT year 
        FROM calculated_outputs 
        WHERE financial_statement_id = %s 
        ORDER BY year
        """

        try:
            results = self._execute_query(query, (str(financial_statement_id),))
            return [row['year'] for row in results if row['year'] is not None]
        except Exception as e:
            raise Exception(f"Error obteniendo años del estado financiero: {str(e)}")

    def get_total_active_alerts_by_evaluator(self, evaluator_id: str) -> int:
        """
        Obtiene el total de alertas activas para un evaluador específico
        """
        query = """
        SELECT COALESCE(SUM(alertas_activas), 0) as total_alertas_activas
        FROM business_alert_counter
        WHERE evaluator_id = %s
        """

        try:
            result = self._execute_query_one(query, (evaluator_id,))
            return result['total_alertas_activas'] if result else 0
        except Exception as e:
            raise Exception(f"Error obteniendo total de alertas activas: {str(e)}")

    def get_active_alerts_by_business_id(self, business_id: str, limit: int = 100, offset: int = 0) -> List[
        Dict[str, Any]]:
        """
        Obtiene solo las alertas activas (no archivadas) para un business específico
        Usa el método del BaseRepository para mayor eficiencia
        """
        try:
            # Usar el método del BaseRepository con filtros
            alerts = self.find_by_attributes(
                filters={"business_id": business_id, "is_archived": False},
                order_by=[("created_at", "DESC")],
                limit=limit,
                offset=offset
            )

            # Convertir a diccionarios para mantener compatibilidad
            return [alert.model_dump() for alert in alerts]
        except Exception as e:
            raise Exception(f"Error obteniendo alertas activas por business_id: {str(e)}")

    def get_archived_alerts(self, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """
        Obtiene todas las alertas archivadas usando el método del BaseRepository con paginación
        """
        try:
            # Usar el método del BaseRepository con filtros
            alerts = self.find_by_attributes(
                filters={"is_archived": True},
                order_by=[("created_at", "DESC")],
                limit=limit,
                offset=offset
            )

            # Convertir a diccionarios para mantener compatibilidad
            return [alert.model_dump() for alert in alerts]
        except Exception as e:
            raise Exception(f"Error obteniendo alertas archivadas: {str(e)}")

    def get_archived_alerts_by_business(self, business_id: str, limit: int = 100, offset: int = 0) -> List[
        Dict[str, Any]]:
        """
        Obtiene las alertas archivadas para un business específico usando el método del BaseRepository con paginación
        """
        try:
            # Usar el método del BaseRepository con filtros
            alerts = self.find_by_attributes(
                filters={"business_id": business_id, "is_archived": True},
                order_by=[("created_at", "DESC")],
                limit=limit,
                offset=offset
            )

            # Convertir a diccionarios para mantener compatibilidad
            return [alert.model_dump() for alert in alerts]
        except Exception as e:
            raise Exception(f"Error obteniendo alertas archivadas por business_id: {str(e)}")