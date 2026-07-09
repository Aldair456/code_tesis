# common_service/service.py
import logging
import uuid
from typing import Optional, Dict, Any, List, TypeVar
from enum import Enum

from common.exceptions.exceptions import (
    ServiceDataValidationError,
    BusinessValidationError,
    ServiceError,
    NotFoundError,
    UnauthorizedError
)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

T = TypeVar('T')

class Role(str, Enum):
    ADMIN = "ADMIN"
    GERENCIA = "GERENCIA"
    SUPERVISOR = "SUPERVISOR"
    ANALYST = "ANALYST"

class Service:
    """
    Servicio base con métodos comunes para todos los servicios.
    """

    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)

    # ============= VALIDACIONES UUID =============

    def _validate_uuid(self, id_value: str, field_name: str = "id") -> str:
        """
        Valida que un string sea un UUID válido y lo retorna como string.

        Args:
            id_value: String a validar
            field_name: Nombre del campo para mensajes de error

        Returns:
            UUID validado como string

        Raises:
            ServiceDataValidationError: Si el UUID no es válido
        """
        if not id_value:
            raise ServiceDataValidationError(f"El campo {field_name} es requerido")

        try:
            # Validar que sea un UUID válido
            uuid.UUID(str(id_value))
            self.logger.debug(f"UUID válido para {field_name}: {id_value}")
            return str(id_value)
        except (ValueError, TypeError, AttributeError) as e:
            error_msg = f"El {field_name} proporcionado no es un UUID válido: {id_value}"
            self.logger.error(error_msg)
            raise ServiceDataValidationError(error_msg) from e

    def _validate_multiple_uuids(self, uuid_dict: Dict[str, str]) -> Dict[str, str]:
        """
        Valida múltiples UUIDs de una vez.

        Args:
            uuid_dict: Diccionario con {nombre_campo: valor_uuid}

        Returns:
            Diccionario con UUIDs validados como strings
        """
        validated = {}
        for field_name, uuid_value in uuid_dict.items():
            validated[field_name] = self._validate_uuid(uuid_value, field_name)
        return validated

    # ============= EXTRACCIÓN DE DATOS DE USUARIO =============
    def _is_role(self, user: Dict[str, Any], role: str) -> bool:
        try:
            roles = self._extract_roles(user)
            return role in roles
        except Exception as e:
            self.logger.error(f"Error inesperado al extraer verificar role de usuario: {str(e)}")
            return False
    def _extract_roles(self, user: Dict[str, Any]) -> List:
        """

        """
        try:
            roles = user.get("roles", [])

            if not roles:
                error_msg = "No se encontró roles en el token de autenticación"
                self.logger.error(f"{error_msg}. Keys disponibles: {list(user.keys())}")
                raise ServiceDataValidationError(error_msg)
            return roles
        except ServiceDataValidationError:
            raise
        except Exception as e:
            self.logger.error(f"Error inesperado al extraer roles: {str(e)}")
            raise ServiceError("Error al procesar información del usuario") from e

    def _extract_user_id(self, user: Dict[str, Any]) -> str:
        """
        Extrae y valida el user_id del objeto usuario.

        Returns:
            user_id como string validado
        """
        try:
            user_id = user.get("sub") or user.get("id")
            if not user_id:
                error_msg = "No se encontró user_id en el token de autenticación"
                self.logger.error(f"{error_msg}. Keys disponibles: {list(user.keys())}")
                raise ServiceDataValidationError(error_msg)

            return self._validate_uuid(str(user_id), "user_id")
        except ServiceDataValidationError:
            raise
        except Exception as e:
            self.logger.error(f"Error inesperado al extraer user_id: {str(e)}")
            raise ServiceError("Error al procesar información del usuario") from e

    def _extract_evaluator_id(self, user: Dict[str, Any]) -> str:
        """
        Extrae y valida el evaluator_id del objeto usuario.

        Returns:
            evaluator_id como string validado
        """
        try:
            evaluator_id = user.get("evaluator_id")
            if not evaluator_id:
                error_msg = "No se encontró evaluator_id en el token de autenticación"
                self.logger.error(f"{error_msg}. Keys disponibles: {list(user.keys())}")
                raise ServiceDataValidationError(error_msg)

            return self._validate_uuid(str(evaluator_id), "evaluator_id")
        except ServiceDataValidationError:
            raise
        except Exception as e:
            self.logger.error(f"Error inesperado al extraer evaluator_id: {str(e)}")
            raise ServiceError("Error al procesar información del evaluador") from e

    # ============= VALIDACIONES DE PAGINACIÓN =============

    def _validate_pagination(self, page: int, size: int, max_size: int = 100) -> tuple[int, int]:
        """
        Valida y calcula parámetros de paginación.

        Args:
            page: Número de página (0-indexed)
            size: Tamaño de página
            max_size: Tamaño máximo permitido

        Returns:
            Tupla (size_validado, offset_calculado)
        """
        if page < 0:
            error_msg = f"El parámetro 'page' debe ser >= 0, recibido: {page}"
            self.logger.error(error_msg)
            raise ServiceDataValidationError(error_msg)

        if size < 1:
            error_msg = f"El parámetro 'size' debe ser >= 1, recibido: {size}"
            self.logger.error(error_msg)
            raise ServiceDataValidationError(error_msg)

        if size > max_size:
            error_msg = f"El parámetro 'size' no puede ser mayor a {max_size}, recibido: {size}"
            self.logger.error(error_msg)
            raise ServiceDataValidationError(error_msg)

        offset = page * size
        self.logger.debug(f"Paginación validada: page={page}, size={size}, offset={offset}")
        return size, offset

    # ============= UTILIDADES GENERALES =============

    def _first_or_none(self, items: List[T]) -> Optional[T]:
        """
        Retorna el primer elemento de una lista o None si está vacía.
        """
        return items[0] if items else None

    def _require_not_none(self, value: Optional[T], error_message: str) -> T:
        """
        Valida que un valor no sea None, de lo contrario lanza NotFoundError.
        """
        if value is None:
            self.logger.error(error_message)
            raise NotFoundError(error_message)
        return value

    def _validate_ownership(
            self,
            resource_evaluator_id: str,
            user_evaluator_id: str,
            resource_name: str = "recurso"
    ) -> None:
        """
        Valida que el evaluator_id del usuario coincida con el del recurso.

        Args:
            resource_evaluator_id: evaluator_id del recurso (string)
            user_evaluator_id: evaluator_id del usuario (string)
            resource_name: Nombre del recurso para el mensaje de error

        Raises:
            UnauthorizedError: Si no coinciden los evaluator_ids
        """
        if resource_evaluator_id != user_evaluator_id:
            error_msg = f"No autorizado para acceder a este {resource_name}"
            self.logger.warning(
                f"{error_msg}. User evaluator: {user_evaluator_id}, "
                f"Resource evaluator: {resource_evaluator_id}"
            )
            raise UnauthorizedError(error_msg)

    def _increment_version(self, current_version: Optional[str], prefix: str = "v") -> str:
        """
        Incrementa una versión en formato vX (v1, v2, etc).

        Args:
            current_version: Versión actual (ej: "v5") o None
            prefix: Prefijo de versión

        Returns:
            Nueva versión incrementada
        """
        if not current_version:
            return f"{prefix}1"

        try:
            # Extraer número de versión
            version_number = int(current_version.replace(prefix, ""))
            return f"{prefix}{version_number + 1}"
        except (ValueError, AttributeError) as e:
            self.logger.warning(f"Error al parsear versión '{current_version}', usando v1")
            return f"{prefix}1"

    def _validate_required_fields(self, data: Dict[str, Any], required_fields: List[str]) -> None:
        """
        Valida que todos los campos requeridos estén presentes en el diccionario.

        Args:
            data: Diccionario a validar
            required_fields: Lista de campos requeridos

        Raises:
            ServiceDataValidationError: Si falta algún campo
        """
        missing_fields = [field for field in required_fields if not data.get(field)]

        if missing_fields:
            error_msg = f"Campos requeridos faltantes: {', '.join(missing_fields)}"
            self.logger.error(error_msg)
            raise ServiceDataValidationError(error_msg)

    def _validate_resource_relationship(
            self,
            parent_id: str,
            child_parent_id: str,
            parent_resource_name: str = "recurso padre",
            child_resource_name: str = "recurso hijo"
    ) -> None:
        """
        Valida que el recurso hijo pertenezca al recurso padre verificando la relación parent_id.

        Args:
            parent_id: ID del recurso padre (string)
            child_parent_id: parent_id del recurso hijo que debe coincidir con parent_id (string)
            parent_resource_name: Nombre del recurso padre para el mensaje de error
            child_resource_name: Nombre del recurso hijo para el mensaje de error

        Raises:
            BusinessValidationError: Si el child_parent_id no coincide con parent_id
        """
        if parent_id != child_parent_id:
            error_msg = (
                f"El {child_resource_name} no pertenece al {parent_resource_name}. "
                f"Los recursos no están relacionados"
            )
            self.logger.warning(
                f"{error_msg}. Expected parent_id: {parent_id}, "
                f"but {child_resource_name} has parent_id: {child_parent_id}"
            )
            raise BusinessValidationError(error_msg)