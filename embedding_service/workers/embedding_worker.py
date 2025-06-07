"""
Worker para procesar acciones de embedding.

# TODO: Oportunidades de mejora futura:
# 1. Estandarizar la forma de convertir entre DomainAction y modelos específicos
# 2. Implementar manejo consistente de errores con clases específicas
# 3. Unificar lógica de envío de callbacks usando un método más genérico
# 4. Considerar base_worker.py para extraer funcionalidad común
Este worker extiende el BaseWorker para procesar acciones
específicas de generación de embeddings usando el sistema de Domain Actions.
"""

import logging
from typing import Dict, Any, List

from common.workers.base_worker import BaseWorker
from common.models.actions import DomainAction
from embedding_service.models.actions import EmbeddingGenerateAction, EmbeddingValidateAction, EmbeddingCallbackAction
from embedding_service.handlers.embedding_handler import EmbeddingHandler
from embedding_service.config.settings import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class EmbeddingWorker(BaseWorker):
    """
    Worker para procesar Domain Actions de embeddings.
    
    Procesa acciones del tipo embedding.generate y embedding.validate
    y envía resultados como callbacks estructurados.
    """
    
    def __init__(self, redis_client=None, action_processor=None):
        """
        Inicializa el worker con servicios necesarios.
        
        Args:
            redis_client: Cliente Redis para acceso a colas (opcional)
            action_processor: Procesador centralizado de acciones (opcional)
        """
        from common.redis_pool import get_redis_client
        from common.services.action_processor import ActionProcessor
        
        # Usar valores por defecto si no se proporcionan
        redis_client = redis_client or get_redis_client(settings.redis_url)
        action_processor = action_processor or ActionProcessor(redis_client)
        
        super().__init__(redis_client, action_processor)
        
        # Inicializar handler
        self.embedding_handler = EmbeddingHandler()
        
        # Registrar handlers en el action_processor
        self.action_processor.register_handler(
            "embedding.generate", 
            self.embedding_handler.handle_generate
        )
        self.action_processor.register_handler(
            "embedding.validate",
            self.embedding_handler.handle_validate
        )
    
    def get_queue_names(self) -> List[str]:
        """
        Retorna nombres de colas a monitorear.
        
        Returns:
            Lista de patrones de colas
        """
        return ["embedding.*.actions"]
    
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
            return EmbeddingGenerateAction(**action_data)
        elif action_type == "embedding.validate":
            return EmbeddingValidateAction(**action_data)
        else:
            # Fallback a DomainAction genérica
            return DomainAction(**action_data)
    
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
                logger.warning(f"No se especificó cola de callback para {action.action_id}")
                return
            
            # Crear acción de callback
            if result.get("success", False):
                # Para acciones exitosas de generación de embeddings
                if action.action_type == "embedding.generate":
                    callback = EmbeddingCallbackAction(
                        tenant_id=action.tenant_id,
                        session_id=action.session_id,
                        task_id=action.task_id or action.action_id,
                        status="completed",
                        embeddings=result.get("embeddings", []),
                        model=result.get("model", ""),
                        dimensions=result.get("dimensions", 0),
                        total_tokens=result.get("total_tokens", 0),
                        processing_time=result.get("processing_time", 0.0)
                    )
                # Para acciones de validación u otras
                else:
                    callback = DomainAction(
                        action_type=f"{action.action_type}.callback",
                        tenant_id=action.tenant_id,
                        session_id=action.session_id,
                        task_id=action.task_id or action.action_id,
                        status="completed",
                        result=result
                    )
            else:
                # Para acciones fallidas
                callback = DomainAction(
                    action_type=f"{action.action_type}.callback",
                    tenant_id=action.tenant_id,
                    session_id=action.session_id,
                    task_id=action.task_id or action.action_id,
                    status="failed",
                    result={
                        "error": result.get("error", {"type": "UnknownError", "message": "Error desconocido"})
                    }
                )
            
            # Enviar a cola de callback
            await self.action_processor.enqueue_action(callback, action.callback_queue)
            logger.info(f"Callback enviado: {action.callback_queue}")
            
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
            tenant_id = action_data.get("tenant_id", "default")
            callback_queue = action_data.get("callback_queue")
            task_id = action_data.get("task_id") or action_data.get("action_id")
            session_id = action_data.get("session_id")
            action_type = action_data.get("action_type", "unknown")
            
            if not callback_queue or not task_id:
                logger.warning("Información insuficiente para enviar error callback")
                return
            
            # Crear acción de callback de error
            callback = DomainAction(
                action_type=f"{action_type}.callback",
                tenant_id=tenant_id,
                session_id=session_id,
                task_id=task_id,
                status="failed",
                result={
                    "error": {
                        "type": "ProcessingError",
                        "message": error_message
                    }
                }
            )
            
            # Enviar a cola de callback
            await self.action_processor.enqueue_action(callback, callback_queue)
            
        except Exception as e:
            logger.error(f"Error enviando error callback: {str(e)}")
