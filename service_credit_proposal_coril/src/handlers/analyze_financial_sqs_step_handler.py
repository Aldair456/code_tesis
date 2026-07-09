"""
Lambda que recibe mensajes de la cola SQS de análisis financiero
y arranca la Step Function BusinessMemoOrchestration con business_id.
La validación de acceso ya se hace en el Lambda emisor (HTTP).
"""
import logging
import json
from typing import Dict, Any

import boto3

from services.service_credit_proposal_coril.src.config.config import BUSINESS_MEMO_STATE_MACHINE_ARN

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def lambda_handler(event: Dict[str, Any], context) -> Dict[str, Any]:
    """
    Handler Lambda disparado por SQS. Por cada mensaje:
    - Parsea body (business_id)
    - Inicia una ejecución de la Step Function BusinessMemoOrchestration con business_id.
    """
    request_id = getattr(context, "aws_request_id", "unknown")
    logger.info("Inicio procesamiento SQS -> Step Function - Request ID: %s", request_id)
    if not BUSINESS_MEMO_STATE_MACHINE_ARN:
        logger.error("BUSINESS_MEMO_STATE_MACHINE_ARN no configurado")
        records = event.get("Records", [])
        return {
            "batchItemFailures": [{"itemIdentifier": r.get("messageId")} for r in records]
        }

    stepfunctions = boto3.client("stepfunctions")
    batch_item_failures = []

    if "Records" not in event:
        logger.warning("Evento sin Records de SQS")
        return {"batchItemFailures": []}

    for record in event["Records"]:
        message_id = record.get("messageId", "unknown")
        try:
            body = record.get("body", "{}")
            if isinstance(body, str):
                message_data = json.loads(body)
            else:
                message_data = body

            business_id = message_data.get("business_id")
            if not business_id:
                logger.error("Mensaje %s sin business_id", message_id)
                batch_item_failures.append({"itemIdentifier": message_id})
                continue
            # Extraer user_id, deal_id y credit_memo_id del mensaje
            user_id = message_data.get("user_id")
            deal_id = message_data.get("deal_id")
            credit_memo_id = message_data.get("credit_memo_id")

            logger.info("Iniciando Step Function para business_id=%s, credit_memo_id=%s, user_id=%s (mensaje=%s)", 
                       business_id, credit_memo_id, user_id, message_id)

            input_payload = {
                "business_id": business_id,
                "user_id": user_id,
                "deal_id": deal_id,
                "credit_memo_id": credit_memo_id,
            }
            stepfunctions.start_execution(
                stateMachineArn=BUSINESS_MEMO_STATE_MACHINE_ARN,
                input=json.dumps(input_payload),
            )
            logger.info("Step Function iniciada para business_id=%s", business_id)
        except Exception as err:
            logger.error("Error procesando mensaje %s: %s", message_id, err, exc_info=True)
            batch_item_failures.append({"itemIdentifier": message_id})

    return {"batchItemFailures": batch_item_failures}
