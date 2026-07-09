import json
import logging
import os
from typing import Any, Dict, List

from common.exceptions.handler_exception import handle_exception_sfn

from models.model_1V2.src.config import config
from models.model_1V2.src.config.dependencies import create_reducto_send_service
from models.model_1V2.src.schemas.s3_event import parse_s3_pdf_records

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

service = create_reducto_send_service()


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda 1: Envía PDFs a Reducto de forma asíncrona.
    Reducto procesará el PDF y llamará al webhook cuando termine.
    
    Soporta eventos S3 directos y via SNS (el parser maneja ambos).
    """
    request_id = getattr(context, "aws_request_id", "unknown")
    logger.info("model_1V2 S3→Reducto (send) inicio request_id=%s", request_id)
    logger.info("Evento recibido: %s", json.dumps(event, default=str))

    try:
        logger.info("Parseando records con prefix: %s", config.FINANCIAL_STATEMENTS_PREFIX)
        parsed_records = parse_s3_pdf_records(
            event,
            input_prefix=config.FINANCIAL_STATEMENTS_PREFIX,
            output_prefix=config.FINANCIAL_STATEMENT_JSON_PREFIX,
        )
        logger.info("Records parseados: %s", len(parsed_records))

        results: List[Dict[str, Any]] = []
        for r in parsed_records:
            logger.info(
                "Procesando record: bucket=%s, key=%s, statement_id=%s",
                r.bucket, r.key, r.statement_id,
            )
            results.append(service.process_record(r))

        logger.info("PDFs enviados a Reducto exitosamente (n=%s)", len(results))
        return {
            "status": "success",
            "request_id": request_id,
            "processed": len(results),
            "results": results,
        }
    except Exception as e:
        return handle_exception_sfn(e, request_id, event)


if __name__ == "__main__":
    class MockContext:
        aws_request_id = "local-test-model-1v2"

    s3_event = {
        "Records": [
            {
                "eventSource": "aws:s3",
                "s3": {
                    "bucket": {"name": os.environ.get("S3_BUCKET", "mi-bucket-financiero-dev2")},
                    "object": {"key": "FinancialStatements/EEFF 11-2021 Magna Cabs.pdf"},
                },
            }
        ]
    }

    sns_event = {
        "Records": [
            {
                "EventSource": "aws:sns",
                "Sns": {
                    "Message": json.dumps(s3_event)
                }
            }
        ]
    }

    print("=== Test S3 directo ===")
    print(json.dumps(lambda_handler(s3_event, MockContext()), indent=2, ensure_ascii=False))

    print("\n=== Test via SNS ===")
    print(json.dumps(lambda_handler(sns_event, MockContext()), indent=2, ensure_ascii=False))