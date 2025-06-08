"""
Worker mejorado para Domain Actions en Embedding Service.

Implementación estandarizada con inicialización asíncrona y
manejo robusto de acciones de generación de embeddings.

VERSIÓN: 2.0 - Adaptado al patrón improved_base_worker
"""

import logging
from typing import Dict, Any, List

from common.workers.base_worker import BaseWorker
from common.models.actions import DomainAction
from common.services.action_processor import ActionProcessor
from embedding_service.models.actions import EmbeddingGenerateAction, EmbeddingValidateAction, EmbeddingCallbackAction
from embedding_service.handlers.embedding_handler import EmbeddingHandler
from embedding_service.handlers.context_handler import get_embedding_context_handler
from embedding_service.handlers.embedding_callback_handler import EmbeddingCallbackHandler
from embedding_service.config.settings import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

class EmbeddingWorker(BaseWorker):
    """
    Worker mejorado para procesar Domain Actions de embeddings.
    
    Características:
    - Inicialización asíncrona robusta
    - Procesamiento de embeddings por tier
    - Manejo detallado de callbacks
    - Estadísticas avanzadas
    """
    
    def __init__(self, redis_client, action_processor=None):
        """
        Inicializa worker con servicios necesarios.
        
        Args:
            redis_client: Cliente Redis configurado (requerido)
            action_processor: Procesador de acciones (opcional)
        """
        action_processor = action_processor or ActionProcessor(redis_client)
        super().__init__(redis_client, action_processor)
        
        # Definir domain específico
        self.domain = settings.domain_name  # "embedding"
        
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
        logger.info("ImprovedEmbeddingWorker inicializado correctamente")
    
    async def start(self):
        """Extiende el start para asegurar inicialización."""
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
        
        logger.info("EmbeddingWorker: Handlers inicializados")
    
    async def _handle_embedding_generate(self, action: DomainAction) -> Dict[str, Any]:
        """
        Handler específico para generación de embeddings.
        
        Args:
            action: Acción de embedding
            
        Returns:
            Resultado del procesamiento
        """
        try:
            # Verificar inicialización
            if not self.initialized:
                await self.initialize()
                
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
            # Verificar inicialización
            if not self.initialized:
                await self.initialize()
                
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
    
    # Método auxiliar para estadísticas específicas
    async def get_embedding_stats(self) -> Dict[str, Any]:
        """
        Obtiene estadísticas específicas del embedding service.
        
        Returns:
            Dict con estadísticas completas
        """
        # Obtener estadísticas básicas del worker
        stats = await self.get_worker_stats()
        
        if not self.initialized:
            stats["worker_info"]["status"] = "not_initialized"
            return stats
        
        try:
            # Stats de embeddings
            if self.embedding_handler and hasattr(self.embedding_handler, 'get_embedding_stats'):
                embedding_stats = await self.embedding_handler.get_embedding_stats("all")
                stats["embedding_stats"] = embedding_stats
            
            # Stats de callbacks
            if self.embedding_callback_handler and hasattr(self.embedding_callback_handler, 'get_callback_stats'):
                callback_stats = await self.embedding_callback_handler.get_callback_stats("all")
                stats["callback_stats"] = callback_stats
                
        except Exception as e:
            logger.error(f"Error obteniendo estadísticas: {str(e)}")
            stats["error"] = str(e)
        
        return stats
