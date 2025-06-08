"""
BaseWorker Mejorado: Clase base para workers que procesan Domain Actions.

Proporciona una implementación estándar para procesar acciones
de colas Redis con implementación común de ciclo de procesamiento.
Incluye inicialización asíncrona estandarizada y gestión robusta de errores.

VERSIÓN: 2.0 - Estandarización completa con mejores prácticas.
"""

import asyncio
import datetime
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
    Worker base estandarizado para procesar acciones de colas Redis.
    
    Esta clase abstracta define el comportamiento común para workers
    que procesan domain actions desde colas Redis con inicialización
    asíncrona segura y gestión robusta de errores.
    
    Características:
    - Inicialización asíncrona segura
    - Validación de redis_client
    - Patrón consistente para registrar handlers
    - Manejo seguro de ciclo de procesamiento
    - Implementación de callbacks
    """
    
    def __init__(self, redis_client, action_processor=None):
        """
        Inicializa el worker base con validación de parámetros.
        
        Args:
            redis_client: Cliente Redis para acceso a colas (requerido)
            action_processor: Procesador de acciones (opcional)
        """
        # Validación de redis_client
        if redis_client is None:
            raise ValueError("redis_client no puede ser None. Debe configurarse externamente")
            
        # Inicialización básica
        self.redis_client = redis_client
        self.action_processor = action_processor or ActionProcessor(self.redis_client)
        self.running = False
        self.sleep_seconds = 1.0
        self.initialized = False
        
        # Integración con DomainQueueManager
        self.queue_manager = DomainQueueManager(self.redis_client)
        
        # Domain específico (debe ser definido por subclases)
        self.domain = getattr(self, 'domain', 'unknown')
        
        if self.domain == 'unknown':
            logger.warning(f"Worker {self.__class__.__name__} no tiene dominio definido.")
        
    async def initialize(self):
        """
        Inicializa el worker de forma asíncrona.
        
        Las subclases deben implementar este método para cualquier
        inicialización asíncrona necesaria (ej: registrar handlers,
        configurar servicios externos, etc).
        """
        if self.initialized:
            return
            
        await self._initialize_handlers()
        self.initialized = True
        logger.info(f"{self.__class__.__name__} inicializado correctamente")
        
    async def _initialize_handlers(self):
        """
        Inicializa y registra handlers.
        
        Las subclases deben implementar este método para registrar
        sus handlers específicos en el action_processor.
        """
        # Implementación vacía por defecto
        # Las subclases deben sobrescribir este método
        pass
        
    async def start(self):
        """
        Inicia el worker asegurando inicialización previa.
        """
        # Asegurar inicialización antes de procesar acciones
        if not self.initialized:
            await self.initialize()
            
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
    
    async def _process_queue_loop(self):
        """
        Procesa colas de forma continua mientras el worker esté activo.
        """
        while self.running:
            try:
                # Desencolar respetando prioridad de tiers
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
        action = None
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
        # Implementación básica que puede ser reemplazada por subclases
        return DomainAction.parse_obj(action_data)
    
    async def _send_callback(self, action: DomainAction, result: Dict[str, Any]):
        """
        Envía resultado como callback.
        
        Esta función debe ser implementada por las subclases para
        definir cómo se envían los resultados como callbacks.
        
        Args:
            action: Acción original
            result: Resultado del procesamiento
        """
        # Implementación estándar que puede ser reemplazada por subclases
        if action.callback_queue and result.get("success") is not None:
            callback_action = DomainAction(
                action_type=f"{action.get_action_name()}_callback",
                task_id=action.task_id,
                tenant_id=action.tenant_id,
                tenant_tier=action.tenant_tier,
                session_id=action.session_id,
                data=result
            )
            await self.enqueue_callback(callback_action, action.callback_queue)
            logger.debug(f"Enviado callback para {action.task_id} a {action.callback_queue}")
    
    async def _send_error_callback(self, action_data: Dict[str, Any], error_message: str):
        """
        Envía callback de error.
        
        Esta función debe ser implementada por las subclases para
        definir cómo se envían los errores como callbacks.
        
        Args:
            action_data: Datos originales de la acción
            error_message: Mensaje de error
        """
        # Implementación estándar que puede ser reemplazada por subclases
        callback_queue = action_data.get("callback_queue")
        if callback_queue:
            error_action = DomainAction(
                action_type=f"{self.domain}.error",
                task_id=action_data.get("task_id"),
                tenant_id=action_data.get("tenant_id"),
                tenant_tier=action_data.get("tenant_tier"),
                session_id=action_data.get("session_id"),
                data={"error": error_message, "success": False}
            )
            await self.enqueue_callback(error_action, callback_queue)
            logger.debug(f"Enviado error callback para {action_data.get('task_id')} a {callback_queue}")
    
    # Métodos auxiliares para subclases
    async def get_queue_stats(self) -> Dict[str, Any]:
        """Obtiene estadísticas del dominio actual."""
        return await self.queue_manager.get_queue_stats(self.domain)
    
    async def enqueue_callback(self, callback_action: DomainAction, callback_queue: str) -> bool:
        """Encola callback usando queue manager."""
        return await self.queue_manager.enqueue_callback(callback_action, callback_queue)
        
    async def get_worker_stats(self) -> Dict[str, Any]:
        """
        Obtiene estadísticas generales del worker.
        
        Este método puede ser extendido por las subclases para incluir
        estadísticas específicas del servicio.
        
        Returns:
            Dict con estadísticas básicas
        """
        # Estadísticas básicas disponibles en todos los workers
        queue_stats = await self.get_queue_stats()
        
        return {
            "queue_stats": queue_stats,
            "worker_info": {
                "domain": self.domain,
                "running": self.running,
                "initialized": self.initialized,
                "timestamp": datetime.datetime.utcnow().isoformat()
            }
        }
