"""
Worker mejorado para Domain Actions en Query Service.

Implementación estandarizada con inicialización asíncrona y
manejo robusto de acciones para procesamiento RAG de consultas.

VERSIÓN: 4.0 - Adaptado al patrón BaseWorker con procesamiento directo
"""

import logging
from datetime import datetime
from typing import Dict, Any, List, Optional

from common.workers.base_worker import BaseWorker
from common.models.actions import DomainAction
from common.models.execution_context import ExecutionContext
from common.services.domain_queue_manager import DomainQueueManager
from query_service.models.actions import (
    QueryGenerateAction, SearchDocsAction, QueryCallbackAction
)
from query_service.handlers.query_handler import QueryHandler
from query_service.handlers.context_handler import get_query_context_handler
from query_service.handlers.query_callback_handler import QueryCallbackHandler
from query_service.handlers.embedding_callback_handler import EmbeddingCallbackHandler
from query_service.config.settings import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

class QueryWorker(BaseWorker):
    """
    Worker mejorado para procesar Domain Actions de consultas (RAG).
    
    Características:
    - Inicialización asíncrona segura
    - Procesamiento RAG de consultas
    - Callbacks detallados con información de calidad
    - Control por tier con límites específicos
    - Estadísticas avanzadas
    """
    
    def __init__(self, redis_client, queue_manager=None):
        """
        Inicializa worker con servicios necesarios.
        
        Args:
            redis_client: Cliente Redis configurado (requerido)
            queue_manager: Gestor de colas por dominio (opcional)
        """
        queue_manager = queue_manager or DomainQueueManager(redis_client)
        super().__init__(redis_client, queue_manager)
        
        # Definir domain específico
        self.domain = settings.domain_name  # "query"
        
        # Handlers que se inicializarán de forma asíncrona
        self.context_handler = None
        self.query_handler = None
        self.query_callback_handler = None
        self.embedding_callback_handler = None
        self.initialized = False
    
    async def initialize(self):
        """Inicializa el worker de forma asíncrona."""
        if self.initialized:
            return
            
        # Inicializar servicios y handlers necesarios
        # Context handler
        self.context_handler = await get_query_context_handler(self.redis_client)
        
        # Query callback handler
        self.query_callback_handler = QueryCallbackHandler(
            self.queue_manager, self.redis_client
        )
        
        # Embedding callback handler
        self.embedding_callback_handler = EmbeddingCallbackHandler()
        
        # Query handler principal
        self.query_handler = QueryHandler(
            self.context_handler, self.redis_client
        )
        
        self.initialized = True
        logger.info("QueryWorker inicializado correctamente")
    
    async def start(self):
        """Extiende el start para asegurar inicialización."""
        # Asegurar inicialización antes de procesar acciones
        await self.initialize()
        
        # Continuar con el comportamiento normal del BaseWorker
        await super().start()
    
    async def _handle_action(self, action: DomainAction, context: Optional[ExecutionContext] = None) -> Dict[str, Any]:
        """
        Implementa el método abstracto de BaseWorker para manejar acciones específicas
        del dominio de query.
        
        Args:
            action: La acción a procesar
            context: Contexto opcional de ejecución
            
        Returns:
            Diccionario con el resultado del procesamiento
            
        Raises:
            ValueError: Si no hay handler implementado para ese tipo de acción
        """
        action_type = action.action_type
        
        # Asegurar inicialización
        if not self.initialized:
            await self.initialize()
        
        try:
            if action_type == "query.generate":
                return await self._handle_query_generate(action, context)
            elif action_type == "query.search":
                return await self._handle_search_docs(action, context)
            elif action_type == "embedding.callback":
                return await self.embedding_callback_handler.handle_embedding_callback(action, context)
            else:
                error_msg = f"No hay handler implementado para la acción: {action_type}"
                logger.warning(error_msg)
                raise ValueError(error_msg)
                
        except Exception as e:
            logger.error(f"Error procesando acción {action_type}: {str(e)}")
            return {
                "success": False,
                "error": {
                    "type": type(e).__name__,
                    "message": str(e)
                }
            }
    
    async def _handle_query_generate(self, action: DomainAction, context: Optional[ExecutionContext] = None) -> Dict[str, Any]:
        """
        Handler específico para procesamiento de consultas.
        
        Args:
            action: Acción de consulta
            context: Contexto de ejecución opcional con metadatos
            
        Returns:
            Resultado del procesamiento
        """
        # Convertir a tipo específico
        query_action = QueryGenerateAction.parse_obj(action.dict())
        
        # Enriquecer con datos de contexto si está disponible
        if context:
            logger.info(f"Procesando consulta con tier: {context.tenant_tier}")
            query_action.tenant_tier = context.tenant_tier
        
        # Procesar consulta
        result = await self.query_handler.handle_query(query_action)
        
        return result
        
    async def _handle_search_docs(self, action: DomainAction, context: Optional[ExecutionContext] = None) -> Dict[str, Any]:
        """
        Handler específico para validación de consultas.
        
        Args:
            action: Acción de validación
            context: Contexto de ejecución opcional con metadatos
            
        Returns:
            Resultado del procesamiento
        """
        try:
            # Verificar inicialización
            if not self.initialized:
                await self.initialize()
                
            # Convertir a tipo específico
            search_action = SearchDocsAction.parse_obj(action.dict())
            
            # Enriquecer con datos de contexto si está disponible
            if context:
                logger.info(f"Procesando búsqueda con tier: {context.tenant_tier}")
                search_action.tenant_tier = context.tenant_tier
            
            # Procesar búsqueda
            result = await self.query_handler.handle_search(search_action)
            
            return result
            
        except Exception as e:
            logger.error(f"Error en handle_query_validate: {str(e)}")
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
                
            # Crear contexto de ejecución para el callback
            context = ExecutionContext(
                tenant_id=action.tenant_id,
                tenant_tier=getattr(action, 'tenant_tier', None),
                session_id=action.session_id
            )
            
            logger.info(f"Preparando callback con contexto. Tier: {context.tenant_tier}")
            
            # Determinar tipo de callback según resultado
            if result.get("success", False) and "result" in result:
                # Callback de consulta exitosa
                await self.query_callback_handler.send_query_success_callback(
                    task_id=action.task_id,
                    tenant_id=action.tenant_id,
                    session_id=action.session_id,
                    callback_queue=action.callback_queue,
                    query_result=result["result"],
                    similarity_score=result.get("metadata", {}).get("similarity_score"),
                    sources=result.get("metadata", {}).get("sources", []),
                    processing_time=result.get("execution_time", 0.0),
                    context=context
                )
            else:
                # Callback de error
                await self.query_callback_handler.send_query_error_callback(
                    task_id=action.task_id,
                    tenant_id=action.tenant_id,
                    session_id=action.session_id,
                    callback_queue=action.callback_queue,
                    error_info=result.get("error", {}),
                    context=context,
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
            
            # Crear contexto de ejecución para el callback
            context = ExecutionContext(
                tenant_id=tenant_id,
                tenant_tier=action_data.get('tenant_tier'),
                session_id=session_id
            )
            
            # Enviar error callback con contexto
            await self.query_callback_handler.send_query_error_callback(
                task_id=task_id,
                tenant_id=tenant_id,
                session_id=session_id,
                callback_queue=callback_queue,
                error_info={
                    "type": "ProcessingError",
                    "message": error_message
                },
                context=context
            )
            
        except Exception as e:
            logger.error(f"Error enviando error callback: {str(e)}")
    
    # Método auxiliar para estadísticas específicas
    async def get_query_stats(self) -> Dict[str, Any]:
        """
        Obtiene estadísticas específicas del query service.
        
        Returns:
            Dict con estadísticas completas
        """
        # Obtener estadísticas básicas del worker
        stats = await self.get_worker_stats()
        
        if not self.initialized:
            stats["worker_info"]["status"] = "not_initialized"
            return stats
        
        try:
            # Stats de consultas
            if self.query_handler and hasattr(self.query_handler, 'get_query_stats'):
                query_stats = await self.query_handler.get_query_stats()
                stats["query_stats"] = query_stats
            
            # Stats de calidad
            if self.query_handler and hasattr(self.query_handler, 'get_quality_metrics'):
                quality_metrics = await self.query_handler.get_quality_metrics()
                stats["quality_metrics"] = quality_metrics
            
            # Stats específicas de RAG
            if self.query_handler and hasattr(self.query_handler, 'get_rag_metrics'):
                rag_metrics = await self.query_handler.get_rag_metrics()
                stats["rag_metrics"] = rag_metrics
                
        except Exception as e:
            logger.error(f"Error obteniendo estadísticas: {str(e)}")
            stats["error"] = str(e)
        
        return stats
