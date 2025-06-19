"""
Cliente para comunicación con Query Service usando Redis para DomainActions.
"""
import logging
import uuid
import asyncio # Aunque BaseRedisClient maneja timeouts, puede ser útil para el cliente
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

import redis.asyncio as redis_async # Para el tipado de redis_conn

from common.models.actions import DomainAction, DomainActionResponse
from common.errors.exceptions import ExternalServiceError
from common.clients.base_redis_client import BaseRedisClient
from ..config.settings import ExecutionServiceSettings # Para tipar settings
from query_service.models import (
    QueryGeneratePayload, QueryGenerateResponseData,
    QueryLLMDirectPayload, QueryLLMDirectResponseData,  # Note: QueryLLMDirectResponseData
    QuerySearchPayload, QuerySearchResponseData,
    QueryServiceLLMConfig, QueryServiceChatMessage, QueryServiceToolDefinition,
    ACTION_QUERY_GENERATE, ACTION_QUERY_LLM_DIRECT, ACTION_QUERY_SEARCH
)
from typing import Union # For tool_choice

logger = logging.getLogger(__name__)

class QueryClient:
    """Cliente para Query Service vía Redis DomainActions, utilizando BaseRedisClient."""

    def __init__(
        self,
        aes_service_name: str, # Nombre del servicio actual (AgentExecutionService)
        redis_conn: redis_async.Redis,
        settings: ExecutionServiceSettings # Configuración de AES
    ):
        if not aes_service_name:
            raise ValueError("aes_service_name es requerido")
        if not redis_conn:
            raise ValueError("redis_conn es requerido")
        if not settings:
            raise ValueError("settings son requeridas")
            
        self.aes_service_name = aes_service_name
        # BaseRedisClient necesita el nombre del servicio que lo USA (AES), la conexión y los settings comunes.
        self.redis_comms = BaseRedisClient(service_name=aes_service_name, redis_client=redis_conn, settings=settings)
        self.default_timeout = settings.query_client_timeout_seconds
        # query_service_name se definirá en el action_type de la DomainAction, ej "query.llm.direct" -> target service "query"



    async def query_with_rag(
        self,
        query_text: str,
        tenant_id: str,
        session_id: str,
        task_id: uuid.UUID,
        collection_ids: List[str],
        llm_config: Optional[QueryServiceLLMConfig] = None,
        conversation_history: Optional[List[QueryServiceChatMessage]] = None,
        system_prompt_template: Optional[str] = None,
        top_k_retrieval: int = 5,
        similarity_threshold: Optional[float] = None,
        timeout: Optional[int] = None
    ) -> QueryGenerateResponseData:
        """
        Realiza una consulta RAG al Query Service usando DomainActions vía Redis.
        """
        # Use provided llm_config or default if None
        qs_llm_config = llm_config if llm_config is not None else QueryServiceLLMConfig()

        payload = QueryGeneratePayload(
            query_text=query_text,
            collection_ids=collection_ids,
            conversation_history=conversation_history if conversation_history is not None else [],
            llm_config=qs_llm_config, # Use created config object
            system_prompt_template=system_prompt_template,
            top_k_retrieval=top_k_retrieval,
            similarity_threshold=similarity_threshold
        )

        action = DomainAction(
            action_id=uuid.uuid4(),
            action_type=ACTION_QUERY_GENERATE,
            timestamp=datetime.now(timezone.utc),
            tenant_id=tenant_id,
            session_id=session_id,
            task_id=task_id,
            origin_service=self.aes_service_name,
            data=payload.model_dump(exclude_none=True),
        )
        actual_timeout = timeout if timeout is not None else self.default_timeout
        try:
            response_action = await self.redis_comms.send_action_pseudo_sync(action, timeout=actual_timeout)
            if not response_action.success or response_action.data is None:
                error_detail = response_action.error
                error_message = f"QueryService error para acción {action.action_id} ({ACTION_QUERY_GENERATE}): {error_detail.message if error_detail else 'Unknown error or no data'}"
                logger.error(error_message, extra={"action_id": str(action.action_id), "error_detail": error_detail.model_dump() if error_detail else None})
                raise ExternalServiceError(error_message, error_detail=error_detail.model_dump() if error_detail else None)
            return QueryGenerateResponseData.model_validate(response_action.data)
        except TimeoutError as e:
            logger.error(f"Timeout esperando respuesta de QueryService para {ACTION_QUERY_GENERATE} ({action.action_id}): {e}")
            raise ExternalServiceError(f"Timeout esperando respuesta de QueryService para {ACTION_QUERY_GENERATE}: {str(e)}", original_exception=e)
        except Exception as e:
            logger.error(f"Error inesperado comunicándose con QueryService para {ACTION_QUERY_GENERATE} ({action.action_id}): {e}", exc_info=True)
            raise ExternalServiceError(f"Error inesperado comunicándose con QueryService para {ACTION_QUERY_GENERATE}: {str(e)}", original_exception=e)


    async def llm_direct(
        self,
        messages: List[QueryServiceChatMessage],
        tenant_id: str,
        session_id: str,
        task_id: uuid.UUID,
        llm_config: Optional[QueryServiceLLMConfig] = None,
        tools: Optional[List[QueryServiceToolDefinition]] = None,
        tool_choice: Optional[Union[str, Dict[str, Any]]] = None, # OpenAI type: Literal['none', 'auto'] | ChatCompletionNamedToolChoice
        timeout: Optional[int] = None
    ) -> QueryLLMDirectResponseData:
        """
        Realiza una llamada directa al LLM (sin RAG) usando DomainActions vía Redis.
        Espera una respuesta de forma pseudo-asíncrona.
        """
        # Use provided llm_config or default if None
        qs_llm_config = llm_config if llm_config is not None else QueryServiceLLMConfig()

        payload = QueryLLMDirectPayload(
            messages=messages,
            llm_config=qs_llm_config, # Use created config object
            tools=tools,
            tool_choice=tool_choice
        )

        action = DomainAction(
            action_id=uuid.uuid4(),
            action_type=ACTION_QUERY_LLM_DIRECT,
            timestamp=datetime.now(timezone.utc),
            tenant_id=tenant_id,
            session_id=session_id,
            task_id=task_id,
            origin_service=self.aes_service_name,
            data=payload.model_dump(exclude_none=True),
        )
        actual_timeout = timeout if timeout is not None else self.default_timeout
        try:
            response_action = await self.redis_comms.send_action_pseudo_sync(action, timeout=actual_timeout)
            if not response_action.success or response_action.data is None:
                error_detail = response_action.error
                error_message = f"QueryService error para acción {action.action_id} ({ACTION_QUERY_LLM_DIRECT}): {error_detail.message if error_detail else 'Unknown error or no data'}"
                logger.error(error_message, extra={"action_id": str(action.action_id), "error_detail": error_detail.model_dump() if error_detail else None})
                raise ExternalServiceError(error_message, error_detail=error_detail.model_dump() if error_detail else None)
            return QueryLLMDirectResponseData.model_validate(response_action.data)
        except TimeoutError as e:
            logger.error(f"Timeout esperando respuesta de QueryService para {ACTION_QUERY_LLM_DIRECT} ({action.action_id}): {e}")
            raise ExternalServiceError(f"Timeout esperando respuesta de QueryService para {ACTION_QUERY_LLM_DIRECT}: {str(e)}", original_exception=e)
        except Exception as e:
            logger.error(f"Error inesperado comunicándose con QueryService para {ACTION_QUERY_LLM_DIRECT} ({action.action_id}): {e}", exc_info=True)
            raise ExternalServiceError(f"Error inesperado comunicándose con QueryService para {ACTION_QUERY_LLM_DIRECT}: {str(e)}", original_exception=e)


    async def search_only(
        self,
        query_text: str,
        tenant_id: str,
        session_id: str,
        task_id: uuid.UUID,
        collection_ids: List[str],
        top_k: int = 5,
        filters: Optional[Dict[str, Any]] = None,
        similarity_threshold: Optional[float] = None,
        timeout: Optional[int] = None
    ) -> QuerySearchResponseData:
        """
        Realiza solo búsqueda vectorial usando DomainActions vía Redis.
        """
        payload = QuerySearchPayload(
            query_text=query_text,
            collection_ids=collection_ids,
            top_k=top_k,
            filters=filters,
            similarity_threshold=similarity_threshold
        )

        action = DomainAction(
            action_id=uuid.uuid4(),
            action_type=ACTION_QUERY_SEARCH,
            timestamp=datetime.now(timezone.utc),
            tenant_id=tenant_id,
            session_id=session_id,
            task_id=task_id,
            origin_service=self.aes_service_name,
            data=payload.model_dump(exclude_none=True),
        )
        actual_timeout = timeout if timeout is not None else self.default_timeout
        try:
            response_action = await self.redis_comms.send_action_pseudo_sync(action, timeout=actual_timeout)
            if not response_action.success or response_action.data is None:
                error_detail = response_action.error
                error_message = f"QueryService error para acción {action.action_id} ({ACTION_QUERY_SEARCH}): {error_detail.message if error_detail else 'Unknown error or no data'}"
                logger.error(error_message, extra={"action_id": str(action.action_id), "error_detail": error_detail.model_dump() if error_detail else None})
                raise ExternalServiceError(error_message, error_detail=error_detail.model_dump() if error_detail else None)
            return QuerySearchResponseData.model_validate(response_action.data)
        except TimeoutError as e:
            logger.error(f"Timeout esperando respuesta de QueryService para {ACTION_QUERY_SEARCH} ({action.action_id}): {e}")
            raise ExternalServiceError(f"Timeout esperando respuesta de QueryService para {ACTION_QUERY_SEARCH}: {str(e)}", original_exception=e)
        except Exception as e:
            logger.error(f"Error inesperado comunicándose con QueryService para {ACTION_QUERY_SEARCH} ({action.action_id}): {e}", exc_info=True)
            raise ExternalServiceError(f"Error inesperado comunicándose con QueryService para {ACTION_QUERY_SEARCH}: {str(e)}", original_exception=e)