"""
Worker mejorado para Domain Actions en Agent Orchestrator Service.

Implementación estandarizada con inicialización asíncrona y
manejo robusto de callbacks vía WebSocket.

VERSIÓN: 2.0 - Adaptado al patrón improved_base_worker
"""

import logging
import datetime
import json
import asyncio
from typing import Dict, Any, List, Optional

from common.workers.base_worker import BaseWorker
from common.models.actions import DomainAction
from common.models.execution_context import ExecutionContext
from common.services.domain_queue_manager import DomainQueueManager
from agent_orchestrator_service.models.actions_model import ExecutionCallbackAction
from agent_orchestrator_service.handlers.callback_handler import CallbackHandler
from agent_orchestrator_service.services.websocket_manager import get_websocket_manager
# Importamos los modelos sólo cuando sea necesario para evitar dependencias circulares
from agent_orchestrator_service.config.settings import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

class OrchestratorWorker(BaseWorker):
    """
    Worker mejorado para procesar Domain Actions en Agent Orchestrator.
    
    Características:
    - Inicialización asíncrona segura
    - Integración con WebSocket manager
    - Manejo de callbacks específicos
    - Estadísticas detalladas
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
        self.domain = settings.domain_name  # "orchestrator"
        
        # Variables que se inicializarán de forma asíncrona
        self.callback_handler = None
        self.websocket_manager = None
        self.initialized = False
    
    async def initialize(self):
        """Inicializa el worker de forma asíncrona."""
        if self.initialized:
            return
            
        await self._initialize_handlers()
        self.initialized = True
        logger.info("ImprovedOrchestratorWorker inicializado correctamente")
    
    async def start(self):
        """Procesa callbacks de múltiples tenants."""
        # Asegurar inicialización antes de procesar acciones
        await self.initialize()
        self.running = True
        
        while self.running:
            try:
                # Buscar todas las colas de callback activas
                callback_queues = await self.redis_client.keys("orchestrator:*:callbacks")
                
                if callback_queues:
                    # Escuchar con timeout en todas las colas
                    result = await self.redis_client.brpop(callback_queues, timeout=5)
                    
                    if result:
                        queue_name, action_data = result
                        action_dict = json.loads(action_data)
                        
                        # Procesar callback directamente
                        if action_dict.get("action_type") == "execution.callback":
                            action = self.create_action_from_data(action_dict)
                            
                            # Extraer contexto si existe
                            context = None
                            if hasattr(action, 'execution_context') and action.execution_context:
                                context = ExecutionContext(
                                    tenant_id=action.tenant_id,
                                    tenant_tier=action.tenant_tier,
                                    session_id=action.session_id
                                )
                            
                            # Procesar con el handler
                            logger.info(f"Procesando callback para task_id={action.task_id}")
                            await self.callback_handler.handle_execution_callback(action, context)
                        else:
                            logger.warning(f"Acción desconocida recibida: {action_dict.get('action_type')}")
                else:
                    # Si no hay colas activas, esperar un poco
                    await asyncio.sleep(1)
                    
            except Exception as e:
                logger.error(f"Error en orchestrator worker: {str(e)}")
                await asyncio.sleep(1)
    
    async def _initialize_handlers(self):
        """Inicializa todos los handlers necesarios."""
        # Inicializar handlers
        self.websocket_manager = get_websocket_manager()
        self.callback_handler = CallbackHandler(self.websocket_manager, self.redis_client)
        
        # El worker ya no registra handlers con queue_manager
        # Se procesarán los callbacks directamente en el método start()
        
        logger.info("OrchestratorWorker: Handlers inicializados")

    def create_action_from_data(self, action_data: Dict[str, Any]) -> DomainAction:
        """
        Crea objeto de acción apropiado según los datos.
        
        Args:
            action_data: Datos de la acción en formato JSON
            
        Returns:
            DomainAction del tipo específico
        """
        action_type = action_data.get("action_type")
        
        if action_type == "execution.callback":
            return ExecutionCallbackAction.parse_obj(action_data)
        else:
            return DomainAction.parse_obj(action_data)
    
    async def _send_callback(self, action: DomainAction, result: Dict[str, Any]):
        """
        Envía resultado como callback.
        
        Args:
            action: Acción original que generó el resultado
            result: Resultado del procesamiento
        """
        # Este servicio normalmente no envía callbacks a otros servicios
        # Los callbacks se procesan aquí y se envían via WebSocket
        logger.debug(f"Orchestrator procesó acción: {action.action_type}")
        
        # Si hay session_id y es necesario, podríamos enviar mensaje via WebSocket
        session_id = getattr(action, "session_id", None)
        tenant_id = getattr(action, "tenant_id", None)
        
        if session_id and tenant_id and self.websocket_manager:
            # Aquí podríamos implementar envío de mensajes específicos
            # según el tipo de acción procesada
            pass
    
    async def _send_error_callback(self, action_data: Dict[str, Any], error_message: str):
        """
        Envía callback de error.
        
        Args:
            action_data: Datos originales de la acción
            error_message: Mensaje de error
        """
        try:
            # Intentar extraer session_id para envío de error via WebSocket
            session_id = action_data.get("session_id")
            tenant_id = action_data.get("tenant_id")
            
            if session_id and tenant_id:
                # Siempre obtenemos el websocket_manager para asegurar que sea el actual
                # Esto mantiene compatibilidad con el comportamiento original
                websocket_manager = get_websocket_manager()
                
                # Importamos localmente para evitar dependencias circulares
                # manteniendo compatibilidad con la implementación original
                from agent_orchestrator_service.models.websocket_model import WebSocketMessage, WebSocketMessageType
                
                # Crear mensaje de error
                error_message_ws = WebSocketMessage(
                    type=WebSocketMessageType.ERROR,
                    data={
                        "error": error_message,
                        "error_type": "processing_error",
                        "task_id": action_data.get("task_id"),
                        "timestamp": datetime.datetime.utcnow().isoformat()
                    },
                    task_id=action_data.get("task_id"),
                    session_id=session_id,
                    tenant_id=tenant_id
                )
                
                # Enviar error via WebSocket
                await websocket_manager.send_to_session(session_id, error_message_ws)
                logger.info(f"Error enviado via WebSocket: session={session_id}")
        
        except Exception as e:
            logger.error(f"Error enviando error callback: {str(e)}")
    
    # Extender get_worker_stats() con estadísticas específicas
    async def get_orchestrator_stats(self) -> Dict[str, Any]:
        """
        Obtiene estadísticas específicas del orchestrator.
        
        Returns:
            Dict con estadísticas completas
        """
        # Obtener estadísticas básicas del worker
        stats = await self.get_worker_stats()
        
        if not self.initialized:
            stats["worker_info"]["status"] = "not_initialized"
            return stats
        
        try:
            # Siempre obtenemos el websocket_manager actual para mejor compatibilidad
            websocket_manager = get_websocket_manager()
            ws_stats = await websocket_manager.get_connection_stats()
            stats["websocket_stats"] = ws_stats
            
            # Stats de callbacks si están disponibles
            if self.callback_handler and hasattr(self.callback_handler, 'get_callback_stats'):
                callback_stats = await self.callback_handler.get_callback_stats("all")
                stats["callback_stats"] = callback_stats
        except Exception as e:
            logger.error(f"Error obteniendo estadísticas: {str(e)}")
            stats["error"] = str(e)
        
        return stats
