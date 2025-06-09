"""
Worker mejorado para Domain Actions en Conversation Service.

Implementación estandarizada con inicialización asíncrona y
manejo robusto de acciones relacionadas con conversaciones.

VERSIÓN: 2.0 - Adaptado al patrón improved_base_worker
"""

import logging
from typing import Dict, Any

from common.workers.base_worker import BaseWorker
from common.models.actions import DomainAction
from common.models.execution_context import ExecutionContext
from common.services.domain_queue_manager import DomainQueueManager
from conversation_service.models.actions_model import (
    SaveMessageAction, GetContextAction, SessionClosedAction
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
            
        await self._initialize_handlers()
        self.initialized = True
        logger.info("ImprovedConversationWorker inicializado correctamente")
    
    async def start(self):
        """Extiende el start para asegurar inicialización."""
        # Asegurar inicialización antes de procesar acciones
        await self.initialize()
        
        # Continuar con el comportamiento normal del BaseWorker
        await super().start()
        
    async def _initialize_handlers(self):
        """Inicializa todos los handlers y servicios necesarios."""
        # Inicializar servicios
        self.conversation_service = ConversationService(self.redis_client, self.db_client)
        self.conversation_handler = ConversationHandler(self.conversation_service)
        
        # Registrar handlers en el queue_manager
        self.queue_manager.register_handler(
            "conversation.save_message",
            self.conversation_handler.handle_save_message
        )
        
        self.queue_manager.register_handler(
            "conversation.get_context", 
            self.conversation_handler.handle_get_context
        )
        
        self.queue_manager.register_handler(
            "conversation.session_closed",
            self.conversation_handler.handle_session_closed
        )
        
        logger.info("ConversationWorker: Handlers inicializados")
    
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
            await self.enqueue_callback(callback_action, action.callback_queue)
    
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
