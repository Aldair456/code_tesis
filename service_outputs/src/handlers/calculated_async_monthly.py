import logging
import json
from common.response import Response
from services.service_outputs.src.config.dependencies import get_output_service
from common.exceptions.handler_exception import handle_exception

from common.exceptions.exceptions import (
    BadRequestError,
)


output_service = get_output_service()

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def parse_sqs_record(record):
    """Parsea un registro individual de SQS."""
    body = record.get("body", "{}")
    return json.loads(body) if isinstance(body, str) else body


def process_single_statement(statement_id, request_id):
    """Procesa un solo statement_id y retorna el resultado."""
    if not statement_id:
        raise BadRequestError("El parámetro 'statement_id' es requerido para calcular outputs.")

    is_calculated = output_service.calculate_monthly_annualized_outputs(statement_id=statement_id)

    if is_calculated:
        logger.info(f"Monthly annualized outputs calculados correctamente para statement_id: {statement_id}")
    else:
        logger.warning(f"Monthly annualized outputs no se calcularon para statement_id: {statement_id}")

    return is_calculated


def process_sqs_event(event, request_id):
    """Procesa múltiples mensajes de SQS."""
    records = event["Records"]
    total = len(records)
    processed = 0
    failed = 0
    results = []

    logger.info(f"Procesando {total} mensaje(s) de SQS - Request ID: {request_id}")

    for index, record in enumerate(records):
        message_id = record.get("messageId", f"unknown-{index}")
        statement_id = None
        try:
            payload = parse_sqs_record(record)
            statement_id = payload.get("statement_id")

            logger.info(f"[{index + 1}/{total}] Procesando mensaje SQS ID: {message_id}, statement_id: {statement_id}")

            is_calculated = process_single_statement(statement_id, request_id)
            processed += 1
            results.append({
                "message_id": message_id,
                "statement_id": statement_id,
                "success": is_calculated
            })

        except Exception as err:
            failed += 1
            logger.error(f"[{index + 1}/{total}] Error procesando mensaje SQS ID: {message_id} - Error: {str(err)}")
            results.append({
                "message_id": message_id,
                "statement_id": statement_id,
                "success": False,
                "error": str(err)
            })

    logger.info(f"Resumen SQS - Total: {total}, Procesados: {processed}, Fallidos: {failed}")

    return Response(
        status_code=200,
        body={
            "success": failed == 0,
            "code": "SQS_BATCH_PROCESSING_COMPLETED",
            "message": f"Procesados {processed}/{total} mensajes. Fallidos: {failed}",
            "results": results
        },
    ).to_dict()


def process_direct_event(event, request_id):
    """Procesa un evento directo (no SQS)."""
    statement_id = event.get("statement_id")

    is_calculated = process_single_statement(statement_id, request_id)

    return Response(
        status_code=200,
        body={
            "success": is_calculated,
            "code": "MONTHLY_ANNUALIZED_OUTPUTS_COMPLETED",
            "message": f"Los outputs mensuales anualizados del FinancialStatement con id({statement_id}) se han calculado correctamente.",
        },
    ).to_dict()


def lambda_handler(event, context):
    request_id = getattr(context, "aws_request_id", "unknown")
    logger.info(f"Inicio procesamiento cálculo de Monthly Annualized outputs - Request ID: {request_id}")

    try:
        if "Records" in event:
            return process_sqs_event(event, request_id)
        else:
            return process_direct_event(event, request_id)

    except Exception as err:
        return handle_exception(err, request_id)


if __name__ == "__main__":
    event_direct = {
        "statement_id": "0d4634c3-3eda-4e64-bdf0-6584316ddf3a",
    }

    print("=== Directo ===")
    print(lambda_handler(event_direct, None))
