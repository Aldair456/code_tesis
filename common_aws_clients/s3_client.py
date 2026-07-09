import boto3
from botocore.exceptions import ClientError, NoCredentialsError
from typing import List, Dict, Optional, Union, BinaryIO
import json
import logging
import os
from io import BytesIO, StringIO

# Configurar logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Cliente S3 global para reutilización entre invocaciones Lambda
_s3_client = None


def get_s3_client(region_name: str = "us-east-1"):
    """Lazy initialization del cliente S3 con reutilización"""
    global _s3_client
    if _s3_client is None:
        _s3_client = boto3.client("s3", region_name=region_name)
        logger.info(f"Cliente S3 inicializado en región: {region_name}")
    return _s3_client


class S3Client:
    """Cliente S3 completo para operaciones genéricas de archivos"""

    def __init__(self, bucket_name: Optional[str] = None, region_name: str = "us-east-1"):
        """
        Args:
            bucket_name: Bucket por defecto (puede ser sobrescrito en cada método)
            region_name: Región de AWS
        """
        self.default_bucket = bucket_name
        self.region_name = region_name

    @property
    def s3(self):
        """Property para lazy loading del cliente S3"""
        return get_s3_client(self.region_name)

    def _get_bucket(self, bucket: Optional[str] = None) -> str:
        """Obtiene el bucket a usar (argumento o default)"""
        if bucket:
            return bucket
        if self.default_bucket:
            return self.default_bucket
        raise ValueError("No se especificó bucket y no hay bucket por defecto")

    # ================================================================
    # ===================== OPERACIONES GET/DOWNLOAD =================
    # ================================================================

    def get(self, key: str, bucket: Optional[str] = None) -> Dict[str, any]:
        """
        Obtiene un objeto de S3 (respuesta completa)

        Returns:
            Dict con Body, ContentType, Metadata, etc.
        """
        try:
            bucket_name = self._get_bucket(bucket)
            response = self.s3.get_object(Bucket=bucket_name, Key=key)
            logger.info(f"Objeto obtenido: s3://{bucket_name}/{key}")
            return response
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', '')
            if error_code == 'NoSuchKey':
                logger.warning(f"Objeto no encontrado: s3://{bucket_name}/{key}")
                return None
            logger.error(f"Error obteniendo objeto {key}: {str(e)}")
            raise

    def get_text(self, key: str, bucket: Optional[str] = None, encoding: str = 'utf-8') -> Optional[str]:
        """
        Obtiene contenido de texto de un archivo

        Returns:
            String con el contenido o None si no existe
        """
        try:
            response = self.get(key, bucket)
            if response is None:
                return None
            content = response['Body'].read().decode(encoding)
            logger.info(f"Texto obtenido: {len(content)} caracteres")
            return content
        except Exception as e:
            logger.error(f"Error leyendo texto de {key}: {str(e)}")
            raise

    def get_json(self, key: str, bucket: Optional[str] = None) -> Optional[Dict]:
        """
        Obtiene y parsea un archivo JSON

        Returns:
            Dict con el JSON parseado o None si no existe
        """
        try:
            text_content = self.get_text(key, bucket)
            if text_content is None:
                return None
            data = json.loads(text_content)
            logger.info(f"JSON parseado exitosamente: {key}")
            return data
        except json.JSONDecodeError as e:
            logger.error(f"Error parseando JSON de {key}: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Error obteniendo JSON de {key}: {str(e)}")
            raise

    def get_binary(self, key: str, bucket: Optional[str] = None) -> Optional[bytes]:
        """
        Obtiene contenido binario de un archivo

        Returns:
            Bytes con el contenido o None si no existe
        """
        try:
            response = self.get(key, bucket)
            if response is None:
                return None
            content = response['Body'].read()
            logger.info(f"Binario obtenido: {len(content)} bytes")
            return content
        except Exception as e:
            logger.error(f"Error leyendo binario de {key}: {str(e)}")
            raise

    def download_file(self, key: str, local_path: str, bucket: Optional[str] = None) -> bool:
        """
        Descarga un archivo de S3 al sistema de archivos local

        Returns:
            True si se descargó exitosamente
        """
        try:
            bucket_name = self._get_bucket(bucket)

            # Crear directorio si no existe
            os.makedirs(os.path.dirname(local_path), exist_ok=True)

            self.s3.download_file(bucket_name, key, local_path)
            logger.info(f"Archivo descargado: s3://{bucket_name}/{key} -> {local_path}")
            return True
        except Exception as e:
            logger.error(f"Error descargando archivo {key}: {str(e)}")
            raise

    def download_fileobj(self, key: str, file_obj: BinaryIO, bucket: Optional[str] = None) -> bool:
        """
        Descarga un archivo de S3 a un objeto file-like

        Returns:
            True si se descargó exitosamente
        """
        try:
            bucket_name = self._get_bucket(bucket)
            self.s3.download_fileobj(bucket_name, key, file_obj)
            logger.info(f"Archivo descargado a fileobj: s3://{bucket_name}/{key}")
            return True
        except Exception as e:
            logger.error(f"Error descargando fileobj {key}: {str(e)}")
            raise

    # ================================================================
    # ===================== OPERACIONES PUT/UPLOAD ===================
    # ================================================================

    def put(self, key: str, body: Union[str, bytes], bucket: Optional[str] = None,
            content_type: Optional[str] = None, metadata: Optional[Dict] = None,
            **kwargs) -> bool:
        """
        Sube un objeto a S3 (método genérico)

        Args:
            key: Key del objeto
            body: Contenido (string o bytes)
            bucket: Bucket destino
            content_type: Content-Type del objeto
            metadata: Metadatos personalizados
            **kwargs: Parámetros adicionales de put_object

        Returns:
            True si se subió exitosamente
        """
        try:
            bucket_name = self._get_bucket(bucket)

            params = {
                'Bucket': bucket_name,
                'Key': key,
                'Body': body
            }

            if content_type:
                params['ContentType'] = content_type

            if metadata:
                params['Metadata'] = metadata

            # Agregar parámetros adicionales
            params.update(kwargs)

            self.s3.put_object(**params)
            logger.info(f"Objeto subido: s3://{bucket_name}/{key}")
            return True
        except Exception as e:
            logger.error(f"Error subiendo objeto {key}: {str(e)}")
            raise

    def put_text(self, key: str, content: str, bucket: Optional[str] = None,
                 encoding: str = 'utf-8', **kwargs) -> bool:
        """
        Sube un archivo de texto a S3

        Returns:
            True si se subió exitosamente
        """
        try:
            body = content.encode(encoding)
            return self.put(key, body, bucket, content_type='text/plain', **kwargs)
        except Exception as e:
            logger.error(f"Error subiendo texto a {key}: {str(e)}")
            raise

    def put_json(self, key: str, data: Union[Dict, List], bucket: Optional[str] = None,
                 indent: Optional[int] = None, **kwargs) -> bool:
        """
        Sube un objeto JSON a S3

        Returns:
            True si se subió exitosamente
        """
        try:
            json_content = json.dumps(data, indent=indent, ensure_ascii=False)
            return self.put(key, json_content.encode('utf-8'), bucket,
                            content_type='application/json', **kwargs)
        except Exception as e:
            logger.error(f"Error subiendo JSON a {key}: {str(e)}")
            raise

    def put_binary(self, key: str, content: bytes, bucket: Optional[str] = None,
                   content_type: str = 'application/octet-stream', **kwargs) -> bool:
        """
        Sube contenido binario a S3

        Returns:
            True si se subió exitosamente
        """
        try:
            return self.put(key, content, bucket, content_type=content_type, **kwargs)
        except Exception as e:
            logger.error(f"Error subiendo binario a {key}: {str(e)}")
            raise

    def upload_file(self, local_path: str, key: str, bucket: Optional[str] = None,
                    extra_args: Optional[Dict] = None) -> bool:
        """
        Sube un archivo local a S3

        Returns:
            True si se subió exitosamente
        """
        try:
            bucket_name = self._get_bucket(bucket)

            if not os.path.exists(local_path):
                raise FileNotFoundError(f"Archivo no encontrado: {local_path}")

            self.s3.upload_file(local_path, bucket_name, key, ExtraArgs=extra_args)
            logger.info(f"Archivo subido: {local_path} -> s3://{bucket_name}/{key}")
            return True
        except Exception as e:
            logger.error(f"Error subiendo archivo {local_path}: {str(e)}")
            raise

    def upload_fileobj(self, file_obj: BinaryIO, key: str, bucket: Optional[str] = None,
                       extra_args: Optional[Dict] = None) -> bool:
        """
        Sube un objeto file-like a S3

        Returns:
            True si se subió exitosamente
        """
        try:
            bucket_name = self._get_bucket(bucket)
            self.s3.upload_fileobj(file_obj, bucket_name, key, ExtraArgs=extra_args)
            logger.info(f"Fileobj subido: s3://{bucket_name}/{key}")
            return True
        except Exception as e:
            logger.error(f"Error subiendo fileobj a {key}: {str(e)}")
            raise

    # ================================================================
    # ===================== OPERACIONES DELETE =======================
    # ================================================================

    def delete(self, key: str, bucket: Optional[str] = None) -> bool:
        """
        Elimina un objeto de S3

        Returns:
            True si se eliminó exitosamente
        """
        try:
            bucket_name = self._get_bucket(bucket)
            self.s3.delete_object(Bucket=bucket_name, Key=key)
            logger.info(f"Objeto eliminado: s3://{bucket_name}/{key}")
            return True
        except Exception as e:
            logger.error(f"Error eliminando objeto {key}: {str(e)}")
            raise

    def delete_many(self, keys: List[str], bucket: Optional[str] = None) -> Dict[str, any]:
        """
        Elimina múltiples objetos de S3 (hasta 1000 por batch)

        Returns:
            Dict con resultado de la eliminación
        """
        try:
            bucket_name = self._get_bucket(bucket)

            if not keys:
                logger.warning("Lista de keys vacía para delete_many")
                return {"Deleted": [], "Errors": []}

            # S3 permite max 1000 objetos por request
            deleted = []
            errors = []

            for i in range(0, len(keys), 1000):
                batch = keys[i:i + 1000]
                objects = [{"Key": key} for key in batch]

                response = self.s3.delete_objects(
                    Bucket=bucket_name,
                    Delete={'Objects': objects}
                )

                deleted.extend(response.get('Deleted', []))
                errors.extend(response.get('Errors', []))

            logger.info(f"Eliminados {len(deleted)} objetos, {len(errors)} errores")
            return {"Deleted": deleted, "Errors": errors}
        except Exception as e:
            logger.error(f"Error en delete_many: {str(e)}")
            raise

    def delete_prefix(self, prefix: str, bucket: Optional[str] = None) -> int:
        """
        Elimina todos los objetos con un prefijo específico

        Returns:
            Número de objetos eliminados
        """
        try:
            keys = self.list_keys(prefix=prefix, bucket=bucket)
            if not keys:
                logger.info(f"No se encontraron objetos con prefijo: {prefix}")
                return 0

            result = self.delete_many(keys, bucket)
            deleted_count = len(result.get('Deleted', []))
            logger.info(f"Eliminados {deleted_count} objetos con prefijo: {prefix}")
            return deleted_count
        except Exception as e:
            logger.error(f"Error eliminando prefijo {prefix}: {str(e)}")
            raise

    # ================================================================
    # ===================== OPERACIONES LIST =========================
    # ================================================================

    def list_objects(self, prefix: str = "", bucket: Optional[str] = None,
                     max_keys: int = 1000, delimiter: Optional[str] = None) -> List[Dict]:
        """
        Lista objetos en S3 con paginación automática

        Returns:
            Lista de objetos (metadata completa)
        """
        try:
            bucket_name = self._get_bucket(bucket)
            objects = []

            paginator = self.s3.get_paginator('list_objects_v2')
            page_iterator = paginator.paginate(
                Bucket=bucket_name,
                Prefix=prefix,
                MaxKeys=max_keys,
                Delimiter=delimiter or ''
            )

            for page in page_iterator:
                if 'Contents' in page:
                    objects.extend(page['Contents'])

            logger.info(f"Listados {len(objects)} objetos con prefijo '{prefix}'")
            return objects
        except Exception as e:
            logger.error(f"Error listando objetos con prefijo {prefix}: {str(e)}")
            raise

    def list_keys(self, prefix: str = "", bucket: Optional[str] = None,
                  max_keys: int = 1000) -> List[str]:
        """
        Lista solo las keys de los objetos (sin metadata)

        Returns:
            Lista de keys
        """
        try:
            objects = self.list_objects(prefix, bucket, max_keys)
            keys = [obj['Key'] for obj in objects]
            logger.info(f"Encontradas {len(keys)} keys")
            return keys
        except Exception as e:
            logger.error(f"Error listando keys: {str(e)}")
            raise

    def list_folders(self, prefix: str = "", bucket: Optional[str] = None) -> List[str]:
        """
        Lista "carpetas" (prefijos comunes) en S3

        Returns:
            Lista de prefijos/carpetas
        """
        try:
            bucket_name = self._get_bucket(bucket)

            response = self.s3.list_objects_v2(
                Bucket=bucket_name,
                Prefix=prefix,
                Delimiter='/'
            )

            folders = []
            if 'CommonPrefixes' in response:
                folders = [cp['Prefix'] for cp in response['CommonPrefixes']]

            logger.info(f"Encontradas {len(folders)} carpetas en prefijo '{prefix}'")
            return folders
        except Exception as e:
            logger.error(f"Error listando carpetas: {str(e)}")
            raise

    # ================================================================
    # ===================== OPERACIONES COPY/MOVE ====================
    # ================================================================

    def copy(self, source_key: str, dest_key: str,
             source_bucket: Optional[str] = None,
             dest_bucket: Optional[str] = None,
             metadata: Optional[Dict] = None) -> bool:
        """
        Copia un objeto dentro de S3

        Returns:
            True si se copió exitosamente
        """
        try:
            src_bucket = self._get_bucket(source_bucket)
            dst_bucket = self._get_bucket(dest_bucket)

            copy_source = {'Bucket': src_bucket, 'Key': source_key}

            extra_args = {}
            if metadata:
                extra_args['Metadata'] = metadata
                extra_args['MetadataDirective'] = 'REPLACE'

            self.s3.copy_object(
                CopySource=copy_source,
                Bucket=dst_bucket,
                Key=dest_key,
                **extra_args
            )

            logger.info(f"Objeto copiado: s3://{src_bucket}/{source_key} -> s3://{dst_bucket}/{dest_key}")
            return True
        except Exception as e:
            logger.error(f"Error copiando objeto: {str(e)}")
            raise

    def move(self, source_key: str, dest_key: str,
             source_bucket: Optional[str] = None,
             dest_bucket: Optional[str] = None) -> bool:
        """
        Mueve un objeto (copia + elimina original)

        Returns:
            True si se movió exitosamente
        """
        try:
            # Copiar
            self.copy(source_key, dest_key, source_bucket, dest_bucket)

            # Eliminar original
            self.delete(source_key, source_bucket)

            src_bucket = self._get_bucket(source_bucket)
            dst_bucket = self._get_bucket(dest_bucket)
            logger.info(f"Objeto movido: s3://{src_bucket}/{source_key} -> s3://{dst_bucket}/{dest_key}")
            return True
        except Exception as e:
            logger.error(f"Error moviendo objeto: {str(e)}")
            raise

    # ================================================================
    # ===================== OPERACIONES DE UTILIDAD ==================
    # ================================================================

    def exists(self, key: str, bucket: Optional[str] = None) -> bool:
        """
        Verifica si un objeto existe en S3

        Returns:
            True si existe, False si no
        """
        try:
            bucket_name = self._get_bucket(bucket)
            self.s3.head_object(Bucket=bucket_name, Key=key)
            return True
        except ClientError as e:
            if e.response['Error']['Code'] == '404':
                return False
            logger.error(f"Error verificando existencia de {key}: {str(e)}")
            raise

    def get_metadata(self, key: str, bucket: Optional[str] = None) -> Optional[Dict]:
        """
        Obtiene metadata de un objeto sin descargar su contenido

        Returns:
            Dict con metadata o None si no existe
        """
        try:
            bucket_name = self._get_bucket(bucket)
            response = self.s3.head_object(Bucket=bucket_name, Key=key)

            metadata = {
                'ContentLength': response.get('ContentLength'),
                'ContentType': response.get('ContentType'),
                'LastModified': response.get('LastModified'),
                'ETag': response.get('ETag'),
                'Metadata': response.get('Metadata', {})
            }

            logger.info(f"Metadata obtenida para: {key}")
            return metadata
        except ClientError as e:
            if e.response['Error']['Code'] == '404':
                logger.warning(f"Objeto no encontrado: {key}")
                return None
            logger.error(f"Error obteniendo metadata de {key}: {str(e)}")
            raise

    def get_size(self, key: str, bucket: Optional[str] = None) -> Optional[int]:
        """
        Obtiene el tamaño de un objeto en bytes

        Returns:
            Tamaño en bytes o None si no existe
        """
        try:
            metadata = self.get_metadata(key, bucket)
            if metadata:
                return metadata.get('ContentLength')
            return None
        except Exception as e:
            logger.error(f"Error obteniendo tamaño de {key}: {str(e)}")
            raise

    def get_public_url(self, key: str, bucket: Optional[str] = None) -> str:
        """
        Obtiene la URL pública de un objeto (si el bucket es público)

        Returns:
            URL pública del objeto
        """
        bucket_name = self._get_bucket(bucket)
        return f"https://{bucket_name}.s3.{self.region_name}.amazonaws.com/{key}"

    # ================================================================
    # ===================== OPERACIONES BATCH ========================
    # ================================================================

    def batch_download(self, keys: List[str], local_dir: str,
                       bucket: Optional[str] = None) -> Dict[str, bool]:
        """
        Descarga múltiples archivos

        Returns:
            Dict con resultado por key {key: success}
        """
        results = {}
        os.makedirs(local_dir, exist_ok=True)

        for key in keys:
            try:
                filename = os.path.basename(key)
                local_path = os.path.join(local_dir, filename)
                self.download_file(key, local_path, bucket)
                results[key] = True
            except Exception as e:
                logger.error(f"Error descargando {key}: {str(e)}")
                results[key] = False

        success_count = sum(1 for v in results.values() if v)
        logger.info(f"Descarga batch: {success_count}/{len(keys)} exitosos")
        return results

    def batch_upload(self, files: List[Dict[str, str]], bucket: Optional[str] = None) -> Dict[str, bool]:
        """
        Sube múltiples archivos

        Args:
            files: Lista de dicts [{"local_path": "...", "key": "..."}, ...]

        Returns:
            Dict con resultado por key {key: success}
        """
        results = {}

        for file_info in files:
            local_path = file_info.get('local_path')
            key = file_info.get('key')

            if not local_path or not key:
                logger.warning(f"Información incompleta: {file_info}")
                results[key] = False
                continue

            try:
                self.upload_file(local_path, key, bucket)
                results[key] = True
            except Exception as e:
                logger.error(f"Error subiendo {local_path}: {str(e)}")
                results[key] = False

        success_count = sum(1 for v in results.values() if v)
        logger.info(f"Carga batch: {success_count}/{len(files)} exitosos")
        return results