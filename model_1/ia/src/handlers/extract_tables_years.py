import json
import logging
import asyncio


from models.model_1.ia.src.config.dependencies import create_service_financial_statement_ia





logger = logging.getLogger()
logger.setLevel(logging.INFO)

service =create_service_financial_statement_ia()

async def main_handler(event, context):
    request_id = getattr(context, "aws_request_id", "unknown")
    logger.info("Inicio de procesamiento")
    logger.info(f"request_id: {event}")
    try:
        records = event.get("Records", [])
        if len(records) != 1:
            msg = f"BatchSize debe ser 1, llegaron {len(records)} registros"
            logger.error(msg)
            return {"statusCode": 200, "status": "error", "request_id": request_id, "error": msg}

        try:
            payload = json.loads(records[0]["body"])
        except (KeyError, json.JSONDecodeError) as e:
            msg = f"JSON inválido en body: {e}"
            logger.error(f"[{request_id}] {msg}")
            return {"statusCode": 200, "status": "error", "request_id": request_id, "error": msg}



        #extraemos lso datos requeidos

        print(payload)
        statement_type = payload.get("type")
        statement_periodicity = payload.get("periodicity_type")
        object_key = payload.get("object_key")
        object_key_txt = payload.get("object_key_txt_output")
        object_key_json_output = payload.get("object_key_json_output")
        page_by_label = payload.get("pages_by_label")
        job_id = payload.get("job_id")

        # Print para verificar que recibe pages_by_label
        print("=" * 80)
        print(f"[DEBUG extract_tables_years] Recibido pages_by_label: {page_by_label}")
        print("=" * 80)

        # user_id = payload['user_id']

        logger.info("............")
        try:
            logger.info(f"tipo: {statement_type}")
            if statement_type.lower() not in ["pb", "bs", "pl"]:
                logger.warning(f"tipo  no valido {statement_type}")
                statement_type = "pb"
                logger.warning(f"tipo  cambiado a {statement_type}")
        except Exception as e:
            logger.warning(f"error al verificar tipo: {e}")

        result = await service.process_extract_data_file_statement(
            object_key=object_key,
            object_key_txt=object_key_txt,
            object_key_json_output=object_key_json_output,
            periodicity_type=statement_periodicity,
            statement_type=statement_type,
            pages_by_label=page_by_label,  # ← IMPORTANTE: pasar pages_by_label para extraer CF
            job_id=job_id
        )
        logger.info(f"se ejecuto todo exitosamente: {result} ")

        return {"statusCode": 200, "status": "success", "request_id": request_id}



    except Exception as err:
        msg = f"Excepción no controlada: {err}"
        logger.exception(msg)
        return {"statusCode": 200, "status": "error", "request_id": request_id, "error": msg}


def lambda_handler(event, context):
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(main_handler(event, context))


if __name__ == "__main__":
    payload = {
        "type": "PB",
        "periodicity_type": "trimestral",
        "pages": [
    1,
    2,
    3,
    4,
    10,
    11,
    12
  ],
        "pages_by_label": {
    "BS": [
      1,
      2
    ],
    "PL": [
      2,
      3,
      4,
      5,
      10,
      11,
      12,
      13
    ],
    "CF": [
      5,
      6,
      11
    ]
  }
        ,
        "object_key": "trimestrales/test1.pdf",
        "object_key_txt_output": "trimestrales/test1.txt",
        "object_key_json_output": "trimestrales/test1.json",
        "timestamp": "2025-11-04T03:01:07.316312",
        "job_id": "d5225db2-e037-4b94-bb3c-748feb733052",
    }

    sqs_event = {
        "Records": [
            {
                "messageId": "test-message-id-0001",
                "receiptHandle": "test-receipt-handle",
                "body": json.dumps(payload),
                "attributes": {
                    "ApproximateReceiveCount": "1",
                    "SentTimestamp": "1600000000000",
                    "SenderId": "ABCDEFGHIJKLMNOPQRSTU",
                    "ApproximateFirstReceiveTimestamp": "1600000000001"
                },
                "messageAttributes": {},
                "md5OfBody": "dummy-md5",
                "eventSource": "aws:sqs",
                "eventSourceARN": "arn:aws:sqs:us-east-1:123456789012:mi-cola.fifo",
                "awsRegion": "us-east-1"
            }
        ]
    }

    print(lambda_handler(sqs_event, None))


