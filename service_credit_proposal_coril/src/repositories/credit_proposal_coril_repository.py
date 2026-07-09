import logging
from typing import List, Dict, Any, Optional
from common.repositories.base import BaseRepository
from services.service_credit_proposal_coril.src.models.credit_proposal_coril import CreditProposalCoril

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class CreditProposalCorilRepository(BaseRepository[CreditProposalCoril]):
    """Repository para gestionar credit_proposals_coril en la base de datos."""
    
    def __init__(self):
        super().__init__("credit_proposals_coril", CreditProposalCoril)
    
    def find_by_evaluator_id(
        self,
        evaluator_id: str,
        business_id: str = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Busca propuestas de crédito coril por evaluator_id (a través de businesses).
        Opcionalmente filtra por business_id.
        Retorna: id, proposal_number, business_id, business_name, user_name, status, total_amount, currency, deal_id, deal_name, created_at, updated_at.
        
        Args:
            evaluator_id: ID del evaluator
            business_id: ID del negocio (opcional)
            limit: Límite de resultados
            offset: Offset para paginación
            
        Returns:
            List[Dict]: Lista de propuestas con campos básicos incluyendo nombres
        """
        try:
            converted_evaluator_id = self._convert_value_for_sql(evaluator_id)
            
            # Query base (total_amount desde deal d.value; currency desde businesses; deal_name desde d.title; user_name en cp)
            query = """
                SELECT 
                    cp.id,
                    cp.proposal_number,
                    cp.business_id,
                    b.name as business_name,
                    cp.user_name,
                    cp.status,
                    d.value as total_amount,
                    b.currency as currency,
                    cp.deal_id,
                    d.title as deal_name,
                    cp.created_at,
                    cp.updated_at
                FROM credit_proposals_coril cp
                INNER JOIN businesses b ON cp.business_id = b.id
                LEFT JOIN deals d ON cp.deal_id = d.id
                WHERE b.evaluator_id = %s
            """
            
            params = [converted_evaluator_id]
            
            # Agregar filtro por business_id si se proporciona
            if business_id:
                converted_business_id = self._convert_value_for_sql(business_id)
                query += " AND cp.business_id = %s"
                params.append(converted_business_id)
            
            query += " ORDER BY cp.created_at DESC LIMIT %s OFFSET %s"
            params.extend([limit, offset])
            
            records = self._execute_query(query, tuple(params))
            
            # Convertir a diccionarios con los campos solicitados
            result = []
            for record in records:
                result.append({
                    "id": str(record.get("id")),
                    "proposal_number": record.get("proposal_number"),
                    "business_id": str(record.get("business_id")),
                    "business_name": record.get("business_name"),
                    "user_name": record.get("user_name"),
                    "status": record.get("status"),
                    "total_amount": float(record["total_amount"]) if record.get("total_amount") is not None else None,
                    "currency": record.get("currency"),
                    "deal_id": str(record["deal_id"]) if record.get("deal_id") else None,
                    "deal_name": record.get("deal_name"),
                    "created_at": record.get("created_at").isoformat() if record.get("created_at") else None,
                    "updated_at": record.get("updated_at").isoformat() if record.get("updated_at") else None
                })
            
            logger.info(f"Se encontraron {len(result)} propuestas coril para evaluator_id {evaluator_id}")
            return result
            
        except Exception as e:
            logger.error(f"Error obteniendo propuestas coril por evaluator_id {evaluator_id}: {str(e)}")
            raise

    def get_proposal_summary_by_id(self, proposal_id: str) -> Optional[Dict[str, Any]]:
        """
        Obtiene un resumen de una propuesta por ID (mismo shape que un ítem de find_by_evaluator_id).
        Para notificación CREADO: la UI puede pintar la fila sin llamar al GET.
        """
        if not proposal_id:
            return None
        try:
            converted_id = self._convert_value_for_sql(proposal_id)
            query = """
                SELECT 
                    cp.id,
                    cp.proposal_number,
                    cp.business_id,
                    b.name as business_name,
                    cp.user_name,
                    cp.status,
                    d.value as total_amount,
                    b.currency as currency,
                    cp.deal_id,
                    d.title as deal_name,
                    cp.created_at,
                    cp.updated_at
                FROM credit_proposals_coril cp
                INNER JOIN businesses b ON cp.business_id = b.id
                LEFT JOIN deals d ON cp.deal_id = d.id
                WHERE cp.id = %s
            """
            record = self._execute_query_one(query, (converted_id,))
            if not record:
                return None
            return {
                "id": str(record.get("id")),
                "proposal_number": record.get("proposal_number"),
                "business_id": str(record.get("business_id")),
                "business_name": record.get("business_name"),
                "user_name": record.get("user_name"),
                "status": record.get("status"),
                "total_amount": float(record["total_amount"]) if record.get("total_amount") is not None else None,
                "currency": record.get("currency"),
                "deal_id": str(record["deal_id"]) if record.get("deal_id") else None,
                "deal_name": record.get("deal_name"),
                "created_at": record.get("created_at").isoformat() if record.get("created_at") else None,
                "updated_at": record.get("updated_at").isoformat() if record.get("updated_at") else None
            }
        except Exception as e:
            logger.warning(f"Error obteniendo resumen de propuesta {proposal_id}: {e}")
            return None

    def get_deal_by_id(self, deal_id: str) -> Optional[Dict[str, Any]]:
        """
        Obtiene un deal por su ID (tabla deals).
        Retorna name (title), value (para total_amount). La tabla deals no tiene currency; usar default PEN.
        """
        if not deal_id:
            return None
        try:
            converted_id = self._convert_value_for_sql(deal_id)
            query = """
                SELECT id, title, value
                FROM deals
                WHERE id = %s
            """
            row = self._execute_query_one(query, (converted_id,))
            if not row:
                return None
            return {
                "id": str(row["id"]),
                "name": row.get("title"),
                "value": float(row["value"]) if row.get("value") is not None else None
            }
        except Exception as e:
            logger.warning(f"Error obteniendo deal por ID {deal_id}: {e}")
            return None

    def get_business_by_id(self, business_id: str):
        """Obtiene un business por su ID."""
        try:
            query = """
            SELECT b.id, b.name, b.ruc, b.legal_name,
                   sec.name as sector, sec_cat.name as subsector, b.evaluator_id
            FROM businesses b
            LEFT JOIN sectores sec_cat ON b.sector_id = sec_cat.id
            LEFT JOIN secciones sec ON sec_cat.seccion_id = sec.id
            WHERE b.id = %s
            """
            
            row = self._execute_query_one(query, (business_id,))
            
            if not row:
                return None
            
            return type('Business', (), {
                'id': row['id'],
                'name': row['name'],
                'ruc': row['ruc'],
                'legal_name': row['legal_name'],
                'sector': row['sector'],
                'subsector': row['subsector'],
                'evaluator_id': row['evaluator_id']
            })()
            
        except Exception as e:
            logger.error(f"Error obteniendo business por ID {business_id}: {str(e)}")
            raise
    

    def get_evaluator_route(self, evaluator_id: str) -> Optional[Dict[str, Any]]:
        """Delega en EvaluatorRoutesRepository (tabla evaluator_routes)."""
        from services.service_credit_proposal_coril.src.repositories.evaluator_routes_repository import (
            EvaluatorRoutesRepository,
        )

        return EvaluatorRoutesRepository().get_evaluator_route(evaluator_id)

    def update_status(self, proposal_id: str, status: str, message: str = None) -> bool:
        """
        Actualiza el status de una propuesta de crédito.
        
        Args:
            proposal_id: ID de la propuesta
            status: Nuevo status (INICIADO, EN_PROGRESO, COMPLETADO, FALLIDO)
            message: Mensaje opcional (no se guarda en BD, solo para logging)
            
        Returns:
            True si se actualizó exitosamente
        """
        try:
            converted_id = self._convert_value_for_sql(proposal_id)
            
            query = """
                UPDATE credit_proposals_coril
                SET status = %s, updated_at = NOW()
                WHERE id = %s
            """
            
            self._execute_command(query, (status, converted_id))
            logger.info(f"Status actualizado a '{status}' para proposal_id: {proposal_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error actualizando status de propuesta {proposal_id}: {str(e)}")
            raise
