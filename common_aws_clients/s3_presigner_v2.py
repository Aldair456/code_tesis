import boto3
from botocore.exceptions import ClientError, NoCredentialsError, BotoCoreError
from botocore.config import Config
from typing import List, Dict, Optional, Union, Tuple, BinaryIO, Generator, Any
import json
import logging
import sys
import os
import hashlib
import time
import mimetypes
from pathlib import Path
from io import BytesIO
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import wraps

# Configurar logging compatible con CloudWatch
logger = logging.getLogger(__name__)
logger.setLevel(os.environ.get('LOG_LEVEL', 'INFO'))

if not logger.handlers:
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter('[%(levelname)s] %(asctime)s %(name)s: %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)


# ==================== CONFIGURACIÓN LAMBDA ====================

class LambdaConfig:
    """
    Configuración centralizada optimizada para AWS Lambda

    Consideraciones Lambda:
        - Cada invocación maneja típicamente 1 request
        - Memoria limitada (128MB - 10GB)
        - Timeout máximo 15 minutos
        - Cold start: el cliente S3 se inicializa una vez y se reutiliza entre invocaciones
        - /tmp tiene máximo 10GB (configurable) de almacenamiento efímero
        - Credenciales vienen del IAM Role (no necesitan refresh manual)
    """

    # Región: preferir variable de entorno de Lambda
    DEFAULT_REGION = os.environ.get('AWS_REGION', os.environ.get('AWS_DEFAULT_REGION', 'us-east-1'))

    # Pool de conexiones: Lambda maneja pocas requests concurrentes
    # Debe ser >= max_workers del ThreadPoolExecutor
    MAX_POOL_CONNECTIONS = int(os.environ.get('S3_MAX_POOL_CONNECTIONS', '10'))

    # Retries: conservadores para no agotar el timeout de Lambda
    # mode='adaptive' agrega backoff inteligente ante throttling
    MAX_RETRY_ATTEMPTS = int(os.environ.get('S3_MAX_RETRIES', '2'))
    RETRY_MODE = 'adaptive'

    # Timeouts: agresivos para fallar rápido y dejar margen al timeout de Lambda
    CONNECT_TIMEOUT = int(os.environ.get('S3_CONNECT_TIMEOUT', '5'))
    READ_TIMEOUT = int(os.environ.get('S3_READ_TIMEOUT', '15'))

    # Multipart: ajustado para Lambda
    # En Lambda rara vez se suben archivos >100MB (limitados por memoria y /tmp)
    MULTIPART_THRESHOLD = int(os.environ.get('S3_MULTIPART_THRESHOLD', str(50 * 1024 * 1024)))  # 50 MB
    MULTIPART_CHUNKSIZE = int(os.environ.get('S3_MULTIPART_CHUNKSIZE', str(10 * 1024 * 1024)))  # 10 MB

    # Concurrencia para batch: limitada por CPU y memoria de Lambda
    # Lambda tiene 2 vCPUs por cada 1769 MB de memoria
    MAX_BATCH_WORKERS = int(os.environ.get('S3_MAX_BATCH_WORKERS', '3'))

    # Multipart concurrency: threads para subida/descarga de partes
    MAX_TRANSFER_CONCURRENCY = int(os.environ.get('S3_MAX_TRANSFER_CONCURRENCY', '5'))

    # Presigned URLs
    PRESIGN_DEFAULT_EXPIRATION = int(os.environ.get('S3_PRESIGN_EXPIRATION', '3600'))
    PRESIGN_MAX_EXPIRATION = 604800  # 7 días (límite de AWS)

    # Retry del decorador: menos agresivo que botocore para no duplicar waits
    DECORATOR_MAX_RETRIES = int(os.environ.get('S3_DECORATOR_RETRIES', '1'))
    DECORATOR_BACKOFF_BASE = float(os.environ.get('S3_DECORATOR_BACKOFF', '0.5'))

    # Directorio temporal de Lambda
    LAMBDA_TMP_DIR = '/tmp'


# ==================== DECORADORES ====================

def retry_on_error(
        max_retries: int = LambdaConfig.DECORATOR_MAX_RETRIES,
        backoff_base: float = LambdaConfig.DECORATOR_BACKOFF_BASE,
        retryable_codes: tuple = (
                'RequestTimeout', 'ServiceUnavailable', 'ThrottlingException',
                'TooManyRequestsException', 'InternalError', 'SlowDown',
        )
):
    """
    Decorador de retry con backoff exponencial para operaciones S3

    NOTA Lambda: botocore ya tiene retry interno (adaptive mode).
    Este decorador es una capa extra SOLO para errores que botocore no reintenta
    o cuando necesitamos lógica adicional (como resetear el cliente).
    Por eso max_retries=1 por defecto (1 reintento extra, no 3).

    Args:
        max_retries: Número máximo de reintentos (default 1 para Lambda)
        backoff_base: Base para backoff exponencial (default 0.5s para Lambda)
        retryable_codes: Códigos de error que permiten reintento
    """

    def decorator(func):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            last_exception = None

            for attempt in range(max_retries + 1):
                try:
                    return func(self, *args, **kwargs)

                except ClientError as e:
                    error_code = e.response.get('Error', {}).get('Code', '')
                    error_message = e.response.get('Error', {}).get('Message', '')
                    last_exception = e

                    if error_code in retryable_codes and attempt < max_retries:
                        wait_time = backoff_base * (2 ** attempt)
                        logger.warning(
                            f"Error retryable '{error_code}' en {func.__name__} "
                            f"(intento {attempt + 1}/{max_retries + 1}). "
                            f"Reintentando en {wait_time:.1f}s..."
                        )
                        time.sleep(wait_time)
                        continue

                    logger.error(f"✗ Error en {func.__name__}: [{error_code}] {error_message}")
                    raise

                except NoCredentialsError as e:
                    logger.error(f"✗ Sin credenciales AWS en {func.__name__}: {str(e)}")
                    raise

                except BotoCoreError as e:
                    last_exception = e
                    if attempt < max_retries:
                        wait_time = backoff_base * (2 ** attempt)
                        logger.warning(
                            f"Error BotoCore en {func.__name__} "
                            f"(intento {attempt + 1}/{max_retries + 1}). "
                            f"Reintentando en {wait_time:.1f}s..."
                        )
                        time.sleep(wait_time)
                        continue
                    raise

                except Exception as e:
                    logger.error(f"✗ Error inesperado en {func.__name__}: {str(e)}")
                    raise

            raise last_exception

        return wrapper

    return decorator


# ==================== CONTENT TYPE DETECTOR ====================

class ContentTypeDetector:
    """Detector avanzado de Content-Type con mapeo exhaustivo"""

    CONTENT_TYPE_MAP = {
        # Imágenes
        '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.png': 'image/png',
        '.gif': 'image/gif', '.webp': 'image/webp', '.svg': 'image/svg+xml',
        '.ico': 'image/x-icon', '.bmp': 'image/bmp', '.tiff': 'image/tiff',
        '.tif': 'image/tiff', '.heic': 'image/heic', '.heif': 'image/heif',
        '.avif': 'image/avif',

        # Videos
        '.mp4': 'video/mp4', '.avi': 'video/x-msvideo', '.mov': 'video/quicktime',
        '.wmv': 'video/x-ms-wmv', '.flv': 'video/x-flv', '.webm': 'video/webm',
        '.mkv': 'video/x-matroska', '.m4v': 'video/x-m4v', '.mpeg': 'video/mpeg',
        '.mpg': 'video/mpeg',

        # Audio
        '.mp3': 'audio/mpeg', '.wav': 'audio/wav', '.ogg': 'audio/ogg',
        '.m4a': 'audio/mp4', '.flac': 'audio/flac', '.aac': 'audio/aac',
        '.wma': 'audio/x-ms-wma', '.opus': 'audio/opus',

        # Documentos
        '.pdf': 'application/pdf', '.doc': 'application/msword',
        '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        '.xls': 'application/vnd.ms-excel',
        '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        '.ppt': 'application/vnd.ms-powerpoint',
        '.pptx': 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
        '.odt': 'application/vnd.oasis.opendocument.text',
        '.ods': 'application/vnd.oasis.opendocument.spreadsheet',
        '.odp': 'application/vnd.oasis.opendocument.presentation',

        # Texto y código
        '.txt': 'text/plain', '.csv': 'text/csv', '.tsv': 'text/tab-separated-values',
        '.log': 'text/plain', '.md': 'text/markdown', '.rtf': 'application/rtf',
        '.yaml': 'text/yaml', '.yml': 'text/yaml', '.ini': 'text/plain',
        '.cfg': 'text/plain', '.conf': 'text/plain', '.env': 'text/plain',

        # Web
        '.html': 'text/html', '.htm': 'text/html', '.css': 'text/css',
        '.js': 'application/javascript', '.mjs': 'application/javascript',
        '.json': 'application/json', '.xml': 'application/xml',
        '.rss': 'application/rss+xml', '.wasm': 'application/wasm',
        '.map': 'application/json',

        # Comprimidos
        '.zip': 'application/zip', '.rar': 'application/x-rar-compressed',
        '.tar': 'application/x-tar', '.gz': 'application/gzip',
        '.7z': 'application/x-7z-compressed', '.bz2': 'application/x-bzip2',
        '.xz': 'application/x-xz', '.zst': 'application/zstd',
        '.tar.gz': 'application/gzip', '.tgz': 'application/gzip',

        # Fuentes
        '.ttf': 'font/ttf', '.otf': 'font/otf', '.woff': 'font/woff',
        '.woff2': 'font/woff2', '.eot': 'application/vnd.ms-fontobject',

        # Otros
        '.apk': 'application/vnd.android.package-archive',
        '.epub': 'application/epub+zip',
        '.psd': 'image/vnd.adobe.photoshop',
        '.ai': 'application/postscript',
        '.parquet': 'application/vnd.apache.parquet',
        '.arrow': 'application/vnd.apache.arrow.file',
    }

    # Cache del mapeo inverso (se construye una sola vez en la vida del container Lambda)
    _EXTENSION_FROM_TYPE_CACHE: Dict[str, str] = None

    PREFERRED_EXTENSIONS = {
        'image/jpeg': '.jpg',
        'image/tiff': '.tiff',
        'video/mpeg': '.mpeg',
        'text/html': '.html',
        'application/javascript': '.js',
    }

    @classmethod
    def _build_inverse_map(cls) -> Dict[str, str]:
        """Construye el mapeo inverso (lazy, persiste entre invocaciones Lambda)"""
        if cls._EXTENSION_FROM_TYPE_CACHE is not None:
            return cls._EXTENSION_FROM_TYPE_CACHE

        inverse = {}
        for ext, ct in cls.CONTENT_TYPE_MAP.items():
            ct_lower = ct.lower()
            if ct_lower not in inverse:
                inverse[ct_lower] = ext

        for ct, ext in cls.PREFERRED_EXTENSIONS.items():
            inverse[ct.lower()] = ext

        cls._EXTENSION_FROM_TYPE_CACHE = inverse
        return inverse

    @classmethod
    def detect(cls, key: str) -> str:
        """Detecta content-type desde la extensión del archivo"""
        ext = Path(key).suffix.lower()

        if ext in cls.CONTENT_TYPE_MAP:
            return cls.CONTENT_TYPE_MAP[ext]

        guessed_type, _ = mimetypes.guess_type(key)
        return guessed_type or 'application/octet-stream'

    @classmethod
    def detect_extension(cls, content_type: str) -> str:
        """
        Detecta la extensión desde un content-type (inverso de detect)

        Args:
            content_type: MIME type (ej: 'image/jpeg', 'application/pdf; charset=utf-8')

        Returns:
            Extensión con punto (ej: '.jpg', '.pdf') o '.bin' si no se reconoce
        """
        clean_type = content_type.split(';')[0].strip().lower()

        inverse = cls._build_inverse_map()
        if clean_type in inverse:
            return inverse[clean_type]

        guessed_ext = mimetypes.guess_extension(clean_type, strict=False)
        if guessed_ext:
            return guessed_ext

        return '.bin'

    @classmethod
    def is_text_type(cls, content_type: str) -> bool:
        text_prefixes = ['text/', 'application/json', 'application/xml', 'application/javascript']
        return any(content_type.startswith(p) for p in text_prefixes)

    @classmethod
    def is_image_type(cls, content_type: str) -> bool:
        return content_type.split(';')[0].strip().lower().startswith('image/')

    @classmethod
    def is_video_type(cls, content_type: str) -> bool:
        return content_type.split(';')[0].strip().lower().startswith('video/')

    @classmethod
    def is_audio_type(cls, content_type: str) -> bool:
        return content_type.split(';')[0].strip().lower().startswith('audio/')


# ==================== CLIENTE S3 SINGLETON (NIVEL MÓDULO) ====================

# IMPORTANTE LAMBDA: El cliente se crea a nivel de módulo para que persista
# entre invocaciones (warm start). Esto evita el costo de re-crear el cliente
# en cada invocación. Lambda congela el container y lo reutiliza.

def _create_s3_client(region_name: str = LambdaConfig.DEFAULT_REGION):
    """
    Crea el cliente S3 con configuración optimizada para Lambda

    Se llama UNA vez en cold start y el cliente se reutiliza en warm starts.
    """
    config = Config(
        region_name=region_name,
        retries={
            'max_attempts': LambdaConfig.MAX_RETRY_ATTEMPTS,
            'mode': LambdaConfig.RETRY_MODE,
        },
        max_pool_connections=LambdaConfig.MAX_POOL_CONNECTIONS,
        connect_timeout=LambdaConfig.CONNECT_TIMEOUT,
        read_timeout=LambdaConfig.READ_TIMEOUT,
    )

    logger.info(
        f"Creando cliente S3: region={region_name}, "
        f"retries={LambdaConfig.MAX_RETRY_ATTEMPTS} ({LambdaConfig.RETRY_MODE}), "
        f"pool={LambdaConfig.MAX_POOL_CONNECTIONS}, "
        f"timeouts=connect:{LambdaConfig.CONNECT_TIMEOUT}s/read:{LambdaConfig.READ_TIMEOUT}s"
    )

    return boto3.client("s3", config=config)


# Cliente singleton a nivel de módulo (persiste entre invocaciones Lambda)
_s3_client = _create_s3_client()


# ==================== S3 SERVICE PRINCIPAL ====================

class S3Service:
    """
    Servicio robusto para operaciones S3 optimizado para AWS Lambda

    Optimizaciones Lambda:
        - Cliente S3 singleton a nivel de módulo (sobrevive warm starts)
        - Config de botocore con retry adaptive + timeouts agresivos
        - Pool de conexiones reducido (10 vs 50)
        - Decorador retry conservador (1 reintento vs 3) para no duplicar con botocore
        - Backoff reducido (0.5s base vs 1s) para no agotar timeout Lambda
        - Multipart threshold/chunk ajustados para memoria Lambda
        - Batch workers limitados (3) por CPU limitada en Lambda
        - Toda configuración overrideable via variables de entorno
        - Directorio temporal en /tmp (único writable en Lambda)

    Variables de entorno soportadas:
        S3_MAX_POOL_CONNECTIONS, S3_MAX_RETRIES, S3_CONNECT_TIMEOUT,
        S3_READ_TIMEOUT, S3_MULTIPART_THRESHOLD, S3_MULTIPART_CHUNKSIZE,
        S3_MAX_BATCH_WORKERS, S3_MAX_TRANSFER_CONCURRENCY,
        S3_PRESIGN_EXPIRATION, S3_DECORATOR_RETRIES, S3_DECORATOR_BACKOFF,
        LOG_LEVEL
    """

    def __init__(
            self,
            bucket_name: str,
            auto_detect_content_type: bool = True,
            multipart_threshold: int = LambdaConfig.MULTIPART_THRESHOLD,
            multipart_chunksize: int = LambdaConfig.MULTIPART_CHUNKSIZE,
    ):
        """
        Inicializa el servicio S3

        Args:
            bucket_name: Nombre del bucket S3 (o usar env S3_BUCKET_NAME)
            auto_detect_content_type: Detectar automáticamente content-type
            multipart_threshold: Umbral en bytes para multipart upload
            multipart_chunksize: Tamaño de cada parte en multipart upload
        """
        self.bucket_name = bucket_name or os.environ.get('S3_BUCKET_NAME', '')
        self.auto_detect_content_type = auto_detect_content_type
        self.multipart_threshold = multipart_threshold
        self.multipart_chunksize = multipart_chunksize
        self.content_detector = ContentTypeDetector()

        if not self.bucket_name:
            raise ValueError("bucket_name es requerido (parámetro o env S3_BUCKET_NAME)")

        logger.info(
            f"S3Service inicializado: bucket={self.bucket_name}, "
            f"multipart_threshold={multipart_threshold / (1024 * 1024):.0f}MB"
        )

    @property
    def client(self):
        """
        Acceso al cliente S3 singleton

        En Lambda, el cliente persiste entre invocaciones (warm start).
        Las credenciales del IAM Role se refrescan automáticamente por botocore.
        """
        return _s3_client

    def _get_transfer_config(self):
        """Crea TransferConfig reutilizable para upload/download"""
        from boto3.s3.transfer import TransferConfig
        return TransferConfig(
            multipart_threshold=self.multipart_threshold,
            multipart_chunksize=self.multipart_chunksize,
            max_concurrency=LambdaConfig.MAX_TRANSFER_CONCURRENCY,
            use_threads=True,
        )

    def _resolve_content_type(self, key: str, content_type: Optional[str] = None) -> str:
        """Resuelve content-type: explícito > auto-detectado > default"""
        if content_type:
            return content_type
        if self.auto_detect_content_type:
            return self.content_detector.detect(key)
        return 'application/octet-stream'

    def _build_extra_args(
            self,
            content_type: Optional[str] = None,
            metadata: Optional[Dict[str, str]] = None,
            acl: Optional[str] = None,
            storage_class: Optional[str] = None,
            server_side_encryption: Optional[str] = None,
            cache_control: Optional[str] = None,
            content_disposition: Optional[str] = None,
            content_encoding: Optional[str] = None,
            tagging: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Construye ExtraArgs para operaciones S3"""
        extra_args = {}

        if content_type:
            extra_args['ContentType'] = content_type
        if metadata:
            extra_args['Metadata'] = metadata
        if acl:
            extra_args['ACL'] = acl
        if storage_class:
            extra_args['StorageClass'] = storage_class
        if server_side_encryption:
            extra_args['ServerSideEncryption'] = server_side_encryption
        if cache_control:
            extra_args['CacheControl'] = cache_control
        if content_disposition:
            extra_args['ContentDisposition'] = content_disposition
        if content_encoding:
            extra_args['ContentEncoding'] = content_encoding
        if tagging:
            extra_args['Tagging'] = tagging

        return extra_args

    # ==================== VERIFICACIÓN ====================

    @retry_on_error()
    def exists(self, key: str) -> bool:
        """Verifica si un objeto existe en S3"""
        try:
            self.client.head_object(Bucket=self.bucket_name, Key=key)
            return True
        except ClientError as e:
            if e.response['Error']['Code'] in ('404', 'NoSuchKey'):
                return False
            raise

    @retry_on_error()
    def get_metadata(self, key: str) -> Optional[Dict[str, Any]]:
        """Obtiene metadatos completos de un objeto"""
        try:
            response = self.client.head_object(Bucket=self.bucket_name, Key=key)

            return {
                'key': key,
                'bucket': self.bucket_name,
                'size': response.get('ContentLength', 0),
                'size_human': self._format_size(response.get('ContentLength', 0)),
                'content_type': response.get('ContentType', 'unknown'),
                'last_modified': response.get('LastModified'),
                'etag': response.get('ETag', '').strip('"'),
                'metadata': response.get('Metadata', {}),
                'storage_class': response.get('StorageClass', 'STANDARD'),
                'content_encoding': response.get('ContentEncoding'),
                'cache_control': response.get('CacheControl'),
                'content_disposition': response.get('ContentDisposition'),
                'server_side_encryption': response.get('ServerSideEncryption'),
                'version_id': response.get('VersionId'),
            }

        except ClientError as e:
            if e.response['Error']['Code'] in ('404', 'NoSuchKey'):
                logger.warning(f"Objeto no encontrado: {key}")
                return None
            raise

    # ==================== UPLOAD ====================

    @retry_on_error()
    def upload_bytes(
            self,
            key: str,
            data: bytes,
            content_type: Optional[str] = None,
            metadata: Optional[Dict[str, str]] = None,
            acl: Optional[str] = None,
            storage_class: Optional[str] = None,
            server_side_encryption: Optional[str] = None,
            cache_control: Optional[str] = None,
            tagging: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Sube bytes directamente a S3

        Args:
            key: Ruta destino en S3
            data: Bytes a subir
            content_type: Content-Type (None para auto-detección)
            metadata: Metadatos personalizados
            acl: ACL del objeto
            storage_class: Clase de almacenamiento (STANDARD, GLACIER, etc)
            server_side_encryption: Encriptación server-side (AES256, aws:kms)
            cache_control: Header Cache-Control
            tagging: Tags del objeto (key1=value1&key2=value2)

        Returns:
            Diccionario con resultado de la operación
        """
        resolved_ct = self._resolve_content_type(key, content_type)
        extra_args = self._build_extra_args(
            content_type=resolved_ct, metadata=metadata, acl=acl,
            storage_class=storage_class, server_side_encryption=server_side_encryption,
            cache_control=cache_control, tagging=tagging,
        )

        md5_hash = hashlib.md5(data).hexdigest()

        response = self.client.put_object(
            Bucket=self.bucket_name,
            Key=key,
            Body=data,
            **extra_args
        )

        result = {
            'key': key,
            'bucket': self.bucket_name,
            'size': len(data),
            'size_human': self._format_size(len(data)),
            'content_type': resolved_ct,
            'etag': response.get('ETag', '').strip('"'),
            'md5': md5_hash,
            'version_id': response.get('VersionId'),
            'server_side_encryption': response.get('ServerSideEncryption'),
        }

        logger.info(f"✓ Upload completado: {key} ({result['size_human']}, {resolved_ct})")
        return result

    def upload_text(
            self,
            key: str,
            text: str,
            encoding: str = 'utf-8',
            content_type: Optional[str] = None,
            **kwargs
    ) -> Dict[str, Any]:
        """Sube texto a S3"""
        data = text.encode(encoding)

        if content_type is None:
            ct = self._resolve_content_type(key)
            content_type = f"{ct}; charset={encoding}" if self.content_detector.is_text_type(ct) else ct

        return self.upload_bytes(key=key, data=data, content_type=content_type, **kwargs)

    def upload_json(
            self,
            key: str,
            obj: Any,
            indent: Optional[int] = None,
            ensure_ascii: bool = False,
            **kwargs
    ) -> Dict[str, Any]:
        """Sube un objeto como JSON a S3"""
        json_str = json.dumps(obj, indent=indent, ensure_ascii=ensure_ascii, default=str)
        return self.upload_text(
            key=key,
            text=json_str,
            content_type='application/json; charset=utf-8',
            **kwargs
        )

    @retry_on_error()
    def upload_file(
            self,
            key: str,
            file_path: str,
            content_type: Optional[str] = None,
            metadata: Optional[Dict[str, str]] = None,
            acl: Optional[str] = None,
            storage_class: Optional[str] = None,
            server_side_encryption: Optional[str] = None,
            cache_control: Optional[str] = None,
            tagging: Optional[str] = None,
            callback: Optional[callable] = None,
    ) -> Dict[str, Any]:
        """
        Sube un archivo local a S3 (usa multipart automáticamente para archivos grandes)

        En Lambda, file_path típicamente está en /tmp/
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Archivo no encontrado: {file_path}")

        file_size = path.stat().st_size
        resolved_ct = self._resolve_content_type(key, content_type)
        extra_args = self._build_extra_args(
            content_type=resolved_ct, metadata=metadata, acl=acl,
            storage_class=storage_class, server_side_encryption=server_side_encryption,
            cache_control=cache_control, tagging=tagging,
        )

        upload_method = "multipart" if file_size > self.multipart_threshold else "standard"
        logger.info(
            f"Subiendo {file_path} → s3://{self.bucket_name}/{key} "
            f"({self._format_size(file_size)}, método: {upload_method})"
        )

        self.client.upload_file(
            Filename=str(path),
            Bucket=self.bucket_name,
            Key=key,
            ExtraArgs=extra_args,
            Config=self._get_transfer_config(),
            Callback=callback,
        )

        result = {
            'key': key,
            'bucket': self.bucket_name,
            'source_path': str(path),
            'size': file_size,
            'size_human': self._format_size(file_size),
            'content_type': resolved_ct,
            'upload_method': upload_method,
        }

        logger.info(f"✓ Upload archivo completado: {key} ({result['size_human']})")
        return result

    @retry_on_error()
    def upload_fileobj(
            self,
            key: str,
            fileobj: BinaryIO,
            content_type: Optional[str] = None,
            metadata: Optional[Dict[str, str]] = None,
            **kwargs
    ) -> Dict[str, Any]:
        """Sube un file-like object a S3"""
        resolved_ct = self._resolve_content_type(key, content_type)
        extra_args = self._build_extra_args(content_type=resolved_ct, metadata=metadata, **kwargs)

        self.client.upload_fileobj(
            Fileobj=fileobj,
            Bucket=self.bucket_name,
            Key=key,
            ExtraArgs=extra_args,
            Config=self._get_transfer_config(),
        )

        logger.info(f"✓ Upload fileobj completado: {key}")
        return {'key': key, 'bucket': self.bucket_name, 'content_type': resolved_ct}

    # ==================== DOWNLOAD ====================

    @retry_on_error()
    def download_bytes(self, key: str, byte_range: Optional[str] = None) -> Optional[bytes]:
        """Descarga un objeto como bytes"""
        try:
            params = {'Bucket': self.bucket_name, 'Key': key}
            if byte_range:
                params['Range'] = byte_range

            response = self.client.get_object(**params)
            data = response['Body'].read()

            logger.info(f"✓ Download bytes: {key} ({self._format_size(len(data))})")
            return data

        except ClientError as e:
            if e.response['Error']['Code'] in ('NoSuchKey', '404'):
                logger.warning(f"Objeto no encontrado: {key}")
                return None
            raise

    def download_text(self, key: str, encoding: str = 'utf-8') -> Optional[str]:
        """Descarga un objeto como texto"""
        data = self.download_bytes(key)
        return data.decode(encoding) if data is not None else None

    def download_json(self, key: str) -> Optional[Any]:
        """Descarga un objeto JSON y lo deserializa"""
        text = self.download_text(key)
        return json.loads(text) if text is not None else None

    @retry_on_error()
    def download_file(
            self,
            key: str,
            file_path: Optional[str] = None,
            callback: Optional[callable] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Descarga un objeto a un archivo local

        Args:
            key: Ruta del objeto en S3
            file_path: Ruta local destino (default: /tmp/{filename})
            callback: Callback de progreso
        """
        # En Lambda, default a /tmp/
        if file_path is None:
            file_path = os.path.join(LambdaConfig.LAMBDA_TMP_DIR, Path(key).name)

        try:
            meta = self.get_metadata(key)
            if meta is None:
                return None

            Path(file_path).parent.mkdir(parents=True, exist_ok=True)

            self.client.download_file(
                Bucket=self.bucket_name,
                Key=key,
                Filename=file_path,
                Config=self._get_transfer_config(),
                Callback=callback,
            )

            result = {
                'key': key,
                'bucket': self.bucket_name,
                'local_path': file_path,
                'size': meta['size'],
                'size_human': meta['size_human'],
                'content_type': meta['content_type'],
            }

            logger.info(f"✓ Download archivo: {key} → {file_path} ({meta['size_human']})")
            return result

        except ClientError as e:
            if e.response['Error']['Code'] in ('NoSuchKey', '404'):
                logger.warning(f"Objeto no encontrado: {key}")
                return None
            raise

    @retry_on_error()
    def download_fileobj(self, key: str, fileobj: BinaryIO) -> bool:
        """Descarga un objeto a un file-like object"""
        self.client.download_fileobj(
            Bucket=self.bucket_name,
            Key=key,
            Fileobj=fileobj,
            Config=self._get_transfer_config(),
        )
        logger.info(f"✓ Download fileobj: {key}")
        return True

    def stream_download(self, key: str, chunk_size: int = 8192) -> Generator[bytes, None, None]:
        """
        Descarga en streaming (generador de chunks)

        Útil en Lambda para procesar archivos grandes sin cargarlos completos en memoria.
        """
        try:
            response = self.client.get_object(Bucket=self.bucket_name, Key=key)
            body = response['Body']

            while True:
                chunk = body.read(chunk_size)
                if not chunk:
                    break
                yield chunk

            body.close()
            logger.info(f"✓ Stream download: {key}")

        except ClientError as e:
            if e.response['Error']['Code'] in ('NoSuchKey', '404'):
                logger.warning(f"Objeto no encontrado para streaming: {key}")
                return
            raise

    # ==================== DELETE ====================

    @retry_on_error()
    def delete(self, key: str) -> bool:
        """Elimina un objeto de S3"""
        self.client.delete_object(Bucket=self.bucket_name, Key=key)
        logger.info(f"✓ Delete: {key}")
        return True

    @retry_on_error()
    def delete_batch(self, keys: List[str]) -> Dict[str, Any]:
        """Elimina múltiples objetos (max 1000 por llamada a S3)"""
        all_deleted = []
        all_errors = []

        for i in range(0, len(keys), 1000):
            batch = keys[i:i + 1000]
            objects = [{'Key': key} for key in batch]

            response = self.client.delete_objects(
                Bucket=self.bucket_name,
                Delete={'Objects': objects, 'Quiet': False}
            )

            all_deleted.extend([d['Key'] for d in response.get('Deleted', [])])
            all_errors.extend([
                {'key': e['Key'], 'code': e.get('Code', ''), 'message': e.get('Message', '')}
                for e in response.get('Errors', [])
            ])

        result = {
            'deleted': all_deleted,
            'deleted_count': len(all_deleted),
            'errors': all_errors,
            'error_count': len(all_errors),
        }

        logger.info(f"✓ Delete batch: {len(all_deleted)} eliminados, {len(all_errors)} errores")
        return result

    @retry_on_error()
    def delete_prefix(self, prefix: str, dry_run: bool = False) -> Dict[str, Any]:
        """Elimina todos los objetos con un prefijo"""
        keys = [obj['key'] for obj in self.list_objects(prefix=prefix, max_keys=100000)]

        if dry_run:
            logger.info(f"DRY RUN: Se eliminarían {len(keys)} objetos con prefijo '{prefix}'")
            return {'dry_run': True, 'would_delete': keys, 'count': len(keys)}

        if not keys:
            return {'deleted': [], 'deleted_count': 0, 'errors': [], 'error_count': 0}

        return self.delete_batch(keys)

    # ==================== COPY / MOVE ====================

    @retry_on_error()
    def copy(
            self,
            source_key: str,
            dest_key: str,
            dest_bucket: Optional[str] = None,
            metadata: Optional[Dict[str, str]] = None,
            content_type: Optional[str] = None,
            acl: Optional[str] = None,
            storage_class: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Copia un objeto dentro de S3"""
        dest_bucket = dest_bucket or self.bucket_name
        copy_source = {'Bucket': self.bucket_name, 'Key': source_key}

        extra_args = {}
        if metadata is not None:
            extra_args['Metadata'] = metadata
            extra_args['MetadataDirective'] = 'REPLACE'

        if content_type:
            extra_args['ContentType'] = content_type
            if 'MetadataDirective' not in extra_args:
                extra_args['MetadataDirective'] = 'REPLACE'

        if acl:
            extra_args['ACL'] = acl
        if storage_class:
            extra_args['StorageClass'] = storage_class

        response = self.client.copy_object(
            Bucket=dest_bucket, Key=dest_key, CopySource=copy_source, **extra_args
        )

        result = {
            'source_key': source_key,
            'source_bucket': self.bucket_name,
            'dest_key': dest_key,
            'dest_bucket': dest_bucket,
            'etag': response.get('CopyObjectResult', {}).get('ETag', '').strip('"'),
        }

        logger.info(f"✓ Copy: {source_key} → {dest_bucket}/{dest_key}")
        return result

    def move(self, source_key: str, dest_key: str, dest_bucket: Optional[str] = None, **kwargs) -> Dict[str, Any]:
        """Mueve un objeto (copy + delete)"""
        copy_result = self.copy(source_key, dest_key, dest_bucket=dest_bucket, **kwargs)
        self.delete(source_key)
        copy_result['operation'] = 'move'
        copy_result['source_deleted'] = True
        logger.info(f"✓ Move: {source_key} → {dest_bucket or self.bucket_name}/{dest_key}")
        return copy_result

    def rename(self, source_key: str, dest_key: str) -> Dict[str, Any]:
        """Renombra un objeto (alias de move)"""
        return self.move(source_key, dest_key)

    # ==================== LISTADO ====================

    def list_objects(
            self,
            prefix: str = "",
            max_keys: int = 1000,
            delimiter: Optional[str] = None,
            start_after: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Lista objetos con paginación automática"""
        objects = []
        paginator = self.client.get_paginator('list_objects_v2')

        params = {
            'Bucket': self.bucket_name,
            'Prefix': prefix,
            'PaginationConfig': {'MaxItems': max_keys, 'PageSize': min(max_keys, 1000)}
        }

        if delimiter:
            params['Delimiter'] = delimiter
        if start_after:
            params['StartAfter'] = start_after

        try:
            for page in paginator.paginate(**params):
                for obj in page.get('Contents', []):
                    objects.append({
                        'key': obj['Key'],
                        'size': obj['Size'],
                        'size_human': self._format_size(obj['Size']),
                        'last_modified': obj['LastModified'],
                        'etag': obj['ETag'].strip('"'),
                        'storage_class': obj.get('StorageClass', 'STANDARD'),
                    })

                if len(objects) >= max_keys:
                    objects = objects[:max_keys]
                    break

            logger.info(f"Listados {len(objects)} objetos con prefijo '{prefix}'")
            return objects

        except ClientError as e:
            logger.error(f"Error listando objetos: {str(e)}")
            return []

    def list_prefixes(self, prefix: str = "", delimiter: str = "/") -> List[str]:
        """Lista prefijos comunes (directorios virtuales)"""
        prefixes = []
        paginator = self.client.get_paginator('list_objects_v2')

        try:
            for page in paginator.paginate(
                    Bucket=self.bucket_name, Prefix=prefix, Delimiter=delimiter
            ):
                for cp in page.get('CommonPrefixes', []):
                    prefixes.append(cp['Prefix'])

            logger.info(f"Listados {len(prefixes)} prefijos bajo '{prefix}'")
            return prefixes

        except ClientError as e:
            logger.error(f"Error listando prefijos: {str(e)}")
            return []

    # ==================== PRESIGNED URLS ====================

    def _validate_expiration(self, expiration: int) -> int:
        """Valida y sanitiza el tiempo de expiración"""
        expiration = int(expiration)

        if expiration > 1_000_000_000:
            logger.error(f"ERROR: expiration parece ser timestamp Unix ({expiration}), no duración")
            return LambdaConfig.PRESIGN_DEFAULT_EXPIRATION

        return max(1, min(expiration, LambdaConfig.PRESIGN_MAX_EXPIRATION))

    @retry_on_error()
    def generate_presigned_url(
            self,
            method: str,
            key: str,
            expiration: int = LambdaConfig.PRESIGN_DEFAULT_EXPIRATION,
            content_type: Optional[str] = None,
            extra_params: Optional[Dict] = None,
    ) -> Optional[str]:
        """Genera URL prefirmada genérica"""
        expiration = self._validate_expiration(expiration)
        params = {"Bucket": self.bucket_name, "Key": key}

        if content_type and method in ('put_object', 'post_object'):
            params["ContentType"] = content_type
        elif content_type is None and method in ('put_object', 'post_object') and self.auto_detect_content_type:
            params["ContentType"] = self.content_detector.detect(key)

        if extra_params:
            params.update(extra_params)

        url = self.client.generate_presigned_url(
            ClientMethod=method, Params=params, ExpiresIn=expiration
        )

        logger.info(f"✓ Presigned URL: method={method}, key={key}, expires_in={expiration}s")
        return url

    def presign_get(
            self,
            key: str,
            expiration: int = LambdaConfig.PRESIGN_DEFAULT_EXPIRATION,
            response_content_type: Optional[str] = None,
            response_content_disposition: Optional[str] = None,
    ) -> Optional[str]:
        """URL prefirmada para descargar (GET)"""
        extra_params = {}
        if response_content_type:
            extra_params['ResponseContentType'] = response_content_type
        if response_content_disposition:
            extra_params['ResponseContentDisposition'] = response_content_disposition

        return self.generate_presigned_url(
            method="get_object", key=key, expiration=expiration,
            extra_params=extra_params or None,
        )

    def presign_get_inline(self, key: str, expiration: int = LambdaConfig.PRESIGN_DEFAULT_EXPIRATION) -> Optional[str]:
        """URL prefirmada para ver en navegador (inline)"""
        return self.presign_get(key, expiration, response_content_disposition='inline')

    def presign_get_download(
            self,
            key: str,
            download_filename: Optional[str] = None,
            expiration: int = LambdaConfig.PRESIGN_DEFAULT_EXPIRATION,
    ) -> Optional[str]:
        """URL prefirmada forzando descarga"""
        filename = download_filename or Path(key).name
        return self.presign_get(
            key, expiration,
            response_content_disposition=f'attachment; filename="{filename}"',
        )

    def presign_put(
            self,
            key: str,
            expiration: int = LambdaConfig.PRESIGN_DEFAULT_EXPIRATION,
            content_type: Optional[str] = None,
    ) -> Optional[str]:
        """URL prefirmada para subir (PUT)"""
        return self.generate_presigned_url(
            method="put_object", key=key, expiration=expiration, content_type=content_type,
        )

    def presign_delete(self, key: str, expiration: int = LambdaConfig.PRESIGN_DEFAULT_EXPIRATION) -> Optional[str]:
        """URL prefirmada para eliminar (DELETE)"""
        return self.generate_presigned_url(method="delete_object", key=key, expiration=expiration)
def generate_upload_presigned_urls(
    self,
    user: Dict[str, Any],
    deal_id: str,
    files_data: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Genera URLs prefirmadas para subir archivos a un deal.

    Crea los registros en BD y devuelve las URLs para que el cliente suba directamente a S3.

    Args:
        user: Diccionario con información del usuario
        deal_id: UUID del deal
        files_data: Lista de archivos con original_name, category, file_type, file_size, description, file_index

    Returns:
        Dict con deal_id, total_files, expires_at y lista de presigned_urls

    Raises:
        ServiceDataValidationError: Si los datos no son válidos
        NotFoundError: Si el deal no existe
        ServiceError: Si hay errores en el proceso
    """
    try:
        user_id = self._extract_user_id(user)
        evaluator_id = self._extract_evaluator_id(user)

        logger.info(f"Usuario {user_id} generando URLs para {len(files_data)} archivos en deal {deal_id}")

        # Validar deal_id
        validated_deal_id = self._validate_uuid(deal_id, "deal_id")

        # Verificar que el deal existe
        deal = self.deal_repository.find_by_id(validated_deal_id)
        self._found_object(deal, f"Deal con ID {validated_deal_id} no encontrado")

        # Validar que no esté vacío
        if not files_data:
            raise ServiceDataValidationError("Se requiere al menos un archivo")

        presigned_urls = []
        expiration_seconds = 3600  # 1 hora
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=expiration_seconds)

        for file_info in files_data:
            # Generar UUID único para el archivo
            file_id = str(uuid.uuid4())

            # Construir S3 key: deals/{deal_id}/{file_id}/{original_name}
            original_name = file_info["original_name"]
            s3_key = f"deals/{validated_deal_id}/{file_id}/{original_name}"

            # Crear registro en BD
            file_record = {
                "id": file_id,
                "deal_id": validated_deal_id,
                "s3_key": s3_key,
                "original_name": original_name,
                "category": file_info["category"],
                "file_type": file_info["file_type"],
                "file_size": file_info.get("file_size"),
                "uploaded_by": user_id,
                "description": file_info.get("description"),
            }

            created_file = self.deal_file_repository.create(file_record)

            if not created_file:
                raise ServiceError(f"Error al crear registro para archivo {original_name}")

            # Generar URL prefirmada para PUT
            upload_url = self.s3_service.presign_put(
                key=s3_key,
                expiration=expiration_seconds,
                content_type=file_info["file_type"]
            )

            if not upload_url:
                raise ServiceError(f"Error al generar URL prefirmada para {original_name}")

            presigned_urls.append({
                "file_index": file_info["file_index"],
                "file_id": file_id,
                "s3_key": s3_key,
                "upload_url": upload_url,
                "expires_in": expiration_seconds,
            })

        result = {
            "deal_id": validated_deal_id,
            "total_files": len(presigned_urls),
            "expires_at": expires_at.isoformat(),
            "presigned_urls": presigned_urls,
        }

        logger.info(f"Generadas {len(presigned_urls)} URLs prefirmadas para deal {validated_deal_id}")
        return result

    except (ServiceDataValidationError, NotFoundError):
        raise
    except Exception as e:
        error_msg = f"Error inesperado al generar URLs prefirmadas: {str(e)}"
        logger.error(error_msg)
        raise ServiceError(error_msg) from e


def get_deal_files(
    self,
    user: Dict[str, Any],
    deal_id: str,
    category: str = None
) -> List[Dict[str, Any]]:
    """
    Obtiene los archivos de un deal con URLs de descarga.

    Args:
        user: Diccionario con información del usuario
        deal_id: UUID del deal
        category: Filtro opcional por categoría

    Returns:
        Lista de archivos con URLs de descarga
    """
    try:
        user_id = self._extract_user_id(user)
        logger.info(f"Usuario {user_id} obteniendo archivos del deal {deal_id}")

        validated_deal_id = self._validate_uuid(deal_id, "deal_id")

        # Obtener archivos del repositorio
        filters = {"deal_id": validated_deal_id}
        if category:
            filters["category"] = category

        files = self.deal_file_repository.find_all(filters=filters)

        # Agregar URLs de descarga
        result = []
        for file in files:
            file_dict = file.model_dump()

            # Generar URL de descarga (válida por 1 hora)
            file_dict["download_url"] = self.s3_service.presign_get(
                key=file.s3_key,
                expiration=3600
            )

            result.append(file_dict)

        logger.info(f"Encontrados {len(result)} archivos para deal {validated_deal_id}")
        return result

    except (ServiceDataValidationError, NotFoundError):
        raise
    except Exception as e:
        error_msg = f"Error inesperado al obtener archivos: {str(e)}"
        logger.error(error_msg)
        raise ServiceError(error_msg) from e


def delete_deal_file(
    self,
    user: Dict[str, Any],
    deal_id: str,
    file_id: str
) -> bool:
    """
    Elimina un archivo de un deal (BD y S3).

    Args:
        user: Diccionario con información del usuario
        deal_id: UUID del deal
        file_id: UUID del archivo

    Returns:
        True si se eliminó exitosamente
    """
    try:
        user_id = self._extract_user_id(user)
        logger.info(f"Usuario {user_id} eliminando archivo {file_id} del deal {deal_id}")

        validated_deal_id = self._validate_uuid(deal_id, "deal_id")
        validated_file_id = self._validate_uuid(file_id, "file_id")

        # Obtener el archivo
        file = self.deal_file_repository.find_by_id(validated_file_id)
        self._found_object(file, f"Archivo con ID {validated_file_id} no encontrado")

        # Verificar que pertenece al deal
        if str(file.deal_id) != validated_deal_id:
            raise BusinessValidationError("El archivo no pertenece al deal especificado")

        # Eliminar de S3
        try:
            self.s3_service.delete(file.s3_key)
            logger.info(f"Archivo eliminado de S3: {file.s3_key}")
        except Exception as e:
            logger.warning(f"No se pudo eliminar de S3 (continuando): {str(e)}")

        # Eliminar de BD
        is_deleted = self.deal_file_repository.delete(id=validated_file_id)

        if is_deleted:
            logger.info(f"Archivo {validated_file_id} eliminado exitosamente")

        return is_deleted

    except (ServiceDataValidationError, NotFoundError, BusinessValidationError):
        raise
    except Exception as e:
        error_msg = f"Error inesperado al eliminar archivo: {str(e)}"
        logger.error(error_msg)
        raise ServiceError(error_msg) from e
    # ==================== BATCH CON PARALELISMO ====================

    def upload_batch(
            self,
            files: List[Dict[str, Any]],
            max_workers: int = LambdaConfig.MAX_BATCH_WORKERS,
    ) -> Dict[str, Any]:
        """
        Sube múltiples archivos en paralelo

        Args:
            files: Lista de dicts con 'key' y ('file_path' | 'data' | 'text')
            max_workers: Threads paralelos (default 3 para Lambda)
        """
        results = {'success': [], 'errors': []}

        def _upload_one(file_spec: Dict) -> Tuple[str, Optional[Dict], Optional[str]]:
            key = file_spec['key']
            try:
                if 'file_path' in file_spec:
                    result = self.upload_file(key=key, file_path=file_spec['file_path'],
                                              content_type=file_spec.get('content_type'),
                                              metadata=file_spec.get('metadata'))
                elif 'data' in file_spec:
                    result = self.upload_bytes(key=key, data=file_spec['data'],
                                               content_type=file_spec.get('content_type'),
                                               metadata=file_spec.get('metadata'))
                elif 'text' in file_spec:
                    result = self.upload_text(key=key, text=file_spec['text'],
                                              content_type=file_spec.get('content_type'),
                                              metadata=file_spec.get('metadata'))
                else:
                    return key, None, "No se especificó file_path, data ni text"
                return key, result, None
            except Exception as e:
                return key, None, str(e)

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(_upload_one, f): f for f in files}
            for future in as_completed(futures):
                key, result, error = future.result()
                if error:
                    results['errors'].append({'key': key, 'error': error})
                else:
                    results['success'].append(result)

        results['success_count'] = len(results['success'])
        results['error_count'] = len(results['errors'])
        logger.info(f"✓ Upload batch: {results['success_count']} exitosos, {results['error_count']} errores")
        return results

    def download_batch(
            self,
            downloads: List[Dict[str, str]],
            max_workers: int = LambdaConfig.MAX_BATCH_WORKERS,
    ) -> Dict[str, Any]:
        """
        Descarga múltiples archivos en paralelo

        Args:
            downloads: Lista de dicts con 'key' y 'file_path' (default /tmp/{filename})
            max_workers: Threads paralelos (default 3 para Lambda)
        """
        results = {'success': [], 'errors': []}

        def _download_one(spec: Dict) -> Tuple[str, Optional[Dict], Optional[str]]:
            key = spec['key']
            try:
                file_path = spec.get('file_path')
                result = self.download_file(key=key, file_path=file_path)
                if result is None:
                    return key, None, "Objeto no encontrado"
                return key, result, None
            except Exception as e:
                return key, None, str(e)

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(_download_one, d): d for d in downloads}
            for future in as_completed(futures):
                key, result, error = future.result()
                if error:
                    results['errors'].append({'key': key, 'error': error})
                else:
                    results['success'].append(result)

        results['success_count'] = len(results['success'])
        results['error_count'] = len(results['errors'])
        logger.info(f"✓ Download batch: {results['success_count']} exitosos, {results['error_count']} errores")
        return results

    def presign_batch(
            self,
            operations: List[Dict[str, Any]],
            default_expiration: int = LambdaConfig.PRESIGN_DEFAULT_EXPIRATION,
    ) -> Dict[str, Optional[str]]:
        """Genera múltiples URLs prefirmadas en lote"""
        method_map = {
            "get": "get_object", "put": "put_object",
            "delete": "delete_object", "head": "head_object",
        }

        results = {}
        for op in operations:
            key = op["key"]
            method = method_map.get(op.get("operation", "get"), "get_object")
            expiration = op.get("expiration", default_expiration)

            try:
                url = self.generate_presigned_url(
                    method=method, key=key, expiration=expiration,
                    content_type=op.get("content_type"),
                    extra_params=op.get("extra_params"),
                )
                results[key] = url
            except Exception as e:
                logger.error(f"Error presign para {key}: {str(e)}")
                results[key] = None

        logger.info(f"✓ Presign batch: {len(results)} URLs procesadas")
        return results

    # ==================== UTILIDADES ====================

    @staticmethod
    def _format_size(size_bytes: int) -> str:
        """Formatea bytes a formato legible"""
        if size_bytes == 0:
            return "0 B"
        units = ['B', 'KB', 'MB', 'GB', 'TB', 'PB']
        i = 0
        size = float(size_bytes)
        while size >= 1024 and i < len(units) - 1:
            size /= 1024
            i += 1
        return f"{size:.2f} {units[i]}" if i > 0 else f"{int(size)} B"

    def get_bucket_size(self, prefix: str = "") -> Dict[str, Any]:
        """Calcula el tamaño total de objetos en un prefijo"""
        total_size = 0
        total_objects = 0
        paginator = self.client.get_paginator('list_objects_v2')

        try:
            for page in paginator.paginate(Bucket=self.bucket_name, Prefix=prefix):
                for obj in page.get('Contents', []):
                    total_size += obj['Size']
                    total_objects += 1

            return {
                'prefix': prefix,
                'total_size': total_size,
                'total_size_human': self._format_size(total_size),
                'total_objects': total_objects,
            }
        except ClientError as e:
            logger.error(f"Error calculando tamaño: {str(e)}")
            return {'prefix': prefix, 'total_size': 0, 'total_size_human': '0 B', 'total_objects': 0}

    def bucket_exists(self) -> bool:
        """Verifica si el bucket existe y es accesible"""
        try:
            self.client.head_bucket(Bucket=self.bucket_name)
            return True
        except ClientError:
            return False


# ==================== FACTORY FUNCTIONS ====================

def create_s3_service(bucket_name: str = None, **kwargs) -> S3Service:
    """
    Factory function para crear S3Service

    Args:
        bucket_name: Nombre del bucket (o env S3_BUCKET_NAME)
        **kwargs: Argumentos adicionales para S3Service
    """
    bucket = bucket_name or os.environ.get('S3_BUCKET_NAME', '')
    return S3Service(bucket_name=bucket, **kwargs)


def detect_content_type(filename: str) -> str:
    """Función standalone para detectar content-type desde extensión"""
    return ContentTypeDetector.detect(filename)


def detect_extension(content_type: str) -> str:
    """Función standalone para detectar extensión desde content-type"""
    return ContentTypeDetector.detect_extension(content_type)