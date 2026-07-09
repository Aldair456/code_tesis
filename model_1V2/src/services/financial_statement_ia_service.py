from typing import Dict, List, Optional, Any, Tuple
from uuid import UUID
import logging
import json
import time
import asyncio
from typing import Dict, List, Optional, Any

# Importaciones de clientes y repositorios (model_1V2: sin depender de models.model_1)
from models.model_1V2.src.repositories.financial_accounts_repository import AccountRepository

from common_aws_client_async.s3_client import S3Client
from common_ia_clients.ia_client import IAInvoker, prompt_ai
from common_aws_client_async.textract_v2 import TextractClient
from common_aws_clients.sqs_client import SQSClient
from common_job.job import JobService

# Importaciones de utilidades locales
from models.model_1V2.src.utils.helper_functions import (
    extract_delimited_text,
    textract_tables_to_text,
    find_page_content
)
from models.model_1V2.src.utils.promts import (
    promt_anuales_bs_and_pl,
    promt_anuales_years,
    promt_trimestral_bs_and_pl,
    promt_trimestral_year_bs,
    promt_trimestral_year_pl,
    promt_extract_bs,
    promt_extract_pl,
    promt_extract_cf,
    promt_extract_cf_main,
    promt_extract_cf_details
)

logger = logging.getLogger(__name__)


class FinancialIaServiceError(Exception):
    """Excepción personalizada para errores del servicio financiero"""

    def __init__(self, message: str, error_code: Optional[str] = None, original_error: Optional[Exception] = None):
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.original_error = original_error




class FinancialStatementIaService:
    """Servicio para procesamiento de estados financieros con IA"""

    # Configuración de prompts
    PROMPTS_CONFIG = {
        "anual": {"all": promt_anuales_bs_and_pl},
        "trimestral": {"all": promt_trimestral_bs_and_pl}
    }

    TRIMESTRAL_PROMPTS = {
        'bs': promt_trimestral_year_bs,
        'pl': promt_trimestral_year_pl
    }

    # Configuración de timeouts y reintentos
    DEFAULT_TIMEOUT = 30  # segundos
    MAX_RETRIES = 3
    RETRY_DELAY = 2  # segundos

    def __init__(self,
                 account_repository: AccountRepository,
                 s3_client: S3Client,
                 textract_client: TextractClient,
                 sqs_client: SQSClient,
                 ia_client: IAInvoker,
                 job_service: JobService
                 ):
        """Inicializa el servicio con las dependencias necesarias."""
        self.account_repository = account_repository
        self.s3_client = s3_client
        self.textract_client = textract_client
        self.sqs_client = sqs_client
        self.ia_client = ia_client
        self.job_service = job_service



    # ==========================================
    # MÉTODOS DE EXTRACCIÓN DE TEXTO
    # ==========================================

    async def extract_text_from_financial_statement(self, object_key_txt: str) -> str:
        """
        Extrae texto de un archivo de estado financiero almacenado en S3.

        :param financial_statement_id: ID del estado financiero.
        :return: Contenido del archivo como texto.
        :raises FinancialServiceError: Si hay error al obtener el archivo.
        """

        try:
            logger.info(f"Obteniendo archivo: {object_key_txt}")
            texto_bytes = await self.s3_client.get_file(object_key_txt)
            return texto_bytes.decode("utf-8")

        except Exception as e:
            raise FinancialIaServiceError(
                f"Error al obtener archivo {object_key_txt}: {e}",
                "FILE_EXTRACTION_ERROR",
                e
            )

    async def extract_text_from_pdf(self, bucket_name: str, object_key: str, object_key_txt: str) -> str:
        """
        Extrae texto completo de un PDF usando Textract y lo guarda en S3.

        :param bucket_name: Nombre del bucket.
        :param object_key: Clave del objeto.
        :param statement_id: ID del estado financiero.
        :return: Texto extraído.
        """
        try:
            logger.info(f"Extrayendo texto de PDF: {object_key}")

            # Procesar PDF con Textract
            text_content = await self._process_pdf_with_textract(bucket_name, object_key)

            # Guardar texto extraído
            await self._save_extracted_text(object_key_txt, text_content)

            return text_content

        except Exception as e:
            raise FinancialIaServiceError(
                f"Error al extraer texto de PDF: {e}",
                "PDF_TEXT_EXTRACTION_ERROR",
                e
            )

    async def _process_pdf_with_textract(self, bucket_name: str, object_key: str) -> str:
        """Procesa PDF de s3 completo con Textract"""
        try:
            async with self.textract_client as textract:
                # Analizar con Textract
                job_id = await textract.start_and_wait_for_result_detection(bucket_name=bucket_name, object_key=object_key)
                logger.info(f"jb_id de la deteccion del texto obtenido: {job_id}")
                # Extraer texto

                text = await textract.process_textract_result_detection(job_id=job_id)
                logger.info("texto de la deteccion obtenido correctamnete")
                return text

        except Exception as e:
            raise FinancialIaServiceError(
                f"Error procesando PDF con Textract: {e}",
                "TEXTRACT_PROCESSING_ERROR",
                e
            )

    async def _save_extracted_text(self, object_key_txt: str, text_content: str) -> None:
        """Guarda el texto extraído en S3"""
        try:
            await self.s3_client.upload_text_file(object_key_txt, text_content)
            logger.info(f"Texto guardado en S3: {object_key_txt}")
        except Exception as e:
            logger.warning(f"Error al guardar texto en S3: {e}")
            # No propagamos el error ya que es opcional

    # ==========================================
    # MÉTODOS DE BÚSQUEDA CON IA
    # ==========================================

    async def find_financial_statements_with_ai(self,
                                                text_content: str,
                                                statement_type: str,
                                                periodicity_type: str) -> Dict[str, List[int]]:
        """
        Encuentra páginas de estados financieros usando IA.

        :param text_content: Contenido del documento.
        :param statement_type: Tipo de estado financiero.
        :param periodicity_type: Periodicidad del estado.
        :return: Diccionario con páginas de BS y PL.
        """
        try:
            # Validar entrada
            if not text_content.strip():
                raise ValueError("El contenido del texto no puede estar vacío")

            # Obtener función de prompt
            prompt_func = self.PROMPTS_CONFIG.get(periodicity_type, {}).get('all')
            if not prompt_func:
                raise ValueError(f"No hay prompt configurado para {periodicity_type}")

            # Generar prompt y consultar IA
            prompt = prompt_func(text_content)
            result_ia = prompt_ai(
                prompt=prompt,
                instance_ia=self.ia_client,
                source="find_financial_statements"
            )

            # Procesar resultado
            return self._parse_json_result(result_ia, '{', '}')

        except Exception as e:
            raise FinancialIaServiceError(
                f"Error al buscar estados financieros: {e}",
                "AI_SEARCH_ERROR",
                e
            )

    async def find_years_annual(self, text_content: str, data_eeff: Dict[str, List[int]]) -> Dict[str, List[int]]:
        """
        Encuentra años en estados financieros anuales.

        :param text_content: Contenido del texto.
        :param data_eeff: Datos de páginas por tipo.
        :return: Años extraídos por tipo.
        """
        if not isinstance(data_eeff, dict):
            raise ValueError("data_eeff debe ser un diccionario")

        try:
            result = {}
            for statement_type, pages in data_eeff.items():
                if pages:
                    first_page = int(pages[0])
                    logger.info(f"Buscando años para {statement_type} en página {first_page}")

                    years = await self._extract_years_annual(text_content, first_page)
                    result[statement_type] = years

                    # Pausa entre llamadas para evitar rate limiting
                    await self._sleep(1)

            return result

        except Exception as e:
            raise FinancialIaServiceError(
                f"Error al encontrar años anuales: {e}",
                "ANNUAL_YEARS_EXTRACTION_ERROR",
                e
            )

    async def _extract_years_annual(self, text_content: str, page_id: int) -> List[int]:
        """Extrae años de una página específica"""
        try:
            # Obtener contenido de la página
            page_content = await self._find_page_content(text_content, page_id)

            # Generar prompt y consultar IA
            prompt = promt_anuales_years(page_content)
            result = prompt_ai(
                prompt=prompt,
                instance_ia=self.ia_client,
                source="extract_years_annual"
            )

            return self._parse_json_result(result, '[', ']')

        except Exception as e:
            raise FinancialIaServiceError(
                f"Error al extraer años de página {page_id}: {e}",
                "PAGE_YEARS_EXTRACTION_ERROR",
                e
            )

    async def find_years_quarterly(self, tables_text: Dict[str, str]) -> Dict[str, List[Dict[str, Any]]]:
        """
        Encuentra años y trimestres en estados financieros trimestrales.

        :param tables_text: Texto de tablas por tipo.
        :return: Años y trimestres por tipo.
        """
        if not isinstance(tables_text, dict):
            raise ValueError("tables_text debe ser un diccionario")

        try:
            result = {}
            for statement_type, text in tables_text.items():
                if text:
                    logger.info(f"Extrayendo años para {statement_type}")
                    years_data = await self._extract_years_quarterly(text, statement_type)
                    result[statement_type] = years_data

            return result

        except Exception as e:
            raise FinancialIaServiceError(
                f"Error al encontrar años trimestrales: {e}",
                "QUARTERLY_YEARS_EXTRACTION_ERROR",
                e
            )

    async def _extract_years_quarterly(self, text_tables: str, statement_type: str) -> List[Dict[str, Any]]:
        """Extrae años y trimestres de tablas"""
        try:
            prompt_func = self.TRIMESTRAL_PROMPTS.get(statement_type)
            if not prompt_func:
                raise ValueError(f"No hay prompt para tipo {statement_type}")

            prompt = prompt_func(text_tables)
            result = prompt_ai(
                prompt=prompt,
                instance_ia=self.ia_client,
                source="extract_years_quarterly"
            )

            return self._parse_json_result(result, '[', ']')

        except Exception as e:
            raise FinancialIaServiceError(
                f"Error al extraer años trimestrales: {e}",
                "QUARTERLY_YEARS_PARSING_ERROR",
                e
            )

    # ==========================================
    # MÉTODOS DE EXTRACCIÓN DE TABLAS
    # ==========================================

    async def extract_tables_by_type(self, pages_by_eeff: Dict[str, List[int]], key_object: str) -> Dict[str, str]:
        """
        Extrae tablas por tipo de estado financiero.

        :param pages_by_eeff: Páginas por tipo de estado financiero.
        :param key_object: Clave del objeto en S3.
        :return: Diccionario con texto de tablas por tipo.
        """
        if not isinstance(pages_by_eeff, dict):
            raise ValueError("pages_by_eeff debe ser un diccionario")

        try:
            result = {}
            for statement_type, pages in pages_by_eeff.items():
                if pages:
                    logger.info(f"Extrayendo tablas para {statement_type}")
                    tables_text = await self._extract_tables_from_pages(key_object, pages)
                    result[statement_type] = tables_text

            return result

        except Exception as e:
            raise FinancialIaServiceError(
                f"Error al extraer tablas: {e}",
                "TABLE_EXTRACTION_ERROR",
                e
            )

    # async def _extract_tables_from_pages(self, key_object: str, pages: List[int]) -> str:
    #     """Extrae tablas de páginas específicas"""
    #     try:
    #         # Extraer páginas del PDF
    #         list_page_bytes = await self.s3_client.extract_pdf_pages_list(
    #             file_name=key_object,
    #             page_numbers=pages
    #         )
    #
    #         all_tables = []
    #         for page_index, page_bytes in enumerate(list_page_bytes, start=1):
    #             logger.info(f"Procesando página {page_index}/{len(list_page_bytes)}")
    #
    #             # Analizar con Textract
    #             async with self.textract_client as textract:
    #                 result = await textract.analyze_document_bytes(
    #                     document_bytes=page_bytes,
    #                     feature_types=['TABLES', 'FORMS']
    #                 )
    #
    #                 # Extraer tablas
    #                 tables = textract.extract_tables_from_textract_response(result)
    #                 all_tables.extend(tables)
    #
    #             # Pausa entre llamadas
    #             if page_index < len(list_page_bytes):
    #                 await self._sleep(2)
    #
    #         return textract_tables_to_text(all_tables)
    #
    #     except Exception as e:
    #         raise FinancialIaServiceError(
    #             f"Error al extraer tablas de páginas: {e}",
    #             "PAGES_TABLE_EXTRACTION_ERROR",
    #             e
    #         )

    async def _extract_tables_from_pages(self, key_object: str, pages: List[int]) -> str:
        """Extrae tablas adaptado para PDF y JPG"""
        try:
            # 1. Detectar tipo de archivo
            file_extension = key_object.lower().split('.')[-1]

            if file_extension in ['jpg', 'jpeg', 'png', 'tiff']:
                # Para imágenes: procesar archivo completo
                logger.info("Procesando archivo de imagen único")
                file_bytes = await self.s3_client.get_file(key_object)

                async with self.textract_client as textract:
                    result = await textract.analyze_document_bytes(
                        document_bytes=file_bytes,
                        feature_types=['TABLES', 'FORMS']
                    )
                    tables = textract.extract_tables_from_textract_response(result)
                    return textract_tables_to_text(tables)

            else:
                # Para PDFs: extraer páginas específicas (código original)
                logger.info(f"Procesando PDF - {len(pages)} páginas")
                list_page_bytes = await self.s3_client.extract_pdf_pages_list(
                    file_name=key_object,
                    page_numbers=pages
                )

                all_tables = []
                for page_index, page_bytes in enumerate(list_page_bytes, start=1):
                    async with self.textract_client as textract:
                        result = await textract.analyze_document_bytes(
                            document_bytes=page_bytes,
                            feature_types=['TABLES', 'FORMS']
                        )
                        tables = textract.extract_tables_from_textract_response(result)
                        all_tables.extend(tables)

                    if page_index < len(list_page_bytes):
                        await self._sleep(2)

                return textract_tables_to_text(all_tables)

        except Exception as e:
            raise FinancialIaServiceError(
                f"Error al extraer tablas: {e}",
                "PAGES_TABLE_EXTRACTION_ERROR",
                e
            )

    # ==========================================
    # MÉTODOS DE PROCESAMIENTO PRINCIPAL
    # ==========================================

    async def process_annual_financial_statement(self,
                                                 bucket_name: str,
                                                 object_key: str,
                                                 object_key_txt: str,
                                                 statement_type: str = "all") -> Dict[str, Any]:
        """
        Procesa un estado financiero anual completo.

        :param bucket_name: Nombre del bucket.
        :param object_key: Clave del objeto.
        :param statement_id: ID del estado.
        :param statement_type: Tipo de estado.
        :return: Resultado completo del procesamiento.
        """
        try:
            logger.info(f"Iniciando procesamiento anual - Statement ID: {object_key_txt}")

            # 1. Obtener o extraer texto
            text_content = await self._get_or_extract_text(
                bucket_name, object_key, object_key_txt
            )

            # 2. Encontrar páginas
            pages_data = await self.find_financial_statements_with_ai(
                text_content, statement_type, "anual"
            )

            # 3. Extraer tablas
            tables_data = await self.extract_tables_by_type(pages_data, object_key)

            # 4. Encontrar años
            years_data = await self.find_years_annual(text_content, pages_data)

            result = {
                "periodicity_type": "anual",
                "statement_type": statement_type,
                "pages": pages_data,
                "tables": tables_data,
                "years": years_data,
                "processing_metadata": {
                    "processed_at": time.time(),
                    "bucket_name": bucket_name,
                    "object_key": object_key,
                    "object_key_txt": object_key_txt
                }
            }

            logger.info(f"Procesamiento anual completado - Statement ID: {object_key}")
            return result

        except Exception as e:
            raise FinancialIaServiceError(
                f"Error en procesamiento anual: {e}",
                "ANNUAL_PROCESSING_ERROR",
                e
            )

    async def process_quarterly_financial_statement(self,
                                                    bucket_name: str,
                                                    object_key: str,
                                                    object_key_txt: str,
                                                    statement_type: str = "all") -> Dict[str, Any]:
        """
        Procesa un estado financiero trimestral completo.

        :param bucket_name: Nombre del bucket.
        :param object_key: Clave del objeto.
        :param object_key_txt: ID del estado.
        :param statement_type: Tipo de estado.
        :return: Resultado completo del procesamiento.
        """
        try:
            logger.info(f"Iniciando procesamiento trimestral - Statement ID: {object_key}")

            # 1. Obtener o extraer texto
            text_content = await self._get_or_extract_text(
                bucket_name, object_key, object_key_txt
            )

            # 2. Encontrar páginas
            pages_data = await self.find_financial_statements_with_ai(
                text_content, statement_type, "trimestral"
            )

            # 3. Extraer tablas
            tables_data = await self.extract_tables_by_type(pages_data, object_key)

            # 4. Encontrar años y trimestres
            years_data = await self.find_years_quarterly(tables_data)

            result = {
                "periodicity_type": "trimestral",
                "statement_type": statement_type,
                "pages": pages_data,
                "tables": tables_data,
                "years": years_data,
                "processing_metadata": {
                    "processed_at": time.time(),
                    "bucket_name": bucket_name,
                    "object_key": object_key,
                    "object_key_txt": object_key_txt
                }
            }

            logger.info(f"Procesamiento trimestral completado - Statement ID: {object_key_txt}")
            return result

        except Exception as e:
            raise FinancialIaServiceError(
                f"Error en procesamiento trimestral: {e}",
                "QUARTERLY_PROCESSING_ERROR",
                e
            )

    # ==========================================
    # MÉTODOS DE REPOSITORIO Y PERSISTENCIA
    # ==========================================

    async def save_processing_results(self, results: Dict[str, Any]) -> bool:
        """Guarda los resultados del procesamiento en la base de datos"""
        try:
            # Implementar lógica de guardado
            pass
        except Exception as e:
            logger.error(f"Error guardando resultados: {e}")
            return False

    async def get_account_info(self, account_id: str) -> Optional[Dict[str, Any]]:
        """Obtiene información de la cuenta"""
        try:
            return await self.account_repository.find_by_id(account_id)
        except Exception as e:
            logger.error(f"Error obteniendo información de cuenta: {e}")
            return None

    async def update_financial_statement_status(self, statement_id: str, status: str) -> bool:
        """Actualiza el estado del procesamiento"""
        try:
            updates = {
                "status": status
            }
            return await self.financial_statement_repository.update(id=statement_id, data=updates)
        except Exception as e:
            logger.error(f"Error actualizando estado: {e}")
            return False

    # ==========================================
    # MÉTODOS AUXILIARES PRIVADOS
    # ==========================================

    async def _get_or_extract_text(self, bucket_name: str, object_key: str, object_key_txt: str) -> str:
        """Intenta obtener texto existente o lo extrae del PDF"""
        try:
            # Primero intentar obtener texto ya extraído
            return await self.extract_text_from_financial_statement(object_key_txt)

        except Exception as e:
            logger.warning("No se encontro el .txt en s3 ")
            logger.info("reintentamos a extraerlo ....")
            return await self.extract_text_from_pdf(bucket_name, object_key, object_key_txt)


    def _parse_json_result(self, result_text: str, start_char: str, end_char: str) -> Any:
        """Parsea resultado JSON de la IA"""
        try:
            json_text = extract_delimited_text(
                text=result_text,
                char_start=start_char,
                char_end=end_char
            )
            return json.loads(json_text)

        except (json.JSONDecodeError, ValueError) as e:
            raise FinancialIaServiceError(
                f"Error al parsear JSON: {e}",
                "JSON_PARSING_ERROR",
                e
            )

    async def _find_page_content(self, text_content: str, page_id: int) -> str:
        """Encuentra el contenido de una página específica"""
        try:
            return await find_page_content(text_content, page_id)
        except Exception as e:
            raise FinancialIaServiceError(
                f"Error encontrando contenido de página {page_id}: {e}",
                "PAGE_CONTENT_ERROR",
                e
            )

    async def _sleep(self, seconds: int) -> None:
        """Pausa asíncrona para evitar rate limiting"""
        import asyncio
        await asyncio.sleep(seconds)

    def _validate_pages_data(self, pages_data: Dict[str, List[int]]) -> bool:
        """Valida que los datos de páginas sean correctos"""
        if not isinstance(pages_data, dict):
            return False

        for statement_type, pages in pages_data.items():
            if not isinstance(pages, list):
                return False
            if pages and not all(isinstance(p, int) and p > 0 for p in pages):
                return False

        return True

    def _validate_statement_type(self, statement_type: str) -> bool:
        """Valida que el tipo de estado financiero sea válido"""
        valid_types = ["all", "bs", "pl"]
        return statement_type.lower() in valid_types



    def _validate_periodicity_type(self, periodicity_type: str) -> bool:
        """Valida que el tipo de periodicidad sea válido"""
        valid_types = ["anual", "trimestral"]
        return periodicity_type in valid_types



    async def get_tables_and_years_by_file_statement(self, object_key: str,
                                                     object_key_txt: str,
                                                     periodicity_type: str,
                                                     statement_type: str = "all"):
        # Validar parámetros requeridos
        if not all([object_key, object_key_txt, periodicity_type, statement_type]):
            error_msg = f"Parámetros faltantes - object_key: {bool(object_key)}, statement_id: {bool(object_key_txt)}, periodicity_type: {bool(periodicity_type)}"
            logger.error(error_msg)
            raise FinancialIaServiceError(error_msg)

        # Normalizar statement_type
        statement_type = "all" if statement_type.lower() == "pb" else statement_type.lower()

        # Validar tipos
        if not self._validate_periodicity_type(periodicity_type):
            error_msg = f"Tipo de periodicidad inválido: {periodicity_type}"
            logger.error(error_msg)
            raise FinancialIaServiceError(error_msg)

        if not self._validate_statement_type(statement_type):
            error_msg = f"Tipo de estado financiero inválido: {statement_type}"
            logger.error(error_msg)
            raise FinancialIaServiceError(error_msg)

        try:
            bucket_name = self.s3_client.bucket_name
            logger.info(f"Procesando object: {object_key}, periodicidad: {periodicity_type}")

            if periodicity_type == "anual":
                data_result = await self.process_annual_financial_statement(
                    bucket_name=bucket_name,
                    object_key=object_key,
                    object_key_txt=object_key_txt,
                    statement_type=statement_type
                )
            else:
                data_result = await self.process_quarterly_financial_statement(
                    bucket_name=bucket_name,
                    object_key=object_key,
                    object_key_txt=object_key_txt,
                    statement_type=statement_type
                )

            logger.info(f"Statement {object_key} procesado exitosamente")
            return data_result

        except Exception as e:
            error_msg = f"Error procesando statement {object_key}: {str(e)}"
            logger.error(error_msg)
            raise FinancialIaServiceError(error_msg) from e

    def _job_run(self, job_id: str):
        """Inicia un job marcándolo como RUNNING"""
        try:
            logger.info(f"Iniciando job para job_id: {job_id}")

            response = self.job_service.start_job(UUID(job_id), "EXTRACT_FS")

            if response.get('success'):
                logger.info(f"Job iniciado exitosamente: {job_id}")
            else:
                logger.error(f"Error iniciando job: {response.get('error', 'Error desconocido')}")

        except ValueError as e:
            logger.error(f"Error de formato en job_id '{job_id}': {e}")
        except Exception as e:
            logger.error(f"Error inesperado iniciando job para job_id '{job_id}': {e}")

    def _job_retry(self, job_id: str, current_retries: int = 0):
        """Incrementa el contador de reintentos del job"""
        try:
            logger.info(f"Incrementando reintento para job_id: {job_id}, intento: {current_retries + 1}")

            response = self.job_service.increment_retry(
                UUID(job_id),
                "EXTRACT_FS",
                current_retry_count=current_retries,
            )

            if response.get('success'):
                logger.info(f"Reintento incrementado exitosamente: {job_id}")
            else:
                logger.error(f"Error incrementando reintento: {response.get('error', 'Error desconocido')}")

        except ValueError as e:
            logger.error(f"Error de formato en statement_id '{job_id}': {e}")
        except Exception as e:
            logger.error(f"Error inesperado incrementando reintento para job_id '{job_id}': {e}")

    def _job_failed(self, job_id: str, msg_error: str = "", should_retry: bool = False):
        """Marca un job como fallido"""
        try:
            logger.info(f"Marcando job como fallido: {job_id}, retry={should_retry}")

            if msg_error:
                logger.warning(f"Error reportado: {msg_error}")

            response = self.job_service.fail_job(
                UUID(job_id),
                "EXTRACT_FS",
                error_message=msg_error,
                should_retry=should_retry,
            )

            if response.get('success'):
                logger.info(f"Job marcado como fallido: {job_id}")
            else:
                logger.error(f"Error marcando job como fallido: {response.get('error', 'Error desconocido')}")

        except ValueError as e:
            logger.error(f"Error de formato en job_id '{job_id}': {e}")
        except Exception as e:
            logger.error(f"Error inesperado marcando job como fallido para statement_id '{job_id}': {e}")

    def _job_complete(self, job_id: str, result_data: Dict[str, Any] = None):
        """Marca un job como completado exitosamente"""
        try:
            logger.info(f"Completando job para statement_id: {job_id}")

            response = self.job_service.complete_job(
                UUID(job_id), "EXTRACT_FS", result_data=result_data
            )

            if response.get('success'):
                logger.info(f"Job completado exitosamente: {job_id}")
            else:
                logger.error(f"Error completando job: {response.get('error', 'Error desconocido')}")

        except ValueError as e:
            logger.error(f"Error de formato en job_id '{job_id}': {e}")
        except Exception as e:
            logger.error(f"Error inesperado completando job para job_id '{job_id}': {e}")

    async def process_extract_data_file_statement(self, object_key: str,
                                                  object_key_txt: str,
                                                  periodicity_type: str,
                                                  object_key_json_output: str,
                                                  pages_by_label: Optional[Dict[str, List[int]]] = None,
                                                  statement_type: str = "all", job_id: Optional[str]=None):

        # Validar parámetros
        if not all([object_key, object_key_txt, periodicity_type, statement_type, object_key_json_output]):
            error_msg = f"Parámetros requeridos faltantes"
            logger.error(error_msg)
            #comunica al job del fallo
            # self._job_failed(statement_id, error_msg)
            raise FinancialIaServiceError(error_msg)

        #empieza a correr el job
        self._job_run(job_id)

        # Procesar con reintentos
        last_exception = None
        for attempt in range(self.MAX_RETRIES):
            try:
                logger.info(f"Procesando statement {object_key}, intento {attempt + 1}/{self.MAX_RETRIES}")

                # Extraer datos
                result = await self.get_tables_and_years_by_file_statement(
                    object_key=object_key,
                    object_key_txt=object_key_txt,
                    periodicity_type=periodicity_type,
                    statement_type=statement_type
                )
                if pages_by_label and 'CF' in pages_by_label and pages_by_label['CF']:
                    cf_pages = pages_by_label['CF']
                    logger.info(f"CF DETECTADO en páginas: {cf_pages}")
                    # Extraer tablas de CF
                    try:
                        cf_tables = await self.extract_tables_by_type(
                            pages_by_eeff={'CF': cf_pages},
                            key_object=object_key
                        )

                        # Agregar CF a las tablas del resultado
                        if 'tables' in result and result['tables']:
                            result['tables'].update(cf_tables)
                        else:
                            result['tables'] = cf_tables

                        # Agregar páginas CF al resultado
                        if 'pages' in result and isinstance(result['pages'], dict):
                            result['pages']['CF'] = cf_pages

                        logger.info(f"CF procesado exitosamente")

                    except Exception as e:
                        logger.error(f"Error al procesar CF: {e}")
                        # No fallar el proceso completo si CF falla

                try:
                    logger.info("insertando dato de output de guardado de json")
                    result["object_key_json_output"] = object_key_json_output
                    result["type"] = statement_type
                    result["periodicity"] = periodicity_type
                    result["job_id"] = job_id
                except Exception as e:
                    logger.warning(f"fallo al agregar data de guardado de json: {e}")

                # Enviar a SQS
                try:
                    # Print del mensaje que se envía a cola_2_de_ia.fifo
                    print("=" * 80)
                    print(f"[DEBUG SQS] Enviando mensaje a cola_2_de_ia.fifo para statement {object_key}:")
                    print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
                    print("=" * 80)

                    if self.sqs_client.is_fifo:
                        self.sqs_client.send_message(
                            message=result,
                            message_group_id="financial_statements"
                        )
                    else:
                        self.sqs_client.send_message(message=result)

                    logger.info(f"Mensaje enviado a SQS para statement {object_key}")

                except Exception as sqs_error:
                    logger.warning(f"Error enviando a SQS: {sqs_error}")
                    # Fallback a S3
                    raise sqs_error

                # Éxito
                # await self._safe_update_status(statement_id, "COMPLETED")
                logger.info(f"Statement {object_key} procesado exitosamente")
                return result

            except Exception as e:
                last_exception = e
                logger.warning(f"Intento {attempt + 1} falló: {str(e)}")

                if attempt < self.MAX_RETRIES - 1:
                    wait_time = self.RETRY_DELAY ** attempt
                    logger.info(f"Reintentando en {wait_time} segundos...")
                    #comunica al job de los reintentos
                    self._job_retry(job_id, attempt)
                    await asyncio.sleep(wait_time)

        # Todos los reintentos fallaron
        error_msg = f"Falló después de {self.MAX_RETRIES} intentos: {str(last_exception)}"
        logger.error(error_msg)
        # await self._safe_update_status(statement_id, "FAILED")
        #comunica al job del fallo
        self._job_failed(job_id, error_msg)
        raise FinancialIaServiceError(error_msg) from last_exception

    async def _safe_update_status(self, statement_id: str, status: str):
        """Helper para actualizar estado sin fallar el proceso principal."""
        if not statement_id:
            return

        try:
            updates = {"status": status}

            self.financial_statement_repository.update(statement_id, updates)
            logger.info(f"Statement {statement_id} actualizado a: {status}")
        except Exception as e:
            logger.error(f"Error actualizando statement {statement_id}: {str(e)}")

    def _fetch_accounts_by_type(self, account_type: str) -> List[Dict]:
        """
        Obtiene las cuentas desde el repositorio filtradas por tipo.
        """
        if not account_type or not isinstance(account_type, str):
            logger.error("El parámetro 'account_type' es inválido o vacío.")
            raise ValueError("Debe especificar un tipo de cuenta válido.")

        logger.debug(f"Consultando cuentas con tipo: {account_type}")
        accounts = self.account_repository.find_all_by_filters(type=account_type)

        if not accounts:
            logger.warning(f"No se encontraron cuentas para el tipo '{account_type}'.")

        return [
            {
                "name": acc.name,
                "display_name": acc.display_name,
                "type": acc.type,
                "tags": acc.tags,
                "valueType": acc.value_type,
                "priority": acc.priority
            }
            for acc in accounts
        ]

    def _generate_accounts_with_ai(
            self,
            account_type: str,
            tables_text: str,
            year_list: list,
            prompt_function,
            normalize_function=None
    ) -> List[Dict]:
        """
        Lógica genérica para generar cuentas usando IA.
        """
        try:
            logger.info(f"Iniciando generación de cuentas para tipo '{account_type}'.")

            accounts_metadata = self._fetch_accounts_by_type(account_type)

            prompt = prompt_function(
                table_text=tables_text,
                years=year_list,
                list_account=accounts_metadata
            )

            result_ia = prompt_ai(
                prompt=prompt,
                instance_ia=self.ia_client,
                source="generate_json_eeff"
            )

            text_json = extract_delimited_text(result_ia, char_start='[', char_end=']')
            json_data = json.loads(text_json)

            if normalize_function:
                json_data = normalize_function(json_data=json_data, cuentas_expenses=accounts_metadata)

            logger.info(f"Generación para '{account_type}' completada correctamente.")
            return json_data

        except Exception as e:
            logger.exception(f"Error al generar cuentas para tipo '{account_type}': {e}")
            raise

    def generate_accounts_bs(self, tables_text: str, year_list: list) -> List[Dict]:
        """
        Genera las cuentas de Balance General (BS) usando IA.
        """
        return self._generate_accounts_with_ai(
            account_type="BS",
            tables_text=tables_text,
            year_list=year_list,
            prompt_function=promt_extract_bs
        )

    def generate_accounts_pl(self, tables_text: str, year_list: list) -> List[Dict]:
        """
        Genera las cuentas de Pérdidas y Ganancias (PL) usando IA.
        """
        return self._generate_accounts_with_ai(
            account_type="PL",
            tables_text=tables_text,
            year_list=year_list,
            prompt_function=promt_extract_pl,
            normalize_function=self._normalize_accounts_pl
        )

    def generate_accounts_cf(self, tables_text: str, year_list: list) -> List[Dict]:
        """
        Genera las cuentas de Flujo de Efectivo (CF) usando IA.
        """
        return self._generate_accounts_with_ai(
            account_type="FC",
            tables_text=tables_text,
            year_list=year_list,
            prompt_function=promt_extract_cf
        )

    def generate_accounts_cf_main(self, tables_text: str, year_list: list) -> List[Dict]:
        """
        Genera SOLO los 3 flujos principales de Flujo de Efectivo (CF) usando IA.
        """
        return self._generate_accounts_with_ai(
            account_type="FC",
            tables_text=tables_text,
            year_list=year_list,
            prompt_function=promt_extract_cf_main
        )

    def generate_accounts_cf_details(self, tables_text: str, year_list: list) -> List[Dict]:
        """
        Genera SOLO las partidas adicionales (details) de Flujo de Efectivo (CF) usando IA.
        """
        return self._generate_accounts_with_ai(
            account_type="FC",
            tables_text=tables_text,
            year_list=year_list,
            prompt_function=promt_extract_cf_details
        )

    def _normalize_accounts_pl(self, json_data: List[Dict], cuentas_expenses: List[Dict]) -> List[Dict]:
        """
        Enriquecer ítems con metadata y normalizar valores negativos para cuentas tipo 'expense'.
        """
        cuentas_expense_dict = {c["name"]: c for c in cuentas_expenses}

        for item in json_data:
            nombre_cuenta = item.get("name")
            valor = item.get("value")
            cuenta_ref = cuentas_expense_dict.get(nombre_cuenta)

            if cuenta_ref:
                item.update({
                    "tags": cuenta_ref.get("tags", []),
                    "value_type": cuenta_ref.get("value_type", "positive"),
                    "priority": cuenta_ref.get("priority", 0),
                    "display_name": cuenta_ref.get("display_name", nombre_cuenta)
                })

                if "expense" in item["tags"] and isinstance(valor, (int, float)):
                    item["value"] = -abs(valor)
                    for detail in item.get("details", []):
                        if isinstance(detail.get("value"), (int, float)):
                            detail["value"] = abs(detail["value"])
            else:
                item.update({
                    "tags": [],
                    "valueType": "unknown",
                    "priority": 0,
                    "displayName": nombre_cuenta
                })

        return json_data

    def generate_accounts_with_retries(
            self, generator_method, tables_text: str, year_list: list, job_id: Optional[str] = None
    ) -> List[Dict]:
        """
        Ejecuta un método de generación con reintentos y backoff exponencial.
        """
        attempt = 0
        while attempt < self.MAX_RETRIES:
            try:
                return generator_method(tables_text, year_list)
            except Exception as e:
                attempt += 1
                if attempt >= self.MAX_RETRIES:
                    logger.error(f"Máximo de reintentos alcanzado para {generator_method.__name__}.")
                    msg_errr = f"Error al procesar con las tablas extraidas con el metodo {generator_method.__name__}"
                    #aca comunicamos al job del fallo
                    self._job_failed(job_id, msg_error=msg_errr)
                    raise
                delay = self.RETRY_DELAY * (2 ** (attempt - 1))
                logger.warning(f"Fallo en intento {attempt} para {generator_method.__name__}: {e}. "
                               f"Reintentando en {delay} segundos...")

                # aca counicamos al job de los reintentos
                self._job_retry(job_id, attempt-1)
                time.sleep(delay)


    def generate_accounts_bs_with_retries(self, tables_text: str, year_list: list, job_id: Optional[str] = None) -> List[Dict]:
        return self.generate_accounts_with_retries(self.generate_accounts_bs, tables_text, year_list, job_id)

    def generate_accounts_pl_with_retries(self, tables_text: str, year_list: list, job_id: Optional[str] = None) -> List[Dict]:
        return self.generate_accounts_with_retries(self.generate_accounts_pl, tables_text, year_list, job_id)

    def generate_accounts_cf_with_retries(self, tables_text: str, year_list: list, job_id: Optional[str] = None) -> List[Dict]:
        return self.generate_accounts_with_retries(self.generate_accounts_cf, tables_text, year_list, job_id)

    def generate_accounts_cf_main_with_retries(self, tables_text: str, year_list: list, job_id: Optional[str] = None) -> List[Dict]:
        """
        Genera SOLO los 3 flujos principales de CF con reintentos.
        """
        return self.generate_accounts_with_retries(self.generate_accounts_cf_main, tables_text, year_list, job_id)

    def generate_accounts_cf_details_with_retries(self, tables_text: str, year_list: list, job_id: Optional[str] = None) -> List[Dict]:
        """
        Genera SOLO las partidas adicionales (details) de CF con reintentos.
        """
        return self.generate_accounts_with_retries(self.generate_accounts_cf_details, tables_text, year_list, job_id)


    ##mas funcioens para guardar el json
    def _extract_and_normalize_data(self, event: List[dict]) -> List[dict]:
        """Extrae y normaliza datos del evento con tolerancia a errores"""
        normalized = []

        for ev_idx, ev in enumerate(event):
            try:
                data = ev.get("data", [])
                if isinstance(data, list):
                    for item in data:
                        if isinstance(item, dict):
                            normalized.append(item)
                        elif isinstance(item, list):
                            normalized.extend([i for i in item if isinstance(i, dict)])
                elif isinstance(data, dict):
                    normalized.append(data)

            except Exception as e:
                logger.warning(f"Error extrayendo datos del evento {ev_idx}: {e}")

        return normalized

    def _validate_event_data(self, event: List[dict]) -> Tuple[bool, str, Optional[str], Optional[str], Optional[str], Optional[str], Optional[str]]:
        """
        Valida la estructura del evento con mayor robustez.
        Returns: (is_valid, error_message, statement_id, request_id, type, periodicity)
        """
        try:
            if not event:
                return False, "El evento está vacío o es None", None, None, None, None, None

            if not isinstance(event, list):
                return False, f"El evento debe ser una lista, recibido: {type(event).__name__}", None, None, None, None, None

            if len(event) == 0:
                return False, "La lista del evento está vacía", None, None, None, None, None

            # Buscar statement_id y request_id con tolerancia a errores
            object_key_json_output = None
            request_id = None
            _type = None
            periodicity = None
            job_id = None

            for idx, ev in enumerate(event):
                try:
                    if not isinstance(ev, dict):
                        logger.warning(f"Elemento {idx} del evento no es dict: {type(ev).__name__}")
                        continue

                    if not object_key_json_output and ev.get("object_key_json_output"):
                        object_key_json_output = str(ev.get("object_key_json_output"))

                    if not request_id and ev.get("request_id"):
                        request_id = str(ev.get("request_id"))
                    if not periodicity and ev.get("periodicity"):
                        periodicity = str(ev.get("periodicity"))

                    if not _type and ev.get("type"):
                        _type = str(ev.get("type"))

                    if not job_id and ev.get("job_id"):
                        job_id = str(ev.get("job_id"))

                    if object_key_json_output and request_id and periodicity and job_id:
                        break

                except Exception as e:
                    logger.warning(f"Error procesando elemento {idx} del evento: {e}")

            if not object_key_json_output:
                return False, "No se encontró object_key_json_output en ningún elemento del evento", None, request_id, _type, periodicity, job_id

            logger.info(f"Evento validado - Statement ID: {object_key_json_output}, Request ID: {request_id or 'N/A'}")
            return True, "", object_key_json_output, request_id, _type, periodicity, job_id
        except Exception as e:
            logger.error("Error crítico validando evento", e)
            return False, f"Error inesperado validando evento: {str(e)}", None, None, None, None, None

    def _create_error_response(self, status_code: int, error: str,
                               object_key_json_output: Optional[str], request_id: Optional[str], job_id: Optional[str] = None) -> dict:
        """Crea una respuesta de error estructurada"""
        logger.error(f"Respuesta de error {status_code}: {error}")

        response_body = {
            "error": error,
            "object_ket_json_output": object_key_json_output or "N/A",
            "request_id": request_id or "N/A",
        }



        self._job_failed(job_id, error)

        return {
            "statusCode": status_code,
            "body": json.dumps(response_body)
        }

    def _create_success_response(self, object_key_json_output: str, request_id: Optional[str], job_id: Optional[str]=None) -> dict:
        """Crea una respuesta exitosa con estadísticas completas"""
        logger.info("=" * 60)
        logger.info("PROCESAMIENTO COMPLETADO EXITOSAMENTE")
        logger.info("=" * 60)

        response_body = {
            "message": "Procesamiento completado exitosamente",
            "object_ket_json_output": object_key_json_output,
            "request_id": request_id or "N/A",
            "json_save": True
        }

        self._job_complete(job_id, response_body)

        return {
            "statusCode": 200,
            "body": json.dumps(response_body)
        }

    def _create_partial_success_response(self, insertion_result: dict, object_key_json_output: str,
                                         request_id: Optional[str]) -> dict:
        """Crea una respuesta de éxito parcial cuando hay algunos errores"""
        logger.warning("Procesamiento completado con errores parciales")

        response_body = {
            "message": "Procesamiento completado con algunos errores",
            "statement_id": object_key_json_output,
            "request_id": request_id or "N/A",
            "partial_success": True,
            "datapoints_inserted": insertion_result.get("inserted", 0),

        }




        return {
            "statusCode": 207,  # Multi-Status para indicar éxito parcial
            "body": json.dumps(response_body)
        }

    def process_financial_data(self, event: List[dict]) -> dict:
        """
        Procesa datos financieros con máxima robustez y continuidad ante errores.
        Optimizado para Lambda con limpieza de estado.
        """
        # Limpiar estado para evitar reutilización en Lambda

        logger.info("=" * 60)
        logger.info("INICIANDO PROCESAMIENTO DE DATOS FINANCIEROS")
        logger.info("=" * 60)

        object_key_json_output = None
        request_id = None

        try:
            # FASE 1: Validación inicial
            is_valid, error_msg, object_key_json_output, request_id, _type, periodicity, job_id = self._validate_event_data(event)
            if not is_valid:
                return self._create_error_response(400, error_msg, object_key_json_output, request_id)

            logger.info(f"Procesando - Request: {request_id or 'N/A'}, Statement: {object_key_json_output}")

            # FASE 2: Obtener y validar financial statement





            # FASE 4: Normalizar y procesar datos
            normalized = self._extract_and_normalize_data(event)

            if not normalized:
                data_save = {
                    "data": [],
                    "type": _type,
                    "periodicity": periodicity
                }
                self.s3_client.upload_json_file(file_name=object_key_json_output, json_content=data_save)
                return self._create_error_response(400, "No hay datos válidos para procesar",
                                                   object_key_json_output, request_id,job_id)

            logger.info(f"Datos normalizados: {len(normalized)} elementos")

            # FASE 5: Procesar
            data_save = {
                "data": normalized,
                "type": _type,
                "periodicity": periodicity
            }
            print(data_save)
            self.s3_client.upload_json_file(file_name=object_key_json_output, json_content=data_save)
            return self._create_success_response(
                object_key_json_output=object_key_json_output,
                request_id=request_id,
                job_id=job_id
            )


        except Exception as e:
            logger.error("ERROR CRÍTICO en procesamiento", e)
            try:
                data_save = {
                    "data": [],
                    "type": '',
                    "periodicity": ''
                }
                self.s3_client.upload_json_file(file_name=object_key_json_output, json_content=data_save)
            except Exception as e:
                logger.error(f"error: {e}")
            return self._create_error_response(
                500, f"Error interno: {str(e)}", object_key_json_output, request_id
            )






