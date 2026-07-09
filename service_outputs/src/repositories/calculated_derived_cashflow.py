from common.repositories.base import BaseRepository
from common.models.models import CalculatedDerivedCashflow
from services.service_outputs.src.models.models import CalculatedDerivedCashflowWithDef
from typing import List, Optional


class CalculatedDerivedCashflowRepository(BaseRepository[CalculatedDerivedCashflow]):
    def __init__(self):
        super().__init__("calculated_derived_cashflows", CalculatedDerivedCashflow)

    def find_with_def_info(self,
                           statement_id: str,
                           evaluator_id: Optional[str] = None,
                           categories: Optional[List[str]] = None,
                           names: Optional[List[str]] = None,
                           period_types: Optional[List[str]] = None,
                           period_identifiers: Optional[List[str]] = None,
                           limit: int = 100,
                           offset: int = 0) -> List[CalculatedDerivedCashflowWithDef]:

        where_conditions = ["cdc.financial_statement_id = %s"]
        params = [statement_id]

        if evaluator_id:
            where_conditions.append("dc.evaluator_id = %s")
            params.append(evaluator_id)

        if categories:
            placeholders = ','.join(['%s'] * len(categories))
            where_conditions.append(f"dc.category IN ({placeholders})")
            params.extend(categories)

        if names:
            placeholders = ','.join(['%s'] * len(names))
            where_conditions.append(f"dc.name IN ({placeholders})")
            params.extend(names)

        if period_types:
            placeholders = ','.join(['%s'] * len(period_types))
            where_conditions.append(f"cdc.period_type IN ({placeholders})")
            params.extend(period_types)

        if period_identifiers:
            placeholders = ','.join(['%s'] * len(period_identifiers))
            where_conditions.append(f"cdc.period_identifier IN ({placeholders})")
            params.extend(period_identifiers)

        where_clause = "WHERE " + " AND ".join(where_conditions)
        params.extend([limit, offset])

        query = f"""
            SELECT
                cdc.*,
                dc.name        AS dcf_name,
                dc.format      AS dcf_format,
                dc.category    AS dcf_category,
                dc.description AS dcf_description,
                dc.priority    AS dcf_priority
            FROM calculated_derived_cashflows cdc
            INNER JOIN derived_cashflows dc ON cdc.derived_cashflow_id = dc.id
            {where_clause}
            ORDER BY
                CASE cdc.period_type
                    WHEN 'ltm'     THEN 1
                    WHEN 'annual'  THEN 2
                    WHEN 'quarterly' THEN 3
                    ELSE 4
                END,
                cdc.period_identifier DESC NULLS LAST,
                cdc.year DESC NULLS LAST,
                dc.priority,
                dc.category,
                dc.name
            LIMIT %s OFFSET %s
        """

        records = self._execute_query(query, tuple(params))
        return [CalculatedDerivedCashflowWithDef(**r) for r in records]
