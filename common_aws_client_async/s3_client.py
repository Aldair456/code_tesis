import logging
import PyPDF2
import io
import aioboto3
import boto3
from typing import List, Optional
from botocore.exceptions import ClientError, NoCredentialsError
import json

# Configuración del logger
logger = logging.getLogger(__name__)


class S3ClientError(Exception):
    """Excepción personalizada para errores del cliente S3"""
    pass

def get_s3_client_sync(region_name: str = "us-east-1"):
    """Lazy initialization del cliente S3 con reutilización"""
    global s3_client
    if s3_client is None:
        s3_client = boto3.client("s3", region_name=region_name)
    return s3_client

class S3Client:
    def __init__(self, bucket_name: str, region_name: str = 'us-east-1'):
        self.bucket_name = bucket_name
        self.region_name = region_name
        self._session = None
        self.s3_client_sync = None

    def _get_session(self):
        """Obtiene o crea una sesión aioboto3 reutilizable"""
        if self._session is None:
            self._session = aioboto3.Session()
        return self._session

    def _get_s3_client_sync(self, region_name: str = "us-east-1"):
        """Lazy initialization del cliente S3 con reutilización"""
        if self.s3_client_sync is None:
            self.s3_client_sync = boto3.client("s3", region_name=region_name)
        return self.s3_client_sync

    async def get_file(self, file_name: str) -> bytes:
        """
        Obtiene un archivo de un bucket de S3.

        :param file_name: Nombre del archivo a obtener.
        :return: El contenido del archivo en bytes.
        :raises S3ClientError: Si hay un error al obtener el archivo.
        """
        session = self._get_session()
        async with session.client('s3', region_name=self.region_name) as s3:
            try:
                response = await s3.get_object(Bucket=self.bucket_name, Key=file_name)
                file_data = await response['Body'].read()
                logger.info(f"Archivo '{file_name}' obtenido exitosamente.")
                return file_data
            except ClientError as e:
                error_code = e.response['Error']['Code']
                if error_code == 'NoSuchKey':
                    raise S3ClientError(f"El archivo '{file_name}' no existe en el bucket.")
                elif error_code == 'NoSuchBucket':
                    raise S3ClientError(f"El bucket '{self.bucket_name}' no existe.")
                else:
                    raise S3ClientError(f"Error de AWS al obtener el archivo '{file_name}': {e}")
            except NoCredentialsError:
                raise S3ClientError("No se encontraron credenciales de AWS válidas.")
            except Exception as e:
                logger.error(f"Error inesperado al obtener el archivo {file_name}: {e}")
                raise S3ClientError(f"Error inesperado al obtener el archivo '{file_name}': {e}")

    def _validate_page_number(self, page_number: int, total_pages: int) -> None:
        """Valida que el número de página esté en el rango válido"""
        if page_number < 1:
            raise ValueError("El número de página debe ser mayor a 0.")
        if page_number > total_pages:
            raise ValueError(
                f"El número de página {page_number} está fuera del rango. El documento tiene {total_pages} páginas.")

    def _validate_page_range(self, start_page: int, end_page: int, total_pages: int) -> None:
        """Valida que el rango de páginas sea válido"""
        if start_page < 1 or end_page < 1:
            raise ValueError("Los números de página deben ser mayores a 0.")
        if start_page > end_page:
            raise ValueError(f"La página inicial ({start_page}) no puede ser mayor que la página final ({end_page}).")
        if start_page > total_pages or end_page > total_pages:
            raise ValueError(f"El rango de páginas está fuera del documento. El documento tiene {total_pages} páginas.")

    async def extract_pdf_page(self, file_name: str, page_number: int) -> bytes:
        """
        Extrae una página de un PDF almacenado en S3 y devuelve un buffer de bytes de la página.

        :param file_name: Nombre del archivo PDF.
        :param page_number: Número de la página a extraer (1-indexado).
        :return: Página extraída en formato de bytes (buffer).
        :raises ValueError: Si el número de página está fuera del rango del PDF.
        :raises S3ClientError: Si hay error al obtener el archivo.
        """
        pdf_data = await self.get_file(file_name)

        try:
            # Usar PyPDF2 para procesar el PDF y extraer la página
            reader = PyPDF2.PdfReader(io.BytesIO(pdf_data))
            total_pages = len(reader.pages)

            # Validar que el número de página esté dentro del rango
            self._validate_page_number(page_number, total_pages)

            writer = PyPDF2.PdfWriter()
            writer.add_page(reader.pages[page_number - 1])

            # Escribir la página extraída en un buffer de memoria
            output_buffer = io.BytesIO()
            writer.write(output_buffer)

            logger.info(f"Página {page_number} extraída exitosamente del archivo '{file_name}'.")
            return output_buffer.getvalue()
        except Exception as e:
            if "PDF" in str(e) or "pdf" in str(e):
                raise ValueError(f"Error al procesar el PDF '{file_name}': {e}")
            else:
                logger.error(f"Error al procesar el PDF '{file_name}': {e}")
                raise S3ClientError(f"Error al procesar el PDF: {e}")





    async def extract_pdf_pages(self, file_name: str, start_page: int, end_page: int) -> bytes:
        """
        Extrae un rango de páginas de un PDF almacenado en S3 y devuelve un buffer de bytes con todas las páginas extraídas.

        :param file_name: Nombre del archivo PDF.
        :param start_page: Número de la página de inicio (1-indexado).
        :param end_page: Número de la página final (1-indexado, inclusivo).
        :return: Páginas extraídas en formato de bytes (buffer).
        :raises ValueError: Si los números de página están fuera del rango del PDF.
        :raises S3ClientError: Si hay error al obtener el archivo.
        """
        pdf_data = await self.get_file(file_name)

        try:
            # Usar PyPDF2 para procesar el PDF y extraer las páginas
            reader = PyPDF2.PdfReader(io.BytesIO(pdf_data))
            total_pages = len(reader.pages)

            # Validar que el rango de páginas esté dentro del rango del documento
            self._validate_page_range(start_page, end_page, total_pages)

            writer = PyPDF2.PdfWriter()

            # Extraer las páginas en el rango solicitado (end_page es inclusivo)
            for page_num in range(start_page - 1, end_page):
                writer.add_page(reader.pages[page_num])

            # Escribir las páginas extraídas en un buffer de memoria
            output_buffer = io.BytesIO()
            writer.write(output_buffer)

            logger.info(f"Páginas {start_page}-{end_page} extraídas exitosamente del archivo '{file_name}'.")
            return output_buffer.getvalue()


        except Exception as e:
            if "PDF" in str(e) or "pdf" in str(e):
                raise ValueError(f"Error al procesar el PDF '{file_name}': {e}")
            else:
                logger.error(f"Error al procesar el PDF '{file_name}': {e}")
                raise S3ClientError(f"Error al procesar el PDF: {e}")

    async def extract_pdf_pages_list(self, file_name: str, page_numbers: List[int], max_pages: int = 10) -> List[bytes]:
        """
        Extrae páginas específicas de un PDF almacenado en S3 y devuelve una lista de buffers de bytes de las páginas.

        :param file_name: Nombre del archivo PDF.
        :param page_numbers: Lista de números de páginas a extraer (1-indexado).
        :param max_pages: Número máximo de páginas que se pueden extraer (por defecto 10).
        :return: Lista de páginas extraídas en formato de bytes (buffer).
        :raises ValueError: Si algún número de página está fuera del rango del PDF o si se excede el límite de páginas.
        :raises S3ClientError: Si hay error al obtener el archivo.
        """
        if not page_numbers:
            raise ValueError("La lista de números de página no puede estar vacía.")

        if len(page_numbers) > max_pages:
            raise ValueError(
                f"No se pueden extraer más de {max_pages} páginas a la vez. Se solicitaron {len(page_numbers)} páginas.")

        pdf_data = await self.get_file(file_name)

        try:
            # Usar PyPDF2 para procesar el PDF y extraer las páginas
            reader = PyPDF2.PdfReader(io.BytesIO(pdf_data))
            total_pages = len(reader.pages)
            extracted_pages = []

            for page_number in page_numbers:
                # Validar que el número de página esté dentro del rango
                self._validate_page_number(page_number, total_pages)

                writer = PyPDF2.PdfWriter()
                writer.add_page(reader.pages[page_number - 1])

                # Escribir la página extraída en un buffer de memoria
                output_buffer = io.BytesIO()
                writer.write(output_buffer)
                extracted_pages.append(output_buffer.getvalue())

            logger.info(f"{len(page_numbers)} páginas extraídas exitosamente del archivo '{file_name}'.")
            return extracted_pages



        except Exception as e:
            if "PDF" in str(e) or "pdf" in str(e):
                raise ValueError(f"Error al procesar el PDF '{file_name}': {e}")
            else:
                logger.error(f"Error al procesar el PDF '{file_name}': {e}")
                raise S3ClientError(f"Error al procesar el PDF: {e}")
    async def upload_text_file(self, file_name: str, text_content: str) -> bool:
        """
        Sube un archivo de texto (.txt) a S3 con un nombre específico.

        :param file_name: Nombre del archivo que se guardará en S3 (incluyendo extensión, ej: "archivo.txt").
        :param text_content: Contenido de texto que se guardará en el archivo.
        :return: True si la subida fue exitosa.
        :raises S3ClientError: Si hay error al subir el archivo.
        """
        if not text_content:
            logger.warning(f"El contenido del archivo '{file_name}' está vacío.")

        session = self._get_session()
        async with session.client('s3', region_name=self.region_name) as s3:
            try:
                await s3.put_object(
                    Bucket=self.bucket_name,
                    Key=file_name,
                    Body=text_content.encode('utf-8'),
                    ContentType='text/plain; charset=utf-8'
                )
                logger.info(f"Archivo de texto '{file_name}' subido exitosamente a S3.")
                return True
            except ClientError as e:
                error_code = e.response['Error']['Code']
                if error_code == 'NoSuchBucket':
                    raise S3ClientError(f"El bucket '{self.bucket_name}' no existe.")
                else:
                    raise S3ClientError(f"Error de AWS al subir el archivo '{file_name}': {e}")
            except NoCredentialsError:
                raise S3ClientError("No se encontraron credenciales de AWS válidas.")
            except Exception as e:
                logger.error(f"Error inesperado al subir el archivo '{file_name}': {e}")
                raise S3ClientError(f"Error inesperado al subir el archivo '{file_name}': {e}")

    def upload_json_file(self, file_name: str, json_content: dict | list) -> bool:
        """
        Sube un archivo JSON (.json) a S3 con un nombre específico.

        :param file_name: Nombre del archivo que se guardará en S3 (incluyendo extensión, ej: "archivo.json").
        :param json_content: Contenido (dict o list) que se serializará a JSON y guardará en el archivo.
        :return: True si la subida fue exitosa.
        :raises S3ClientError: Si hay error al subir el archivo.
        """
        if not json_content:
            logger.warning(f"El contenido del archivo '{file_name}' está vacío.")


        try:
            json_string = json.dumps(json_content, ensure_ascii=False, indent=2)
            self._get_s3_client_sync()
            self.s3_client_sync.put_object(
                Bucket=self.bucket_name,
                Key=file_name,
                Body=json_string.encode('utf-8'),
                ContentType='application/json; charset=utf-8'
            )
            logger.info(f"Archivo JSON '{file_name}' subido exitosamente a S3.")
            return True
        except (TypeError, ValueError) as e:
            raise S3ClientError(f"Error al serializar el contenido a JSON: {e}")
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'NoSuchBucket':
                raise S3ClientError(f"El bucket '{self.bucket_name}' no existe.")
            else:
                raise S3ClientError(f"Error de AWS al subir el archivo '{file_name}': {e}")
        except NoCredentialsError:
            raise S3ClientError("No se encontraron credenciales de AWS válidas.")
        except Exception as e:
            logger.error(f"Error inesperado al subir el archivo '{file_name}': {e}")
            raise S3ClientError(f"Error inesperado al subir el archivo '{file_name}': {e}")




    async def close(self):
        """Cierra la sesión y libera recursos"""
        if self._session:
            # aioboto3 se encarga de cerrar las conexiones automáticamente
            self._session = None