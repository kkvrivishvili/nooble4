"""
Servicio principal de ejecución de agentes.
"""
import logging
import uuid
from typing import Optional, Dict, Any

from common.services.base_service import BaseService
from common.models.actions import DomainAction
from common.errors.exceptions import InvalidActionError, ExternalServiceError
from common.clients import BaseRedisClient

from ..config.settings import ExecutionServiceSettings
from ..clients.query_client import QueryClient
from ..clients.conversation_client import ConversationClient
from ..models.execution_payloads import SimpleChatPayload, AdvanceChatPayload, OperationMode
from ..handlers.simple_chat_handler import SimpleChatHandler
from ..handlers.advance_chat_handler import AdvanceChatHandler
from ..tools.registry import ToolRegistry

logger = logging.getLogger(__name__)


class ExecutionService(BaseService):
    """Servicio principal para ejecución de agentes."""

    def __init__(
        self,
        app_settings: ExecutionServiceSettings,
        service_redis_client: BaseRedisClient,
        direct_redis_conn=None
    ):
        super().__init__(app_settings, service_redis_client, direct_redis_conn)
        self._logger = logging.getLogger(f"{self.service_name}.{self.__class__.__name__}")
        
        # Inicializar clientes
        self.query_client = QueryClient(
            redis_client=service_redis_client,
            settings=app_settings
        )
        
        self.conversation_client = ConversationClient(
            redis_client=service_redis_client,
            settings=app_settings
        )
        
        # Inicializar registro de herramientas
        self.tool_registry = ToolRegistry()
        
        # Inicializar handlers
        self.simple_handler = SimpleChatHandler(
            query_client=self.query_client,
            conversation_client=self.conversation_client,
            settings=app_settings
        )
        
        self.advance_handler = AdvanceChatHandler(
            query_client=self.query_client,
            conversation_client=self.conversation_client,
            tool_registry=self.tool_registry,
            settings=app_settings
        )

    async def process_action(self, action: DomainAction) -> Optional[Dict[str, Any]]:
        """
        Procesa una DomainAction de ejecución.
        
        Soporta:
        - execution.chat.simple: Chat con RAG integrado
        - execution.chat.advance: Chat con capacidades ReAct
        """
        try:
            action_type = action.action_type
            self._logger.info(
                f"Procesando acción: {action_type}",
                extra={
                    "action_id": str(action.action_id),
                    "tenant_id": action.tenant_id,
                    "session_id": action.session_id
                }
            )

            # Validar acción
            self._validate_action(action)

            if action_type == "execution.chat.simple":
                return await self._handle_simple_chat(action)
            
            elif action_type == "execution.chat.advance":
                return await self._handle_advance_chat(action)
            
            else:
                raise InvalidActionError(f"Tipo de acción no soportado: {action_type}")

        except InvalidActionError:
            raise
        except ExternalServiceError:
            raise
        except Exception as e:
            self._logger.error(f"Error procesando acción: {e}", exc_info=True)
            raise ExternalServiceError(f"Error interno: {str(e)}")

    def _validate_action(self, action: DomainAction) -> None:
        """Valida que la acción tenga los campos requeridos."""
        if not action.data:
            raise InvalidActionError("El campo data está vacío")
            
        if not action.task_id:
            raise InvalidActionError("task_id es requerido")

    async def _handle_simple_chat(self, action: DomainAction) -> Dict[str, Any]:
        """Maneja chat simple."""
        try:
            # Validar y parsear payload
            payload = SimpleChatPayload.model_validate(action.data)
            
            # Ejecutar handler
            response = await self.simple_handler.handle_simple_chat(
                payload=payload,
                tenant_id=action.tenant_id,
                session_id=action.session_id,
                task_id=action.task_id
            )
            
            return response.model_dump()
            
        except Exception as e:
            self._logger.error(f"Error en chat simple: {e}")
            raise

    async def _handle_advance_chat(self, action: DomainAction) -> Dict[str, Any]:
        """Maneja chat avanzado."""
        try:
            # Validar y parsear payload
            payload = AdvanceChatPayload.model_validate(action.data)
            
            # Ejecutar handler
            response = await self.advance_handler.handle_advance_chat(
                payload=payload,
                tenant_id=action.tenant_id,
                session_id=action.session_id,
                task_id=action.task_id
            )
            
            return response.model_dump()
            
        except Exception as e:
            self._logger.error(f"Error en chat avanzado: {e}")
            raise