import json
import logging
from typing import Dict, Any, List, Optional
from common.repositories.base import BaseRepository

logger = logging.getLogger(__name__)


class FinancialAnalysisRepository(BaseRepository):
    """
    Repositorio para análisis financiero.
    Maneja consultas específicas para análisis de IA de indicadores financieros.
    """
    
    def __init__(self):
        super().__init__("financial_statements", None) 
         # No necesitamos model_class específico
    def get_financial_stament_Datapoints(self , bussines_id:str)-> Optional[List[Dict[str, Any]]]:
        """
        Obtiene los datapoints financieros de un business_id específico.
        Busca el FS oficial y trae sus datapoints con nombres de cuentas.
        """
        try:
            # 1. Obtener ID del Financial Statement OFFICIAL
            query_fs = """
            SELECT fs.id as financial_statement_id
            FROM businesses b
            JOIN financial_statements fs ON b.id = fs.business_id 
            WHERE b.id = %s AND fs.type = 'OFFICIAL'
            ORDER BY fs.created_at DESC
            LIMIT 1
            """
            result_fs = self._execute_query(query_fs, (bussines_id,))
            print("Estado financiero", result_fs)
            if not result_fs:
                logger.warning(f"No se encontró FS OFFICIAL para business_id: {bussines_id}")
                return []
                
            financial_statement_id = result_fs[0]['financial_statement_id']
            
            # Additional metadata for LTM
            query_meta = "SELECT ltm_title, ltm_composition FROM financial_statements WHERE id = %s"
            result_meta = self._execute_query(query_meta, (financial_statement_id,))
            ltm_title = ""
            ltm_composition = []
            if result_meta:
                ltm_title = result_meta[0].get('ltm_title', "")
                comp_raw = result_meta[0].get('ltm_composition')
                if isinstance(comp_raw, str) and comp_raw.strip():
                    try: ltm_composition = json.loads(comp_raw)
                    except: ltm_composition = []
                elif isinstance(comp_raw, list):
                    ltm_composition = comp_raw

            # 2. Obtener Datapoints con JOIN a Accounts (incluyendo priority)
            query_dp = """
            SELECT 
                fd.id, fd.value, fd.year, fd.period,
                CASE WHEN a.type = 'FC' THEN fd.details ELSE NULL END as details,
                a.name as indicator_name, a.display_name as indicator_display_name,
                a.type as indicator_category, a.value_type, a.tags, a.priority
            FROM financial_datapoints fd
            INNER JOIN accounts a ON fd.account_id = a.id
            WHERE fd.financial_statement_id = %s
            ORDER BY fd.year, fd.period, a.priority, a.name
            """
            
            result_dp = self._execute_query(query_dp, (financial_statement_id,))
            
            datapoints = []
            for row in result_dp:
                datapoints.append({
                    'id': row['id'],
                    'value': row['value'],
                    'year': row['year'],
                    'period': row['period'],
                    'details': row['details'],
                    'indicator_name': row['indicator_name'],
                    'indicator_display_name': row.get('indicator_display_name') or row['indicator_name'],
                    'indicator_priority': row.get('priority'), 
                    'indicator_category': row['indicator_category'],
                    'value_type': row['value_type'],
                    'tags': row['tags'] or []
                })
            
            logger.info(f"Se encontraron {len(datapoints)} datapoints para business_id {bussines_id}")
            return {
                "datapoints": datapoints,
                "ltm_composition": ltm_composition,
                "ltm_title": ltm_title
            }
            
        except Exception as e:
            logger.error(f"Error en get_financial_stament_Datapoints: {str(e)}")
            return []

    def get_financial_data_by_business_id(self, business_id: str) -> Optional[Dict[str, Any]]:
        """
        Obtiene datos financieros completos de un business para análisis.
        
        Args:
            business_id: ID del business
            
        Returns:
            Dict con datos financieros y del business o None si no existe
        """
        try:
            query = """
            SELECT 
                b.id, b.name, b.ruc, b.legal_name, 
                sec.name as sector, sec_cat.name as subsector,
                b.evaluator_id, e.name as evaluator_name, COALESCE(e.country, 'PE') as country,
                fs.id as financial_statement_id, fs.years, fs.periods, 
                fs.currency, fs.scale_type, fs.type
            FROM businesses b
            LEFT JOIN evaluators e ON b.evaluator_id = e.id
            LEFT JOIN sectores sec_cat ON b.sector_id = sec_cat.id
            LEFT JOIN secciones sec ON sec_cat.seccion_id = sec.id
            LEFT JOIN financial_statements fs ON b.id = fs.business_id 
                AND fs.type = 'OFFICIAL'
            WHERE b.id = %s
            ORDER BY fs.created_at DESC
            LIMIT 1
            """
            
            result = self._execute_query(query, (business_id,))
            
            if not result:
                return None
            
            row = result[0]
            
            # Obtener indicadores financieros calculados
            financial_indicators = self._get_financial_indicators(row['financial_statement_id'])
            
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
                'financial_statement': {
                    'id': row['financial_statement_id'],
                    'years': row['years'],
                    'periods': row['periods'],
                    'currency': row['currency'],
                    'scale_type': row['scale_type'],
                    'type': row['type']
                },
                'financial_indicators': financial_indicators
            }
            
        except Exception as e:
            logger.error(f"Error obteniendo datos financieros por business_id {business_id}: {str(e)}")
            raise
    
    def _get_financial_indicators(self, financial_statement_id: str) -> List[Dict[str, Any]]:
        """
        Obtiene indicadores financieros calculados de un estado financiero.
        
        Args:
            financial_statement_id: ID del estado financiero
            
        Returns:
            Lista de indicadores financieros con sus valores
        """
        try:
            if not financial_statement_id:
                return []
            
            query = """
            SELECT 
                co.id, co.value, co.year, co.period_type, co.period_identifier,
                o.name as indicator_name, o.category as indicator_category
            FROM calculated_outputs co
            LEFT JOIN outputs o ON co.output_id = o.id
            WHERE co.financial_statement_id = %s
            ORDER BY o.name, co.year, co.period_type
            """
            
            result = self._execute_query(query, (financial_statement_id,))
            
            indicators = []
            for row in result:
                indicators.append({
                    'id': row['id'],
                    'value': row['value'],
                    'year': row['year'],
                    'period_type': row['period_type'],
                    'period_identifier': row['period_identifier'],
                    'indicator_name': row['indicator_name'],
                    'indicator_category': row['indicator_category']
                })
            
            logger.info(f"Se encontraron {len(indicators)} indicadores financieros")
            return indicators
            
        except Exception as e:
            logger.error(f"Error obteniendo indicadores financieros: {str(e)}")
            raise
    
    def get_businesses_for_financial_analysis(self, evaluator_id: Optional[str] = None, 
                                            sector: Optional[str] = None, 
                                            limit: int = 100) -> List[Dict[str, Any]]:
        """
        Obtiene businesses para análisis financiero con filtros opcionales.
        
        Args:
            evaluator_id: Filtro por evaluator (opcional)
            sector: Filtro por sector (opcional)
            limit: Límite de resultados
            
        Returns:
            Lista de businesses para análisis financiero
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
            
            # Solo businesses con estados financieros oficiales
            conditions.append("fs.id IS NOT NULL")
            
            where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""
            
            query = f"""
            SELECT DISTINCT 
                b.id, b.name, b.ruc, b.legal_name, 
                sec.name as sector, sec_cat.name as subsector, b.evaluator_id, b.created_at
            FROM businesses b
            LEFT JOIN sectores sec_cat ON b.sector_id = sec_cat.id
            LEFT JOIN secciones sec ON sec_cat.seccion_id = sec.id
            LEFT JOIN financial_statements fs ON b.id = fs.business_id 
                AND fs.type = 'OFFICIAL'
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
            
            logger.info(f"Se encontraron {len(businesses)} businesses para análisis financiero")
            return businesses
            
        except Exception as e:
            logger.error(f"Error obteniendo businesses para análisis financiero: {str(e)}")
            raise
