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
from common.models.actions import DomainAction
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
        
    async def _handle_action(self, action: DomainAction, context: Optional[ExecutionContext] = None) -> Dict[str, Any]:
        """
        Implementa el método abstracto de BaseWorker para manejar acciones específicas
        del dominio de conversation.
        
        Args:
            action: La acción a procesar
            context: Contexto opcional de ejecución
            
        Returns:
            Diccionario con el resultado del procesamiento
            
        Raises:
            ValueError: Si no hay handler implementado para ese tipo de acción
        """
        action_type = action.action_type
        
        if action_type == "conversation.save_message":
            return await self.conversation_handler.handle_save_message(action, context)
        elif action_type == "conversation.get_context":
            return await self.conversation_handler.handle_get_context(action, context)
        elif action_type == "conversation.session_closed":
            return await self.conversation_handler.handle_session_closed(action, context)
        elif action_type == "conversation.get_history":
            result = await self.conversation_handler.handle_get_history(action, context)
            # Para acciones con correlation_id, enviar la respuesta a una cola específica
            if hasattr(action, 'correlation_id') and action.correlation_id:
                await self._send_sync_response(action.correlation_id, result)
            return result
        else:
            error_msg = f"No hay handler implementado para la acción: {action_type}"
            logger.warning(error_msg)
            raise ValueError(error_msg)
    
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
            
    async def _send_sync_response(self, correlation_id: str, result: Dict[str, Any]):
        """
        Envía una respuesta síncrona a través de Redis para el patrón pseudo-síncrono.
        
        Esta función es clave para implementar el patrón de request-response sobre Redis.
        El cliente que espera esta respuesta está bloqueando en la cola específica de
        respuestas con este correlation_id.
        
        Args:
            correlation_id: ID único que correlaciona solicitud y respuesta
            result: Resultado a enviar como respuesta
        """
        try:
            # Crear clave única para la cola de respuestas
            response_queue = f"conversation:responses:{correlation_id}"
            
            # Serializar resultado
            serialized_result = json.dumps(result)
            
            # Almacenar en Redis con TTL de 60 segundos (por si el cliente no lo recoge)
            await self.redis_client.lpush(response_queue, serialized_result)
            await self.redis_client.expire(response_queue, 60)  # TTL de 60 segundos
            
            logger.info(f"Respuesta enviada a cola {response_queue} con correlation_id {correlation_id}")
        except Exception as e:
            logger.error(f"Error enviando respuesta síncrona: {str(e)}")
    
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
