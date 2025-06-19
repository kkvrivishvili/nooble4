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
from common.config.base_settings import CommonAppSettings # Para tipar settings

logger = logging.getLogger(__name__)

DEFAULT_REDIS_TIMEOUT = 30 # segundos

class QueryClient:
    """Cliente para Query Service vía Redis DomainActions, utilizando BaseRedisClient."""

    def __init__(
        self,
        aes_service_name: str, # Nombre del servicio actual (AgentExecutionService)
        redis_conn: redis_async.Redis,
        settings: CommonAppSettings, # Configuración de AES, que hereda de CommonAppSettings
        default_timeout: int = DEFAULT_REDIS_TIMEOUT
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
        self.default_timeout = default_timeout
        # query_service_name se definirá en el action_type de la DomainAction, ej "query.llm.direct" -> target service "query"



    async def query_with_rag(
        self,
        query_text: str,
        tenant_id: str,
        session_id: str,
        task_id: uuid.UUID, # Añadido para propagación
        collection_ids: Optional[List[str]] = None,
        # llm_config es parte de QueryGeneratePayload, no campos separados como en LLMDirectPayload
        llm_config_params: Optional[Dict[str, Any]] = None, # Renombrado para claridad
        timeout: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Realiza una consulta RAG al Query Service usando DomainActions vía Redis.
        Asegúrate que QueryGeneratePayload en QueryService espera estos campos.
        """
        payload = {
            "query_text": query_text,
            "tenant_id": tenant_id, 
            "session_id": session_id,
            "collection_ids": collection_ids or [],
        }
        # QueryGeneratePayload espera campos como llm_model, temperature, etc. directamente.
        if llm_config_params:
            payload.update({
                "llm_model": llm_config_params.get("model_name") or llm_config_params.get("llm_model"),
                "temperature": llm_config_params.get("temperature"),
                "max_tokens": llm_config_params.get("max_tokens"),
                "system_prompt": llm_config_params.get("system_prompt"),
                "top_p": llm_config_params.get("top_p"),
                "frequency_penalty": llm_config_params.get("frequency_penalty"),
                "presence_penalty": llm_config_params.get("presence_penalty"),
                "stop_sequences": llm_config_params.get("stop_sequences"),
                "user_id": llm_config_params.get("user_id"),
                "conversation_history": llm_config_params.get("conversation_history"),
                # Campos de búsqueda
                "top_k": llm_config_params.get("top_k"),
                "similarity_threshold": llm_config_params.get("similarity_threshold"),
            })

        action = DomainAction(
            action_id=uuid.uuid4(),
            action_type="query.generate", # Target service "query", action "generate"
            timestamp=datetime.now(timezone.utc),
            tenant_id=tenant_id,
            session_id=session_id,
            task_id=task_id,
            origin_service=self.aes_service_name,
            data=payload,
            # correlation_id y callback_queue_name son gestionados por send_action_pseudo_sync
        )
        actual_timeout = timeout if timeout is not None else self.default_timeout
        try:
            response_action = await self.redis_comms.send_action_pseudo_sync(action, timeout=actual_timeout)
            if not response_action.success:
                error_detail = response_action.error
                error_message = f"QueryService error para acción {action.action_id} (query.generate): {error_detail.message if error_detail else 'Unknown error'}"
                logger.error(error_message, extra={"action_id": str(action.action_id), "error_detail": error_detail.model_dump() if error_detail else None})
                raise ExternalServiceError(error_message, error_detail=error_detail.model_dump() if error_detail else None)
            return response_action.data if response_action.data is not None else {}
        except TimeoutError as e:
            logger.error(f"Timeout esperando respuesta de QueryService para query.generate ({action.action_id}): {e}")
            raise ExternalServiceError(f"Timeout esperando respuesta de QueryService para query.generate: {str(e)}", original_exception=e)
        except Exception as e:
            logger.error(f"Error inesperado comunicándose con QueryService para query.generate ({action.action_id}): {e}", exc_info=True)
            raise ExternalServiceError(f"Error inesperado comunicándose con QueryService para query.generate: {str(e)}", original_exception=e)

    async def llm_direct(
        self,
        messages: List[Dict[str, str]],
        tenant_id: str,
        session_id: str,
        task_id: uuid.UUID, # Añadido para propagación
        llm_config_params: Optional[Dict[str, Any]] = None, # Renombrado para claridad
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: Optional[str] = None,
        timeout: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Realiza una llamada directa al LLM (sin RAG) usando DomainActions vía Redis.
        Espera una respuesta de forma pseudo-asíncrona.
        
        Args:
            messages: Lista de mensajes en formato OpenAI.
            tenant_id: ID del tenant.
            session_id: ID de la sesión.
            task_id: ID de la tarea de alto nivel.
            llm_config_params: Configuración del LLM (ej. model_name, temperature).
            tools: Definiciones de herramientas para tool calling.
            tool_choice: Control de selección de herramientas.
            timeout: Timeout específico para esta llamada.
            
        Returns:
            Diccionario con la respuesta del LLM, incluyendo posibles tool_calls.
            Corresponde al 'data' de LLMDirectResponse.
        """
        payload = {
            "messages": messages,
            "tenant_id": tenant_id, 
            "session_id": session_id,
        }

        if llm_config_params:
            payload["llm_model"] = llm_config_params.get("model_name") or llm_config_params.get("llm_model")
            if "temperature" in llm_config_params: payload["temperature"] = llm_config_params.get("temperature")
            if "max_tokens" in llm_config_params: payload["max_tokens"] = llm_config_params.get("max_tokens")
            if "top_p" in llm_config_params: payload["top_p"] = llm_config_params.get("top_p")
            if "frequency_penalty" in llm_config_params: payload["frequency_penalty"] = llm_config_params.get("frequency_penalty")
            if "presence_penalty" in llm_config_params: payload["presence_penalty"] = llm_config_params.get("presence_penalty")
            if "stop_sequences" in llm_config_params: payload["stop_sequences"] = llm_config_params.get("stop_sequences")
            if "user_id" in llm_config_params: payload["user_id"] = llm_config_params.get("user_id")
        
        if tools:
            payload["tools"] = tools
            if tool_choice: 
                payload["tool_choice"] = tool_choice

        action = DomainAction(
            action_id=uuid.uuid4(),
            action_type="query.llm.direct", # Target service "query", action "llm.direct"
            timestamp=datetime.now(timezone.utc),
            tenant_id=tenant_id,
            session_id=session_id,
            task_id=task_id,
            origin_service=self.aes_service_name,
            data=payload,
        )
        actual_timeout = timeout if timeout is not None else self.default_timeout
        try:
            response_action = await self.redis_comms.send_action_pseudo_sync(action, timeout=actual_timeout)
            if not response_action.success:
                error_detail = response_action.error
                error_message = f"QueryService error para acción {action.action_id} (query.llm.direct): {error_detail.message if error_detail else 'Unknown error'}"
                logger.error(error_message, extra={"action_id": str(action.action_id), "error_detail": error_detail.model_dump() if error_detail else None})
                raise ExternalServiceError(error_message, error_detail=error_detail.model_dump() if error_detail else None)
            return response_action.data if response_action.data is not None else {}
        except TimeoutError as e:
            logger.error(f"Timeout esperando respuesta de QueryService para query.llm.direct ({action.action_id}): {e}")
            raise ExternalServiceError(f"Timeout esperando respuesta de QueryService para query.llm.direct: {str(e)}", original_exception=e)
        except Exception as e:
            logger.error(f"Error inesperado comunicándose con QueryService para query.llm.direct ({action.action_id}): {e}", exc_info=True)
            raise ExternalServiceError(f"Error inesperado comunicándose con QueryService para query.llm.direct: {str(e)}", original_exception=e)

    async def search_only(
        self,
        query_text: str,
        tenant_id: str,
        session_id: str,
        task_id: uuid.UUID, # Añadido para propagación
        collection_ids: Optional[List[str]] = None,
        top_k: int = 5,
        # Otros parámetros de QuerySearchPayload como filters, similarity_threshold
        search_params: Optional[Dict[str, Any]] = None,
        timeout: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Realiza solo búsqueda vectorial usando DomainActions vía Redis.
        Asegúrate que QuerySearchPayload en QueryService espera estos campos.
        """
        payload = {
            "query_text": query_text,
            "tenant_id": tenant_id,
            "session_id": session_id,
            "collection_ids": collection_ids or [],
            "top_k": top_k
        }
        if search_params:
            if "filters" in search_params: payload["filters"] = search_params.get("filters")
            if "similarity_threshold" in search_params: payload["similarity_threshold"] = search_params.get("similarity_threshold")

        action = DomainAction(
            action_id=uuid.uuid4(),
            action_type="query.search", # Target service "query", action "search"
            timestamp=datetime.now(timezone.utc),
            tenant_id=tenant_id,
            session_id=session_id,
            task_id=task_id,
            origin_service=self.aes_service_name,
            data=payload,
        )
        actual_timeout = timeout if timeout is not None else self.default_timeout
        try:
            response_action = await self.redis_comms.send_action_pseudo_sync(action, timeout=actual_timeout)
            if not response_action.success:
                error_detail = response_action.error
                error_message = f"QueryService error para acción {action.action_id} (query.search): {error_detail.message if error_detail else 'Unknown error'}"
                logger.error(error_message, extra={"action_id": str(action.action_id), "error_detail": error_detail.model_dump() if error_detail else None})
                raise ExternalServiceError(error_message, error_detail=error_detail.model_dump() if error_detail else None)
            return response_action.data if response_action.data is not None else {}
        except TimeoutError as e:
            logger.error(f"Timeout esperando respuesta de QueryService para query.search ({action.action_id}): {e}")
            raise ExternalServiceError(f"Timeout esperando respuesta de QueryService para query.search: {str(e)}", original_exception=e)
        except Exception as e:
            logger.error(f"Error inesperado comunicándose con QueryService para query.search ({action.action_id}): {e}", exc_info=True)
            raise ExternalServiceError(f"Error inesperado comunicándose con QueryService para query.search: {str(e)}", original_exception=e)