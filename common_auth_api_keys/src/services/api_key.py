import logging
from typing import Optional, Tuple
from dataclasses import dataclass
from common_auth_api_keys.src.repositories.api_key import ApiKeyRepository
logger = logging.getLogger(__name__)


@dataclass
class ApiKeyData:
    """Datos del API key extraídos de la BD."""
    key_id: str
    evaluator_id: str
    is_active: bool
    name: Optional[str] = None


class ApiKeyAuthService:
    """Servicio para validar API keys que vienen de API Gateway."""

    def __init__(self, api_key_repository: ApiKeyRepository):
        """
        Args:
            repository: Repositorio para consultar la tabla api_keys
        """
        self.api_key_repository = api_key_repository

    def extract_api_key_id_from_event(self, event: dict) -> Optional[str]:
        """
        Extrae el API Key ID que API Gateway inyecta en el evento.

        API Gateway inyecta el ID en: event['requestContext']['identity']['apiKeyId']
        """
        # Para tests: si ya viene el api_key_id directamente
        if "api_key_id" in event:
            return event["api_key_id"]

        try:
            api_key_id = event["requestContext"]["identity"]["apiKeyId"]
            logger.info(f"API Key ID extraído: {api_key_id}")
            return api_key_id

        except (KeyError, TypeError) as e:
            logger.warning(f"No se pudo extraer el API Key ID del evento: {e}")
            return None

    def validate_api_key(self, api_key_id: str) -> Tuple[bool, Optional[ApiKeyData]]:
        """
        Valida el API key consultando la base de datos.

        Returns:
            tuple: (is_valid: bool, api_key_data: Optional[ApiKeyData])
        """
        if not api_key_id:
            logger.warning("API Key ID vacío")
            return False, None

        try:
            # Buscar en la BD
            api_key_record = self.api_key_repository.find_one_by_attributes(
                {
                    "key_id": api_key_id,
                }
            )

            if not api_key_record:
                logger.warning(f"API Key no encontrado en BD: {api_key_id}")
                return False, None

            # Verificar si está activo
            if not api_key_record.is_active:
                logger.warning(f"API Key inactivo/revocado: {api_key_id}")
                return False, None

            # Construir datos del API key con solo los campos disponibles
            api_key_data = ApiKeyData(
                key_id=api_key_record.key_id,
                evaluator_id=api_key_record.evaluator_id_str,
                is_active=api_key_record.is_active,
                name=api_key_record.name
            )

            logger.info(f"API Key válido para evaluator_id: {api_key_data.evaluator_id}")
            return True, api_key_data

        except Exception as e:
            logger.error(f"Error al validar API Key: {e}", exc_info=True)
            return False, None

    def validate_access(self, event: dict) -> Tuple[bool, Optional[ApiKeyData], Optional[str]]:
        """
        Valida acceso completo: extrae API key ID y verifica en BD.

        Returns:
            tuple: (is_valid: bool, api_key_data: Optional[ApiKeyData], error_message: Optional[str])
        """
        # Extraer API Key ID del evento
        api_key_id = self.extract_api_key_id_from_event(event)

        if not api_key_id:
            return False, None, "API Key no proporcionado en la solicitud"

        # Validar en BD
        is_valid, api_key_data = self.validate_api_key(api_key_id)

        if not is_valid:
            if api_key_data and not api_key_data.is_active:
                return False, None, "API Key revocado o inactivo"
            return False, None, "API Key inválido"

        return True, api_key_data, None