import json
import logging
from typing import Any, Dict

from common.exceptions.handler_exception import handle_exception
from common.response import Response

from models.model_1V2.src.config import config
from models.model_1V2.src.config.dependencies import create_reducto_receive_service

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

service = create_reducto_receive_service()


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda 2: Recibe el resultado de Reducto vía webhook.
    Guarda el JSON en S3 y encola mensaje SQS para iniciar extractores.
    """
    request_id = getattr(context, "aws_request_id", "unknown")
    logger.info("model_1V2 Reducto→Callback (receive) inicio request_id=%s", request_id)
    logger.info("Evento recibido: %s", json.dumps(event, default=str))

    try:
        # Parse del body (puede venir como string JSON o dict)
        body = event.get("body")
        if isinstance(body, str):
            payload = json.loads(body)
        elif isinstance(body, dict):
            payload = body
        else:
            raise ValueError(f"Body inválido: {type(body)}")

        # Extraer metadata del webhook de Reducto
        metadata = payload.get("metadata", {})
        statement_id = metadata.get("financial_statement_id")
        bucket = metadata.get("bucket") or config.S3_BUCKET
        object_key = metadata.get("object_key")
        tracking_job_id = metadata.get("job_id")
        job_id = payload.get("job_id")
        status = payload.get("status")

        logger.info(
            "Webhook Reducto recibido: job_id=%s, status=%s, statement_id=%s, tracking_job_id=%s",
            job_id,
            status,
            statement_id,
            tracking_job_id,
        )

        # Validar que el job esté completado
        if status != "Completed":
            logger.warning("Job no completado aún: status=%s, job_id=%s", status, job_id)
            response = Response(
                status_code=200,
                body={"status": status, "job_id": job_id},
                message=f"Job en estado: {status}",
            )
            return response.to_dict()

        if not statement_id:
            raise ValueError("financial_statement_id no encontrado en metadata")

        if not job_id:
            raise ValueError("job_id no encontrado en payload")

        if not bucket:
            raise ValueError("bucket no configurado (ni en metadata ni en S3_BUCKET)")

        # Construir output_key (mismo patrón que antes)
        output_key_s3 = f"{config.FINANCIAL_STATEMENT_JSON_PREFIX}{statement_id}.json"

        # Guardar resultado y encolar mensaje (el service fetcheará el resultado de Reducto usando job_id)
        result = service.save_reducto_result(
            job_id=job_id,
            bucket=bucket,
            output_key=output_key_s3,
            statement_id=statement_id,
            request_id=request_id,
            tracking_job_id=tracking_job_id,
        )

        logger.info("Resultado Reducto procesado exitosamente: %s", statement_id)
        
        response = Response(
            status_code=200,
            body=result,
            message="Resultado Reducto guardado y mensaje encolado",
        )
        return response.to_dict()

    except Exception as e:
        return handle_exception(e, request_id)


if __name__ == "__main__":
    class MockContext:
        aws_request_id = "local-test-reducto-callback"

    # Simula webhook de Reducto
    test_event = {
        "body": json.dumps({
            "statement_id": "Talently",
            "data": {
                "job_id": "reducto-job-123",
                "status": "completed",
                "result": {"pages": [], "tables": []},
            }
        })
    }

    print(json.dumps(lambda_handler(test_event, MockContext()), indent=2, ensure_ascii=False))
