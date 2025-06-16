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
