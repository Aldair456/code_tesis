import os

from common_aws_clients.sqs_client import SQSClient
from common_aws_client_async.s3_client import S3Client
from common_ia_clients.ia_client import IAInvoker, AnthropicStrategy
from common_aws_client_async.textract_v2 import TextractClient

from common_job.job import JobService
from models.model_1V2.src.repositories.financial_statement_s3_repository import (
    FinancialStatementS3Repository,
)
from models.model_1V2.src.repositories.financial_accounts_repository import (
    AccountRepository,
)
from models.model_1V2.src.services.financial_statement_reducto_service import (
    FinancialStatementReductoService,
)
from models.model_1V2.src.services.reducto_send_service import (
    ReductoSendService,
)
from models.model_1V2.src.services.reducto_receive_service import (
    ReductoReceiveService,
)
from models.model_1V2.src.services.financial_statement_reducto_payload_service import (
    FinancialStatementReductoPayloadService,
)
from models.model_1V2.src.services.financial_statement_ia_service import (
    FinancialStatementIaService,
)


def create_financial_statement_reducto_service() -> FinancialStatementReductoService:
    """DEPRECATED: Usar create_reducto_send_service y create_reducto_receive_service por separado."""
    from models.model_1V2.src.config import config
    
    repo = FinancialStatementS3Repository()
    return FinancialStatementReductoService(
        repository=repo,
        sqs_init_job_url=config.SQS_INIT_JOB_FIFO_URL,
        sqs_message_group_id=config.SQS_INIT_JOB_MESSAGE_GROUP_ID,
    )


def create_reducto_send_service() -> ReductoSendService:
    """Servicio para enviar PDFs a Reducto (Lambda 1)."""
    from models.model_1V2.src.config import config
    
    repo = FinancialStatementS3Repository()
    sqs_job_events_url = os.environ.get("SQS_JOB_EVENTS_URL", "")
    job_service = (
        JobService(sqs_client=SQSClient(sqs_job_events_url), table="financial_statements")
        if sqs_job_events_url
        else None
    )

    return ReductoSendService(
        repository=repo,
        job_service=job_service,
    )


def create_reducto_receive_service() -> ReductoReceiveService:
    """Servicio para recibir resultado de Reducto y encolar (Lambda 2)."""
    from models.model_1V2.src.config import config

    repo = FinancialStatementS3Repository()

    return ReductoReceiveService(
        repository=repo,
        sqs_init_job_url=config.SQS_INIT_JOB_FIFO_URL,
        sqs_message_group_id=config.SQS_INIT_JOB_MESSAGE_GROUP_ID,
        api_key=config.REDUCTO_API_KEY,
    )


def create_financial_statement_reducto_payload_service() -> FinancialStatementReductoPayloadService:
    repo = FinancialStatementS3Repository()
    return FinancialStatementReductoPayloadService(repository=repo)


def create_financial_statement_ia_service() -> FinancialStatementIaService:
    """
    Misma composición que model_1/ia pero con clases bajo models.model_1V2 (sin mezclar model_1).
    Lee variables de entorno solo al construir el servicio (no al importar este módulo).
    """
    anthropic_api_key = os.environ["ANTHROPIC_API_KEY"]
    bucket_name = os.environ["S3_BUCKET_NAME"]
    queue_url = os.environ["QUEUE_URL_STRUCTURE_ACCOUNT"]
    sqs_job_events_url = os.environ["SQS_JOB_EVENTS_URL"]

    strategy = AnthropicStrategy(
        api_key=anthropic_api_key,
        model="claude-sonnet-4-6",
        timeout_seconds=60 * 10,
        max_tokens=10000,
    )
    ia_client = IAInvoker(strategy=strategy)
    account_repository = AccountRepository()
    s3_client = S3Client(bucket_name=bucket_name)
    textract_client = TextractClient()
    sqs_client = SQSClient(queue_url=queue_url)
    job_service = JobService(
        sqs_client=SQSClient(sqs_job_events_url),
        table="financial_statements",
    )

    return FinancialStatementIaService(
        account_repository=account_repository,
        s3_client=s3_client,
        textract_client=textract_client,
        sqs_client=sqs_client,
        ia_client=ia_client,
        job_service=job_service,
    )

