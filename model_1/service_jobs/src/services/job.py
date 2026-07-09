import logging
import uuid
from typing import List, Dict, Any

from models.model_1.service_jobs.src.repositories.job import ModelJobRepository
from common_aws_clients.sqs_client import SQSClient


from common.exceptions.exceptions import (
    ServiceDataValidationError,
    ServiceError,
    BusinessValidationError,
    NotFoundError
)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class JobService:
    """
    Servicio de business, como entidad principal maneja algunos gets de eeff(officials y drafts)
    """

    def __init__(
            self,
            job_repository: ModelJobRepository,
            sqs_client: SQSClient
    ):
        self.job_repository = job_repository
        self.sqs_client = sqs_client

    def _validate_uuid(self, id_value: str, field_name: str = "id") -> str:
        """
        Valida que un string sea un UUID válido.

        Args:
            id_value: Valor a validar
            field_name: Nombre del campo para el mensaje de error

        Returns:
            str: UUID validado

        Raises:
            ServiceDataValidationError: Si el UUID no es válido
        """
        try:
            uuid.UUID(id_value)
            logger.debug(f"UUID válido para {field_name}: {id_value}")
            return id_value
        except (ValueError, TypeError) as e:
            error_msg = f"El {field_name} proporcionado no es un UUID válido: {id_value}"
            logger.error(error_msg)
            raise ServiceDataValidationError(error_msg) from e

    def _extract_user_id(self, user: Dict[str, Any]) -> str:
        """
        Extrae y valida el user_id del objeto usuario.

        Args:
            user: Diccionario con información del usuario

        Returns:
            str: UUID del usuario validado

        Raises:
            ServiceDataValidationError: Si no se encuentra un user_id válido
        """
        user_id = user.get("sub") or user.get("id")

        if not user_id:
            error_msg = "No se encontró user_id válido en el objeto usuario"
            logger.error(f"{error_msg}. Usuario recibido: {user}")
            raise ServiceDataValidationError(error_msg)

        return self._validate_uuid(user_id, "user_id")

    def _extract_evaluator_id(self, user: Dict[str, Any]) -> str:
        """
        Extrae y valida el evaluator_id del objeto usuario.

        Args:
            user: Diccionario con información del usuario

        Returns:
            str: UUID del evaluador validado

        Raises:
            ServiceDataValidationError: Si no se encuentra un evaluator_id válido
        """
        evaluator_id = user.get("evaluator_id")

        if not evaluator_id:
            error_msg = "No se encontró evaluator_id válido en el objeto usuario"
            logger.error(f"{error_msg}. Usuario recibido: {user}")
            raise ServiceDataValidationError(error_msg)

        return self._validate_uuid(evaluator_id, "evaluator_id")

    def create(self, data: Dict[str, Any]) :
        data["status"] = "CREATED"
        job = self.job_repository.create(data)
        return job

    def update(self, update_filters: dict, data: Dict[str, Any]) :

        job = self.job_repository.find_one_by_attributes(update_filters)
        job_id = str(job.id)

        update_job = self.job_repository.update(job_id, data)

        return update_job
    def get_job(self,user: Dict[str, Any], job_id: str) -> Dict[str, Any]:
        job = self.job_repository.find_by_id(job_id)
        if not job:
            raise NotFoundError("job not found")
        return job.model_dump()

    def get_by_evaluator_and_filters(self, user: Dict[str, Any], page: int = 0, size: int = 10, business_id: str = None,
                                     user_id: str = None, status: str = None, job_type: str = None) -> List[dict]:
        """
        Obtiene jobs paginados con filtros opcionales

        Args:
            user: Diccionario con información del usuario
            page: Número de página (default: 0)
            size: Tamaño de página (default: 10)
            business_id: ID del business para filtrar (opcional)
            user_id: ID del usuario para filtrar (opcional)
            status: Estado del job para filtrar (opcional)
            job_type: Tipo de job para filtrar (opcional)

        Returns:
            List[dict]: Lista de jobs filtrados

        Raises:
            ServiceDataValidationError: Si los parámetros no son válidos
            ServiceError: Si hay errores en el proceso
        """
        try:
            evaluator_id = self._extract_evaluator_id(user)

            # Validaciones
            if page < 0:
                raise ServiceDataValidationError("El parámetro 'page' debe ser mayor o igual a 0")

            if size < 1 or size > 100:
                raise ServiceDataValidationError("El parámetro 'size' debe estar entre 1 y 100")

            if business_id:
                self._validate_uuid(business_id)

            if user_id:
                self._validate_uuid(user_id)

            # Validar status si se proporciona
            if status:
                valid_statuses = ['CREATED', 'PENDING', 'RUNNING', 'COMPLETED', 'FAILED', 'CANCELLED', 'RETRY']
                if status not in valid_statuses:
                    raise ServiceDataValidationError(f"El status debe ser uno de: {', '.join(valid_statuses)}")

            # Validar job_type si se proporciona
            if job_type:
                valid_job_types = ['EXTRACT_FS', 'EXTRACT_NOTES', 'PROCESS_FS', 'CALCULATE_RATIOS', 'VALIDATE_DATA']
                if job_type not in valid_job_types:
                    raise ServiceDataValidationError(f"El job_type debe ser uno de: {', '.join(valid_job_types)}")

            offset = page * size

            logger.info(f"Obteniendo jobs - evaluator: {evaluator_id}, page: {page}, size: {size}")

            jobs = self.job_repository.get_all_jobs_paginated(
                evaluator_id=evaluator_id,
                business_id=business_id,
                user_id=user_id,
                status=status,
                job_type=job_type,
                limit=size,
                offset=offset
            )

            logger.info(f"Se encontraron {len(jobs)} jobs")
            return jobs

        except ServiceDataValidationError:
            raise
        except Exception as e:
            error_msg = f"Error obteniendo jobs: {str(e)}"
            logger.error(error_msg)
            raise ServiceError(error_msg) from e

    # def get_job(self, user: Dict[str, Any], job_id: str) -> dict:
    #     """
    #     Obtiene un job específico por ID
    #
    #     Args:
    #         user: Diccionario con información del usuario
    #         job_id: ID del job a obtener
    #
    #     Returns:
    #         dict: Job encontrado con información adicional
    #
    #     Raises:
    #         ServiceDataValidationError: Si el job_id no es válido
    #         NotFoundError: Si el job no existe
    #         ServiceError: Si hay errores en el proceso
    #     """
    #     try:
    #         evaluator_id = self._extract_evaluator_id(user)
    #
    #         # Validar job_id
    #         if not job_id:
    #             raise ServiceDataValidationError("job_id es obligatorio")
    #
    #         self._validate_uuid(job_id)
    #
    #         logger.info(f"Obteniendo job por ID - evaluator: {evaluator_id}, job_id: {job_id}")
    #
    #         job = self.job_repository.get_job_by_id(evaluator_id, job_id)
    #
    #         if not job:
    #             raise NotFoundError(f"Job con ID {job_id} no encontrado")
    #
    #         logger.info(f"Job encontrado: {job.get('job_name', 'N/A')}")
    #         return job
    #
    #     except (ServiceDataValidationError, NotFoundError):
    #         raise
    #     except Exception as e:
    #         error_msg = f"Error obteniendo job por ID: {str(e)}"
    #         logger.error(error_msg)
    #         raise ServiceError(error_msg) from e

    def verify_evaluator_id(self, obj: Any, evaluator_id: str) -> bool:
        """
        Verifica si un objeto (dict o model) pertenece al evaluator_id especificado

        Args:
            obj: Objeto a verificar (dict o model con evaluator_id)
            evaluator_id: ID del evaluador a comparar

        Returns:
            bool: True si coincide, False en caso de error o no coincidencia
        """
        try:
            # Validar parámetros de entrada
            if not obj or not evaluator_id:
                logger.warning("Objeto o evaluator_id es None/vacío")
                return False

            obj_evaluator_id = None

            # Caso 1: Es un diccionario
            if isinstance(obj, dict):
                obj_evaluator_id = obj.get('evaluator_id')

            # Caso 2: Es un objeto con atributos
            else:
                # Intentar diferentes formas de acceder al evaluator_id
                if hasattr(obj, 'evaluator_id'):
                    obj_evaluator_id = obj.evaluator_id
                elif hasattr(obj, 'evaluator_id_str'):
                    obj_evaluator_id = obj.evaluator_id_str
                else:
                    logger.warning(f"Objeto tipo {type(obj)} no tiene evaluator_id")
                    return False

            # Verificar si se encontró el evaluator_id del objeto
            if not obj_evaluator_id:
                logger.warning("evaluator_id no encontrado o es None en el objeto")
                return False

            # Convertir ambos a string para comparación
            obj_evaluator_str = str(obj_evaluator_id).strip()
            evaluator_str = str(evaluator_id).strip()

            # Verificar que no estén vacíos después del strip
            if not obj_evaluator_str or not evaluator_str:
                logger.warning("evaluator_id vacío después de conversión")
                return False

            # Comparar los IDs
            is_match = obj_evaluator_str == evaluator_str

            if not is_match:
                logger.warning(f"evaluator_id no coincide: objeto={obj_evaluator_str}, esperado={evaluator_str}")

            return is_match

        except AttributeError as e:
            logger.error(f"Error accediendo a atributos del objeto: {str(e)}")
            return False
        except (TypeError, ValueError) as e:
            logger.error(f"Error de tipo o valor en verify_evaluator_id: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"Error inesperado en verify_evaluator_id: {str(e)}")
            return False

    def delete_job(self, user: Dict[str, Any], job_id: str) -> bool:
        """
        Elimina un job específico por ID

        Args:
            user: Diccionario con información del usuario
            job_id: ID del job a eliminar

        Returns:
            bool: True si se eliminó exitosamente

        Raises:
            ServiceDataValidationError: Si el job_id no es válido
            NotFoundError: Si el job no existe
            BusinessValidationError: Si el job no pertenece al evaluador del usuario
            ServiceError: Si hay errores en el proceso de eliminación
        """
        try:
            evaluator_id = self._extract_evaluator_id(user)

            # Validar job_id
            if not job_id:
                raise ServiceDataValidationError("job_id es obligatorio")

            self._validate_uuid(job_id)

            logger.info(f"Eliminando job - evaluator: {evaluator_id}, job_id: {job_id}")

            # Obtener el job
            job = self.job_repository.find_by_id(job_id)

            if not job:
                raise NotFoundError(f"Job con ID {job_id} no encontrado")

            # Verificar que pertenece al evaluador del usuario
            if not self.verify_evaluator_id(job, evaluator_id):
                raise BusinessValidationError("No tienes permisos para acceder a este recurso")

            # Validaciones de negocio - no eliminar jobs en ejecución
            try:
                job_status = job.get('status') if isinstance(job, dict) else getattr(job, 'status', None)
                if job_status == 'RUNNING':
                    raise BusinessValidationError("No se puede eliminar un job que está en ejecución")
            except (AttributeError, TypeError):
                logger.warning("No se pudo verificar el status del job, continuando con eliminación")

            try:
                job_name = job.get('job_name') if isinstance(job, dict) else getattr(job, 'job_name', 'N/A')
            except (AttributeError, TypeError):
                job_name = 'N/A'

            logger.info(f"Eliminando job: {job_name}")

            # Eliminar usando el ID directamente
            is_deleted = self.job_repository.delete(job_id)

            if not is_deleted:
                raise ServiceError("Ocurrió un error al eliminar el job")

            logger.info(f"Job eliminado exitosamente: {job_id}")
            return True

        except (ServiceDataValidationError, NotFoundError, BusinessValidationError):
            raise
        except Exception as e:
            error_msg = f"Error eliminando job: {str(e)}"
            logger.error(error_msg)
            raise ServiceError(error_msg) from e

    def create_job(self, user: Dict[str, Any], data: Dict[str, Any]) -> dict:

        event_job = {
        }

        if "object_key" not in data:
            raise ServiceDataValidationError("object_key es obligatorio")

        event_job["object_key"] = data.get("object_key")
        new_job_data = {
            "job_name":  data.get("object_key")
        }
        if "object_key_txt_output" in data:
            event_job["object_key_txt_output"] = data.get("object_key_txt_output")

        if "object_key_json_output" in data:
            event_job["object_key_json_output"] = data.get("object_key_json_output")

        new_job = self.job_repository.create(data=new_job_data)

        event_job["job_id"] = new_job.id_str

        self.sqs_client.send_message(
            message=event_job, message_group_id="event_jobs"
        )
        return new_job.model_dump()













