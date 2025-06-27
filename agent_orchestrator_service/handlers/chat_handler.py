"""
Handler para procesamiento de mensajes de chat.
"""
import logging
import uuid
from typing import Dict, Any, Optional
from datetime import datetime

from common.errors.exceptions import ValidationError, ExternalServiceError
from ..models.session_models import SessionState, ChatTask, ConversationContext
from ..models.websocket_model import WebSocketMessage, WebSocketMessageType
from ..clients import ExecutionClient, ManagementClient
from ..websocket import WebSocketManager


class ChatHandler:
    """
    Handler para procesar mensajes de chat y coordinar con otros servicios.
    """
    
    def __init__(
        self,
        execution_client: ExecutionClient,
        management_client: ManagementClient,
        websocket_manager: WebSocketManager
    ):
        """
        Inicializa el handler.
        
        Args:
            execution_client: Cliente para Execution Service
            management_client: Cliente para Management Service
            websocket_manager: Manager de WebSockets
        """
        self.execution_client = execution_client
        self.management_client = management_client
        self.websocket_manager = websocket_manager
        self._logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        
        # Cache de configuraciones por agente (TTL de 5 minutos)
        self._config_cache = {}
        self._cache_ttl = 300  # 5 minutos
    
    async def process_chat_message(
        self,
        session_state: SessionState,
        message: str,
        message_type: str = "text",
        metadata: Optional[Dict[str, Any]] = None
    ) -> ChatTask:
        """
        Procesa un mensaje de chat completo.
        
        Args:
            session_state: Estado de la sesión
            message: Mensaje del usuario
            message_type: Tipo de mensaje
            metadata: Metadata adicional
            
        Returns:
            ChatTask con el resultado
        """
        # Crear nueva tarea
        task = ChatTask(
            session_id=session_state.session_id,
            message=message,
            message_type=message_type
        )
        
        # Actualizar task actual en sesión
        await self.websocket_manager.update_session_task(
            session_state.session_id,
            task.task_id
        )
        
        try:
            # 1. Notificar inicio de procesamiento
            await self._send_status_update(
                session_state.session_id,
                task.task_id,
                "processing",
                "Procesando mensaje..."
            )
            
            # 2. Obtener configuraciones del agente
            self._logger.info(
                f"Obteniendo configuraciones para agent_id={session_state.agent_id}"
            )
            
            execution_config, query_config, rag_config = await self._get_agent_configs(
                session_state.tenant_id,
                session_state.agent_id,
                session_state.session_id,
                session_state.user_id
            )
            
            # 3. Determinar modo basado en metadata o configuración
            mode = metadata.get("mode", "simple") if metadata else "simple"
            
            # 4. Generar conversation_id si no existe
            if not session_state.conversation_id:
                session_state.conversation_id = self._generate_conversation_id(
                    session_state.tenant_id,
                    session_state.session_id,
                    session_state.agent_id
                )
            
            # 5. Enviar al Execution Service
            self._logger.info(
                f"Enviando mensaje al Execution Service en modo {mode}"
            )
            
            response = await self.execution_client.send_chat_message(
                message=message,
                conversation_id=session_state.conversation_id,
                session_id=session_state.session_id,
                task_id=task.task_id,
                tenant_id=session_state.tenant_id,
                agent_id=session_state.agent_id,
                user_id=session_state.user_id,
                execution_config=execution_config,
                query_config=query_config,
                rag_config=rag_config,
                mode=mode
            )
            
            # 6. Procesar respuesta
            task.response = response.get("message", {}).get("content", "")
            task.status = "completed"
            task.completed_at = datetime.utcnow()
            task.execution_time_ms = response.get("execution_time_ms")
            task.tokens_used = response.get("usage", {})
            
            # 7. Enviar respuesta por WebSocket
            await self._send_chat_response(
                session_state.session_id,
                task.task_id,
                task.response,
                metadata={
                    "execution_time_ms": task.execution_time_ms,
                    "tokens_used": task.tokens_used,
                    "mode": mode
                }
            )
            
            self._logger.info(
                f"Mensaje procesado exitosamente para task_id={task.task_id}"
            )
            
            return task
            
        except ExternalServiceError as e:
            # Error de servicio externo
            task.status = "failed"
            task.error = str(e)
            task.completed_at = datetime.utcnow()
            
            await self._send_error(
                session_state.session_id,
                task.task_id,
                str(e),
                "service_error"
            )
            
            raise
            
        except Exception as e:
            # Error inesperado
            self._logger.error(
                f"Error procesando mensaje: {e}",
                exc_info=True
            )
            
            task.status = "failed"
            task.error = str(e)
            task.completed_at = datetime.utcnow()
            
            await self._send_error(
                session_state.session_id,
                task.task_id,
                "Error interno al procesar el mensaje",
                "internal_error"
            )
            
            raise
    
    async def _get_agent_configs(
        self,
        tenant_id: str,
        agent_id: str,
        session_id: str,
        user_id: Optional[str]
    ):
        """Obtiene configuraciones del agente con cache."""
        cache_key = f"{tenant_id}:{agent_id}"
        
        # Verificar cache
        if cache_key in self._config_cache:
            cached_data = self._config_cache[cache_key]
            if (datetime.utcnow() - cached_data["timestamp"]).seconds < self._cache_ttl:
                self._logger.debug(f"Usando configuraciones cacheadas para {cache_key}")
                return cached_data["configs"]
        
        # Obtener del Management Service
        configs = await self.management_client.get_agent_configurations(
            tenant_id=tenant_id,
            agent_id=agent_id,
            session_id=session_id,
            user_id=user_id
        )
        
        # Cachear
        self._config_cache[cache_key] = {
            "configs": configs,
            "timestamp": datetime.utcnow()
        }
        
        return configs
    
    def _generate_conversation_id(
        self,
        tenant_id: str,
        session_id: str,
        agent_id: str
    ) -> str:
        """Genera un ID determinístico para la conversación."""
        combined = f"{tenant_id}:{session_id}:{agent_id}"
        return str(uuid.uuid5(uuid.NAMESPACE_DNS, combined))
    
    async def _send_status_update(
        self,
        session_id: str,
        task_id: str,
        status: str,
        message: str
    ):
        """Envía actualización de estado por WebSocket."""
        await self.websocket_manager.send_to_session(
            session_id,
            WebSocketMessage(
                type=WebSocketMessageType.TASK_UPDATE,
                task_id=task_id,
                data={
                    "status": status,
                    "message": message,
                    "timestamp": datetime.utcnow().isoformat()
                }
            )
        )
    
    async def _send_chat_response(
        self,
        session_id: str,
        task_id: str,
        response: str,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Envía respuesta de chat por WebSocket."""
        await self.websocket_manager.send_to_session(
            session_id,
            WebSocketMessage(
                type=WebSocketMessageType.AGENT_RESPONSE,
                task_id=task_id,
                data={
                    "response": response,
                    "metadata": metadata or {},
                    "timestamp": datetime.utcnow().isoformat()
                }
            )
        )
    
    async def _send_error(
        self,
        session_id: str,
        task_id: str,
        error: str,
        error_type: str
    ):
        """Envía error por WebSocket."""
        await self.websocket_manager.send_to_session(
            session_id,
            WebSocketMessage(
                type=WebSocketMessageType.ERROR,
                task_id=task_id,
                data={
                    "error": error,
                    "error_type": error_type,
                    "timestamp": datetime.utcnow().isoformat()
                }
            )
        )