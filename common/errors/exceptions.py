"""
Excepciones comunes para la librería common.
"""

class BaseError(Exception):
    """Clase base para todas las excepciones personalizadas del proyecto."""
    def __init__(self, message: str, original_exception: Exception = None):
        super().__init__(message)
        self.original_exception = original_exception

class RedisClientError(BaseError):
    """Errores específicos del BaseRedisClient."""
    pass

class MessageProcessingError(BaseError):
    """Errores durante el procesamiento de un DomainAction."""
    pass

class ConfigurationError(BaseError):
    """Errores relacionados con la configuración del servicio o componente."""
    pass

class ExternalServiceError(BaseError):
    """Errores originados en un servicio externo (ej. API de un tercero)."""
    pass

class InvalidActionError(MessageProcessingError):
    """Cuando un DomainAction no es válido o no puede ser manejado."""
    pass

class QueueManagerError(BaseError):
    """Errores específicos del QueueManager."""
    pass

class WorkerError(BaseError):
    """Errores generales dentro de la lógica de un Worker."""
    pass


# --- HTTP Error Classes ---

class BadRequestError(ExternalServiceError):
    """Corresponds to a 400 Bad Request error."""
    pass

class UnauthorizedError(ExternalServiceError):
    """Corresponds to a 401 Unauthorized error."""
    pass

class ForbiddenError(ExternalServiceError):
    """Corresponds to a 403 Forbidden error."""
    pass

class NotFoundError(ExternalServiceError):
    """Corresponds to a 404 Not Found error."""
    pass

class ConflictError(ExternalServiceError):
    """Corresponds to a 409 Conflict error."""
    pass

class InternalServerError(ExternalServiceError):
    """Corresponds to a 500 Internal Server Error."""
    pass

class ServiceUnavailableError(ExternalServiceError):
    """Corresponds to a 503 Service Unavailable error."""
    pass

