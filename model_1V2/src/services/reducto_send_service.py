import logging
import os
from typing import Any, Dict, Optional
from uuid import UUID

from reducto import Reducto

from common_job.job import JobService

from models.model_1V2.src.config import config
from models.model_1V2.src.repositories.financial_statement_s3_repository import (
    FinancialStatementS3Repository,
)
from models.model_1V2.src.schemas.s3_event import S3PdfRecord

logger = logging.getLogger(__name__)


class ReductoSendService:
    """
    Servicio para enviar PDFs a Reducto de forma asíncrona.
    No espera el resultado, Reducto llamará al webhook cuando termine.
    """

    def __init__(
        self,
        repository: FinancialStatementS3Repository,
        api_key: str = "",
        pipeline_id: str = "",
        webhook_url: str = "",
        job_service: Optional[JobService] = None,
    ) -> None:
        self._repo = repository
        self._api_key = api_key or config.REDUCTO_API_KEY
        self._pipeline_id = pipeline_id or config.REDUCTO_PIPELINE_ID
        self._webhook_url = webhook_url
        self._job_service = job_service

    def send_to_reducto(
        self,
        *,
        bucket: str,
        key: str,
        statement_id: str,
        job_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Lee el PDF de S3 y lo envía a Reducto de forma asíncrona.
        Reducto llamará al webhook cuando termine el procesamiento.
        """
        if not bucket:
            raise ValueError("bucket vacío en evento S3")
        if not key:
            raise ValueError("key vacío en evento S3")
        if not statement_id:
            raise ValueError("statement_id vacío")
        if not self._api_key:
            raise ValueError("REDUCTO_API_KEY no configurada en env")
        if not self._pipeline_id:
            raise ValueError("REDUCTO_PIPELINE_ID no configurado en env")

        file_bytes = self._repo.get_pdf_bytes(key, bucket=bucket)
        _, ext = os.path.splitext(key)
        upload_name = f"{statement_id}{ext}" if ext else f"{statement_id}.pdf"
        client = Reducto(api_key=self._api_key)
        if self._job_service:
            self._job_service.start_job(
                UUID(statement_id),
                "EXTRACT_FS",
                result_data={"bucket": bucket, "key": key},
            )
            logger.info("Job encolado RUNNING (EXTRACT_FS) statement_id=%s", statement_id)
        logger.info("Subiendo archivo a Reducto: %s (%s)", statement_id, upload_name)
        upload = client.upload(file=(upload_name, file_bytes))

        # Envío asíncrono: Reducto procesará y llamará al webhook cuando termine
        logger.info("Iniciando pipeline Reducto (async) para: %s", statement_id)
        submission = client.pipeline.run_job(
            input=upload,
            pipeline_id=self._pipeline_id,
            async_={
                "webhook": {
                    "mode": "svix"
                },
                "metadata": {
                    "financial_statement_id": statement_id,
                    "bucket": bucket,
                    "object_key": key,
                    "job_id": job_id,
                }
            }
        )
        
        reducto_job_id = submission.job_id

        logger.info(
            "Archivo enviado a Reducto exitosamente (async). statement_id=%s, job_id=%s, reducto_job_id=%s",
            statement_id,
            job_id,
            reducto_job_id,
        )

        return {
            "statement_id": statement_id,
            "input_bucket": bucket,
            "input_key": key,
            "reducto_pipeline_id": self._pipeline_id,
            "reducto_job_id": reducto_job_id,
            "job_id": job_id,
            "status": "sent_to_reducto",
        }

    def process_record(self, record: S3PdfRecord) -> Dict[str, Any]:
        """Procesa un record S3 y envía a Reducto."""
        return self.send_to_reducto(
            bucket=record.bucket,
            key=record.key,
            statement_id=record.statement_id,
        )
