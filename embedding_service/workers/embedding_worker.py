"""
Worker para Domain Actions en Embedding Service.

Implementación estandarizada con inicialización asíncrona y
manejo robusto de acciones de generación de embeddings siguiendo
el patrón BaseWorker 4.0 con procesamiento directo de acciones.

VERSIÓN: 4.0 - Actualizado al patrón BaseWorker con _handle_action
"""

import logging
import json
from typing import Dict, Any, List, Optional

from common.workers.base_worker import BaseWorker
from common.models.actions import DomainAction
from common.models.execution_context import ExecutionContext
from common.services.domain_queue_manager import DomainQueueManager
from embedding_service.models.actions import EmbeddingGenerateAction, EmbeddingValidateAction, EmbeddingCallbackAction
from embedding_service.services.generation_service import GenerationService
from embedding_service.handlers.context_handler import get_embedding_context_handler
from embedding_service.handlers.embedding_callback_handler import EmbeddingCallbackHandler
from embedding_service.config.settings import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

class EmbeddingWorker(BaseWorker):
    """
    Worker para procesar Domain Actions de embeddings siguiendo el patrón BaseWorker 4.0.
    
    Características:
    - Implementa completamente el patrón BaseWorker 4.0 con _handle_action
    - Inicialización asíncrona robusta
    - Procesamiento de embeddings por tier
    - Manejo detallado de callbacks
    - Estadísticas avanzadas
    - Sin registro de handlers obsoleto
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
        self.domain = settings.domain_name  # "embedding"
        
        # Handlers que se inicializarán de forma asíncrona
        self.context_handler = None
        self.embedding_callback_handler = None
        self.generation_service = None
        self.initialized = False
    
    async def initialize(self):
        """Inicializa el worker de forma asíncrona."""
        if self.initialized:
            return
            
        # Inicializar handlers necesarios sin registrarlos
        await self._initialize_components()
        
        self.initialized = True
        logger.info("EmbeddingWorker 4.0 inicializado correctamente")
    
    async def start(self):
        """Extiende el start para asegurar inicialización."""
        # Asegurar inicialización antes de procesar acciones
        await self.initialize()
        
        # Continuar con el comportamiento normal del BaseWorker
        await super().start()
        
    async def _initialize_components(self):
        """Inicializa todos los componentes necesarios sin registrar handlers."""
        # Context handler
        self.context_handler = await get_embedding_context_handler(self.redis_client)
        
        # Embedding callback handler
        self.embedding_callback_handler = EmbeddingCallbackHandler(
            self.queue_manager, self.redis_client
        )
        
        # Servicio de generación principal
        self.generation_service = GenerationService(
            self.context_handler, self.redis_client
        )
        
        # Ya no registramos handlers en el queue_manager - todo se procesa vía _handle_action
        
        logger.info("EmbeddingWorker: Componentes inicializados")
    
    async def _handle_action(self, action: DomainAction, context: Optional[ExecutionContext] = None) -> Dict[str, Any]:
        """
        Procesa acciones de dominio centralizadamente siguiendo el patrón BaseWorker 4.0.
        
        Este método reemplaza el registro de handlers y centraliza todo el procesamiento
        de acciones, mejorando la coherencia arquitectónica.
        
        Args:
            action: Acción de dominio a procesar
            context: Contexto de ejecución opcional
            
        Returns:
            Resultado del procesamiento de la acción
            
        Raises:
            ValueError: Si la acción no está soportada
        """
        if not self.initialized:
            await self.initialize()
            
        action_type = action.action_type
        
        try:
            if action_type == "embedding.generate" or action_type == "embedding.generate.sync":
                return await self.generation_service.generate_embeddings(action)

            elif action_type == "embedding.validate":
                return await self.generation_service.validate_embeddings(action)
                
            elif action_type == "embedding.callback":
                return await self._handle_embedding_callback(action, context)
                
            else:
                error_msg = f"No hay handler implementado para la acción: {action_type}"
                logger.warning(error_msg)
                raise ValueError(error_msg)
                
        except Exception as e:
            logger.error(f"Error procesando acción {action_type}: {str(e)}")
            return {
                "success": False,
                "error": str(e)
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
        Envía resultado como callback con contexto de ejecución.
        
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
                tenant_tier=getattr(action, 'tenant_tier', None),
                session_id=action.session_id
            )
            
            logger.info(f"Preparando callback con contexto. Tier: {context.tenant_tier}")
            
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
                    processing_time=result.get("execution_time", 0.0),
                    context=context
                )
            else:
                # Callback de error
                await self.embedding_callback_handler.send_error_callback(
                    task_id=action.task_id,
                    tenant_id=action.tenant_id,
                    session_id=action.session_id,
                    callback_queue=action.callback_queue,
                    error_info=result.get("error", {}),
                    processing_time=result.get("execution_time"),
                    context=context
                )
            
        except Exception as e:
            logger.error(f"Error enviando callback: {str(e)}")
    
    async def _send_error_callback(self, action_data: Dict[str, Any], error_message: str):
        """
        Envía callback de error con contexto de ejecución.
        
        Args:
            action_data: Datos originales de la acción
            error_message: Mensaje de error
        """
        try:
            # Extraer información necesaria
            task_id = action_data.get("task_id") or action_data.get("action_id")
            tenant_id = action_data.get("tenant_id", "unknown")
            session_id = action_data.get("session_id", "unknown")
            tenant_tier = action_data.get("tenant_tier")
            callback_queue = action_data.get("callback_queue")
            
            if not callback_queue or not task_id:
                logger.warning("Información insuficiente para enviar error callback")
                return
                
            # Crear contexto de ejecución
            context = ExecutionContext(
                tenant_id=tenant_id,
                tenant_tier=tenant_tier,
                session_id=session_id
            )
            
            # Enviar error callback
            await self.embedding_callback_handler.send_error_callback(
                task_id=task_id,
                tenant_id=tenant_id,
                session_id=session_id,
                callback_queue=callback_queue,
                error_info={
                    "type": "ProcessingError",
                    "message": error_message
                },
                context=context
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
            if self.generation_service and hasattr(self.generation_service, 'get_embedding_stats'):
                embedding_stats = await self.generation_service.get_embedding_stats("all")
                stats["embedding_stats"] = embedding_stats
            
            # Stats de callbacks
            if self.embedding_callback_handler and hasattr(self.embedding_callback_handler, 'get_callback_stats'):
                callback_stats = await self.embedding_callback_handler.get_callback_stats("all")
                stats["callback_stats"] = callback_stats
                
        except Exception as e:
            logger.error(f"Error obteniendo estadísticas: {str(e)}")
            stats["error"] = str(e)
        
        return stats
        

