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
            
            # Parámetros de búsqueda
            top_k=payload.top_k or config_overrides.get("top_k"),
            similarity_threshold=payload.similarity_threshold or config_overrides.get("similarity_threshold"),
            
            # Parámetros de generación
            llm_model=payload.llm_model or config_overrides.get("llm_model"),
            temperature=payload.temperature or config_overrides.get("temperature"),
            max_tokens=payload.max_tokens or config_overrides.get("max_tokens"),
            system_prompt=payload.system_prompt,
            top_p=payload.top_p,
            frequency_penalty=payload.frequency_penalty,
            presence_penalty=payload.presence_penalty,
            stop_sequences=payload.stop_sequences,
            user_id=payload.user_id,

            # Contexto
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