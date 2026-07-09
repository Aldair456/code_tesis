from common.repositories.base import BaseRepository
from common.models.models import CalculatedOutput
from services.service_outputs.src.models.models import CalculatedOutputWithOutput
from typing import List

class CalculatedOutputRepository(BaseRepository[CalculatedOutput]):
    def __init__(self):
        super().__init__("calculated_outputs", CalculatedOutput)

    # def find_with_output_info_arrays(self,
    #                                  statement_id: str = None,
    #                                  output_names: List[str] = None,
    #                                  output_categories: List[str] = None,
    #                                  years: List[int] = None,
    #                                  limit: int = 100,
    #                                  offset: int = 0) -> List[CalculatedOutputWithOutput]:
    #     """
    #     Obtiene calculated outputs con información del output asociado usando JOIN
    #     Soporta filtros por arrays para mayor flexibilidad
    #
    #     Args:
    #         statement_id: ID del statement financiero
    #         output_names: Lista de nombres de output a filtrar (ej: ['Revenue', 'EBITDA'])
    #         output_categories: Lista de categorías de output (ej: ['Income', 'Ratios'])
    #         years: Lista de años (ej: [2023, 2024])
    #         limit: Límite de resultados
    #         offset: Offset para paginación
    #     """
    #     where_conditions = []
    #     params = []
    #
    #     if statement_id:
    #         where_conditions.append("co.financial_statement_id = %s")
    #         params.append(statement_id)
    #
    #     if output_names and len(output_names) > 0:
    #         placeholders = ','.join(['%s'] * len(output_names))
    #         where_conditions.append(f"o.name IN ({placeholders})")
    #         params.extend(output_names)
    #
    #     if output_categories and len(output_categories) > 0:
    #         placeholders = ','.join(['%s'] * len(output_categories))
    #         where_conditions.append(f"o.category IN ({placeholders})")
    #         params.extend(output_categories)
    #
    #     if years and len(years) > 0:
    #         placeholders = ','.join(['%s'] * len(years))
    #         where_conditions.append(f"co.year IN ({placeholders})")
    #         params.extend(years)
    #
    #     where_clause = ""
    #     if where_conditions:
    #         where_clause = "WHERE " + " AND ".join(where_conditions)
    #
    #     # Agregamos limit y offset al final
    #     params.extend([limit, offset])
    #
    #     query = f"""
    #        SELECT
    #            co.*,
    #            -- datos del output
    #            o.name as output_name,
    #            o.format as output_format,
    #            o.category as output_category
    #        FROM calculated_outputs co
    #        INNER JOIN outputs o ON co.output_id = o.id
    #        {where_clause}
    #        ORDER BY co.year DESC, o.category, o.name
    #        LIMIT %s OFFSET %s
    #    """
    #
    #     records = self._execute_query(query, tuple(params))
    #     return [CalculatedOutputWithOutput(**r) for r in records]

    # def find_with_output_info_arrays(self,
    #                                  statement_id: str = None,
    #                                  output_names: List[str] = None,
    #                                  output_categories: List[str] = None,
    #                                  years: List[int] = None,
    #                                  period_types: List[str] = None,  # NUEVO
    #                                  period_identifiers: List[str] = None,  # NUEVO
    #                                  covenant_metrics_only: bool = False,  # NUEVO
    #                                  limit: int = 100,
    #                                  offset: int = 0) -> List[CalculatedOutputWithOutput]:
    #     """
    #     Obtiene calculated outputs con información del output asociado usando JOIN
    #     Soporta filtros por arrays para mayor flexibilidad
    #
    #     Args:
    #         statement_id: ID del statement financiero
    #         output_names: Lista de nombres de output a filtrar (ej: ['Revenue', 'EBITDA'])
    #         output_categories: Lista de categorías de output (ej: ['Income', 'Ratios'])
    #         years: Lista de años (ej: [2023, 2024])
    #         period_types: Lista de tipos de período (ej: ['annual', 'ltm'])
    #         period_identifiers: Lista de identificadores (ej: ['2024', 'LTM_2024Q1'])
    #         covenant_metrics_only: Si True, solo métricas de covenant
    #         limit: Límite de resultados
    #         offset: Offset para paginación
    #     """
    #     where_conditions = []
    #     params = []
    #
    #     if statement_id:
    #         where_conditions.append("co.financial_statement_id = %s")
    #         params.append(statement_id)
    #
    #     if output_names and len(output_names) > 0:
    #         placeholders = ','.join(['%s'] * len(output_names))
    #         where_conditions.append(f"o.name IN ({placeholders})")
    #         params.extend(output_names)
    #
    #     if output_categories and len(output_categories) > 0:
    #         placeholders = ','.join(['%s'] * len(output_categories))
    #         where_conditions.append(f"o.category IN ({placeholders})")
    #         params.extend(output_categories)
    #
    #     # Filtro por years (backward compatibility)
    #     if years and len(years) > 0:
    #         placeholders = ','.join(['%s'] * len(years))
    #         where_conditions.append(f"co.year IN ({placeholders})")
    #         params.extend(years)
    #
    #     # NUEVO: Filtro por period_types
    #     if period_types and len(period_types) > 0:
    #         placeholders = ','.join(['%s'] * len(period_types))
    #         where_conditions.append(f"co.period_type IN ({placeholders})")
    #         params.extend(period_types)
    #
    #     # NUEVO: Filtro por period_identifiers
    #     if period_identifiers and len(period_identifiers) > 0:
    #         placeholders = ','.join(['%s'] * len(period_identifiers))
    #         where_conditions.append(f"co.period_identifier IN ({placeholders})")
    #         params.extend(period_identifiers)
    #
    #     # NUEVO: Solo métricas de covenant
    #     if covenant_metrics_only:
    #         where_conditions.append("co.is_covenant_metric = TRUE")
    #
    #     where_clause = ""
    #     if where_conditions:
    #         where_clause = "WHERE " + " AND ".join(where_conditions)
    #
    #     # Agregamos limit y offset al final
    #     params.extend([limit, offset])
    #
    #     query = f"""
    #         SELECT
    #             co.*,  -- 👈 USANDO co.* para simplicidad
    #             -- datos del output
    #             o.name as output_name,
    #             o.format as output_format,
    #             o.category as output_category
    #         FROM calculated_outputs co
    #         INNER JOIN outputs o ON co.output_id = o.id
    #         {where_clause}
    #         ORDER BY
    #             COALESCE(co.period_identifier, CAST(co.year AS VARCHAR)) DESC,
    #             o.category,
    #             o.name
    #         LIMIT %s OFFSET %s
    #     """
    #
    #     records = self._execute_query(query, tuple(params))
    #     return [CalculatedOutputWithOutput(**r) for r in records]

    def find_with_output_info_arrays(self,
                                     statement_id: str = None,
                                     output_names: List[str] = None,
                                     output_categories: List[str] = None,
                                     years: List[int] = None,
                                     period_types: List[str] = None,
                                     period_identifiers: List[str] = None,
                                     covenant_metrics_only: bool = False,
                                     evaluator_id: str = None,
                                     limit: int = 100,
                                     offset: int = 0) -> List[CalculatedOutputWithOutput]:
        """
        Obtiene calculated outputs con información del output asociado usando JOIN
        Soporta filtros por arrays para mayor flexibilidad (ACTUALIZADO PARA LTM)

        Args:
            statement_id: ID del statement financiero
            output_names: Lista de nombres de output a filtrar (ej: ['Revenue', 'EBITDA'])
            output_categories: Lista de categorías de output (ej: ['Income', 'Ratios'])
            years: Lista de años (ej: [2023, 2024]) - backward compatibility
            period_types: Lista de tipos de período (ej: ['annual', 'ltm'])
            period_identifiers: Lista de identificadores (ej: ['2024', 'LTM_2024Q1'])
            covenant_metrics_only: Si True, solo métricas de covenant
            limit: Límite de resultados
            offset: Offset para paginación
        """
        where_conditions = []
        params = []

        if statement_id:
            where_conditions.append("co.financial_statement_id = %s")
            params.append(statement_id)

        if output_names and len(output_names) > 0:
            placeholders = ','.join(['%s'] * len(output_names))
            where_conditions.append(f"o.name IN ({placeholders})")
            params.extend(output_names)

        if output_categories and len(output_categories) > 0:
            placeholders = ','.join(['%s'] * len(output_categories))
            where_conditions.append(f"o.category IN ({placeholders})")
            params.extend(output_categories)

        # Filtro por years (backward compatibility)
        if years and len(years) > 0:
            placeholders = ','.join(['%s'] * len(years))
            where_conditions.append(f"co.year IN ({placeholders})")
            params.extend(years)

        # NUEVO: Filtro por period_types
        if period_types and len(period_types) > 0:
            placeholders = ','.join(['%s'] * len(period_types))
            where_conditions.append(f"co.period_type IN ({placeholders})")
            params.extend(period_types)

        # NUEVO: Filtro por period_identifiers
        if period_identifiers and len(period_identifiers) > 0:
            placeholders = ','.join(['%s'] * len(period_identifiers))
            where_conditions.append(f"co.period_identifier IN ({placeholders})")
            params.extend(period_identifiers)

        # NUEVO: Solo métricas de covenant
        if covenant_metrics_only:
            where_conditions.append("co.is_covenant_metric = TRUE")

        if evaluator_id:
            where_conditions.append("o.evaluator_id = %s")
            params.append(evaluator_id)

        where_clause = ""
        if where_conditions:
            where_clause = "WHERE " + " AND ".join(where_conditions)

        # Agregamos limit y offset al final
        params.extend([limit, offset])

        query = f"""
            SELECT 
                co.*,  -- Usando co.* para simplicidad
                -- datos del output
                o.name as output_name,
                o.format as output_format,
                o.category as output_category,
                o.description as output_description
            FROM calculated_outputs co
            INNER JOIN outputs o ON co.output_id = o.id
            {where_clause}
            ORDER BY 
                CASE co.period_type 
                    WHEN 'ltm' THEN 1 
                    WHEN 'annual' THEN 2 
                    WHEN 'quarterly' THEN 3 
                    ELSE 4 
                END,
                co.period_identifier DESC NULLS LAST,
                co.year DESC NULLS LAST,
                CASE WHEN co.is_covenant_metric THEN 0 ELSE 1 END,
                o.category, 
                o.name
            LIMIT %s OFFSET %s
        """

        records = self._execute_query(query, tuple(params))
        return [CalculatedOutputWithOutput(**r) for r in records]
