"""
Implementación del servicio principal de Query Service.
"""

import logging
from typing import Optional, Dict, Any
from uuid import uuid4

from pydantic import ValidationError

from common.services import BaseService
from common.models import DomainAction
from common.errors.exceptions import InvalidActionError, ExternalServiceError

from ..models import (
    ACTION_QUERY_SIMPLE,
    ACTION_QUERY_ADVANCE,
    ACTION_QUERY_RAG,
    QuerySimplePayload,
    QueryAdvancePayload,
    QueryRAGPayload
)
from ..handlers.simple_handler import SimpleHandler
from ..handlers.advance_handler import AdvanceHandler
from ..handlers.rag_handler import RAGHandler
from ..clients.embedding_client import EmbeddingClient


class QueryService(BaseService):
    """
    Servicio principal para procesamiento de consultas.
    
    Maneja las acciones:
    - query.simple: Chat simple con RAG automático
    - query.advance: Chat avanzado con soporte de tools
    - query.rag: Búsqueda RAG para knowledge tool
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
        
        # Crear embedding client si tenemos redis client
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
        
        self._logger.info("QueryService inicializado correctamente")
    
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
            # Re-raise as is
            raise
            
        except Exception as e:
            self._logger.exception(f"Error inesperado procesando {action.action_type}")
            raise ExternalServiceError(f"Error interno en Query Service: {str(e)}")
    
    async def _handle_simple(self, action: DomainAction) -> Dict[str, Any]:
        """Maneja query.simple."""
        payload = QuerySimplePayload.model_validate(action.data)
        
        response = await self.simple_handler.process_simple_query(
            payload=payload,
            tenant_id=action.tenant_id,
            session_id=action.session_id,
            task_id=action.task_id,
            trace_id=action.trace_id,
            correlation_id=action.correlation_id
        )
        
        return response.model_dump()
    
    async def _handle_advance(self, action: DomainAction) -> Dict[str, Any]:
        """Maneja query.advance."""
        payload = QueryAdvancePayload.model_validate(action.data)
        
        response = await self.advance_handler.process_advance_query(
            payload=payload,
            tenant_id=action.tenant_id,
            session_id=action.session_id,
            task_id=action.task_id,
            trace_id=action.trace_id,
            correlation_id=action.correlation_id
        )
        
        return response.model_dump()
    
    async def _handle_rag(self, action: DomainAction) -> Dict[str, Any]:
        """Maneja query.rag."""
        payload = QueryRAGPayload.model_validate(action.data)
        
        response = await self.rag_handler.process_rag_search(
            payload=payload,
            tenant_id=action.tenant_id,
            session_id=action.session_id,
            task_id=action.task_id,
            trace_id=action.trace_id,
            correlation_id=action.correlation_id
        )
        
        return response.model_dump()