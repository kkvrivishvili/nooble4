"""
[LEGACY] ActionProcessor: Procesador centralizado de Domain Actions.

IMPORTANTE: ESTA CLASE ESTÁ DEPRECADA Y SERÁ REMOVIDA EN FUTURAS VERSIONES.
MIGRAR TODO EL CÓDIGO A 'common.services.domain_queue_manager.DomainQueueManager'.

Este componente se encargaba de procesar acciones del dominio y 
manejar su ejecución asíncrona a través de handlers registrados, pero
ha sido reemplazado por DomainQueueManager para mejorar el sistema de colas por tier.

Véase: common/services/domain_queue_manager.py para la implementación recomendada.
"""

import logging
import json
from typing import Dict, Any, Callable, Coroutine, Optional, List
import time
from datetime import datetime

from common.models.actions import DomainAction
from common.models.execution_context import ExecutionContext
from common.redis_pool import get_redis_client
from common.config import get_service_settings

logger = logging.getLogger(__name__)

class ActionProcessor:
    """
    [LEGACY] Procesador centralizado de acciones.
    
    DEPRECADO: Esta clase será eliminada en futuras versiones.
    Se debe migrar todo el código a usar DomainQueueManager directamente.
    
    Anteriormente permitía registrar handlers para cada tipo de acción y
    encolar/procesar acciones de forma consistente, pero ahora solo actúa
    como wrapper temporal sobre DomainQueueManager durante la migración.
    """
    
    def __init__(self, redis_client=None, queue_manager=None):
        """
        [LEGACY] Inicializa el procesador.
        
        DEPRECADO: Usar DomainQueueManager directamente.
        
        Args:
            redis_client: Cliente Redis para encolado (opcional)
            queue_manager: Gestor de colas por tier (opcional)
        """
        self.redis_client = redis_client or get_redis_client()
        self.handlers = {}
        
        # Integración con queue manager
        if queue_manager:
            self.queue_manager = queue_manager
        else:
            from .domain_queue_manager import DomainQueueManager
            self.queue_manager = DomainQueueManager(self.redis_client)
        
    def register_handler(self, action_type: str, handler_func: Callable):
        """
        [LEGACY] Registra un handler para un tipo de acción específico.
        
        DEPRECADO: Usar DomainQueueManager.register_handler() en su lugar.
        
        Args:
            action_type: Tipo de acción en formato "dominio.accion"
            handler_func: Función asíncrona que procesa la acción
        """
        self.handlers[action_type] = handler_func
        logger.info(f"Handler registrado para: {action_type}")
    
    async def process(self, action: DomainAction) -> Dict[str, Any]:
        """
        [LEGACY] Procesa una acción usando el handler correspondiente.
        
        DEPRECADO: Usar DomainQueueManager y sus handlers directamente.
        
        Args:
            action: Acción a procesar
            
        Returns:
            Diccionario con resultado del procesamiento
        """
        start_time = time.time()
        
        try:
            logger.info(f"Procesando acción: {action.action_type} para tenant: {action.tenant_id}")
            
            # Obtener handler
            handler = self.handlers.get(action.action_type)
            if not handler:
                raise ValueError(f"No hay handler para la acción: {action.action_type}")
            
            # Ejecutar acción
            result = await handler(action)
            
            # Agregar campos estándar al resultado
            if isinstance(result, dict):
                result["action_id"] = action.action_id
                result["execution_time"] = time.time() - start_time
                
            logger.info(f"Acción {action.action_type} completada en {time.time() - start_time:.2f}s")
            return result
            
        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"Error procesando acción {action.action_type}: {str(e)}")
            
            return {
                "success": False,
                "error": {
                    "type": type(e).__name__,
                    "message": str(e)
                },
                "action_id": action.action_id,
                "execution_time": execution_time
            }
    
    # MODIFICADO: Usar DomainQueueManager
    async def enqueue_action(self, action: DomainAction, queue: Optional[str] = None) -> bool:
        """
        Encola una acción para procesamiento asíncrono.
        
        DEPRECATED: Usar queue_manager.enqueue_execution() en su lugar.
        
        Args:
            action: Acción a encolar
            queue: Cola específica (opcional)
            
        Returns:
            True si se encoló correctamente
        """
        logger.warning("enqueue_action() está deprecated. Usar DomainQueueManager.enqueue_execution()")
        
        try:
            queue_name = queue or f"{action.get_domain()}.{action.tenant_id}.actions"
            
            # Convertir acción a formato JSON
            action_data = action.dict()
            
            # Encolar
            await self.redis_client.lpush(queue_name, json.dumps(action_data))
            logger.info(f"Acción encolada en {queue_name}: {action.action_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error encolando acción: {str(e)}")
            return False
    
    # NUEVO: Métodos para integración con DomainQueueManager
    async def enqueue_execution(
        self,
        action: DomainAction,
        target_domain: str,
        context: ExecutionContext
    ) -> str:
        """
        Encola acción usando DomainQueueManager.
        
        Args:
            action: Acción a encolar
            target_domain: Dominio destino
            context: Contexto de ejecución
            
        Returns:
            Nombre de cola donde se encoló
        """
        return await self.queue_manager.enqueue_execution(action, target_domain, context)
    
    async def enqueue_callback(
        self,
        callback_action: DomainAction,
        callback_queue: str
    ) -> bool:
        """
        Encola callback usando DomainQueueManager.
        
        Args:
            callback_action: Acción de callback
            callback_queue: Cola destino
            
        Returns:
            True si se encoló correctamente
        """
        return await self.queue_manager.enqueue_callback(callback_action, callback_queue)
    
    async def get_queue_stats(self, domain: str) -> Dict[str, Any]:
        """
        Obtiene estadísticas de colas para un dominio.
        
        Args:
            domain: Dominio a consultar
            
        Returns:
            Estadísticas por tier
        """
        return await self.queue_manager.get_queue_stats(domain)