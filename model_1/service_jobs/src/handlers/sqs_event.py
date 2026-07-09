import logging
import json
from models.model_1.service_jobs.src.config.dependencies import get_job_service

from models.model_1.service_jobs.src.schemas.request import JobCreateSchema, JobUpdateSchema

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

job_service = get_job_service()

dto_create = JobCreateSchema()

dto_update = JobUpdateSchema()




def lambda_handler(event, context):
    """
    Lambda disparada por mensajes de SQS para registrar actividades de analistas.
    Cada mensaje contiene los datos para crear un log de actividad.
    """
    for record in event.get("Records", []):
        try:
            body = json.loads(record.get("body", "{}"))
            logger.info("Mensaje SQS recibido: %s", body)

            action = body.get("action")
            if not isinstance(action, str) or not action:
                logger.error("es neseario que la accion sea valida")
                raise ValueError("Accion no valida")


            if action == "CREATE_JOB":

                data = body.get("job_data")
                data_valid = dto_create.load(data)

                job = job_service.create(data_valid)

            if action == "UPDATE_JOB":
                job_identifier = body.get("job_identifier")

                if not job_identifier:
                    logger.error("No se encuentra un job_identifier.")
                    raise ValueError("No se encuentra un job_identifier.")

                data = body.get("job_data")
                data_valid = dto_update.load(data)
                job = job_service.update(job_identifier, data_valid)

            logger.info("Datos de jobs porcesados exitosamente con ID")

        except json.JSONDecodeError as e:
            logger.error("Error al parsear JSON del mensaje SQS: %s", e)
        except Exception as e:
            logger.error("Error al procesar mensaje de SQS: %s", e, exc_info=True)

    return {"statusCode": 200, "body": "Processed"}
