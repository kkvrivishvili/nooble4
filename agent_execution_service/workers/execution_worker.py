"""
Worker mejorado para Domain Actions en Agent Execution Service.

Implementación estandarizada con inicialización asíncrona y
manejo robusto de callbacks y acciones de ejecución.

VERSIÓN: 4.0 - Adaptado al patrón BaseWorker con procesamiento directo
"""

import logging
import json
import asyncio
import uuid # For correlation_id
from typing import Dict, Any, List, Optional

from common.workers.base_worker import BaseWorker
from common.models.actions import DomainAction, DomainActionResponse, ErrorDetail
from common.services.domain_queue_manager import DomainQueueManager
from common.models.execution_context import ExecutionContext
from agent_execution_service.models.actions_model import (
    AgentExecutionAction,
    ExecutionCallbackAction,
    # EmbeddingRequestAction, # Removed as unused
    # QueryRequestAction,     # Removed as unused
    DocumentProcessSyncActionData,
    DocumentProcessSyncAction,
    ConversationGetHistoryActionData, # For AES to send to CS
    ConversationGetHistoryAction,     # For AES to send to CS
    ConversationGetContextActionData, # For AES to send to CS
    ConversationGetContextAction,     # For AES to send to CS
    ExecutionGetAgentConfigActionData,    # For AES to receive
    ExecutionGetAgentConfigAction,        # For AES to receive
    ExecutionGetConversationHistoryActionData, # For AES to receive
    ExecutionGetConversationHistoryAction,     # For AES to receive
    ExecutionGetConversationContextActionData, # For AES to receive
    ExecutionGetConversationContextAction      # For AES to receive
)
from agent_management_service.models.actions_model import GetAgentConfigAction as ManagementGetAgentConfigAction # Action AES sends to AMS
from ingestion_service.models.actions import DocumentProcessAction as IngestionDocumentProcessAction # To avoid name clash
from agent_execution_service.handlers.agent_execution_handler import AgentExecutionHandler
from agent_execution_service.handlers.context_handler import get_context_handler
from agent_execution_service.handlers.execution_callback_handler import ExecutionCallbackHandler
from agent_execution_service.handlers.embedding_callback_handler import EmbeddingCallbackHandler
from agent_execution_service.handlers.query_callback_handler import QueryCallbackHandler
from agent_execution_service.config.settings import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

class ExecutionWorker(BaseWorker):
    """
    Worker mejorado para procesar Domain Actions de ejecución de agentes.
    
    Características:
    - Inicialización asíncrona segura
    - Integración con context handlers
    - Manejo de callbacks específicos
    - Estadísticas detalladas
    """
    
    def __init__(self, redis_client, queue_manager=None):
        """
        Inicializa worker con servicios necesarios.
        
        Args:
            redis_client: Cliente Redis configurado (requerido)
            queue_manager: Gestor de colas por dominio (opcional)
        """
        queue_manager = queue_manager or DomainQueueManager(redis_client)
        super().__init__(redis_client, queue_manager)
        
        # Definir domain específico
        self.domain = settings.domain_name  # "execution"
        
        # Variables que se inicializarán de forma asíncrona
        self.context_handler = None
        self.execution_callback_handler = None
        self.agent_execution_handler = None
        self.embedding_callback_handler = None
        self.query_callback_handler = None
        self.initialized = False
        self.uuid = uuid # For generating correlation IDs
    
    async def initialize(self):
        """Inicializa el worker de forma asíncrona."""
        if self.initialized:
            return
            
        # Inicializar servicios y handlers necesarios
        # Context handler
        self.context_handler = await get_context_handler(self.redis_client)
        
        # Execution callback handler
        self.execution_callback_handler = ExecutionCallbackHandler(
            self.queue_manager, self.redis_client
        )
        
        # Agent execution handler
        self.agent_execution_handler = AgentExecutionHandler(
            self.context_handler, self.redis_client
        )
        
        # Callback handlers para servicios externos
        self.embedding_callback_handler = EmbeddingCallbackHandler()
        self.query_callback_handler = QueryCallbackHandler()
        
        # Definir las colas adicionales para callbacks
        self.callback_queues = [
            "embedding:callbacks",
            "query:callbacks"
        ]
        
        self.initialized = True
        logger.info("ExecutionWorker inicializado correctamente")
    
    async def start(self):
        """Extiende el método start para monitorear colas adicionales."""
        # Asegurar inicialización antes de procesar acciones
        await self.initialize()
        
        # Iniciar procesamiento estándar
        await super().start()
    
    async def _process_action_loop(self):
        """Sobrescribe el loop de procesamiento para incluir colas adicionales."""
        self.running = True
        
        action_queues = [
            f"{self.domain}:{tenant_id}:actions" 
            for tenant_id in settings.supported_tenants
        ]
        all_queues = action_queues + self.callback_queues
        
        logger.info(f"Escuchando en colas: {all_queues}")
        
        while self.running:
            action_dict_for_error_cb = None
            action_for_error_cb = None
            queue_name_for_log = "desconocida"
            try:
                result_brpop = await self.redis_client.brpop(all_queues, timeout=5)
                
                if result_brpop:
                    queue_name, action_data_str = result_brpop
                    queue_name_for_log = queue_name # For logging in exception block
                    action_dict = json.loads(action_data_str)
                    action_dict_for_error_cb = action_dict
                    
                    action = self.create_action_from_data(action_dict)
                    action_for_error_cb = action
                    
                    context = None
                    if hasattr(action, 'execution_context') and action.execution_context:
                        context = ExecutionContext(
                            tenant_id=action.tenant_id,
                            tenant_tier=action.tenant_tier if hasattr(action, 'tenant_tier') else "standard",
                            session_id=action.session_id if hasattr(action, 'session_id') else None
                        )
                    
                    handler_result = await self._handle_action(action, context)

                    # For non-pseudo-sync actions that return a result and have an async callback queue:
                    if handler_result is not None and hasattr(action, 'callback_queue') and action.callback_queue:
                        await self._send_callback(action, handler_result)
            
            except asyncio.CancelledError:
                logger.info("Procesamiento de acciones cancelado")
                self.running = False
                break
            except Exception as e:
                current_action_id = "unknown"
                if action_dict_for_error_cb and action_dict_for_error_cb.get("action_id"):
                    current_action_id = action_dict_for_error_cb.get("action_id")
                elif action_for_error_cb and hasattr(action_for_error_cb, 'action_id'):
                    current_action_id = action_for_error_cb.action_id
                
                logger.error(f"Error en ExecutionWorker loop procesando acción {current_action_id} desde {queue_name_for_log}: {str(e)}", exc_info=True)
                
                if action_dict_for_error_cb and action_dict_for_error_cb.get("callback_queue"):
                    try:
                        await self._send_error_callback(action_dict_for_error_cb, f"Unhandled error in worker loop: {str(e)}")
                    except Exception as cb_e:
                        logger.error(f"Failed to send error callback after worker loop error for action {current_action_id}: {str(cb_e)}", exc_info=True)
                await asyncio.sleep(1)
        
        logger.info("ExecutionWorker: Handlers inicializados")

    async def _send_pseudo_sync_response(self, action: DomainAction, handler_result: Dict[str, Any]):
        """Sends a pseudo-synchronous success or error response based on handler_result."""
        # Determine if the handler_result itself is a fully formed DomainActionResponse payload
        # or if it's a simpler dict that needs to be wrapped.
        # For now, assume handler_result is the direct payload for DomainActionResponse's data or error fields.
        is_success = handler_result.get("success", False) if isinstance(handler_result, dict) else False
        
        data_payload = None
        error_detail_payload = None

        if isinstance(handler_result, dict):
            if is_success:
                data_payload = handler_result # Assumes handler_result is the data for success
            else:
                # Attempt to construct ErrorDetail from handler_result if it's an error dict
                error_content = handler_result.get("error", handler_result) # If no 'error' key, use the dict itself
                error_message = error_content.get("message", "Unknown error during pseudo-sync operation") if isinstance(error_content, dict) else str(error_content)
                error_code = error_content.get("type", "PSEUDO_SYNC_HANDLER_ERROR") if isinstance(error_content, dict) else "PSEUDO_SYNC_HANDLER_ERROR"
                error_detail_payload = ErrorDetail(message=error_message, code=error_code)
        else:
            # If handler_result is not a dict, it's unexpected for a pseudo-sync response structure.
            # Treat as error.
            is_success = False
            error_detail_payload = ErrorDetail(message=f"Unexpected handler result type for pseudo-sync: {type(handler_result).__name__}", code="UNEXPECTED_HANDLER_RESULT")

        response = DomainActionResponse(
            success=is_success,
            correlation_id=action.correlation_id,
            trace_id=action.trace_id,
            action_type_response_to=action.action_type,
            data=data_payload if is_success else None,
            error=error_detail_payload if not is_success else None
        )
        
        if action.callback_queue_name:
            await self.redis_client.rpush(action.callback_queue_name, response.json())
            logger.info(f"Sent pseudo-sync response for {action.action_type} to {action.callback_queue_name}")
        else:
            logger.warning(f"No callback_queue_name provided for pseudo-sync action {action.action_type} (orig_id: {action.action_id}), response not sent.")

    async def _send_pseudo_sync_error_response(self, action: DomainAction, error_message: str, error_code: Optional[str] = None):
        """Sends a pseudo-synchronous error response."""
        error_response = DomainActionResponse(
            success=False,
            correlation_id=action.correlation_id,
            trace_id=action.trace_id,
            action_type_response_to=action.action_type,
            error=ErrorDetail(message=error_message, code=error_code or "PSEUDO_SYNC_ERROR")
        )
        if action.callback_queue_name:
            await self.redis_client.rpush(action.callback_queue_name, error_response.json())
            logger.info(f"Sent pseudo-sync error response for {action.action_type} to {action.callback_queue_name}")
        else:
            logger.warning(f"No callback_queue_name provided for pseudo-sync error action {action.action_type} (orig_id: {action.action_id}), error response not sent.")
    
    async def _handle_action(self, action: DomainAction, context: Optional[ExecutionContext] = None) -> Optional[Dict[str, Any]]:
        """
        Handles domain-specific actions.
        For pseudo-synchronous actions received by AES (defined in PSEUDO_SYNC_ACTIONS_RECEIVED_BY_AES),
        it orchestrates the downstream call, sends the response to action.callback_queue_name (the client's queue),
        and returns None to signal that the response has been handled.
        
        For other asynchronous actions, it processes them and returns a result dictionary.
        This result is then picked up by _process_action_loop to send an asynchronous callback
        to action.callback_queue (if provided).
        """
        if not self.initialized:
            await self.initialize()
            
        action_type = action.action_type
        # This list defines actions that AES receives and for which AES itself must provide a pseudo-synchronous response
        # back to ITS original caller using action.callback_queue_name.
        PSEUDO_SYNC_ACTIONS_RECEIVED_BY_AES = [
            "document.process.sync",
            "execution.management.get_agent_config",
            "execution.conversation.get_history",
            "execution.conversation.get_context"
        ]
        
        handler_result: Optional[Dict[str, Any]] = None # Default for async actions if no specific result

        try:
            if action_type == "execution.agent_run":
                logger.info(f"Procesando ejecución de agente: {action.task_id if hasattr(action, 'task_id') else action.action_id}")
                handler_result = await self._handle_agent_execution(action, context) # This will be returned for async callback
            elif action_type == "embedding.callback":
                logger.info(f"Procesando callback de embedding: {action.task_id if hasattr(action, 'task_id') else action.action_id}")
                handler_result = await self.embedding_callback_handler.handle_embedding_callback(action, context) # Returned for async
            elif action_type == "query.callback":
                logger.info(f"Procesando callback de query: {action.task_id if hasattr(action, 'task_id') else action.action_id}")
                handler_result = await self.query_callback_handler.handle_query_callback(action, context) # Returned for async

            elif action_type == "execution.cache.invalidate":
                logger.info(f"Processing cache invalidation for agent: {action.data.get('agent_id')} in tenant: {action.tenant_id}")
                if hasattr(action, 'data') and 'agent_id' in action.data:
                    await self.context_handler.invalidate_agent_config_cache(
                        agent_id=action.data['agent_id'],
                        tenant_id=action.tenant_id
                    )
                else:
                    logger.warning(f"Received execution.cache.invalidate action without agent_id in data. Action ID: {action.action_id}")
                return None # Fire-and-forget, no response needed.
            
            elif action_type in PSEUDO_SYNC_ACTIONS_RECEIVED_BY_AES:
                # These actions require AES to orchestrate a call and send a response to action.callback_queue_name
                specific_downstream_result: Optional[Dict[str, Any]] = None # Result from the _request_... or _handle_..._sync methods
                if action_type == "document.process.sync":
                    logger.info(f"Processing synchronous document action: {action.action_id}")
                    specific_downstream_result = await self._handle_document_process_sync(action, context)
                elif action_type == "execution.management.get_agent_config":
                    logger.info(f"Processing exec get agent config action: {action.action_id}")
                    specific_downstream_result = await self._request_agent_config_sync(action, context)
                elif action_type == "execution.conversation.get_history":
                    logger.info(f"Processing exec get conversation history action: {action.action_id}")
                    specific_downstream_result = await self._request_conversation_history_sync(action, context)
                elif action_type == "execution.conversation.get_context":
                    logger.info(f"Processing exec get conversation context action: {action.action_id}")
                    specific_downstream_result = await self._request_conversation_context_sync(action, context)
                
                # Now, send the pseudo-sync response using the result from the specific handler
                if specific_downstream_result is not None: # Should always be true as handlers return dicts
                    # The action here is the original action received by AES, which has the client's callback_queue_name
                    await self._send_pseudo_sync_response(action, specific_downstream_result)
                else:
                    # This case should ideally not be hit if handlers are robust and always return a dict.
                    logger.error(f"Pseudo-sync handler for {action_type} returned None unexpectedly. Action ID: {action.action_id}")
                    await self._send_pseudo_sync_error_response(action, "Internal handler error: No result from downstream service.", "INTERNAL_HANDLER_ERROR_NONE_RESULT")
                return None # Signal that response has been handled for pseudo-sync actions; _process_action_loop should not send another callback.

            else: # Action type not recognized by any specific handler
                error_msg = f"No handler implemented for action: {action_type}"
                logger.warning(error_msg)
                # For unhandled actions, if it was expected to be pseudo-sync (has callback_queue_name), send error there.
                if hasattr(action, 'callback_queue_name') and action.callback_queue_name: # Check if it's a pseudo-sync client call
                    await self._send_pseudo_sync_error_response(action, error_msg, "UNHANDLED_ACTION_TYPE_PSEUDO_SYNC_EXPECTED")
                    return None # Response handled
                # Otherwise, for async, return an error structure for _process_action_loop to handle via async callback.
                handler_result = {"success": False, "error": {"type": "ValueError", "message": error_msg, "code": "UNHANDLED_ACTION_TYPE"}}
        
        except Exception as e:
            action_id_for_log = action.action_id if hasattr(action, 'action_id') else 'unknown'
            logger.error(f"Exception in ExecutionWorker._handle_action for {action_type} (action_id: {action_id_for_log}): {str(e)}", exc_info=True)
            
            # If it was a pseudo-sync action (identified by being in the list AND having the client's callback_queue_name),
            # try to send an error response on its callback_queue_name.
            if hasattr(action, 'callback_queue_name') and action.callback_queue_name and action_type in PSEUDO_SYNC_ACTIONS_RECEIVED_BY_AES:
                await self._send_pseudo_sync_error_response(action, f"Handler exception: {str(e)}", "HANDLER_EXCEPTION")
                return None # Response handled, _process_action_loop should not send another callback.
            
            # For non-pseudo-sync actions, or if pseudo-sync but something went wrong with its specific error path (e.g., no callback_queue_name),
            # return an error structure for _process_action_loop to send as an async callback.
            handler_result = {
                "success": False,
                "error": {"type": type(e).__name__, "message": str(e), "code": "EXECUTION_HANDLER_EXCEPTION"}
            }
        
        # This return is for:
        # 1. Successfully handled async actions (e.g., execution.agent_run) -> handler_result contains success data.
        # 2. Errors from async actions (either caught by the main try-except or from an unhandled action type) -> handler_result contains error data.
        # It will be picked up by _process_action_loop to potentially send an async callback to action.callback_queue.
        return handler_result

    async def _request_conversation_history_sync(self, action: ExecutionGetConversationHistoryAction, context: Optional[ExecutionContext] = None) -> Dict[str, Any]:
        """
        Sends a 'conversation.get_history' request to ConversationService and waits for a pseudo-synchronous response.
        The 'action' here is the ExecutionGetConversationHistoryAction received by AES.
        """
        if not self.initialized:
            await self.initialize()

        request_data: ExecutionGetConversationHistoryActionData = action.data
        # Use the original action_id from the client of AES to form part of the correlation_id for the downstream call
        base_correlation_id = action.action_id 
        correlation_id = f"{base_correlation_id}_{self.uuid.uuid4()}" # Unique ID for this AES <-> CS leg

        # Callback queue AES listens on for CS's response
        # Format: {redis_prefix}:{env}:{this_service_domain}:responses:{action_type_short}:{correlation_id}
        # Here, 'this_service_domain' is 'execution' (AES), 'action_type_short' refers to the action sent to CS.
        callback_queue_name_for_cs_response = f"{settings.redis_prefix}:{settings.env_name}:{settings.domain_name}:responses:conv_hist_sync:{correlation_id}"

        # Action to send to Conversation Service
        cs_action_payload = ConversationGetHistoryAction(
            action_id=f"cs-hist-{action.action_id[:30]}-{self.uuid.uuid4().hex[:8]}", # New action_id for the CS leg
            action_type="conversation.get_history",
            tenant_id=action.tenant_id,
            origin_service=settings.domain_name, # AES is the origin of this request to CS
            callback_queue_name=callback_queue_name_for_cs_response, # CS will send DomainActionResponse here
            correlation_id=correlation_id, # CS should include this in its response
            trace_id=action.trace_id, # Propagate trace_id
            data=ConversationGetHistoryActionData(
                session_id=request_data.session_id,
                limit=request_data.limit
            )
        )

        # Determine Conversation Service queue (typically tenant-specific)
        cs_queue_name = f"conversation:{action.tenant_id}:actions"
        timeout_seconds = getattr(settings, 'CONVERSATION_SERVICE_SYNC_TIMEOUT_SECONDS', 30)

        try:
            logger.info(f"Sending conversation.get_history request to CS (action_id: {cs_action_payload.action_id}, tenant: {action.tenant_id}, callback: {callback_queue_name_for_cs_response}) via queue {cs_queue_name}")
            await self.queue_manager.enqueue_action(cs_queue_name, cs_action_payload)

            logger.info(f"Waiting for response from CS on {callback_queue_name_for_cs_response} for {timeout_seconds}s...")
            response_data_tuple = await self.redis_client.brpop([callback_queue_name_for_cs_response], timeout=timeout_seconds)

            if response_data_tuple:
                _queue, response_payload_str = response_data_tuple
                logger.info(f"Received response from CS for conversation.get_history: {response_payload_str[:500]}...")
                response_payload = json.loads(response_payload_str)
                
                # The response_payload should be a DomainActionResponse dictionary
                if response_payload.get("correlation_id") != correlation_id:
                    mismatch_msg = f"Correlation ID mismatch. Expected {correlation_id}, got {response_payload.get('correlation_id')}"
                    logger.warning(mismatch_msg)
                    # Return as error to the original caller of AES
                    return {"success": False, "error": {"type": "CorrelationIdMismatch", "message": mismatch_msg}}
                
                # The entire response_payload (which is a DomainActionResponse from CS) is what _handle_action expects
                return response_payload 
            else:
                timeout_msg = f"Timeout waiting for conversation.get_history response from CS for session {request_data.session_id} on {callback_queue_name_for_cs_response}"
                logger.error(timeout_msg)
                return {"success": False, "error": {"type": "TimeoutError", "message": timeout_msg}}

        except Exception as e:
            error_msg = f"Error during conversation.get_history sync request to CS for session {request_data.session_id}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {"success": False, "error": {"type": type(e).__name__, "message": error_msg}}

    async def _request_conversation_context_sync(self, action: ExecutionGetConversationContextAction, context: Optional[ExecutionContext] = None) -> Dict[str, Any]:
        """
        Sends a 'conversation.get_context' request to ConversationService and waits for a pseudo-synchronous response.
        The 'action' here is the ExecutionGetConversationContextAction received by AES.
        """
        if not self.initialized:
            await self.initialize()

        request_data: ExecutionGetConversationContextActionData = action.data
        base_correlation_id = action.action_id
        correlation_id = f"{base_correlation_id}_{self.uuid.uuid4()}"

        callback_queue_name_for_cs_response = f"{settings.redis_prefix}:{settings.env_name}:{settings.domain_name}:responses:conv_ctx_sync:{correlation_id}"

        cs_action_payload = ConversationGetContextAction(
            action_id=f"cs-ctx-{action.action_id[:30]}-{self.uuid.uuid4().hex[:8]}",
            action_type="conversation.get_context",
            tenant_id=action.tenant_id,
            origin_service=settings.domain_name, 
            callback_queue_name=callback_queue_name_for_cs_response,
            correlation_id=correlation_id,
            trace_id=action.trace_id,
            data=ConversationGetContextActionData(
                session_id=request_data.session_id
            )
        )

        cs_queue_name = f"conversation:{action.tenant_id}:actions"
        timeout_seconds = getattr(settings, 'CONVERSATION_SERVICE_SYNC_TIMEOUT_SECONDS', 30)

        try:
            logger.info(f"Sending conversation.get_context request to CS (action_id: {cs_action_payload.action_id}, tenant: {action.tenant_id}, callback: {callback_queue_name_for_cs_response}) via queue {cs_queue_name}")
            await self.queue_manager.enqueue_action(cs_queue_name, cs_action_payload)

            logger.info(f"Waiting for response from CS on {callback_queue_name_for_cs_response} for {timeout_seconds}s...")
            response_data_tuple = await self.redis_client.brpop([callback_queue_name_for_cs_response], timeout=timeout_seconds)

            if response_data_tuple:
                _queue, response_payload_str = response_data_tuple
                logger.info(f"Received response from CS for conversation.get_context: {response_payload_str[:500]}...")
                response_payload = json.loads(response_payload_str)
                
                if response_payload.get("correlation_id") != correlation_id:
                    mismatch_msg = f"Correlation ID mismatch. Expected {correlation_id}, got {response_payload.get('correlation_id')}"
                    logger.warning(mismatch_msg)
                    return {"success": False, "error": {"type": "CorrelationIdMismatch", "message": mismatch_msg}}
                
                return response_payload 
            else:
                timeout_msg = f"Timeout waiting for conversation.get_context response from CS for session {request_data.session_id} on {callback_queue_name_for_cs_response}"
                logger.error(timeout_msg)
                return {"success": False, "error": {"type": "TimeoutError", "message": timeout_msg}}

        except Exception as e:
            error_msg = f"Error during conversation.get_context sync request to CS for session {request_data.session_id}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {"success": False, "error": {"type": type(e).__name__, "message": error_msg}}

    async def _request_agent_config_sync(self, action: ExecutionGetAgentConfigAction, context: Optional[ExecutionContext] = None) -> Dict[str, Any]:
        """
        Sends a 'management.get_agent_config' request to AgentManagementService and waits for a pseudo-synchronous response.
        The 'action' here is the ExecutionGetAgentConfigAction received by AES.
        """
        if not self.initialized:
            await self.initialize()

        request_data: ExecutionGetAgentConfigActionData = action.data
        base_correlation_id = action.action_id
        correlation_id = f"{base_correlation_id}_{self.uuid.uuid4()}"

        callback_queue_name_for_ams_response = f"{settings.redis_prefix}:{settings.env_name}:{settings.domain_name}:responses:agent_cfg_sync:{correlation_id}"

        # Use the imported ManagementGetAgentConfigAction for the payload to AMS
        ams_action_payload = ManagementGetAgentConfigAction(
            action_id=f"ams-cfg-{action.action_id[:30]}-{self.uuid.uuid4().hex[:8]}",
            action_type="management.get_agent_config",
            tenant_id=action.tenant_id,
            origin_service=settings.domain_name, 
            callback_queue_name=callback_queue_name_for_ams_response,
            correlation_id=correlation_id,
            trace_id=action.trace_id,
            data={"agent_id": request_data.agent_id} # AMS GetAgentConfigActionData expects a dict with agent_id
        )

        ams_queue_name = f"management:{action.tenant_id}:actions"
        timeout_seconds = getattr(settings, 'AGENT_MANAGEMENT_SERVICE_SYNC_TIMEOUT_SECONDS', 30)

        try:
            logger.info(f"Sending management.get_agent_config request to AMS (action_id: {ams_action_payload.action_id}, tenant: {action.tenant_id}, callback: {callback_queue_name_for_ams_response}) via queue {ams_queue_name}")
            await self.queue_manager.enqueue_action(ams_queue_name, ams_action_payload)

            logger.info(f"Waiting for response from AMS on {callback_queue_name_for_ams_response} for {timeout_seconds}s...")
            response_data_tuple = await self.redis_client.brpop([callback_queue_name_for_ams_response], timeout=timeout_seconds)

            if response_data_tuple:
                _queue, response_payload_str = response_data_tuple
                logger.info(f"Received response from AMS for management.get_agent_config: {response_payload_str[:500]}...")
                response_payload = json.loads(response_payload_str)
                
                if response_payload.get("correlation_id") != correlation_id:
                    mismatch_msg = f"Correlation ID mismatch. Expected {correlation_id}, got {response_payload.get('correlation_id')}"
                    logger.warning(mismatch_msg)
                    return {"success": False, "error": {"type": "CorrelationIdMismatch", "message": mismatch_msg}}
                
                return response_payload 
            else:
                timeout_msg = f"Timeout waiting for management.get_agent_config response from AMS for agent {request_data.agent_id} on {callback_queue_name_for_ams_response}"
                logger.error(timeout_msg)
                return {"success": False, "error": {"type": "TimeoutError", "message": timeout_msg}}

        except Exception as e:
            error_msg = f"Error during management.get_agent_config sync request to AMS for agent {request_data.agent_id}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {"success": False, "error": {"type": type(e).__name__, "message": error_msg}}

        # If the action was pseudo-synchronous and had a callback queue, response was already sent.
        if action_type in PSEUDO_SYNC_ACTIONS_RECEIVED and action.callback_queue_name:
            if handler_result is not None: # handler_result should contain the response from the downstream service
                await self._send_pseudo_sync_response(action, handler_result)
            # else: error or timeout already handled by the specific _handle_..._sync method and returned as handler_result
            # or if an exception occurred, it was caught above and error response sent.
            return None # Signal to BaseWorker that response has been handled

        # For actions not in PSEUDO_SYNC_ACTIONS_RECEIVED, or if they are but somehow didn't have a callback_queue_name,
        # return the handler_result. BaseWorker's _process_action will then call _send_callback
        # if action.callback_queue_name is set (for async callbacks) and handler_result is not None.
        return handler_result

    async def _handle_document_process_sync(self, action: DocumentProcessSyncAction, context: Optional[ExecutionContext] = None) -> Dict[str, Any]:
        """
        Handles synchronous document processing by sending a request to IngestionService
        and waiting for a response on a callback queue.
        """
        if not self.initialized:
            await self.initialize()

        sync_action_data: DocumentProcessSyncActionData = action.data
        task_id = action.action_id # Use the action_id of the sync request as the task_id for ingestion
        correlation_id = f"{task_id}_{uuid.uuid4()}" # Unique correlation for this specific interaction

        # Define the callback queue AES will listen on for Ingestion Service's response
        # Following MEMORY[9395f05a-ecfb-4003-ad50-a3deff0156af] pattern for pseudo-sync responses
        # nooble4:dev:{client_service_name}:responses:{action_type_short}:{correlation_id}
        # AES is the client here.
        callback_queue_name = f"{settings.redis_prefix}:{settings.env_name}:{settings.domain_name}:responses:doc_proc_sync:{correlation_id}"
        
        # Prepare the action to send to Ingestion Service
        ingestion_action_payload = IngestionDocumentProcessAction(
            action_id=f"ingestion-{task_id}", # New action_id for the async leg
            task_id=task_id, # Propagate original task_id for tracking
            document_id=sync_action_data.document_id,
            collection_id=sync_action_data.collection_id,
            tenant_id=action.tenant_id, # From root DomainAction
            file_key=sync_action_data.file_key,
            url=sync_action_data.url,
            text_content=sync_action_data.text_content,
            title=sync_action_data.title,
            description=sync_action_data.description,
            tags=sync_action_data.tags,
            metadata=sync_action_data.metadata,
            chunk_size=sync_action_data.chunk_size,
            chunk_overlap=sync_action_data.chunk_overlap,
            embedding_model=sync_action_data.embedding_model,
            callback_queue=callback_queue_name, # Ingestion service will send its final status here
            origin_service=settings.domain_name, # This service is the origin for this specific action
            correlation_id=correlation_id # For Ingestion Service to include in its response
        )

        ingestion_queue = settings.INGESTION_DOCUMENT_QUEUE # e.g., "ingestion:documents:process"
        
        try:
            logger.info(f"Sending document processing request to IngestionService (task: {task_id}, callback: {callback_queue_name}) via queue {ingestion_queue}")
            await self.queue_manager.enqueue_action(ingestion_queue, ingestion_action_payload)

            # Wait for the response from Ingestion Service on the callback queue
            # Timeout should be configurable, e.g., settings.DOCUMENT_PROCESS_SYNC_TIMEOUT_SECONDS
            timeout_seconds = getattr(settings, 'DOCUMENT_PROCESS_SYNC_TIMEOUT_SECONDS', 120) 
            logger.info(f"Waiting for response on {callback_queue_name} for {timeout_seconds}s...")
            
            response_data = await self.redis_client.brpop([callback_queue_name], timeout=timeout_seconds)

            if response_data:
                _queue, response_payload_str = response_data
                logger.info(f"Received response from IngestionService: {response_payload_str}")
                response_payload = json.loads(response_payload_str)
                # Ensure the response is for our correlation_id if IngestionService includes it
                if response_payload.get("correlation_id") != correlation_id:
                    logger.warning(f"Correlation ID mismatch. Expected {correlation_id}, got {response_payload.get('correlation_id')}")
                    # Decide if this is a hard error or just a warning
                return response_payload # This is the DomainActionResponse from Ingestion
            else:
                logger.error(f"Timeout waiting for document processing response for task {task_id} on {callback_queue_name}")
                return {"success": False, "error": {"type": "TimeoutError", "message": "Timeout waiting for document processing response."}}

        except Exception as e:
            logger.error(f"Error during synchronous document processing for task {task_id}: {str(e)}", exc_info=True)
            return {"success": False, "error": {"type": type(e).__name__, "message": str(e)}}
    
    async def _handle_agent_execution(self, action: DomainAction, context: Optional[ExecutionContext] = None) -> Dict[str, Any]:
        """
        Handler específico para ejecución de agentes.
        
        Args:
            action: Acción de ejecución
            context: Contexto de ejecución opcional con metadatos adicionales
            
        Returns:
            Resultado del procesamiento
        """
        try:
            # Verificar inicialización
            if not self.initialized:
                await self.initialize()
            
            # Convertir a tipo específico
            agent_action = AgentExecutionAction.parse_obj(action.dict())
            
            # Enriquecer acción con contexto si está disponible
            if context:
                logger.info(f"Procesando acción con tier: {context.tenant_tier}")
                agent_action.tenant_tier = context.tenant_tier
            
            # Procesar ejecución
            result = await self.agent_execution_handler.handle_agent_execution(agent_action)
            
            return result
            
        except Exception as e:
            logger.error(f"Error en handle_agent_execution: {str(e)}")
            return {
                "success": False,
                "error": {
                    "type": type(e).__name__,
                    "message": str(e)
                }
            }

    def create_action_from_data(self, action_data: Dict[str, Any]) -> DomainAction:
        """
        Crea objeto de acción apropiado según los datos.
        
        Args:
            action_data: Datos de la acción en formato JSON
            
        Returns:
            DomainAction del tipo específico
        """
        action_type = action_data.get("action_type")
        
        if action_type == "execution.agent_run":
            return AgentExecutionAction.parse_obj(action_data)
        elif action_type == "embedding.callback":
            # Assuming ExecutionCallbackAction is generic enough or specific model exists
            return ExecutionCallbackAction.parse_obj(action_data) 
        elif action_type == "query.callback":
            # Assuming ExecutionCallbackAction is generic enough or specific model exists
            return ExecutionCallbackAction.parse_obj(action_data) 
        elif action_type == "document.process.sync": # Received by AES
            return DocumentProcessSyncAction.parse_obj(action_data)
        elif action_type == "execution.management.get_agent_config": # Received by AES
            return ExecutionGetAgentConfigAction.parse_obj(action_data)
        elif action_type == "execution.conversation.get_history": # Received by AES
            return ExecutionGetConversationHistoryAction.parse_obj(action_data)
        elif action_type == "execution.conversation.get_context": # Received by AES
            return ExecutionGetConversationContextAction.parse_obj(action_data)
        # Add more specific action types here if necessary
        else:
            # Fallback to generic DomainAction
            logger.warning(f"Creating generic DomainAction for unknown action_type: {action_type}")
            return DomainAction.parse_obj(action_data)
    
    async def _send_callback(self, action: DomainAction, result: Dict[str, Any]):
        """
        Envía resultado como callback.
        
        Args:
            action: Acción original que generó el resultado
            result: Resultado del procesamiento
        """
        try:
            # Validar que haya cola de callback
            if not action.callback_queue:
                logger.warning(f"No se especificó cola de callback para {action.task_id}")
                return
            
            # Crear contexto de ejecución para el callback
            context = ExecutionContext(
                tenant_id=action.tenant_id,
                tenant_tier=action.tenant_tier or "free",  # Asegurar tier por defecto
                session_id=action.session_id
            )
            
            # Determinar tipo de callback según resultado
            if result.get("success", False) and "execution_result" in result:
                # Callback de ejecución exitosa con contexto
                await self.execution_callback_handler.send_success_callback(
                    task_id=action.task_id,
                    tenant_id=action.tenant_id,
                    tenant_tier=action.tenant_tier,
                    session_id=action.session_id,
                    callback_queue=action.callback_queue,
                    execution_result=result["execution_result"],
                    context=context
                )
            else:
                # Callback de error
                await self.execution_callback_handler.send_error_callback(
                    task_id=action.task_id,
                    tenant_id=action.tenant_id,
                    tenant_tier=action.tenant_tier,
                    session_id=action.session_id,
                    callback_queue=action.callback_queue,
                    error_info=result.get("error", {}),
                    execution_time=result.get("execution_time")
                )
            
        except Exception as e:
            logger.error(f"Error enviando callback: {str(e)}")
    
    async def _send_error_callback(self, action_data: Dict[str, Any], error_msg: str):
        """
        Envía callback de error para una acción.
        
        Args:
            action_data: Datos originales de la acción
            error_msg: Mensaje de error
        """
        try:
            # Extraer datos mínimos necesarios
            task_id = action_data.get("task_id", "unknown")
            tenant_id = action_data.get("tenant_id", "unknown")
            tenant_tier = action_data.get("tenant_tier", "free")
            session_id = action_data.get("session_id", "unknown")
            callback_queue = action_data.get("callback_queue", "")
            
            if not callback_queue:
                logger.warning(f"No hay cola de callback para error: {task_id}")
                return
            
            # Crear contexto de ejecución para el callback
            context = ExecutionContext(
                tenant_id=tenant_id,
                tenant_tier=tenant_tier,
                session_id=session_id
            )
                
            # Enviar callback de error con contexto
            await self.execution_callback_handler.send_error_callback(
                task_id=task_id,
                tenant_id=tenant_id,
                tenant_tier=tenant_tier,
                session_id=session_id,
                callback_queue=callback_queue,
                error_message=error_msg,
                context=context
            )
            
        except Exception as e:
            logger.error(f"Error enviando error callback: {str(e)}")
    
    # Método auxiliar para estadísticas específicas del execution service
    async def get_execution_stats(self) -> Dict[str, Any]:
        """Obtiene estadísticas específicas del execution service."""
        # Obtener estadísticas básicas del worker
        stats = await self.get_worker_stats()
        
        if not self.initialized:
            stats["worker_info"]["status"] = "not_initialized"
            return stats
        
        try:
            # Stats de colas
            queue_stats = await self.get_queue_stats()
            
            # Stats de ejecución si están disponibles
            execution_stats = {}
            if self.agent_execution_handler and hasattr(self.agent_execution_handler, 'get_execution_stats'):
                execution_stats = await self.agent_execution_handler.get_execution_stats("all")
            
            # Stats de callbacks
            callback_stats = {}
            if self.execution_callback_handler and hasattr(self.execution_callback_handler, 'get_callback_stats'):
                callback_stats = await self.execution_callback_handler.get_callback_stats("all")
            
            # Añadir estadísticas específicas
            stats.update({
                "queue_stats": queue_stats,
                "execution_stats": execution_stats,
                "callback_stats": callback_stats
            })
            
        except Exception as e:
            logger.error(f"Error obteniendo estadísticas: {str(e)}")
            stats["error"] = str(e)
        
        return stats
