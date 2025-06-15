"""
Worker mejorado para Domain Actions en Query Service.

Implementación estandarizada con inicialización asíncrona y
manejo robusto de acciones para procesamiento RAG de consultas.

VERSIÓN: 4.0 - Adaptado al patrón BaseWorker con procesamiento directo
"""

import logging
import json
from datetime import datetime
from typing import Dict, Any, List, Optional

from common.workers.base_worker import BaseWorker
from common.models.actions import DomainAction
from common.models.execution_context import ExecutionContext
from common.services.domain_queue_manager import DomainQueueManager
from query_service.config.settings import QuerySettings
from query_service.models.actions import (
    QueryGenerateAction,
    SearchDocsAction,
    QueryCallbackAction,
)
from query_service.handlers.query_handler import QueryHandler
from query_service.handlers.context_handler import get_query_context_handler
from query_service.handlers.query_callback_handler import QueryCallbackHandler
from query_service.handlers.embedding_callback_handler import EmbeddingCallbackHandler

logger = logging.getLogger(__name__)

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
    
    def __init__(
        self,
        redis_client,
        settings: QuerySettings,
        queue_manager: Optional[DomainQueueManager] = None,
    ):
        """
        Inicializa worker con servicios necesarios.

        Args:
            redis_client: Cliente Redis configurado (requerido).
            settings: Configuración de la aplicación (inyectada).
            queue_manager: Gestor de colas por dominio (opcional).
        """
        queue_manager = queue_manager or DomainQueueManager(redis_client)
        super().__init__(redis_client, queue_manager)

        # Inyectar settings
        self.settings = settings

        # Definir domain específico
        self.domain = self.settings.domain_name  # "query"

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
            app_settings=self.settings,
            context_handler=self.context_handler,
            redis_client=self.redis_client,
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
            if action_type == "query.generate.sync" or action_type == "query.rag.sync":
                return await self._handle_query_generate_sync(action, context)
            elif action_type == "query.search.sync":
                return await self._handle_search_docs_sync(action, context)
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
    
    def create_action_from_data(self, action_data: Dict[str, Any]) -> DomainAction:
        """
        Crea objeto de acción apropiado según los datos.
        
        Args:
            action_data: Datos de la acción en formato JSON
            
        Returns:
            DomainAction del tipo específico
        """
        action_type = action_data.get("action_type")
        
        if action_type == "query.generate.sync" or action_type == "query.rag.sync":
            return QueryGenerateAction.parse_obj(action_data)
        elif action_type == "query.search.sync":
            return SearchDocsAction.parse_obj(action_data)
        elif action_type == "query.callback":
            return QueryCallbackAction.parse_obj(action_data)
        else:
            # Fallback a DomainAction genérica
            return DomainAction.parse_obj(action_data)
    
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
    
    async def _handle_query_generate_sync(self, action: DomainAction, context: Optional[ExecutionContext] = None) -> Dict[str, Any]:
        """
        Handler específico para procesamiento de consultas RAG con patrón pseudo-síncrono.
        
        A diferencia del método asíncrono normal, este método responde directamente
        a una cola temporal específica con el correlation_id proporcionado en la acción.
        
        Args:
            action: Acción de consulta RAG con correlation_id
            context: Contexto de ejecución opcional con metadatos
            
        Returns:
            Resultado del procesamiento con la respuesta generada
        """
        try:
            # Verificar inicialización
            if not self.initialized:
                await self.initialize()
                
            # Convertir a tipo específico
            query_action = QueryGenerateAction.parse_obj(action.dict())
            
            # Extraer correlation_id de los datos
            correlation_id = query_action.data.get('correlation_id')
            if not correlation_id:
                raise ValueError("Se requiere correlation_id para acciones sync")
                
            # Generar cola de respuesta basada en correlation_id
            response_queue = f"query:responses:generate:{correlation_id}"
                
            # Enriquecer con datos de contexto si está disponible
            if context:
                logger.info(f"Procesando consulta RAG sync con tier: {context.tenant_tier}")
                query_action.tenant_tier = context.tenant_tier
            
            # Procesar consulta RAG
            result = await self.query_handler.handle_query(query_action)
            
            # Publicar resultado directamente en la cola de respuesta
            if result.get("success", False):
                await self.redis_client.rpush(
                    response_queue,
                    json.dumps({
                        "success": True,
                        "result": result.get("result", ""),
                        "sources": result.get("metadata", {}).get("sources", []),
                        "similarity_score": result.get("metadata", {}).get("similarity_score"),
                        "execution_time": result.get("execution_time", 0)
                    })
                )
                # Establecer tiempo de expiración para la cola temporal
                await self.redis_client.expire(response_queue, 300)  # 5 minutos
            else:
                await self.redis_client.rpush(
                    response_queue,
                    json.dumps({
                        "success": False,
                        "error": result.get("error", "Error desconocido")
                    })
                )
                await self.redis_client.expire(response_queue, 300)  # 5 minutos
                
            logger.info(f"Respuesta RAG sync enviada a {response_queue}")
            return result
            
        except Exception as e:
            logger.error(f"Error en handle_query_generate_sync: {str(e)}")
            # Intentar enviar error a cola de respuesta si tenemos correlation_id
            correlation_id = action.data.get('correlation_id')
            if correlation_id:
                response_queue = f"query:responses:generate:{correlation_id}"
                await self.redis_client.rpush(
                    response_queue,
                    json.dumps({
                        "success": False,
                        "error": str(e)
                    })
                )
                await self.redis_client.expire(response_queue, 300)  # 5 minutos
            
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _handle_search_docs_sync(self, action: DomainAction, context: Optional[ExecutionContext] = None) -> Dict[str, Any]:
        """
        Handler específico para búsqueda de documentos con patrón pseudo-síncrono.
        
        A diferencia del método asíncrono normal, este método responde directamente
        a una cola temporal específica con el correlation_id proporcionado en la acción.
        
        Args:
            action: Acción de búsqueda con correlation_id
            context: Contexto de ejecución opcional con metadatos
            
        Returns:
            Resultado del procesamiento con los documentos encontrados
        """
        try:
            # Verificar inicialización
            if not self.initialized:
                await self.initialize()
                
            # Convertir a tipo específico
            search_action = SearchDocsAction.parse_obj(action.dict())
            
            # Extraer correlation_id de los datos
            correlation_id = search_action.data.get('correlation_id')
            if not correlation_id:
                raise ValueError("Se requiere correlation_id para acciones sync")
                
            # Generar cola de respuesta basada en correlation_id
            response_queue = f"query:responses:search:{correlation_id}"
                
            # Enriquecer con datos de contexto si está disponible
            if context:
                logger.info(f"Procesando búsqueda sync con tier: {context.tenant_tier}")
                search_action.tenant_tier = context.tenant_tier
            
            # Procesar búsqueda
            result = await self.query_handler.handle_search(search_action)
            
            # Publicar resultado directamente en la cola de respuesta
            if result.get("success", False):
                await self.redis_client.rpush(
                    response_queue,
                    json.dumps({
                        "success": True,
                        "documents": result.get("documents", []),
                        "similarity_scores": result.get("similarity_scores", []),
                        "execution_time": result.get("execution_time", 0),
                        "metadata": result.get("metadata", {})
                    })
                )
                # Establecer tiempo de expiración para la cola temporal
                await self.redis_client.expire(response_queue, 300)  # 5 minutos
            else:
                await self.redis_client.rpush(
                    response_queue,
                    json.dumps({
                        "success": False,
                        "error": result.get("error", "Error desconocido")
                    })
                )
                await self.redis_client.expire(response_queue, 300)  # 5 minutos
                
            logger.info(f"Respuesta búsqueda sync enviada a {response_queue}")
            return result
            
        except Exception as e:
            logger.error(f"Error en handle_search_docs_sync: {str(e)}")
            # Intentar enviar error a cola de respuesta si tenemos correlation_id
            correlation_id = action.data.get('correlation_id')
            if correlation_id:
                response_queue = f"query:responses:search:{correlation_id}"
                await self.redis_client.rpush(
                    response_queue,
                    json.dumps({
                        "success": False,
                        "error": str(e)
                    })
                )
                await self.redis_client.expire(response_queue, 300)  # 5 minutos
            
            return {
                "success": False,
                "error": str(e)
            }
