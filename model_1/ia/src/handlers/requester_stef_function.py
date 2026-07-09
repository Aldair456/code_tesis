import os
import json
import time
import uuid
import logging
import boto3

STATE_MACHINE_ARN = os.environ['STATE_MACHINE_ARN']




# Logger
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# AWS Step Functions client
_stepfunctions = boto3.client('stepfunctions')

# Configuración de reintentos y polling
MAX_RETRIES = 3
POLL_INTERVAL = 5


def lambda_handler(event, context):
    """
    Lambda mediador entre SQS y Step Functions.
    Lee un único mensaje SQS (BatchSize=1), arranca la ejecución
    y pasa TODO el evento de SQS (incluyendo messageId y group) a Step Functions.
    Espera a que termine, retornando siempre statusCode=200.
    """
    request_id = getattr(context, 'aws_request_id', 'unknown')
    logger.info(f"Inicio de procesamiento SQS → StepFunctions")

    try:
        # 1. Validar BatchSize=1
        records = event.get('Records', [])
        if len(records) != 1:
            msg = f"BatchSize debe ser 1, recibidos {len(records)} mensajes"
            logger.error(msg)
            return {
                'statusCode': 200,
                'status': 'error',
                'request_id': request_id,
                'error': msg
            }

        # 2. Mantener el evento completo para Step Functions
        sf_input = json.dumps(event)

        # 3. Ejecutar Step Functions con reintentos
        execution_name = f"exec-{uuid.uuid4()}"
        logger.info(f"Iniciando Step Functions: {execution_name}")
        retries = 0

        while retries < MAX_RETRIES:
            try:
                start_resp = _stepfunctions.start_execution(
                    stateMachineArn=STATE_MACHINE_ARN,
                    name=execution_name,
                    input=sf_input
                )
                exec_arn = start_resp['executionArn']
                logger.info(f"ExecutionArn: {exec_arn}")

                # 4. Polling hasta que termine
                while True:
                    desc = _stepfunctions.describe_execution(executionArn=exec_arn)
                    status = desc.get('status')
                    if status in ('SUCCEEDED', 'FAILED', 'TIMED_OUT', 'ABORTED'):
                        break
                    time.sleep(POLL_INTERVAL)

                logger.info(f"Estado final: {status}")

                # 5. Retornar resultado
                if status == 'SUCCEEDED':
                    output = desc.get('output', '{}')
                    return {
                        'statusCode': 200,
                        'status': 'ok',
                        'request_id': request_id,
                        'result': json.loads(output)
                    }
                else:
                    msg = f"Ejecución finalizada con estado {status}"
                    logger.error(msg)
                    return {
                        'statusCode': 200,
                        'status': 'error',
                        'request_id': request_id,
                        'error': msg
                    }

            except Exception as start_err:
                retries += 1
                logger.warning(f"Error intento {retries}/{MAX_RETRIES}: {start_err}", exc_info=True)
                if retries >= MAX_RETRIES:
                    msg = f"Agotados {MAX_RETRIES} intentos de start_execution: {start_err}"
                    logger.error(msg, exc_info=True)
                    return {
                        'statusCode': 200,
                        'status': 'error',
                        'request_id': request_id,
                        'error': msg
                    }
                time.sleep(POLL_INTERVAL)

    except Exception as unexp_err:
        msg = f"Excepción no controlada: {unexp_err}"
        logger.exception(msg)
        return {
            'statusCode': 200,
            'status': 'error',
            'request_id': request_id,
            'error': msg
        }



# Si lo ejecutamos localmente para probar (solo con un evento de prueba)
if __name__ == '__main__':



    payload = {
        "bucket": "mi-bucket-financiero-dev2",
        "key": "anuales/12 EEFF BG dic 23 mba-final.pdf",
        "type": "bs",
        "statement_periodicity": "trimestrales",
        "business_id": "678a8a66491d13c4290ceaaf",
        "statement_id": "678a8a66491d13c4290ceaaf",
        # si tu schema requiere "user_id", agrégalo aquí
        "user_id": "1234567890abcdef12345678"
    }

    # Construimos el evento SQS emulado
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

    response = lambda_handler(sqs_event, None)
    print(response)

