"""
Módulo Común de la Aplicación Nooble4 (`refactorizado.common`)

Este paquete agrega diversos sub-módulos y utilidades compartidas entre los
diferentes servicios de la aplicación.

Exporta directamente las excepciones comunes definidas en `common.exceptions`.
"""

# Configuracion
from .config import CommonAppSettings

# Modelos
from .models import (
    DomainAction,
    DomainActionResponse,
    ErrorDetail,
    ExecutionContext,
)

# Handlers
from .handlers import BaseActionHandler, HandlerNotFoundError

# Workers
from .workers import BaseWorker, WorkerError # WorkerError ya estaba en exceptions

# Clients
from .clients import BaseRedisClient

# Utils
from .utils import QueueManager, init_logging

# Excepciones
from .exceptions import (
    BaseError,
    RedisClientError,
    MessageProcessingError,
    ConfigurationError,
    ExternalServiceError,
    InvalidActionError,
    QueueManagerError,
    WorkerError, # Duplicado, ya importado con .workers
)

__all__ = [
    # Config
    "CommonAppSettings",
    # Models
    "DomainAction",
    "DomainActionResponse",
    "ErrorDetail",
    "ExecutionContext",
    # Handlers
    "BaseActionHandler",
    "HandlerNotFoundError",
    # Workers
    "BaseWorker",
    # "WorkerError", # Ya está en la lista de excepciones abajo
    # Clients
    "BaseRedisClient",
    # Utils
    "QueueManager",
    "init_logging",
    # Exceptions
    "BaseError",
    "RedisClientError",
    "MessageProcessingError",
    "ConfigurationError",
    "ExternalServiceError",
    "InvalidActionError",
    "QueueManagerError",
    "WorkerError",
]


