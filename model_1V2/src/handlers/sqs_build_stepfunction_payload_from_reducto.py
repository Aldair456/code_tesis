import json
import logging
import os
import uuid
from typing import Any, Dict, List

import boto3

from common.exceptions.handler_exception import handle_exception_sfn

from models.model_1V2.src.config import config
from models.model_1V2.src.config.dependencies import (
    create_financial_statement_reducto_payload_service,
)
from models.model_1V2.src.schemas.financial_statement_event import (
    parse_financial_statement_id_sqs_event,
)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

service = create_financial_statement_reducto_payload_service()
_stepfunctions = boto3.client("stepfunctions")


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    request_id = getattr(context, "aws_request_id", "unknown")
    logger.info("model_1V2 sqs payload builder inicio request_id=%s", request_id)
    logger.info("Evento recibido: %s", json.dumps(event, default=str))
    try:
        parsed = parse_financial_statement_id_sqs_event(event)
        bucket = config.S3_BUCKET
        if not bucket:
            raise ValueError("S3_BUCKET no configurado")

        results: List[Dict[str, Any]] = []
        for p in parsed:
            payload = service.build_payload(
                bucket=bucket,
                financial_statement_id=p.financial_statement_id,
            )
            results.append(payload)

        logger.info(
            "Payloads construidos (n=%s), financial_statement_id=%s",
            len(results),
            [r.get("financial_statement_id") for r in results],
        )

        executions: List[Dict[str, Any]] = []
        # ARN de la Step Function que orquesta extract_bs/pl/cf y subir_bd_reducto.
        state_machine_arn = config.MODEL2_IA_DEV_EXTRACTOR_STATE_MACHINE_ARN
        if not state_machine_arn:  
                raise ValueError("MODEL2_IA_DEV_EXTRACTOR_STATE_MACHINE_ARN no configurado")
        else:
            for payload in results:
                execution_name = f"exec-{uuid.uuid4()}"
                logger.info("Iniciando Step Function: %s", execution_name)

                start_resp = _stepfunctions.start_execution(
                    stateMachineArn=state_machine_arn,
                    name=execution_name,
                    # Contrato solicitado: mandamos payload DIRECTO (sin envoltorio SQS).
                    input=json.dumps(payload, default=str),
                )
                executions.append(
                    {
                        "executionArn": start_resp.get("executionArn"),
                        "name": execution_name,
                        "financial_statement_id": payload.get("financial_statement_id"),
                    }
                )

        # Si BatchSize=1, devolvemos el payload directamente como conveniencia.
        return {
            "status": "success",
            "request_id": request_id,
            "processed": len(results),
            "payload": results[0] if len(results) == 1 else None,
            "payloads": results,
            "executions": executions,
        }
    except Exception as e:
        return handle_exception_sfn(e, request_id, event)



if __name__ == "__main__":
    class MockContext:
        aws_request_id = "local-test-model-1v2-sqs"

    # Para pruebas locales: no invocar AWS Step Functions.
    os.environ["SKIP_STEP_FUNCTIONS"] = "true"

    test_event = {
        "Records": [
            {
                "body": json.dumps(
                    {
                        "financial_statement_id": "5009c3bd-33b4-4e13-849e-192bca07c2f0",
                    }
                )
            }
        ]
    }

    print(json.dumps(lambda_handler(test_event, MockContext()), indent=2, ensure_ascii=False))

