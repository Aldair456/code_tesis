"""
TextractClient - Cliente síncrono unificado para Amazon Textract

Versión síncrona del cliente original asíncrono.
Usa boto3 en lugar de aioboto3, eliminando async/await.

Características principales:
- Soporte para operaciones síncronas
- Procesamiento de documentos locales y en S3
- Extracción de texto, tablas, formularios y análisis de gastos
- Manejo robusto de paginación y resultados grandes
- Configuración para operaciones asíncronas con SNS/SQS
- Patrón de contexto (with) para gestión de recursos

Ejemplos de uso:
    with TextractClient() as client:
        # Análisis síncrono para documentos pequeños
        result = client.analyze_document_bytes(pdf_bytes, ['TABLES', 'FORMS'])

        # Detección asíncrona para documentos grandes
        job_id = client.start_text_detection(bucket, key)
        text = client.process_textract_result_detection(job_id)

        # Análisis de gastos (invoices/receipts)
        expenses = client.analyze_expense_bytes(receipt_bytes)
"""

import boto3
import time
import logging
from collections import defaultdict
from typing import List, Dict, Optional, Any

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class TextractClient:
    def __init__(self, region_name: str = 'us-east-1'):
        """
        Inicializa el cliente de Amazon Textract.

        :param region_name: Región de AWS donde se encuentra el servicio Textract.
        """
        self.region_name = region_name
        self.textract_client = None

    def __enter__(self):
        """
        Patrón de contexto para gestión automática de recursos.
        """
        self.textract_client = boto3.client(
            'textract',
            region_name=self.region_name
        )
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        Limpieza de recursos al salir del contexto.
        """
        # boto3 no requiere cierre explícito, pero limpiamos la referencia
        self.textract_client = None

    def _ensure_client(self):
        """
        Asegura que el cliente de Textract esté inicializado.
        Si no se usa el contexto with, inicializa el cliente aquí.
        """
        if self.textract_client is None:
            self.textract_client = boto3.client(
                'textract',
                region_name=self.region_name
            )
        return self.textract_client

    # =========================================================================
    # OPERACIONES ASÍNCRONAS PARA DOCUMENTOS GRANDES
    # =========================================================================

    def start_text_detection(self, bucket_name: str, object_key: str,
                              sns_topic_arn: str = None, sns_role_arn: str = None,
                              job_tag: str = None, client_request_token: str = None) -> str:
        """
        Inicia el procesamiento asíncrono para detección de texto en documentos grandes.

        :param bucket_name: Nombre del bucket S3
        :param object_key: Clave del objeto en S3
        :param sns_topic_arn: ARN del tema SNS (opcional pero recomendado para async)
        :param sns_role_arn: ARN del rol IAM (opcional pero recomendado para async)
        :param job_tag: Etiqueta para identificar el trabajo
        :param client_request_token: Token para prevenir duplicación (vida 7 días)
        :return: JobId del trabajo iniciado
        """
        try:
            client = self._ensure_client()

            params = {
                'DocumentLocation': {
                    'S3Object': {'Bucket': bucket_name, 'Name': object_key}
                }
            }

            if sns_topic_arn and sns_role_arn:
                params['NotificationChannel'] = {
                    'SNSTopicArn': sns_topic_arn,
                    'RoleArn': sns_role_arn
                }

            if job_tag:
                params['JobTag'] = job_tag

            if client_request_token:
                params['ClientRequestToken'] = client_request_token

            response = client.start_document_text_detection(**params)
            job_id = response.get('JobId', '')

            if job_id:
                logger.info(f"Text detection job started. JobId: {job_id}")
            else:
                logger.error("No JobId received from Textract")

            return job_id

        except Exception as e:
            logger.error(f"Error starting text detection: {e}")
            raise

    def start_document_analysis(self, bucket_name: str, object_key: str,
                                 feature_types: List[str], sns_topic_arn: str = None,
                                 sns_role_arn: str = None, job_tag: str = None) -> str:
        """
        Inicia análisis asíncrono para extracción de tablas y formularios.

        :param bucket_name: Nombre del bucket S3
        :param object_key: Clave del objeto en S3
        :param feature_types: Tipos de características ['TABLES', 'FORMS']
        :param sns_topic_arn: ARN del tema SNS para notificaciones
        :param sns_role_arn: ARN del rol IAM para permisos
        :param job_tag: Etiqueta para identificar el trabajo
        :return: JobId del trabajo iniciado
        """
        try:
            client = self._ensure_client()

            params = {
                'DocumentLocation': {
                    'S3Object': {'Bucket': bucket_name, 'Name': object_key}
                },
                'FeatureTypes': feature_types
            }

            if sns_topic_arn and sns_role_arn:
                params['NotificationChannel'] = {
                    'SNSTopicArn': sns_topic_arn,
                    'RoleArn': sns_role_arn
                }

            if job_tag:
                params['JobTag'] = job_tag

            response = client.start_document_analysis(**params)
            job_id = response.get('JobId', '')
            logger.info(f"Document analysis job started. JobId: {job_id}")
            return job_id

        except Exception as e:
            logger.error(f"Error starting document analysis: {e}")
            raise

    def start_expense_analysis(self, bucket_name: str, object_key: str,
                                sns_topic_arn: str = None, sns_role_arn: str = None) -> str:
        """
        Inicia análisis asíncrono de gastos para invoices y receipts.

        :param bucket_name: Nombre del bucket S3
        :param object_key: Clave del objeto en S3
        :param sns_topic_arn: ARN del tema SNS para notificaciones
        :param sns_role_arn: ARN del rol IAM para permisos
        :return: JobId del trabajo iniciado
        """
        try:
            client = self._ensure_client()

            params = {
                'DocumentLocation': {
                    'S3Object': {'Bucket': bucket_name, 'Name': object_key}
                }
            }

            if sns_topic_arn and sns_role_arn:
                params['NotificationChannel'] = {
                    'SNSTopicArn': sns_topic_arn,
                    'RoleArn': sns_role_arn
                }

            response = client.start_expense_analysis(**params)
            job_id = response.get('JobId', '')
            logger.info(f"Expense analysis job started. JobId: {job_id}")
            return job_id

        except Exception as e:
            logger.error(f"Error starting expense analysis: {e}")
            raise

    # =========================================================================
    # OPERACIONES SÍNCRONAS PARA DOCUMENTOS PEQUEÑOS
    # =========================================================================

    def analyze_document(self, bucket_name: str, file_name: str, feature_types: List[str]):
        """
        Analiza un documento en S3 de forma síncrona.

        :param bucket_name: Nombre del bucket en S3
        :param file_name: Nombre del archivo en S3
        :param feature_types: Lista de características a extraer ['TABLES', 'FORMS']
        :return: Respuesta de Textract con los bloques detectados
        """
        try:
            client = self._ensure_client()

            response = client.analyze_document(
                Document={'S3Object': {'Bucket': bucket_name, 'Name': file_name}},
                FeatureTypes=feature_types
            )
            logger.info(f"Document analysis completed. Detected {len(response.get('Blocks', []))} blocks.")
            return response
        except Exception as e:
            logger.error(f"Error analyzing document {file_name}: {e}")
            return None

    def analyze_document_bytes(self, document_bytes: bytes, feature_types: List[str]):
        """
        Analiza un documento desde bytes en memoria.

        :param document_bytes: Documento en formato bytes
        :param feature_types: Lista de características a extraer
        :return: Respuesta de Textract con los bloques detectados
        """
        try:
            client = self._ensure_client()

            response = client.analyze_document(
                Document={'Bytes': document_bytes},
                FeatureTypes=feature_types
            )
            logger.info(f"Document analysis from bytes completed. Detected {len(response.get('Blocks', []))} blocks.")
            return response
        except Exception as e:
            logger.error(f"Error analyzing document from bytes: {e}")
            return None

    def detect_document_text_bytes(self, document_bytes: bytes):
        """
        Detecta texto en un documento desde bytes.

        :param document_bytes: Documento en formato bytes
        :return: Respuesta de Textract con el texto detectado
        """
        try:
            client = self._ensure_client()

            response = client.detect_document_text(
                Document={'Bytes': document_bytes}
            )
            logger.info(f"Text detection from bytes completed. Detected {len(response.get('Blocks', []))} blocks.")
            return response
        except Exception as e:
            logger.error(f"Error detecting text from bytes: {e}")
            return None

    def analyze_expense_bytes(self, document_bytes: bytes):
        """
        Analiza gastos desde invoices/receipts en formato bytes.

        :param document_bytes: Documento de gastos en formato bytes
        :return: Respuesta de Textract con los gastos detectados
        """
        try:
            client = self._ensure_client()

            response = client.analyze_expense(
                Document={'Bytes': document_bytes}
            )
            logger.info(
                f"Expense analysis completed. Found {len(response.get('ExpenseDocuments', []))} expense documents.")
            return response
        except Exception as e:
            logger.error(f"Error analyzing expenses: {e}")
            return None

    # =========================================================================
    # GESTIÓN DE RESULTADOS Y PAGINACIÓN
    # =========================================================================

    def wait_for_result(self, job_id: str, operation_type: str = 'text_detection'):
        """
        Espera (bloqueando) hasta que el trabajo de Textract esté completo.

        :param job_id: ID del trabajo a consultar
        :param operation_type: Tipo de operación ('text_detection', 'document_analysis' o 'expense_analysis')
        :return: Resultado del trabajo o None si falló
        """
        client = self._ensure_client()

        if operation_type == 'text_detection':
            get_operation = client.get_document_text_detection
        elif operation_type == 'document_analysis':
            get_operation = client.get_document_analysis
        elif operation_type == 'expense_analysis':
            get_operation = client.get_expense_analysis
        else:
            raise ValueError(f"Unsupported operation type: {operation_type}")

        while True:
            try:
                result = get_operation(JobId=job_id)
                status = result.get('JobStatus')

                if status == 'SUCCEEDED':
                    logger.info(f"Textract job {job_id} completed successfully.")
                    return result
                elif status == 'FAILED':
                    logger.error(f"Textract job {job_id} failed.")
                    return None
                elif status == 'PARTIAL_SUCCESS':
                    logger.warning(f"Textract job {job_id} completed with partial success.")
                    return result

                logger.info(f"Job {job_id} status: {status}. Waiting 5 seconds...")
                time.sleep(5)

            except Exception as e:
                logger.error(f"Error checking job status {job_id}: {e}")
                raise

    def get_next_token(self, job_id: str, next_token: str = None,
                       operation_type: str = 'text_detection'):
        """
        Obtiene la siguiente página de resultados paginados.

        :param job_id: ID del trabajo de Textract
        :param next_token: Token para la siguiente página
        :param operation_type: Tipo de operación
        :return: Tupla (resultado, next_token)
        """
        try:
            client = self._ensure_client()

            if operation_type == 'text_detection':
                get_operation = client.get_document_text_detection
            elif operation_type == 'document_analysis':
                get_operation = client.get_document_analysis
            elif operation_type == 'expense_analysis':
                get_operation = client.get_expense_analysis
            else:
                raise ValueError(f"Unsupported operation type: {operation_type}")

            params = {'JobId': job_id}
            if next_token:
                params['NextToken'] = next_token

            result = get_operation(**params)
            return result, result.get('NextToken')

        except Exception as e:
            logger.error(f"Error getting paginated results for JobId {job_id}: {e}")
            return None, None

    def process_textract_result_detection(self, job_id: str) -> str:
        """
        Procesa todos los resultados de detección de texto y los agrupa por página.

        :param job_id: ID del trabajo de Textract
        :return: Texto procesado con separadores de página
        """
        lineas_por_pagina = defaultdict(list)
        next_token = None

        while True:
            try:
                result, next_token = self.get_next_token(job_id, next_token, 'text_detection')
                if not result:
                    break

                for bloque in result.get('Blocks', []):
                    if bloque.get('BlockType') == 'LINE' and 'Text' in bloque:
                        page_num = bloque.get('Page', 1)
                        lineas_por_pagina[page_num].append(bloque['Text'])

                if not next_token:
                    break

            except Exception as e:
                logger.error(f"Error processing Textract result: {e}")
                return ""

        ordered_pages = []
        for page_num in sorted(lineas_por_pagina.keys()):
            page_text = "\n".join(lineas_por_pagina[page_num])
            labeled_page = f"###PAGE_ID:{page_num:03d}###\n{page_text}"
            ordered_pages.append(labeled_page)

        return "\n-------------\n".join(ordered_pages).strip()

    def start_and_wait_for_result_detection(self, bucket_name: str, object_key: str) -> str:
        """
        Método combinado: inicia detección y espera resultado.

        :param bucket_name: Bucket S3 del documento
        :param object_key: Clave S3 del documento
        :return: JobId del trabajo completado
        """
        job_id = self.start_text_detection(bucket_name, object_key)
        if not job_id:
            return ""

        result = self.wait_for_result(job_id, 'text_detection')
        return job_id if result else ""

    # =========================================================================
    # MÉTODOS UTILITARIOS PARA PROCESAMIENTO DE RESULTADOS
    # =========================================================================

    @staticmethod
    def extract_tables_from_textract_response(textract_response):
        """
        Extrae tablas de la respuesta de Textract.

        :param textract_response: Respuesta de Textract
        :return: Lista de tablas (cada tabla es lista de filas)
        """
        blocks = textract_response['Blocks']
        block_map = {block['Id']: block for block in blocks}

        def get_text_for_cell(cell_block):
            text = []
            if 'Relationships' in cell_block:
                for rel in cell_block['Relationships']:
                    if rel['Type'] == 'CHILD':
                        for child_id in rel['Ids']:
                            word = block_map[child_id]
                            if word['BlockType'] == 'WORD':
                                text.append(word['Text'])
                            elif word['BlockType'] == 'SELECTION_ELEMENT':
                                text.append("[X]" if word['SelectionStatus'] == 'SELECTED' else "[ ]")
            return " ".join(text)

        tables = []
        for block in blocks:
            if block['BlockType'] == 'TABLE':
                rows = {}
                if 'Relationships' in block:
                    for rel in block['Relationships']:
                        if rel['Type'] == 'CHILD':
                            for cell_id in rel['Ids']:
                                cell = block_map[cell_id]
                                if cell['BlockType'] == 'CELL':
                                    row_idx = cell['RowIndex']
                                    col_idx = cell['ColumnIndex']

                                    if row_idx not in rows:
                                        rows[row_idx] = {}
                                    rows[row_idx][col_idx] = get_text_for_cell(cell)

                table_content = []
                for row_idx in sorted(rows.keys()):
                    row_cells = [rows[row_idx][col_idx] for col_idx in sorted(rows[row_idx].keys())]
                    table_content.append(row_cells)

                tables.append(table_content)

        return tables

    @staticmethod
    def extract_forms_from_textract_response(textract_response):
        """
        Extrae pares clave-valor de formularios.

        :param textract_response: Respuesta de Textract
        :return: Diccionario con pares clave-valor
        """
        blocks = textract_response['Blocks']
        block_map = {block['Id']: block for block in blocks}
        forms = {}

        for block in blocks:
            if block['BlockType'] == 'KEY_VALUE_SET':
                if 'ENTITY_TYPES' in block:
                    if 'KEY' in block['ENTITY_TYPES']:
                        key_text = TextractClient._get_text_from_block(block, block_map)
                        if 'Relationships' in block:
                            for relationship in block['Relationships']:
                                if relationship['Type'] == 'VALUE':
                                    for value_id in relationship['Ids']:
                                        value_block = block_map[value_id]
                                        value_text = TextractClient._get_text_from_block(value_block, block_map)
                                        forms[key_text] = value_text

        return forms

    @staticmethod
    def _get_text_from_block(block, block_map):
        """Extrae texto de un bloque y sus hijos."""
        text_parts = []
        if 'Relationships' in block:
            for relationship in block['Relationships']:
                if relationship['Type'] == 'CHILD':
                    for child_id in relationship['Ids']:
                        child_block = block_map[child_id]
                        if child_block['BlockType'] == 'WORD':
                            text_parts.append(child_block['Text'])
        return ' '.join(text_parts)

    @staticmethod
    def get_detected_text(textract_response):
        """
        Extrae todo el texto detectado de la respuesta.

        :param textract_response: Respuesta de Textract
        :return: Texto concatenado
        """
        lines = []
        for block in textract_response.get('Blocks', []):
            if block['BlockType'] == 'LINE':
                lines.append(block.get('Text', ''))
        return '\n'.join(lines)
