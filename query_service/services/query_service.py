"""
Implementación del servicio principal de Query Service.
"""
import logging
from typing import Optional, Dict, Any
from uuid import uuid4

from pydantic import ValidationError

from common.services import BaseService
from common.models import DomainAction
from common.errors.exceptions import InvalidActionError, ExternalServiceError, AppValidationError
from common.models.chat_models import ChatRequest, ChatResponse, RAGSearchResult

from ..models import (
    ACTION_QUERY_SIMPLE,
    ACTION_QUERY_ADVANCE,
    ACTION_QUERY_RAG,
)
from ..handlers.simple_handler import SimpleHandler
from ..handlers.advance_handler import AdvanceHandler
from ..handlers.rag_handler import RAGHandler
from ..clients.embedding_client import EmbeddingClient


class QueryService(BaseService):
    """
    Servicio principal para procesamiento de consultas.
    """
    
    def __init__(self, app_settings, service_redis_client=None, direct_redis_conn=None):
        """
        Inicializa el servicio con sus handlers.
        """
        super().__init__(app_settings, service_redis_client, direct_redis_conn)
        
        # Crear embedding client
        self.embedding_client = None
        if service_redis_client:
            self.embedding_client = EmbeddingClient(service_redis_client)
        else:
            raise ValueError("service_redis_client es requerido para comunicación con Embedding Service")
        
        # Inicializar handlers
        self.simple_handler = SimpleHandler(
            app_settings=app_settings,
            embedding_client=self.embedding_client,
            direct_redis_conn=direct_redis_conn
        )
        
        self.advance_handler = AdvanceHandler(
            app_settings=app_settings,
            direct_redis_conn=direct_redis_conn
        )
        
        self.rag_handler = RAGHandler(
            app_settings=app_settings,
            embedding_client=self.embedding_client,
            direct_redis_conn=direct_redis_conn
        )
        
        self.logger.info("QueryService inicializado correctamente")
    
    async def process_action(self, action: DomainAction) -> Optional[Dict[str, Any]]:
        """
        Procesa una DomainAction según su tipo.
        """
        self.logger.info(
            f"Procesando acción: {action.action_type} ({action.action_id})",
            extra={
                "action_id": str(action.action_id),
                "action_type": action.action_type,
                "tenant_id": action.tenant_id,
                "correlation_id": str(action.correlation_id) if action.correlation_id else None,
                "task_id": str(action.task_id) if action.task_id else None
            }
        )
        
        try:
            if action.action_type == ACTION_QUERY_SIMPLE:
                return await self._handle_simple(action)
            elif action.action_type == ACTION_QUERY_ADVANCE:
                return await self._handle_advance(action)
            elif action.action_type == ACTION_QUERY_RAG:
                return await self._handle_rag(action)
            else:
                self.logger.warning(f"Tipo de acción no soportado: {action.action_type}")
                raise InvalidActionError(
                    f"Acción '{action.action_type}' no es soportada por Query Service"
                )
                
        except ValidationError as e:
            self.logger.error(f"Error de validación en {action.action_type}: {e}")
            raise AppValidationError(f"Payload inválido: {str(e)}")
            
        except ExternalServiceError:
            raise
            
        except Exception as e:
            self.logger.exception(f"Error inesperado procesando {action.action_type}")
            raise ExternalServiceError(f"Error interno en Query Service: {str(e)}")
    
    async def _handle_simple(self, action: DomainAction) -> Dict[str, Any]:
        """Maneja query.simple."""
        # Validar y parsear payload como ChatRequest
        payload = ChatRequest.model_validate(action.data)
        
        # Procesar con handler
        response = await self.simple_handler.process_simple_query(
            payload=payload,
            tenant_id=action.tenant_id,
            session_id=action.session_id,
            task_id=action.task_id,
            trace_id=action.trace_id,
            agent_id=action.agent_id,
            correlation_id=action.correlation_id
        )
        
        # Retornar respuesta serializada
        return response.model_dump()
    
    async def _handle_advance(self, action: DomainAction) -> Dict[str, Any]:
        """Maneja query.advance."""
        # Validar y parsear payload como ChatRequest
        payload = ChatRequest.model_validate(action.data)
        
        # Procesar con handler
        response = await self.advance_handler.process_advance_query(
            payload=payload,
            tenant_id=action.tenant_id,
            session_id=action.session_id,
            task_id=action.task_id,
            trace_id=action.trace_id,
            correlation_id=action.correlation_id
        )
        
        # Retornar respuesta serializada
        return response.model_dump()
    
    async def _handle_rag(self, action: DomainAction) -> Dict[str, Any]:
        """Maneja query.rag para búsqueda RAG directa."""
        # El payload para RAG es diferente: contiene query_text y rag_config
        query_text = action.data.get("query_text")
        rag_config_data = action.data.get("rag_config")
        
        if not query_text or not rag_config_data:
            raise AppValidationError("query_text y rag_config son requeridos para query.rag")
        
        # Parsear RAGConfig
        from common.models.chat_models import RAGConfig
        rag_config = RAGConfig.model_validate(rag_config_data)
        
        # Permitir override de parámetros
        top_k = action.data.get("top_k", rag_config.top_k)
        similarity_threshold = action.data.get("similarity_threshold", rag_config.similarity_threshold)
        
        # Procesar con handler
        result = await self.rag_handler.process_rag_search(
            query_text=query_text,
            rag_config=rag_config,
            tenant_id=action.tenant_id,
            session_id=action.session_id,
            task_id=action.task_id,
            trace_id=action.trace_id,
            correlation_id=action.correlation_id,
            agent_id=action.agent_id,
            top_k=top_k,
            similarity_threshold=similarity_threshold
        )
        
        # Retornar resultado serializado
        return result.model_dump()