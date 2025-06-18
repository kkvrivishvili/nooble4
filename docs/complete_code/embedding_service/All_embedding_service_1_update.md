# Embedding Service Simplificado - Archivos Modificados

## `embedding_service/handlers/__init__.py`

```python
"""
Handlers del Embedding Service.
"""

from .openai_handler import OpenAIHandler
from .validation_handler import ValidationHandler

__all__ = ['OpenAIHandler', 'ValidationHandler']
```

## `embedding_service/models/payloads.py`

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
        if len(v) > 100:  # Límite básico para evitar sobrecarga
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
    
    # Metadatos del lote
    collection_id: Optional[UUID] = Field(None)
    document_ids: Optional[List[str]] = Field(None)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class EmbeddingValidatePayload(BaseModel):
    """Payload para embedding.validate - Validación de capacidad."""
    
    texts: List[str] = Field(..., description="Textos a validar")
    model: Optional[str] = Field(None, description="Modelo a validar")


# --- Modelos de Response (para DomainActionResponse.data o callbacks) ---

class EmbeddingResult(BaseModel):
    """Representa un embedding individual."""
    
    text_index: int = Field(..., description="Índice del texto original")
    embedding: List[float] = Field(..., description="Vector de embedding")
    dimensions: int = Field(..., description="Dimensiones del vector")
    

class EmbeddingResponse(BaseModel):
    """Respuesta para embedding.generate."""
    
    embeddings: List[List[float]] = Field(..., description="Lista de embeddings generados")
    model: str = Field(..., description="Modelo utilizado")
    dimensions: int = Field(..., description="Dimensiones de los embeddings")
    
    # Métricas
    total_tokens: int = Field(..., description="Total de tokens procesados")
    processing_time_ms: int = Field(..., description="Tiempo de procesamiento en ms")
    
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
    
    # Performance
    avg_processing_time_ms: float = Field(0.0)
    avg_texts_per_request: float = Field(0.0)
    
    # Por modelo
    usage_by_model: Dict[str, int] = Field(default_factory=dict)
```

## `embedding_service/handlers/validation_handler.py`

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
    
    Verifica formatos y disponibilidad de modelos.
    """
    
    def __init__(self, app_settings, direct_redis_conn=None):
        """
        Inicializa el handler de validación.
        
        Args:
            app_settings: EmbeddingServiceSettings
            direct_redis_conn: Conexión Redis opcional
        """
        super().__init__(app_settings, direct_redis_conn)
        
        # Configurar límites básicos
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
            "model_available": True
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
```

## `embedding_service/services/embedding_service.py`

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
        
        # Generar embeddings directamente
        response = await self.openai_handler.generate_embeddings(
            texts=payload.texts,
            model=payload.model,
            dimensions=payload.dimensions,
            encoding_format=payload.encoding_format,
            tenant_id=action.tenant_id,
            trace_id=action.trace_id
        )
        
        # Construir respuesta
        from ..models.payloads import EmbeddingResponse
        embedding_response = EmbeddingResponse(
            embeddings=response["embeddings"],
            model=response["model"],
            dimensions=response["dimensions"],
            total_tokens=response.get("total_tokens", 0),
            processing_time_ms=response.get("processing_time_ms", 0),
            metadata={
                "collection_id": str(payload.collection_id) if payload.collection_id else None,
                "chunk_ids": payload.chunk_ids
            }
        )
        
        # Tracking de métricas
        await self._track_metrics(action, embedding_response)
        
        return embedding_response.model_dump()
    
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
        
        # Generar embedding
        result = await self.openai_handler.generate_embeddings(
            texts=[query_text],
            model=payload.model,
            tenant_id=action.tenant_id,
            trace_id=action.trace_id
        )
        
        embedding = result["embeddings"][0]
        
        from ..models.payloads import EmbeddingQueryResponse
        response = EmbeddingQueryResponse(
            embedding=embedding,
            model=result["model"],
            dimensions=result["dimensions"],
            tokens=result.get("prompt_tokens", 0),
            processing_time_ms=result.get("processing_time_ms", 0)
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
                        dimensions=result["dimensions"]
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
        
        from ..models.payloads import EmbeddingValidationResponse
        response = EmbeddingValidationResponse(
            is_valid=validation_result["is_valid"],
            can_process=validation_result["can_process"],
            text_count=len(payload.texts),
            estimated_tokens=validation_result["estimated_tokens"],
            model_available=validation_result["model_available"],
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
            
            if hasattr(response, "total_tokens"):
                await self.direct_redis_conn.hincrby(metrics_key, "total_tokens", response.total_tokens)
            
            # TTL de 7 días
            await self.direct_redis_conn.expire(metrics_key, 86400 * 7)
            
        except Exception as e:
            self._logger.error(f"Error tracking metrics: {e}")
```

## `embedding_service/handlers/openai_handler.py`

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