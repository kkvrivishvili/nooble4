"""
Módulo Común de la Aplicación Nooble4 (`refactorizado.common`)

Este paquete agrega diversos sub-módulos y utilidades compartidas entre los
diferentes servicios de la aplicación.

Exporta directamente las excepciones comunes definidas en `common.exceptions`.
"""

from .exceptions import (
    BaseError,
    RedisClientError,
    MessageProcessingError,
    ConfigurationError,
    ExternalServiceError,
    InvalidActionError,
    QueueManagerError,
    WorkerError,
)

__all__ = [
    "BaseError",
    "RedisClientError",
    "MessageProcessingError",
    "ConfigurationError",
    "ExternalServiceError",
    "InvalidActionError",
    "QueueManagerError",
    "WorkerError",
]
