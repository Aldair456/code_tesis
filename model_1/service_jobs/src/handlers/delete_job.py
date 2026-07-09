import logging
from common.response import Response
from services.service_jobs.src.config.dependencies import get_job_service
from common.exceptions.handler_exception import handle_exception

from common.exceptions.exceptions import (
    BadRequestError,
)

from common.auth.auth_proxy import authorize
from common.auth.strategies import RoleHierarchyStrategy

job_service = get_job_service()

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


@authorize(required_permission="ANALYST", strategy_cls=RoleHierarchyStrategy)
def lambda_handler(event, context):
    request_id = getattr(context, "aws_request_id", "unknown")
    logger.info(f"Inicio procesamiento delete job - Request ID: {request_id}")

    try:
        user = event.get("user")

        if not user:
            logger.error("Error usuario no autenticado, verificar el auth")
            raise BadRequestError("Usuario no reconocido.")

        # Obtener parámetros de la ruta
        path_params = event.get("pathParameters") or {}
        job_id = path_params.get("job_id")

        if not job_id:
            logger.error("Falta parámetro 'job_id' en pathParameters")
            raise BadRequestError("El parámetro 'job_id' es requerido en la ruta.")

        # Validación básica del formato
        if len(job_id.strip()) == 0:
            logger.error("El parámetro 'job_id' está vacío")
            raise BadRequestError("El parámetro 'job_id' no puede estar vacío.")

        logger.info(f"Eliminando job con ID: {job_id}")

        # Llamar al servicio para eliminar el job
        result = job_service.delete_job(user=user, job_id=job_id)

        logger.info(f"Job eliminado exitosamente: {job_id}")

        # Retornar 204 No Content (sin body)
        return Response(
            status_code=204,
            body=None
        ).to_dict()

    except Exception as err:
        return handle_exception(err, request_id)


if __name__ == "__main__":
    # Evento de prueba para eliminar job por ID
    event = {
        "user": {
            "roles": ["ADMIN"],
            "evaluator_id": "9ca49e78-dec4-4046-a48a-8fc661110b28"
        },
        "pathParameters": {
            "job_id": "fecaa0a8-8a58-450f-92fc-3d702d7bbbaa"
        }
    }

    print(lambda_handler(event, None))