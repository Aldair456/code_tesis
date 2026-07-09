import json
import boto3
import logging
from typing import Dict, Any, Optional, List, Union
from botocore.exceptions import ClientError, NoCredentialsError
from datetime import datetime
import uuid

logger = logging.getLogger(__name__)


class SQSClient:
    """
    Cliente SQS reutilizable optimizado para entornos serverless.
    Maneja conexiones eficientemente y proporciona métodos simples para envío de mensajes.
    """

    def __init__(self,
                 queue_url: str,
                 region_name: str = 'us-east-1',
                 aws_access_key_id: Optional[str] = None,
                 aws_secret_access_key: Optional[str] = None,
                 endpoint_url: Optional[str] = None):
        """
        Inicializa el cliente SQS.

        Args:
            queue_url: URL completa de la cola SQS
            region_name: Región de AWS (default: us-east-1)
            aws_access_key_id: Access Key (opcional, usa IAM roles si no se proporciona)
            aws_secret_access_key: Secret Key (opcional)
            endpoint_url: URL del endpoint (útil para LocalStack o testing)
        """
        self.queue_url = queue_url
        self.region_name = region_name
        self._client = None

        # Configuración de credenciales
        self._aws_config = {}
        if aws_access_key_id and aws_secret_access_key:
            self._aws_config.update({
                'aws_access_key_id': aws_access_key_id,
                'aws_secret_access_key': aws_secret_access_key
            })

        if endpoint_url:
            self._aws_config['endpoint_url'] = endpoint_url

        # Determinar si es FIFO queue
        self.is_fifo = queue_url.endswith('.fifo')

        logger.info(f"SQS Client configurado para cola: {queue_url} ({'FIFO' if self.is_fifo else 'Standard'})")

    @property
    def client(self):
        """
        Lazy loading del cliente SQS para optimizar en serverless.
        Crea el cliente solo cuando se necesita.
        """
        if self._client is None:
            try:
                self._client = boto3.client(
                    'sqs',
                    region_name=self.region_name,
                    **self._aws_config
                )
                logger.debug("Cliente SQS inicializado correctamente")
            except NoCredentialsError:
                logger.error("No se encontraron credenciales AWS")
                raise
            except Exception as e:
                logger.error(f"Error inicializando cliente SQS: {e}")
                raise

        return self._client

    def send_message(self,
                     message: Union[str, Dict[Any, Any]],
                     message_attributes: Optional[Dict[str, Any]] = None,
                     delay_seconds: Optional[int] = None,
                     message_group_id: Optional[str] = None,
                     message_deduplication_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Envía un mensaje individual a la cola SQS.

        Args:
            message: Mensaje a enviar (str o dict)
            message_attributes: Atributos del mensaje (opcional)
            delay_seconds: Retraso en segundos antes de que el mensaje esté disponible
            message_group_id: ID del grupo para colas FIFO (obligatorio para FIFO)
            message_deduplication_id: ID de deduplicación (se genera automáticamente si no se proporciona en FIFO)

        Returns:
            Respuesta de SQS con MessageId, MD5, etc.

        Raises:
            ValueError: Si es cola FIFO y no se proporciona message_group_id
        """
        try:
            # Validar parámetros FIFO
            if self.is_fifo and not message_group_id:
                raise ValueError("message_group_id es obligatorio para colas FIFO")

            # Preparar parámetros para SQS
            params = {
                'QueueUrl': self.queue_url,
                'MessageBody': self._serialize_body(message)
            }

            # Agregar atributos opcionales
            if message_attributes:
                params['MessageAttributes'] = self._format_message_attributes(message_attributes)

            if delay_seconds is not None:
                params['DelaySeconds'] = delay_seconds

            # Parámetros específicos para FIFO queues
            if self.is_fifo:
                params['MessageGroupId'] = message_group_id

                # Auto-generar deduplication ID si no se proporciona
                if message_deduplication_id:
                    params['MessageDeduplicationId'] = message_deduplication_id
                else:
                    params['MessageDeduplicationId'] = str(uuid.uuid4())

            # Enviar mensaje
            response = self.client.send_message(**params)

            logger.info(f"Mensaje enviado exitosamente. MessageId: {response['MessageId']}")
            return response

        except ClientError as e:
            error_code = e.response['Error']['Code']
            logger.error(f"Error enviando mensaje SQS [{error_code}]: {e}")
            raise
        except Exception as e:
            logger.error(f"Error inesperado enviando mensaje: {e}")
            raise

    def send_batch_messages(self,
                            messages: List[Dict[str, Any]],
                            batch_size: int = 10) -> List[Dict[str, Any]]:
        """
        Envía múltiples mensajes en lotes (máximo 10 por lote según AWS).

        Args:
            messages: Lista de diccionarios con estructura:
                     {
                         'message': Union[str, Dict[Any, Any]],
                         'message_attributes': Optional[Dict[str, Any]],
                         'delay_seconds': Optional[int],
                         'message_group_id': Optional[str],  # Obligatorio para FIFO
                         'message_deduplication_id': Optional[str]
                     }
            batch_size: Tamaño del lote (máximo 10)

        Returns:
            Lista con todas las respuestas de los lotes enviados
        """
        if batch_size > 10:
            logger.warning("Batch size reducido a 10 (límite de AWS SQS)")
            batch_size = 10

        responses = []

        # Procesar en lotes
        for i in range(0, len(messages), batch_size):
            batch = messages[i:i + batch_size]
            batch_response = self._send_message_batch(batch)
            responses.append(batch_response)

        logger.info(f"Enviados {len(messages)} mensajes en {len(responses)} lotes")
        return responses

    def _send_message_batch(self, messages: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Envía un lote de mensajes (uso interno)"""
        try:
            entries = []

            for idx, msg_data in enumerate(messages):
                entry_id = f"msg_{idx}_{uuid.uuid4().hex[:8]}"

                # Extraer datos del mensaje
                message = msg_data['message']
                message_attributes = msg_data.get('message_attributes')
                delay_seconds = msg_data.get('delay_seconds')
                message_group_id = msg_data.get('message_group_id')
                message_deduplication_id = msg_data.get('message_deduplication_id')

                # Validar FIFO
                if self.is_fifo and not message_group_id:
                    raise ValueError(f"message_group_id es obligatorio para mensaje {idx} en cola FIFO")

                entry = {
                    'Id': entry_id,
                    'MessageBody': self._serialize_body(message)
                }

                if message_attributes:
                    entry['MessageAttributes'] = self._format_message_attributes(message_attributes)

                if delay_seconds is not None:
                    entry['DelaySeconds'] = delay_seconds

                # FIFO específico
                if self.is_fifo:
                    entry['MessageGroupId'] = message_group_id
                    entry['MessageDeduplicationId'] = message_deduplication_id or str(uuid.uuid4())

                entries.append(entry)

            # Enviar lote
            response = self.client.send_message_batch(
                QueueUrl=self.queue_url,
                Entries=entries
            )

            # Log de resultados
            successful = len(response.get('Successful', []))
            failed = len(response.get('Failed', []))
            logger.info(f"Lote enviado: {successful} exitosos, {failed} fallidos")

            if failed > 0:
                for failure in response.get('Failed', []):
                    logger.error(f"Mensaje falló [ID: {failure['Id']}]: {failure['Message']}")

            return response

        except Exception as e:
            logger.error(f"Error enviando lote de mensajes: {e}")
            raise

    def send_json_message(self,
                          data: Dict[Any, Any],
                          message_group_id: Optional[str] = None,
                          **kwargs) -> Dict[str, Any]:
        """
        Método de conveniencia para enviar objetos JSON.

        Args:
            data: Diccionario a enviar como JSON
            message_group_id: ID del grupo para colas FIFO (obligatorio para FIFO)
            **kwargs: Argumentos adicionales para send_message
        """
        return self.send_message(data, message_group_id=message_group_id, **kwargs)

    def send_task_message(self,
                          task_type: str,
                          payload: Dict[Any, Any],
                          priority: str = 'normal',
                          message_group_id: Optional[str] = None,
                          **kwargs) -> Dict[str, Any]:
        """
        Método de conveniencia para enviar mensajes de tareas con formato estándar.

        Args:
            task_type: Tipo de tarea
            payload: Datos de la tarea
            priority: Prioridad ('high', 'normal', 'low')
            message_group_id: ID del grupo para colas FIFO (obligatorio para FIFO)
            **kwargs: Argumentos adicionales
        """
        task_message = {
            'task_type': task_type,
            'payload': payload,
            'timestamp': datetime.utcnow().isoformat(),
            'priority': priority,
            'message_id': str(uuid.uuid4())
        }

        # Mapear prioridad a delay_seconds si no se especifica
        if 'delay_seconds' not in kwargs:
            priority_delays = {'high': 0, 'normal': 0, 'low': 30}
            kwargs['delay_seconds'] = priority_delays.get(priority, 0)

        return self.send_message(task_message, message_group_id=message_group_id, **kwargs)

    def get_queue_attributes(self) -> Dict[str, Any]:
        """Obtiene atributos de la cola (útil para monitoring)"""
        try:
            response = self.client.get_queue_attributes(
                QueueUrl=self.queue_url,
                AttributeNames=['All']
            )
            return response['Attributes']
        except Exception as e:
            logger.error(f"Error obteniendo atributos de la cola: {e}")
            raise

    def purge_queue(self) -> Dict[str, Any]:
        """Elimina todos los mensajes de la cola (usar con precaución)"""
        try:
            response = self.client.purge_queue(QueueUrl=self.queue_url)
            logger.warning(f"Cola purgada: {self.queue_url}")
            return response
        except Exception as e:
            logger.error(f"Error purgando cola: {e}")
            raise

    def _serialize_body(self, body: Union[str, Dict[Any, Any]]) -> str:
        """Serializa el cuerpo del mensaje a string"""
        if isinstance(body, str):
            return body
        return json.dumps(body, ensure_ascii=False, default=str)

    def _format_message_attributes(self, attributes: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        """Formatea los atributos del mensaje para SQS"""
        formatted = {}
        for key, value in attributes.items():
            if isinstance(value, str):
                formatted[key] = {'StringValue': value, 'DataType': 'String'}
            elif isinstance(value, (int, float)):
                formatted[key] = {'StringValue': str(value), 'DataType': 'Number'}
            elif isinstance(value, bool):
                formatted[key] = {'StringValue': str(value).lower(), 'DataType': 'String'}
            else:
                formatted[key] = {'StringValue': json.dumps(value), 'DataType': 'String'}
        return formatted

    def __enter__(self):
        """Context manager support"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Cleanup en context manager (no necesario para SQS, pero buena práctica)"""
        pass



