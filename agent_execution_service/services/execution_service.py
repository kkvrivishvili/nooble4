"""
Servicio principal de ejecución de agentes.
"""
import logging
import uuid
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
from ..handlers.executor_simple_handler import SimpleChatHandler
from ..handlers.executor_advance_handler import AdvanceChatHandler
from ..config.settings import ExecutionServiceSettings
from ..clients.query_client import QueryClient
from ..tools.tool_registry import ToolRegistry

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

        if not isinstance(self.direct_redis_conn, AIORedis):
            self._logger.error("Conexión Redis asíncrona directa (direct_redis_conn) no es una instancia válida de AIORedis o no fue proporcionada a ExecutionService.")
            raise ValueError("ExecutionService requiere una instancia válida de AIORedis en direct_redis_conn para QueryClient.")

        # Inicializar QueryClient con la nueva firma
        self.query_client = QueryClient(
            aes_service_name=self.settings.service_name,
            redis_conn=self.direct_redis_conn, 
            settings=self.settings
        )

        # Inicializar ToolRegistry y registrar herramientas
        self.tool_registry = ToolRegistry()
        self._register_default_tools()
        
        # Inicializar handlers con dependencias actualizadas
        self.simple_chat_handler = SimpleChatHandler(self.query_client, self.settings)
        self.react_handler = ReactHandler(self.query_client, self.tool_registry, self.settings)
        
        self._logger.info("ExecutionService handlers inicializados con QueryClient y ToolRegistry.")

    async def initialize(self):
        """Inicializa el servicio y sus handlers."""
        try:
            # La configuración de API keys ahora se maneja a través del QueryService
            # y los handlers utilizan QueryClient. _setup_handlers ya no es necesario aquí.
            
            self._logger.info(f"ExecutionService inicializado correctamente")
            
        except Exception as e:
            self._logger.error(f"Error inicializando ExecutionService: {e}")
            raise

    def _register_default_tools(self) -> None:
        """Registra las herramientas por defecto en el ToolRegistry."""
        # Ejemplo de cómo se podrían registrar herramientas:
        # from ..tools.example_tools import ExampleSearchTool # Suponiendo que existe
        # search_tool = ExampleSearchTool()
        # self.tool_registry.register_tool(search_tool)
        # self._logger.info(f"Herramienta '{search_tool.name}' registrada.")
        # Por ahora, lo dejamos vacío hasta que definamos herramientas concretas.
        self._logger.info("No hay herramientas por defecto para registrar en esta etapa.")
        pass

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

            task_id = action.task_id
            if task_id is None:
                self._logger.error(f"task_id es None para la acción {action.action_id} de tipo {action_type}. Es requerido.")
                raise InvalidActionError(f"task_id es None para la acción {action.action_id} de tipo {action_type}. Es requerido.")

            if action_type == "execution.chat.simple":
                return await self._handle_simple_chat(action, task_id)
            
            elif action_type == "execution.react.execute":
                return await self._handle_react_execution(action, task_id)
            
            elif action_type == "execution.agent.execute":
                return await self._handle_agent_execution(action, task_id)
            
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

    async def _handle_simple_chat(self, action: DomainAction, task_id: uuid.UUID) -> Dict[str, Any]:
        """Maneja chat simple con RAG."""
        try:
            # Validar y parsear payload
            payload = ExecuteSimpleChatPayload.model_validate(action.data)
            
            # Ejecutar chat simple
            result = await self.simple_chat_handler.execute_simple_chat(
                payload=payload,
                tenant_id=action.tenant_id,
                session_id=action.session_id,
                task_id=task_id
            )
            
            return result.model_dump()
            
        except Exception as e:
            self._logger.error(f"Error en chat simple: {e}")
            raise

    async def _handle_react_execution(self, action: DomainAction, task_id: uuid.UUID) -> Dict[str, Any]:
        """Maneja ejecución ReAct."""
        try:
            # Validar y parsear payload
            payload = ExecuteReactPayload.model_validate(action.data)
            
            # Ejecutar ReAct
            result = await self.react_handler.execute_react(
                payload=payload,
                tenant_id=action.tenant_id,
                session_id=action.session_id,
                task_id=task_id
            )
            
            return result.model_dump()
            
        except Exception as e:
            self._logger.error(f"Error en ReAct: {e}")
            raise

    async def _handle_agent_execution(self, action: DomainAction, task_id: uuid.UUID) -> Dict[str, Any]:
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
                    session_id=action.session_id,
                    task_id=task_id
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
                    session_id=action.session_id,
                    task_id=task_id
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