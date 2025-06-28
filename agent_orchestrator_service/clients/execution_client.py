"""
Cliente para comunicación con Agent Execution Service.
"""
import logging
import uuid
from typing import Dict, Any, Optional
from datetime import datetime

from common.models.actions import DomainAction
from common.models.config_models import ExecutionConfig, QueryConfig, RAGConfig
from common.errors.exceptions import ExternalServiceError
from common.clients.base_redis_client import BaseRedisClient
from common.config.service_settings import OrchestratorSettings


class ExecutionClient:
    """Cliente para Agent Execution Service vía Redis DomainActions."""
    
    def __init__(
        self,
        redis_client: BaseRedisClient,
        settings: OrchestratorSettings
    ):
        if not redis_client:
            raise ValueError("redis_client es requerido")
        if not settings:
            raise ValueError("settings son requeridas")
            
        self.redis_client = redis_client
        self.default_timeout = 30  # Timeout por defecto para chat
        self._logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
    
    async def send_chat_message(
        self,
        message: str,
        conversation_id: str,
        session_id: str,
        task_id: str,
        tenant_id: str,
        agent_id: str,
        user_id: Optional[str],
        execution_config: ExecutionConfig,
        query_config: QueryConfig,
        rag_config: RAGConfig,
        mode: str = "simple",
        timeout: Optional[int] = None
    ) -> Dict[str, Any]:
        """Envía un mensaje de chat al Execution Service."""
        
        # ✅ CORRECTO: Solo datos de chat en payload
        chat_payload = {
            "messages": [
                {
                    "role": "user",
                    "content": message
                }
            ],
            "conversation_id": conversation_id,
            "metadata": {
                "source": "websocket",
                "mode": mode
            }
        }
        
        # ✅ CORRECTO: Contexto va en DomainAction header
        action = DomainAction(
            action_id=uuid.uuid4(),
            action_type=f"execution.chat.{mode}",
            timestamp=datetime.utcnow(),
            # ✅ Contexto en header:
            tenant_id=uuid.UUID(tenant_id),
            session_id=uuid.UUID(session_id),
            task_id=uuid.UUID(task_id),
            agent_id=uuid.UUID(agent_id),
            user_id=uuid.UUID(user_id) if user_id else None,
            origin_service=self.redis_client.service_name,
            # ✅ Configuraciones en header:
            execution_config=execution_config,
            query_config=query_config,
            rag_config=rag_config,
            # ✅ Solo datos de chat en payload:
            data=chat_payload
        )
        
        actual_timeout = timeout if timeout is not None else self.default_timeout
        
        try:
            response = await self.redis_client.send_action_pseudo_sync(
                action,
                timeout=actual_timeout
            )
            
            if not response.success or response.data is None:
                error_detail = response.error
                error_message = f"Execution Service error: {error_detail.message if error_detail else 'Unknown error'}"
                self._logger.error(error_message, extra={
                    "action_id": str(action.action_id),
                    "task_id": task_id,
                    "error_detail": error_detail.model_dump() if error_detail else None
                })
                raise ExternalServiceError(error_message, error_detail=error_detail)
            
            return response.data
            
        except TimeoutError as e:
            self._logger.error(f"Timeout en chat {mode}: {e}")
            raise ExternalServiceError(f"Timeout esperando respuesta del Execution Service: {str(e)}")
        except Exception as e:
            self._logger.error(f"Error en chat {mode}: {e}", exc_info=True)
            raise ExternalServiceError(f"Error comunicándose con Execution Service: {str(e)}")