
import logging
import json
import uuid
from multiprocessing import RawArray
from typing import Optional, Dict, Any, List
from uuid import UUID
import re
from common_aws_clients.s3_presigner import S3Presigner
from common_aws_client_async.textract_v2 import TextractClient
from common_aws_clients.sqs_client import SQSClient

from models.model_1.preia.src.repositories.account import AccountRepository
from models.model_1.preia.src.utils.generic_similarity_classifier import GenericSimilarityClassifier
from models.model_1.preia.src.utils.document_page_classifier import DocumentPageClassifier
from models.model_1.preia.src.utils.periodicity_analyzer import PeriodicityAnalyzer
from models.model_1.preia.src.utils.text_nomalizer import TextNormalizer


from models.common_model_job.job import JobService


from common.exceptions.exceptions import (
    ServiceDataValidationError,
    BusinessValidationError
)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class S3Service:
    """
    Servicio para procesamiento de documentos financieros desde S3
    Disparado por eventos de S3 cuando se sube un nuevo documento
    """

    def __init__(self,
                 account_repository: AccountRepository,
                 s3_client: S3Presigner,
                 sqs_client: SQSClient,
                 sqs_client_notes: SQSClient,
                 textract_client: TextractClient,
                 classifier: GenericSimilarityClassifier,
                 periodicity_analyzer: PeriodicityAnalyzer,
                 page_classifier: DocumentPageClassifier,
                 text_normalizer: TextNormalizer,
                 job_service: JobService
                 ):

        self.account_repository = account_repository
        self.s3_client = s3_client
        self.sqs_client = sqs_client
        self.sqs_client_notes = sqs_client_notes
        self.textract_client = textract_client
        self.classifier = classifier
        self.periodicity_analyzer = periodicity_analyzer
        self.text_normalizer = text_normalizer
        self.page_classifier = page_classifier
        self.job_service = job_service

    
    async def extract_text_from_pdf(self, object_key: str) -> str:
        """
        Extrae texto del PDF usando Textract (solo extracción)

        Args:
            object_key: Clave del archivo en S3

        Returns:
            str: Texto extraído del documento
        """
        if not object_key:
            raise ServiceDataValidationError("object_key es requerido")

        try:
            bucket_name = self.s3_client.bucket_name
            logger.info(f"Iniciando extracción de texto - Bucket: {bucket_name}, Archivo: {object_key}")

            # Proceso de Textract
            job_id = await self.textract_client.start_and_wait_for_result_detection(
                bucket_name=bucket_name,
                object_key=object_key
            )

            logger.info(f"Procesando resultados Textract - Job ID: {job_id}")
            text_result = await self.textract_client.process_textract_result_detection(job_id)

            if not text_result or len(text_result.strip()) < 10:
                raise ServiceDataValidationError(f"Texto extraído insuficiente o vacío")

            logger.info(f"Extracción completada - {len(text_result)} caracteres extraídos")
            return text_result

        except Exception as e:
            logger.error(f"Error extrayendo texto de {object_key}: {str(e)}")
            raise ServiceDataValidationError(f"Error en extracción de texto: {str(e)}")

    def _save_text_backup(self, object_key_txt_output: str, text_content: str) -> None:
        """Guarda respaldo del texto extraído"""
        try:
            self.s3_client.upload_text_file(object_key_txt_output, text_content)
            logger.debug(f"Texto respaldado en: {object_key_txt_output}")
        except Exception as e:
            logger.warning(f"Error guardando respaldo de texto: {str(e)}")

    def _prepare_classification_templates(self) -> Dict[str, str]:
        """Prepara templates para clasificación de documentos"""
        try:
            accounts_bs = self.account_repository.find_all_by_filters(type="BS")
            accounts_pl = self.account_repository.find_all_by_filters(type="PL")

            if not accounts_bs or not accounts_pl:
                logger.warning(f"Cuentas faltantes - BS: {len(accounts_bs)}, PL: {len(accounts_pl)}")

            templates = {
                "balance_general": ", ".join([acc.display_name for acc in accounts_bs if acc.display_name]),
                "estado_resultados": ", ".join([acc.display_name for acc in accounts_pl if acc.display_name])
            }

            logger.info(f"Templates preparados - BS: {len(accounts_bs)} cuentas, PL: {len(accounts_pl)} cuentas")
            return templates

        except Exception as e:
            logger.error(f"Error preparando templates: {str(e)}")
            raise ServiceDataValidationError(f"Error obteniendo cuentas: {str(e)}")

    def _configure_classifiers(self, templates: Dict[str, str]) -> None:
        """Configura los clasificadores con templates"""
        try:
            self.classifier.set_templates(templates=templates)
            self.page_classifier.set_templates(templates=templates)
            logger.debug("Clasificadores configurados correctamente")
        except Exception as e:
            logger.error(f"Error configurando clasificadores: {str(e)}")
            raise ServiceDataValidationError(f"Error configurando clasificadores: {str(e)}")
     
    async def _analyze_document(self, text: str) -> Dict[str, Any]:
        """Analiza y clasifica el documento"""
        if not text or not text.strip():
            raise ServiceDataValidationError("Texto vacío para análisis")

        try:
            logger.info("Iniciando análisis y clasificación del documento")

            # Clasificar tipo de documento
            document_type = self.classifier.classify_document(raw_text=text)

            # Analizar periodicidad
            periodicity = self.periodicity_analyzer.analyze_periodicity(text=text, lines_per_page=20)

            # Clasificar páginas
            pages = self.page_classifier.classify_pages(full_text=text)

            results = {
                'type': document_type,
                'periodicity_type': periodicity,
                'pages': pages,
                'success': bool(document_type and document_type != 'unknown')
            }

            logger.info(f"Análisis completado - Tipo: {document_type}, Periodicidad: {periodicity}")
            return results

        except Exception as e:
            logger.error(f"Error analizando documento: {str(e)}")
            return {
                'type': None,
                'periodicity_type': None,
                'pages': None,
                'success': False,
                'error': str(e)
            }

    async def process_document_analysis(self, object_key: str, object_key_txt_output: str) -> Dict[str, Any]:
        """
        Procesa análisis completo del documento

        Args:
            key: Clave del archivo en S3
            statement_id: ID del statement (opcional)

        Returns:
            Dict con resultados del análisis
        """
        if not object_key:
            raise ServiceDataValidationError("object_key es requerido")

        try:
            logger.info(f"Iniciando procesamiento - Key: {object_key}")

            # 1. Preparar templates
            templates = self._prepare_classification_templates()

            # 2. Configurar clasificadores
            self._configure_classifiers(templates)

            # 3. Extraer texto (solo extracción)
            text = await self.extract_text_from_pdf(object_key)

            # 4. Guardar respaldo del texto DESPUÉS de extracción exitosa
            try:
                normalized_text = self.text_normalizer.normalize(text)
                if not normalized_text:
                    logger.warning(f"Texto normalizado invaliddo invalido: {normalized_text}")
                    raise ValueError(f"Texto normalizado invaliddo invalido: {normalized_text}")

                logger.info("texto normalizado corectamente")
                self._save_text_backup(object_key_txt_output, normalized_text)
                text = normalized_text
                logger.info("se guardo el texto normalizado corectamente")

            except Exception as e:
                logger.warning(f"No se pudo normalizar alguno caracteres del texto, error: {str(e)}")
                self._save_text_backup(object_key_txt_output, text)

            # 5. Analizar documento
            analysis_results = await self._analyze_document(text)

            # 5.1 Log de verificación rápida: ¿hay CF detectado por regex en páginas?
            pages_by_label = None
            try:
                pages_by_label = self.page_classifier.classify_pages_by_label(full_text=text)
                print("--------------------------------")
                print(f"\n[DEBUG CF] pages_by_label completo: {pages_by_label}")
                if pages_by_label and 'CF' in pages_by_label and pages_by_label['CF']:
                    print(f"\n[DEBUG CF]  CF DETECTADO en páginas: {pages_by_label['CF']}")
                    logger.info(f"[CF DETECTADO] Páginas CF: {pages_by_label['CF']}")
                else:
                    print(f"\n[DEBUG CF]  CF NO DETECTADO - pages_by_label: {pages_by_label}")
                    logger.info("[CF NO DETECTADO] No se encontraron páginas CF")
            except Exception as e:
                print(f"\n[DEBUG CF]  ERROR en verificación CF: {str(e)}")
                logger.warning(f"No se pudo ejecutar verificación de CF por páginas: {str(e)}")
            
            # 6. Agregar metadata
            analysis_results['object_key'] = object_key
            analysis_results['object_key_txt_output'] = object_key_txt_output
            analysis_results['text_length'] = len(text)
            analysis_results['pages_by_label'] = pages_by_label  
            logger.info(f"Procesamiento completado - Success: {analysis_results.get('success')}")
            return analysis_results

        except Exception as e:
            logger.error(f"Error en procesamiento - Key: {object_key}, Error: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                's3_key': object_key
            }

    def _send_sqs_message(self, results: Dict[str, Any]) -> None:
        """Envía resultados a SQS"""
        try:
            if not results.get('success'):
                logger.warning(f"No enviando mensaje SQS para procesamiento fallido")
                return

            message_data = {
                "statement_id": results.get('statement_id'),
                "type": results.get('type'),
                "periodicity_type": results.get('periodicity_type'),
                "pages": results.get('pages'),
                "pages_by_label": results.get('pages_by_label'),  # ← AGREGAR ESTA LÍNEA para incluir CF en SQS
                "object_key": results.get('object_key'),
                "object_key_txt_output": results.get('object_key_txt_output'),
                "object_key_json_output": results.get('object_key_json_output'),
                "job_id": results.get('job_id'),
                "timestamp": self._get_timestamp()
            }

            # Limpiar valores None
            message_data = {k: v for k, v in message_data.items() if v is not None}

            # Print del mensaje que se envía a la cola
            print("=" * 80)
            print(f"[DEBUG SQS] Enviando mensaje a cola_1_de_ia.fifo para statement {results.get('statement_id')}:")
            print(json.dumps(message_data, indent=2, ensure_ascii=False, default=str))
            print("=" * 80)

            logger.info(f"Enviando mensaje a SQS - Statement: {results.get('statement_id')}")

            # Enviar según tipo de cola
            if self.sqs_client.is_fifo:
                group_id = f"document-{results.get('statement_id', 'unknown')}"
                self.sqs_client.send_message(
                    message=message_data,
                    message_group_id=group_id
                )
            else:
                self.sqs_client.send_message(message=message_data)

            logger.info("Mensaje SQS enviado exitosamente")

        except Exception as e:
            logger.error(f"Error enviando mensaje SQS: {str(e)}")

    def _send_sqs_message_notes(self, results: Dict[str, Any]) -> None:
        """Envía resultados a SQS"""
        try:
            if not results.get('success'):
                logger.warning(f"No enviando mensaje SQS para procesamiento fallido")
                return

            message_data = {
                "statement_id": results.get('statement_id'),
                "type": results.get('type'),
                "periodicity_type": results.get('periodicity_type'),
                "pages": results.get('pages'),
                "s3_key": results.get('s3_key'),
                "timestamp": self._get_timestamp()
            }

            # Limpiar valores None
            message_data = {k: v for k, v in message_data.items() if v is not None}

            logger.info(f"Enviando mensaje a SQS - Statement: {results.get('statement_id')}")

            # Enviar según tipo de cola
            if self.sqs_client_notes.is_fifo:
                group_id = f"document-{results.get('statement_id', 'unknown')}"
                self.sqs_client_notes.send_message(
                    message=message_data,
                    message_group_id=group_id
                )
            else:
                self.sqs_client_notes.send_message(message=message_data)

            logger.info("Mensaje SQS enviado exitosamente")

        except Exception as e:
            logger.error(f"Error enviando mensaje SQS: {str(e)}")



    def _get_timestamp(self) -> str:
        """Obtiene timestamp actual"""
        from datetime import datetime
        return datetime.utcnow().isoformat()

    def _job_create(self, job_id: str, metadata: dict, key_object: str):
        try:
            logger.info(f"creando job con job_id: {job_id}")
            metadata = metadata or {}


            job_model = self.job_service.get_create_job_model()
            new_job = job_model(
                id=job_id,
                metadata=metadata,
                job_name=key_object,
                job_description=f"Este job extrae las cuentas de los estados financieros del documento {key_object}.",
            )
            response = self.job_service.create_job(new_job)

            if response.get('success'):
                logger.info(f"Job actualizado exitosamente: {job_id}")
            else:
                logger.error(f"Error actualizando job: {response.get('error', 'Error desconocido')}")

        except ValueError as e:
            logger.error(f"Error de formato en job_id '{job_id}': {e}")
        except Exception as e:
            logger.error(f"Error inesperado actualizando job para job_id '{job_id}': {e}")


    def _job_update(self, job_id: str,results: Dict[str, Any]=None, metadata: Dict[str,Any]=None):
        """Actualiza un job con resultados y marca como PENDING"""
        try:
            logger.info(f"Actualizando job para job_id: {job_id}")

            job_identifier = self.job_service.create_identifier(
                id=UUID(job_id),
            )

            config_data = results or {}
            job_model_update = self.job_service.get_update_job_model()
            updates = job_model_update(
                status="PENDING",
                metadata=metadata,
                config_data=config_data
            )

            response = self.job_service.update_job(job_identifier, updates)

            if response.get('success'):
                logger.info(f"Job actualizado exitosamente: {job_id}")
            else:
                logger.error(f"Error actualizando job: {response.get('error', 'Error desconocido')}")

        except ValueError as e:
            logger.error(f"Error de formato en job_id '{job_id}': {e}")
        except Exception as e:
            logger.error(f"Error inesperado actualizando job para job_id '{job_id}': {e}")

    # def _job_update_notes(self, statement_id: str):
    #     """Actualiza un job con resultados y marca como PENDING"""
    #     try:
    #         logger.info(f"Actualizando job para statement_id para notas: {statement_id}")
    #
    #         job_identifier = self.job_service.create_identifier(
    #             resource_id=UUID(statement_id),
    #             job_type="EXTRACT_NOTES"
    #         )
    #
    #         job_model_update = self.job_service.get_update_job_model()
    #         updates = job_model_update(
    #             status="PENDING"
    #         )
    #
    #         response = self.job_service.update_job(job_identifier, updates)
    #
    #         if response.get('success'):
    #             logger.info(f"Job actualizado exitosamente: {statement_id}")
    #         else:
    #             logger.error(f"Error actualizando job: {response.get('error', 'Error desconocido')}")
    #
    #     except ValueError as e:
    #         logger.error(f"Error de formato en statement_id '{statement_id}': {e}")
    #     except Exception as e:
    #         logger.error(f"Error inesperado actualizando job para statement_id '{statement_id}': {e}")

    def _job_failed(self, job_id: str, msg_error: str = "", should_retry: bool = False):
        """Marca un job como fallido"""
        try:
            logger.info(f"Marcando job como fallido: {job_id}, retry={should_retry}")

            if msg_error:
                logger.warning(f"Error reportado: {msg_error}")

            response = self.job_service.fail_job(
                id=UUID(job_id),
                error_message=msg_error,
                should_retry=should_retry
            )

            if response.get('success'):
                logger.info(f"Job marcado como fallido: {job_id}")
            else:
                logger.error(f"Error marcando job como fallido: {response.get('error', 'Error desconocido')}")

        except ValueError as e:
            logger.error(f"Error de formato en job_id '{job_id}': {e}")
        except Exception as e:
            logger.error(f"Error inesperado marcando job como fallido para job_id '{job_id}': {e}")

    # def _job_failed_notes(self, statement_id: str, msg_error: str = "", should_retry: bool = False):
    #     """Marca un job como fallido"""
    #     try:
    #         logger.info(f"Marcando job como fallido: {statement_id}, retry={should_retry}")
    #
    #         if msg_error:
    #             logger.warning(f"Error reportado: {msg_error}")
    #
    #         response = self.job_service.fail_job(
    #             resource_id=UUID(statement_id),
    #             job_type="EXTRACT_FS",
    #             error_message=msg_error,
    #             should_retry=should_retry
    #         )
    #
    #         if response.get('success'):
    #             logger.info(f"Job marcado como fallido: {statement_id}")
    #         else:
    #             logger.error(f"Error marcando job como fallido: {response.get('error', 'Error desconocido')}")
    #
    #     except ValueError as e:
    #         logger.error(f"Error de formato en statement_id '{statement_id}': {e}")
    #     except Exception as e:
    #         logger.error(f"Error inesperado marcando job como fallido para statement_id '{statement_id}': {e}")


    def _generate_job_id(self)-> Optional[str]:
        try:
            job_id = str(uuid.uuid4())
            return job_id
        except Exception as e:
            logger.error("Error al generar job_id: {e}")
            return None




    async def process_document(self, object_key: str, object_key_txt_output: str, object_key_json_output: str, job_id: Optional[str] = None, is_not_created: [bool] = False) -> bool:
            """
            Método principal para procesar documento desde trigger de S3

            Args:
                key: Clave del archivo en S3 (viene del evento S3)
                statement_id: ID del financial statement

            Returns:
                bool: True si procesamiento fue exitoso
            """
            if not object_key:
                logger.error(f"Parámetros inválidos - Key: {object_key}")
                return False



            if not job_id:
                job_id = self._generate_job_id()
                try:
                    metadata = {
                        "object_key": object_key,
                        "object_key_txt_output": object_key_txt_output,
                        "object_key_json_output": object_key_json_output
                    }
                    self._job_create(job_id,metadata,object_key)
                except Exception as e:
                    logger.error(f"error al generar job_id: {e}")

            if is_not_created:
                try:
                    metadata = {
                        "object_key": object_key,
                        "object_key_txt_output": object_key_txt_output,
                        "object_key_json_output": object_key_json_output
                    }
                    self._job_create(job_id,metadata,object_key)
                except Exception as e:
                    logger.error(f"error al generar job_id: {e}")





            try:
                metadata = {
                    "object_key": object_key,
                    "object_key_txt_output": object_key_txt_output,
                    "object_key_json_output": object_key_json_output
                }
                self._job_update(job_id, metadata=metadata)
            except Exception as e:
                logger.error(f"error al generar job_id: {e}")

            try:
                logger.info(f"=== PROCESAMIENTO S3 TRIGGER === Key: {object_key}")
                # 1. Procesar análisis del documento

                results = await self.process_document_analysis(object_key,object_key_txt_output)

                success = results.get('success', False)
                error_msg = results.get('error')
                type = results.get('type', None)
                periodicity_type = results.get('periodicity_type', None)
                pages = results.get('pages', None)
                results["object_key_json_output"] = object_key_json_output
                results["job_id"] = job_id

                if error_msg:
                    logger.warning("error la realizar el analsis del documento: ", error_msg)





                # 2. Enviar mensaje a SQS si fue exitoso
                if success:
                    self._send_sqs_message(results)




                if success:
                    self._job_update(job_id, results )
                else:
                    self._job_failed(job_id, error_msg)


                logger.info(f"=== PROCESAMIENTO COMPLETADO === Success: {success}")
                return success

            except Exception as e:
                logger.error(f"Error crítico procesando documento - Key: {object_key}, Error: {str(e)}")

                # Asegurar actualización de estado
                self._job_failed(job_id=job_id, msg_error=str(e))
                return False

    # Método de conveniencia para procesar desde evento S3
    async def process_from_s3_event(self, s3_event: Dict[str, Any]) -> bool:
        """
        Procesa documento desde evento de S3

        Args:
            s3_event: Evento completo de S3 trigger

        Returns:
            bool: True si procesamiento fue exitoso
        """
        try:
            # Extraer información del evento S3
            records = s3_event.get('Records', [])
            if not records:
                logger.error("No hay records en el evento S3")
                return False

            # Tomar el primer record
            record = records[0]
            s3_info = record.get('s3', {})
            bucket_name = s3_info.get('bucket', {}).get('name', '')
            object_key = s3_info.get('object', {}).get('key', '')

            if not object_key:
                logger.error("No se pudo extraer object_key del evento S3")
                return False

            # Extraer statement_id del nombre del archivo o metadata
            # Asumiendo que el statement_id viene en el nombre del archivo o se puede extraer
            statement_id = self._extract_statement_id_from_key(object_key)

            if not statement_id:
                logger.error(f"No se pudo extraer statement_id de: {object_key}")
                return False

            logger.info(
                f"Procesando desde evento S3 - Bucket: {bucket_name}, Key: {object_key}, Statement: {statement_id}")

            return await self.process_document(object_key, statement_id)

        except Exception as e:
            logger.error(f"Error procesando evento S3: {str(e)}")
            return False

    def _extract_statement_id_from_key(self, object_key: str) -> Optional[str]:
        """
        Extrae statement_id (UUID) del nombre del archivo
        Ejemplos:
        - "documents/statement_550e8400-e29b-41d4-a716-446655440000.pdf" -> "550e8400-e29b-41d4-a716-446655440000"
        - "financial/550e8400-e29b-41d4-a716-446655440000.pdf" -> "550e8400-e29b-41d4-a716-446655440000"
        """
        try:
            import re

            # Patrón para UUID v4 (más común)
            uuid_pattern = r'([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})'
            match = re.search(uuid_pattern, object_key, re.IGNORECASE)
            if match:
                return match.group(1)

            # Patrón para UUID sin guiones
            uuid_no_dash_pattern = r'([0-9a-f]{32})'
            match = re.search(uuid_no_dash_pattern, object_key, re.IGNORECASE)
            if match:
                # Convertir a formato con guiones
                uuid_str = match.group(1)
                formatted_uuid = f"{uuid_str[:8]}-{uuid_str[8:12]}-{uuid_str[12:16]}-{uuid_str[16:20]}-{uuid_str[20:]}"
                return formatted_uuid

            # Fallback: buscar cualquier string alfanumérico largo (posible UUID custom)
            fallback_pattern = r'/([a-zA-Z0-9-]{32,36})\.'
            match = re.search(fallback_pattern, object_key)
            if match:
                return match.group(1)

            logger.warning(f"No se pudo extraer UUID del object_key: {object_key}")
            return None

        except Exception as e:
            logger.error(f"Error extrayendo statement_id de {object_key}: {str(e)}")
            return None