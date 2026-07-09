import json
import logging
from typing import Dict, Any, List
from services.service_alerts.src.config.dependencies import get_alert_service
from common.exceptions.handler_exception import handle_exception
from common.exceptions.exceptions import ServiceDataValidationError, ServiceError

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    request_id = getattr(context, "aws_request_id", "unknown")
    logger.info(f"=== INICIANDO PROCESAMIENTO DE ALERTAS SQS - Request ID: {request_id} ===")

    try:
        # Obtener servicio de alertas
        alert_service = get_alert_service()

        # Información del evento
        total_records = len(event.get('Records', []))
        logger.info(f"Procesando {total_records} mensajes SQS")
        logger.info(f"Función Lambda: {context.function_name if context else 'local'}")

        # Procesar cada mensaje del lote
        results = []
        for record in event.get('Records', []):
            try:
                # Información del mensaje
                message_id = record.get('messageId', 'unknown')
                receipt_handle = record.get('receiptHandle', 'unknown')

                logger.info(f"--- Procesando mensaje ID: {message_id} ---")

                # Procesar el mensaje
                result = alert_service.process_sqs_message(record)
                result['receipt_handle'] = receipt_handle  # Para debugging
                results.append(result)

            except Exception as e:
                logger.error(f"Error procesando record de SQS: {e}")
                results.append({
                    'success': False,
                    'message_id': record.get('messageId', 'unknown'),
                    'error': f'Error inesperado: {str(e)}',
                    'alerts_created': 0
                })

        # Calcular estadísticas finales
        successful_messages = sum(1 for r in results if r.get('success'))
        failed_messages = len(results) - successful_messages
        total_alerts_created = sum(r.get('alerts_created', 0) for r in results if r.get('success'))

        # Preparar respuesta
        response = {
            "statusCode": 200 if failed_messages == 0 else 207,  # 207 = Multi-Status
            "body": json.dumps({
                "message": "Procesamiento de SQS completado",
                "queue_info": {
                    "queue_arn": "arn:aws:sqs:us-east-1:051826715282:process_sqs_alerts.fifo",
                    "queue_url": "https://sqs.us-east-1.amazonaws.com/051826715282/process_sqs_alerts.fifo",
                    "queue_type": "FIFO",
                    "batch_size": total_records
                },
                "processing_summary": {
                    "total_messages": total_records,
                    "successful": successful_messages,
                    "failed": failed_messages,
                    "success_rate": f"{(successful_messages / total_records) * 100:.1f}%" if total_records > 0 else "0%"
                },
                "alerts_summary": {
                    "total_alerts_created": total_alerts_created
                },
                "results": results
            }, indent=2)
        }

        logger.info(f"=== PROCESAMIENTO COMPLETADO ===")
        logger.info(f"Éxito: {successful_messages}/{total_records} mensajes")
        logger.info(f"Alertas creadas: {total_alerts_created}")

        return response

    except ServiceDataValidationError as e:
        logger.error(f"Error de validación: {e}")
        return handle_exception(e, request_id)
    except ServiceError as e:
        logger.error(f"Error del servicio: {e}")
        return handle_exception(e, request_id)
    except Exception as e:
        logger.error(f"Error inesperado en handler: {e}")
        return handle_exception(e, request_id)


if __name__ == '__main__':
    # Ejemplo de evento para testing
    test_event = {
        "Records": [
            {
                "messageId": "test-message-1",
                "receiptHandle": "test-receipt-1",
                "body": json.dumps({
                    "financialStatementId": "5990dfd0-862d-4056-a8bf-253a0ddb89a0"
                })
            }
        ]
    }

    result = lambda_handler(test_event, None)
    print(json.dumps(result, indent=2))
