"""
BaseWorker: Clase base para workers que procesan Domain Actions.

Proporciona una implementación estándar para procesar acciones
de colas Redis con implementación común de ciclo de procesamiento.

MODIFICADO: Integración con sistema de colas por tier.
"""

import asyncio
import json
import logging
from typing import Dict, Any, List, Optional

from common.models.actions import DomainAction
from common.models.execution_context import ExecutionContext
from common.services.action_processor import ActionProcessor
from common.services.domain_queue_manager import DomainQueueManager

logger = logging.getLogger(__name__)

class BaseWorker:
    """
    Worker base para procesar acciones de colas Redis.
    
    Esta clase abstracta define el comportamiento común para workers
    que procesan domain actions desde colas Redis.
    
    MODIFICADO: Usa DomainQueueManager para procesar por prioridad de tier.
    """
    
    def __init__(self, redis_client, action_processor: ActionProcessor):
        """
        Inicializa el worker base.
        
        Args:
            redis_client: Cliente Redis para acceso a colas
            action_processor: Procesador de acciones
        """
        self.redis_client = redis_client
        self.action_processor = action_processor
        self.running = False
        self.sleep_seconds = 1.0
        
        # NUEVO: Integración con DomainQueueManager
        self.queue_manager = DomainQueueManager(redis_client)
        
        # NUEVO: Domain específico (debe ser definido por subclases)
        self.domain = getattr(self, 'domain', 'unknown')
        
    async def start(self):
        """
        Inicia el worker y comienza a procesar colas.
        """
        self.running = True
        logger.info(f"Iniciando {self.__class__.__name__} para dominio {self.domain}")
        
        try:
            await self._process_queue_loop()
        except Exception as e:
            logger.error(f"Error en worker {self.__class__.__name__}: {str(e)}")
        finally:
            self.running = False
    
    async def stop(self):
        """
        Detiene el worker de manera segura.
        """
        self.running = False
        logger.info(f"Deteniendo {self.__class__.__name__}")
    
    # MODIFICADO: Usa DomainQueueManager para procesar por prioridad
    async def _process_queue_loop(self):
        """
        Procesa colas de forma continua mientras el worker esté activo.
        MODIFICADO: Usa queue manager para respetar prioridades por tier.
        """
        while self.running:
            try:
                # NUEVO: Desencolar respetando prioridad de tiers
                action_data = await self.queue_manager.dequeue_with_priority(
                    domain=self.domain,
                    timeout=1
                )
                
                if action_data:
                    # Procesar la acción
                    await self._process_action(action_data)
                else:
                    # Pequeña pausa entre ciclos cuando no hay trabajo
                    await asyncio.sleep(self.sleep_seconds)
                    
            except Exception as e:
                logger.error(f"Error procesando colas: {str(e)}")
                await asyncio.sleep(1)  # Esperar en caso de error para no saturar
    
    async def _process_action(self, action_data: Dict[str, Any]):
        """
        Procesa una acción específica obtenida de la cola.
        
        Args:
            action_data: Datos de la acción en formato dict
        """
        try:
            # Convertir datos a objeto DomainAction
            action = self.create_action_from_data(action_data)
            
            # Procesar la acción
            result = await self.action_processor.process(action)
            
            # Manejar resultado si es necesario
            if action.callback_queue and result:
                await self._send_callback(action, result)
                
        except Exception as e:
            logger.error(f"Error procesando acción: {str(e)}")
            # Intentar enviar callback de error si es posible
            if action_data.get("callback_queue"):
                await self._send_error_callback(action_data, str(e))
    
    def create_action_from_data(self, action_data: Dict[str, Any]) -> DomainAction:
        """
        Crea objeto DomainAction desde datos JSON.
        
        Esta función debe ser implementada por las subclases para
        crear instancias del tipo apropiado según los datos.
        
        Args:
            action_data: Datos de la acción
            
        Returns:
            Instancia de DomainAction apropiada
        """
        raise NotImplementedError("Debe implementarse en subclase")
    
    # DEPRECATED: Reemplazado por domain-based queues
    def get_queue_names(self) -> List[str]:
        """
        Retorna nombres de colas a procesar.
        
        DEPRECATED: Las subclases deben definir self.domain en su lugar.
        
        Returns:
            Lista de nombres de colas
        """
        logger.warning("get_queue_names() está deprecated. Definir self.domain en subclase.")
        return []
    
    async def _send_callback(self, action: DomainAction, result: Dict[str, Any]):
        """
        Envía resultado como callback.
        
        Esta función debe ser implementada por las subclases para
        definir cómo se envían los resultados como callbacks.
        
        Args:
            action: Acción original
            result: Resultado del procesamiento
        """
        raise NotImplementedError("Debe implementarse en subclase")
    
    async def _send_error_callback(self, action_data: Dict[str, Any], error_message: str):
        """
        Envía callback de error.
        
        Esta función debe ser implementada por las subclases para
        definir cómo se envían los errores como callbacks.
        
        Args:
            action_data: Datos originales de la acción
            error_message: Mensaje de error
        """
        raise NotImplementedError("Debe implementarse en subclase")
    
    # NUEVO: Métodos auxiliares para subclases
    async def get_queue_stats(self) -> Dict[str, Any]:
        """Obtiene estadísticas del dominio actual."""
        return await self.queue_manager.get_queue_stats(self.domain)
    
    async def enqueue_callback(self, callback_action: DomainAction, callback_queue: str) -> bool:
        """Encola callback usando queue manager."""
        return await self.queue_manager.enqueue_callback(callback_action, callback_queue)