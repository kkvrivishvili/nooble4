"""
Handler para procesar Domain Actions de Query Service.

MODIFICADO: Integración con sistema de colas por tier y nuevos servicios.
"""

import logging
import time
from typing import Dict, Any, Optional

from common.models.execution_context import ExecutionContext
from query_service.config.settings import QuerySettings
from query_service.models.actions import QueryGenerateAction, SearchDocsAction
from query_service.handlers.context_handler import QueryContextHandler
from query_service.services.rag_processor import RAGProcessor
from query_service.services.vector_search_service import VectorSearchService

logger = logging.getLogger(__name__)


class QueryHandler:
    """
    Handler para procesar acciones de query y búsqueda.
    MODIFICADO: Usar nuevos servicios y context handler.
    """

    def __init__(
        self,
        app_settings: QuerySettings,
        context_handler: QueryContextHandler,
        redis_client=None,
    ):
        """
        Inicializa handler.

        Args:
            app_settings: Configuración de la aplicación (inyectada).
            context_handler: Handler de contexto.
            redis_client: Cliente Redis (opcional).
        """
        self.app_settings = app_settings
        self.context_handler = context_handler
        self.redis_client = redis_client

        # Inicializar servicios
        self.vector_search_service = VectorSearchService(
            app_settings=self.app_settings, redis_client=self.redis_client
        )
        self.rag_processor = RAGProcessor(self.vector_search_service, self.redis_client)
    
    async def handle_query_generate(self, action: QueryGenerateAction) -> Dict[str, Any]:
        """
        Procesa una acción de generación de consulta RAG.
        
        Args:
            action: Acción de consulta
            
        Returns:
            Dict con resultado del procesamiento
        """
        start_time = time.time()
        task_id = action.task_id
        
        try:
            logger.info(f"Procesando consulta RAG para tarea {task_id}")
            
            # 1. Resolver contexto de consulta
            context = await self.context_handler.resolve_query_context(
                action.execution_context
            )
            
            # 2. Obtener configuración de la colección
            collection_config = await self.context_handler.get_collection_configuration(
                collection_id=action.collection_id,
                tenant_id=context.tenant_id
            )
            
            # 3. Validar permisos de consulta
            await self.context_handler.validate_query_permissions(
                context, collection_config, "generate"
            )
            
            # 4. Procesar consulta RAG
            rag_result = await self.rag_processor.process_rag_query(
                action, context, collection_config
            )
            
            # 5. Tracking de métricas
            await self._track_query_metrics(
                context, action, rag_result, time.time() - start_time
            )
            
            logger.info(f"Consulta RAG completada: task_id={task_id}, tiempo={time.time() - start_time:.2f}s")
            
            return {
                "success": True,
                "result": rag_result,
                "execution_time": time.time() - start_time
            }
            
        except Exception as e:
            logger.error(f"Error en consulta {task_id}: {str(e)}")
            return {
                "success": False,
                "execution_time": time.time() - start_time,
                "error": {
                    "type": type(e).__name__,
                    "message": str(e)
                }
            }
    
    async def handle_search_docs(self, action: SearchDocsAction) -> Dict[str, Any]:
        """
        Procesa una acción de búsqueda de documentos.
        
        Args:
            action: Acción de búsqueda
            
        Returns:
            Dict con resultado del procesamiento
        """
        start_time = time.time()
        task_id = action.task_id
        
        try:
            logger.info(f"Procesando búsqueda para tarea {task_id}")
            
            # 1. Resolver contexto de búsqueda
            context = await self.context_handler.resolve_query_context(
                action.execution_context
            )
            
            # 2. Obtener configuración de la colección
            collection_config = await self.context_handler.get_collection_configuration(
                collection_id=action.collection_id,
                tenant_id=context.tenant_id
            )
            
            # 3. Validar permisos de búsqueda
            await self.context_handler.validate_query_permissions(
                context, collection_config, "search"
            )
            
            # 4. Ejecutar búsqueda
            documents = await self.vector_search_service.search_documents(
                collection_id=action.collection_id,
                tenant_id=context.tenant_id,
                query_embedding=action.query_embedding,
                top_k=action.limit,
                similarity_threshold=action.similarity_threshold,
                metadata_filter=action.metadata_filter
            )
            
            # 5. Procesar resultados
            search_result = {
                "documents": documents,
                "metadata": {
                    "found_documents": len(documents),
                    "collection_id": action.collection_id,
                    "processing_time": time.time() - start_time,
                    "similarity_threshold": action.similarity_threshold
                }
            }
            
            processing_time = time.time() - start_time
            logger.info(f"Búsqueda completada: {len(documents)} docs en {processing_time:.2f}s")
            
            # 6. Tracking de métricas
            await self._track_search_metrics(
                context, action, search_result, processing_time
            )
            
            return {
                "success": True,
                "result": search_result,
                "execution_time": processing_time
            }
            
        except Exception as e:
            logger.error(f"Error en búsqueda {task_id}: {str(e)}")
            return {
                "success": False,
                "execution_time": time.time() - start_time,
                "error": {
                    "type": type(e).__name__,
                    "message": str(e)
                }
            }
    
    async def _track_query_metrics(
        self,
        context: ExecutionContext,
        action: QueryGenerateAction,
        result: Dict[str, Any],
        processing_time: float
    ):
        """Registra métricas de consulta RAG."""
        if not self.redis_client or not self.app_settings.enable_query_tracking:
            return

        try:
            from datetime import datetime

            today = datetime.now().date().isoformat()

            # Métricas por tenant
            tenant_key = f"query_metrics:{context.tenant_id}:{today}"
            await self.redis_client.hincrby(tenant_key, "total_queries", 1)
            await self.redis_client.hincrby(tenant_key, "rag_queries", 1)
            
            # Tokens utilizados
            if result.get("metadata", {}).get("tokens_used"):
                await self.redis.hincrby(tenant_key, "total_tokens", result["metadata"]["tokens_used"])
            
            # Tiempo de procesamiento por tier

            
            # TTL
            await self.redis.expire(tenant_key, 86400 * 7)  # 7 días
            
        except Exception as e:
            logger.error(f"Error tracking query metrics: {str(e)}")
    
    async def _track_search_metrics(
        self,
        context: ExecutionContext,
        action: SearchDocsAction,
        result: Dict[str, Any],
        processing_time: float
    ):
        """Registra métricas de búsqueda."""
        if not self.redis_client or not self.app_settings.enable_query_tracking:
            return

        try:
            from datetime import datetime

            today = datetime.now().date().isoformat()

            # Métricas por tenant
            tenant_key = f"query_metrics:{context.tenant_id}:{today}"
            await self.redis_client.hincrby(tenant_key, "total_searches", 1)

            # Métricas de resultados
            found_docs = result.get("metadata", {}).get("found_documents", 0)
            await self.redis_client.hincrby(
                tenant_key, "total_search_results", found_docs
            )

            # Métricas de tiempo
            await self.redis_client.rpush(
                f"search_times:{context.tenant_id}", processing_time
            )  # 7 días
            
        except Exception as e:
            logger.error(f"Error tracking search metrics: {str(e)}")
    
    async def get_query_stats(self, tenant_id: str) -> Dict[str, Any]:
        """Obtiene estadísticas de consultas para un tenant."""
        if not self.redis_client:
            return {"metrics": "disabled"}
        
        try:
            from datetime import datetime
            today = datetime.now().date().isoformat()
            metrics_key = f"query_metrics:{tenant_id}:{today}"
            
            metrics = await self.redis.hgetall(metrics_key)
            
            return {
                "date": today,
                "total_queries": int(metrics.get("total_queries", 0)),
                "rag_queries": int(metrics.get("rag_queries", 0)),
                "total_searches": int(metrics.get("total_searches", 0)),
                "total_tokens": int(metrics.get("total_tokens", 0)),
                "total_search_results": int(metrics.get("total_search_results", 0))
            }
            
        except Exception as e:
            logger.error(f"Error obteniendo query stats: {str(e)}")
            return {"error": str(e)}