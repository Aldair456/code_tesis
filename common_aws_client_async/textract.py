"""
TextractClient - Cliente asíncrono para Amazon Textract

Permite procesar documentos (PDFs, imágenes) usando AWS Textract para:
- Detección de texto (async para documentos grandes)
- Análisis de documentos (sync para documentos pequeños)
- Extracción de tablas y formularios
- Manejo de paginación y resultados

Uso:
    async with TextractClient() as client:
        # Para documentos pequeños
        result = await client.analyze_document_bytes(pdf_bytes, ['TABLES'])

        # Para documentos grandes
        job_id = await client.start_text_detection(bucket, key)
        text = await client.process_textract_result_detection(job_id)
"""

import aioboto3
import asyncio
import logging
from collections import defaultdict

logger = logging.getLogger()
logger.setLevel(logging.INFO)


class TextractClient:
    def __init__(self, region_name: str = 'us-east-1'):
        self.region_name = region_name
        self.session = aioboto3.Session()

    async def __aenter__(self):
        self.textract_client = await self.session.client('textract', region_name=self.region_name).__aenter__()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if hasattr(self, 'textract_client'):
            await self.textract_client.__aexit__(exc_type, exc_val, exc_tb)

    async def start_text_detection(self, bucket_name: str, object_key: str) -> str:
        try:
            response = await self.textract_client.start_document_text_detection(
                DocumentLocation={'S3Object': {'Bucket': bucket_name, 'Name': object_key}}
            )
            job_id = response.get('JobId', '')
            if job_id:
                logger.info(f"JobId: {job_id} - Esperando el resultado...")
            return job_id
        except Exception as e:
            logger.error(f"Error iniciando Textract: {e}")
            raise

    async def wait_for_result(self, job_id: str):
        while True:
            try:
                result = await self.textract_client.get_document_text_detection(JobId=job_id)
                status = result.get('JobStatus')

                if status == 'SUCCEEDED':
                    logger.info("Trabajo de Textract completado con éxito.")
                    return result
                elif status == 'FAILED':
                    logger.error(f"El trabajo de Textract falló")
                    return None

                logger.info("Procesando documento, esperando 5 segundos...")
                await asyncio.sleep(5)

            except Exception as e:
                logger.error(f"Error consultando JobId {job_id}: {e}")
                raise

    async def start_and_wait_for_result_detection(self, bucket_name: str, object_key: str) -> str:
        job_id = await self.start_text_detection(bucket_name, object_key)
        if not job_id:
            return ""

        result = await self.wait_for_result(job_id)
        return job_id if result else ""

    async def analyze_document(self, bucket_name: str, file_name: str, feature_types: list):
        try:
            response = await self.textract_client.analyze_document(
                Document={'S3Object': {'Bucket': bucket_name, 'Name': file_name}},
                FeatureTypes=feature_types
            )
            logger.info("Análisis del documento completado.")
            return response
        except Exception as e:
            logger.error(f"Error analizando documento {file_name}: {e}")
            return None

    async def analyze_document_bytes(self, document_bytes: bytes, feature_types: list):
        try:
            response = await self.textract_client.analyze_document(
                Document={'Bytes': document_bytes},
                FeatureTypes=feature_types
            )
            logger.info("Análisis del documento completado.")
            return response
        except Exception as e:
            logger.error(f"Error analizando documento: {e}")
            return None

    async def get_next_token(self, job_id: str, next_token: str = None):
        try:
            params = {'JobId': job_id}
            if next_token:
                params['NextToken'] = next_token

            result = await self.textract_client.get_document_text_detection(**params)
            return result, result.get('NextToken')
        except Exception as e:
            logger.error(f"Error obteniendo resultados paginados JobId {job_id}: {e}")
            return None, None

    async def process_textract_result_detection(self, job_id: str) -> str:
        lineas_por_pagina = defaultdict(list)
        next_token = None

        while True:
            result, next_token = await self.get_next_token(job_id, next_token)
            if not result:
                break

            for bloque in result.get('Blocks', []):
                if bloque.get('BlockType') == 'LINE' and 'Text' in bloque:
                    page_num = bloque.get('Page', 1)
                    lineas_por_pagina[page_num].append(bloque['Text'])

            if not next_token:
                break

        ordered_pages = []
        for page_num in sorted(lineas_por_pagina.keys()):
            page_text = "\n".join(lineas_por_pagina[page_num])
            labeled_page = f"###PAGE_ID:{page_num:03d}###\n{page_text}"
            ordered_pages.append(labeled_page)

        return "\n-------------\n".join(ordered_pages).strip()

    @staticmethod
    def extract_tables_from_textract_response(textract_response):
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