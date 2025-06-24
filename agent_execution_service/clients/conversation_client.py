"""
Cliente para comunicación con Conversation Service usando Redis para DomainActions.
"""
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from common.models.actions import DomainAction
from common.clients.base_redis_client import BaseRedisClient
from common.config import ExecutionServiceSettings

logger = logging.getLogger(__name__)

# Action type para Conversation Service
ACTION_CONVERSATION_MESSAGE_CREATE = "conversation.message.create"


class ConversationClient:
    """Cliente para Conversation Service vía Redis DomainActions."""

    def __init__(
        self,
        redis_client: BaseRedisClient,
        settings: ExecutionServiceSettings
    ):
        """
        Inicializa el cliente.
        
        Args:
            redis_client: Cliente Redis base para comunicación
            settings: Configuración del servicio
        """
        if not redis_client:
            raise ValueError("redis_client es requerido")
        if not settings:
            raise ValueError("settings son requeridas")
            
        self.redis_client = redis_client
        self._logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    async def save_conversation(
        self,
        conversation_id: str,
        message_id: str,
        user_message: str,
        agent_message: str,
        tenant_id: str,
        session_id: str,
        task_id: uuid.UUID,
        agent_id: Optional[str] = None,  # NUEVO parámetro
        metadata: Optional[dict] = None
    ) -> None:
        """
        Guarda una conversación en el Conversation Service (fire-and-forget).
        El agent_id viene en metadata.
        
        Args:
            conversation_id: ID único de la conversación
            message_id: ID único del mensaje
            user_message: Mensaje del usuario
            agent_message: Respuesta del agente
            tenant_id: ID del tenant
            session_id: ID de la sesión
            task_id: ID de la tarea
            metadata: Metadata adicional (incluye agent_id)
        """
        payload = {
            "conversation_id": conversation_id,
            "message_id": message_id,
            "user_message": user_message,
            "agent_message": agent_message,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "metadata": metadata or {}
        }

        action = DomainAction(
            action_id=uuid.uuid4(),
            action_type=ACTION_CONVERSATION_MESSAGE_CREATE,
            timestamp=datetime.now(timezone.utc),
            tenant_id=tenant_id,
            session_id=session_id,
            task_id=task_id,
            agent_id=agent_id,
            origin_service=self.redis_client.service_name,
            data=payload
        )

        try:
            # Fire-and-forget: enviamos sin esperar respuesta
            await self.redis_client.send_action_async(action)
            
            self._logger.info(
                f"Conversación enviada a Conversation Service",
                extra={
                    "conversation_id": conversation_id,
                    "message_id": message_id,
                    "action_id": str(action.action_id)
                }
            )
            
        except Exception as e:
            # En fire-and-forget, solo logueamos el error pero no lo propagamos
            self._logger.error(
                f"Error enviando conversación a Conversation Service: {e}",
                extra={
                    "conversation_id": conversation_id,
                    "message_id": message_id,
                    "error": str(e)
                }
            )