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

logger = logging.getLogger(__name__)


class ReductoReceiveService:
    """
    Servicio para recibir el resultado de Reducto, guardarlo en S3 y encolar mensaje SQS.
    """

    def __init__(
        self,
        repository: FinancialStatementS3Repository,
        sqs_init_job_url: Optional[str] = None,
        sqs_message_group_id: Optional[str] = None,
        api_key: str = "",
    ) -> None:
        self._repo = repository
        self._sqs_init_job_url = sqs_init_job_url
        self._sqs_message_group_id = sqs_message_group_id or "financial_statements_reducto"
        self._sqs = boto3.client("sqs") if sqs_init_job_url else None
        self._api_key = api_key or config.REDUCTO_API_KEY

    def save_reducto_result(
        self,
        *,
        job_id: str,
        bucket: str,
        output_key: str,
        statement_id: str,
        request_id: str = "unknown",
        tracking_job_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Fetchea el resultado de Reducto usando job_id, lo guarda en S3 y encola mensaje para iniciar extractores.
        """
        if not job_id:
            raise ValueError("job_id vacío")
        if not bucket:
            raise ValueError("bucket vacío")
        if not output_key:
            raise ValueError("output_key vacío")
        if not statement_id:
            raise ValueError("statement_id vacío")
        if not self._api_key:
            raise ValueError("REDUCTO_API_KEY no configurada")

        # Fetchear resultado de Reducto usando job_id
        logger.info("Fetcheando resultado de Reducto para job_id=%s", job_id)
        client = Reducto(api_key=self._api_key)
        result = client.job.get(job_id)
        reducto_data: Dict[str, Any] = result.model_dump()

        logger.info("Resultado Reducto fetcheado exitosamente")

        # Guardar en S3
        logger.info("Guardando resultado Reducto en S3: %s", output_key)
        self._repo.put_json(output_key, reducto_data, bucket=bucket)

        logger.info("Resultado Reducto guardado exitosamente en S3")

        # Encolar mensaje para iniciar extractores
        self._enqueue_init_job(statement_id=statement_id, request_id=request_id)

        return {
            "statement_id": statement_id,
            "output_bucket": bucket,
            "output_key": output_key,
            "reducto_job_id": job_id,
            "tracking_job_id": tracking_job_id,
            "status": "saved_and_queued",
        }

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
