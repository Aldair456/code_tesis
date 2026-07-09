import hashlib
import json
import logging
from typing import Any, Dict, Optional

import boto3
from reducto import Reducto

from models.model_1V2.src.config import config
from models.model_1V2.src.repositories.financial_statement_s3_repository import (
    FinancialStatementS3Repository,
)
from models.model_1V2.src.schemas.s3_event import S3PdfRecord

logger = logging.getLogger(__name__)


class FinancialStatementReductoService:
    def __init__(
        self,
        repository: FinancialStatementS3Repository,
        api_key: str = "",
        pipeline_id: str = "",
        sqs_init_job_url: Optional[str] = None,
        sqs_message_group_id: Optional[str] = None,
    ) -> None:
        self._repo = repository
        self._api_key = api_key or config.REDUCTO_API_KEY
        self._pipeline_id = pipeline_id or config.REDUCTO_PIPELINE_ID
        self._sqs_init_job_url = sqs_init_job_url
        self._sqs_message_group_id = sqs_message_group_id or "financial_statements_reducto"
        self._sqs = boto3.client("sqs") if sqs_init_job_url else None

    def run_from_s3_upload(
        self,
        *,
        bucket: str,
        key: str,
        statement_id: str,
        output_key: str,
    ) -> Dict[str, Any]:
        if not bucket:
            raise ValueError("bucket vacío en evento S3")
        if not key:
            raise ValueError("key vacío en evento S3")
        if not statement_id:
            raise ValueError("statement_id vacío")
        if not output_key:
            raise ValueError("output_key vacío")
        if not self._api_key:
            raise ValueError("REDUCTO_API_KEY no configurada en env")
        if not self._pipeline_id:
            raise ValueError("REDUCTO_PIPELINE_ID no configurado en env")

        pdf_bytes = self._repo.get_pdf_bytes(key, bucket=bucket)
        client = Reducto(api_key=self._api_key)

        upload = client.upload(file=(f"{statement_id}.pdf", pdf_bytes))
        result = client.pipeline.run(input=upload, pipeline_id=self._pipeline_id)
        data: Dict[str, Any] = result.model_dump()

        self._repo.put_json(output_key, data, bucket=bucket)

        return {
            "statement_id": statement_id,
            "input_bucket": bucket,
            "input_key": key,
            "output_bucket": bucket,
            "output_key": output_key,
            "reducto_pipeline_id": self._pipeline_id,
            "reducto_job_id": data.get("job_id"),
        }

    def process_record(self, record: S3PdfRecord, request_id: str = "unknown") -> Dict[str, Any]:
        result = self.run_from_s3_upload(
            bucket=record.bucket,
            key=record.key,
            statement_id=record.statement_id,
            output_key=record.output_key,
        )
        self._enqueue_init_job(statement_id=record.statement_id, request_id=request_id)
        return result

    def _enqueue_init_job(self, statement_id: str, request_id: str) -> None:
        """
        Encola en la FIFO post-Reducto (mismo body que espera sqs_build_stepfunction_payload_from_reducto):
        {"financial_statement_id": "<statement_id>"} — statement_id = nombre del PDF sin extensión.
        """
        if not self._sqs_init_job_url:
            logger.info(
                "SQS_INIT_JOB_FIFO_URL vacío; no se envía mensaje init-job (statement_id=%s)",
                statement_id,
            )
            return

        body = json.dumps({"financial_statement_id": statement_id})
        group_id = self._sqs_message_group_id[:128]
        dedup = hashlib.sha256(f"{request_id}:{statement_id}".encode()).hexdigest()[:128]

        self._sqs.send_message(
            QueueUrl=self._sqs_init_job_url,
            MessageBody=body,
            MessageGroupId=group_id,
            MessageDeduplicationId=dedup,
        )
        logger.info(
            "Mensaje enviado a cola init-job FIFO (financial_statement_id=%s)",
            statement_id,
        )

