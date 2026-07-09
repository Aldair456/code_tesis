import logging
from typing import List, Optional, Dict
from common.repositories.base import BaseRepository
from common.models.models import ModelJob

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class ModelJobRepository(BaseRepository[ModelJob]):
    def __init__(self):
        super().__init__("model_jobs", ModelJob)

    # def get_all_jobs_paginated(self, evaluator_id: str, business_id: str = None,
    #                            user_id: str = None, status: str = None, job_type: str = None,  limit: int = 10, offset: int = 0) -> List[dict]:
    #     """
    #     Obtiene todos los jobs paginados con información del usuario, ordenados por created_at descendente
    #
    #     Args:
    #         evaluator_id: ID del evaluador (obligatorio)
    #         limit: Límite de resultados (default: 10)
    #         offset: Offset para paginación (default: 0)
    #         business_id: ID del business para filtrar (opcional)
    #         user_id: ID del usuario para filtrar (opcional)
    #         status: Estado del job para filtrar (opcional)
    #         job_type: Tipo de job para filtrar (opcional)
    #
    #     Returns:
    #         List[dict]: Lista de jobs con información del usuario
    #     """
    #     try:
    #         logger.info(f"Obteniendo jobs paginados - evaluator_id: {evaluator_id}, limit: {limit}, offset: {offset}")
    #
    #         if not evaluator_id:
    #             raise ValueError("evaluator_id es obligatorio")
    #
    #         # Query base
    #         base_query = """
    #             SELECT
    #                 j.*,
    #                 u.name as user_name,
    #                 b.name as business_name
    #             FROM jobs j
    #             LEFT JOIN users u ON j.user_id = u.id
    #             LEFT JOIN businesses b ON j.business_id = b.id
    #             WHERE j.evaluator_id = %s
    #         """
    #
    #         params = [self._convert_value_for_sql(evaluator_id)]
    #
    #         # Agregar filtros opcionales
    #         if business_id:
    #             base_query += " AND j.business_id = %s"
    #             params.append(self._convert_value_for_sql(business_id))
    #
    #         if user_id:
    #             base_query += " AND j.user_id = %s"
    #             params.append(self._convert_value_for_sql(user_id))
    #
    #         if status:
    #             base_query += " AND j.status = %s"
    #             params.append(status)
    #
    #         if job_type:
    #             base_query += " AND j.job_type = %s"
    #             params.append(job_type)
    #
    #         # Ordenamiento y paginación
    #         base_query += """
    #             ORDER BY j.created_at DESC
    #             LIMIT %s OFFSET %s
    #         """
    #         params.extend([limit, offset])
    #
    #         logger.info(f"Ejecutando query con {len(params)} parámetros")
    #
    #         # Ejecutar query
    #         records = self._execute_query(base_query, tuple(params))
    #
    #         if not records:
    #             logger.info("No se encontraron jobs")
    #             return []
    #
    #         # Convertir los registros a diccionarios
    #         jobs_with_user_info = []
    #         for record in records:
    #             job_dict = dict(record)
    #             jobs_with_user_info.append(job_dict)
    #
    #         logger.info(f"Se encontraron {len(jobs_with_user_info)} jobs")
    #         return jobs_with_user_info
    #
    #     except Exception as e:
    #         logger.error(f"Error obteniendo jobs paginados: {str(e)}")
    #         raise

    def get_all_jobs_paginated(self, evaluator_id: str, business_id: str = None,
                               user_id: str = None, status: str = None, job_type: str = None, limit: int = 10,
                               offset: int = 0) -> List[dict]:
        """
        Obtiene todos los jobs paginados con información del usuario, ordenados por created_at descendente

        Args:
            evaluator_id: ID del evaluador (obligatorio)
            limit: Límite de resultados (default: 10)
            offset: Offset para paginación (default: 0)
            business_id: ID del business para filtrar (opcional)
            user_id: ID del usuario para filtrar (opcional)
            status: Estado del job para filtrar (opcional)
            job_type: Tipo de job para filtrar (opcional)

        Returns:
            List[dict]: Lista de jobs con información del usuario
        """
        try:
            logger.info(f"Obteniendo jobs paginados - evaluator_id: {evaluator_id}, limit: {limit}, offset: {offset}")

            if not evaluator_id:
                raise ValueError("evaluator_id es obligatorio")

            # Query base con COALESCE para manejar valores NULL
            base_query = """
                SELECT 
                    j.*,
                    COALESCE(u.name, '') as user_name,
                    COALESCE(b.name, '') as business_name
                FROM jobs j
                LEFT JOIN users u ON j.user_id = u.id
                LEFT JOIN businesses b ON j.business_id = b.id
                WHERE j.evaluator_id = %s
            """

            params = [self._convert_value_for_sql(evaluator_id)]

            # Agregar filtros opcionales
            if business_id:
                base_query += " AND j.business_id = %s"
                params.append(self._convert_value_for_sql(business_id))

            if user_id:
                base_query += " AND j.user_id = %s"
                params.append(self._convert_value_for_sql(user_id))

            if status:
                base_query += " AND j.status = %s"
                params.append(status)

            if job_type:
                base_query += " AND j.job_type = %s"
                params.append(job_type)

            # Ordenamiento y paginación
            base_query += """
                ORDER BY j.created_at DESC
                LIMIT %s OFFSET %s
            """
            params.extend([limit, offset])

            logger.info(f"Ejecutando query con {len(params)} parámetros")

            # Ejecutar query
            records = self._execute_query(base_query, tuple(params))

            if not records:
                logger.info("No se encontraron jobs")
                return []

            # Convertir los registros a diccionarios
            jobs_with_user_info = []
            for record in records:
                job_dict = dict(record)
                jobs_with_user_info.append(job_dict)

            logger.info(f"Se encontraron {len(jobs_with_user_info)} jobs")
            return jobs_with_user_info

        except Exception as e:
            logger.error(f"Error obteniendo jobs paginados: {str(e)}")
            raise

    def get_job_by_id(self, evaluator_id: str, job_id: str) -> Optional[dict]:
        """
        Obtiene un job específico por ID con información del usuario y business

        Args:
            evaluator_id: ID del evaluador (obligatorio)
            job_id: ID del job a buscar (obligatorio)

        Returns:
            Optional[dict]: Job con información del usuario o None si no existe
        """
        try:
            logger.info(f"Obteniendo job por ID - evaluator_id: {evaluator_id}, job_id: {job_id}")

            if not evaluator_id:
                raise ValueError("evaluator_id es obligatorio")

            if not job_id:
                raise ValueError("job_id es obligatorio")

            query = """
                SELECT 
                    j.*,
                    u.name as user_name,
                    b.name as business_name
                FROM jobs j
                LEFT JOIN users u ON j.user_id = u.id
                LEFT JOIN businesses b ON j.business_id = b.id
                WHERE j.evaluator_id = %s AND j.id = %s
            """

            params = (
                self._convert_value_for_sql(evaluator_id),
                self._convert_value_for_sql(job_id)
            )

            logger.info("Ejecutando query para obtener job por ID")

            # Ejecutar query
            record = self._execute_query_one(query, params)

            if not record:
                logger.info(f"No se encontró job con ID: {job_id}")
                return None

            job_dict = dict(record)
            logger.info(f"Job encontrado: {job_dict.get('job_name', 'N/A')}")
            return job_dict

        except Exception as e:
            logger.error(f"Error obteniendo job por ID: {str(e)}")
            raise

