import os
from models.model_1.preia.src.repositories.account import AccountRepository

from common_aws_clients.sqs_client import SQSClient
from common_aws_client_async.textract_v2 import TextractClient
from common_aws_clients.s3_presigner import S3Presigner

from models.model_1.preia.src.services.service_s3 import S3Service
from models.model_1.preia.src.utils.document_page_classifier import DocumentPageClassifier
from models.model_1.preia.src.utils.generic_similarity_classifier import GenericSimilarityClassifier
from models.model_1.preia.src.utils.periodicity_analyzer import PeriodicityAnalyzer
from models.model_1.preia.src.utils.text_nomalizer import TextNormalizer

from models.common_model_job.job import JobService


BUCKET_NAME = os.environ['S3_BUCKET_NAME']
SQS_JOB_EVENTS_URL = os.environ['SQS_JOB_EVENTS_URL']
SQS_EXTRACT_TABLES_URL= os.environ['SQS_EXTRACT_TABLES_URL']
SQS_NOTIFY_NOTES_URL = os.environ['SQS_NOTIFY_NOTES_URL']

def create_job_service() -> JobService:
    sqs = SQSClient(SQS_JOB_EVENTS_URL)
    return JobService(sqs_client=sqs)

def create_financial_classifier_page() -> DocumentPageClassifier:
    """Crea un clasificador preconfigurado para estados financieros."""

    classifier = DocumentPageClassifier(
        similarity_threshold=0.10,
        max_page_id=15,
        boost_factor=0.08,
        language='spanish',
        enable_windowing=True,
        window_sizes=[1, 2]
    )

    classifier.configure_classification(
        template_mapping={
            'balance_general': 'BS',
            'estado_resultados': 'PL'
        },
        combination_rules={
            ('BS', 'PL'): 'ESTADOS_FINANCIEROS'
        }
    )

    # 2. CONFIGURAR BOOST DE KEYWORDS (equivalente al código original)
    classifier.configure_keyword_boosting(
        # Palabras clave ponderadas originales (PALABRAS_CLAVE_PONDERADAS)
        weighted_keywords={
            "gastos": 3,
            "ingresos": 3,
            "intereses": 3,
            "deuda": 2,
            "ventas": 2,
            "costos": 2,
            "impuestos": 2,
        },

        # Sinónimos por categoría (equivalentes a KW_BS y KW_PL del original)
        category_synonyms={
            'BS': [  # Sinónimos para Balance General (KW_BS original)
                "balance general",
                "estado de situación financiera",
                "balance sheet",
                "estado de situación patrimonial",
                "estado de posición financiera",
                "balance de situación",
                "estado de balance",
                "estado patrimonial",
                "hoja de balance",
                "informe de situación financiera",
                "estado de activos, pasivos y patrimonio"
            ],
            'PL': [  # Sinónimos para Estado de Resultados (KW_PL original)
                "p&l",
                "estado de pérdidas y ganancias",
                "estado de resultados",
                "estado de resultados integrales",
                "estado de resultados acumulados",
                "egp",
                "estado de ganancias y pérdidas"
            ]
        }
    )

    # Patrones regex para detectar páginas de Flujo de Caja (CF)
    try:
        classifier.set_regex_patterns({
            'CF': [
                r'(estado\s+de\s+flujo[s]?\s+de\s+efectivo[s]?)',
                r'(estado.*flujo.*efectivo)',  # Patrón flexible: permite cualquier cosa entre palabras
                r'(flujo[s]?\s+de\s+caja)',
                r'(cash\s*flow)',
                r'(actividades?\s+de\s+(operaci[oó]n|inversi[oó]n|financiaci[oó]n))',
                r'(flujo.{0,40}(efectivo|caja))',
                r'((efectivo|caja).{0,40}flujo)'
            ]
        })
    except Exception:
        # Si la versión del clasificador no soporta regex aún, continuar sin fallar
        pass

    return classifier


def create_financial_classifier() -> GenericSimilarityClassifier:
    """Ejemplo de configuración para clasificación de estados financieros."""

    classifier = GenericSimilarityClassifier(
        similarity_threshold=0.1,
        language='spanish',
        default_not_detected_label='ND'
    )

    # Configurar palabras clave ponderadas
    classifier.set_weighted_keywords({
        "gastos": 3,
        "ingresos": 3,
        "intereses": 3,
        "deuda": 2,
        "ventas": 2,
        "costos": 2,
        "impuestos": 2,
        "activos": 3,
        "pasivos": 3,
        "patrimonio": 2,
    })

    # Configurar mapeo de clasificación
    template_mapping = {
        'balance_general': 'BS',
        'estado_resultados': 'PL'
    }

    # Reglas de combinación
    combination_rules = {
        ('BS', 'PL'): 'PB'
    }

    classifier.configure_classification(
        template_mapping=template_mapping,
        combination_rules=combination_rules,
        multiple_detection_strategy='combine'
    )

    return classifier


def create_periodicity_analyzer() -> PeriodicityAnalyzer:
    """Crea un analizador de periodicidad preconfigurado."""
    # Asumo configuración básica, ajusta según tus necesidades
    analyzer = PeriodicityAnalyzer()
    return analyzer


def create_s3() -> S3Presigner:
    """Crea cliente S3 preconfigurado."""
    s3 = S3Presigner(BUCKET_NAME)
    return s3


def create_textract() -> TextractClient:
    """Crea cliente Textract preconfigurado."""
    textract = TextractClient()
    return textract



def create_sqs_client() -> SQSClient:
    """Crea cliente SQS preconfigurado."""
    sqs = SQSClient(SQS_EXTRACT_TABLES_URL)
    return sqs

def create_sqs_client_notes() -> SQSClient:
    """Crea cliente SQS preconfigurado."""
    sqs = SQSClient(SQS_NOTIFY_NOTES_URL)
    return sqs

def get_service_s3() -> S3Service:
    """
    Factory function para crear S3Service con todas las dependencias inyectadas.

    Returns:
        S3Service: Instancia completamente configurada
    """
    # 1. Crear repositorios
    account_repository = AccountRepository()

    # 2. Crear clientes
    s3_client = create_s3()
    sqs_client = create_sqs_client()
    sqs_client_notes = create_sqs_client_notes()
    textract_client = create_textract()

    # 3. Crear clasificadores y analizadores
    generic_classifier = create_financial_classifier()
    page_classifier = create_financial_classifier_page()
    periodicity_analyzer = create_periodicity_analyzer()

    text_normalizer = TextNormalizer()

    # 4. crear servicios basicos
    job_service = create_job_service()

    # 4. Crear e inyectar todas las dependencias en S3Service
    s3_service = S3Service(
        account_repository=account_repository,
        s3_client=s3_client,
        sqs_client=sqs_client,
        sqs_client_notes=sqs_client_notes,
        textract_client=textract_client,
        classifier=generic_classifier,
        periodicity_analyzer=periodicity_analyzer,
        page_classifier=page_classifier,
        job_service=job_service,
        text_normalizer=text_normalizer
    )

    return s3_service


# Función de conveniencia para usar en Lambda/handlers
def get_configured_s3_service() -> S3Service:
    """
    Alias más descriptivo para obtener el servicio S3 configurado.
    Útil para handlers de Lambda o controladores.
    """
    return get_service_s3()


# Para debugging/testing - función que muestra las dependencias
def validate_s3_service_dependencies() -> dict:
    """
    Valida que todas las dependencias se puedan crear correctamente.
    Útil para debugging y testing.
    """
    try:
        service = get_service_s3()

        return {
            "status": "success",
            "dependencies": {
                "account_repository": type(service.account_repository).__name__,
                "s3_client": type(service.s3_client).__name__,
                "sqs_client": type(service.sqs_client).__name__,
                "textract_client": type(service.textract_client).__name__,
                "classifier": type(service.classifier).__name__,
                "periodicity_analyzer": type(service.periodicity_analyzer).__name__,
                "page_classifier": type(service.page_classifier).__name__,
            }
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e)
        }


#sdfghjklñ

