"""
Servicio principal de ejecución de agentes.
"""
import logging
from typing import Optional, Dict, Any
from common.services.base_service import BaseService
from common.models.actions import DomainAction
from common.clients import BaseRedisClient
from common.errors.exceptions import InvalidActionError, ExternalServiceError
from redis.asyncio import Redis as AIORedis

from ..models.payloads import (
    ExecuteSimpleChatPayload, ExecuteReactPayload, ExecuteAgentPayload,
    ExecutionErrorResponse
)
from ..handlers.simple_chat_handler import SimpleChatHandler
from ..handlers.react_handler import ReactHandler
from ..config.settings import ExecutionServiceSettings

logger = logging.getLogger(__name__)

class ExecutionService(BaseService):
    """Servicio principal para ejecución de agentes."""

    def __init__(
        self,
        app_settings: ExecutionServiceSettings,
        service_redis_client: Optional[BaseRedisClient] = None,
        direct_redis_conn: Optional[AIORedis] = None
    ):
        super().__init__(app_settings, service_redis_client, direct_redis_conn)
        
        # Asegurar que tenemos ExecutionServiceSettings
        if not isinstance(app_settings, ExecutionServiceSettings):
            raise ValueError("app_settings debe ser una instancia de ExecutionServiceSettings")
        
        self.settings = app_settings
        
        # Inicializar handlers
        self.simple_chat_handler = SimpleChatHandler(app_settings)
        self.react_handler = ReactHandler(app_settings)
        
        # Setup de handlers
        self._setup_handlers_task = None

    async def initialize(self):
        """Inicializa el servicio y sus handlers."""
        try:
            # Configurar handlers con API keys disponibles
            await self._setup_handlers()
            
            self._logger.info(f"ExecutionService inicializado correctamente")
            
        except Exception as e:
            self._logger.error(f"Error inicializando ExecutionService: {e}")
            raise

    async def _setup_handlers(self):
        """Configura los handlers con API keys."""
        try:
            # Configurar SimpleChatHandler con LLM si hay API key
            if self.settings.groq_api_key:
                await self.simple_chat_handler.setup_llm_client(
                    provider="groq", 
                    api_key=self.settings.groq_api_key
                )
            elif self.settings.openai_api_key:
                await self.simple_chat_handler.setup_llm_client(
                    provider="openai", 
                    api_key=self.settings.openai_api_key
                )
            
            # Configurar ReactHandler
            if self.settings.groq_api_key:
                await self.react_handler.setup(
                    api_key=self.settings.groq_api_key, 
                    provider="groq"
                )
            elif self.settings.openai_api_key:
                await self.react_handler.setup(
                    api_key=self.settings.openai_api_key, 
                    provider="openai"
                )
            
            self._logger.info("Handlers configurados correctamente")
            
        except Exception as e:
            self._logger.error(f"Error configurando handlers: {e}")
            raise

    async def process_action(self, action: DomainAction) -> Optional[Dict[str, Any]]:
        """
        Procesa una DomainAction de ejecución.
        
        Soporta:
        - execution.chat.simple: Chat simple con RAG
        - execution.react.execute: Ejecución ReAct 
        - execution.agent.execute: Ejecución general de agente
        """
        try:
            action_type = action.action_type
            self._logger.info(
                f"Procesando acción: {action_type} para tenant {action.tenant_id}",
                extra={
                    "action_id": str(action.action_id),
                    "action_type": action_type,
                    "tenant_id": action.tenant_id,
                    "session_id": action.session_id
                }
            )

            # Validar que tenemos los campos requeridos
            self._validate_action(action)

            if action_type == "execution.chat.simple":
                return await self._handle_simple_chat(action)
            
            elif action_type == "execution.react.execute":
                return await self._handle_react_execution(action)
            
            elif action_type == "execution.agent.execute":
                return await self._handle_agent_execution(action)
            
            else:
                raise InvalidActionError(f"Tipo de acción no soportado: {action_type}")

        except InvalidActionError:
            # Re-lanzar errores de validación
            raise
        except ExternalServiceError:
            # Re-lanzar errores de servicios externos
            raise
        except Exception as e:
            self._logger.error(
                f"Error procesando acción {action.action_id}: {e}",
                extra={
                    "action_id": str(action.action_id),
                    "action_type": action.action_type,
                    "error": str(e)
                }
            )
            raise

    def _validate_action(self, action: DomainAction):
        """Valida que la acción tenga los campos requeridos."""
        required_fields = ['tenant_id', 'session_id', 'data']
        
        for field in required_fields:
            if not hasattr(action, field) or getattr(action, field) is None:
                raise InvalidActionError(f"Campo requerido faltante: {field}")
        
        if not action.data:
            raise InvalidActionError("El payload de datos está vacío")

    async def _handle_simple_chat(self, action: DomainAction) -> Dict[str, Any]:
        """Maneja chat simple con RAG."""
        try:
            # Validar y parsear payload
            payload = ExecuteSimpleChatPayload.model_validate(action.data)
            
            # Ejecutar chat simple
            result = await self.simple_chat_handler.execute_simple_chat(
                payload=payload,
                tenant_id=action.tenant_id,
                session_id=action.session_id
            )
            
            return result.model_dump()
            
        except Exception as e:
            self._logger.error(f"Error en chat simple: {e}")
            raise

    async def _handle_react_execution(self, action: DomainAction) -> Dict[str, Any]:
        """Maneja ejecución ReAct."""
        try:
            # Validar y parsear payload
            payload = ExecuteReactPayload.model_validate(action.data)
            
            # Ejecutar ReAct
            result = await self.react_handler.execute_react(
                payload=payload,
                tenant_id=action.tenant_id,
                session_id=action.session_id
            )
            
            return result.model_dump()
            
        except Exception as e:
            self._logger.error(f"Error en ReAct: {e}")
            raise

    async def _handle_agent_execution(self, action: DomainAction) -> Dict[str, Any]:
        """Maneja ejecución general de agente."""
        try:
            # Validar y parsear payload
            payload = ExecuteAgentPayload.model_validate(action.data)
            
            # Determinar modo de ejecución basado en el payload
            execution_mode = payload.execution_mode
            
            if execution_mode == "simple":
                # Convertir a SimpleChat payload
                simple_payload = ExecuteSimpleChatPayload(
                    user_message=payload.user_message,
                    collection_ids=payload.collection_ids,
                    conversation_history=payload.conversation_history,
                    llm_config=payload.llm_config
                )
                result = await self.simple_chat_handler.execute_simple_chat(
                    payload=simple_payload,
                    tenant_id=action.tenant_id,
                    session_id=action.session_id
                )
                
                # Envolver en ExecuteAgentResponse
                return {
                    "execution_result": {
                        "success": True,
                        "final_answer": result.response,
                        "execution_mode": "simple",
                        "execution_time_seconds": result.execution_time_seconds,
                        "tokens_used": result.tokens_used
                    }
                }
                
            else:
                # Modo avanzado (ReAct)
                react_payload = ExecuteReactPayload(
                    user_message=payload.user_message,
                    agent_id=payload.agent_id,
                    llm_config=payload.llm_config
                )
                result = await self.react_handler.execute_react(
                    payload=react_payload,
                    tenant_id=action.tenant_id,
                    session_id=action.session_id
                )
                
                return result.model_dump()
            
        except Exception as e:
            self._logger.error(f"Error en ejecución de agente: {e}")
            raise

    async def cleanup(self):
        """Limpia recursos del servicio."""
        try:
            await self.simple_chat_handler.cleanup()
            await self.react_handler.cleanup()
            
            self._logger.info("ExecutionService limpiado correctamente")
        except Exception as e:
            self._logger.error(f"Error limpiando ExecutionService: {e}")