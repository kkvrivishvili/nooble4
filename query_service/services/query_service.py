"""
Implementación del servicio principal de Query Service.

Este servicio extiende BaseService y orquesta la lógica de negocio,
delegando operaciones específicas a los handlers correspondientes.
"""

import logging
from typing import Optional, Dict, Any
from uuid import uuid4

from pydantic import ValidationError

from common.services import BaseService
from common.models import DomainAction, ErrorDetail # ErrorDetail might not be used directly here anymore
from common.errors.exceptions import InvalidActionError, ExternalServiceError

from ..models import (
    ACTION_QUERY_GENERATE,
    ACTION_QUERY_LLM_DIRECT,
    ACTION_QUERY_SEARCH,
    ACTION_QUERY_STATUS,
    QueryGeneratePayload,
    QuerySearchPayload,
    QueryStatusPayload,
    QueryLLMDirectPayload,
    QueryErrorResponseData, # Changed from QueryErrorResponse
    QueryStatusResponseData # Added for status response
)
from ..handlers.rag_handler import RAGHandler
from ..handlers.search_handler import SearchHandler
from ..handlers.llm_handler import LLMHandler


class QueryService(BaseService):
    """
    Servicio principal para procesamiento de consultas.
    
    Maneja las acciones:
    - query.generate: Procesamiento RAG completo (búsqueda + generación)
    - query.search: Solo búsqueda vectorial
    - query.llm.direct: Llamada directa al LLM
    - query.status: Estado de una consulta (opcional)
    """
    
    def __init__(self, app_settings, service_redis_client=None, direct_redis_conn=None):
        """
        Inicializa el servicio con sus handlers.
        
        Args:
            app_settings: QueryServiceSettings con la configuración
            service_redis_client: Cliente Redis para enviar acciones a otros servicios
            direct_redis_conn: Conexión Redis directa para operaciones internas
        """
        super().__init__(app_settings, service_redis_client, direct_redis_conn)
        
        self.rag_handler = RAGHandler(
            app_settings=app_settings,
            direct_redis_conn=direct_redis_conn
        )
        
        self.search_handler = SearchHandler(
            app_settings=app_settings,
            direct_redis_conn=direct_redis_conn
        )
        
        self.llm_handler = LLMHandler(
            app_settings=app_settings,
            direct_redis_conn=direct_redis_conn
        )
        
        self.embedding_client = None
        if service_redis_client:
            # Consider moving client instantiation to an on-demand or factory pattern if complex
            from ..clients.embedding_client import EmbeddingClient
            self.embedding_client = EmbeddingClient(service_redis_client)
        
        self._logger.info("QueryService inicializado correctamente")
    
    async def process_action(self, action: DomainAction) -> Optional[Dict[str, Any]]:
        """
        Procesa una DomainAction según su tipo.
        """
        self._logger.info(
            f"Procesando acción: {action.action_type} ({action.action_id})",
            extra={
                "action_id": str(action.action_id),
                "action_type": action.action_type,
                "tenant_id": action.tenant_id,
                "correlation_id": str(action.correlation_id) if action.correlation_id else None,
                "task_id": str(action.task_id) if action.task_id else None
            }
        )
        
        try:
            if action.action_type == ACTION_QUERY_GENERATE:
                return await self._handle_generate(action)
            elif action.action_type == ACTION_QUERY_SEARCH:
                return await self._handle_search(action)
            elif action.action_type == ACTION_QUERY_LLM_DIRECT:
                return await self._handle_llm_direct(action)
            elif action.action_type == ACTION_QUERY_STATUS:
                return await self._handle_status(action)
            else:
                self._logger.warning(f"Tipo de acción no soportado: {action.action_type}")
                raise InvalidActionError(
                    f"Acción '{action.action_type}' no es soportada por Query Service"
                )
        except ValidationError as e:
            self._logger.error(f"Error de validación en {action.action_type} para action_id {action.action_id}: {e}", exc_info=True)
            error_response = QueryErrorResponseData(
                query_id=str(action.action_id),
                action=action.action_type,
                error_type="ValidationError",
                error_message="Error de validación en el payload de la acción.",
                error_details={"validation_errors": e.errors()}
            )
            return error_response.model_dump()
        except ExternalServiceError as e:
            self._logger.error(f"Error de servicio externo en {action.action_type} para action_id {action.action_id}: {e}", exc_info=True)
            error_response = QueryErrorResponseData(
                query_id=str(action.action_id),
                action=action.action_type,
                error_type="ExternalServiceError",
                error_message=str(e),
                error_details={"service_name": e.service_name, "original_error": str(e.original_exception) if e.original_exception else None}
            )
            return error_response.model_dump()
        except Exception as e:
            self._logger.exception(f"Error inesperado procesando {action.action_type} para action_id {action.action_id}")
            # For unexpected errors, we might not have a query_id if parsing action itself failed
            # However, action_id is from DomainAction, so it should be available.
            error_response = QueryErrorResponseData(
                query_id=str(action.action_id),
                action=action.action_type,
                error_type="InternalServerError",
                error_message="Ocurrió un error inesperado en QueryService.",
                error_details={"exception_type": e.__class__.__name__, "detail": str(e)}
            )
            # Unlike BaseWorker, BaseService might not automatically handle this response.
            # Depending on the worker's _handle_action, this might need to be returned or re-raised.
            # For now, returning the error payload, assuming worker sends it back.
            return error_response.model_dump()

    def _get_effective_llm_params(self, llm_config, overrides):
        """Helper to get effective LLM parameters considering overrides."""
        # Start with llm_config as a dict
        params = llm_config.model_dump()
        
        # Apply overrides for specific keys that map to llm_config fields
        # Note: overrides keys should match the expected handler param names or llm_config field names
        if "llm_model" in overrides: params["model_name"] = overrides["llm_model"]
        if "temperature" in overrides: params["temperature"] = overrides["temperature"]
        if "max_tokens" in overrides: params["max_tokens"] = overrides["max_tokens"]
        if "top_p" in overrides: params["top_p"] = overrides["top_p"]
        if "frequency_penalty" in overrides: params["frequency_penalty"] = overrides["frequency_penalty"]
        if "presence_penalty" in overrides: params["presence_penalty"] = overrides["presence_penalty"]
        if "stop_sequences" in overrides: params["stop_sequences"] = overrides["stop_sequences"]
        if "user_id" in overrides: params["user_id"] = overrides["user_id"]
        # stream is part of llm_config but usually not overridden this way by action.metadata

        return params

    async def _handle_generate(self, action: DomainAction) -> Dict[str, Any]:
        payload = QueryGeneratePayload.model_validate(action.data)
        config_overrides = action.metadata or {}

        # Apply overrides from action.metadata to the payload object
        if "top_k_retrieval" in config_overrides and config_overrides["top_k_retrieval"] is not None:
            payload.top_k_retrieval = config_overrides["top_k_retrieval"]
        if "similarity_threshold" in config_overrides and config_overrides["similarity_threshold"] is not None:
            payload.similarity_threshold = config_overrides["similarity_threshold"]
        if "system_prompt_template" in config_overrides and config_overrides["system_prompt_template"] is not None:
            payload.system_prompt_template = config_overrides["system_prompt_template"]
        
        if payload.llm_config: # Ensure llm_config exists before trying to update it
            if "llm_model" in config_overrides and config_overrides["llm_model"] is not None:
                payload.llm_config.model_name = config_overrides["llm_model"]
            if "temperature" in config_overrides and config_overrides["temperature"] is not None:
                payload.llm_config.temperature = config_overrides["temperature"]
            if "max_tokens" in config_overrides and config_overrides["max_tokens"] is not None:
                payload.llm_config.max_tokens = config_overrides["max_tokens"]
            if "top_p" in config_overrides and config_overrides["top_p"] is not None:
                payload.llm_config.top_p = config_overrides["top_p"]
            if "frequency_penalty" in config_overrides and config_overrides["frequency_penalty"] is not None:
                payload.llm_config.frequency_penalty = config_overrides["frequency_penalty"]
            if "presence_penalty" in config_overrides and config_overrides["presence_penalty"] is not None:
                payload.llm_config.presence_penalty = config_overrides["presence_penalty"]
            if "stop_sequences" in config_overrides: # Allow None or empty list
                payload.llm_config.stop_sequences = config_overrides["stop_sequences"]
            if "user_id" in config_overrides: # Allow None
                payload.llm_config.user = config_overrides["user_id"] # Assuming llm_config has a 'user' field
        elif config_overrides: # If llm_config is None but there are LLM overrides, create a default config
            from ..models.base_models import QueryServiceLLMConfig # Local import
            payload.llm_config = QueryServiceLLMConfig(
                model_name=config_overrides.get("llm_model"),
                temperature=config_overrides.get("temperature"),
                max_tokens=config_overrides.get("max_tokens"),
                top_p=config_overrides.get("top_p"),
                frequency_penalty=config_overrides.get("frequency_penalty"),
                presence_penalty=config_overrides.get("presence_penalty"),
                stop_sequences=config_overrides.get("stop_sequences"),
                user=config_overrides.get("user_id")
            )

        response = await self.rag_handler.process_rag_query(
            payload=payload, # Pass the entire payload object
            tenant_id=action.tenant_id,
            session_id=action.session_id,
            task_id=action.task_id,
            trace_id=action.trace_id,
            correlation_id=action.correlation_id,
            embedding_client=self.embedding_client
        )
        return response.model_dump()
    
    async def _handle_search(self, action: DomainAction) -> Dict[str, Any]:
        payload = QuerySearchPayload.model_validate(action.data)
        config_overrides = action.metadata or {}
        
        response = await self.search_handler.search_documents(
            query_text=payload.query_text,
            collection_ids=payload.collection_ids,
            tenant_id=action.tenant_id,
            top_k=payload.top_k or config_overrides.get("top_k"),
            similarity_threshold=payload.similarity_threshold or config_overrides.get("similarity_threshold"),
            filters=payload.filters,
            trace_id=action.trace_id,
            embedding_client=self.embedding_client,
            session_id=action.session_id,
            task_id=action.task_id
        )
        return response.model_dump()
    
    async def _handle_status(self, action: DomainAction) -> Dict[str, Any]:
        try:
            payload = QueryStatusPayload.model_validate(action.data)
        except ValidationError as e:
            # Handle validation error specifically for status payload if needed, or let global handler catch
            self._logger.error(f"Validation error in QueryStatusPayload for action_id {action.action_id}: {e}")
            error_response = QueryErrorResponseData(
                query_id=action.data.get("query_id", str(action.action_id)), # Try to get query_id if parsing failed
                action=action.action_type,
                error_type="ValidationError",
                error_message="Payload para query.status inválido.",
                error_details={"validation_errors": e.errors()}
            )
            return error_response.model_dump()

        self._logger.info(f"Status check solicitado para query_id: {payload.query_id}")
        
        # Placeholder: Actual status check logic would go here (e.g., check DB or cache)
        status_response = QueryStatusResponseData(
            query_id=payload.query_id,
            status="not_found", # Example status
            action_type=None, # Could be enriched if status tracking stores original action type
            result_preview=None,
            error_info=None,
            metadata={"message": "La funcionalidad de status check detallado no está completamente implementada."}
        )
        return status_response.model_dump()

    async def _handle_llm_direct(self, action: DomainAction) -> Dict[str, Any]:
        payload = QueryLLMDirectPayload.model_validate(action.data)
        config_overrides = action.metadata or {}

        llm_params_for_handler = self._get_effective_llm_params(payload.llm_config, config_overrides)
        
        response = await self.llm_handler.process_llm_direct(
            messages=payload.messages, # Now List[QueryServiceChatMessage]
            tenant_id=action.tenant_id,
            session_id=action.session_id,
            
            llm_model=llm_params_for_handler["model_name"],
            temperature=llm_params_for_handler["temperature"],
            max_tokens=llm_params_for_handler["max_tokens"],
            top_p=llm_params_for_handler["top_p"],
            frequency_penalty=llm_params_for_handler["frequency_penalty"],
            presence_penalty=llm_params_for_handler["presence_penalty"],
            stop_sequences=llm_params_for_handler["stop_sequences"],
            # provider and stream are part of llm_config but not typically passed individually here
            
            tools=payload.tools, # Now List[QueryServiceToolDefinition]
            tool_choice=payload.tool_choice,
            
            user_id=llm_params_for_handler["user_id"],
            trace_id=action.trace_id,
            correlation_id=action.correlation_id
            # task_id could be added if llm_handler supports it
        )
        return response.model_dump()