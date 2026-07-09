import logging
import warnings
from pathlib import Path
from typing import Optional

# Suprimir warning de pkg_resources deprecado en docxcompose (dependencia de docxtpl)
# Este warning viene de una librería externa y no podemos controlarlo
warnings.filterwarnings("ignore", message=".*pkg_resources is deprecated.*", category=UserWarning)

import boto3
from services.service_credit_proposal_coril.src.repositories.credit_proposal_coril_repository import CreditProposalCorilRepository
from services.service_credit_proposal_coril.src.services.pdf_generator_coril_service import PDFGeneratorCorilService
from services.service_credit_proposal_coril.src.services.word_generator_coril_service import WordGeneratorCorilService
from services.service_credit_proposal_coril.src.services.credit_proposal_coril_service import CreditProposalCorilService
from services.service_credit_proposal_coril.src.services.business_analysis_service import BusinessAnalysisService
from services.service_credit_proposal_coril.src.services.financial_analysis_service import FinancialAnalysisService
from services.service_credit_proposal_coril.src.services.solvency_liquidity_service import SolvencyLiquidityService
from services.service_credit_proposal_coril.src.services.foda_risks_service import FodaRisksService
from services.service_credit_proposal_coril.src.services.credit_memo_builder_service import CreditMemoBuilderService
from services.service_credit_proposal_coril.src.config.config import AWS_REGION, S3_BUCKET
from services.service_credit_proposal_coril.src.repositories.business import BusinessRepository
from services.service_credit_proposal_coril.src.repositories.evaluator_routes_repository import EvaluatorRoutesRepository
from services.service_credit_proposal_coril.src.services.evaluator_route_service import EvaluatorRouteService

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def get_credit_proposal_coril_service() -> CreditProposalCorilService:
    """
    Obtiene una instancia del servicio CreditProposalCorilService.
    """
    # Crear repositorio
    repository = CreditProposalCorilRepository()
    
    # Crear generador de PDF
    templates_dir = Path(__file__).resolve().parent.parent / "templates"
    pdf_generator = PDFGeneratorCorilService(templates_dir=templates_dir)
    
    # Crear generador de Word (con templates_dir)
    word_generator = WordGeneratorCorilService(templates_dir=templates_dir)
    
    # Crear cliente S3
    s3_client = boto3.client("s3", region_name=AWS_REGION)
    s3_bucket = S3_BUCKET
    if s3_bucket:
        s3_client.bucket_name = s3_bucket
        logger.info(f"S3 bucket configurado: {s3_bucket}")
    else:
        logger.warning("S3_BUCKET no configurado, las funciones de S3 no estarán disponibles")
        s3_client.bucket_name = None
    
    # Crear repositorio de businesses
    business_repository = BusinessRepository()
    
    # Crear servicio principal
    return CreditProposalCorilService(
        repository=repository,
        pdf_generator=pdf_generator,
        word_generator=word_generator,
        s3_client=s3_client,
        business_repository=business_repository
    )


def get_business_analysis_service():
    """
    Obtiene una instancia del servicio BusinessAnalysisService.
    """
    return BusinessAnalysisService()


def get_financial_analysis_service():
    """
    Obtiene una instancia del servicio FinancialAnalysisService.
    """
    return FinancialAnalysisService()


def get_solvency_liquidity_service():
    """
    Obtiene una instancia del servicio SolvencyLiquidityService.
    """
    return SolvencyLiquidityService()


def get_foda_risks_service():
    """
    Obtiene una instancia del servicio FodaRisksService.
    """
    return FodaRisksService()


def get_credit_memo_builder_service() -> CreditMemoBuilderService:
    """
    Obtiene una instancia del servicio CreditMemoBuilderService.
    Usa BusinessAnalysisService para datos del negocio.
    Usa FinancialAnalysisRepository para obtener estados financieros y datapoints.
    Usa EvaluatorRoutesRepository para decidir título por defecto (TS → informe general, sin CORIL).
    """
    from services.service_credit_proposal_coril.src.repositories.financial_analysis_repository import FinancialAnalysisRepository
    from services.service_credit_proposal_coril.src.repositories.evaluator_routes_repository import EvaluatorRoutesRepository
    return CreditMemoBuilderService(
        business_analysis_service=get_business_analysis_service(),
        financial_analysis_repository=FinancialAnalysisRepository(),
        evaluator_routes_repository=EvaluatorRoutesRepository(),
    )


def get_credit_proposal_coril_repository() -> CreditProposalCorilRepository:
    """
    Obtiene una instancia del repositorio CreditProposalCorilRepository.
    """
    return CreditProposalCorilRepository()


def get_evaluator_route_service() -> EvaluatorRouteService:
    """Obtiene una instancia del servicio EvaluatorRouteService."""
    return EvaluatorRouteService(
        evaluator_routes_repository=EvaluatorRoutesRepository(),
    )
