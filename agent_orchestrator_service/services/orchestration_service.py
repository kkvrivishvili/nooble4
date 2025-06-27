"""
Servicio principal de orquestación.

Coordina la comunicación entre WebSocket, Management Service y Execution Service.
"""
import logging
from typing import Dict, Any, Optional
from datetime import datetime

from common.services.base_service import BaseService
from common.models.actions import DomainAction
from common.errors.exceptions import InvalidActionError, ExternalServiceError
from common.clients.base_redis_client import BaseRedisClient
from common.config.service_settings import OrchestratorSettings

from ..clients import ExecutionClient, ManagementClient
from ..websocket import WebSocketManager
from ..handlers import ChatHandler
from ..models.session_models import SessionState


class OrchestrationService(BaseService):
    """
    Servicio principal de orquestación.
    
    Coordina el flujo de mensajes entre el cliente WebSocket,
    el Management Service para configuraciones, y el Execution
    Service para procesamiento.
    """
    
    def __init__(
        self,
        app_settings: OrchestratorSettings,
        service_redis_client: Optional[BaseRedisClient] = None,
        direct_redis_conn=None
    ):
        """
        Inicializa el servicio.
        
        Args:
            app_settings: Configuración del servicio
            service_redis_client: Cliente Redis para comunicación entre servicios
            direct_redis_conn: Conexión directa a Redis
        """
        super().__init__(app_settings, service_redis_client, direct_redis_conn)
        
        if not service_redis_client:
            raise ValueError("service_redis_client es requerido para OrchestrationService")
        
        # Inicializar clientes
        self.execution_client = ExecutionClient(
            redis_client=service_redis_client,
            settings=app_settings
        )
        
        self.management_client = ManagementClient(
            redis_client=service_redis_client,
            settings=app_settings
        )
        
        # WebSocket manager
        self.websocket_manager = WebSocketManager()
        
        # Chat handler
        self.chat_handler = ChatHandler(
            execution_client=self.execution_client,
            management_client=self.management_client,
            websocket_manager=self.websocket_manager
        )
        
        self._logger.info("OrchestrationService inicializado")
    
    async def process_action(self, action: DomainAction) -> Optional[Dict[str, Any]]:
        """
        Procesa una DomainAction.
        
        Este método es principalmente para compatibilidad con BaseService.
        La mayor parte del procesamiento ocurre directamente a través
        de WebSocket y el ChatHandler.
        """
        try:
            action_type = action.action_type
            self._logger.info(
                f"Procesando acción: {action_type}",
                extra={
                    "action_id": str(action.action_id),
                    "tenant_id": str(action.tenant_id),
                    "session_id": str(action.session_id)
                }
            )
            
            # Por ahora, el orchestrator principalmente maneja WebSocket
            # Las acciones llegarían solo para casos especiales
            
            if action_type == "orchestrator.session.status":
                return await self._get_session_status(action)
            else:
                raise InvalidActionError(f"Tipo de acción no soportado: {action_type}")
                
        except InvalidActionError:
            raise
        except Exception as e:
            self._logger.error(f"Error procesando acción: {e}", exc_info=True)
            raise ExternalServiceError(f"Error interno: {str(e)}")
    
    async def process_websocket_message(
        self,
        session_id: str,
        message_data: Dict[str, Any]
    ) -> None:
        """
        Procesa un mensaje recibido por WebSocket.
        
        Args:
            session_id: ID de la sesión
            message_data: Datos del mensaje
        """
        # Obtener estado de sesión
        session_state = await self.websocket_manager.get_session_state(session_id)
        if not session_state:
            self._logger.error(f"No se encontró estado para sesión {session_id}")
            return
        
        # Extraer mensaje
        message = message_data.get("message", "")
        if not message:
            await self.chat_handler._send_error(
                session_id,
                "",
                "Mensaje vacío",
                "invalid_message"
            )
            return
        
        # Procesar mensaje
        try:
            await self.chat_handler.process_chat_message(
                session_state=session_state,
                message=message,
                message_type=message_data.get("type", "text"),
                metadata=message_data.get("metadata")
            )
        except Exception as e:
            self._logger.error(
                f"Error procesando mensaje WebSocket: {e}",
                exc_info=True
            )
    
    async def _get_session_status(self, action: DomainAction) -> Dict[str, Any]:
        """Obtiene el estado de una sesión."""
        session_id = action.data.get("session_id")
        if not session_id:
            raise InvalidActionError("session_id es requerido")
        
        session_state = await self.websocket_manager.get_session_state(session_id)
        if not session_state:
            return {
                "session_id": session_id,
                "status": "not_found"
            }
        
        return {
            "session_id": session_id,
            "status": "active",
            "tenant_id": session_state.tenant_id,
            "agent_id": session_state.agent_id,
            "connection_id": session_state.connection_id,
            "created_at": session_state.created_at.isoformat(),
            "last_activity": session_state.last_activity.isoformat(),
            "message_count": session_state.messages_sent + session_state.messages_received,
            "current_task_id": session_state.current_task_id
        }
    
    def get_websocket_manager(self) -> WebSocketManager:
        """Obtiene el WebSocket manager."""
        return self.websocket_manager