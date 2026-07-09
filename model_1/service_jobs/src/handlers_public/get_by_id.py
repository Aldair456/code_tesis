import logging
from common.response import Response
from models.model_1.service_jobs.src.config.dependencies import get_job_service
from common.exceptions.handler_exception import handle_exception
from models.model_1.service_jobs.src.schemas.response import JobResponseSchema

from common.exceptions.exceptions import (
    BadRequestError,
)
from common_auth_api_keys.src.decorators.api_key import require_api_key

job_service = get_job_service()

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

dto_response = JobResponseSchema()
@require_api_key()
def lambda_handler(event, context):
    request_id = getattr(context, "aws_request_id", "unknown")
    logger.info(f"Inicio procesamiento get job by ID - Request ID: {request_id}")

    try:
        data_key = event.get("api_key_data")

        if not data_key:
            logger.error("Error usuario no autenticado, verificar el auth")
            raise BadRequestError("Usuario no reconocido.")

        # Obtener parámetros de la ruta
        path_params = event.get("pathParameters") or {}
        job_id = path_params.get("job_id")

        if not job_id:
            logger.error("Falta parámetro 'job_id' en pathParameters")
            raise BadRequestError("El parámetro 'job_id' es requerido en la ruta.")

        # Validación básica del formato UUID (opcional pero recomendado)
        if len(job_id.strip()) == 0:
            logger.error("El parámetro 'job_id' está vacío")
            raise BadRequestError("El parámetro 'job_id' no puede estar vacío.")

        logger.info(f"Obteniendo job con ID: {job_id}")

        # Llamar al servicio para obtener el job
        job = job_service.get_job(user=data_key, job_id=job_id)

        # Serializar la respuesta
        data_response = dto_response.dump(job)

        # Información del job para el mensaje
        job_name = job.get('job_name', 'N/A')
        job_status = job.get('status', 'N/A')

        logger.info(f"Job encontrado: {job_name} (Status: {job_status})")

        return Response(
            status_code=200,
            body={
                "success": True,
                "message": f"Job obtenido correctamente.",
                "data": data_response,
            },
        ).to_dict()

    except Exception as err:
        return handle_exception(err, request_id)


if __name__ == "__main__":
    # Evento de prueba para obtener job por ID
    event = {
        "api_key_id": "7dwvnzvi1m",
        "pathParameters": {
            "job_id": "2b44b0a7-e9e2-4029-ae4d-8540cc37b521"
        },
        "queryStringParameters": None
    }

    print(lambda_handler(event, None))