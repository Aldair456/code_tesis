import logging
from typing import Dict, Any, List, Optional
from common.repositories.base import BaseRepository

logger = logging.getLogger(__name__)


class BusinessAnalysisRepository(BaseRepository):
    """
    Repositorio para análisis de negocio.
    Maneja consultas específicas para análisis de IA de businesses.
    """
    
    def __init__(self):
        super().__init__("businesses", None)  # No necesitamos model_class específico
    
    def get_business_by_id(self, business_id: str) -> Optional[Dict[str, Any]]:
        """
        Obtiene un business por su ID con datos necesarios para análisis.
        
        Args:
            business_id: ID del business
            
        Returns:
            Dict con datos del business o None si no existe
        """
        try:
            query = """
            SELECT b.id, b.name, b.ruc, b.legal_name, 
                   sec.name as sector, sec_cat.name as subsector,
                   b.evaluator_id, e.name as evaluator_name, COALESCE(e.country, 'PE') as country
            FROM businesses b
            LEFT JOIN evaluators e ON b.evaluator_id = e.id
            LEFT JOIN sectores sec_cat ON b.sector_id = sec_cat.id
            LEFT JOIN secciones sec ON sec_cat.seccion_id = sec.id
            WHERE b.id = %s
            """
            
            result = self._execute_query(query, (business_id,))
            
            if not result:
                return None
            
            row = result[0]
            return {
                'id': row['id'],
                'name': row['name'],
                'ruc': row['ruc'],
                'legal_name': row['legal_name'],
                'sector': row['sector'],
                'subsector': row['subsector'],
                'evaluator_id': row['evaluator_id'],
                'evaluator_name': row['evaluator_name'],
                'country': row['country'],
            }
            
        except Exception as e:
            logger.error(f"Error obteniendo business por ID {business_id}: {str(e)}")
            raise
    
    def get_businesses_for_analysis(self, evaluator_id: Optional[str] = None, 
                                  sector: Optional[str] = None, 
                                  limit: int = 100) -> List[Dict[str, Any]]:
        """
        Obtiene businesses para análisis con filtros opcionales.
        
        Args:
            evaluator_id: Filtro por evaluator (opcional)
            sector: Filtro por sector (opcional)
            limit: Límite de resultados
            
        Returns:
            Lista de businesses para analizar
        """
        try:
            # Construir query dinámico
            conditions = []
            params = []
            
            if evaluator_id:
                conditions.append("b.evaluator_id = %s")
                params.append(evaluator_id)
            
            if sector:
                conditions.append("sec.name ILIKE %s")
                params.append(f"%{sector}%")
            
            where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""
            
            query = f"""
            SELECT b.id, b.name, b.ruc, b.legal_name, 
                   sec.name as sector, sec_cat.name as subsector, b.evaluator_id, b.created_at
            FROM businesses b
            LEFT JOIN sectores sec_cat ON b.sector_id = sec_cat.id
            LEFT JOIN secciones sec ON sec_cat.seccion_id = sec.id
            {where_clause}
            ORDER BY b.created_at DESC
            LIMIT %s
            """
            
            params.append(limit)
            result = self._execute_query(query, tuple(params))
            
            businesses = []
            for row in result:
                businesses.append({
                    'id': row['id'],
                    'name': row['name'],
                    'ruc': row['ruc'],
                    'legal_name': row['legal_name'],
                    'sector': row['sector'],
                    'subsector': row['subsector'],
                    'evaluator_id': row['evaluator_id'],
                    'created_at': row['created_at']
                })
            
            logger.info(f"Se encontraron {len(businesses)} businesses para análisis")
            return businesses
            
        except Exception as e:
            logger.error(f"Error obteniendo businesses para análisis: {str(e)}")
            raise
