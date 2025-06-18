# Embedding Service - Refactorización Completa

## Estructura del Proyecto

```
embedding_service/
├── __init__.py
├── main.py
├── requirements.txt
├── Dockerfile
├── config/
│   ├── __init__.py
│   └── settings.py
├── workers/
│   ├── __init__.py
│   └── embedding_worker.py
├── services/
│   ├── __init__.py
│   └── embedding_service.py
├── handlers/
│   ├── __init__.py
│   ├── openai_handler.py
│   ├── validation_handler.py
│   └── cache_handler.py
├── models/
│   ├── __init__.py
│   └── payloads.py
└── clients/
    ├── __init__.py
    └── openai_client.py
```

## Archivos de Implementación

### `embedding_service/__init__.py`

```python
"""
Embedding Service - Servicio de generación de embeddings.

Este servicio maneja la generación de embeddings vectoriales
para textos usando la API de OpenAI y otros proveedores.
"""

__version__ = "1.0.0"
```

### `embedding_service/main.py`

```python
"""
Punto de entrada principal del Embedding Service.

Configura y ejecuta el servicio con FastAPI y el EmbeddingWorker.
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Optional, List

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from common.clients import RedisManager
from common.utils import init_logging

from .config.settings import get_settings
from .workers.embedding_worker import EmbeddingWorker


# Variables globales para el ciclo de vida
redis_manager: Optional[RedisManager] = None
embedding_workers: List[EmbeddingWorker] = []
worker_tasks: List[asyncio.Task] = []

# Configuración
settings = get_settings()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Gestiona el ciclo de vida de la aplicación.
    
    Inicializa recursos al inicio y los limpia al finalizar.
    """
    global redis_manager, embedding_workers, worker_tasks
    
    try:
        # Inicializar logging
        init_logging(
            log_level=settings.log_level,
            service_name=settings.service_name
        )
        
        logger.info(f"Iniciando {settings.service_name} v{settings.service_version}")
        
        # Inicializar Redis Manager
        redis_manager = RedisManager(settings=settings)
        redis_conn = await redis_manager.get_client()
        logger.info("Redis Manager inicializado")
        
        # Crear workers según configuración
        num_workers = getattr(settings, 'worker_count', 2)
        
        for i in range(num_workers):
            worker = EmbeddingWorker(
                app_settings=settings,
                async_redis_conn=redis_conn,
                consumer_id_suffix=f"worker-{i}"
            )
            embedding_workers.append(worker)
            
            # Inicializar y ejecutar worker
            await worker.initialize()
            task = asyncio.create_task(worker.run())
            worker_tasks.append(task)
        
        logger.info(f"{num_workers} EmbeddingWorkers iniciados")
        
        # Hacer disponibles las referencias en app.state
        app.state.redis_manager = redis_manager
        app.state.embedding_workers = embedding_workers
        
        yield
        
    finally:
        logger.info("Deteniendo Embedding Service...")
        
        # Detener workers
        for worker in embedding_workers:
            await worker.stop()
        
        # Cancelar tareas
        for task in worker_tasks:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        
        # Cerrar Redis Manager
        if redis_manager:
            await redis_manager.close()
        
        logger.info("Embedding Service detenido completamente")


# Crear aplicación FastAPI
app = FastAPI(
    title=settings.service_name,
    description="Servicio de generación de embeddings vectoriales",
    version=settings.service_version,
    lifespan=lifespan
)

# Configurar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # En producción, especificar orígenes permitidos
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Health Check Endpoints ---

@app.get("/health")
async def health_check():
    """
    Health check básico del servicio.
    """
    return {
        "status": "healthy",
        "service": settings.service_name,
        "version": settings.service_version,
        "environment": settings.environment
    }


@app.get("/health/detailed")
async def detailed_health_check():
    """
    Health check detallado con estado de componentes.
    """
    health_status = {
        "service": settings.service_name,
        "version": settings.service_version,
        "environment": settings.environment,
        "components": {}
    }
    
    # Verificar Redis
    try:
        if redis_manager:
            client = await redis_manager.get_client()
            await client.ping()
            health_status["components"]["redis"] = {"status": "healthy"}
        else:
            health_status["components"]["redis"] = {"status": "unhealthy", "error": "Not initialized"}
    except Exception as e:
        health_status["components"]["redis"] = {"status": "unhealthy", "error": str(e)}
    
    # Verificar Workers
    workers_status = []
    for i, worker in enumerate(embedding_workers):
        worker_status = {
            "id": i,
            "running": worker._running,
            "initialized": worker.initialized
        }
        workers_status.append(worker_status)
    
    health_status["components"]["workers"] = {
        "status": "healthy" if all(w["running"] for w in workers_status) else "degraded",
        "details": workers_status
    }
    
    # Verificar OpenAI API (opcional)
    try:
        # Aquí podríamos hacer un ping a OpenAI si es necesario
        health_status["components"]["openai_api"] = {"status": "healthy"}
    except Exception as e:
        health_status["components"]["openai_api"] = {"status": "unknown", "note": "No check implemented"}
    
    # Estado general
    all_healthy = all(
        comp.get("status") == "healthy" 
        for comp in health_status["components"].values()
    )
    health_status["status"] = "healthy" if all_healthy else "degraded"
    
    return health_status


# --- Metrics Endpoints ---

@app.get("/metrics")
async def get_metrics():
    """
    Obtiene métricas del servicio.
    """
    metrics = {
        "service": settings.service_name,
        "workers": []
    }
    
    # Aquí podríamos agregar métricas específicas del servicio
    # como embeddings generados, tiempos de procesamiento, etc.
    
    return metrics


# --- API Info ---

@app.get("/")
async def root():
    """
    Información básica del servicio.
    """
    return {
        "service": settings.service_name,
        "version": settings.service_version,
        "description": "Embedding Service - Generación de embeddings vectoriales",
        "endpoints": {
            "health": "/health",
            "health_detailed": "/health/detailed",
            "metrics": "/metrics",
            "docs": "/docs",
            "redoc": "/redoc"
        }
    }


if __name__ == "__main__":
    uvicorn.run(
        "embedding_service.main:app",
        host="0.0.0.0",
        port=8003,
        reload=False,  # En producción debe ser False
        log_level=settings.log_level.lower()
    )
```

### `embedding_service/config/__init__.py`

```python
"""
Configuración para Embedding Service.
"""

from .settings import get_settings

__all__ = ['get_settings']
```

### `embedding_service/config/settings.py`

```python
"""
Configuración para Embedding Service.

Este módulo carga la configuración del servicio usando EmbeddingServiceSettings
definido en common.config.service_settings.embedding
"""

from functools import lru_cache
from common.config import EmbeddingServiceSettings

@lru_cache()
def get_settings() -> EmbeddingServiceSettings:
    """
    Retorna la instancia de configuración para Embedding Service.
    Usa lru_cache para asegurar que solo se crea una instancia.
    """
    return EmbeddingServiceSettings()

# Para facilitar el acceso directo
settings = get_settings()
```

### `embedding_service/models/__init__.py`

```python
"""
Modelos de datos para Embedding Service.
"""

from .payloads import (
    EmbeddingGeneratePayload,
    EmbeddingGenerateQueryPayload,
    EmbeddingBatchPayload,
    EmbeddingValidatePayload,
    EmbeddingResult,
    EmbeddingResponse,
    EmbeddingQueryResponse,
    EmbeddingBatchResponse,
    EmbeddingValidationResponse,
    EmbeddingErrorResponse,
    EmbeddingMetrics
)

__all__ = [
    'EmbeddingGeneratePayload',
    'EmbeddingGenerateQueryPayload',
    'EmbeddingBatchPayload',
    'EmbeddingValidatePayload',
    'EmbeddingResult',
    'EmbeddingResponse',
    'EmbeddingQueryResponse',
    'EmbeddingBatchResponse',
    'EmbeddingValidationResponse',
    'EmbeddingErrorResponse',
    'EmbeddingMetrics'
]
```

### `embedding_service/models/payloads.py`

```python
"""
Modelos Pydantic para los payloads de las acciones del Embedding Service.

Estos modelos definen la estructura esperada del campo 'data' en DomainAction
para cada tipo de acción que maneja el servicio.
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, field_validator
from datetime import datetime
from uuid import UUID

# --- Modelos de Request (para action.data) ---

class EmbeddingGeneratePayload(BaseModel):
    """Payload para acción embedding.generate - Generación de embeddings."""
    
    texts: List[str] = Field(..., description="Lista de textos para generar embeddings")
    model: Optional[str] = Field(None, description="Modelo de embedding específico a usar")
    
    # Opciones adicionales
    dimensions: Optional[int] = Field(None, description="Dimensiones del embedding (si el modelo lo soporta)")
    encoding_format: Optional[str] = Field("float", description="Formato de codificación: 'float' o 'base64'")
    
    # Metadatos para tracking
    collection_id: Optional[UUID] = Field(None, description="ID de la colección asociada")
    chunk_ids: Optional[List[str]] = Field(None, description="IDs de los chunks correspondientes")
    
    @field_validator('texts')
    @classmethod
    def validate_texts(cls, v):
        if not v:
            raise ValueError("La lista de textos no puede estar vacía")
        if len(v) > 100:  # Límite para evitar sobrecarga
            raise ValueError("No se pueden procesar más de 100 textos a la vez")
        return v


class EmbeddingGenerateQueryPayload(BaseModel):
    """Payload para embedding.generate_query - Embedding de consulta única."""
    
    texts: List[str] = Field(..., description="Lista con un único texto de consulta", max_length=1)
    model: Optional[str] = Field(None, description="Modelo de embedding específico")
    
    @field_validator('texts')
    @classmethod
    def validate_single_text(cls, v):
        if not v or len(v) != 1:
            raise ValueError("Se requiere exactamente un texto para generate_query")
        return v


class EmbeddingBatchPayload(BaseModel):
    """Payload para embedding.batch_process - Procesamiento por lotes."""
    
    batch_id: str = Field(..., description="ID único del lote")
    texts: List[str] = Field(..., description="Lista de textos del lote")
    model: Optional[str] = Field(None, description="Modelo de embedding")
    priority: Optional[str] = Field("normal", description="Prioridad: 'low', 'normal', 'high'")
    
    # Metadatos del lote
    collection_id: Optional[UUID] = Field(None)
    document_ids: Optional[List[str]] = Field(None)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class EmbeddingValidatePayload(BaseModel):
    """Payload para embedding.validate - Validación de capacidad."""
    
    texts: List[str] = Field(..., description="Textos a validar")
    model: Optional[str] = Field(None, description="Modelo a validar")
    check_cache: bool = Field(True, description="Si verificar disponibilidad en cache")


# --- Modelos de Response (para DomainActionResponse.data o callbacks) ---

class EmbeddingResult(BaseModel):
    """Representa un embedding individual."""
    
    text_index: int = Field(..., description="Índice del texto original")
    embedding: List[float] = Field(..., description="Vector de embedding")
    dimensions: int = Field(..., description="Dimensiones del vector")
    from_cache: bool = Field(False, description="Si el embedding vino del cache")
    

class EmbeddingResponse(BaseModel):
    """Respuesta para embedding.generate."""
    
    embeddings: List[List[float]] = Field(..., description="Lista de embeddings generados")
    model: str = Field(..., description="Modelo utilizado")
    dimensions: int = Field(..., description="Dimensiones de los embeddings")
    
    # Métricas
    total_tokens: int = Field(..., description="Total de tokens procesados")
    processing_time_ms: int = Field(..., description="Tiempo de procesamiento en ms")
    from_cache: bool = Field(False, description="Si todos los embeddings vinieron del cache")
    cache_hits: int = Field(0, description="Número de hits en cache")
    cache_misses: int = Field(0, description="Número de misses en cache")
    
    # Metadatos
    metadata: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class EmbeddingQueryResponse(BaseModel):
    """Respuesta para embedding.generate_query."""
    
    embedding: List[float] = Field(..., description="Embedding del texto de consulta")
    model: str = Field(..., description="Modelo utilizado")
    dimensions: int = Field(..., description="Dimensiones del embedding")
    
    # Métricas
    tokens: int = Field(..., description="Tokens en el texto")
    processing_time_ms: int = Field(..., description="Tiempo de procesamiento")
    from_cache: bool = Field(False, description="Si vino del cache")
    
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class EmbeddingBatchResponse(BaseModel):
    """Respuesta para embedding.batch_process."""
    
    batch_id: str = Field(..., description="ID del lote procesado")
    status: str = Field(..., description="Estado: 'completed', 'partial', 'failed'")
    
    # Resultados
    embeddings: List[EmbeddingResult] = Field(..., description="Embeddings procesados")
    successful_count: int = Field(..., description="Número de embeddings exitosos")
    failed_count: int = Field(..., description="Número de embeddings fallidos")
    
    # Métricas
    total_tokens: int = Field(0)
    processing_time_ms: int = Field(...)
    
    # Errores si los hay
    errors: Optional[List[Dict[str, Any]]] = Field(None)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class EmbeddingValidationResponse(BaseModel):
    """Respuesta para embedding.validate."""
    
    is_valid: bool = Field(..., description="Si la solicitud es válida")
    can_process: bool = Field(..., description="Si el servicio puede procesarla")
    
    # Detalles de validación
    text_count: int = Field(..., description="Número de textos")
    estimated_tokens: int = Field(..., description="Tokens estimados")
    model_available: bool = Field(..., description="Si el modelo está disponible")
    within_limits: bool = Field(..., description="Si está dentro de los límites")
    
    # Cache info
    cache_available: bool = Field(False)
    cached_count: int = Field(0)
    
    # Mensajes
    messages: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)


class EmbeddingErrorResponse(BaseModel):
    """Respuesta de error para cualquier acción de embedding."""
    
    error_type: str = Field(..., description="Tipo de error")
    error_message: str = Field(..., description="Mensaje de error")
    error_details: Optional[Dict[str, Any]] = Field(None)
    
    # Contexto
    action_type: Optional[str] = Field(None)
    model: Optional[str] = Field(None)
    text_count: Optional[int] = Field(None)
    
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class EmbeddingMetrics(BaseModel):
    """Métricas de uso de embeddings."""
    
    tenant_id: str
    date: str
    
    # Contadores
    total_requests: int = Field(0)
    total_texts: int = Field(0)
    total_tokens: int = Field(0)
    
    # Cache
    cache_hits: int = Field(0)
    cache_misses: int = Field(0)
    cache_hit_rate: float = Field(0.0)
    
    # Performance
    avg_processing_time_ms: float = Field(0.0)
    avg_texts_per_request: float = Field(0.0)
    
    # Por modelo
    usage_by_model: Dict[str, int] = Field(default_factory=dict)
```

### `embedding_service/workers/__init__.py`

```python
"""
Workers del Embedding Service.
"""

from .embedding_worker import EmbeddingWorker

__all__ = ['EmbeddingWorker']
```

### `embedding_service/workers/embedding_worker.py`

```python
"""
Worker principal del Embedding Service.

Implementa BaseWorker para consumir DomainActions del stream Redis
y delegar el procesamiento al EmbeddingService.
"""

import logging
from typing import Optional, Dict, Any

from common.workers import BaseWorker
from common.models import DomainAction
from common.clients import BaseRedisClient

from ..services.embedding_service import EmbeddingService
from ..config.settings import get_settings


class EmbeddingWorker(BaseWorker):
    """
    Worker que procesa acciones de embedding desde Redis Streams.
    
    Consume DomainActions del stream del Embedding Service y las
    procesa usando EmbeddingService (que implementa BaseService).
    """
    
    def __init__(
        self, 
        app_settings=None,
        async_redis_conn=None,
        consumer_id_suffix: Optional[str] = None
    ):
        """
        Inicializa el EmbeddingWorker.
        
        Args:
            app_settings: EmbeddingServiceSettings (si no se proporciona, se carga)
            async_redis_conn: Conexión Redis asíncrona
            consumer_id_suffix: Sufijo para el ID del consumidor
        """
        # Cargar settings si no se proporcionan
        if app_settings is None:
            app_settings = get_settings()
        
        if async_redis_conn is None:
            raise ValueError("async_redis_conn es requerido para EmbeddingWorker")
        
        # Inicializar BaseWorker
        super().__init__(
            app_settings=app_settings,
            async_redis_conn=async_redis_conn,
            consumer_id_suffix=consumer_id_suffix
        )
        
        # El servicio se inicializará en el método initialize
        self.embedding_service = None
        
        self.logger = logging.getLogger(f"{__name__}.{self.consumer_name}")
        
    async def initialize(self):
        """
        Inicializa el worker y sus dependencias.
        
        Crea la instancia de EmbeddingService con las conexiones necesarias.
        """
        # Primero llamar a la inicialización del BaseWorker
        await super().initialize()
        
        # Crear cliente Redis para que el servicio pueda enviar acciones
        service_redis_client = BaseRedisClient(
            service_name=self.service_name,
            redis_client=self.async_redis_conn,
            settings=self.app_settings
        )
        
        # Inicializar EmbeddingService
        self.embedding_service = EmbeddingService(
            app_settings=self.app_settings,
            service_redis_client=service_redis_client,
            direct_redis_conn=self.async_redis_conn
        )
        
        self.logger.info(
            f"EmbeddingWorker inicializado. "
            f"Escuchando en stream: {self.action_stream_name}, "
            f"grupo: {self.consumer_group_name}"
        )
    
    async def _handle_action(self, action: DomainAction) -> Optional[Dict[str, Any]]:
        """
        Procesa una DomainAction delegando a EmbeddingService.
        
        Args:
            action: La acción a procesar
            
        Returns:
            Diccionario con los datos de respuesta o None
            
        Raises:
            Exception: Si hay un error en el procesamiento
        """
        if not self.embedding_service:
            raise RuntimeError("EmbeddingService no inicializado. Llamar initialize() primero.")
        
        self.logger.debug(
            f"Procesando acción {action.action_type} "
            f"(ID: {action.action_id}, Tenant: {action.tenant_id})"
        )
        
        # Delegar al servicio
        try:
            result = await self.embedding_service.process_action(action)
            
            # Log resultado
            if result:
                self.logger.debug(
                    f"Acción {action.action_id} procesada exitosamente. "
                    f"Respuesta generada: {bool(result)}"
                )
            else:
                self.logger.debug(
                    f"Acción {action.action_id} procesada sin respuesta (fire-and-forget)"
                )
            
            return result
            
        except Exception as e:
            self.logger.error(
                f"Error procesando acción {action.action_id}: {e}",
                exc_info=True
            )
            # Re-lanzar para que BaseWorker maneje el error
            raise
```

### `embedding_service/services/__init__.py`

```python
"""
Servicios del Embedding Service.
"""

from .embedding_service import EmbeddingService

__all__ = ['EmbeddingService']
```

### `embedding_service/services/embedding_service.py`

```python
"""
Implementación del servicio principal de Embedding Service.

Este servicio extiende BaseService y orquesta la lógica de negocio,
delegando operaciones específicas a los handlers correspondientes.
"""

import logging
from typing import Optional, Dict, Any
from uuid import uuid4

from pydantic import ValidationError

from common.services import BaseService
from common.models import DomainAction
from common.errors.exceptions import InvalidActionError, ExternalServiceError

from ..models.payloads import (
    EmbeddingGeneratePayload,
    EmbeddingGenerateQueryPayload,
    EmbeddingBatchPayload,
    EmbeddingValidatePayload,
    EmbeddingErrorResponse
)
from ..handlers.openai_handler import OpenAIHandler
from ..handlers.validation_handler import ValidationHandler
from ..handlers.cache_handler import CacheHandler


class EmbeddingService(BaseService):
    """
    Servicio principal para generación de embeddings.
    
    Maneja las acciones:
    - embedding.generate: Generación de embeddings para múltiples textos
    - embedding.generate_query: Generación de embedding para consulta única
    - embedding.batch_process: Procesamiento por lotes
    - embedding.validate: Validación de capacidad
    """
    
    def __init__(self, app_settings, service_redis_client=None, direct_redis_conn=None):
        """
        Inicializa el servicio con sus handlers.
        
        Args:
            app_settings: EmbeddingServiceSettings con la configuración
            service_redis_client: Cliente Redis para enviar acciones a otros servicios
            direct_redis_conn: Conexión Redis directa para operaciones internas
        """
        super().__init__(app_settings, service_redis_client, direct_redis_conn)
        
        # Inicializar handlers
        self.openai_handler = OpenAIHandler(
            app_settings=app_settings,
            direct_redis_conn=direct_redis_conn
        )
        
        self.validation_handler = ValidationHandler(
            app_settings=app_settings,
            direct_redis_conn=direct_redis_conn
        )
        
        self.cache_handler = CacheHandler(
            app_settings=app_settings,
            direct_redis_conn=direct_redis_conn
        )
        
        self._logger.info("EmbeddingService inicializado correctamente")
    
    async def process_action(self, action: DomainAction) -> Optional[Dict[str, Any]]:
        """
        Procesa una DomainAction según su tipo.
        
        Args:
            action: La acción a procesar
            
        Returns:
            Diccionario con los datos de respuesta o None
            
        Raises:
            InvalidActionError: Si el tipo de acción no es soportado
            ValidationError: Si el payload no es válido
        """
        self._logger.info(
            f"Procesando acción: {action.action_type} ({action.action_id})",
            extra={
                "action_id": str(action.action_id),
                "action_type": action.action_type,
                "tenant_id": action.tenant_id,
                "correlation_id": str(action.correlation_id) if action.correlation_id else None
            }
        )
        
        try:
            # Enrutar según el tipo de acción
            if action.action_type == "embedding.generate":
                return await self._handle_generate(action)
                
            elif action.action_type == "embedding.generate_query":
                return await self._handle_generate_query(action)
                
            elif action.action_type == "embedding.batch_process":
                return await self._handle_batch_process(action)
                
            elif action.action_type == "embedding.validate":
                return await self._handle_validate(action)
                
            elif action.action_type == "embedding.result":
                # Este es un callback, no debería llegar aquí normalmente
                self._logger.warning(f"Recibido callback embedding.result en el servicio")
                return None
                
            else:
                self._logger.warning(f"Tipo de acción no soportado: {action.action_type}")
                raise InvalidActionError(
                    f"Acción '{action.action_type}' no es soportada por Embedding Service"
                )
                
        except ValidationError as e:
            self._logger.error(f"Error de validación en {action.action_type}: {e}")
            # Crear respuesta de error
            error_response = EmbeddingErrorResponse(
                error_type="ValidationError",
                error_message="Error de validación en el payload",
                error_details={"validation_errors": e.errors()},
                action_type=action.action_type
            )
            return error_response.model_dump()
            
        except ExternalServiceError as e:
            self._logger.error(f"Error de servicio externo en {action.action_type}: {e}")
            error_response = EmbeddingErrorResponse(
                error_type="ExternalServiceError",
                error_message=str(e),
                error_details={"original_error": str(e.original_exception) if e.original_exception else None},
                action_type=action.action_type
            )
            return error_response.model_dump()
            
        except Exception as e:
            self._logger.exception(f"Error inesperado procesando {action.action_type}")
            # Re-lanzar para que BaseWorker maneje el error
            raise
    
    async def _handle_generate(self, action: DomainAction) -> Dict[str, Any]:
        """
        Maneja la acción embedding.generate para múltiples textos.
        
        Args:
            action: DomainAction con EmbeddingGeneratePayload
            
        Returns:
            Diccionario con EmbeddingResponse
        """
        # Validar y parsear payload
        payload = EmbeddingGeneratePayload(**action.data)
        
        # Obtener configuración de metadata si existe
        config_overrides = action.metadata or {}
        
        # Primero validar los textos
        validation_result = await self.validation_handler.validate_texts(
            texts=payload.texts,
            model=payload.model or config_overrides.get("model"),
            tenant_id=action.tenant_id
        )
        
        if not validation_result["is_valid"]:
            raise ValueError(f"Validación fallida: {validation_result['messages'][0]}")
        
        # Verificar cache si está habilitado
        embeddings_from_cache = []
        texts_to_generate = []
        cache_indices = []
        
        if self.app_settings.embedding_cache_enabled:
            for i, text in enumerate(payload.texts):
                cached = await self.cache_handler.get_cached_embedding(
                    text=text,
                    model=payload.model or self.app_settings.default_models_by_provider.get("openai"),
                    tenant_id=action.tenant_id
                )
                if cached:
                    embeddings_from_cache.append((i, cached))
                else:
                    texts_to_generate.append(text)
                    cache_indices.append(i)
        else:
            texts_to_generate = payload.texts
            cache_indices = list(range(len(payload.texts)))
        
        # Generar embeddings para textos no cacheados
        generated_embeddings = []
        if texts_to_generate:
            response = await self.openai_handler.generate_embeddings(
                texts=texts_to_generate,
                model=payload.model,
                dimensions=payload.dimensions,
                encoding_format=payload.encoding_format,
                tenant_id=action.tenant_id,
                trace_id=action.trace_id
            )
            generated_embeddings = response["embeddings"]
            
            # Cachear nuevos embeddings
            if self.app_settings.embedding_cache_enabled:
                for text, embedding in zip(texts_to_generate, generated_embeddings):
                    await self.cache_handler.cache_embedding(
                        text=text,
                        embedding=embedding,
                        model=response["model"],
                        tenant_id=action.tenant_id
                    )
        
        # Reconstruir lista completa de embeddings en orden original
        final_embeddings = [None] * len(payload.texts)
        
        # Insertar embeddings desde cache
        for idx, embedding in embeddings_from_cache:
            final_embeddings[idx] = embedding
        
        # Insertar embeddings generados
        for i, embedding in enumerate(generated_embeddings):
            final_embeddings[cache_indices[i]] = embedding
        
        # Construir respuesta
        from ..models.payloads import EmbeddingResponse
        response = EmbeddingResponse(
            embeddings=final_embeddings,
            model=response["model"] if texts_to_generate else (payload.model or self.app_settings.default_models_by_provider.get("openai")),
            dimensions=response["dimensions"] if texts_to_generate else len(final_embeddings[0]),
            total_tokens=response.get("total_tokens", 0) if texts_to_generate else 0,
            processing_time_ms=response.get("processing_time_ms", 0) if texts_to_generate else 0,
            from_cache=len(texts_to_generate) == 0,
            cache_hits=len(embeddings_from_cache),
            cache_misses=len(texts_to_generate),
            metadata={
                "collection_id": str(payload.collection_id) if payload.collection_id else None,
                "chunk_ids": payload.chunk_ids
            }
        )
        
        # Tracking de métricas
        await self._track_metrics(action, response)
        
        return response.model_dump()
    
    async def _handle_generate_query(self, action: DomainAction) -> Dict[str, Any]:
        """
        Maneja la acción embedding.generate_query para consulta única.
        
        Args:
            action: DomainAction con EmbeddingGenerateQueryPayload
            
        Returns:
            Diccionario con EmbeddingQueryResponse
        """
        # Validar y parsear payload
        payload = EmbeddingGenerateQueryPayload(**action.data)
        
        # Obtener el único texto
        query_text = payload.texts[0]
        
        # Verificar cache primero
        cached_embedding = None
        if self.app_settings.embedding_cache_enabled:
            cached_embedding = await self.cache_handler.get_cached_embedding(
                text=query_text,
                model=payload.model or self.app_settings.default_models_by_provider.get("openai"),
                tenant_id=action.tenant_id
            )
        
        if cached_embedding:
            # Respuesta desde cache
            from ..models.payloads import EmbeddingQueryResponse
            response = EmbeddingQueryResponse(
                embedding=cached_embedding,
                model=payload.model or self.app_settings.default_models_by_provider.get("openai"),
                dimensions=len(cached_embedding),
                tokens=0,  # No sabemos los tokens desde cache
                processing_time_ms=0,
                from_cache=True
            )
        else:
            # Generar nuevo embedding
            result = await self.openai_handler.generate_embeddings(
                texts=[query_text],
                model=payload.model,
                tenant_id=action.tenant_id,
                trace_id=action.trace_id
            )
            
            embedding = result["embeddings"][0]
            
            # Cachear si está habilitado
            if self.app_settings.embedding_cache_enabled:
                await self.cache_handler.cache_embedding(
                    text=query_text,
                    embedding=embedding,
                    model=result["model"],
                    tenant_id=action.tenant_id
                )
            
            from ..models.payloads import EmbeddingQueryResponse
            response = EmbeddingQueryResponse(
                embedding=embedding,
                model=result["model"],
                dimensions=result["dimensions"],
                tokens=result.get("prompt_tokens", 0),
                processing_time_ms=result.get("processing_time_ms", 0),
                from_cache=False
            )
        
        return response.model_dump()
    
    async def _handle_batch_process(self, action: DomainAction) -> Dict[str, Any]:
        """
        Maneja la acción embedding.batch_process para procesamiento por lotes.
        
        Args:
            action: DomainAction con EmbeddingBatchPayload
            
        Returns:
            Diccionario con EmbeddingBatchResponse
        """
        # Por ahora, implementación básica que delega a generate
        payload = EmbeddingBatchPayload(**action.data)
        
        try:
            # Procesar como generate normal
            generate_action = DomainAction(
                action_id=action.action_id,
                action_type="embedding.generate",
                tenant_id=action.tenant_id,
                session_id=action.session_id,
                task_id=action.task_id,
                user_id=action.user_id,
                origin_service=action.origin_service,
                trace_id=action.trace_id,
                data={
                    "texts": payload.texts,
                    "model": payload.model,
                    "collection_id": payload.collection_id
                }
            )
            
            result = await self._handle_generate(generate_action)
            
            # Convertir a batch response
            from ..models.payloads import EmbeddingBatchResponse, EmbeddingResult
            
            embedding_results = []
            for i, embedding in enumerate(result["embeddings"]):
                embedding_results.append(
                    EmbeddingResult(
                        text_index=i,
                        embedding=embedding,
                        dimensions=result["dimensions"],
                        from_cache=False  # Simplificado
                    )
                )
            
            response = EmbeddingBatchResponse(
                batch_id=payload.batch_id,
                status="completed",
                embeddings=embedding_results,
                successful_count=len(embedding_results),
                failed_count=0,
                total_tokens=result.get("total_tokens", 0),
                processing_time_ms=result.get("processing_time_ms", 0),
                metadata=payload.metadata
            )
            
            return response.model_dump()
            
        except Exception as e:
            # En caso de error, devolver respuesta parcial
            from ..models.payloads import EmbeddingBatchResponse
            response = EmbeddingBatchResponse(
                batch_id=payload.batch_id,
                status="failed",
                embeddings=[],
                successful_count=0,
                failed_count=len(payload.texts),
                total_tokens=0,
                processing_time_ms=0,
                errors=[{"error": str(e)}]
            )
            return response.model_dump()
    
    async def _handle_validate(self, action: DomainAction) -> Dict[str, Any]:
        """
        Maneja la acción embedding.validate para validación de capacidad.
        
        Args:
            action: DomainAction con EmbeddingValidatePayload
            
        Returns:
            Diccionario con EmbeddingValidationResponse
        """
        # Validar y parsear payload
        payload = EmbeddingValidatePayload(**action.data)
        
        # Usar validation handler
        validation_result = await self.validation_handler.validate_texts(
            texts=payload.texts,
            model=payload.model,
            tenant_id=action.tenant_id
        )
        
        # Verificar cache si se solicita
        cache_info = {"available": False, "count": 0}
        if payload.check_cache and self.app_settings.embedding_cache_enabled:
            cache_info = await self.cache_handler.check_cache_availability(
                texts=payload.texts,
                model=payload.model or self.app_settings.default_models_by_provider.get("openai"),
                tenant_id=action.tenant_id
            )
        
        from ..models.payloads import EmbeddingValidationResponse
        response = EmbeddingValidationResponse(
            is_valid=validation_result["is_valid"],
            can_process=validation_result["can_process"],
            text_count=len(payload.texts),
            estimated_tokens=validation_result["estimated_tokens"],
            model_available=validation_result["model_available"],
            within_limits=validation_result["within_limits"],
            cache_available=cache_info["available"],
            cached_count=cache_info["count"],
            messages=validation_result.get("messages", []),
            warnings=validation_result.get("warnings", [])
        )
        
        return response.model_dump()
    
    async def _track_metrics(self, action: DomainAction, response: Any):
        """
        Registra métricas del servicio.
        
        Args:
            action: La acción procesada
            response: La respuesta generada
        """
        if not self.direct_redis_conn or not self.app_settings.enable_embedding_tracking:
            return
        
        try:
            from datetime import datetime
            today = datetime.now().date().isoformat()
            
            # Clave de métricas por tenant
            metrics_key = f"embedding_metrics:{action.tenant_id}:{today}"
            
            # Incrementar contadores
            await self.direct_redis_conn.hincrby(metrics_key, "total_requests", 1)
            
            if hasattr(response, "cache_hits"):
                await self.direct_redis_conn.hincrby(metrics_key, "cache_hits", response.cache_hits)
                await self.direct_redis_conn.hincrby(metrics_key, "cache_misses", response.cache_misses)
            
            if hasattr(response, "total_tokens"):
                await self.direct_redis_conn.hincrby(metrics_key, "total_tokens", response.total_tokens)
            
            # TTL de 7 días
            await self.direct_redis_conn.expire(metrics_key, 86400 * 7)
            
        except Exception as e:
            self._logger.error(f"Error tracking metrics: {e}")
```

### `embedding_service/handlers/__init__.py`

```python
"""
Handlers del Embedding Service.
"""

from .openai_handler import OpenAIHandler
from .validation_handler import ValidationHandler
from .cache_handler import CacheHandler

__all__ = ['OpenAIHandler', 'ValidationHandler', 'CacheHandler']
```

### `embedding_service/handlers/openai_handler.py`

```python
"""
Handler para la generación de embeddings usando OpenAI API.

Maneja la comunicación con la API de OpenAI y la generación
de embeddings vectoriales.
"""

import logging
import time
from typing import List, Dict, Any, Optional
from uuid import UUID

from common.handlers import BaseHandler
from common.errors.exceptions import ExternalServiceError

from ..clients.openai_client import OpenAIClient


class OpenAIHandler(BaseHandler):
    """
    Handler para generar embeddings usando OpenAI.
    
    Coordina la generación de embeddings con reintentos,
    manejo de errores y tracking de métricas.
    """
    
    def __init__(self, app_settings, direct_redis_conn=None):
        """
        Inicializa el handler con sus dependencias.
        
        Args:
            app_settings: EmbeddingServiceSettings
            direct_redis_conn: Conexión Redis para operaciones directas
        """
        super().__init__(app_settings, direct_redis_conn)
        
        # Inicializar cliente OpenAI
        self.openai_client = OpenAIClient(
            api_key=app_settings.openai_api_key,
            timeout=app_settings.provider_timeout_seconds,
            max_retries=app_settings.provider_max_retries
        )
        
        # Configuración
        self.default_model = app_settings.default_models_by_provider.get("openai", "text-embedding-3-small")
        self.default_dimensions = app_settings.default_dimensions_by_model
        self.preferred_dimensions = app_settings.preferred_dimensions
        self.encoding_format = app_settings.encoding_format.value
        
        self._logger.info("OpenAIHandler inicializado")
    
    async def generate_embeddings(
        self,
        texts: List[str],
        model: Optional[str] = None,
        dimensions: Optional[int] = None,
        encoding_format: Optional[str] = None,
        tenant_id: Optional[str] = None,
        trace_id: Optional[UUID] = None
    ) -> Dict[str, Any]:
        """
        Genera embeddings para una lista de textos.
        
        Args:
            texts: Lista de textos
            model: Modelo específico a usar
            dimensions: Dimensiones del embedding
            encoding_format: Formato de codificación
            tenant_id: ID del tenant
            trace_id: ID de traza
            
        Returns:
            Dict con embeddings y metadatos
        """
        start_time = time.time()
        
        # Configurar parámetros
        model = model or self.default_model
        dimensions = dimensions or self.preferred_dimensions
        encoding_format = encoding_format or self.encoding_format
        
        self._logger.info(
            f"Generando embeddings para {len(texts)} textos con modelo {model}",
            extra={
                "tenant_id": tenant_id,
                "trace_id": str(trace_id) if trace_id else None,
                "model": model
            }
        )
        
        try:
            # Llamar al cliente OpenAI
            result = await self.openai_client.generate_embeddings(
                texts=texts,
                model=model,
                dimensions=dimensions,
                encoding_format=encoding_format
            )
            
            # Calcular tiempo de procesamiento
            processing_time_ms = int((time.time() - start_time) * 1000)
            
            # Agregar métricas al resultado
            result["processing_time_ms"] = processing_time_ms
            
            self._logger.info(
                f"Embeddings generados exitosamente en {processing_time_ms}ms",
                extra={
                    "tenant_id": tenant_id,
                    "model": model,
                    "text_count": len(texts),
                    "total_tokens": result.get("total_tokens", 0)
                }
            )
            
            return result
            
        except Exception as e:
            self._logger.error(
                f"Error generando embeddings: {e}",
                exc_info=True,
                extra={"tenant_id": tenant_id, "model": model}
            )
            raise ExternalServiceError(
                f"Error al generar embeddings con OpenAI: {str(e)}",
                original_exception=e
            )
    
    async def validate_model(self, model: str) -> bool:
        """
        Valida si un modelo está disponible.
        
        Args:
            model: Nombre del modelo
            
        Returns:
            True si el modelo está disponible
        """
        try:
            # Por ahora, validamos contra una lista conocida
            valid_models = [
                "text-embedding-3-small",
                "text-embedding-3-large",
                "text-embedding-ada-002"
            ]
            return model in valid_models
            
        except Exception as e:
            self._logger.error(f"Error validando modelo {model}: {e}")
            return False
    
    def estimate_tokens(self, texts: List[str]) -> int:
        """
        Estima el número de tokens para una lista de textos.
        
        Esta es una estimación aproximada. Para una estimación
        precisa se debería usar tiktoken.
        
        Args:
            texts: Lista de textos
            
        Returns:
            Número estimado de tokens
        """
        # Estimación simple: ~4 caracteres por token
        total_chars = sum(len(text) for text in texts)
        return max(1, total_chars // 4)
```

### `embedding_service/handlers/validation_handler.py`

```python
"""
Handler para validación de textos y configuraciones.

Valida que los textos cumplan con los requisitos antes
de generar embeddings.
"""

import logging
from typing import List, Dict, Any, Optional

from common.handlers import BaseHandler


class ValidationHandler(BaseHandler):
    """
    Handler para validar textos antes de generar embeddings.
    
    Verifica límites, formatos y disponibilidad de recursos.
    """
    
    def __init__(self, app_settings, direct_redis_conn=None):
        """
        Inicializa el handler de validación.
        
        Args:
            app_settings: EmbeddingServiceSettings
            direct_redis_conn: Conexión Redis opcional
        """
        super().__init__(app_settings, direct_redis_conn)
        
        # Configurar límites
        self.max_text_length = app_settings.default_max_text_length
        self.max_batch_size = app_settings.default_batch_size
        self.valid_models = list(app_settings.default_models_by_provider.values())
        
        self._logger.info("ValidationHandler inicializado")
    
    async def validate_texts(
        self,
        texts: List[str],
        model: Optional[str] = None,
        tenant_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Valida una lista de textos para procesamiento.
        
        Args:
            texts: Textos a validar
            model: Modelo a usar
            tenant_id: ID del tenant
            
        Returns:
            Dict con resultado de validación
        """
        validation_result = {
            "is_valid": True,
            "can_process": True,
            "messages": [],
            "warnings": [],
            "estimated_tokens": 0,
            "model_available": True,
            "within_limits": True
        }
        
        # Validar cantidad de textos
        if not texts:
            validation_result["is_valid"] = False
            validation_result["can_process"] = False
            validation_result["messages"].append("No se proporcionaron textos")
            return validation_result
        
        if len(texts) > self.max_batch_size:
            validation_result["is_valid"] = False
            validation_result["can_process"] = False
            validation_result["within_limits"] = False
            validation_result["messages"].append(
                f"Demasiados textos: {len(texts)} (máximo: {self.max_batch_size})"
            )
            return validation_result
        
        # Validar longitud de textos
        texts_too_long = []
        empty_texts = []
        total_chars = 0
        
        for i, text in enumerate(texts):
            if not text or not text.strip():
                empty_texts.append(i)
            elif len(text) > self.max_text_length:
                texts_too_long.append(i)
            else:
                total_chars += len(text)
        
        if empty_texts:
            validation_result["warnings"].append(
                f"Textos vacíos en posiciones: {empty_texts}"
            )
        
        if texts_too_long:
            validation_result["is_valid"] = False
            validation_result["can_process"] = False
            validation_result["within_limits"] = False
            validation_result["messages"].append(
                f"Textos muy largos en posiciones: {texts_too_long} "
                f"(máximo {self.max_text_length} caracteres)"
            )
        
        # Estimar tokens
        validation_result["estimated_tokens"] = max(1, total_chars // 4)
        
        # Validar modelo si se especifica
        if model and model not in self.valid_models:
            validation_result["model_available"] = False
            validation_result["warnings"].append(
                f"Modelo '{model}' no reconocido, se usará el modelo por defecto"
            )
        
        # Log del resultado
        self._logger.debug(
            f"Validación completada: {len(texts)} textos, "
            f"válido={validation_result['is_valid']}, "
            f"tokens estimados={validation_result['estimated_tokens']}",
            extra={"tenant_id": tenant_id}
        )
        
        return validation_result
    
    async def validate_tenant_limits(
        self,
        tenant_id: str,
        estimated_tokens: int
    ) -> Dict[str, Any]:
        """
        Valida los límites del tenant.
        
        Args:
            tenant_id: ID del tenant
            estimated_tokens: Tokens estimados
            
        Returns:
            Dict con información de límites
        """
        # Por ahora, implementación básica sin límites reales
        return {
            "within_limits": True,
            "current_usage": 0,
            "limit": 1000000,
            "estimated_cost": estimated_tokens * 0.0001  # Ejemplo
        }
```

### `embedding_service/handlers/cache_handler.py`

```python
"""
Handler para gestión de cache de embeddings.

Maneja el almacenamiento y recuperación de embeddings
cacheados en Redis.
"""

import json
import hashlib
import logging
from typing import List, Optional, Dict, Any

from common.handlers import BaseHandler


class CacheHandler(BaseHandler):
    """
    Handler para gestionar el cache de embeddings.
    
    Almacena y recupera embeddings en Redis para evitar
    regeneraciones innecesarias.
    """
    
    def __init__(self, app_settings, direct_redis_conn=None):
        """
        Inicializa el handler de cache.
        
        Args:
            app_settings: EmbeddingServiceSettings
            direct_redis_conn: Conexión Redis requerida
        """
        if not direct_redis_conn:
            raise ValueError("CacheHandler requiere direct_redis_conn")
            
        super().__init__(app_settings, direct_redis_conn)
        
        # Configuración de cache
        self.cache_enabled = app_settings.embedding_cache_enabled
        self.cache_ttl = app_settings.cache_ttl_seconds
        self.cache_prefix = "embedding_cache"
        
        self._logger.info(
            f"CacheHandler inicializado. Cache {'habilitado' if self.cache_enabled else 'deshabilitado'}"
        )
    
    async def get_cached_embedding(
        self,
        text: str,
        model: str,
        tenant_id: str
    ) -> Optional[List[float]]:
        """
        Obtiene un embedding cacheado si existe.
        
        Args:
            text: Texto del embedding
            model: Modelo usado
            tenant_id: ID del tenant
            
        Returns:
            Embedding si existe en cache, None si no
        """
        if not self.cache_enabled:
            return None
        
        try:
            cache_key = self._generate_cache_key(text, model, tenant_id)
            
            cached_data = await self.direct_redis_conn.get(cache_key)
            if cached_data:
                embedding = json.loads(cached_data)
                self._logger.debug(f"Cache hit para key: {cache_key}")
                return embedding
            
            self._logger.debug(f"Cache miss para key: {cache_key}")
            return None
            
        except Exception as e:
            self._logger.error(f"Error obteniendo embedding del cache: {e}")
            return None
    
    async def cache_embedding(
        self,
        text: str,
        embedding: List[float],
        model: str,
        tenant_id: str
    ) -> bool:
        """
        Cachea un embedding.
        
        Args:
            text: Texto original
            embedding: Vector de embedding
            model: Modelo usado
            tenant_id: ID del tenant
            
        Returns:
            True si se cacheó exitosamente
        """
        if not self.cache_enabled:
            return False
        
        try:
            cache_key = self._generate_cache_key(text, model, tenant_id)
            
            # Serializar y guardar con TTL
            await self.direct_redis_conn.setex(
                cache_key,
                self.cache_ttl,
                json.dumps(embedding)
            )
            
            self._logger.debug(f"Embedding cacheado: {cache_key}")
            return True
            
        except Exception as e:
            self._logger.error(f"Error cacheando embedding: {e}")
            return False
    
    async def check_cache_availability(
        self,
        texts: List[str],
        model: str,
        tenant_id: str
    ) -> Dict[str, Any]:
        """
        Verifica qué textos están disponibles en cache.
        
        Args:
            texts: Lista de textos a verificar
            model: Modelo a usar
            tenant_id: ID del tenant
            
        Returns:
            Dict con información de disponibilidad
        """
        if not self.cache_enabled:
            return {"available": False, "count": 0, "indices": []}
        
        try:
            cached_count = 0
            cached_indices = []
            
            for i, text in enumerate(texts):
                cache_key = self._generate_cache_key(text, model, tenant_id)
                exists = await self.direct_redis_conn.exists(cache_key)
                if exists:
                    cached_count += 1
                    cached_indices.append(i)
            
            return {
                "available": cached_count > 0,
                "count": cached_count,
                "indices": cached_indices,
                "percentage": (cached_count / len(texts) * 100) if texts else 0
            }
            
        except Exception as e:
            self._logger.error(f"Error verificando disponibilidad de cache: {e}")
            return {"available": False, "count": 0, "indices": []}
    
    def _generate_cache_key(self, text: str, model: str, tenant_id: str) -> str:
        """
        Genera una clave de cache única para un embedding.
        
        Args:
            text: Texto del embedding
            model: Modelo usado
            tenant_id: ID del tenant
            
        Returns:
            Clave de cache
        """
        # Crear hash del texto para la clave
        text_hash = hashlib.sha256(text.encode()).hexdigest()[:16]
        
        # Incluir información del modelo para diferenciar embeddings
        model_clean = model.replace(".", "_").replace("-", "_")
        
        return f"{self.cache_prefix}:{tenant_id}:{model_clean}:{text_hash}"
    
    async def clear_tenant_cache(self, tenant_id: str) -> int:
        """
        Limpia todo el cache de un tenant.
        
        Args:
            tenant_id: ID del tenant
            
        Returns:
            Número de claves eliminadas
        """
        try:
            pattern = f"{self.cache_prefix}:{tenant_id}:*"
            
            # Buscar todas las claves del tenant
            cursor = 0
            deleted_count = 0
            
            while True:
                cursor, keys = await self.direct_redis_conn.scan(
                    cursor, match=pattern, count=100
                )
                
                if keys:
                    deleted = await self.direct_redis_conn.delete(*keys)
                    deleted_count += deleted
                
                if cursor == 0:
                    break
            
            self._logger.info(
                f"Cache limpiado para tenant {tenant_id}: "
                f"{deleted_count} claves eliminadas"
            )
            
            return deleted_count
            
        except Exception as e:
            self._logger.error(f"Error limpiando cache del tenant: {e}")
            return 0
```

### `embedding_service/clients/__init__.py`

```python
"""
Clientes del Embedding Service.
"""

from .openai_client import OpenAIClient

__all__ = ['OpenAIClient']
```

### `embedding_service/clients/openai_client.py`

```python
"""
Cliente para la API de OpenAI Embeddings.

Proporciona una interfaz limpia para generar embeddings
usando la API de OpenAI con manejo de errores y reintentos.
"""

import logging
import time
from typing import List, Optional, Dict, Any

import httpx
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type
)

from common.clients.base_http_client import BaseHTTPClient
from common.errors.http_errors import ServiceUnavailableError


class OpenAIClient(BaseHTTPClient):
    """
    Cliente asíncrono para la API de OpenAI Embeddings.
    
    Extiende BaseHTTPClient para proporcionar funcionalidad
    específica para la generación de embeddings.
    """
    
    def __init__(
        self, 
        api_key: str,
        base_url: str = "https://api.openai.com/v1",
        timeout: int = 30,
        max_retries: int = 3
    ):
        """
        Inicializa el cliente con la API key.
        
        Args:
            api_key: API key de OpenAI
            base_url: URL base de la API
            timeout: Timeout en segundos
            max_retries: Número máximo de reintentos
        """
        if not api_key:
            raise ValueError("API key de OpenAI es requerida")
        
        # Headers con autenticación
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        # Inicializar cliente base
        super().__init__(
            base_url=base_url,
            headers=headers
        )
        
        self.timeout = timeout
        self.max_retries = max_retries
        self.logger = logging.getLogger(__name__)
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(ServiceUnavailableError)
    )
    async def generate_embeddings(
        self,
        texts: List[str],
        model: str = "text-embedding-3-small",
        dimensions: Optional[int] = None,
        encoding_format: str = "float",
        user: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Genera embeddings para una lista de textos.
        
        Args:
            texts: Lista de textos para generar embeddings
            model: Modelo de embedding a usar
            dimensions: Dimensiones del embedding (opcional)
            encoding_format: Formato de codificación
            user: Identificador único del usuario
            
        Returns:
            Dict con embeddings y metadatos
            
        Raises:
            ServiceUnavailableError: Si el servicio no está disponible
            Exception: Para otros errores
        """
        start_time = time.time()
        
        # Filtrar textos vacíos y recordar sus posiciones
        non_empty_texts = []
        non_empty_indices = []
        for i, text in enumerate(texts):
            if text and text.strip():
                non_empty_texts.append(text)
                non_empty_indices.append(i)
        
        if not non_empty_texts:
            # Si todos los textos están vacíos, devolver embeddings de ceros
            dimensions = dimensions or 1536  # Default para text-embedding-3-small
            return {
                "embeddings": [[0.0] * dimensions for _ in texts],
                "model": model,
                "dimensions": dimensions,
                "total_tokens": 0,
                "prompt_tokens": 0,
                "total_tokens": 0,
                "processing_time_ms": 0
            }
        
        # Preparar payload
        payload = {
            "input": non_empty_texts,
            "model": model,
            "encoding_format": encoding_format
        }
        
        # Agregar parámetros opcionales
        if dimensions and model.startswith("text-embedding-3"):
            payload["dimensions"] = dimensions
        
        if user:
            payload["user"] = user
        
        self.logger.debug(
            f"Generando embeddings para {len(non_empty_texts)} textos con {model}"
        )
        
        try:
            # Hacer petición
            response = await self.post(
                "/embeddings",
                json=payload,
                timeout=self.timeout
            )
            
            # Parsear respuesta
            data = response.json()
            
            # Validar estructura
            if "data" not in data:
                raise ValueError("Respuesta inválida de OpenAI API: sin data")
            
            # Extraer embeddings
            embeddings_data = data["data"]
            embeddings_dict = {item["index"]: item["embedding"] for item in embeddings_data}
            
            # Reconstruir lista completa con embeddings vacíos donde corresponda
            dimensions_actual = len(embeddings_dict[0]) if embeddings_dict else (dimensions or 1536)
            full_embeddings = []
            
            for i in range(len(texts)):
                if i in non_empty_indices:
                    # Obtener el índice en la respuesta de OpenAI
                    response_idx = non_empty_indices.index(i)
                    full_embeddings.append(embeddings_dict[response_idx])
                else:
                    # Texto vacío, agregar embedding de ceros
                    full_embeddings.append([0.0] * dimensions_actual)
            
            # Extraer métricas
            usage = data.get("usage", {})
            processing_time_ms = int((time.time() - start_time) * 1000)
            
            # Log métricas
            self.logger.info(
                f"Embeddings generados en {processing_time_ms}ms. "
                f"Tokens: {usage.get('total_tokens', 0)}"
            )
            
            return {
                "embeddings": full_embeddings,
                "model": data.get("model", model),
                "dimensions": dimensions_actual,
                "prompt_tokens": usage.get("prompt_tokens", 0),
                "total_tokens": usage.get("total_tokens", 0),
                "processing_time_ms": processing_time_ms
            }
            
        except httpx.TimeoutException:
            self.logger.error(f"Timeout en llamada a OpenAI API después de {self.timeout}s")
            raise ServiceUnavailableError(
                f"OpenAI API timeout después de {self.timeout} segundos"
            )
        
        except Exception as e:
            self.logger.error(f"Error en llamada a OpenAI API: {str(e)}")
            raise
    
    async def list_models(self) -> List[Dict[str, Any]]:
        """
        Lista los modelos de embedding disponibles.
        
        Returns:
            Lista de modelos disponibles
        """
        try:
            response = await self.get("/models")
            data = response.json()
            
            # Filtrar solo modelos de embedding
            embedding_models = [
                model for model in data.get("data", [])
                if "embedding" in model.get("id", "")
            ]
            
            return embedding_models
            
        except Exception as e:
            self.logger.error(f"Error listando modelos: {e}")
            raise
    
    async def health_check(self) -> bool:
        """
        Verifica si la API de OpenAI está disponible.
        
        Returns:
            True si está disponible
        """
        try:
            # Intentar generar un embedding simple como health check
            result = await self.generate_embeddings(
                texts=["health check"],
                model="text-embedding-3-small"
            )
            return len(result["embeddings"]) > 0
            
        except Exception:
            return False
```

### `embedding_service/requirements.txt`

```python
# Core dependencies
fastapi==0.115.0
uvicorn[standard]==0.32.0
pydantic==2.10.0
pydantic-settings==2.6.0

# Redis
redis==5.0.0

# HTTP clients
httpx==0.28.0

# OpenAI (para tipos, aunque usamos httpx directamente)
openai==1.6.1

# Utilities
tenacity==8.5.0
python-dotenv==1.0.0

# Logging
python-json-logger==2.0.7

# Testing (optional)
pytest==8.3.0
pytest-asyncio==0.24.0
pytest-cov==5.0.0

# Common module dependencies
# Estas deberían estar en common/requirements.txt
# pero las incluimos por si se ejecuta de forma aislada
```

### `embedding_service/Dockerfile`

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Instalar dependencias del sistema
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copiar archivos de requirements
COPY requirements.txt .

# Instalar dependencias de Python
RUN pip install --no-cache-dir -r requirements.txt

# Copiar código de la aplicación
COPY . .

# Copiar módulo common (asumiendo estructura de monorepo)
COPY ../common /app/common

# Variables de entorno por defecto
ENV PYTHONPATH=/app
ENV EMBEDDING_SERVICE_NAME=embedding
ENV EMBEDDING_ENVIRONMENT=development
ENV EMBEDDING_LOG_LEVEL=INFO

# Puerto por defecto
EXPOSE 8003

# Comando de inicio
CMD ["python", "-m", "embedding_service.main"]
```