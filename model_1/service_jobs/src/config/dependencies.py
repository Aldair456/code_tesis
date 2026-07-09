import os
from models.model_1.service_jobs.src.repositories.job import ModelJobRepository
from models.model_1.service_jobs.src.services.job import JobService
from common_aws_clients.sqs_client import SQSClient

SQS_INIT_MODEL_URL= os.environ['SQS_INIT_MODEL_URL']
def create_sqs_client() -> SQSClient:
    """Crea cliente SQS preconfigurado."""
    sqs = SQSClient(SQS_INIT_MODEL_URL)
    return sqs
def get_job_service():
    job_repository = ModelJobRepository()
    return JobService(
        job_repository=job_repository,
        sqs_client=create_sqs_client(),
        )







