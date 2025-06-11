"""
Worker mejorado para Domain Actions en Conversation Service.

Implementación estandarizada con inicialización asíncrona y
manejo robusto de acciones relacionadas con conversaciones.

VERSIÓN: 4.0 - Adaptado al patrón BaseWorker con procesamiento directo
"""

import logging
import json
from typing import Dict, Any, Optional

from common.workers.base_worker import BaseWorker
from common.models.actions import DomainAction, DomainActionResponse, ErrorDetail
from common.models.execution_context import ExecutionContext
from common.services.domain_queue_manager import DomainQueueManager
from conversation_service.models.actions_model import (
    SaveMessageAction, GetContextAction, SessionClosedAction, GetHistoryAction
)
from conversation_service.handlers.conversation_handler import ConversationHandler
from conversation_service.services.conversation_service import ConversationService
from conversation_service.config.settings import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

class ConversationWorker(BaseWorker):
    """
    Worker mejorado para Domain Actions de conversaciones.
    
    Características:
    - Inicialización asíncrona segura
    - Integración con servicios de conversación
    - Soporte para guardar mensajes y obtener contexto
    - Manejo de cierre de sesiones
    """
    
    def __init__(self, redis_client, queue_manager=None, db_client=None):
        """
        Inicializa worker con servicios necesarios.
        
        Args:
            redis_client: Cliente Redis configurado (requerido)
            queue_manager: Gestor de colas por dominio (opcional)
            db_client: Cliente de base de datos (opcional)
        """
        queue_manager = queue_manager or DomainQueueManager(redis_client)
        super().__init__(redis_client, queue_manager)
        
        # Definir domain específico
        self.domain = settings.domain_name  # "conversation"
        
        # Almacenar db_client para usar en la inicialización
        self.db_client = db_client
        
        # Variables para inicialización asíncrona
        self.conversation_service = None
        self.conversation_handler = None
        self.initialized = False
    
    async def initialize(self):
        """Inicializa el worker de forma asíncrona."""
        if self.initialized:
            return
            
        # Inicializar servicios requeridos
        self.conversation_service = ConversationService(self.redis_client, self.db_client)
        self.conversation_handler = ConversationHandler(self.conversation_service)
        
        self.initialized = True
        logger.info("ConversationWorker inicializado correctamente")
    
    async def start(self):
        """Extiende el start para asegurar inicialización."""
        # Asegurar inicialización antes de procesar acciones
        await self.initialize()
        
        # Continuar con el comportamiento normal del BaseWorker
        await super().start()

    async def _send_pseudo_sync_response(self, action: DomainAction, handler_result: Dict[str, Any]):
        response = DomainActionResponse(
            success=handler_result.get("success", False),
            correlation_id=action.correlation_id,
            trace_id=action.trace_id,
            action_type_response_to=action.action_type,
            error=ErrorDetail(message=str(handler_result.get("error", "Unknown error"))) if not handler_result.get("success", False) else None
        )
        if response.success:
            # Pass through any data from the handler result, except for the 'success' flag itself.
            response.data = {k: v for k, v in handler_result.items() if k != 'success'}
            if not response.data:
                response.data = None # Ensure data is None if empty, not {}

        try:
            action_suffix = action.action_type.split('.', 1)[1]
            callback_queue = f"{self.domain}:responses:{action_suffix}:{action.correlation_id}"
        except IndexError:
            logger.error(f"Could not determine action_suffix for action_type: {action.action_type}. Cannot send response.")
            callback_queue = None

        if callback_queue:
            await self.redis_client.rpush(callback_queue, response.json())
            logger.info(f"Sent pseudo-sync response for {action.action_type} to {callback_queue}")
        else:
            logger.warning(f"No callback_queue could be determined for pseudo-sync action {action.action_type}, response not sent.")

    async def _send_pseudo_sync_error_response(self, action: DomainAction, error_message: str, error_code: Optional[str] = None):
        error_response = DomainActionResponse(
            success=False,
            correlation_id=action.correlation_id,
            trace_id=action.trace_id,
            action_type_response_to=action.action_type,
            error=ErrorDetail(message=error_message, code=error_code)
        )

        try:
            action_suffix = action.action_type.split('.', 1)[1]
            callback_queue = f"{self.domain}:responses:{action_suffix}:{action.correlation_id}"
        except IndexError:
            logger.error(f"Could not determine action_suffix for action_type: {action.action_type}. Cannot send error response.")
            callback_queue = None

        if callback_queue:
            await self.redis_client.rpush(callback_queue, error_response.json())
            logger.info(f"Sent pseudo-sync error response for {action.action_type} to {callback_queue}")
        else:
            logger.warning(f"No callback_queue could be determined for pseudo-sync error action {action.action_type}, error response not sent.")
        
    async def _handle_action(self, action: DomainAction, context: Optional[ExecutionContext] = None) -> Optional[Dict[str, Any]]:
        """
        Implementa el método abstracto de BaseWorker para manejar acciones específicas
        del dominio de conversation.
        """
        action_type = action.action_type
        
        PSEUDO_SYNC_ACTIONS = ["conversation.get_context", "conversation.get_history", "conversation.save_message"]

        try:
            handler_result = None
            if action_type == "conversation.save_message":
                handler_result = await self.conversation_handler.handle_save_message(action, context)
            elif action_type == "conversation.get_context":
                handler_result = await self.conversation_handler.handle_get_context(action, context)
            elif action_type == "conversation.get_history":
                handler_result = await self.conversation_handler.handle_get_history(action, context)
            elif action_type == "conversation.session_closed":
                # Fire-and-forget, no pseudo-sync response needed. Return result for potential async callback.
                return await self.conversation_handler.handle_session_closed(action, context)
            else:
                error_msg = f"No hay handler implementado para la acción: {action_type}"
                logger.warning(error_msg)
                # If a client seems to be waiting for a response to an unhandled action, send an error.
                if action.callback_queue_name:
                    await self._send_pseudo_sync_error_response(action, error_msg, "UNHANDLED_ACTION")
                return None # Drop unhandled actions

            # For all pseudo-sync actions that were handled, send response and stop processing.
            if handler_result:
                await self._send_pseudo_sync_response(action, handler_result)
            
            return None

        except Exception as e:
            logger.error(f"Exception in ConversationWorker._handle_action for {action_type}: {str(e)}", exc_info=True)
            # If the failed action was supposed to be pseudo-sync, send an error response back.
            if action_type in PSEUDO_SYNC_ACTIONS:
                await self._send_pseudo_sync_error_response(action, str(e), "HANDLER_EXCEPTION")
                return None # Response sent, prevent BaseWorker's default error callback
            
            # For non-pseudo-sync actions, re-raise for BaseWorker's default error handling.
            raise
    
    def create_action_from_data(self, action_data: Dict[str, Any]) -> DomainAction:
        """
        Crea objeto de acción apropiado según los datos.
        
        Args:
            action_data: Datos de la acción en formato JSON
            
        Returns:
            DomainAction del tipo específico
        """
        action_type = action_data.get("action_type")
        
        if action_type == "conversation.save_message":
            return SaveMessageAction.parse_obj(action_data)
        elif action_type == "conversation.get_context":
            return GetContextAction.parse_obj(action_data)
        elif action_type == "conversation.session_closed":
            return SessionClosedAction.parse_obj(action_data)
        elif action_type == "conversation.get_history":
            return GetHistoryAction.parse_obj(action_data)
        else:
            # Fallback a DomainAction genérica
            return DomainAction.parse_obj(action_data)
    
    async def _send_callback(self, action: DomainAction, result: Dict[str, Any]):
        """
        Envía resultado como callback.
        
        Args:
            action: Acción original que generó el resultado
            result: Resultado del procesamiento
        """
        if action.callback_queue and result.get("success"):
            callback_action = DomainAction(
                action_type=f"{action.get_action_name()}_callback",
                task_id=action.task_id,
                tenant_id=action.tenant_id,
                tenant_tier=action.tenant_tier,
                session_id=action.session_id,
                data=result
            )
            await self.queue_manager.enqueue_to_specific_queue(
                callback_action, action.callback_queue
            )
            
    async def _send_error_callback(self, action_data: Dict[str, Any], error_message: str):
        """
        Envía callback de error.
        
        Args:
            action_data: Datos originales de la acción
            error_message: Mensaje de error
        """
        callback_queue = action_data.get("callback_queue")
        if callback_queue:
            error_action = DomainAction(
                action_type="conversation.error",
                task_id=action_data.get("task_id"),
                tenant_id=action_data.get("tenant_id"),
                tenant_tier=action_data.get("tenant_tier"),
                session_id=action_data.get("session_id"),
                data={"error": error_message}
            )
            await self.enqueue_callback(error_action, callback_queue)
    
    # Método auxiliar para estadísticas específicas del conversation service
    async def get_conversation_stats(self) -> Dict[str, Any]:
        """Obtiene estadísticas específicas del conversation service."""
        # Obtener estadísticas básicas del worker
        stats = await self.get_worker_stats()
        
        if not self.initialized:
            stats["worker_info"]["status"] = "not_initialized"
            return stats
            
        try:
            # Stats de colas
            queue_stats = await self.get_queue_stats()
            stats["queue_stats"] = queue_stats
            
            # Stats de conversación si el servicio tiene método para ello
            if self.conversation_service and hasattr(self.conversation_service, 'get_stats'):
                conversation_stats = await self.conversation_service.get_stats()
                stats["conversation_stats"] = conversation_stats
        
        except Exception as e:
            logger.error(f"Error obteniendo estadísticas: {str(e)}")
            stats["error"] = str(e)
        
        return stats
