"""
Servicio de análisis financiero con IA.
Usa common_ia_clients para interactuar con Claude y repository para datos.
"""

import logging
from typing import Dict, Any, Optional
from dataclasses import dataclass

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
    get_profitability_analysis_prompt,
    get_cash_generation_analysis_prompt,
    extract_sources_from_text,
    prepare_financial_data_for_analysis,
    validate_financial_data,
    load_analysis_context,
)

logger = logging.getLogger(__name__)


@dataclass
class FinancialAnalysisResult:
    """Resultado del análisis financiero"""
    profitability_analysis: str
    cash_generation_analysis: str
    profitability_sources: list
    cash_generation_sources: list


class FinancialAnalysisService:
    """
    Servicio para analizar finanzas usando IA.
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
    
    def analyze_financial_by_business_id(self, business_id: str) -> FinancialAnalysisResult:
        """
        Analiza finanzas de un negocio por su ID usando el repository y utils.
        
        Args:
            business_id: ID del business a analizar
            
        Returns:
            FinancialAnalysisResult con ambos análisis
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
            
            logger.info(f"Analizando finanzas de: {financial_data_prepared['company_name']} ({financial_data_prepared['sector']}/{financial_data_prepared['subsector']}) - {financial_data_prepared['country_name']}")
            
            # 1. Análisis de Rentabilidad
            logger.info("Generando análisis de rentabilidad...")
            profitability_prompt = get_profitability_analysis_prompt(
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
            profitability_response = self.call_ai(profitability_prompt, "financial_analysis_profitability")
            profitability_clean, profitability_sources = extract_sources_from_text(profitability_response)
            
            # 2. Análisis de Generación de Caja
            logger.info("Generando análisis de generación de caja...")
            cash_generation_prompt = get_cash_generation_analysis_prompt(
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
            logger.info("country_name: %s", financial_data_prepared['country_name'])
            cash_generation_response = self.call_ai(cash_generation_prompt, "financial_analysis_cash_generation")
            cash_generation_clean, cash_generation_sources = extract_sources_from_text(cash_generation_response)
            
            result = FinancialAnalysisResult(
                profitability_analysis=profitability_clean,
                cash_generation_analysis=cash_generation_clean,
                profitability_sources=profitability_sources,
                cash_generation_sources=cash_generation_sources
            )
            
            logger.info(f"Análisis financiero completado para {financial_data_prepared['company_name']}")
            return result
            
        except Exception as e:
            logger.error(f"Error analizando finanzas {business_id}: {str(e)}", exc_info=True)
            raise RuntimeError(f"Error en análisis financiero: {str(e)}") from e
    
    def get_businesses_for_financial_analysis(self, evaluator_id: Optional[str] = None, 
                                            sector: Optional[str] = None, 
                                            limit: int = 100) -> list:
        """
        Obtiene businesses para análisis financiero usando repository.
        
        Args:
            evaluator_id: Filtro por evaluator (opcional)
            sector: Filtro por sector (opcional)
            limit: Límite de resultados
            
        Returns:
            Lista de businesses disponibles para análisis financiero
        """
        try:
            return self.repository.get_businesses_for_financial_analysis(
                evaluator_id=evaluator_id,
                sector=sector,
                limit=limit
            )
        except Exception as e:
            logger.error(f"Error obteniendo businesses para análisis financiero: {str(e)}")
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
