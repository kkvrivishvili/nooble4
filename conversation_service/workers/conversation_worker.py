"""
Worker principal para Domain Actions.
"""

import logging
from typing import Dict, Any

from common.workers.base_worker import BaseWorker
from common.models.actions import DomainAction
from common.services.action_processor import ActionProcessor
from conversation_service.models.actions_model import (
    SaveMessageAction, GetContextAction, SessionClosedAction
)
from conversation_service.handlers.conversation_handler import ConversationHandler
from conversation_service.services.conversation_service import ConversationService
from conversation_service.config.settings import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

class ConversationWorker(BaseWorker):
    """Worker principal para Domain Actions de conversaciones."""
    
    def __init__(self, redis_client=None, action_processor=None, db_client=None):
        action_processor = action_processor or ActionProcessor(redis_client)
        super().__init__(redis_client, action_processor)
        
        self.domain = settings.domain_name
        
        # Inicializar servicios
        conversation_service = ConversationService(redis_client, db_client)
        conversation_handler = ConversationHandler(conversation_service)
        
        # Registrar handlers
        self.action_processor.register_handler(
            "conversation.save_message",
            conversation_handler.handle_save_message
        )
        
        self.action_processor.register_handler(
            "conversation.get_context", 
            conversation_handler.handle_get_context
        )
        
        self.action_processor.register_handler(
            "conversation.session_closed",
            conversation_handler.handle_session_closed
        )
    
    def create_action_from_data(self, action_data: Dict[str, Any]) -> DomainAction:
        action_type = action_data.get("action_type")
        
        if action_type == "conversation.save_message":
            return SaveMessageAction.parse_obj(action_data)
        elif action_type == "conversation.get_context":
            return GetContextAction.parse_obj(action_data)
        elif action_type == "conversation.session_closed":
            return SessionClosedAction.parse_obj(action_data)
        else:
            return DomainAction.parse_obj(action_data)
    
    async def _send_callback(self, action: DomainAction, result: Dict[str, Any]):
        if action.callback_queue and result.get("success"):
            callback_action = DomainAction(
                action_type=f"{action.get_action_name()}_callback",
                task_id=action.task_id,
                tenant_id=action.tenant_id,
                tenant_tier=action.tenant_tier,
                session_id=action.session_id,
                data=result
            )
            await self.enqueue_callback(callback_action, action.callback_queue)
    
    async def _send_error_callback(self, action_data: Dict[str, Any], error_message: str):
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

