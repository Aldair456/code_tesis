import boto3
from botocore.exceptions import ClientError, NoCredentialsError
from typing import List, Dict, Optional, Union
import json
import logging
import sys

# Configurar logging con handler para consola
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Agregar handler de consola si no existe
if not logger.handlers:
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)

class S3Presigner:
    # Cliente S3 de clase para reutilización entre instancias
    _s3_client = None
    _s3_client_region = None
    
    @classmethod
    def _get_s3_client(cls, region_name: str = "us-east-1"):
        """Lazy initialization del cliente S3 con reutilización"""
        if cls._s3_client is None or cls._s3_client_region != region_name:
            cls._s3_client = boto3.client("s3", region_name=region_name)
            cls._s3_client_region = region_name
        return cls._s3_client
    
    @classmethod
    def _reset_s3_client(cls):
        """Resetea el cliente S3 de clase para forzar refresco de credenciales"""
        logger.info("Reseteando cliente S3 para refrescar credenciales")
        cls._s3_client = None
        cls._s3_client_region = None
    
    def __init__(self, bucket_name: str, region_name: str = "us-east-1"):
        self.bucket_name = bucket_name
        self.region_name = region_name
        # No inicializar el cliente aquí, usar lazy loading

    @property
    def s3(self):
        """Property para lazy loading del cliente S3"""
        return self._get_s3_client(self.region_name)

    def generate_presigned_url(
            self,
            method: str,
            key: str,
            expiration: int = 3600,
            extra_params: Optional[Dict] = None
    ) -> Optional[str]:
        """Método genérico para generar URLs presignadas"""
        try:
            params = {"Bucket": self.bucket_name, "Key": key}
            if extra_params:
                params.update(extra_params)

            return self.s3.generate_presigned_url(
                ClientMethod=method,
                Params=params,
                ExpiresIn=expiration
            )
        except (ClientError, NoCredentialsError) as e:
            # Obtener código de error de forma más robusta
            error_code = ''
            error_message = str(e)
            
            if isinstance(e, ClientError):
                try:
                    error_code = e.response.get('Error', {}).get('Code', '') if hasattr(e, 'response') else ''
                    error_message = e.response.get('Error', {}).get('Message', error_message) if hasattr(e, 'response') else error_message
                except (AttributeError, KeyError):
                    pass
            
            # Detectar ExpiredToken o TokenRefreshRequired
            if ('ExpiredToken' in error_code or 'ExpiredToken' in error_message or 
                'TokenRefreshRequired' in error_code or 
                ('token' in error_message.lower() and 'expired' in error_message.lower())):
                logger.warning(f"Token de credenciales expirado detectado (Code: {error_code}). Refrescando cliente S3...")
                self._reset_s3_client()
                # Intentar nuevamente con credenciales frescas
                try:
                    params = {"Bucket": self.bucket_name, "Key": key}
                    if extra_params:
                        params.update(extra_params)
                    return self.s3.generate_presigned_url(
                        ClientMethod=method,
                        Params=params,
                        ExpiresIn=expiration
                    )
                except Exception as retry_error:
                    logger.error(f"Error generando URL presignada después de refrescar credenciales para {key}: {str(retry_error)}")
                    return None
            
            logger.error(f"Error generating presigned URL for {key}: {str(e)}")
            return None

    def generate_url_put(
            self,
            key: str,
            expiration: int = 3600,
            content_type: Optional[str] = None
    ) -> Optional[str]:
        """Generar URL presignada para PUT"""
        extra_params = {}
        if content_type:
            extra_params["ContentType"] = content_type

        return self.generate_presigned_url("put_object", key, expiration, extra_params)

    def generate_url_get_v2(self, key: str, expiration: int) -> Optional[str]:
        """Generar URL presignada para GET (versión simplificada)"""
        try:
            # Validar que expiration sea una duración válida (NO timestamp Unix)
            # Timestamps Unix son > 1000000000 (año 2001+)
            # Duraciones razonables: 1-604800 segundos (máximo 7 días)
            expiration_int = int(expiration)
            
            # Detectar si es un timestamp Unix en lugar de duración
            if expiration_int > 1000000000:
                logger.error(f"ERROR: expiration parece ser timestamp Unix ({expiration_int}), no duración. Usando 3600 segundos.")
                expiration_int = 3600
            
            # Validar rango: máximo 7 días (604800 segundos)
            if expiration_int <= 0:
                logger.warning(f"expiration debe ser positivo ({expiration_int}), usando 3600")
                expiration_int = 3600
            elif expiration_int > 604800:
                logger.warning(f"expiration {expiration_int} excede máximo (604800), usando 604800")
                expiration_int = 604800
            
            logger.info(f"Generando URL presignada: key={key}, expiration={expiration_int} segundos")
            
            return self.s3.generate_presigned_url(
                ClientMethod="get_object",
                Params={
                    "Bucket": self.bucket_name,
                    "Key": key
                },
                ExpiresIn=expiration_int
            )
        except (ClientError, NoCredentialsError) as e:
            # Obtener código de error de forma más robusta
            error_code = ''
            error_message = str(e)
            
            if isinstance(e, ClientError):
                try:
                    error_code = e.response.get('Error', {}).get('Code', '') if hasattr(e, 'response') else ''
                    error_message = e.response.get('Error', {}).get('Message', error_message) if hasattr(e, 'response') else error_message
                except (AttributeError, KeyError):
                    pass
            
            # Detectar ExpiredToken o TokenRefreshRequired
            if ('ExpiredToken' in error_code or 'ExpiredToken' in error_message or 
                'TokenRefreshRequired' in error_code or 
                ('token' in error_message.lower() and 'expired' in error_message.lower())):
                logger.warning(f"Token de credenciales expirado detectado en generate_url_get_v2 (Code: {error_code}). Refrescando cliente S3...")
                self._reset_s3_client()
                # Intentar nuevamente con credenciales frescas
                try:
                    expiration_int = int(expiration)
                    if expiration_int > 1000000000:
                        expiration_int = 3600
                    if expiration_int <= 0:
                        expiration_int = 3600
                    elif expiration_int > 604800:
                        expiration_int = 604800
                    return self.s3.generate_presigned_url(
                        ClientMethod="get_object",
                        Params={
                            "Bucket": self.bucket_name,
                            "Key": key
                        },
                        ExpiresIn=expiration_int
                    )
                except Exception as retry_error:
                    logger.error(f"Error generando URL presignada después de refrescar credenciales para {key}: {str(retry_error)}")
                    return None
            
            logger.error(f"Error generating presigned URL for {key}: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error generating presigned URL: {str(e)}")
            return None

    def generate_url_get(self, key: str, expiration: int = 3600) -> Optional[str]:
        """Generar URL presignada para GET"""
        return self.generate_presigned_url("get_object", key, expiration)

    def generate_urls_batch(
            self,
            operations: List[Dict[str, Union[str, int]]],
            default_expiration: int = 3600
    ) -> Dict[str, Optional[str]]:
        """
        Generar múltiples URLs en batch
        operations: [{"method": "put_object", "key": "file.txt", "expiration": 600}, ...]
        """
        results = {}
        for op in operations:
            method = op["method"]
            key = op["key"]
            expiration = op.get("expiration", default_expiration)
            extra_params = op.get("extra_params")

            results[key] = self.generate_presigned_url(method, key, expiration, extra_params)

        return results

       

    def upload_text_file(self, file_name: str, text_content: str) -> bool:
        """
        Sube archivo de texto a S3 - versión ultraligera
        """
        try:
            self.s3.put_object(
                Bucket=self.bucket_name,
                Key=file_name,
                Body=text_content.encode('utf-8'),
                ContentType='text/plain'
            )
            logger.info(f"Archivo '{file_name}' subido exitosamente.")
            return True
        except Exception as e:
            logger.error(f"Error al subir '{file_name}': {e}")
            raise


