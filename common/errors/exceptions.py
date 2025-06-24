"""
Excepciones comunes para la librería common.
"""

class BaseError(Exception):
    """Clase base para todas las excepciones personalizadas del proyecto."""
    def __init__(self, message: str, original_exception: Exception = None):
        super().__init__(message)
        self.original_exception = original_exception

class AppError(BaseError):
    """
    Clase base para errores de la aplicación que se pueden mapear a respuestas HTTP.
    """
    def __init__(self, message: str, status_code: int = 500, error_code: str = "INTERNAL_ERROR", original_exception: Exception = None):
        super().__init__(message, original_exception)
        self.status_code = status_code
        self.error_code = error_code

# --- Application-specific Errors ---

class AppValidationError(AppError):
    """Excepción para errores de validación de datos de la aplicación."""
    def __init__(self, message="Error de validación"):
        super().__init__(message, status_code=400, error_code="VALIDATION_ERROR")

class InvalidActionError(AppError):
    """Excepción para acciones inválidas o no soportadas."""
    def __init__(self, message="Acción inválida o no soportada"):
        super().__init__(message, status_code=400, error_code="INVALID_ACTION")

class ConfigurationError(AppError):
    """Errores relacionados con la configuración del servicio o componente."""
    def __init__(self, message="Error de configuración"):
        super().__init__(message, status_code=500, error_code="CONFIGURATION_ERROR")

class ExternalServiceError(AppError):
    """Errores originados en un servicio externo (ej. API de un tercero)."""
    def __init__(self, message="Error en servicio externo", status_code=502, error_code="EXTERNAL_SERVICE_ERROR"):
        super().__init__(message, status_code=status_code, error_code=error_code)

class MessageProcessingError(AppError):
    """Errores durante el procesamiento de un DomainAction."""
    def __init__(self, message="Error procesando el mensaje"):
        super().__init__(message, status_code=500, error_code="MESSAGE_PROCESSING_ERROR")

class WorkerError(AppError):
    """Errores generales dentro de la lógica de un Worker."""
    def __init__(self, message="Error en el worker"):
        super().__init__(message, status_code=500, error_code="WORKER_ERROR")


# --- Infrastructure Errors ---

class RedisClientError(BaseError):
    """Errores específicos del BaseRedisClient."""
    pass

class QueueManagerError(BaseError):
    """Errores específicos del QueueManager."""
    pass

# --- HTTP Error Classes ---
# These can be used to wrap specific external service responses

class BadRequestError(ExternalServiceError):
    """Corresponds to a 400 Bad Request error."""
    def __init__(self, message="Bad Request"):
        super().__init__(message, status_code=400, error_code="BAD_REQUEST")

class UnauthorizedError(ExternalServiceError):
    """Corresponds to a 401 Unauthorized error."""
    def __init__(self, message="Unauthorized"):
        super().__init__(message, status_code=401, error_code="UNAUTHORIZED")

class ForbiddenError(ExternalServiceError):
    """Corresponds to a 403 Forbidden error."""
    def __init__(self, message="Forbidden"):
        super().__init__(message, status_code=403, error_code="FORBIDDEN")

class NotFoundError(ExternalServiceError):
    """Corresponds to a 404 Not Found error."""
    def __init__(self, message="Not Found"):
        super().__init__(message, status_code=404, error_code="NOT_FOUND")

class ConflictError(ExternalServiceError):
    """Corresponds to a 409 Conflict error."""
    def __init__(self, message="Conflict"):
        super().__init__(message, status_code=409, error_code="CONFLICT")

class InternalServerError(ExternalServiceError):
    """Corresponds to a 500 Internal Server Error."""
    def __init__(self, message="Internal Server Error"):
        super().__init__(message, status_code=500, error_code="INTERNAL_SERVER_ERROR")

class ServiceUnavailableError(ExternalServiceError):
    """Corresponds to a 503 Service Unavailable error."""
    def __init__(self, message="Service Unavailable"):
        super().__init__(message, status_code=503, error_code="SERVICE_UNAVAILABLE")


