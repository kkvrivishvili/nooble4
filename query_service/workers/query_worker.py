"""
Worker para procesar acciones de consulta.

# TODO: Oportunidades de mejora futura:
# 1. Refactorizar método process_action para usar validate_and_process desde una clase BaseHandler
# 2. Unificar métodos _send_callback y _send_error_callback en un solo método más flexible
# 3. Implementar mecanismo de retry para acciones fallidas con backoff exponencial
# 4. Separar responsabilidades de procesamiento y envío de callbacks usando patrones asinc
"""

import logging
import asyncio
from typing import List, Dict, Any, Union, cast

import redis.asyncio as aioredis

from common.workers.base_worker import BaseWorker
from common.models.actions import DomainAction
from common.services.action_processor import ActionProcessor
from common.redis_pool import get_redis_client

from query_service.models.actions import QueryGenerateAction, SearchDocsAction, QueryCallbackAction

from query_service.handlers.query_handler import QueryHandler
from query_service.handlers.embedding_callback_handler import EmbeddingCallbackHandler
from query_service.config.settings import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

class QueryWorker(BaseWorker):
    """
    Worker que procesa acciones de consulta de forma asíncrona.
    """
    
    def __init__(
        self,
        redis_client: aioredis.Redis = None,
        action_processor: ActionProcessor = None
    ):
        """
        Inicializa el worker.
        
        Args:
            redis_client: Cliente Redis (opcional)
            action_processor: Procesador de acciones (opcional)
        """
        # Inicializar Redis y action processor
        redis_client = redis_client or get_redis_client(settings.redis_url)
        action_processor = action_processor or ActionProcessor(redis_client)
        
        super().__init__(redis_client, action_processor)
        
        # Inicializar handlers
        self.query_handler = QueryHandler()
        self.embedding_callback_handler = EmbeddingCallbackHandler()
        
        # Registrar handlers en el action_processor
        self.action_processor.register_handler(
            "query.generate", 
            self.query_handler.handle_query_generate
        )
        self.action_processor.register_handler(
            "query.search", 
            self.query_handler.handle_search_docs
        )
        
        # Registrar handler para callbacks de embeddings
        self.action_processor.register_handler(
            "embedding.callback",
            self.embedding_callback_handler.handle_embedding_callback
        )
    
    def get_queue_names(self) -> List[str]:
        """
        Obtiene los nombres de las colas a monitorear.
        
        Returns:
            Lista de colas
        """
        # Monitorear colas por tenant
        tenant_queue_pattern = f"{settings.query_actions_queue_prefix}.*.actions"
        
        # También podemos agregar una cola global si es necesario
        return [tenant_queue_pattern]
    
    async def process_action(self, action: DomainAction) -> None:
        """
        Procesa una acción y envía el resultado como callback.
        
        Args:
            action: Acción a procesar
        """
        start_time = asyncio.get_event_loop().time()
        action_type = action.action_type
        task_id = action.task_id
        
        try:
            logger.info(f"Procesando acción {action_type} para tarea {task_id}")
            
            # Procesar según tipo
            if action_type == "query.generate":
                # Convertir a tipo específico para mejor validación
                typed_action = QueryGenerateAction.parse_obj(action.dict())
                result = await self.query_handler.handle_query_generate(typed_action)
            elif action_type == "query.search":
                typed_action = SearchDocsAction.parse_obj(action.dict())
                result = await self.query_handler.handle_search_docs(typed_action)
            else:
                logger.warning(f"Tipo de acción desconocido: {action_type}")
                return
            
            # Enviar callback con resultado
            await self._send_callback(
                task_id=task_id,
                tenant_id=action.tenant_id,
                success=result.get("success", False),
                result=result.get("result", {}),
                error=result.get("error"),
                callback_queue=action.callback_queue
            )
            
            process_time = asyncio.get_event_loop().time() - start_time
            logger.info(f"Acción {action_type} completada en {process_time:.2f}s")
            
        except Exception as e:
            logger.error(f"Error procesando acción {action_type}: {str(e)}")
            
            # Enviar error como callback
            await self._send_error_callback(
                task_id=task_id,
                tenant_id=getattr(action, "tenant_id", "unknown"),
                error_type=type(e).__name__,
                error_message=str(e),
                callback_queue=getattr(action, "callback_queue", None)
            )
    
    async def _send_callback(
        self,
        task_id: str,
        tenant_id: str,
        success: bool,
        result: Dict[str, Any],
        error: Dict[str, Any] = None,
        callback_queue: str = None
    ) -> None:
        """
        Envía resultado como callback.
        
        Args:
            task_id: ID de la tarea
            tenant_id: ID del tenant
            success: Si fue exitoso
            result: Resultado
            error: Error (si aplica)
            callback_queue: Cola para callback
        """
        if not callback_queue:
            logger.warning(f"No hay cola de callback para tarea {task_id}")
            return
            
        # Crear acción de callback usando el modelo específico
        callback_action = QueryCallbackAction(
            task_id=task_id,
            tenant_id=tenant_id,
            status="completed" if success else "error",
            result=result,
            error=error if error else None
        )
        
        # Convertir a DomainAction para enviar
        domain_action = DomainAction.parse_obj(callback_action.dict())
        
        # Enviar callback
        await self.action_processor.enqueue_action(domain_action, callback_queue)
        logger.debug(f"Callback enviado para tarea {task_id}")
        
    async def _send_error_callback(
        self,
        task_id: str,
        tenant_id: str,
        error_type: str,
        error_message: str,
        callback_queue: str = None
    ) -> None:
        """
        Envía error como callback.
        
        Args:
            task_id: ID de la tarea
            tenant_id: ID del tenant
            error_type: Tipo de error
            error_message: Mensaje de error
            callback_queue: Cola para callback
        """
        if not callback_queue:
            logger.warning(f"No hay cola de callback para error de tarea {task_id}")
            return
            
        # Crear acción de callback con error usando modelo específico
        callback_action = QueryCallbackAction(
            task_id=task_id,
            tenant_id=tenant_id,
            status="error",
            result={},
            error={
                "type": error_type,
                "message": error_message
            }
        )
        
        # Convertir a DomainAction para enviar
        domain_action = DomainAction.parse_obj(callback_action.dict())
        
        # Enviar callback
        await self.action_processor.enqueue_action(domain_action, callback_queue)
        logger.debug(f"Callback de error enviado para tarea {task_id}")
