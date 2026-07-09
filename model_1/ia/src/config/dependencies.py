import os
from common_aws_clients.sqs_client import SQSClient
from common_aws_client_async.s3_client import S3Client
from common_ia_clients.ia_client import IAInvoker, AnthropicStrategy
from common_aws_client_async.textract_v2 import TextractClient

from models.model_1.ia.src.repositories.account import AccountRepository
from models.model_1.ia.src.services.service_accounts_ia import FinancialStatementIaService

from models.common_model_job.job import JobService








ANTHROPIC_API_KEY= os.environ['ANTHROPIC_API_KEY']
BUCKET_NAME = os.environ['S3_BUCKET_NAME']
QUEUE_URL = os.environ['QUEUE_URL_STRUCTURE_ACCOUNT']
WS_ENDPOINT = os.environ['WS_ENDPOINT']
SQS_JOB_EVENTS_URL = os.environ['SQS_JOB_EVENTS_URL']

MAX_RETRIES = 3


def create_job_service() -> JobService:
    sqs = SQSClient(SQS_JOB_EVENTS_URL)
    return JobService(sqs_client=sqs)

def crate_ia_client():
    strategy = AnthropicStrategy(
        api_key=ANTHROPIC_API_KEY,
        model="claude-sonnet-4-6",
        timeout_seconds=60*10,
        max_tokens=10000

    )

    return IAInvoker(strategy=strategy)

def create_s3_client():
    return S3Client(bucket_name=BUCKET_NAME)

def create_sqs_client():
    return SQSClient(queue_url=QUEUE_URL)

def create_textract_client():
    return TextractClient()

def create_service_financial_statement_ia():
    account_repository = AccountRepository()
    s3_client = create_s3_client()
    textract_client = create_textract_client()
    sqs_client = create_sqs_client()
    ia_client = crate_ia_client()

    job_service = create_job_service()

    return FinancialStatementIaService(
        account_repository=account_repository,
        s3_client=s3_client,
        textract_client=textract_client,
        sqs_client=sqs_client,
        ia_client=ia_client,
        job_service=job_service
    )






