"""
Servicio de análisis FODA y Riesgos con IA.
Usa common_ia_clients para interactuar con Claude y repository para datos.
"""

import logging
from typing import Dict, Any, Optional
from dataclasses import dataclass
import json
from common_ia_clients.ia_client import AnthropicStrategy, IAInvoker, prompt_ai, IAProviderError
from services.service_credit_proposal_coril.src.repositories.financial_analysis_repository import FinancialAnalysisRepository
from services.service_credit_proposal_coril.src.repositories.business_log_event_repository import BusinessLogEventRepository
from services.service_credit_proposal_coril.src.repositories.guarantee_repository import GuaranteeRepository
from services.service_credit_proposal_coril.src.config.config import (
    ANALYZE_CORIL_API_KEY, 
    ANALYZE_CORIL_MODEL, 
    ANALYZE_CORIL_MAX_TOKENS, 
    ANALYZE_CORIL_TEMPERATURE
)
from services.service_credit_proposal_coril.src.utils.normalizers import (
    get_foda_analysis_prompt,
    get_risks_analysis_prompt,
    extract_sources_from_text,
    prepare_financial_data_for_analysis,
    validate_financial_data,
    load_analysis_context,
)

logger = logging.getLogger(__name__)


@dataclass
class FodaRisksResult:
    """Resultado del análisis FODA y Riesgos"""
    foda_analysis: str
    risks_analysis: str
    foda_sources: list
    risks_sources: list


class FodaRisksService:
    """
    Servicio para analizar FODA y Riesgos usando IA.
    Usa repository para datos, utils para prompts y common_ia_clients para IA.
    """
    
    def __init__(self):
        self.repository = FinancialAnalysisRepository()
        self.business_log_repository = BusinessLogEventRepository()
        self.guarantee_repository = GuaranteeRepository()
        self.ia_invoker = None
        
        # Inicializar cliente IA si hay API key
        if ANALYZE_CORIL_API_KEY:
            try:
                anthropic_strategy = AnthropicStrategy(
                    api_key=ANALYZE_CORIL_API_KEY,
                    model=ANALYZE_CORIL_MODEL,
                    max_tokens=ANALYZE_CORIL_MAX_TOKENS,
                    temperature=ANALYZE_CORIL_TEMPERATURE
                )
                self.ia_invoker = IAInvoker(anthropic_strategy)
                logger.info(f"Cliente IA inicializado con modelo: {ANALYZE_CORIL_MODEL}")
            except Exception as e:
                logger.error(f"Error inicializando cliente IA: {e}")
        else:
            logger.warning("API key ANALYZE_CORIL_API_KEY no configurada")
    
    def call_ai(self, prompt: str, source: str) -> str:
        """Llama a la IA usando common_ia_clients"""
        if not self.ia_invoker:
            raise RuntimeError("Cliente IA no disponible")
        
        try:
            return prompt_ai(
                prompt=prompt,
                instance_ia=self.ia_invoker,
                source=source,
                max_tokens=ANALYZE_CORIL_MAX_TOKENS,
                temperature=ANALYZE_CORIL_TEMPERATURE
            )
            
        except IAProviderError as e:
            logger.error(f"Error en API de IA: {e}")
            raise RuntimeError(f"Error en servicio de IA: {str(e)}") from e
        except Exception as e:
            logger.error(f"Error inesperado llamando a IA: {e}")
            raise RuntimeError(f"Error inesperado: {str(e)}") from e
    
    def analyze_foda_risks_by_business_id(self, business_id: str) -> FodaRisksResult:
        """
        Analiza FODA y Riesgos de un negocio por su ID usando el repository y utils.
        
        Args:
            business_id: ID del business a analizar
            
        Returns:
            FodaRisksResult con ambos análisis
        """
        try:
            # Obtener datos financieros usando repository
            financial_data = self.repository.get_financial_data_by_business_id(business_id)
            if not financial_data:
                raise ValueError(f"Datos financieros para business con ID {business_id} no encontrados")
            
            # Validar datos usando utils
            if not validate_financial_data(financial_data):
                raise ValueError(f"Datos financieros del business {business_id} no son válidos para análisis")
            
            # Preparar datos usando utils
            financial_data_prepared = prepare_financial_data_for_analysis(financial_data)
            analysis_context = load_analysis_context(
                business_id, self.business_log_repository, self.guarantee_repository
            )
            
            logger.info(f"Analizando FODA y Riesgos de: {financial_data_prepared['company_name']} ({financial_data_prepared['sector']}/{financial_data_prepared['subsector']}) - {financial_data_prepared['country_name']}")
            
            # 1. Análisis FODA
            logger.info("Generando análisis FODA...")
            foda_prompt = get_foda_analysis_prompt(
                financial_data_prepared['company_name'], 
                financial_data_prepared['ruc'], 
                financial_data_prepared['sector'], 
                financial_data_prepared['subsector'],
                country_name=financial_data_prepared['country_name'],
                tax_id_label=financial_data_prepared['tax_id_label'],
                business_log_context=analysis_context["business_log_context"],
                guarantees_context=analysis_context["guarantees_context"],
            )
            foda_response = self.call_ai(foda_prompt, "foda_risks_analysis_foda")
            
            # Procesar JSON de FODA ANTES de extract_sources_from_text
            try:
             
                foda_data = json.loads(foda_response)
                if isinstance(foda_data, dict) and 'foda' in foda_data:
                    # Extraer el JSON interno
                    foda_clean = json.dumps(foda_data['foda'], ensure_ascii=False, indent=2)
                elif isinstance(foda_data, dict) and 'fortalezas' in foda_data:
                    # Ya tiene el formato correcto
                    foda_clean = json.dumps(foda_data, ensure_ascii=False, indent=2)
                else:
                    # Si no es JSON, usar el response original
                    foda_clean = foda_response
            except (json.JSONDecodeError, KeyError):
                # Si no es JSON, usar el response original
                foda_clean = foda_response
            
            foda_clean, foda_sources = extract_sources_from_text(foda_clean)
            
            # 2. Análisis de Riesgos
            logger.info("Generando análisis de riesgos...")
            risks_prompt = get_risks_analysis_prompt(
                financial_data_prepared['company_name'], 
                financial_data_prepared['ruc'], 
                financial_data_prepared['sector'], 
                financial_data_prepared['subsector'],
                financial_data_prepared['financial_indicators'],
                country_name=financial_data_prepared['country_name'],
                tax_id_label=financial_data_prepared['tax_id_label'],
                business_log_context=analysis_context["business_log_context"],
                guarantees_context=analysis_context["guarantees_context"],
            )
            risks_response = self.call_ai(risks_prompt, "foda_risks_analysis_risks")
            risks_clean, risks_sources = extract_sources_from_text(risks_response)
            
            result = FodaRisksResult(
                foda_analysis=foda_clean,
                risks_analysis=risks_clean,
                foda_sources=foda_sources,
                risks_sources=risks_sources
            )
            
            logger.info(f"Análisis FODA y Riesgos completado para {financial_data_prepared['company_name']}")
            return result
            
        except Exception as e:
            logger.error(f"Error analizando FODA y Riesgos {business_id}: {str(e)}", exc_info=True)
            raise RuntimeError(f"Error en análisis FODA y Riesgos: {str(e)}") from e
    
    def get_businesses_for_foda_risks_analysis(self, evaluator_id: Optional[str] = None, 
                                            sector: Optional[str] = None, 
                                            limit: int = 100) -> list:
        """
        Obtiene businesses para análisis FODA y Riesgos usando repository.
        
        Args:
            evaluator_id: Filtro por evaluator (opcional)
            sector: Filtro por sector (opcional)
            limit: Límite de resultados
            
        Returns:
            Lista de businesses disponibles para análisis FODA y Riesgos
        """
        try:
            return self.repository.get_businesses_for_financial_analysis(
                evaluator_id=evaluator_id,
                sector=sector,
                limit=limit
            )
        except Exception as e:
            logger.error(f"Error obteniendo businesses para análisis FODA y Riesgos: {str(e)}")
            raise
    
    def is_available(self) -> bool:
        """Verifica si el servicio está disponible"""
        return self.ia_invoker is not None and ANALYZE_CORIL_API_KEY is not None
    
    def get_service_info(self) -> Dict[str, Any]:
        """Retorna información del servicio"""
        return {
            "model": ANALYZE_CORIL_MODEL,
            "max_tokens": ANALYZE_CORIL_MAX_TOKENS,
            "temperature": ANALYZE_CORIL_TEMPERATURE,
            "is_available": self.is_available(),
            "repository_available": self.repository is not None
        }
