from common.repositories.base import BaseRepository
from common.models.models import FinancialDataPoint
from services.service_outputs.src.models.models import FinancialDataPointWithAccount
from typing import List, Optional, Dict, Any


_ACCOUNT_JOIN_FROM = """
    FROM financial_datapoints fd
    LEFT JOIN accounts a ON fd.account_id = a.id
    LEFT JOIN account_extracts ae ON ae.id = fd.account_extract_id
"""

_ACCOUNT_SELECT_COLUMNS = """
                fd.id,
                fd.value,
                fd.account_id,
                fd.account_extract_id,
                fd.financial_statement_id,
                fd.details,
                fd.year,
                fd.period,
                fd.created_at,
                fd.updated_at,
                COALESCE(a.name, ae.name, '') AS account_name,
                COALESCE(a.display_name, ae.display_name) AS account_display_name,
                COALESCE(a.type, ae.type) AS account_type,
                COALESCE(a.value_type, ae.value_type) AS account_value_type,
                COALESCE(a.tags, ae.tags) AS account_tags,
                COALESCE(a.priority, ae.priority) AS account_priority
"""


class FinancialDatapointRepository(BaseRepository):
    def __init__(self):
        super().__init__("financial_datapoints", FinancialDataPoint)

    @staticmethod
    def _row_to_datapoint_with_account(record: Dict[str, Any]) -> FinancialDataPointWithAccount:
        """Normaliza filas del JOIN; account_name nunca null (legacy / cuenta huérfana)."""
        row = dict(record)
        if row.get("account_name") is None:
            row["account_name"] = ""
        return FinancialDataPointWithAccount(**row)

    def find_by_statement_id(self, statement_id: str) -> List[FinancialDataPoint]:
        """Encuentra todos los datapoints por statement_id"""
        return self.find_by_attribute("financial_statement_id", statement_id)

    def find_by_account_id(self, account_id: str) -> List[FinancialDataPoint]:
        """Encuentra todos los datapoints por account_id"""
        return self.find_by_attribute("account_id", account_id)

    def find_by_year(self, year: int) -> List[FinancialDataPoint]:
        """Encuentra todos los datapoints por año"""
        return self.find_by_attribute("year", year)

    def find_by_period(self, period: str) -> List[FinancialDataPoint]:
        """Encuentra todos los datapoints por período"""
        return self.find_by_attribute("period", period)

    def find_with_account_info(self,
                               statement_id: str = None,
                               account_name: str = None,
                               account_type: str = None,
                               year: int = None,
                               period: str = None,
                               limit: int = 100,
                               offset: int = 0) -> List[FinancialDataPointWithAccount]:
        """
        Obtiene datapoints con información de la cuenta asociada usando JOIN
        Devuelve diccionarios con datos combinados en lugar de objetos modelo
        """
        where_conditions = []
        params = []

        if statement_id:
            where_conditions.append("fd.financial_statement_id = %s")
            params.append(statement_id)

        if account_name:
            where_conditions.append("COALESCE(a.name, ae.name) = %s")
            params.append(account_name)

        if account_type:
            where_conditions.append("COALESCE(a.type, ae.type) = %s")
            params.append(account_type)

        if year:
            where_conditions.append("fd.year = %s")
            params.append(year)

        if period:
            where_conditions.append("fd.period = %s")
            params.append(period)

        where_clause = ""
        if where_conditions:
            where_clause = "WHERE " + " AND ".join(where_conditions)

        params.extend([limit, offset])

        query = f"""
            SELECT
{_ACCOUNT_SELECT_COLUMNS}
            {_ACCOUNT_JOIN_FROM}
            {where_clause}
            ORDER BY fd.year DESC, fd.period, COALESCE(a.priority, ae.priority) NULLS LAST, COALESCE(a.name, ae.name)
            LIMIT %s OFFSET %s
        """

        records = self._execute_query(query, tuple(params))
        return [self._row_to_datapoint_with_account(r) for r in records]

    def find_with_account_info_arrays(self,
                               statement_id: str = None,
                               account_names: List[str] = None,
                               account_types: List[str] = None,
                               years: List[int] = None,
                               periods: List[str] = None,
                               limit: int = 100,
                               offset: int = 0) -> List[FinancialDataPointWithAccount]:
        """
        Obtiene datapoints con información de la cuenta asociada usando JOIN
        Soporta filtros por arrays para mayor flexibilidad
        """
        where_conditions = []
        params = []

        if statement_id:
            where_conditions.append("fd.financial_statement_id = %s")
            params.append(statement_id)

        if account_names and len(account_names) > 0:
            placeholders = ','.join(['%s'] * len(account_names))
            where_conditions.append(f"COALESCE(a.name, ae.name) IN ({placeholders})")
            params.extend(account_names)

        if account_types and len(account_types) > 0:
            placeholders = ','.join(['%s'] * len(account_types))
            where_conditions.append(f"COALESCE(a.type, ae.type) IN ({placeholders})")
            params.extend(account_types)

        if years and len(years) > 0:
            placeholders = ','.join(['%s'] * len(years))
            where_conditions.append(f"fd.year IN ({placeholders})")
            params.extend(years)

        if periods and len(periods) > 0:
            placeholders = ','.join(['%s'] * len(periods))
            where_conditions.append(f"fd.period IN ({placeholders})")
            params.extend(periods)

        where_clause = ""
        if where_conditions:
            where_clause = "WHERE " + " AND ".join(where_conditions)

        params.extend([limit, offset])

        query = f"""
            SELECT
{_ACCOUNT_SELECT_COLUMNS}
            {_ACCOUNT_JOIN_FROM}
            {where_clause}
            ORDER BY fd.year DESC, fd.period, COALESCE(a.priority, ae.priority) NULLS LAST, COALESCE(a.name, ae.name)
            LIMIT %s OFFSET %s
        """

        records = self._execute_query(query, tuple(params))
        return [self._row_to_datapoint_with_account(r) for r in records]

    def find_statement_summary(self, statement_id: str) -> List[Dict[str, Any]]:
        """
        Obtiene un resumen de todos los datapoints de un statement agrupados por cuenta
        """
        query = """
            SELECT
                fd.account_id,
                fd.account_extract_id,
                COALESCE(a.name, ae.name, '') AS account_name,
                COALESCE(a.display_name, ae.display_name) AS account_display_name,
                COALESCE(a.type, ae.type) AS account_type,
                COALESCE(a.value_type, ae.value_type) AS account_value_type,
                COALESCE(a.priority, ae.priority) AS account_priority,
                COUNT(fd.id) AS datapoint_count,
                SUM(fd.value) AS total_value,
                AVG(fd.value) AS avg_value,
                MIN(fd.year) AS earliest_year,
                MAX(fd.year) AS latest_year,
                array_agg(DISTINCT fd.period ORDER BY fd.period) AS periods
            FROM financial_datapoints fd
            LEFT JOIN accounts a ON fd.account_id = a.id
            LEFT JOIN account_extracts ae ON fd.account_extract_id = ae.id
            WHERE fd.financial_statement_id = %s
            GROUP BY fd.account_id, fd.account_extract_id,
                     a.name, ae.name, a.display_name, ae.display_name,
                     a.type, ae.type, a.value_type, ae.value_type,
                     a.priority, ae.priority
            ORDER BY COALESCE(a.priority, ae.priority) NULLS LAST, COALESCE(a.name, ae.name)
        """

        return self._execute_query(query, (statement_id,))

    def find_account_evolution(self, account_id: str, start_year: int = None, end_year: int = None) -> List[
        Dict[str, Any]]:
        """
        Obtiene la evolución temporal de una cuenta específica
        """
        where_conditions = ["(fd.account_extract_id = %s OR fd.account_id = %s)"]
        params = [account_id, account_id]

        if start_year:
            where_conditions.append("fd.year >= %s")
            params.append(start_year)

        if end_year:
            where_conditions.append("fd.year <= %s")
            params.append(end_year)

        where_clause = "WHERE " + " AND ".join(where_conditions)

        query = f"""
            SELECT
                fd.year,
                fd.period,
                fd.value,
                fd.details,
                COALESCE(a.name, ae.name, '') AS account_name,
                COALESCE(a.display_name, ae.display_name) AS account_display_name,
                COALESCE(a.value_type, ae.value_type) AS account_value_type
            FROM financial_datapoints fd
            LEFT JOIN accounts a ON fd.account_id = a.id
            LEFT JOIN account_extracts ae ON fd.account_extract_id = ae.id
            {where_clause}
            ORDER BY fd.year, fd.period
        """

        return self._execute_query(query, tuple(params))

    def bulk_create_for_statement(self, statement_id: str, datapoints_data: List[Dict[str, Any]]) -> int:
        """
        Crea múltiples datapoints para un statement específico de forma eficiente
        """
        enriched_data = []
        for data in datapoints_data:
            enriched_data.append({
                **data,
                'financial_statement_id': statement_id
            })

        return self.create_many(enriched_data)

    def update_values_by_criteria(self,
                                  statement_id: str = None,
                                  account_id: str = None,
                                  year: int = None,
                                  period: str = None,
                                  value_multiplier: float = None,
                                  new_details: Dict[str, Any] = None) -> int:
        """
        Actualización masiva de datapoints basada en criterios
        """
        if not any([value_multiplier, new_details]):
            raise ValueError("Debe especificar al menos value_multiplier o new_details")

        filters = {}
        if statement_id:
            filters['financial_statement_id'] = statement_id
        if account_id:
            filters['account_id'] = account_id
        if year:
            filters['year'] = year
        if period:
            filters['period'] = period

        if not filters:
            raise ValueError("Debe especificar al menos un criterio de filtrado")

        if value_multiplier and not new_details:
            where_conditions = []
            params = []

            for field, value in filters.items():
                where_conditions.append(f"{field} = %s")
                params.append(self._convert_value_for_sql(value))

            params.append(value_multiplier)

            query = f"""
                UPDATE {self.table_name}
                SET value = value * %s, updated_at = CURRENT_TIMESTAMP
                WHERE {' AND '.join(where_conditions)}
            """

            return self._execute_command(query, tuple(params))

        elif value_multiplier and new_details:
            conn = self._get_connection()
            try:
                with conn.cursor() as cursor:
                    where_conditions = []
                    params = []

                    for field, value in filters.items():
                        where_conditions.append(f"{field} = %s")
                        params.append(self._convert_value_for_sql(value))

                    cursor.execute(f"""
                        UPDATE {self.table_name}
                        SET details = %s, updated_at = CURRENT_TIMESTAMP
                        WHERE {' AND '.join(where_conditions)}
                    """, (self._convert_value_for_sql(new_details),) + tuple(params))

                    cursor.execute(f"""
                        UPDATE {self.table_name}
                        SET value = value * %s, updated_at = CURRENT_TIMESTAMP
                        WHERE {' AND '.join(where_conditions)}
                    """, (value_multiplier,) + tuple(params))

                    conn.commit()
                    return cursor.rowcount
            except Exception:
                conn.rollback()
                raise
        else:
            where_conditions = []
            params = []

            for field, value in filters.items():
                where_conditions.append(f"{field} = %s")
                params.append(self._convert_value_for_sql(value))

            query = f"""
                UPDATE {self.table_name}
                SET details = %s, updated_at = CURRENT_TIMESTAMP
                WHERE {' AND '.join(where_conditions)}
            """

            return self._execute_command(query, (self._convert_value_for_sql(new_details),) + tuple(params))
