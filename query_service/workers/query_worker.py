"""
Worker para Domain Actions en Query Service.

MODIFICADO: Integración completa con sistema de colas por tier.
"""

import logging
from typing import Dict, Any, List

from common.workers.base_worker import BaseWorker
from common.models.actions import DomainAction
from common.redis_pool import get_redis_client
from common.services.action_processor import ActionProcessor
from common.services.domain_queue_manager import DomainQueueManager
from query_service.models.actions import QueryGenerateAction, SearchDocsAction, QueryCallbackAction
from query_service.handlers.query_handler import QueryHandler
from query_service.handlers.context_handler import get_query_context_handler
from query_service.handlers.query_callback_handler import QueryCallbackHandler
from query_service.handlers.embedding_callback_handler import EmbeddingCallbackHandler
from query_service.config.settings import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

class QueryWorker(BaseWorker):
    """
    Worker para procesar Domain Actions de consulta y búsqueda.
    
    MODIFICADO: 
    - Define domain específico
    - Procesa consultas por tier
    - Integra con callback handlers
    """
    
    def __init__(self, redis_client=None, action_processor=None):
        """
        Inicializa worker con servicios necesarios.
        """
        # Usar valores por defecto si no se proporcionan
        redis_client = redis_client or get_redis_client()
        action_processor = action_processor or ActionProcessor(redis_client)
        
        super().__init__(redis_client, action_processor)
        
        # NUEVO: Definir domain específico
        self.domain = settings.domain_name  # "query"
        
        # Inicializar queue manager
        self.queue_manager = DomainQueueManager(redis_client)
        
        # Inicializar handlers
        self._initialize_handlers()
    
    async def _initialize_handlers(self):
        """Inicializa todos los handlers necesarios."""
        # Context handler
        self.context_handler = await get_query_context_handler(self.redis_client)
        
        # Query callback handler
        self.query_callback_handler = QueryCallbackHandler(
            self.queue_manager, self.redis_client
        )
        
        # Query handler principal
        self.query_handler = QueryHandler(
            self.context_handler, self.redis_client
        )
        
        # Embedding callback handler
        self.embedding_callback_handler = EmbeddingCallbackHandler()
        
        # Registrar handlers en el action_processor
        self.action_processor.register_handler(
            "query.generate",
            self._handle_query_generate
        )
        
        self.action_processor.register_handler(
            "query.search",
            self._handle_search_docs
        )
        
        # Registrar handler para callbacks de embeddings
        self.action_processor.register_handler(
            "embedding.callback",
            self.embedding_callback_handler.handle_embedding_callback
        )
    
    async def _handle_query_generate(self, action: DomainAction) -> Dict[str, Any]:
        """
        Handler específico para generación de consultas RAG.
        
        Args:
            action: Acción de consulta
            
        Returns:
            Resultado del procesamiento
        """
        try:
            # Convertir a tipo específico
            query_action = QueryGenerateAction.parse_obj(action.dict())
            
            # Procesar consulta
            result = await self.query_handler.handle_query_generate(query_action)
            
            return result
            
        except Exception as e:
            logger.error(f"Error en handle_query_generate: {str(e)}")
            return {
                "success": False,
                "error": {
                    "type": type(e).__name__,
                    "message": str(e)
                }
            }
    
    async def _handle_search_docs(self, action: DomainAction) -> Dict[str, Any]:
        """
        Handler específico para búsqueda de documentos.
        
        Args:
            action: Acción de búsqueda
            
        Returns:
            Resultado del procesamiento
        """
        try:
            # Convertir a tipo específico
            search_action = SearchDocsAction.parse_obj(action.dict())
            
            # Procesar búsqueda
            result = await self.query_handler.handle_search_docs(search_action)
            
            return result
            
        except Exception as e:
            logger.error(f"Error en handle_search_docs: {str(e)}")
            return {
                "success": False,
                "error": {
                    "type": type(e).__name__,
                    "message": str(e)
                }
            }
    
    def create_action_from_data(self, action_data: Dict[str, Any]) -> DomainAction:
        """
        Crea objeto de acción apropiado según los datos.
        
        Args:
            action_data: Datos de la acción en formato JSON
            
        Returns:
            DomainAction del tipo específico
        """
        action_type = action_data.get("action_type")
        
        if action_type == "query.generate":
            return QueryGenerateAction.parse_obj(action_data)
        elif action_type == "query.search":
            return SearchDocsAction.parse_obj(action_data)
        elif action_type == "query.callback":
            return QueryCallbackAction.parse_obj(action_data)
        else:
            # Fallback a DomainAction genérica
            return DomainAction.parse_obj(action_data)
    
    async def _send_callback(self, action: DomainAction, result: Dict[str, Any]):
        """
        Envía resultado como callback.
        
        Args:
            action: Acción original que generó el resultado
            result: Resultado del procesamiento
        """
        try:
            # Validar que haya cola de callback
            if not action.callback_queue:
                logger.warning(f"No se especificó cola de callback para {action.task_id}")
                return
            
            # Determinar tipo de callback según resultado y acción
            if result.get("success", False) and "result" in result:
                if action.action_type == "query.generate":
                    # Callback de consulta RAG exitosa
                    await self.query_callback_handler.send_query_success_callback(
                        task_id=action.task_id,
                        tenant_id=action.tenant_id,
                        session_id=action.session_id,
                        callback_queue=action.callback_queue,
                        query_result=result["result"],
                        processing_time=result.get("execution_time", 0.0),
                        tokens_used=result.get("result", {}).get("metadata", {}).get("tokens_used")
                    )
                elif action.action_type == "query.search":
                    # Callback de búsqueda exitosa
                    await self.query_callback_handler.send_search_success_callback(
                        task_id=action.task_id,
                        tenant_id=action.tenant_id,
                        session_id=action.session_id,
                        callback_queue=action.callback_queue,
                        search_result=result["result"],
                        processing_time=result.get("execution_time", 0.0)
                    )
            else:
                # Callback de error
                await self.query_callback_handler.send_error_callback(
                    task_id=action.task_id,
                    tenant_id=action.tenant_id,
                    session_id=action.session_id,
                    callback_queue=action.callback_queue,
                    error_info=result.get("error", {}),
                    processing_time=result.get("execution_time")
                )
            
        except Exception as e:
            logger.error(f"Error enviando callback: {str(e)}")
    
    async def _send_error_callback(self, action_data: Dict[str, Any], error_message: str):
        """
        Envía callback de error.
        
        Args:
            action_data: Datos originales de la acción
            error_message: Mensaje de error
        """
        try:
            # Extraer información necesaria
            task_id = action_data.get("task_id") or action_data.get("action_id")
            tenant_id = action_data.get("tenant_id", "unknown")
            session_id = action_data.get("session_id", "unknown")
            callback_queue = action_data.get("callback_queue")
            
            if not callback_queue or not task_id:
                logger.warning("Información insuficiente para enviar error callback")
                return
            
            # Enviar error callback
            await self.query_callback_handler.send_error_callback(
                task_id=task_id,
                tenant_id=tenant_id,
                session_id=session_id,
                callback_queue=callback_queue,
                error_info={
                    "type": "ProcessingError",
                    "message": error_message
                }
            )
            
        except Exception as e:
            logger.error(f"Error enviando error callback: {str(e)}")
    
    # NUEVO: Métodos auxiliares específicos del query service
    async def get_query_stats(self) -> Dict[str, Any]:
        """Obtiene estadísticas específicas del query service."""
        
        # Stats de colas
        queue_stats = await self.get_queue_stats()
        
        # Stats de consultas
        query_stats = await self.query_handler.get_query_stats("all")
        
        # Stats de callbacks
        callback_stats = await self.query_callback_handler.get_callback_stats("all")
        
        # Stats de búsqueda vectorial
        search_stats = await self.query_handler.vector_search_service.get_search_stats("all")
        
        return {
            "queue_stats": queue_stats,
            "query_stats": query_stats,
            "callback_stats": callback_stats,
            "search_stats": search_stats,
            "worker_info": {
                "domain": self.domain,
                "running": self.running
            }
        }