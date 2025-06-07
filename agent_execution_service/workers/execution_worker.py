"""
Worker para procesamiento de Domain Actions en Agent Execution Service.

Este worker extiende el BaseWorker para procesar acciones
específicas de ejecución de agentes usando el nuevo sistema de Domain Actions.
"""

import logging
import json
from typing import Dict, Any, List
from datetime import datetime

from common.workers.base_worker import BaseWorker
from common.models.actions import DomainAction
from agent_execution_service.models.actions_model import AgentExecutionAction, ExecutionCallbackAction
from agent_execution_service.handlers.embedding_callback_handler import EmbeddingCallbackHandler
from agent_execution_service.handlers.handlers_domain_action import ExecutionHandler
from agent_execution_service.handlers.query_callback_handler import QueryCallbackHandler
from agent_execution_service.config.settings import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

class ExecutionWorker(BaseWorker):
    """
    Worker para procesar Domain Actions de ejecución de agentes.
    
    Procesa acciones del tipo execution.agent_run y envía resultados
    como callbacks estructurados.
    """
    
    def __init__(self, redis_client=None, action_processor=None):
        """
        Inicializa el worker con servicios necesarios.
        
        Args:
            redis_client: Cliente Redis para acceso a colas (opcional)
            action_processor: Procesador centralizado de acciones (opcional)
        """
        from common.redis_pool import get_redis_client
        from common.services.action_processor import ActionProcessor
        
        # Usar valores por defecto si no se proporcionan
        redis_client = redis_client or get_redis_client(settings.redis_url)
        action_processor = action_processor or ActionProcessor(redis_client)
        
        super().__init__(redis_client, action_processor)
        
        # Inicializar handlers
        self.execution_handler = ExecutionHandler(None)  # Agregar servicio de agentes apropiado
        self.embedding_callback_handler = EmbeddingCallbackHandler()
        self.query_callback_handler = QueryCallbackHandler()
        
        # Registrar handlers en el action_processor
        self.action_processor.register_handler(
            "execution.agent_run", 
            self.execution_handler.handle_agent_run
        )
        
        # Registrar handler para callbacks de embeddings
        self.action_processor.register_handler(
            "embedding.callback",
            self.embedding_callback_handler.handle_embedding_callback
        )
        
        # Registrar handler para callbacks de query
        self.action_processor.register_handler(
            "query.callback",
            self.query_callback_handler.handle_query_callback
        )
    
    def get_queue_names(self) -> List[str]:
        """
        Retorna nombres de colas a monitorear.
        
        Returns:
            Lista de patrones de colas
        """
        return ["execution.*.actions"]
    
    def create_action_from_data(self, action_data: Dict[str, Any]) -> DomainAction:
        """
        Crea objeto de acción apropiado según los datos.
        
        Args:
            action_data: Datos de la acción en formato JSON
            
        Returns:
            DomainAction del tipo específico
        """
        action_type = action_data.get("action_type")
        
        if action_type == "execution.agent_run":
            return AgentExecutionAction(**action_data)
        else:
            # Fallback a DomainAction genérica
            return DomainAction(**action_data)
    
    async def _send_callback(self, action: AgentExecutionAction, result: Dict[str, Any]):
        """
        Envía resultado como callback.
        
        Args:
            action: Acción original que generó el resultado
            result: Resultado del procesamiento
        """
        try:
            # Validar que haya cola de callback
            if not action.callback_queue:
                logger.warning(f"No se especificó cola de callback para {action.action_id}")
                return
            
            # Crear acción de callback
            callback = ExecutionCallbackAction(
                tenant_id=action.tenant_id,
                session_id=action.session_id,
                task_id=action.task_id or action.action_id,
                result=result.get("result", {}),
                status="completed" if result.get("success") else "failed",
                execution_time=result.get("execution_time")
            )
            
            # Si hubo error, incluirlo en el resultado
            if not result.get("success") and result.get("error"):
                callback.status = "failed"
                callback.result = {
                    "status": "failed",
                    "error": result.get("error")
                }
            
            # Enviar a cola de callback
            await self.action_processor.enqueue_action(callback, action.callback_queue)
            logger.info(f"Callback enviado: {action.callback_queue}")
            
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
            tenant_id = action_data.get("tenant_id", "default")
            callback_queue = action_data.get("callback_queue")
            task_id = action_data.get("task_id") or action_data.get("action_id")
            session_id = action_data.get("session_id")
            
            if not callback_queue or not task_id:
                logger.warning("Información insuficiente para enviar error callback")
                return
            
            # Crear acción de callback de error
            callback = ExecutionCallbackAction(
                tenant_id=tenant_id,
                session_id=session_id,
                task_id=task_id,
                status="failed",
                result={
                    "status": "failed",
                    "error": {
                        "type": "ExecutionError",
                        "message": error_message
                    }
                }
            )
            
            # Enviar a cola de callback
            await self.action_processor.enqueue_action(callback, callback_queue)
            
        except Exception as e:
            logger.error(f"Error enviando error callback: {str(e)}")
