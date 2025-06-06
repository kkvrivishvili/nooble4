"""
BaseWorker: Clase base para workers que procesan Domain Actions.

Proporciona una implementación estándar para procesar acciones
de colas Redis con implementación común de ciclo de procesamiento.
"""

import asyncio
import json
import logging
from typing import Dict, Any, List, Optional

from common.models.actions import DomainAction
from common.services.action_processor import ActionProcessor

logger = logging.getLogger(__name__)

class BaseWorker:
    """
    Worker base para procesar acciones de colas Redis.
    
    Esta clase abstracta define el comportamiento común para workers
    que procesan domain actions desde colas Redis.
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
        
    async def start(self):
        """
        Inicia el worker y comienza a procesar colas.
        """
        self.running = True
        logger.info(f"Iniciando {self.__class__.__name__}")
        
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
    
    async def _process_queue_loop(self):
        """
        Procesa colas de forma continua mientras el worker esté activo.
        """
        while self.running:
            try:
                # Obtener lista de colas a procesar
                queues = self.get_queue_names()
                
                for queue in queues:
                    # Intentar obtener una acción de la cola con timeout corto
                    raw_data = await self.redis_client.brpop(queue, timeout=1)
                    if not raw_data:
                        continue
                    
                    # Procesar la acción
                    _, data = raw_data
                    action_data = json.loads(data)
                    await self._process_action(action_data)
                
                # Pequeña pausa entre ciclos
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
    
    def get_queue_names(self) -> List[str]:
        """
        Retorna nombres de colas a procesar.
        
        Esta función debe ser implementada por las subclases para
        especificar qué colas debe monitorear el worker.
        
        Returns:
            Lista de nombres de colas
        """
        raise NotImplementedError("Debe implementarse en subclase")
    
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
