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
from embedding_service.handlers.embedding_handler import EmbeddingHandler
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
        self.embedding_handler = None
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
        
        # Embedding handler principal
        self.embedding_handler = EmbeddingHandler(
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
            if action_type == "embedding.generate":
                return await self._handle_embedding_generate(action, context)
                
            elif action_type == "embedding.generate.sync":
                return await self._handle_embedding_generate_sync(action, context)
                
            elif action_type == "embedding.validate":
                return await self._handle_embedding_validate(action, context)
                
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
    
    async def _handle_embedding_generate(self, action: DomainAction, context: ExecutionContext = None) -> Dict[str, Any]:
        """
        Handler específico para generación de embeddings.
        
        Args:
            action: Acción de embedding
            context: Contexto de ejecución opcional con metadatos
            
        Returns:
            Resultado del procesamiento
        """
        try:
            # Verificar inicialización
            if not self.initialized:
                await self.initialize()
                
            # Convertir a tipo específico
            embedding_action = EmbeddingGenerateAction.parse_obj(action.dict())
            
            # Enriquecer con datos de contexto si está disponible
            if context:
                logger.info(f"Generando embeddings con tier: {context.tenant_tier}")
                embedding_action.tenant_tier = context.tenant_tier
            
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
    
    async def _handle_embedding_validate(self, action: DomainAction, context: ExecutionContext = None) -> Dict[str, Any]:
        """
        Handler específico para validación de embeddings.
        
        Args:
            action: Acción de validación
            context: Contexto de ejecución opcional con metadatos
            
        Returns:
            Resultado del procesamiento
        """
        try:
            # Verificar inicialización
            if not self.initialized:
                await self.initialize()
                
            # Convertir a tipo específico
            validate_action = EmbeddingValidateAction.parse_obj(action.dict())
            
            # Enriquecer con datos de contexto si está disponible
            if context:
                logger.info(f"Validando embeddings con tier: {context.tenant_tier}")
                validate_action.tenant_tier = context.tenant_tier
            
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
        
    async def _handle_embedding_generate_sync(self, action: DomainAction, context: ExecutionContext = None) -> Dict[str, Any]:
        """
        Handler específico para generación de embeddings con patrón pseudo-síncrono.
        
        A diferencia del método asíncrono normal, este método responde directamente
        a una cola temporal específica con el correlation_id proporcionado en la acción.
        
        Args:
            action: Acción de embedding con correlation_id
            context: Contexto de ejecución opcional con metadatos
            
        Returns:
            Resultado del procesamiento con los embeddings generados
        """
        try:
            # Verificar inicialización
            if not self.initialized:
                await self.initialize()
                
            # Convertir a tipo específico
            generate_action = EmbeddingGenerateAction.parse_obj(action.dict())
            
            # Extraer correlation_id de los datos
            correlation_id = generate_action.data.get('correlation_id')
            if not correlation_id:
                raise ValueError("Se requiere correlation_id para acciones sync")
                
            # Generar cola de respuesta basada en correlation_id
            response_queue = f"embedding:responses:generate:{correlation_id}"
                
            # Enriquecer con datos de contexto si está disponible
            if context:
                logger.info(f"Procesando generación sync con tier: {context.tenant_tier}")
                generate_action.tenant_tier = context.tenant_tier
            
            # Procesar generación de embeddings
            result = await self.embedding_handler.handle_embedding_generate(generate_action)
            
            # Publicar resultado directamente en la cola de respuesta
            if result.get("success", False):
                await self.redis_client.rpush(
                    response_queue,
                    json.dumps({
                        "success": True,
                        "embeddings": result.get("embeddings", []),
                        "metadata": result.get("metadata", {})
                    })
                )
                # Establecer tiempo de expiración para la cola temporal
                await self.redis_client.expire(response_queue, 300)  # 5 minutos
            else:
                await self.redis_client.rpush(
                    response_queue,
                    json.dumps({
                        "success": False,
                        "error": result.get("error", "Error desconocido")
                    })
                )
                await self.redis_client.expire(response_queue, 300)  # 5 minutos
                
            logger.info(f"Respuesta sync enviada a {response_queue}")
            return result
            
        except Exception as e:
            logger.error(f"Error en handle_embedding_generate_sync: {str(e)}")
            # Intentar enviar error a cola de respuesta si tenemos correlation_id
            correlation_id = action.data.get('correlation_id')
            if correlation_id:
                response_queue = f"embedding:responses:generate:{correlation_id}"
                await self.redis_client.rpush(
                    response_queue,
                    json.dumps({
                        "success": False,
                        "error": str(e)
                    })
                )
                await self.redis_client.expire(response_queue, 300)  # 5 minutos
            
            return {
                "success": False,
                "error": str(e)
            }
