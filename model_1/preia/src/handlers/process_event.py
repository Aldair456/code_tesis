from models.model_1.preia.src.config.dependencies import get_service_s3
import asyncio
import json


async def main_handler(event, context):
    """
    Lambda handler que soporta eventos de S3, SQS y procesamiento manual
    """
    try:
        s3_service = get_service_s3()

        if 'Records' in event:
            records = event['Records']
            results = []

            for record in records:
                event_source = record.get('eventSource', '')

                # Evento de SQS
                if event_source == 'aws:sqs':
                    result = await process_sqs_record(s3_service, record)
                    results.append(result)

                # Evento directo de S3
                elif event_source == 'aws:s3':
                    data = extract_from_s3_record(record)
                    success = await process_manual(s3_service, data)
                    results.append(success)

                else:
                    data = extract_from_s3_record(record)
                    success = await process_manual(s3_service, data)
                    results.append(success)

            all_success = all(results)
            return {
                'statusCode': 200 if all_success else 500,
                'body': {
                    'success': all_success,
                    'results': results,
                    'processed_count': len(results)
                }
            }

        else:
            # Procesamiento manual directo
            success = await process_manual(s3_service, event)
            return {
                'statusCode': 200 if success else 500,
                'body': {'success': success}
            }

    except Exception as e:
        return {
            'statusCode': 500,
            'body': {'error': str(e)}
        }


def extract_from_s3_record(record):
    """
    Extrae object_key de un registro S3
    """
    s3_info = record.get('s3', {})
    object_key = s3_info.get('object', {}).get('key', '')
    return {
        'object_key': object_key
    }


async def process_manual(s3_service, data):
    """
    Extrae los campos y llama a process_document
    """
    object_key = data.get('object_key')
    object_key_txt_output = data.get('object_key_txt_output')
    object_key_json_output = data.get('object_key_json_output')
    job_id = data.get('job_id')
    is_not_created = data.get('is_not_created')

    # Completar si son None
    if not object_key_txt_output or not object_key_json_output:
        name_object = object_key.rsplit('.', 1)[0]
        if not object_key_txt_output:
            object_key_txt_output = f"{name_object}.txt"
        if not object_key_json_output:
            object_key_json_output = f"{name_object}.json"

    success = await s3_service.process_document(
        object_key=object_key,
        object_key_txt_output=object_key_txt_output,
        object_key_json_output=object_key_json_output,
        job_id= job_id,
        is_not_created=is_not_created
    )
    return success


async def process_sqs_record(s3_service, record):
    """
    Procesa un registro individual de SQS
    """
    try:
        body = record.get('body', '{}')

        if isinstance(body, str):
            message = json.loads(body)
        else:
            message = body

        # Caso 1: El mensaje SQS contiene un evento de S3
        if 'Records' in message:
            data = extract_from_s3_record(message['Records'][0])
            success = await process_manual(s3_service, data)
            return success

        # Caso 2: El mensaje SQS contiene notificación de SNS
        elif 'Message' in message:
            inner_message = message['Message']
            if isinstance(inner_message, str):
                inner_message = json.loads(inner_message)

            if 'Records' in inner_message:
                data = extract_from_s3_record(inner_message['Records'][0])
                success = await process_manual(s3_service, data)
                return success
            else:
                success = await process_manual(s3_service, inner_message)
                return success

        # Caso 3: Mensaje directo con parámetros
        else:
            success = await process_manual(s3_service, message)
            return success

    except json.JSONDecodeError as e:
        return {'success': False, 'error': f'Invalid JSON in SQS message: {str(e)}'}
    except Exception as e:
        return {'success': False, 'error': str(e)}


def lambda_handler(event, context):
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(main_handler(event, context))


if __name__ == '__main__':
    event = {
        "object_key": "trimestrales/test4.png",
    }
    print(lambda_handler(event, None))