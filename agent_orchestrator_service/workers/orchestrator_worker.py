"""
Worker para Domain Actions en Agent Orchestrator Service.

MODIFICADO: Integración completa con sistema de colas por tier y callbacks.
"""

import logging
from typing import Dict, Any, List

from common.workers.base_worker import BaseWorker
from common.models.actions import DomainAction
from common.redis_pool import get_redis_client
from common.services.action_processor import ActionProcessor
from agent_orchestrator_service.models.actions_model import ExecutionCallbackAction
from agent_orchestrator_service.handlers.callback_handler import CallbackHandler
from agent_orchestrator_service.services.websocket_manager import get_websocket_manager
from agent_orchestrator_service.config.settings import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

class OrchestratorWorker(BaseWorker):
    """
    Worker para procesar Domain Actions en Agent Orchestrator.
    
    MODIFICADO: 
    - Define domain específico
    - Procesa callbacks por tier
    - Integra con WebSocket manager
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
        self.domain = settings.domain_name  # "orchestrator"
        
        # Inicializar handlers
        websocket_manager = get_websocket_manager()
        self.callback_handler = CallbackHandler(websocket_manager, redis_client)
        
        # Registrar handlers en el action_processor
        self.action_processor.register_handler(
            "execution.callback",
            self.callback_handler.handle_execution_callback
        )
        
        # TODO: Registrar otros handlers cuando sean necesarios
        # self.action_processor.register_handler("websocket.send", self._handle_websocket_send)
        # self.action_processor.register_handler("websocket.broadcast", self._handle_websocket_broadcast)
    
    # NOTA: get_queue_names() ya no se usa en BaseWorker modificado
    # BaseWorker usa self.domain para construir colas automáticamente
    
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
            # Fallback a DomainAction genérica
            return DomainAction.parse_obj(action_data)
    
    async def _send_callback(self, action: DomainAction, result: Dict[str, Any]):
        """
        Envía resultado como callback.
        
        Para Orchestrator, normalmente no enviamos callbacks hacia otros servicios,
        sino que procesamos callbacks desde otros servicios.
        """
        # Este servicio normalmente no envía callbacks a otros servicios
        # Los callbacks se procesan aquí y se envían via WebSocket
        logger.debug(f"Orchestrator procesó acción: {action.action_type}")
    
    async def _send_error_callback(self, action_data: Dict[str, Any], error_message: str):
        """
        Envía callback de error.
        
        En caso de error, intenta enviar mensaje a WebSocket si posible.
        """
        try:
            # Intentar extraer session_id para envío de error via WebSocket
            session_id = action_data.get("session_id")
            tenant_id = action_data.get("tenant_id")
            
            if session_id and tenant_id:
                websocket_manager = get_websocket_manager()
                
                # Crear mensaje de error
                from agent_orchestrator_service.models.websocket_model import WebSocketMessage, WebSocketMessageType
                
                error_message_ws = WebSocketMessage(
                    type=WebSocketMessageType.ERROR,
                    data={
                        "error": error_message,
                        "error_type": "processing_error",
                        "task_id": action_data.get("task_id"),
                        "timestamp": datetime.utcnow().isoformat()
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
    
    # NUEVO: Métodos auxiliares específicos del orchestrator
    async def get_orchestrator_stats(self) -> Dict[str, Any]:
        """Obtiene estadísticas específicas del orchestrator."""
        
        # Stats de colas
        queue_stats = await self.get_queue_stats()
        
        # Stats de WebSocket
        websocket_manager = get_websocket_manager()
        ws_stats = await websocket_manager.get_connection_stats()
        
        # Stats de callbacks
        callback_stats = await self.callback_handler.get_callback_stats("all")  # TODO: Mejorar esto
        
        return {
            "queue_stats": queue_stats,
            "websocket_stats": ws_stats,
            "callback_stats": callback_stats,
            "worker_info": {
                "domain": self.domain,
                "running": self.running
            }
        }