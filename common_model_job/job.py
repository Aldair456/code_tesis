from datetime import datetime
from typing import Optional, Dict, Any
from uuid import UUID, uuid4
from pydantic import BaseModel, Field
from enum import Enum
from common_aws_clients.sqs_client import SQSClient


class JobStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    RETRY = "RETRY"
    CANCELLED = "CANCELLED"


# Modelo para CREAR jobs (campos mínimos requeridos)
class CreateJobModel(BaseModel):
    id: UUID
    # Campos opcionales con valores por defecto
    job_name: Optional[str] = None
    job_description: Optional[str] = None
    priority: int = 5
    metadata: Optional[Dict[str, Any]] = None
    config_data: Optional[Dict[str, Any]] = None
    max_retries: int = 3


# Modelo para identificar un job
class JobIdentifier(BaseModel):
    id: UUID


# Modelo para ACTUALIZAR jobs (solo campos que se pueden cambiar)
class UpdateJobModel(BaseModel):
    # Campos opcionales para actualizar
    status: Optional[str] = None
    result_data: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    retry_count: Optional[int] = None
    config_data: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None


# Modelos para mensajes SQS
class SQSCreateJobMessage(BaseModel):
    action: str = "CREATE_JOB"
    job_data: CreateJobModel
    message_id: UUID = Field(default_factory=uuid4)
    timestamp: datetime = Field(default_factory=datetime.utcnow)



class SQSUpdateJobMessage(BaseModel):
    action: str = "UPDATE_JOB"
    job_identifier: JobIdentifier
    job_data: UpdateJobModel
    message_id: UUID = Field(default_factory=uuid4)
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class JobService:
    def __init__(self, sqs_client: SQSClient):
        self.sqs_client = sqs_client


    # Método para obtener modelo de creación
    def get_create_job_model(self) -> type[CreateJobModel]:
        """Retorna la clase del modelo para crear jobs"""
        return CreateJobModel

    # Método para obtener modelo de actualización
    def get_update_job_model(self) -> type[UpdateJobModel]:
        """Retorna la clase del modelo para actualizar jobs"""
        return UpdateJobModel

    # Método para obtener modelo identificador
    def get_job_identifier_model(self) -> type[JobIdentifier]:
        """Retorna la clase del modelo para identificar jobs"""
        return JobIdentifier

    # Crear job y enviar a SQS

    def create_identifier(self, id: UUID) -> JobIdentifier:

        return JobIdentifier(
            id=id
        )


    def create_job(self, job_data: CreateJobModel) -> dict:
        """Envía un job a la cola de creación"""
        try:
            message = SQSCreateJobMessage(job_data=job_data)

            # El SQSClient debe recibir string o dict, convertimos a dict
            message_dict = message.model_dump()

            response = self.sqs_client.send_message(
                message=message_dict,
                message_group_id=f"job-1"
            )

            return {
                "success": True,
                "message_id": response.get('MessageId', str(message.message_id)),
                "job_id": str(job_data.id),
                "status": "QUEUED_FOR_CREATION"
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

    # Actualizar job y enviar a SQS
    def update_job(self, job_identifier: JobIdentifier, job_data: UpdateJobModel) -> dict:
        """Envía una actualización de job a la cola de updates"""
        try:
            message = SQSUpdateJobMessage(
                job_identifier=job_identifier,
                job_data=job_data
            )

            # Convertimos a dict para el SQSClient
            message_dict = message.model_dump()

            response = self.sqs_client.send_message(
                message=message_dict,
                message_group_id=f"job-update-{job_identifier.id}"
            )

            return {
                "success": True,
                "message_id": response.get('MessageId', str(message.message_id)),
                "job_id": str(job_identifier.id),
                "status": "QUEUED_FOR_UPDATE"
            }

        except Exception as e:
            print(e)
            return {
                "success": False,
                "error": str(e)
            }

    # Métodos de conveniencia para updates comunes
    def start_job(self,id: UUID) -> dict:
        """Marca un job como iniciado"""

        job_identifier = JobIdentifier(
            id=id
        )
        update_data = UpdateJobModel(
            status=JobStatus.RUNNING,
            started_at=datetime.utcnow()
        )
        return self.update_job(job_identifier, update_data)

    def complete_job(self, id: UUID,result_data: Optional[Dict[str, Any]] = None) -> dict:
        """Marca un job como completado"""
        job_identifier = JobIdentifier(
            id=id
        )
        update_data = UpdateJobModel(
            status=JobStatus.COMPLETED,
            completed_at=datetime.utcnow(),
            result_data=result_data
        )
        return self.update_job(job_identifier, update_data)

    # def fail_job(self, resource_id: UUID, job_type: str, resource_table: Optional[str] = None,
    #              error_message: str = "", should_retry: bool = True) -> dict:
    #     """Marca un job como fallido"""
    #     status = JobStatus.RETRY if should_retry else JobStatus.FAILED
    #
    #     job_identifier = JobIdentifier(
    #         resource_id=resource_id,
    #         job_type=job_type,
    #         resource_table=resource_table or self.table
    #     )
    #     update_data = UpdateJobModel(
    #         status=status,
    #         error_message=error_message,
    #         completed_at=datetime.utcnow() if not should_retry else None
    #     )
    #     return self.update_job(job_identifier, update_data)

    def fail_job(self, id: UUID,
                 error_message: str = "", should_retry: bool = True,
                 result_data: Optional[Dict[str, Any]] = None) -> dict:
        """Marca un job como fallido, opcionalmente con datos de resultado parcial"""
        status = JobStatus.RETRY if should_retry else JobStatus.FAILED

        job_identifier = JobIdentifier(
            id=id
        )
        update_data = UpdateJobModel(
            status=status,
            error_message=error_message,
            completed_at=datetime.utcnow() if not should_retry else None,
            result_data=result_data
        )
        return self.update_job(job_identifier, update_data)

    def increment_retry(self, id: UUID,
                        current_retry_count: int = 0) -> dict:
        """Incrementa el contador de reintentos"""
        job_identifier = JobIdentifier(
            id=id
        )
        update_data = UpdateJobModel(
            retry_count=current_retry_count + 1,
            status=JobStatus.PENDING  # Vuelve a pending para retry
        )
        return self.update_job(job_identifier, update_data)


