"""
ActionProcessor: Procesador centralizado de Domain Actions.

Este componente se encarga de procesar acciones del dominio y 
manejar su ejecución asíncrona a través de handlers registrados.
"""

import logging
import json
from typing import Dict, Any, Callable, Coroutine, Optional, List
import time
from datetime import datetime

from common.models.actions import DomainAction
from common.redis_pool import get_redis_client
from common.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

class ActionProcessor:
    """
    Procesador centralizado de acciones.
    
    Permite registrar handlers para cada tipo de acción y
    encolar/procesar acciones de forma consistente.
    """
    
    def __init__(self, redis_client=None):
        """
        Inicializa el procesador.
        
        Args:
            redis_client: Cliente Redis para encolado (opcional)
        """
        self.redis_client = redis_client or get_redis_client(settings.redis_url)
        self.handlers = {}
        
    def register_handler(self, action_type: str, handler_func: Callable):
        """
        Registra un handler para un tipo de acción específico.
        
        Args:
            action_type: Tipo de acción en formato "dominio.accion"
            handler_func: Función asíncrona que procesa la acción
        """
        self.handlers[action_type] = handler_func
        logger.info(f"Handler registrado para: {action_type}")
    
    async def process(self, action: DomainAction) -> Dict[str, Any]:
        """
        Procesa una acción usando el handler correspondiente.
        
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
    
    async def enqueue_action(self, action: DomainAction, queue: Optional[str] = None) -> bool:
        """
        Encola una acción para procesamiento asíncrono.
        
        Args:
            action: Acción a encolar
            queue: Cola específica (opcional, por defecto se usa el dominio)
            
        Returns:
            True si se encoló correctamente
        """
        try:
            queue_name = queue or self._get_queue_name(action)
            
            # Convertir acción a formato JSON
            action_data = action.dict()
            
            # Encolar
            await self.redis_client.lpush(queue_name, json.dumps(action_data))
            logger.info(f"Acción encolada en {queue_name}: {action.action_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error encolando acción: {str(e)}")
            return False
    
    def _get_queue_name(self, action: DomainAction) -> str:
        """
        Genera nombre de cola estándar basado en dominio.
        
        Args:
            action: Acción
            
        Returns:
            Nombre de cola estándar
        """
        domain = action.get_domain()
        return f"{domain}.{action.tenant_id}.actions"
