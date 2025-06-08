"""
Worker para Domain Actions en Embedding Service.

MODIFICADO: Integración completa con sistema de colas por tier.
"""

import logging
from typing import Dict, Any, List

from common.workers.base_worker import BaseWorker
from common.models.actions import DomainAction
from common.redis_pool import get_redis_client
from common.services.action_processor import ActionProcessor
from common.services.domain_queue_manager import DomainQueueManager
from embedding_service.models.actions import EmbeddingGenerateAction, EmbeddingValidateAction, EmbeddingCallbackAction
from embedding_service.handlers.embedding_handler import EmbeddingHandler
from embedding_service.handlers.context_handler import get_embedding_context_handler
from embedding_service.handlers.embedding_callback_handler import EmbeddingCallbackHandler
from embedding_service.config.settings import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

class EmbeddingWorker(BaseWorker):
    """
    Worker para procesar Domain Actions de embeddings.
    
    MODIFICADO: 
    - Define domain específico
    - Procesa embeddings por tier
    - Integra con callback handlers
    """
    
    def __init__(self, redis_client=None, action_processor=None):
        """
        Inicializa worker con servicios necesarios.
        """
        # Usar valores por defecto si no se proporcionan
        self.redis_client = redis_client or get_redis_client()
        action_processor = action_processor or ActionProcessor(self.redis_client)
        
        super().__init__(self.redis_client, action_processor)
        
        # NUEVO: Definir domain específico
        self.domain = settings.domain_name  # "embedding"
        
        # Inicializar queue manager
        self.queue_manager = DomainQueueManager(self.redis_client)
        
        # Handlers que se inicializarán de forma asíncrona
        self.context_handler = None
        self.embedding_callback_handler = None
        self.embedding_handler = None
        self.initialized = False
    
    async def initialize(self):
        """Inicializa el worker de forma asíncrona."""
        if self.initialized:
            return
            
        await self._initialize_handlers()
        self.initialized = True
        logger.info("EmbeddingWorker inicializado correctamente")
        
    async def start(self):
        """
        Extiende el start de BaseWorker para asegurar inicialización asincrónica.
        """
        # Asegurar inicialización antes de procesar acciones
        await self.initialize()
        
        # Continuar con el comportamiento normal del BaseWorker
        await super().start()
        
    async def _initialize_handlers(self):
        """Inicializa todos los handlers necesarios."""
        # Context handler
        self.context_handler = await get_embedding_context_handler(self.redis_client)
        
        # Embedding callback handler
        self.embedding_callback_handler = EmbeddingCallbackHandler(
            self.queue_manager, self.redis_client
        )
        
        # Embedding handler principal
        self.embedding_handler = EmbeddingHandler(
            self.context_handler, self.redis_client
        )
        
        # Registrar handlers en el action_processor
        self.action_processor.register_handler(
            "embedding.generate",
            self._handle_embedding_generate
        )
        
        self.action_processor.register_handler(
            "embedding.validate",
            self._handle_embedding_validate
        )
    
    async def _handle_embedding_generate(self, action: DomainAction) -> Dict[str, Any]:
        """
        Handler específico para generación de embeddings.
        
        Args:
            action: Acción de embedding
            
        Returns:
            Resultado del procesamiento
        """
        try:
            # Convertir a tipo específico
            embedding_action = EmbeddingGenerateAction.parse_obj(action.dict())
            
            # Procesar embedding
            result = await self.embedding_handler.handle_generate(embedding_action)
            
            return result
            
        except Exception as e:
            logger.error(f"Error en handle_embedding_generate: {str(e)}")
            return {
                "success": False,
                "error": {
                    "type": type(e).__name__,
                    "message": str(e)
                }
            }
    
    async def _handle_embedding_validate(self, action: DomainAction) -> Dict[str, Any]:
        """
        Handler específico para validación de embeddings.
        
        Args:
            action: Acción de validación
            
        Returns:
            Resultado del procesamiento
        """
        try:
            # Convertir a tipo específico
            validate_action = EmbeddingValidateAction.parse_obj(action.dict())
            
            # Procesar validación
            result = await self.embedding_handler.handle_validate(validate_action)
            
            return result
            
        except Exception as e:
            logger.error(f"Error en handle_embedding_validate: {str(e)}")
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
        
        if action_type == "embedding.generate":
            return EmbeddingGenerateAction.parse_obj(action_data)
        elif action_type == "embedding.validate":
            return EmbeddingValidateAction.parse_obj(action_data)
        elif action_type == "embedding.callback":
            return EmbeddingCallbackAction.parse_obj(action_data)
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
        try:
            # Validar que haya cola de callback
            if not action.callback_queue:
                logger.warning(f"No se especificó cola de callback para {action.task_id}")
                return
            
            # Determinar tipo de callback según resultado
            if result.get("success", False) and "result" in result:
                # Callback de embedding exitoso
                await self.embedding_callback_handler.send_success_callback(
                    task_id=action.task_id,
                    tenant_id=action.tenant_id,
                    session_id=action.session_id,
                    callback_queue=action.callback_queue,
                    embeddings=result["result"]["embeddings"],
                    model=result["result"]["model"],
                    dimensions=result["result"]["dimensions"],
                    total_tokens=result["result"]["total_tokens"],
                    processing_time=result.get("execution_time", 0.0)
                )
            else:
                # Callback de error
                await self.embedding_callback_handler.send_error_callback(
                    task_id=action.task_id,
                    tenant_id=action.tenant_id,
                    session_id=action.session_id,
                    callback_queue=action.callback_queue,
                    error_info=result.get("error", {}),
                    processing_time=result.get("execution_time")
                )
            
        except Exception as e:
            logger.error(f"Error enviando callback: {str(e)}")
    
    async def _send_error_callback(self, action_data: Dict[str, Any], error_message: str):
        """
        Envía callback de error.
        
        Args:
            action_data: Datos originales de la acción
            error_message: Mensaje de error
        """
        try:
            # Extraer información necesaria
            task_id = action_data.get("task_id") or action_data.get("action_id")
            tenant_id = action_data.get("tenant_id", "unknown")
            session_id = action_data.get("session_id", "unknown")
            callback_queue = action_data.get("callback_queue")
            
            if not callback_queue or not task_id:
                logger.warning("Información insuficiente para enviar error callback")
                return
            
            # Enviar error callback
            await self.embedding_callback_handler.send_error_callback(
                task_id=task_id,
                tenant_id=tenant_id,
                session_id=session_id,
                callback_queue=callback_queue,
                error_info={
                    "type": "ProcessingError",
                    "message": error_message
                }
            )
            
        except Exception as e:
            logger.error(f"Error enviando error callback: {str(e)}")
    
    # NUEVO: Métodos auxiliares específicos del embedding service
    async def get_embedding_stats(self) -> Dict[str, Any]:
        """Obtiene estadísticas específicas del embedding service."""
        
        # Stats de colas
        queue_stats = await self.get_queue_stats()
        
        # Stats de embeddings
        embedding_stats = await self.embedding_handler.get_embedding_stats("all")
        
        # Stats de callbacks
        callback_stats = await self.embedding_callback_handler.get_callback_stats("all")
        
        return {
            "queue_stats": queue_stats,
            "embedding_stats": embedding_stats,
            "callback_stats": callback_stats,
            "worker_info": {
                "domain": self.domain,
                "running": self.running
            }
        }