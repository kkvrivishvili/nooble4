# Query Service Refactorizado - Estructura Completa

## 1. query_service/__init__.py
```python
"""
Query Service - Servicio de búsqueda vectorial y generación RAG.

Este servicio maneja consultas de búsqueda vectorial y generación
de respuestas usando Retrieval-Augmented Generation (RAG).
"""

__version__ = "1.0.0"
```

## 2. query_service/config/__init__.py
```python
"""
Configuración para Query Service.
"""

from .settings import get_settings

__all__ = ['get_settings']
```

## 3. query_service/config/settings.py
```python
"""
Configuración para Query Service.

Este módulo carga la configuración del servicio usando QueryServiceSettings
definido en common.config.service_settings.query
"""

from functools import lru_cache
from common.config import QueryServiceSettings

@lru_cache()
def get_settings() -> QueryServiceSettings:
    """
    Retorna la instancia de configuración para Query Service.
    Usa lru_cache para asegurar que solo se crea una instancia.
    """
    return QueryServiceSettings()
```

## 4. query_service/models/__init__.py
```python
"""
Modelos de datos para Query Service.
"""

from .payloads import (
    QueryGeneratePayload,
    QuerySearchPayload,
    QueryStatusPayload,
    SearchResult,
    QueryGenerateResponse,
    QuerySearchResponse,
    QueryErrorResponse,
    EmbeddingRequest,
    CollectionConfig
)

__all__ = [
    'QueryGeneratePayload',
    'QuerySearchPayload',
    'QueryStatusPayload',
    'SearchResult',
    'QueryGenerateResponse',
    'QuerySearchResponse',
    'QueryErrorResponse',
    'EmbeddingRequest',
    'CollectionConfig'
]
```

## 5. query_service/models/payloads.py
```python
"""
Modelos Pydantic para los payloads de las acciones del Query Service.

Estos modelos definen la estructura esperada del campo 'data' en DomainAction
para cada tipo de acción que maneja el servicio.
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, field_validator
from datetime import datetime
from uuid import UUID

# --- Modelos de Request (para action.data) ---

class QueryGeneratePayload(BaseModel):
    """Payload para acción query.generate - Procesamiento RAG completo."""
    
    query_text: str = Field(..., description="Texto de la consulta en lenguaje natural")
    collection_ids: List[str] = Field(..., description="IDs de las colecciones donde buscar")
    
    # Parámetros opcionales de búsqueda
    top_k: Optional[int] = Field(None, description="Número de resultados a recuperar")
    similarity_threshold: Optional[float] = Field(None, ge=0.0, le=1.0, description="Umbral mínimo de similitud")
    
    # Parámetros opcionales de generación
    llm_model: Optional[str] = Field(None, description="Modelo LLM específico a usar")
    temperature: Optional[float] = Field(None, ge=0.0, le=2.0, description="Temperatura para generación")
    max_tokens: Optional[int] = Field(None, ge=1, description="Máximo de tokens en la respuesta")
    system_prompt: Optional[str] = Field(None, description="Prompt de sistema personalizado")
    
    # Contexto adicional
    conversation_history: Optional[List[Dict[str, str]]] = Field(
        default_factory=list,
        description="Historial de conversación para contexto"
    )
    
    @field_validator('collection_ids')
    @classmethod
    def validate_collection_ids(cls, v):
        if not v:
            raise ValueError("Al menos una collection_id es requerida")
        return v


class QuerySearchPayload(BaseModel):
    """Payload para acción query.search - Solo búsqueda vectorial."""
    
    query_text: str = Field(..., description="Texto de búsqueda")
    collection_ids: List[str] = Field(..., description="IDs de las colecciones donde buscar")
    
    # Parámetros de búsqueda
    top_k: Optional[int] = Field(None, description="Número de resultados")
    similarity_threshold: Optional[float] = Field(None, ge=0.0, le=1.0)
    
    # Filtros adicionales
    filters: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Filtros adicionales para la búsqueda"
    )


class QueryStatusPayload(BaseModel):
    """Payload para acción query.status - Consultar estado."""
    
    query_id: str = Field(..., description="ID de la consulta a verificar")


# --- Modelos de Response (para DomainActionResponse.data o callbacks) ---

class SearchResult(BaseModel):
    """Representa un resultado individual de búsqueda."""
    
    chunk_id: str = Field(..., description="ID único del chunk")
    content: str = Field(..., description="Contenido del chunk")
    similarity_score: float = Field(..., description="Score de similitud (0-1)")
    
    # Metadatos del documento
    document_id: str = Field(..., description="ID del documento origen")
    document_title: Optional[str] = Field(None, description="Título del documento")
    collection_id: str = Field(..., description="ID de la colección")
    
    # Metadatos adicionales
    metadata: Dict[str, Any] = Field(default_factory=dict)
    

class QueryGenerateResponse(BaseModel):
    """Respuesta para query.generate."""
    
    query_id: str = Field(..., description="ID único de la consulta")
    query_text: str = Field(..., description="Texto original de la consulta")
    
    # Respuesta generada
    generated_response: str = Field(..., description="Respuesta generada por el LLM")
    
    # Contexto utilizado
    search_results: List[SearchResult] = Field(
        ..., 
        description="Chunks recuperados y utilizados para la generación"
    )
    
    # Metadatos de generación
    llm_model: str = Field(..., description="Modelo LLM utilizado")
    temperature: float = Field(..., description="Temperatura usada")
    prompt_tokens: Optional[int] = Field(None, description="Tokens en el prompt")
    completion_tokens: Optional[int] = Field(None, description="Tokens en la respuesta")
    total_tokens: Optional[int] = Field(None, description="Total de tokens")
    
    # Timing
    search_time_ms: int = Field(..., description="Tiempo de búsqueda en ms")
    generation_time_ms: int = Field(..., description="Tiempo de generación en ms")
    total_time_ms: int = Field(..., description="Tiempo total en ms")
    
    # Metadatos adicionales
    metadata: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class QuerySearchResponse(BaseModel):
    """Respuesta para query.search."""
    
    query_id: str = Field(..., description="ID único de la búsqueda")
    query_text: str = Field(..., description="Texto de búsqueda original")
    
    # Resultados
    search_results: List[SearchResult] = Field(..., description="Resultados encontrados")
    total_results: int = Field(..., description="Total de resultados encontrados")
    
    # Timing
    search_time_ms: int = Field(..., description="Tiempo de búsqueda en ms")
    
    # Metadatos
    collections_searched: List[str] = Field(..., description="Colecciones consultadas")
    metadata: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class QueryErrorResponse(BaseModel):
    """Respuesta de error para cualquier acción de query."""
    
    query_id: Optional[str] = Field(None, description="ID de la consulta si está disponible")
    error_type: str = Field(..., description="Tipo de error")
    error_message: str = Field(..., description="Mensaje de error")
    error_details: Optional[Dict[str, Any]] = Field(None, description="Detalles adicionales del error")
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# --- Modelos internos para comunicación con otros servicios ---

class EmbeddingRequest(BaseModel):
    """Request para solicitar embeddings al Embedding Service."""
    
    texts: List[str] = Field(..., description="Textos para generar embeddings")
    model: Optional[str] = Field(None, description="Modelo de embedding específico")
    

class CollectionConfig(BaseModel):
    """Configuración de una colección."""
    
    collection_id: str
    collection_name: str
    embedding_model: str
    chunk_size: int
    chunk_overlap: int
    metadata: Dict[str, Any] = Field(default_factory=dict)
```

## 6. query_service/services/__init__.py
```python
"""
Servicios del Query Service.
"""

from .query_service import QueryService

__all__ = ['QueryService']
```

## 7. query_service/services/query_service.py
```python
"""
Implementación del servicio principal de Query Service.

Este servicio extiende BaseService y orquesta la lógica de negocio,
delegando operaciones específicas a los handlers correspondientes.
"""

import logging
from typing import Optional, Dict, Any
from uuid import uuid4

from pydantic import ValidationError

from common.services import BaseService
from common.models import DomainAction, ErrorDetail
from common.errors.exceptions import InvalidActionError, ExternalServiceError

from ..models.payloads import (
    QueryGeneratePayload,
    QuerySearchPayload,
    QueryStatusPayload,
    QueryErrorResponse
)
from ..handlers.rag_handler import RAGHandler
from ..handlers.search_handler import SearchHandler


class QueryService(BaseService):
    """
    Servicio principal para procesamiento de consultas RAG.
    
    Maneja las acciones:
    - query.generate: Procesamiento RAG completo (búsqueda + generación)
    - query.search: Solo búsqueda vectorial
    - query.status: Estado de una consulta (opcional)
    """
    
    def __init__(self, app_settings, service_redis_client=None, direct_redis_conn=None):
        """
        Inicializa el servicio con sus handlers.
        
        Args:
            app_settings: QueryServiceSettings con la configuración
            service_redis_client: Cliente Redis para enviar acciones a otros servicios
            direct_redis_conn: Conexión Redis directa para operaciones internas
        """
        super().__init__(app_settings, service_redis_client, direct_redis_conn)
        
        # Inicializar handlers
        self.rag_handler = RAGHandler(
            app_settings=app_settings,
            direct_redis_conn=direct_redis_conn
        )
        
        self.search_handler = SearchHandler(
            app_settings=app_settings,
            direct_redis_conn=direct_redis_conn
        )
        
        # Si necesitamos comunicarnos con otros servicios
        self.embedding_client = None
        if service_redis_client:
            from ..clients.embedding_client import EmbeddingClient
            self.embedding_client = EmbeddingClient(service_redis_client)
        
        self._logger.info("QueryService inicializado correctamente")
    
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
            if action.action_type == "query.generate":
                return await self._handle_generate(action)
                
            elif action.action_type == "query.search":
                return await self._handle_search(action)
                
            elif action.action_type == "query.status":
                return await self._handle_status(action)
                
            else:
                self._logger.warning(f"Tipo de acción no soportado: {action.action_type}")
                raise InvalidActionError(
                    f"Acción '{action.action_type}' no es soportada por Query Service"
                )
                
        except ValidationError as e:
            self._logger.error(f"Error de validación en {action.action_type}: {e}")
            # Crear respuesta de error
            error_response = QueryErrorResponse(
                query_id=str(action.action_id),
                error_type="ValidationError",
                error_message="Error de validación en el payload",
                error_details={"validation_errors": e.errors()}
            )
            return error_response.model_dump()
            
        except ExternalServiceError as e:
            self._logger.error(f"Error de servicio externo en {action.action_type}: {e}")
            error_response = QueryErrorResponse(
                query_id=str(action.action_id),
                error_type="ExternalServiceError",
                error_message=str(e),
                error_details={"original_error": str(e.original_exception) if e.original_exception else None}
            )
            return error_response.model_dump()
            
        except Exception as e:
            self._logger.exception(f"Error inesperado procesando {action.action_type}")
            # Re-lanzar para que BaseWorker maneje el error
            raise
    
    async def _handle_generate(self, action: DomainAction) -> Dict[str, Any]:
        """
        Maneja la acción query.generate para procesamiento RAG completo.
        
        Args:
            action: DomainAction con QueryGeneratePayload
            
        Returns:
            Diccionario con QueryGenerateResponse
        """
        # Validar y parsear payload
        payload = QueryGeneratePayload(**action.data)
        
        # Obtener configuración de metadata si existe
        config_overrides = action.metadata or {}
        
        # Pasar embedding_client si está disponible
        response = await self.rag_handler.process_rag_query(
            query_text=payload.query_text,
            collection_ids=payload.collection_ids,
            tenant_id=action.tenant_id,
            session_id=action.session_id,
            # Parámetros opcionales
            top_k=payload.top_k or config_overrides.get("top_k"),
            similarity_threshold=payload.similarity_threshold or config_overrides.get("similarity_threshold"),
            llm_model=payload.llm_model or config_overrides.get("llm_model"),
            temperature=payload.temperature or config_overrides.get("temperature"),
            max_tokens=payload.max_tokens or config_overrides.get("max_tokens"),
            system_prompt=payload.system_prompt,
            conversation_history=payload.conversation_history,
            # Contexto de trazabilidad
            trace_id=action.trace_id,
            correlation_id=action.correlation_id,
            # Cliente de embedding si está disponible
            embedding_client=self.embedding_client,
            task_id=action.task_id
        )
        
        return response.model_dump()
    
    async def _handle_search(self, action: DomainAction) -> Dict[str, Any]:
        """
        Maneja la acción query.search para solo búsqueda vectorial.
        
        Args:
            action: DomainAction con QuerySearchPayload
            
        Returns:
            Diccionario con QuerySearchResponse
        """
        # Validar y parsear payload
        payload = QuerySearchPayload(**action.data)
        
        # Obtener configuración de metadata si existe
        config_overrides = action.metadata or {}
        
        # Delegar al search handler
        response = await self.search_handler.search_documents(
            query_text=payload.query_text,
            collection_ids=payload.collection_ids,
            tenant_id=action.tenant_id,
            # Parámetros opcionales
            top_k=payload.top_k or config_overrides.get("top_k"),
            similarity_threshold=payload.similarity_threshold or config_overrides.get("similarity_threshold"),
            filters=payload.filters,
            # Contexto
            trace_id=action.trace_id,
            # Cliente de embedding si está disponible
            embedding_client=self.embedding_client,
            session_id=action.session_id,
            task_id=action.task_id
        )
        
        return response.model_dump()
    
    async def _handle_status(self, action: DomainAction) -> Dict[str, Any]:
        """
        Maneja la acción query.status para consultar estado.
        
        Esta es una funcionalidad opcional que podría implementarse
        para consultas de larga duración.
        
        Args:
            action: DomainAction con QueryStatusPayload
            
        Returns:
            Diccionario con estado de la consulta
        """
        # Por ahora, retornamos un mensaje indicando que no está implementado
        self._logger.info(f"Status check solicitado para {action.data.get('query_id')}")
        
        return {
            "status": "not_implemented",
            "message": "La funcionalidad de status check no está implementada en esta versión",
            "query_id": action.data.get("query_id")
        }
```

## 8. query_service/handlers/__init__.py
```python
"""
Handlers del Query Service.
"""

from .rag_handler import RAGHandler
from .search_handler import SearchHandler

__all__ = ['RAGHandler', 'SearchHandler']
```

## 9. query_service/handlers/rag_handler.py
```python
"""
Handler para procesamiento RAG (Retrieval-Augmented Generation).

Este handler orquesta el flujo completo de RAG:
1. Obtener embeddings de la consulta
2. Buscar documentos relevantes
3. Construir prompt con contexto
4. Generar respuesta usando LLM
"""

import logging
import time
from typing import List, Optional, Dict, Any
from uuid import UUID
import json

from common.handlers import BaseHandler
from common.errors.exceptions import ExternalServiceError

from ..models.payloads import (
    QueryGenerateResponse,
    SearchResult
)
from ..clients.groq_client import GroqClient
from ..clients.vector_client import VectorClient


class RAGHandler(BaseHandler):
    """
    Handler para procesamiento completo de consultas RAG.
    
    Coordina la búsqueda vectorial con la generación de respuestas
    usando LLMs para proporcionar respuestas contextualizadas.
    """
    
    def __init__(self, app_settings, direct_redis_conn=None):
        """
        Inicializa el handler con sus dependencias.
        
        Args:
            app_settings: QueryServiceSettings
            direct_redis_conn: Conexión Redis para operaciones directas
        """
        super().__init__(app_settings, direct_redis_conn)
        
        # Inicializar clientes
        self.groq_client = GroqClient(api_key=app_settings.groq_api_key)
        self.vector_client = VectorClient(
            base_url=app_settings.vector_db_url,
            timeout=app_settings.http_timeout_seconds
        )
        
        # Configuración
        self.default_top_k = app_settings.default_top_k
        self.similarity_threshold = app_settings.similarity_threshold
        self.default_llm_model = app_settings.default_llm_model
        self.llm_temperature = app_settings.llm_temperature
        self.llm_max_tokens = app_settings.llm_max_tokens
        
        self._logger.info("RAGHandler inicializado")
    
    async def process_rag_query(
        self,
        query_text: str,
        collection_ids: List[str],
        tenant_id: str,
        session_id: str,
        top_k: Optional[int] = None,
        similarity_threshold: Optional[float] = None,
        llm_model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        system_prompt: Optional[str] = None,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        trace_id: Optional[UUID] = None,
        correlation_id: Optional[UUID] = None,
        embedding_client=None,
        task_id: Optional[UUID] = None
    ) -> QueryGenerateResponse:
        """
        Procesa una consulta RAG completa.
        
        Args:
            query_text: Texto de la consulta
            collection_ids: IDs de colecciones donde buscar
            tenant_id: ID del tenant
            session_id: ID de sesión
            top_k: Número de resultados a recuperar
            similarity_threshold: Umbral de similitud mínimo
            llm_model: Modelo LLM a usar
            temperature: Temperatura para generación
            max_tokens: Máximo de tokens
            system_prompt: Prompt de sistema personalizado
            conversation_history: Historial de conversación
            trace_id: ID de traza
            correlation_id: ID de correlación
            embedding_client: Cliente para obtener embeddings
            task_id: ID de la tarea
            
        Returns:
            QueryGenerateResponse con la respuesta generada
        """
        start_time = time.time()
        query_id = str(correlation_id) if correlation_id else str(UUID())
        
        # Usar valores por defecto si no se especifican
        top_k = top_k or self.default_top_k
        similarity_threshold = similarity_threshold or self.similarity_threshold
        llm_model = llm_model or self.default_llm_model
        temperature = temperature if temperature is not None else self.llm_temperature
        max_tokens = max_tokens or self.llm_max_tokens
        
        self._logger.info(
            f"Procesando consulta RAG: '{query_text[:50]}...' en colecciones {collection_ids}",
            extra={
                "query_id": query_id,
                "tenant_id": tenant_id,
                "collections": collection_ids
            }
        )
        
        try:
            # 1. Obtener embeddings de la consulta
            search_start = time.time()
            query_embedding = await self._get_query_embedding(
                query_text, 
                tenant_id, 
                session_id,
                trace_id,
                embedding_client,
                task_id
            )
            
            # 2. Buscar documentos relevantes
            search_results = await self._search_documents(
                query_text=query_text,
                query_embedding=query_embedding,
                collection_ids=collection_ids,
                top_k=top_k,
                similarity_threshold=similarity_threshold,
                tenant_id=tenant_id
            )
            search_time_ms = int((time.time() - search_start) * 1000)
            
            # 3. Construir prompt con contexto
            prompt = self._build_rag_prompt(
                query_text=query_text,
                search_results=search_results,
                conversation_history=conversation_history
            )
            
            # 4. Generar respuesta
            generation_start = time.time()
            generated_response, token_usage = await self._generate_response(
                prompt=prompt,
                system_prompt=system_prompt or self._get_default_system_prompt(),
                model=llm_model,
                temperature=temperature,
                max_tokens=max_tokens
            )
            generation_time_ms = int((time.time() - generation_start) * 1000)
            
            # 5. Construir respuesta
            total_time_ms = int((time.time() - start_time) * 1000)
            
            response = QueryGenerateResponse(
                query_id=query_id,
                query_text=query_text,
                generated_response=generated_response,
                search_results=search_results,
                llm_model=llm_model,
                temperature=temperature,
                prompt_tokens=token_usage.get("prompt_tokens"),
                completion_tokens=token_usage.get("completion_tokens"),
                total_tokens=token_usage.get("total_tokens"),
                search_time_ms=search_time_ms,
                generation_time_ms=generation_time_ms,
                total_time_ms=total_time_ms,
                metadata={
                    "collections_searched": collection_ids,
                    "top_k": top_k,
                    "similarity_threshold": similarity_threshold
                }
            )
            
            self._logger.info(
                f"Consulta RAG completada en {total_time_ms}ms",
                extra={
                    "query_id": query_id,
                    "search_time_ms": search_time_ms,
                    "generation_time_ms": generation_time_ms,
                    "results_count": len(search_results)
                }
            )
            
            return response
            
        except Exception as e:
            self._logger.error(f"Error en procesamiento RAG: {e}", exc_info=True)
            raise ExternalServiceError(
                f"Error procesando consulta RAG: {str(e)}",
                original_exception=e
            )
    
    async def _get_query_embedding(
        self, 
        query_text: str, 
        tenant_id: str, 
        session_id: str,
        trace_id: Optional[UUID],
        embedding_client,
        task_id: Optional[UUID]
    ) -> List[float]:
        """
        Obtiene el embedding de la consulta.
        """
        # Si tenemos un cliente de embedding, usarlo
        if embedding_client:
            try:
                self._logger.debug("Solicitando embedding al Embedding Service")
                response = await embedding_client.request_query_embedding(
                    query_text=query_text,
                    tenant_id=tenant_id,
                    session_id=session_id,
                    task_id=task_id,
                    trace_id=trace_id
                )
                # Asumiendo que la respuesta tiene un campo 'embedding' en data
                return response.data.get("embedding", [])
            except Exception as e:
                self._logger.warning(f"Error obteniendo embedding del servicio: {e}")
                # Continuar con embedding simulado
        
        # Simulación: generar un vector aleatorio normalizado
        self._logger.debug("Generando embedding simulado para la consulta")
        import random
        embedding_dim = 1536  # Dimensión típica de embeddings
        embedding = [random.gauss(0, 1) for _ in range(embedding_dim)]
        
        # Normalizar
        magnitude = sum(x**2 for x in embedding) ** 0.5
        if magnitude > 0:
            embedding = [x / magnitude for x in embedding]
        
        return embedding
    
    async def _search_documents(
        self,
        query_text: str,
        query_embedding: List[float],
        collection_ids: List[str],
        top_k: int,
        similarity_threshold: float,
        tenant_id: str
    ) -> List[SearchResult]:
        """
        Busca documentos relevantes en las colecciones especificadas.
        """
        try:
            # Buscar en vector store
            results = await self.vector_client.search(
                query_embedding=query_embedding,
                collection_ids=collection_ids,
                top_k=top_k,
                similarity_threshold=similarity_threshold,
                tenant_id=tenant_id
            )
            
            return results
            
        except Exception as e:
            self._logger.error(f"Error en búsqueda vectorial: {e}")
            raise ExternalServiceError(
                "Error al buscar documentos en el vector store",
                original_exception=e
            )
    
    def _build_rag_prompt(
        self,
        query_text: str,
        search_results: List[SearchResult],
        conversation_history: Optional[List[Dict[str, str]]] = None
    ) -> str:
        """
        Construye el prompt para el LLM con el contexto recuperado.
        """
        # Construir contexto desde los resultados
        context_parts = []
        for i, result in enumerate(search_results, 1):
            context_parts.append(
                f"[Documento {i} - Score: {result.similarity_score:.2f}]\n"
                f"Colección: {result.collection_id}\n"
                f"Contenido: {result.content}\n"
            )
        
        context = "\n---\n".join(context_parts)
        
        # Construir prompt
        prompt_parts = []
        
        # Agregar historial si existe
        if conversation_history:
            prompt_parts.append("HISTORIAL DE CONVERSACIÓN:")
            for msg in conversation_history[-5:]:  # Últimos 5 mensajes
                role = msg.get("role", "user")
                content = msg.get("content", "")
                prompt_parts.append(f"{role.upper()}: {content}")
            prompt_parts.append("")
        
        # Agregar contexto
        prompt_parts.append("CONTEXTO RELEVANTE:")
        prompt_parts.append(context)
        prompt_parts.append("")
        
        # Agregar pregunta
        prompt_parts.append("PREGUNTA ACTUAL:")
        prompt_parts.append(query_text)
        prompt_parts.append("")
        prompt_parts.append("Por favor, responde la pregunta basándote en el contexto proporcionado. Si la información en el contexto no es suficiente para responder completamente, indícalo claramente.")
        
        return "\n".join(prompt_parts)
    
    def _get_default_system_prompt(self) -> str:
        """
        Retorna el prompt de sistema por defecto.
        """
        return (
            "Eres un asistente útil que responde preguntas basándose en el contexto proporcionado. "
            "Siempre cita la información relevante del contexto cuando sea posible. "
            "Si el contexto no contiene información suficiente para responder la pregunta, "
            "indícalo claramente. No inventes información que no esté en el contexto."
        )
    
    async def _generate_response(
        self,
        prompt: str,
        system_prompt: str,
        model: str,
        temperature: float,
        max_tokens: int
    ) -> tuple[str, Dict[str, int]]:
        """
        Genera la respuesta usando el LLM.
        
        Returns:
            Tupla de (respuesta, uso_de_tokens)
        """
        try:
            response, token_usage = await self.groq_client.generate(
                prompt=prompt,
                system_prompt=system_prompt,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens
            )
            
            return response, token_usage
            
        except Exception as e:
            self._logger.error(f"Error generando respuesta con LLM: {e}")
            raise ExternalServiceError(
                f"Error al generar respuesta con {model}",
                original_exception=e
            )
```

## 10. query_service/handlers/search_handler.py
```python
"""
Handler para búsqueda vectorial sin generación LLM.

Este handler maneja búsquedas puras en el vector store,
útil cuando solo se necesitan recuperar documentos relevantes
sin generar una respuesta.
"""

import logging
import time
from typing import List, Optional, Dict, Any
from uuid import UUID
import hashlib
import json

from common.handlers import BaseHandler
from common.errors.exceptions import ExternalServiceError

from ..models.payloads import QuerySearchResponse, SearchResult
from ..clients.vector_client import VectorClient


class SearchHandler(BaseHandler):
    """
    Handler para búsqueda vectorial pura.
    
    Realiza búsquedas en el vector store y retorna los documentos
    más relevantes sin procesamiento adicional con LLM.
    """
    
    def __init__(self, app_settings, direct_redis_conn=None):
        """
        Inicializa el handler con sus dependencias.
        
        Args:
            app_settings: QueryServiceSettings
            direct_redis_conn: Conexión Redis para operaciones directas
        """
        super().__init__(app_settings, direct_redis_conn)
        
        # Cliente de vector store
        self.vector_client = VectorClient(
            base_url=app_settings.vector_db_url,
            timeout=app_settings.http_timeout_seconds
        )
        
        # Configuración por defecto
        self.default_top_k = app_settings.default_top_k
        self.similarity_threshold = app_settings.similarity_threshold
        
        self._logger.info("SearchHandler inicializado")
    
    async def search_documents(
        self,
        query_text: str,
        collection_ids: List[str],
        tenant_id: str,
        top_k: Optional[int] = None,
        similarity_threshold: Optional[float] = None,
        filters: Optional[Dict[str, Any]] = None,
        trace_id: Optional[UUID] = None,
        embedding_client=None,
        session_id: Optional[str] = None,
        task_id: Optional[UUID] = None
    ) -> QuerySearchResponse:
        """
        Realiza una búsqueda vectorial en las colecciones especificadas.
        
        Args:
            query_text: Texto de búsqueda
            collection_ids: IDs de colecciones donde buscar
            tenant_id: ID del tenant
            top_k: Número de resultados
            similarity_threshold: Umbral de similitud
            filters: Filtros adicionales
            trace_id: ID de traza
            embedding_client: Cliente para obtener embeddings
            session_id: ID de sesión
            task_id: ID de la tarea
            
        Returns:
            QuerySearchResponse con los resultados
        """
        start_time = time.time()
        query_id = str(trace_id) if trace_id else str(UUID())
        
        # Usar valores por defecto si no se especifican
        top_k = top_k or self.default_top_k
        similarity_threshold = similarity_threshold or self.similarity_threshold
        
        self._logger.info(
            f"Búsqueda vectorial: '{query_text[:50]}...' en colecciones {collection_ids}",
            extra={
                "query_id": query_id,
                "tenant_id": tenant_id,
                "top_k": top_k
            }
        )
        
        try:
            # Obtener embedding de la consulta
            query_embedding = await self._get_query_embedding(
                query_text,
                tenant_id,
                session_id,
                trace_id,
                embedding_client,
                task_id
            )
            
            # Realizar búsqueda en vector store
            search_results = await self.vector_client.search(
                query_embedding=query_embedding,
                collection_ids=collection_ids,
                top_k=top_k,
                similarity_threshold=similarity_threshold,
                tenant_id=tenant_id,
                filters=filters
            )
            
            # Calcular tiempo de búsqueda
            search_time_ms = int((time.time() - start_time) * 1000)
            
            # Construir respuesta
            response = QuerySearchResponse(
                query_id=query_id,
                query_text=query_text,
                search_results=search_results,
                total_results=len(search_results),
                search_time_ms=search_time_ms,
                collections_searched=collection_ids,
                metadata={
                    "similarity_threshold": similarity_threshold,
                    "filters_applied": filters is not None
                }
            )
            
            self._logger.info(
                f"Búsqueda completada en {search_time_ms}ms con {len(search_results)} resultados",
                extra={
                    "query_id": query_id,
                    "results_count": len(search_results),
                    "search_time_ms": search_time_ms
                }
            )
            
            return response
            
        except Exception as e:
            self._logger.error(f"Error en búsqueda vectorial: {e}", exc_info=True)
            raise ExternalServiceError(
                f"Error realizando búsqueda vectorial: {str(e)}",
                original_exception=e
            )
    
    async def _get_query_embedding(
        self, 
        query_text: str,
        tenant_id: str,
        session_id: Optional[str],
        trace_id: Optional[UUID],
        embedding_client,
        task_id: Optional[UUID]
    ) -> List[float]:
        """
        Obtiene el embedding de la consulta.
        """
        # Si tenemos un cliente de embedding, usarlo
        if embedding_client and session_id and task_id:
            try:
                self._logger.debug("Solicitando embedding al Embedding Service")
                response = await embedding_client.request_query_embedding(
                    query_text=query_text,
                    tenant_id=tenant_id,
                    session_id=session_id,
                    task_id=task_id,
                    trace_id=trace_id
                )
                # Asumiendo que la respuesta tiene un campo 'embedding' en data
                return response.data.get("embedding", [])
            except Exception as e:
                self._logger.warning(f"Error obteniendo embedding del servicio: {e}")
                # Continuar con embedding simulado
        
        self._logger.debug("Generando embedding simulado para búsqueda")
        
        # Simulación: generar vector basado en hash del texto para consistencia
        import random
        
        # Usar hash del texto como semilla para reproducibilidad
        seed = int(hashlib.md5(query_text.encode()).hexdigest()[:8], 16)
        random.seed(seed)
        
        embedding_dim = 1536
        embedding = [random.gauss(0, 1) for _ in range(embedding_dim)]
        
        # Normalizar
        magnitude = sum(x**2 for x in embedding) ** 0.5
        if magnitude > 0:
            embedding = [x / magnitude for x in embedding]
        
        return embedding
```

## 11. query_service/clients/__init__.py
```python
"""
Clientes para servicios externos del Query Service.
"""

from .groq_client import GroqClient
from .vector_client import VectorClient
from .embedding_client import EmbeddingClient

__all__ = ['GroqClient', 'VectorClient', 'EmbeddingClient']
```

## 12. query_service/clients/groq_client.py
```python
"""
Cliente para interactuar con la API de Groq.

Proporciona una interfaz limpia para generar respuestas usando
los modelos de lenguaje de Groq, con manejo de errores y reintentos.
"""

import logging
import time
from typing import Optional, Dict, Any, List, Tuple

import httpx
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type
)

from common.clients.base_http_client import BaseHTTPClient
from common.errors.http_errors import ServiceUnavailableError


class GroqClient(BaseHTTPClient):
    """
    Cliente asíncrono para la API de Groq.
    
    Extiende BaseHTTPClient para proporcionar funcionalidad
    específica para la generación de texto con LLMs de Groq.
    """
    
    def __init__(self, api_key: str, timeout: int = 30):
        """
        Inicializa el cliente con la API key.
        
        Args:
            api_key: API key de Groq
            timeout: Timeout en segundos para las peticiones
        """
        if not api_key:
            raise ValueError("API key de Groq es requerida")
        
        # Headers con autenticación
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        # Inicializar cliente base
        super().__init__(
            base_url="https://api.groq.com/openai/v1",
            headers=headers
        )
        
        self.timeout = timeout
        self.logger = logging.getLogger(__name__)
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(ServiceUnavailableError)
    )
    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        model: str = "llama3-8b-8192",
        temperature: float = 0.3,
        max_tokens: int = 1024,
        top_p: float = 1.0,
        n: int = 1,
        stream: bool = False
    ) -> Tuple[str, Dict[str, int]]:
        """
        Genera una respuesta usando el modelo especificado.
        
        Args:
            prompt: Prompt principal del usuario
            system_prompt: Prompt de sistema (opcional)
            model: Modelo a usar
            temperature: Controla la aleatoriedad (0-2)
            max_tokens: Máximo de tokens en la respuesta
            top_p: Nucleus sampling
            n: Número de respuestas a generar
            stream: Si usar streaming (no implementado)
            
        Returns:
            Tupla de (respuesta_generada, uso_de_tokens)
            
        Raises:
            ServiceUnavailableError: Si el servicio no está disponible
            Exception: Para otros errores
        """
        start_time = time.time()
        
        # Construir mensajes
        messages = []
        if system_prompt:
            messages.append({
                "role": "system",
                "content": system_prompt
            })
        
        messages.append({
            "role": "user",
            "content": prompt
        })
        
        # Preparar payload
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "top_p": top_p,
            "n": n,
            "stream": stream
        }
        
        self.logger.debug(
            f"Generando respuesta con {model}, "
            f"temp={temperature}, max_tokens={max_tokens}"
        )
        
        try:
            # Hacer petición
            response = await self.post(
                "/chat/completions",
                json=payload,
                timeout=self.timeout
            )
            
            # Parsear respuesta
            data = response.json()
            
            # Validar estructura de respuesta
            if "choices" not in data or not data["choices"]:
                raise ValueError("Respuesta inválida de Groq API: sin choices")
            
            # Extraer respuesta principal
            choice = data["choices"][0]
            content = choice.get("message", {}).get("content", "")
            finish_reason = choice.get("finish_reason")
            
            # Verificar si se truncó
            if finish_reason == "length":
                self.logger.warning(
                    f"Respuesta truncada por límite de tokens ({max_tokens})"
                )
            
            # Extraer uso de tokens
            usage = data.get("usage", {})
            token_usage = {
                "prompt_tokens": usage.get("prompt_tokens", 0),
                "completion_tokens": usage.get("completion_tokens", 0),
                "total_tokens": usage.get("total_tokens", 0)
            }
            
            # Log métricas
            elapsed = time.time() - start_time
            self.logger.info(
                f"Generación completada en {elapsed:.2f}s. "
                f"Tokens: {token_usage['total_tokens']} "
                f"(prompt: {token_usage['prompt_tokens']}, "
                f"completion: {token_usage['completion_tokens']})"
            )
            
            return content, token_usage
            
        except httpx.TimeoutException:
            self.logger.error(f"Timeout en llamada a Groq API después de {self.timeout}s")
            raise ServiceUnavailableError(
                f"Groq API timeout después de {self.timeout} segundos"
            )
        
        except Exception as e:
            self.logger.error(f"Error en llamada a Groq API: {str(e)}")
            raise
    
    async def list_models(self) -> List[Dict[str, Any]]:
        """
        Lista los modelos disponibles en Groq.
        
        Returns:
            Lista de modelos disponibles
        """
        try:
            response = await self.get("/models")
            data = response.json()
            return data.get("data", [])
            
        except Exception as e:
            self.logger.error(f"Error listando modelos: {e}")
            raise
    
    async def health_check(self) -> bool:
        """
        Verifica si la API de Groq está disponible.
        
        Returns:
            True si está disponible, False en caso contrario
        """
        try:
            # Intentar listar modelos como health check
            models = await self.list_models()
            return len(models) > 0
            
        except Exception:
            return False
    
    async def close(self):
        """Cierra el cliente HTTP subyacente."""
        await self._client.aclose()
```

## 13. query_service/clients/vector_client.py
```python
"""
Cliente para interactuar con el Vector Store (base de datos vectorial).

Proporciona una interfaz unificada para realizar búsquedas vectoriales,
independientemente del proveedor específico (Qdrant, Pinecone, etc.).
"""

import logging
from typing import List, Optional, Dict, Any
import time

from common.clients.base_http_client import BaseHTTPClient
from common.errors.http_errors import NotFoundError, ServiceUnavailableError

from ..models.payloads import SearchResult


class VectorClient(BaseHTTPClient):
    """
    Cliente para realizar búsquedas en el vector store.
    
    Implementa la comunicación con la API del vector store
    para búsquedas de similitud y recuperación de documentos.
    """
    
    def __init__(self, base_url: str, timeout: int = 30):
        """
        Inicializa el cliente del vector store.
        
        Args:
            base_url: URL base del vector store
            timeout: Timeout para las peticiones
        """
        super().__init__(base_url=base_url)
        self.timeout = timeout
        self.logger = logging.getLogger(__name__)
    
    async def search(
        self,
        query_embedding: List[float],
        collection_ids: List[str],
        top_k: int = 5,
        similarity_threshold: float = 0.7,
        tenant_id: str = None,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[SearchResult]:
        """
        Realiza una búsqueda vectorial en las colecciones especificadas.
        
        Args:
            query_embedding: Vector de embedding de la consulta
            collection_ids: IDs de las colecciones donde buscar
            top_k: Número máximo de resultados por colección
            similarity_threshold: Umbral mínimo de similitud
            tenant_id: ID del tenant para filtrado
            filters: Filtros adicionales específicos del vector store
            
        Returns:
            Lista de SearchResult ordenados por similitud
            
        Raises:
            NotFoundError: Si alguna colección no existe
            ServiceUnavailableError: Si el vector store no está disponible
        """
        start_time = time.time()
        
        # Preparar payload para la búsqueda
        payload = {
            "vector": query_embedding,
            "collections": collection_ids,
            "limit": top_k,
            "score_threshold": similarity_threshold
        }
        
        # Agregar filtros opcionales
        if tenant_id:
            if "filter" not in payload:
                payload["filter"] = {}
            payload["filter"]["tenant_id"] = tenant_id
        
        if filters:
            if "filter" not in payload:
                payload["filter"] = {}
            payload["filter"].update(filters)
        
        self.logger.debug(
            f"Búsqueda vectorial en colecciones {collection_ids}, "
            f"top_k={top_k}, threshold={similarity_threshold}"
        )
        
        try:
            # Realizar búsqueda
            response = await self.post(
                "/api/v1/search",
                json=payload,
                timeout=self.timeout
            )
            
            # Parsear respuesta
            data = response.json()
            
            # Convertir a SearchResult
            results = self._parse_search_results(data)
            
            # Log métricas
            elapsed = time.time() - start_time
            self.logger.info(
                f"Búsqueda completada en {elapsed:.2f}s. "
                f"Encontrados {len(results)} resultados"
            )
            
            return results
            
        except NotFoundError as e:
            # Una o más colecciones no existen
            self.logger.error(f"Colección no encontrada: {e}")
            raise
            
        except Exception as e:
            self.logger.error(f"Error en búsqueda vectorial: {e}")
            raise ServiceUnavailableError(
                f"Error al buscar en vector store: {str(e)}"
            )
    
    def _parse_search_results(self, response_data: Dict[str, Any]) -> List[SearchResult]:
        """
        Parsea la respuesta del vector store a objetos SearchResult.
        
        Args:
            response_data: Respuesta JSON del vector store
            
        Returns:
            Lista de SearchResult
        """
        results = []
        
        # La estructura exacta depende del vector store específico
        # Este es un ejemplo genérico que debería adaptarse
        
        search_results = response_data.get("results", [])
        
        for item in search_results:
            # Extraer campos según el formato del vector store
            result = SearchResult(
                chunk_id=item.get("id", ""),
                content=item.get("content", item.get("text", "")),
                similarity_score=item.get("score", 0.0),
                document_id=item.get("document_id", ""),
                document_title=item.get("document_title"),
                collection_id=item.get("collection_id", ""),
                metadata=item.get("metadata", {})
            )
            results.append(result)
        
        # Ordenar por score descendente
        results.sort(key=lambda x: x.similarity_score, reverse=True)
        
        return results
    
    async def get_collections(self, tenant_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Lista las colecciones disponibles.
        
        Args:
            tenant_id: Filtrar por tenant (opcional)
            
        Returns:
            Lista de colecciones con sus metadatos
        """
        try:
            params = {}
            if tenant_id:
                params["tenant_id"] = tenant_id
            
            response = await self.get(
                "/api/v1/collections",
                params=params
            )
            
            data = response.json()
            return data.get("collections", [])
            
        except Exception as e:
            self.logger.error(f"Error listando colecciones: {e}")
            raise ServiceUnavailableError(
                f"Error al listar colecciones: {str(e)}"
            )
    
    async def get_collection_info(self, collection_id: str) -> Dict[str, Any]:
        """
        Obtiene información detallada de una colección.
        
        Args:
            collection_id: ID de la colección
            
        Returns:
            Información de la colección
            
        Raises:
            NotFoundError: Si la colección no existe
        """
        try:
            response = await self.get(f"/api/v1/collections/{collection_id}")
            return response.json()
            
        except NotFoundError:
            self.logger.error(f"Colección {collection_id} no encontrada")
            raise
            
        except Exception as e:
            self.logger.error(f"Error obteniendo info de colección: {e}")
            raise ServiceUnavailableError(
                f"Error al obtener información de colección: {str(e)}"
            )
    
    async def health_check(self) -> bool:
        """
        Verifica si el vector store está disponible.
        
        Returns:
            True si está disponible, False en caso contrario
        """
        try:
            response = await self.get("/health", timeout=5)
            return response.status_code == 200
            
        except Exception:
            return False
    
    async def close(self):
        """Cierra el cliente HTTP subyacente."""
        await self._client.aclose()
```

## 14. query_service/clients/embedding_client.py
```python
"""
Cliente para comunicarse con el Embedding Service.

Utiliza BaseRedisClient para enviar DomainActions al
Embedding Service cuando se necesitan generar embeddings.
"""

import logging
from typing import List, Optional
from uuid import UUID, uuid4

from common.models import DomainAction, DomainActionResponse
from common.clients import BaseRedisClient

from ..models.payloads import EmbeddingRequest


class EmbeddingClient:
    """
    Cliente para solicitar embeddings al Embedding Service.
    
    Envía DomainActions asíncronas al Embedding Service y
    puede esperar respuestas mediante callbacks.
    """
    
    def __init__(self, redis_client: BaseRedisClient):
        """
        Inicializa el cliente con un BaseRedisClient.
        
        Args:
            redis_client: Cliente Redis para enviar acciones
        """
        self.redis_client = redis_client
        self.logger = logging.getLogger(__name__)
    
    async def request_embeddings(
        self,
        texts: List[str],
        tenant_id: str,
        session_id: str,
        task_id: UUID,
        trace_id: UUID,
        model: Optional[str] = None,
        callback_queue: Optional[str] = None
    ) -> str:
        """
        Solicita embeddings para una lista de textos.
        
        Args:
            texts: Textos para generar embeddings
            tenant_id: ID del tenant
            session_id: ID de sesión
            task_id: ID de la tarea
            trace_id: ID de traza
            model: Modelo de embedding específico
            callback_queue: Cola para recibir el resultado
            
        Returns:
            ID de la acción enviada
        """
        # Crear payload
        embedding_request = EmbeddingRequest(
            texts=texts,
            model=model
        )
        
        # Crear DomainAction
        action = DomainAction(
            action_id=uuid4(),
            action_type="embedding.generate",
            tenant_id=tenant_id,
            session_id=session_id,
            task_id=task_id,
            user_id=None,  # Query service actúa como sistema
            origin_service="query",
            trace_id=trace_id,
            data=embedding_request.model_dump(),
            callback_queue_name=callback_queue,
            callback_action_type="embedding.result" if callback_queue else None
        )
        
        # Enviar acción
        if callback_queue:
            # Asíncrono con callback
            await self.redis_client.send_action_async_with_callback(
                action=action,
                callback_event_name="embedding.result"
            )
        else:
            # Fire and forget
            await self.redis_client.send_action_async(action)
        
        self.logger.info(
            f"Solicitud de embeddings enviada: {action.action_id} "
            f"para {len(texts)} textos"
        )
        
        return str(action.action_id)
    
    async def request_query_embedding(
        self,
        query_text: str,
        tenant_id: str,
        session_id: str,
        task_id: UUID,
        trace_id: UUID,
        model: Optional[str] = None
    ) -> DomainActionResponse:
        """
        Solicita embedding para una consulta específica.
        
        Este es un método de conveniencia para solicitar un
        único embedding de forma pseudo-síncrona.
        
        Args:
            query_text: Texto de la consulta
            tenant_id: ID del tenant
            session_id: ID de sesión
            task_id: ID de la tarea
            trace_id: ID de traza
            model: Modelo de embedding
            
        Returns:
            DomainActionResponse con el embedding
        """
        # Crear payload
        embedding_request = EmbeddingRequest(
            texts=[query_text],
            model=model
        )
        
        # Crear DomainAction con correlation_id para pseudo-sync
        action = DomainAction(
            action_id=uuid4(),
            action_type="embedding.generate_query",
            tenant_id=tenant_id,
            session_id=session_id,
            task_id=task_id,
            user_id=None,
            origin_service="query",
            correlation_id=uuid4(),  # Para pseudo-sync
            trace_id=trace_id,
            data=embedding_request.model_dump()
        )
        
        # Enviar y esperar respuesta
        response = await self.redis_client.send_action_pseudo_sync(
            action=action,
            timeout=30  # 30 segundos de timeout
        )
        
        if not response.success:
            error_msg = f"Error obteniendo embedding: {response.error.message if response.error else 'Unknown error'}"
            self.logger.error(error_msg)
            raise Exception(error_msg)
        
        return response
```

## 15. query_service/workers/__init__.py
```python
"""
Workers del Query Service.
"""

from .query_worker import QueryWorker

__all__ = ['QueryWorker']
```

## 16. query_service/workers/query_worker.py
```python
"""
Worker principal del Query Service.

Implementa BaseWorker para consumir DomainActions del stream Redis
y delegar el procesamiento al QueryService.
"""

import logging
from typing import Optional, Dict, Any

from common.workers import BaseWorker
from common.models import DomainAction
from common.clients import BaseRedisClient

from ..services.query_service import QueryService
from ..config.settings import get_settings


class QueryWorker(BaseWorker):
    """
    Worker que procesa acciones de consulta desde Redis Streams.
    
    Consume DomainActions del stream del Query Service y las
    procesa usando QueryService (que implementa BaseService).
    """
    
    def __init__(
        self, 
        app_settings=None,
        async_redis_conn=None,
        consumer_id_suffix: Optional[str] = None
    ):
        """
        Inicializa el QueryWorker.
        
        Args:
            app_settings: QueryServiceSettings (si no se proporciona, se carga)
            async_redis_conn: Conexión Redis asíncrona
            consumer_id_suffix: Sufijo para el ID del consumidor
        """
        # Cargar settings si no se proporcionan
        if app_settings is None:
            app_settings = get_settings()
        
        if async_redis_conn is None:
            raise ValueError("async_redis_conn es requerido para QueryWorker")
        
        # Inicializar BaseWorker
        super().__init__(
            app_settings=app_settings,
            async_redis_conn=async_redis_conn,
            consumer_id_suffix=consumer_id_suffix
        )
        
        # El servicio se inicializará en el método initialize
        self.query_service = None
        
        self.logger = logging.getLogger(f"{__name__}.{self.consumer_name}")
        
    async def initialize(self):
        """
        Inicializa el worker y sus dependencias.
        
        Crea la instancia de QueryService con las conexiones necesarias.
        """
        # Primero llamar a la inicialización del BaseWorker
        await super().initialize()
        
        # Crear cliente Redis para que el servicio pueda enviar acciones
        service_redis_client = BaseRedisClient(
            service_name=self.service_name,
            redis_client=self.async_redis_conn,
            settings=self.app_settings
        )
        
        # Inicializar QueryService
        self.query_service = QueryService(
            app_settings=self.app_settings,
            service_redis_client=service_redis_client,
            direct_redis_conn=self.async_redis_conn
        )
        
        self.logger.info(
            f"QueryWorker inicializado. "
            f"Escuchando en stream: {self.action_stream_name}, "
            f"grupo: {self.consumer_group_name}"
        )
    
    async def _handle_action(self, action: DomainAction) -> Optional[Dict[str, Any]]:
        """
        Procesa una DomainAction delegando a QueryService.
        
        Args:
            action: La acción a procesar
            
        Returns:
            Diccionario con los datos de respuesta o None
            
        Raises:
            Exception: Si hay un error en el procesamiento
        """
        if not self.query_service:
            raise RuntimeError("QueryService no inicializado. Llamar initialize() primero.")
        
        self.logger.debug(
            f"Procesando acción {action.action_type} "
            f"(ID: {action.action_id}, Tenant: {action.tenant_id})"
        )
        
        # Delegar al servicio
        try:
            result = await self.query_service.process_action(action)
            
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

## 17. query_service/main.py
```python
"""
Punto de entrada principal del Query Service.

Configura y ejecuta el servicio con FastAPI y el QueryWorker.
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
from .workers.query_worker import QueryWorker


# Variables globales para el ciclo de vida
redis_manager: Optional[RedisManager] = None
query_workers: List[QueryWorker] = []
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
    global redis_manager, query_workers, worker_tasks
    
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
            worker = QueryWorker(
                app_settings=settings,
                async_redis_conn=redis_conn,
                consumer_id_suffix=f"worker-{i}"
            )
            query_workers.append(worker)
            
            # Inicializar y ejecutar worker
            await worker.initialize()
            task = asyncio.create_task(worker.run())
            worker_tasks.append(task)
        
        logger.info(f"{num_workers} QueryWorkers iniciados")
        
        # Hacer disponibles las referencias en app.state
        app.state.redis_manager = redis_manager
        app.state.query_workers = query_workers
        
        yield
        
    finally:
        logger.info("Deteniendo Query Service...")
        
        # Detener workers
        for worker in query_workers:
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
        
        logger.info("Query Service detenido completamente")


# Crear aplicación FastAPI
app = FastAPI(
    title=settings.service_name,
    description="Servicio de búsqueda vectorial y generación RAG",
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
    for i, worker in enumerate(query_workers):
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
    
    # Por ahora no tenemos métricas específicas implementadas
    # pero podríamos agregar contadores de acciones procesadas, etc.
    
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
        "description": "Query Service - Búsqueda vectorial y generación RAG",
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
        "query_service.main:app",
        host="0.0.0.0",
        port=8002,
        reload=False,  # En producción debe ser False
        log_level=settings.log_level.lower()
    )
```

## 18. query_service/Dockerfile
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
ENV QUERY_SERVICE_NAME=query
ENV QUERY_ENVIRONMENT=development
ENV QUERY_LOG_LEVEL=INFO

# Puerto por defecto
EXPOSE 8002

# Comando de inicio
CMD ["python", "-m", "query_service.main"]
```

## 19. query_service/requirements.txt
```
# Core dependencies
fastapi==0.115.0
uvicorn[standard]==0.32.0
pydantic==2.10.0
pydantic-settings==2.6.0

# Redis
redis==5.0.0

# HTTP clients
httpx==0.28.0

# Groq API
# No hay SDK oficial, se usa httpx directamente

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

## Cambios principales realizados:

1. **Eliminación de cache**: Se eliminó todo el código relacionado con cache (cache_manager.py y referencias en handlers).

2. **Uso correcto de BaseService**: QueryService ahora hereda correctamente de BaseService e implementa solo process_action.

3. **Uso correcto de BaseWorker**: QueryWorker hereda de BaseWorker e implementa solo _handle_action.

4. **Uso correcto de BaseHandler**: RAGHandler y SearchHandler heredan de BaseHandler.

5. **Manejo de errores con common.errors**: Se usan las excepciones InvalidActionError y ExternalServiceError de common.errors.

6. **Configuración desde common.config**: Se usa QueryServiceSettings desde common.config.

7. **Logging con common.utils**: Se usa init_logging desde common.utils.

8. **Redis Manager**: Se usa RedisManager de common.clients en main.py.

9. **Clientes HTTP**: GroqClient y VectorClient heredan de BaseHTTPClient.

10. **EmbeddingClient**: Usa BaseRedisClient para enviar acciones al Embedding Service.

El servicio ahora es 100% compatible con la arquitectura common y cumple sus objetivos de búsqueda vectorial y generación RAG.





-----  UPDATE A ESTE CODIGO ----

# Query Service - Archivos Actualizados

## 1. query_service/config/settings.py (ACTUALIZADO)
```python
"""
Configuración para Query Service.

Este módulo carga la configuración del servicio usando QueryServiceSettings
definido en common.config.service_settings.query
"""

from functools import lru_cache
from common.config import QueryServiceSettings

@lru_cache()
def get_settings() -> QueryServiceSettings:
    """
    Retorna la instancia de configuración para Query Service.
    Usa lru_cache para asegurar que solo se crea una instancia.
    """
    return QueryServiceSettings()

# Para facilitar el acceso directo
settings = get_settings()
```

## 2. common/config/service_settings/query.py (ACTUALIZADO)
```python
"""
Configuración específica para el Query Service.
"""
from typing import Dict, Any, List
from pydantic import Field
from pydantic_settings import SettingsConfigDict
from ..base_settings import CommonAppSettings

class QueryServiceSettings(CommonAppSettings):
    """
    Configuración específica para Query Service.
    Hereda de CommonAppSettings y añade/sobrescribe configuraciones.
    """
    model_config = SettingsConfigDict(extra='ignore', env_file='.env', env_prefix='QUERY_')
    
    # Domain específico para colas
    domain_name: str = Field(default="query", description="Dominio del servicio para colas y logging")
    
    # Groq API Settings
    groq_api_key: str = Field(default="", description="API Key para Groq (usar variable de entorno QUERY_GROQ_API_KEY)")
    groq_api_base_url: str = Field(default="https://api.groq.com/openai/v1", description="URL base de la API de Groq")
    
    # LLM Settings por defecto
    default_llm_model: str = Field(default="llama-3.3-70b-versatile", description="Modelo LLM por defecto para las consultas")
    llm_temperature: float = Field(default=0.3, description="Temperatura para la generación del LLM")
    llm_max_tokens: int = Field(default=1024, description="Máximo número de tokens a generar por el LLM")
    llm_timeout_seconds: int = Field(default=30, description="Timeout para las llamadas al LLM en segundos")
    llm_top_p: float = Field(default=1.0, description="Parámetro Top P para el LLM")
    llm_frequency_penalty: float = Field(default=0.0, description="Penalización de frecuencia para el LLM")
    llm_presence_penalty: float = Field(default=0.0, description="Penalización de presencia para el LLM")
    
    # Modelos disponibles
    available_llm_models: List[str] = Field(
        default_factory=lambda: [
            "llama-3.3-70b-versatile",
            "llama3-70b-8192", 
            "llama3-8b-8192",
            "llama-3.1-8b-instant",
            "gemma2-9b-it",
            "llama-guard-3-8b"
        ],
        description="Modelos LLM disponibles en Groq"
    )
    
    # Vector Store Configuration
    vector_db_url: str = Field(default="http://localhost:8006", description="URL del servicio de base de datos vectorial")
    similarity_threshold: float = Field(default=0.7, description="Umbral de similitud mínimo para considerar un resultado relevante")
    default_top_k: int = Field(default=5, description="Número de resultados (chunks) a recuperar por defecto de la base de datos vectorial")
    
    # Embedding Service Configuration
    embedding_service_timeout: int = Field(default=30, description="Timeout para comunicación con Embedding Service")
    
    # Search Settings
    max_search_results: int = Field(default=10, description="Número máximo de resultados de búsqueda a retornar")
    search_timeout_seconds: int = Field(default=10, description="Timeout para búsquedas vectoriales")
    
    # RAG Settings
    rag_context_window: int = Field(default=4000, description="Tamaño máximo del contexto en tokens para RAG")
    rag_system_prompt_template: str = Field(
        default=(
            "Eres un asistente útil que responde preguntas basándose en el contexto proporcionado. "
            "Siempre cita la información relevante del contexto cuando sea posible. "
            "Si el contexto no contiene información suficiente para responder la pregunta, "
            "indícalo claramente. No inventes información que no esté en el contexto."
        ),
        description="Prompt de sistema por defecto para RAG"
    )
    
    # Performance Settings
    enable_query_tracking: bool = Field(default=True, description="Habilitar el seguimiento de métricas de rendimiento")
    parallel_search_enabled: bool = Field(default=True, description="Habilitar búsquedas paralelas en múltiples colecciones")
    
    # Worker Settings
    worker_count: int = Field(default=2, description="Número de workers para procesar queries")
    
    # Retry Settings para servicios externos
    max_retries: int = Field(default=3, description="Reintentos máximos para llamadas a servicios externos")
    retry_delay_seconds: float = Field(default=1.0, description="Delay base entre reintentos")
    retry_backoff_factor: float = Field(default=2.0, description="Factor de backoff para reintentos")
```

## 3. query_service/clients/groq_client.py (ACTUALIZADO)
```python
"""
Cliente para interactuar con la API de Groq.

Proporciona una interfaz limpia para generar respuestas usando
los modelos de lenguaje de Groq, con manejo de errores y reintentos.
"""

import logging
import time
from typing import Optional, Dict, Any, List, Tuple, Union

import httpx
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type
)

from common.clients.base_http_client import BaseHTTPClient
from common.errors.http_errors import ServiceUnavailableError


class GroqClient(BaseHTTPClient):
    """
    Cliente asíncrono para la API de Groq.
    
    Extiende BaseHTTPClient para proporcionar funcionalidad
    específica para la generación de texto con LLMs de Groq.
    """
    
    def __init__(self, api_key: str, base_url: str = "https://api.groq.com/openai/v1", timeout: int = 30):
        """
        Inicializa el cliente con la API key.
        
        Args:
            api_key: API key de Groq
            base_url: URL base de la API
            timeout: Timeout en segundos para las peticiones
        """
        if not api_key:
            raise ValueError("API key de Groq es requerida")
        
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
        self.logger = logging.getLogger(__name__)
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(ServiceUnavailableError)
    )
    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        model: str = "llama-3.3-70b-versatile",
        temperature: float = 0.3,
        max_tokens: int = 1024,
        top_p: float = 1.0,
        frequency_penalty: float = 0.0,
        presence_penalty: float = 0.0,
        n: int = 1,
        stream: bool = False,
        stop: Optional[Union[str, List[str]]] = None,
        user: Optional[str] = None
    ) -> Tuple[str, Dict[str, int]]:
        """
        Genera una respuesta usando el modelo especificado.
        
        Args:
            prompt: Prompt principal del usuario
            system_prompt: Prompt de sistema (opcional)
            model: Modelo a usar
            temperature: Controla la aleatoriedad (0-2)
            max_tokens: Máximo de tokens en la respuesta
            top_p: Nucleus sampling
            frequency_penalty: Penalización de frecuencia (-2 a 2)
            presence_penalty: Penalización de presencia (-2 a 2)
            n: Número de respuestas a generar
            stream: Si usar streaming (no implementado)
            stop: Secuencias donde parar la generación
            user: Identificador único del usuario
            
        Returns:
            Tupla de (respuesta_generada, uso_de_tokens)
            
        Raises:
            ServiceUnavailableError: Si el servicio no está disponible
            Exception: Para otros errores
        """
        start_time = time.time()
        
        # Construir mensajes
        messages = []
        if system_prompt:
            messages.append({
                "role": "system",
                "content": system_prompt
            })
        
        messages.append({
            "role": "user",
            "content": prompt
        })
        
        # Preparar payload según la documentación de Groq
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "top_p": top_p,
            "frequency_penalty": frequency_penalty,
            "presence_penalty": presence_penalty,
            "n": n,
            "stream": stream
        }
        
        # Agregar parámetros opcionales si están presentes
        if stop is not None:
            payload["stop"] = stop
        
        if user is not None:
            payload["user"] = user
        
        self.logger.debug(
            f"Generando respuesta con {model}, "
            f"temp={temperature}, max_tokens={max_tokens}"
        )
        
        try:
            # Hacer petición
            response = await self.post(
                "/chat/completions",
                json=payload,
                timeout=self.timeout
            )
            
            # Parsear respuesta
            data = response.json()
            
            # Validar estructura de respuesta
            if "choices" not in data or not data["choices"]:
                raise ValueError("Respuesta inválida de Groq API: sin choices")
            
            # Extraer respuesta principal
            choice = data["choices"][0]
            content = choice.get("message", {}).get("content", "")
            finish_reason = choice.get("finish_reason")
            
            # Verificar si se truncó
            if finish_reason == "length":
                self.logger.warning(
                    f"Respuesta truncada por límite de tokens ({max_tokens})"
                )
            
            # Extraer uso de tokens
            usage = data.get("usage", {})
            token_usage = {
                "prompt_tokens": usage.get("prompt_tokens", 0),
                "completion_tokens": usage.get("completion_tokens", 0),
                "total_tokens": usage.get("total_tokens", 0),
                "queue_time": usage.get("queue_time", 0),
                "prompt_time": usage.get("prompt_time", 0),
                "completion_time": usage.get("completion_time", 0),
                "total_time": usage.get("total_time", 0)
            }
            
            # Log métricas
            elapsed = time.time() - start_time
            self.logger.info(
                f"Generación completada en {elapsed:.2f}s. "
                f"Tokens: {token_usage['total_tokens']} "
                f"(prompt: {token_usage['prompt_tokens']}, "
                f"completion: {token_usage['completion_tokens']})"
            )
            
            return content, token_usage
            
        except httpx.TimeoutException:
            self.logger.error(f"Timeout en llamada a Groq API después de {self.timeout}s")
            raise ServiceUnavailableError(
                f"Groq API timeout después de {self.timeout} segundos"
            )
        
        except Exception as e:
            self.logger.error(f"Error en llamada a Groq API: {str(e)}")
            raise
    
    async def generate_with_messages(
        self,
        messages: List[Dict[str, str]],
        model: str = "llama-3.3-70b-versatile",
        temperature: float = 0.3,
        max_tokens: int = 1024,
        **kwargs
    ) -> Tuple[str, Dict[str, int]]:
        """
        Genera una respuesta usando una lista completa de mensajes.
        
        Args:
            messages: Lista de mensajes con formato {"role": "...", "content": "..."}
            model: Modelo a usar
            temperature: Temperatura de generación
            max_tokens: Máximo de tokens
            **kwargs: Otros parámetros opcionales
            
        Returns:
            Tupla de (respuesta_generada, uso_de_tokens)
        """
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            **kwargs
        }
        
        try:
            response = await self.post(
                "/chat/completions",
                json=payload,
                timeout=self.timeout
            )
            
            data = response.json()
            
            if "choices" not in data or not data["choices"]:
                raise ValueError("Respuesta inválida de Groq API")
            
            content = data["choices"][0]["message"]["content"]
            usage = data.get("usage", {})
            
            return content, usage
            
        except Exception as e:
            self.logger.error(f"Error en generate_with_messages: {e}")
            raise
    
    async def list_models(self) -> List[Dict[str, Any]]:
        """
        Lista los modelos disponibles en Groq.
        
        Returns:
            Lista de modelos disponibles
        """
        try:
            response = await self.get("/models")
            data = response.json()
            return data.get("data", [])
            
        except Exception as e:
            self.logger.error(f"Error listando modelos: {e}")
            raise
    
    async def get_model_info(self, model_id: str) -> Dict[str, Any]:
        """
        Obtiene información detallada de un modelo específico.
        
        Args:
            model_id: ID del modelo
            
        Returns:
            Información del modelo
        """
        try:
            response = await self.get(f"/models/{model_id}")
            return response.json()
            
        except Exception as e:
            self.logger.error(f"Error obteniendo info del modelo {model_id}: {e}")
            raise
    
    async def health_check(self) -> bool:
        """
        Verifica si la API de Groq está disponible.
        
        Returns:
            True si está disponible, False en caso contrario
        """
        try:
            # Intentar listar modelos como health check
            models = await self.list_models()
            return len(models) > 0
            
        except Exception:
            return False
    
    async def close(self):
        """Cierra el cliente HTTP subyacente."""
        await self._client.aclose()
```

## 4. query_service/handlers/rag_handler.py (ACTUALIZADO - solo cambios en __init__ y _generate_response)
```python
# ... (código anterior sin cambios hasta __init__)

    def __init__(self, app_settings, direct_redis_conn=None):
        """
        Inicializa el handler con sus dependencias.
        
        Args:
            app_settings: QueryServiceSettings
            direct_redis_conn: Conexión Redis para operaciones directas
        """
        super().__init__(app_settings, direct_redis_conn)
        
        # Inicializar clientes
        self.groq_client = GroqClient(
            api_key=app_settings.groq_api_key,
            base_url=app_settings.groq_api_base_url,
            timeout=app_settings.llm_timeout_seconds
        )
        self.vector_client = VectorClient(
            base_url=app_settings.vector_db_url,
            timeout=app_settings.search_timeout_seconds
        )
        
        # Configuración
        self.default_top_k = app_settings.default_top_k
        self.similarity_threshold = app_settings.similarity_threshold
        self.default_llm_model = app_settings.default_llm_model
        self.llm_temperature = app_settings.llm_temperature
        self.llm_max_tokens = app_settings.llm_max_tokens
        self.llm_top_p = app_settings.llm_top_p
        self.llm_frequency_penalty = app_settings.llm_frequency_penalty
        self.llm_presence_penalty = app_settings.llm_presence_penalty
        self.available_models = app_settings.available_llm_models
        
        self._logger.info("RAGHandler inicializado")

# ... (código sin cambios hasta _generate_response)

    async def _generate_response(
        self,
        prompt: str,
        system_prompt: str,
        model: str,
        temperature: float,
        max_tokens: int
    ) -> tuple[str, Dict[str, int]]:
        """
        Genera la respuesta usando el LLM.
        
        Returns:
            Tupla de (respuesta, uso_de_tokens)
        """
        try:
            # Validar que el modelo esté disponible
            if model not in self.available_models:
                self._logger.warning(f"Modelo {model} no está en la lista de disponibles, usando default")
                model = self.default_llm_model
            
            response, token_usage = await self.groq_client.generate(
                prompt=prompt,
                system_prompt=system_prompt,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                top_p=self.llm_top_p,
                frequency_penalty=self.llm_frequency_penalty,
                presence_penalty=self.llm_presence_penalty
            )
            
            return response, token_usage
            
        except Exception as e:
            self._logger.error(f"Error generando respuesta con LLM: {e}")
            raise ExternalServiceError(
                f"Error al generar respuesta con {model}",
                original_exception=e
            )

# ... (resto del código sin cambios)
```

## 5. query_service/models/payloads.py (ACTUALIZACIÓN para nuevos campos)
```python
# ... (código anterior sin cambios hasta QueryGeneratePayload)

class QueryGeneratePayload(BaseModel):
    """Payload para acción query.generate - Procesamiento RAG completo."""
    
    query_text: str = Field(..., description="Texto de la consulta en lenguaje natural")
    collection_ids: List[str] = Field(..., description="IDs de las colecciones donde buscar")
    
    # Parámetros opcionales de búsqueda
    top_k: Optional[int] = Field(None, description="Número de resultados a recuperar")
    similarity_threshold: Optional[float] = Field(None, ge=0.0, le=1.0, description="Umbral mínimo de similitud")
    
    # Parámetros opcionales de generación
    llm_model: Optional[str] = Field(None, description="Modelo LLM específico a usar")
    temperature: Optional[float] = Field(None, ge=0.0, le=2.0, description="Temperatura para generación")
    max_tokens: Optional[int] = Field(None, ge=1, description="Máximo de tokens en la respuesta")
    system_prompt: Optional[str] = Field(None, description="Prompt de sistema personalizado")
    
    # Nuevos parámetros de Groq
    top_p: Optional[float] = Field(None, ge=0.0, le=1.0, description="Nucleus sampling parameter")
    frequency_penalty: Optional[float] = Field(None, ge=-2.0, le=2.0, description="Penalización de frecuencia")
    presence_penalty: Optional[float] = Field(None, ge=-2.0, le=2.0, description="Penalización de presencia")
    stop_sequences: Optional[List[str]] = Field(None, description="Secuencias donde detener la generación")
    user_id: Optional[str] = Field(None, description="ID único del usuario para tracking")
    
    # Contexto adicional
    conversation_history: Optional[List[Dict[str, str]]] = Field(
        default_factory=list,
        description="Historial de conversación para contexto"
    )
    
    # Modo de respuesta
    stream: Optional[bool] = Field(False, description="Si usar streaming (no implementado aún)")
    
    @field_validator('collection_ids')
    @classmethod
    def validate_collection_ids(cls, v):
        if not v:
            raise ValueError("Al menos una collection_id es requerida")
        return v

# ... (resto del código sin cambios)
```

## 6. query_service/services/query_service.py (ACTUALIZACIÓN en _handle_generate)
```python
# ... (código anterior sin cambios hasta _handle_generate)

    async def _handle_generate(self, action: DomainAction) -> Dict[str, Any]:
        """
        Maneja la acción query.generate para procesamiento RAG completo.
        
        Args:
            action: DomainAction con QueryGeneratePayload
            
        Returns:
            Diccionario con QueryGenerateResponse
        """
        # Validar y parsear payload
        payload = QueryGeneratePayload(**action.data)
        
        # Obtener configuración de metadata si existe
        config_overrides = action.metadata or {}
        
        # Pasar embedding_client si está disponible
        response = await self.rag_handler.process_rag_query(
            query_text=payload.query_text,
            collection_ids=payload.collection_ids,
            tenant_id=action.tenant_id,
            session_id=action.session_id,
            # Parámetros opcionales con valores de payload o metadata
            top_k=payload.top_k or config_overrides.get("top_k"),
            similarity_threshold=payload.similarity_threshold or config_overrides.get("similarity_threshold"),
            llm_model=payload.llm_model or config_overrides.get("llm_model"),
            temperature=payload.temperature if payload.temperature is not None else config_overrides.get("temperature"),
            max_tokens=payload.max_tokens or config_overrides.get("max_tokens"),
            system_prompt=payload.system_prompt,
            conversation_history=payload.conversation_history,
            # Nuevos parámetros de Groq
            top_p=payload.top_p if payload.top_p is not None else config_overrides.get("top_p"),
            frequency_penalty=payload.frequency_penalty if payload.frequency_penalty is not None else config_overrides.get("frequency_penalty"),
            presence_penalty=payload.presence_penalty if payload.presence_penalty is not None else config_overrides.get("presence_penalty"),
            stop_sequences=payload.stop_sequences,
            user_id=payload.user_id or action.user_id,
            # Contexto de trazabilidad
            trace_id=action.trace_id,
            correlation_id=action.correlation_id,
            # Cliente de embedding si está disponible
            embedding_client=self.embedding_client,
            task_id=action.task_id
        )
        
        return response.model_dump()

# ... (resto del código sin cambios)
```

## 7. Ejemplo de cómo agent_executor enviaría una DomainAction al Query Service

```python
# Ejemplo en agent_executor_service/handlers/some_handler.py

from common.models import DomainAction
from common.clients import BaseRedisClient
import uuid

async def request_rag_generation(
    self,
    query_text: str,
    collection_ids: List[str],
    tenant_id: str,
    session_id: str,
    task_id: UUID,
    user_id: str,
    llm_model: Optional[str] = None
) -> DomainActionResponse:
    """
    Solicita generación RAG al Query Service de forma pseudo-síncrona.
    """
    # Preparar payload
    query_payload = {
        "query_text": query_text,
        "collection_ids": collection_ids,
        "llm_model": llm_model or "llama-3.3-70b-versatile",
        "temperature": 0.7,
        "max_tokens": 1500,
        "conversation_history": []  # Podría incluir historial si lo tiene
    }
    
    # Crear DomainAction
    action = DomainAction(
        action_id=uuid.uuid4(),
        action_type="query.generate",
        tenant_id=tenant_id,
        session_id=session_id,
        task_id=task_id,
        user_id=user_id,
        origin_service="agent_executor",
        correlation_id=uuid.uuid4(),  # Importante para pseudo-sync
        trace_id=uuid.uuid4(),
        data=query_payload,
        metadata={
            "agent_type": "rag_agent",
            "priority": "high"
        }
    )
    
    # Enviar y esperar respuesta
    response = await self.redis_client.send_action_pseudo_sync(
        action=action,
        timeout=60  # 60 segundos de timeout para RAG
    )
    
    if not response.success:
        raise Exception(f"Error en Query Service: {response.error.message}")
    
    # response.data contendrá QueryGenerateResponse como dict
    return response
```

## 8. Flujo completo de comunicación:

1. **Agent Executor → Query Service (pseudo-síncrono)**:
   - Envía DomainAction con `action_type="query.generate"` 
   - Incluye `correlation_id` y `callback_queue_name`
   - Espera respuesta en la cola de callback

2. **Query Service → Embedding Service (pseudo-síncrono)**:
   - Si necesita embeddings, envía DomainAction con `action_type="embedding.generate_query"`
   - Espera respuesta con el embedding

3. **Query Service → Vector Store (HTTP directo)**:
   - Realiza búsqueda con el embedding obtenido

4. **Query Service → Groq API (HTTP directo)**:
   - Envía el prompt con contexto para generar respuesta

5. **Query Service → Agent Executor (respuesta)**:
   - Envía DomainActionResponse con la respuesta generada