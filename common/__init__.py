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
)

# Handlers
from .handlers import BaseHandler

# Workers
from .workers import BaseWorker

# Clients
from .clients import BaseRedisClient, RedisManager, RedisStateManager, QueueManager, CacheKeyManager, CacheManager

# Services
from .services import BaseService

# Utils
from .utils import init_logging # QueueManager is now imported from .clients

# Excepciones
from .errors.exceptions import (
    BaseError,
    RedisClientError,
    MessageProcessingError,
    ConfigurationError,
    ExternalServiceError,
    InvalidActionError,
    QueueManagerError,
    WorkerError
)

__all__ = [
    # Config
    "CommonAppSettings",
    # Models
    "DomainAction",
    "DomainActionResponse",
    "ErrorDetail",
    # Handlers
    "BaseHandler",
    # Workers
    "BaseWorker",
    # Clients
    "BaseRedisClient",
    "RedisManager",
    "RedisStateManager",
    "QueueManager",
    # Services
    "BaseService",
    # Utils
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


