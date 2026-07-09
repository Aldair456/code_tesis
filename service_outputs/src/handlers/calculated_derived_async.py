import logging
import json
from common.response import Response
from services.service_outputs.src.config.dependencies import get_derived_cashflow_service
from common.exceptions.handler_exception import handle_exception
from common.exceptions.exceptions import BadRequestError

derived_cashflow_service = get_derived_cashflow_service()
logger = logging.getLogger(__name__)


def _process_one(statement_id: str, evaluator_id: str):
    if not statement_id or not evaluator_id:
        raise BadRequestError("statement_id y evaluator_id son requeridos")
    ok = derived_cashflow_service.calculate_derived_cashflows(
        statement_id=statement_id,
        evaluator_id=evaluator_id
    )
    try:
        derived_cashflow_service.calculate_derived_cashflows_ltm(
            statement_id=statement_id,
            evaluator_id=evaluator_id
        )
    except Exception as e:
        logger.warning(f"LTM derived cashflows no calculados para {statement_id}: {e}")
    try:
        derived_cashflow_service.calculate_derived_cashflows_monthly_annualized(
            statement_id=statement_id,
            evaluator_id=evaluator_id
        )
    except Exception as e:
        logger.warning(f"Monthly annualized derived cashflows no calculados para {statement_id}: {e}")
    return ok


def _process_sqs(event, request_id):
    records = event["Records"]
    processed, failed = 0, 0
    results = []

    for i, record in enumerate(records):
        msg_id = record.get("messageId", f"unknown-{i}")
        try:
            payload = json.loads(record.get("body", "{}"))
            statement_id = payload.get("statement_id")
            evaluator_id = payload.get("evaluator_id")
            ok = _process_one(statement_id, evaluator_id)
            processed += 1
            results.append({"message_id": msg_id, "statement_id": statement_id, "success": ok})
        except Exception as err:
            failed += 1
            logger.error(f"Error procesando mensaje {msg_id}: {err}")
            results.append({"message_id": msg_id, "success": False, "error": str(err)})

    return Response(
        status_code=200,
        body={
            "success": failed == 0,
            "code": "SQS_DERIVED_CASHFLOWS_COMPLETED",
            "message": f"Procesados {processed}/{len(records)}. Fallidos: {failed}",
            "results": results
        }
    ).to_dict()


def _process_direct(event, request_id):
    statement_id = event.get("statement_id")
    evaluator_id = event.get("evaluator_id")
    ok = _process_one(statement_id, evaluator_id)
    return Response(
        status_code=200,
        body={
            "success": ok,
            "code": "DERIVED_CASHFLOWS_CALCULATED",
            "message": f"Derived cashflows calculados para statement {statement_id}"
        }
    ).to_dict()


def lambda_handler(event, context):
    request_id = getattr(context, "aws_request_id", "unknown")
    try:
        if "Records" in event:
            return _process_sqs(event, request_id)
        return _process_direct(event, request_id)
    except Exception as err:
        return handle_exception(err, request_id)


if __name__ == "__main__":
    event = {
        "statement_id": "00000000-0000-0000-0000-000000000001",
        "evaluator_id": "00000000-0000-0000-0000-000000000002"
    }
    print(lambda_handler(event, None))
