import os

from models.model_1.ia.src.repositories.financial_statement import FinancialStatementRepository
from models.model_1.ia.src.repositories.account import AccountRepository
from models.model_1.ia.src.repositories.financial_datapoint import FinancialDataPointRepository
from models.model_1.ia.src.repositories.business import BusinessRepository
from models.model_1.ia.src.repositories.match_account_extracts import MatchAccountExtractsRepository

from models.model_1.ia.src.services.simple_servicio_datapoints import FinancialDataPointService

from common_job.job import JobService
from common_job.sqs_client import SQSClient


# Required env vars: QUEUE_URL, STATE_MACHINE_ARN, ANTHROPIC_API_KEY, MONGO_URI,
#   BUCKET_NAME, MY_DATABASE_NAME, DATABASE_URL, WS_ENDPOINT
# Set these in your environment before running locally.

ANTHROPIC_API_KEY= os.environ['ANTHROPIC_API_KEY']
MONGO_URI = os.environ['MONGO_URI']
BUCKET_NAME = os.environ['BUCKET_NAME']
QUEUE_URL = os.environ['QUEUE_URL']
DATABASE_URL = os.environ['DATABASE_URL']
MY_DATABASE_NAME = os.environ['MY_DATABASE_NAME']
STATE_MACHINE_ARN = os.environ['STATE_MACHINE_ARN']
WS_ENDPOINT = os.environ['WS_ENDPOINT']
MAX_RETRIES = 3


def create_job_service() -> JobService:
    sqs = SQSClient(os.environ.get("JOBS_QUEUE_URL", QUEUE_URL))
    return JobService(sqs_client=sqs, table="financial_statements")

def create_service_financial_datapoints():
    financial_statement_repository = FinancialStatementRepository()
    account_repository = AccountRepository()
    financial_datapoints_repository = FinancialDataPointRepository()
    business_repository = BusinessRepository()
    match_account_extracts_repository = MatchAccountExtractsRepository()
    job_service = create_job_service()

    return FinancialDataPointService(
        financial_statement_repository=financial_statement_repository,
        account_repository=account_repository,
        financial_datapoint_repository=financial_datapoints_repository,
        job_service=job_service,
        business_repository=business_repository,
        match_account_extracts_repository=match_account_extracts_repository,
    )
