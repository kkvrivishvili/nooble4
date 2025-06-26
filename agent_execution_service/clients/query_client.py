"""
Cliente para comunicación con Query Service usando Redis para DomainActions.
"""
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

from common.models.actions import DomainAction
from common.models.config_models import QueryConfig, RAGConfig
from common.errors.exceptions import ExternalServiceError
from common.clients.base_redis_client import BaseRedisClient
from common.config.service_settings.agent_execution import ExecutionServiceSettings

logger = logging.getLogger(__name__)

# Action types para Query Service
ACTION_QUERY_SIMPLE = "query.simple"
ACTION_QUERY_ADVANCE = "query.advance"
ACTION_QUERY_RAG = "query.rag"


class QueryClient:
    """Cliente para Query Service vía Redis DomainActions."""

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
        self.default_timeout = settings.query_timeout_seconds
        self._logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    async def query_simple(
        self,
        payload: Dict[str, Any],  # Ya es ChatRequest serializado
        query_config: QueryConfig,
        rag_config: RAGConfig,
        tenant_id: uuid.UUID,
        session_id: uuid.UUID,
        task_id: uuid.UUID,
        agent_id: uuid.UUID,
        timeout: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Realiza una consulta simple con RAG integrado.
        """
        action = DomainAction(
            action_id=uuid.uuid4(),
            action_type=ACTION_QUERY_SIMPLE,
            timestamp=datetime.now(timezone.utc),
            tenant_id=tenant_id,
            session_id=session_id,
            task_id=task_id,
            agent_id=agent_id,
            origin_service=self.redis_client.service_name,
            query_config=query_config,  # Config explícita para Query Service
            rag_config=rag_config,      # Config explícita para RAG
            data=payload  # Solo datos de chat, sin configuraciones
        )

        actual_timeout = timeout if timeout is not None else self.default_timeout
        
        try:
            response = await self.redis_client.send_action_pseudo_sync(
                action, 
                timeout=actual_timeout
            )
            
            if not response.success or response.data is None:
                error_detail = response.error
                error_message = f"Query Service error: {error_detail.message if error_detail else 'Unknown error'}"
                self._logger.error(error_message, extra={
                    "action_id": str(action.action_id),
                    "error_detail": error_detail.model_dump() if error_detail else None
                })
                raise ExternalServiceError(error_message, error_detail=error_detail)
                
            return response.data
            
        except TimeoutError as e:
            self._logger.error(f"Timeout en query.simple: {e}")
            raise ExternalServiceError(f"Timeout esperando respuesta de Query Service: {str(e)}")
        except Exception as e:
            self._logger.error(f"Error en query.simple: {e}", exc_info=True)
            raise ExternalServiceError(f"Error comunicándose con Query Service: {str(e)}")

    async def query_advance(
        self,
        payload: Dict[str, Any],  # Ya es ChatRequest serializado
        query_config: QueryConfig,
        rag_config: RAGConfig,
        tenant_id: uuid.UUID,
        session_id: uuid.UUID,
        task_id: uuid.UUID,
        agent_id: uuid.UUID,
        timeout: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Realiza una consulta avanzada para ReAct.
        """
        action = DomainAction(
            action_id=uuid.uuid4(),
            action_type=ACTION_QUERY_ADVANCE,
            timestamp=datetime.now(timezone.utc),
            tenant_id=tenant_id,
            session_id=session_id,
            task_id=task_id,
            agent_id=agent_id,
            origin_service=self.redis_client.service_name,
            query_config=query_config,  # Config explícita para Query Service
            rag_config=rag_config,      # Config explícita para RAG
            data=payload  # Solo datos de chat, sin configuraciones
        )

        actual_timeout = timeout if timeout is not None else self.default_timeout
        
        try:
            response = await self.redis_client.send_action_pseudo_sync(
                action, 
                timeout=actual_timeout
            )
            
            if not response.success or response.data is None:
                error_detail = response.error
                error_message = f"Query Service error: {error_detail.message if error_detail else 'Unknown error'}"
                self._logger.error(error_message, extra={
                    "action_id": str(action.action_id),
                    "error_detail": error_detail.model_dump() if error_detail else None
                })
                raise ExternalServiceError(error_message, error_detail=error_detail)
                
            return response.data
            
        except TimeoutError as e:
            self._logger.error(f"Timeout en query.advance: {e}")
            raise ExternalServiceError(f"Timeout esperando respuesta de Query Service: {str(e)}")
        except Exception as e:
            self._logger.error(f"Error en query.advance: {e}", exc_info=True)
            raise ExternalServiceError(f"Error comunicándose con Query Service: {str(e)}")

    async def query_rag(
        self,
        query_text: str,
        rag_config: Dict[str, Any],  # RAGConfig serializado
        tenant_id: uuid.UUID,
        session_id: uuid.UUID,
        task_id: uuid.UUID,
        agent_id: uuid.UUID,
        timeout: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Realiza búsqueda RAG cuando se invoca la tool "knowledge".
        """
        payload = {
            "query_text": query_text  # Solo datos, no configuración
        }

        action = DomainAction(
            action_id=uuid.uuid4(),
            action_type=ACTION_QUERY_RAG,
            timestamp=datetime.now(timezone.utc),
            tenant_id=tenant_id,
            session_id=session_id,
            task_id=task_id,
            agent_id=agent_id,
            origin_service=self.redis_client.service_name,
            rag_config=rag_config,  # Config en el header
            data=payload
        )

        actual_timeout = timeout if timeout is not None else self.default_timeout
        
        try:
            response = await self.redis_client.send_action_pseudo_sync(
                action, 
                timeout=actual_timeout
            )
            
            if not response.success or response.data is None:
                error_detail = response.error
                error_message = f"Query Service error: {error_detail.message if error_detail else 'Unknown error'}"
                self._logger.error(error_message, extra={
                    "action_id": str(action.action_id),
                    "error_detail": error_detail.model_dump() if error_detail else None
                })
                raise ExternalServiceError(error_message, error_detail=error_detail)
                
            return response.data
            
        except TimeoutError as e:
            self._logger.error(f"Timeout en query.rag: {e}")
            raise ExternalServiceError(f"Timeout esperando respuesta de Query Service: {str(e)}")
        except Exception as e:
            self._logger.error(f"Error en query.rag: {e}", exc_info=True)
            raise ExternalServiceError(f"Error comunicándose con Query Service: {str(e)}")