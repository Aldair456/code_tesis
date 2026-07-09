"""
Servicio de análisis de negocio con IA.
Usa common_ia_clients para interactuar con Claude y repository para datos.
"""

import logging
from typing import Dict, Any, Optional
from dataclasses import dataclass

from common_ia_clients.ia_client import AnthropicStrategy, IAInvoker, prompt_ai, IAProviderError
from services.service_credit_proposal_coril.src.repositories.business_analysis_repository import BusinessAnalysisRepository
from services.service_credit_proposal_coril.src.repositories.business_log_event_repository import BusinessLogEventRepository
from services.service_credit_proposal_coril.src.repositories.guarantee_repository import GuaranteeRepository
from services.service_credit_proposal_coril.src.config.config import (
    ANALYZE_CORIL_API_KEY, 
    ANALYZE_CORIL_MODEL, 
    ANALYZE_CORIL_MAX_TOKENS, 
    ANALYZE_CORIL_TEMPERATURE
)
from services.service_credit_proposal_coril.src.utils.normalizers import (
    get_sector_analysis_prompt,
    get_product_analysis_prompt,
    extract_sources_from_text,
    prepare_business_data_for_analysis,
    validate_business_data,
    load_analysis_context,
)
from services.service_credit_proposal_coril.src.utils.appsync_status import notify_en_progreso, notify_fallido

logger = logging.getLogger(__name__)


@dataclass
class AnalysisResult:
    """Resultado del análisis de negocio"""
    sector_analysis: str
    product_analysis: str
    sector_sources: list
    product_sources: list


class BusinessAnalysisService:
    """
    Servicio para analizar negocios usando IA.
    Usa repository para datos, utils para prompts y common_ia_clients para IA.
    """
    
    def __init__(self):
        self.repository = BusinessAnalysisRepository()
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
    
    def get_business_by_id(self, business_id: str) -> Optional[Dict[str, Any]]:
        """Obtiene datos del negocio por ID (para armar memo, header, etc.)."""
        return self.repository.get_business_by_id(business_id)

    def analyze_business_by_id(self, business_id: str, credit_memo_id: Optional[str] = None) -> AnalysisResult:
        """
        Analiza un negocio por su ID usando el repository y utils.
        Notifica EN_PROGRESO al inicio y FALLIDO si ocurre error.
        
        Args:
            business_id: ID del business a analizar
            credit_memo_id: ID del credit memo para notificaciones AppSync (opcional)
            
        Returns:
            AnalysisResult con ambos análisis
        """
        notify_en_progreso("Analizando negocio y producto", credit_memo_id)
        try:
            # Obtener datos del business usando repository
            business = self.repository.get_business_by_id(business_id)
            if not business:
                raise ValueError(f"Business con ID {business_id} no encontrado")
            
            # Validar datos usando utils
            if not validate_business_data(business):
                raise ValueError(f"Datos del business {business_id} no son válidos para análisis")
            
            # Preparar datos usando utils
            business_data = prepare_business_data_for_analysis(business)
            analysis_context = load_analysis_context(
                business_id, self.business_log_repository, self.guarantee_repository
            )
            
            logger.info(f"Analizando business: {business_data['company_name']} ({business_data['sector']}/{business_data['subsector']}) - {business_data['country_name']}")
            
            # 1. Análisis de Sector Económico
            logger.info("Generando análisis de sector económico...")
            sector_prompt = get_sector_analysis_prompt(
                business_data['company_name'], 
                business_data['ruc'], 
                business_data['sector'], 
                business_data['subsector'],
                country_name=business_data['country_name'],
                tax_id_label=business_data['tax_id_label'],
                business_log_context=analysis_context["business_log_context"],
                guarantees_context=analysis_context["guarantees_context"],
            )
            sector_response = self.call_ai(sector_prompt, "business_analysis_sector")
            sector_clean, sector_sources = extract_sources_from_text(sector_response)
            
            # 2. Análisis de Producto, Demanda y Mercado
            logger.info("Generando análisis de producto, demanda y mercado...")
            product_prompt = get_product_analysis_prompt(
                business_data['company_name'], 
                business_data['ruc'], 
                business_data['sector'], 
                business_data['subsector'],
                country_name=business_data['country_name'],
                tax_id_label=business_data['tax_id_label'],
                business_log_context=analysis_context["business_log_context"],
                guarantees_context=analysis_context["guarantees_context"],
            )
            product_response = self.call_ai(product_prompt, "business_analysis_product")
            product_clean, product_sources = extract_sources_from_text(product_response)
            
            result = AnalysisResult(
                sector_analysis=sector_clean,
                product_analysis=product_clean,
                sector_sources=sector_sources,
                product_sources=product_sources
            )
            
            logger.info(f"Análisis completado para {business_data['company_name']}")
            return result
            
        except Exception as e:
            logger.error(f"Error analizando negocio {business_id}: {str(e)}", exc_info=True)
            notify_fallido(f"Error en análisis de negocio: {str(e)}", credit_memo_id)
            raise RuntimeError(f"Error en análisis de negocio: {str(e)}") from e
    
    def get_businesses_for_analysis(self, evaluator_id: Optional[str] = None, 
                                  sector: Optional[str] = None, 
                                  limit: int = 100) -> list:
        """
        Obtiene businesses para análisis usando repository.
        
        Args:
            evaluator_id: Filtro por evaluator (opcional)
            sector: Filtro por sector (opcional)
            limit: Límite de resultados
            
        Returns:
            Lista de businesses disponibles para análisis
        """
        try:
            return self.repository.get_businesses_for_analysis(
                evaluator_id=evaluator_id,
                sector=sector,
                limit=limit
            )
        except Exception as e:
            logger.error(f"Error obteniendo businesses para análisis: {str(e)}")
            raise
    
    def is_available(self) -> bool:
        """Verifica si el servicio está disponible"""
        return self.ia_invoker is not None and ANALYZE_CORIL_API_KEY is not None
    
    def analyze_sector_only(self, business_id: str) -> Dict[str, Any]:
        """
        Analiza solo el sector económico de un negocio por su ID.
        
        Args:
            business_id: ID del business a analizar
            
        Returns:
            Dict con sector_analysis, sector_sources y caracteres
        """
        try:
            # Obtener datos del business usando repository
            business = self.repository.get_business_by_id(business_id)
            if not business:
                raise ValueError(f"Business con ID {business_id} no encontrado")
            
            # Validar datos usando utils
            if not validate_business_data(business):
                raise ValueError(f"Datos del business {business_id} no son válidos para análisis")
            
            # Preparar datos usando utils
            business_data = prepare_business_data_for_analysis(business)
            analysis_context = load_analysis_context(
                business_id, self.business_log_repository, self.guarantee_repository
            )
            
            logger.info(f"Analizando sector económico de: {business_data['company_name']} ({business_data['sector']}/{business_data['subsector']}) - {business_data['country_name']}")
            
            # Análisis de Sector Económico
            logger.info("Generando análisis de sector económico...")
            sector_prompt = get_sector_analysis_prompt(
                business_data['company_name'], 
                business_data['ruc'], 
                business_data['sector'], 
                business_data['subsector'],
                country_name=business_data['country_name'],
                tax_id_label=business_data['tax_id_label'],
                business_log_context=analysis_context["business_log_context"],
                guarantees_context=analysis_context["guarantees_context"],
            )
            sector_response = self.call_ai(sector_prompt, "sector_economico_analysis")
            sector_clean, sector_sources = extract_sources_from_text(sector_response)
            
            return {
                "sector_analysis": sector_clean,
                "sector_sources": sector_sources,
                "caracteres": len(sector_clean)
            }
            
        except Exception as e:
            logger.error(f"Error analizando sector económico {business_id}: {str(e)}", exc_info=True)
            raise RuntimeError(f"Error en análisis de sector económico: {str(e)}") from e
    
    def get_service_info(self) -> Dict[str, Any]:
        """Retorna información del servicio"""
        return {
            "model": ANALYZE_CORIL_MODEL,
            "max_tokens": ANALYZE_CORIL_MAX_TOKENS,
            "temperature": ANALYZE_CORIL_TEMPERATURE,
            "is_available": self.is_available(),
            "repository_available": self.repository is not None
        }