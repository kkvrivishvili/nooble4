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
from ..clients.groq_client import GroqClient
from ..clients.qdrant_client import QdrantClient


class QueryService(BaseService):
    """
    Servicio principal para procesamiento de consultas.
    """
    
    def __init__(self, app_settings, service_redis_client=None, direct_redis_conn=None):
        """
        Inicializa el servicio con sus handlers y clientes.
        
        Todos los clientes se inicializan a nivel de servicio y se inyectan en los handlers,
        siguiendo el patrón de inyección de dependencias.
        """
        super().__init__(app_settings, service_redis_client, direct_redis_conn)
        
        # Inicializar clientes
        if not service_redis_client:
            raise ValueError("service_redis_client es requerido para comunicación con Embedding Service")
            
        # 1. Cliente de embeddings para comunicación con el Embedding Service
        self.embedding_client = EmbeddingClient(service_redis_client)
        
        # 2. Cliente de vectores para búsqueda en Qdrant
        self.qdrant_client = QdrantClient(
            url=str(app_settings.qdrant_url) if hasattr(app_settings, 'qdrant_url') and app_settings.qdrant_url else "http://localhost:6333",
            api_key=app_settings.qdrant_api_key
        )
        
        # 3. Cliente de Groq para consultas LLM
        self.groq_client = GroqClient(
            api_key=app_settings.groq_api_key,
            timeout=60,      # Valor por defecto razonable
            max_retries=2    # Valor por defecto razonable
        )
        
        # Inicializar handlers inyectando los clientes como dependencias
        self.simple_handler = SimpleHandler(
            app_settings=app_settings,
            embedding_client=self.embedding_client,
            qdrant_client=self.qdrant_client,
            groq_client=self.groq_client,
            direct_redis_conn=direct_redis_conn
        )
        
        self.advance_handler = AdvanceHandler(
            app_settings=app_settings,
            groq_client=self.groq_client,
            direct_redis_conn=direct_redis_conn
        )
        
        self.rag_handler = RAGHandler(
            app_settings=app_settings,
            embedding_client=self.embedding_client,
            qdrant_client=self.qdrant_client,
            direct_redis_conn=direct_redis_conn
        )
        
        self._logger.info("QueryService inicializado correctamente con inyección de clientes")
    
    async def process_action(self, action: DomainAction) -> Optional[Dict[str, Any]]:
        """
        Procesa una DomainAction según su tipo.
        """
        self._logger.info(
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
                self._logger.warning(f"Tipo de acción no soportado: {action.action_type}")
                raise InvalidActionError(
                    f"Acción '{action.action_type}' no es soportada por Query Service"
                )
                
        except ValidationError as e:
            self._logger.error(f"Error de validación en {action.action_type}: {e}")
            raise AppValidationError(f"Payload inválido: {str(e)}")
            
        except ExternalServiceError:
            raise
            
        except Exception as e:
            self._logger.exception(f"Error inesperado procesando {action.action_type}")
            raise ExternalServiceError(f"Error interno en Query Service: {str(e)}")
    
    async def _handle_simple(self, action: DomainAction) -> Dict[str, Any]:
        """Maneja query.simple."""
        # Validar que agent_id esté presente
        if not action.agent_id:
            raise AppValidationError("agent_id es requerido para query.simple")
        
        # Extraer configuraciones del DomainAction (ahora están en la raíz)
        query_config = action.query_config
        rag_config = action.rag_config
        
        # Validar que las configuraciones estén presente
        if not query_config:
            raise AppValidationError("query_config es requerido para query.simple")
        if not rag_config:
            raise AppValidationError("rag_config es requerido para query.simple")
        
        # Validar y parsear payload como ChatRequest (sin configuraciones)
        payload = ChatRequest.model_validate(action.data)
        
        # Procesar con handler pasando configuraciones explícitas
        response = await self.simple_handler.process_simple_query(
            data=action.data,
            query_config=query_config,  # Config explícita
            rag_config=rag_config,      # Config explícita
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
        # Validar que agent_id esté presente
        if not action.agent_id:
            raise AppValidationError("agent_id es requerido para query.advance")
        
        # Extraer configuraciones del DomainAction (ahora están en la raíz)
        query_config = action.query_config
        rag_config = action.rag_config
        
        # Validar que las configuraciones estén presente
        if not query_config:
            raise AppValidationError("query_config es requerido para query.advance")
        if not rag_config:
            raise AppValidationError("rag_config es requerido para query.advance")
        
        # Validar y parsear payload como ChatRequest (sin configuraciones)
        payload = ChatRequest.model_validate(action.data)
        
        # Procesar con handler pasando configuraciones explícitas
        response = await self.advance_handler.process_advance_query(
            data=action.data,
            query_config=query_config,  # Config explícita
            rag_config=rag_config,      # Config explícita
            tenant_id=action.tenant_id,
            session_id=action.session_id,
            task_id=action.task_id,
            trace_id=action.trace_id,
            correlation_id=action.correlation_id,
            agent_id=action.agent_id
        )
        
        # Retornar respuesta serializada
        return response.model_dump()
    
    async def _handle_rag(self, action: DomainAction) -> Dict[str, Any]:
        """Maneja query.rag para búsqueda RAG directa."""
        # Extraer rag_config del DomainAction (ahora está en la raíz)
        rag_config = action.rag_config
        
        # Validar que rag_config esté presente
        if not rag_config:
            raise AppValidationError("rag_config es requerido para query.rag")
        
        # Extraer query_text del payload limpio
        query_text = action.data.get("query_text")
        
        if not query_text:
            raise AppValidationError("query_text es requerido para query.rag")
        
        # Validar que agent_id esté presente
        if not action.agent_id:
            raise AppValidationError("agent_id es requerido para query.rag")
        
        # Procesar con handler usando la configuración RAG del DomainAction
        result = await self.rag_handler.process_rag_search(
            query_text=query_text,
            rag_config=rag_config,  # Config explícita desde DomainAction
            tenant_id=action.tenant_id,
            session_id=action.session_id,
            task_id=action.task_id,
            trace_id=action.trace_id,
            correlation_id=action.correlation_id,
            agent_id=action.agent_id
        )
        
        # Retornar resultado serializado
        return result.model_dump()