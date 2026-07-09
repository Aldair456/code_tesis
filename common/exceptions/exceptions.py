class ValidationError(Exception):
    pass


# exceptions.py
class AppError(Exception):
    """Excepción base para toda la aplicación."""
    pass


# Excepciones para la capa de repositorio
class RepositoryError(AppError):
    """Error general en la capa de repositorio."""
    pass

class NotFoundError(RepositoryError):
    """Error cuando no se encuentra un recurso."""
    pass

class UserAlreadyExistsError(RepositoryError):
    pass

class RepositoryDataValidationError(RepositoryError):
    """Error de validación en datos dentro del repositorio."""
    pass


# Excepciones para la capa de servicio
class ServiceError(AppError):
    """Error general en la capa de servicio."""
    pass

class ServiceDataValidationError(ServiceError):
    """Error de validación de datos estructurales o de negocio"""
    pass

class BusinessValidationError(ServiceError):
    """Error de validación de reglas de negocio."""
    pass


# Excepciones para la capa de API / Handler
class APIError(AppError):
    """Error general en la capa API o handler."""
    pass

class BadRequestError(APIError):
    """Error de solicitud incorrecta (400)."""
    pass

class UnauthorizedError(APIError):
    """Error de autorización (401)."""
    pass

class ForbiddenError(APIError):
    """Error de acceso prohibido (403)."""
    pass

class NotFoundAPIError(APIError):
    """Error de recurso no encontrado (404)."""
    pass

class ConflictError(APIError):
    """Error de conflicto (409)"""
    pass

class InternalServerError(APIError):
    """Error interno del servidor (500)."""
    pass



