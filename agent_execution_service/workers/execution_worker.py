"""
Worker mejorado para Domain Actions en Agent Execution Service.

Implementación estandarizada con inicialización asíncrona y
manejo robusto de callbacks y acciones de ejecución.

VERSIÓN: 2.0 - Adaptado al patrón improved_base_worker
"""

import logging
from typing import Dict, Any, List

from common.workers.base_worker import BaseWorker
from common.models.actions import DomainAction
from common.services.action_processor import ActionProcessor
from common.services.domain_queue_manager import DomainQueueManager 
from agent_execution_service.models.actions import (
    AgentRunAction, ExecutionCallbackAction
)
from agent_execution_service.handlers.execution_handler import AgentExecutionHandler
from agent_execution_service.handlers.context_handler import get_context_handler
from agent_execution_service.handlers.execution_callback_handler import ExecutionCallbackHandler
from agent_execution_service.handlers.embedding_callback_handler import EmbeddingCallbackHandler
from agent_execution_service.handlers.query_callback_handler import QueryCallbackHandler
from agent_execution_service.config.settings import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

class ExecutionWorker(BaseWorker):
    """
    Worker mejorado para procesar Domain Actions de ejecución de agentes.
    
    Características:
    - Inicialización asíncrona segura
    - Integración con context handlers
    - Manejo de callbacks específicos
    - Estadísticas detalladas
    """
    
    def __init__(self, redis_client, action_processor=None):
        """
        Inicializa worker con servicios necesarios.
        
        Args:
            redis_client: Cliente Redis configurado (requerido)
            action_processor: Procesador de acciones (opcional)
        """
        action_processor = action_processor or ActionProcessor(redis_client)
        super().__init__(redis_client, action_processor)
        
        # Definir domain específico
        self.domain = settings.domain_name  # "execution"
        
        # Variables que se inicializarán de forma asíncrona
        self.context_handler = None
        self.execution_callback_handler = None
        self.agent_execution_handler = None
        self.embedding_callback_handler = None
        self.query_callback_handler = None
        self.initialized = False
    
    async def initialize(self):
        """Inicializa el worker de forma asíncrona."""
        if self.initialized:
            return
            
        await self._initialize_handlers()
        self.initialized = True
        logger.info("ImprovedExecutionWorker inicializado correctamente")
    
    async def start(self):
        """Extiende el start para asegurar inicialización."""
        # Asegurar inicialización antes de procesar acciones
        await self.initialize()
        
        # Continuar con el comportamiento normal del BaseWorker
        await super().start()
    
    async def _initialize_handlers(self):
        """Inicializa todos los handlers necesarios."""
        # Context handler
        self.context_handler = await get_context_handler(self.redis_client)
        
        # Execution callback handler
        self.execution_callback_handler = ExecutionCallbackHandler(
            self.queue_manager, self.redis_client
        )
        
        # Agent execution handler
        self.agent_execution_handler = AgentExecutionHandler(
            self.context_handler, self.redis_client
        )
        
        # Callback handlers para servicios externos
        self.embedding_callback_handler = EmbeddingCallbackHandler()
        self.query_callback_handler = QueryCallbackHandler()
        
        # Registrar handlers en el action_processor
        self.action_processor.register_handler(
            "execution.agent_run",
            self._handle_agent_execution
        )
        
        # Registrar handlers para callbacks de servicios externos
        self.action_processor.register_handler(
            "embedding.callback",
            self.embedding_callback_handler.handle_embedding_callback
        )
        
        self.action_processor.register_handler(
            "query.callback",
            self.query_callback_handler.handle_query_callback
        )
        
        logger.info("ExecutionWorker: Handlers inicializados")
    
    async def _handle_agent_execution(self, action: DomainAction) -> Dict[str, Any]:
        """
        Handler específico para ejecución de agentes.
        
        Args:
            action: Acción de ejecución
            
        Returns:
            Resultado del procesamiento
        """
        try:
            # Verificar inicialización
            if not self.initialized:
                await self.initialize()
            
            # Convertir a tipo específico
            agent_action = AgentRunAction.parse_obj(action.dict())
            
            # Procesar ejecución
            result = await self.agent_execution_handler.handle_agent_execution(agent_action)
            
            return result
            
        except Exception as e:
            logger.error(f"Error en handle_agent_execution: {str(e)}")
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
        
        if action_type == "execution.agent_run":
            return AgentRunAction.parse_obj(action_data)
        elif action_type == "execution.callback":
            return ExecutionCallbackAction.parse_obj(action_data)
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
            
            # Determinar tipo de callback según resultado
            if result.get("success", False) and "execution_result" in result:
                # Callback de ejecución exitosa
                await self.execution_callback_handler.send_success_callback(
                    task_id=action.task_id,
                    tenant_id=action.tenant_id,
                    tenant_tier=action.tenant_tier,
                    session_id=action.session_id,
                    callback_queue=action.callback_queue,
                    execution_result=result["execution_result"]
                )
            else:
                # Callback de error
                await self.execution_callback_handler.send_error_callback(
                    task_id=action.task_id,
                    tenant_id=action.tenant_id,
                    tenant_tier=action.tenant_tier,
                    session_id=action.session_id,
                    callback_queue=action.callback_queue,
                    error_info=result.get("error", {}),
                    execution_time=result.get("execution_time")
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
            tenant_tier = action_data.get("tenant_tier", "free")
            session_id = action_data.get("session_id", "unknown")
            callback_queue = action_data.get("callback_queue")
            
            if not callback_queue or not task_id:
                logger.warning("Información insuficiente para enviar error callback")
                return
            
            # Enviar error callback
            await self.execution_callback_handler.send_error_callback(
                task_id=task_id,
                tenant_id=tenant_id,
                tenant_tier=tenant_tier,
                session_id=session_id,
                callback_queue=callback_queue,
                error_info={
                    "type": "ProcessingError",
                    "message": error_message
                }
            )
            
        except Exception as e:
            logger.error(f"Error enviando error callback: {str(e)}")
    
    # Método auxiliar para estadísticas específicas del execution service
    async def get_execution_stats(self) -> Dict[str, Any]:
        """Obtiene estadísticas específicas del execution service."""
        # Obtener estadísticas básicas del worker
        stats = await self.get_worker_stats()
        
        if not self.initialized:
            stats["worker_info"]["status"] = "not_initialized"
            return stats
        
        try:
            # Stats de colas
            queue_stats = await self.get_queue_stats()
            
            # Stats de ejecución si están disponibles
            execution_stats = {}
            if self.agent_execution_handler and hasattr(self.agent_execution_handler, 'get_execution_stats'):
                execution_stats = await self.agent_execution_handler.get_execution_stats("all")
            
            # Stats de callbacks
            callback_stats = {}
            if self.execution_callback_handler and hasattr(self.execution_callback_handler, 'get_callback_stats'):
                callback_stats = await self.execution_callback_handler.get_callback_stats("all")
            
            # Añadir estadísticas específicas
            stats.update({
                "queue_stats": queue_stats,
                "execution_stats": execution_stats,
                "callback_stats": callback_stats
            })
            
        except Exception as e:
            logger.error(f"Error obteniendo estadísticas: {str(e)}")
            stats["error"] = str(e)
        
        return stats
