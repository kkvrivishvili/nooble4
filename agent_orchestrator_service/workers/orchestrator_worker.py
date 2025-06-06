"""
Worker para Domain Actions en Agent Orchestrator Service.

Procesa Domain Actions específicas para orquestación de agentes
a través del BaseWorker.
"""

import logging
from typing import Dict, Any, List

from common.workers.base_worker import BaseWorker
from common.models.actions import DomainAction
from agent_orchestrator_service.models.actions import (
    WebSocketSendAction, WebSocketBroadcastAction,
    ChatProcessAction, ChatStatusAction, ChatCancelAction
)

logger = logging.getLogger(__name__)

class OrchestratorWorker(BaseWorker):
    """
    Worker para procesar Domain Actions en Agent Orchestrator.
    
    Gestiona acciones relacionadas con WebSockets y procesamiento de chats.
    """
    
    def __init__(self, redis_client=None, action_processor=None, websocket_handler=None, chat_handler=None):
        """
        Inicializa worker con servicios necesarios.
        
        Args:
            redis_client: Cliente Redis para acceso a colas (opcional)
            action_processor: Procesador centralizado de acciones (opcional)
            websocket_handler: Handler para acciones WebSocket (opcional)
            chat_handler: Handler para acciones Chat (opcional)
        """
        from common.redis_pool import get_redis_client
        from common.services.action_processor import ActionProcessor
        from agent_orchestrator_service.handlers.handlers import WebSocketHandler, ChatHandler
        from services.websocket_manager import get_websocket_manager
        
        # Usar valores por defecto si no se proporcionan
        redis_client = redis_client or get_redis_client()
        action_processor = action_processor or ActionProcessor(redis_client)
        
        super().__init__(redis_client, action_processor)
        
        # Inicializar handlers si no se proporcionan
        self.websocket_handler = websocket_handler or WebSocketHandler(get_websocket_manager())
        self.chat_handler = chat_handler or ChatHandler(None)  # Reemplazar con servicio de chat apropiado
        
        # Registrar handlers en el action_processor
        self._register_handlers()
    
    def _register_handlers(self):
        """Registra todos los handlers en el action_processor."""
        # Handlers WebSocket
        self.action_processor.register_handler(
            "websocket.send",
            self.websocket_handler.handle_send
        )
        self.action_processor.register_handler(
            "websocket.broadcast",
            self.websocket_handler.handle_broadcast
        )
        
        # Handlers Chat
        self.action_processor.register_handler(
            "chat.process",
            self.chat_handler.handle_process
        )
        self.action_processor.register_handler(
            "chat.status",
            self.chat_handler.handle_status
        )
        self.action_processor.register_handler(
            "chat.cancel",
            self.chat_handler.handle_cancel
        )
        
        # También registrar handler para execution.callback
        self.action_processor.register_handler(
            "execution.callback",
            self._handle_execution_callback
        )
    
    async def _handle_execution_callback(self, action: DomainAction) -> Dict[str, Any]:
        """
        Maneja callbacks del servicio de ejecución.
        
        Args:
            action: Acción con resultado de ejecución
            
        Returns:
            Resultado del procesamiento
        """
        try:
            # Extraer datos relevantes
            session_id = action.session_id
            task_id = action.task_id
            result = action.data.get("result", {})
            
            # Procesar resultado a través del chat handler
            await self.chat_handler.process_execution_result(
                session_id=session_id,
                task_id=task_id,
                result=result
            )
            
            return {
                "success": True,
                "processed": True
            }
            
        except Exception as e:
            logger.error(f"Error procesando callback de ejecución: {str(e)}")
            return {
                "success": False,
                "error": {
                    "type": type(e).__name__,
                    "message": str(e)
                }
            }
    
    def get_queue_names(self) -> List[str]:
        """
        Obtiene nombres de colas a monitorear.
        
        Returns:
            Lista de patrones de colas
        """
        return [
            # Colas del dominio orquestador
            "orchestrator.*.actions",
            
            # Cola de callbacks desde ejecución
            "orchestrator.*.callbacks"
        ]
    
    def create_action_from_data(self, action_data: Dict[str, Any]) -> DomainAction:
        """
        Crea objeto de acción apropiado según los datos.
        
        Args:
            action_data: Datos de la acción en formato JSON
            
        Returns:
            DomainAction del tipo específico
        """
        action_type = action_data.get("action_type")
        
        # Crear la acción específica según el tipo
        if action_type == "websocket.send":
            return WebSocketSendAction(**action_data)
        elif action_type == "websocket.broadcast":
            return WebSocketBroadcastAction(**action_data)
        elif action_type == "chat.process":
            return ChatProcessAction(**action_data)
        elif action_type == "chat.status":
            return ChatStatusAction(**action_data)
        elif action_type == "chat.cancel":
            return ChatCancelAction(**action_data)
        else:
            # Fallback a DomainAction genérica
            return DomainAction(**action_data)
    
    async def _send_callback(self, action: DomainAction, result: Dict[str, Any]):
        """
        No implementado - este worker no envía callbacks.
        Las respuestas se envían directamente vía WebSocket.
        """
        pass
    
    async def _send_error_callback(self, action_data: Dict[str, Any], error_message: str):
        """
        En caso de error, intenta enviar mensaje a WebSocket si posible.
        
        Args:
            action_data: Datos de la acción
            error_message: Mensaje de error
        """
        try:
            # Intentar extraer session_id
            session_id = action_data.get("session_id")
            if not session_id:
                return
                
            # Crear acción WebSocket para enviar error
            error_action = WebSocketSendAction(
                tenant_id=action_data.get("tenant_id", "default"),
                session_id=session_id,
                message_type="error",
                message_data={
                    "error": error_message,
                    "type": "system_error",
                    "task_id": action_data.get("task_id")
                }
            )
            
            # Procesar directamente
            await self.websocket_handler.handle_send(error_action)
            
        except Exception as e:
            logger.error(f"Error enviando error callback: {str(e)}")
