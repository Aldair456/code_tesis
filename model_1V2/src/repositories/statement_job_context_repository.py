import logging
from typing import Optional, Tuple
from uuid import UUID

from psycopg2.extras import RealDictCursor

from common.database.database import DatabaseSingletonConnection

logger = logging.getLogger(__name__)


class StatementJobContextRepository:
    """
    Resuelve business_id y evaluator_id (vía businesses) para crear jobs
    alineados con service_jobs / JobCreateSchema.
    """

    def resolve_for_financial_statement(
        self, statement_id: str
    ) -> Optional[Tuple[UUID, Optional[UUID]]]:
        if not statement_id or not str(statement_id).strip():
            return None
        sid = str(statement_id).strip()
        try:
            UUID(sid)
        except (ValueError, TypeError):
            logger.warning("statement_id no es UUID válido: %s", sid)
            return None
        conn = DatabaseSingletonConnection.get_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # LEFT JOIN: el FS puede existir aunque falte o esté roto el vínculo con businesses
                # (un INNER JOIN devolvía 0 filas y parecía "no existe el statement").
                cur.execute(
                    """
                    SELECT fs.business_id, b.evaluator_id
                    FROM financial_statements fs
                    LEFT JOIN businesses b ON b.id = fs.business_id
                    WHERE fs.id = %s
                    """,
                    (sid,),
                )
                row = cur.fetchone()
        except Exception as e:
            logger.error("Error resolviendo contexto job para statement %s: %s", sid, e)
            return None
        if not row:
            logger.warning(
                "No hay fila en financial_statements para job context (id=%s). "
                "¿La Lambda usa la misma DATABASE_URL que la BD donde ves el registro?",
                sid,
            )
            return None
        bid = row["business_id"]
        if bid is None:
            logger.warning(
                "financial_statements.id=%s existe pero business_id es NULL; no se crea job",
                sid,
            )
            return None
        if row.get("evaluator_id") is None:
            logger.info(
                "statement_id=%s: business sin evaluator_id en businesses (job con evaluator NULL)",
                sid,
            )
        eid = row.get("evaluator_id")
        return (
            UUID(str(bid)),
            UUID(str(eid)) if eid is not None else None,
        )
