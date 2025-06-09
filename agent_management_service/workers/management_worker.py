"""
Worker mejorado para Agent Management Service.

Implementación estandarizada con inicialización asíncrona y
manejo de validación de agentes y cache.

VERSIÓN: 2.0 - Adaptado al patrón improved_base_worker
"""

import logging
from typing import Dict, Any

from common.workers.base_worker import BaseWorker
from common.models.actions import DomainAction
from common.models.execution_context import ExecutionContext
from common.services.domain_queue_manager import DomainQueueManager
from agent_management_service.models.actions_model import AgentValidationAction, CacheInvalidationAction
from agent_management_service.config.settings import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

class ManagementWorker(BaseWorker):
    """
    Worker mejorado para procesar Domain Actions de gestión de agentes.
    
    Características:
    - Inicialización asíncrona segura
    - Validación de configuración de agentes
    - Invalidación de cache
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
        self.domain = settings.domain_name  # "management"
        
        # Control de inicialización
        self.initialized = False
    
    async def initialize(self):
        """Inicializa el worker de forma asíncrona."""
        if self.initialized:
            return
        
        # Ya no registramos handlers sino que procesamos directamente
        # las acciones en el método _process_action
        self.initialized = True
        logger.info("ManagementWorker inicializado correctamente")
    
    async def start(self):
        """Extiende el start para asegurar inicialización."""
        # Asegurar inicialización antes de procesar acciones
        await self.initialize()
        
        # Continuar con el comportamiento normal del BaseWorker
        await super().start()
    
    # Ya no es necesario sobrescribir _process_queue_loop
    # porque BaseWorker ahora proporciona la implementación correcta
    
    def create_action_from_data(self, action_data: Dict[str, Any]) -> DomainAction:
        """
        Crea objeto de acción apropiado según los datos.
        
        Args:
            action_data: Datos de la acción en formato JSON
            
        Returns:
            DomainAction del tipo específico
        """
        action_type = action_data.get("action_type")
        
        if action_type == "management.validate_agent":
            return AgentValidationAction.parse_obj(action_data)
        elif action_type == "management.invalidate_cache":
            return CacheInvalidationAction.parse_obj(action_data)
        else:
            # Fallback a DomainAction genérica
            return DomainAction.parse_obj(action_data)
    
    # Ya no necesitamos sobrescribir _process_action ya que ahora
    # implementamos _handle_action en su lugar
    
    async def _handle_action(self, action: DomainAction, context: Optional[ExecutionContext] = None) -> Dict[str, Any]:
        """
        Implementa el método abstracto de BaseWorker para manejar acciones específicas
        del dominio de management.
        
        Args:
            action: La acción a procesar
            context: Contexto opcional de ejecución
            
        Returns:
            Diccionario con el resultado del procesamiento
        
        Raises:
            ValueError: Si no hay handler implementado para ese tipo de acción
        """
        action_type = action.action_type
        
        if action_type == "management.validate_agent":
            return await self._handle_agent_validation(action, context)
        elif action_type == "management.invalidate_cache":
            return await self._handle_cache_invalidation(action, context)
        else:
            error_msg = f"No hay handler implementado para la acción: {action_type}"
            logger.warning(error_msg)
            raise ValueError(error_msg)
    
    async def _handle_agent_validation(self, action: DomainAction, context: ExecutionContext = None) -> Dict[str, Any]:
        """
        Handler para validación de agentes.
        
        Args:
            action: Acción de validación
            context: Contexto de ejecución opcional con metadatos adicionales
            
        Returns:
            Resultado de la validación
        """
        try:
            # Ya no necesitamos verificar inicialización aquí
            validation_action = AgentValidationAction.parse_obj(action.dict())
            
            # Enriquecer acción con contexto si está disponible
            if context:
                logger.info(f"Validando agente con tier: {context.tenant_tier}")
                validation_action.tenant_tier = context.tenant_tier
                
            # TODO: Implementar lógica de validación
            logger.info(f"Validando configuración de agente: {validation_action.task_id}")
            
            return {
                "success": True,
                "message": "Validación completada",
                "valid": True
            }
            
        except Exception as e:
            logger.error(f"Error en validación de agente: {str(e)}")
            return {
                "success": False,
                "error": {"type": type(e).__name__, "message": str(e)}
            }
    
    async def _handle_cache_invalidation(self, action: DomainAction, context: ExecutionContext = None) -> Dict[str, Any]:
        """
        Handler para invalidación de cache.
        
        Args:
            action: Acción de invalidación
            context: Contexto de ejecución opcional con metadatos adicionales
            
        Returns:
            Resultado de la invalidación
        """
        try:
            # Ya no necesitamos verificar inicialización aquí
            cache_action = CacheInvalidationAction.parse_obj(action.dict())
            
            # Enriquecer acción con contexto si está disponible
            if context:
                logger.info(f"Invalidando cache con tier: {context.tenant_tier}")
                cache_action.tenant_tier = context.tenant_tier
            
            # TODO: Implementar lógica de invalidación
            logger.info(f"Invalidando cache para agente: {cache_action.agent_id}")
            
            return {
                "success": True,
                "message": "Cache invalidado exitosamente"
            }
            
        except Exception as e:
            logger.error(f"Error invalidando cache: {str(e)}")
            return {
                "success": False,
                "error": {"type": type(e).__name__, "message": str(e)}
            }
    
    async def _send_callback(self, action: DomainAction, result: Dict[str, Any]):
        """
        Envía resultado como callback.
        
        En Management Service, normalmente no se envían callbacks
        pero se mantiene la implementación por compatibilidad.
        
        Args:
            action: Acción original que generó el resultado
            result: Resultado del procesamiento
        """
        # Para management service, usualmente no necesitamos enviar callbacks
        # pero si fuera necesario, debemos crearlo con ExecutionContext
        if action.callback_queue and result.get("success"):
            logger.debug(f"Callback disponible para {action.task_id} pero no implementado")
            # Si implementáramos callbacks, se haría así:
            # context = ExecutionContext(
            #     tenant_id=action.tenant_id,
            #     tenant_tier=action.tenant_tier,
            #     session_id=action.session_id
            # )
            # await self.queue_manager.enqueue_execution(
            #     action=callback_action,
            #     target_domain=action.callback_queue.split(".")[0],
            #     context=context
            # )
    
    async def _send_error_callback(self, action_data: Dict[str, Any], error_message: str):
        """
        Envía callback de error.
        
        Args:
            action_data: Datos originales de la acción
            error_message: Mensaje de error
        """
        logger.error(f"Error en worker de management: {error_message}")
        
        # Si fuera necesario implementar callbacks de error:
        callback_queue = action_data.get("callback_queue")
        if callback_queue:
            logger.debug(f"Callback de error disponible pero no implementado: {error_message}")
    
    # Método auxiliar para estadísticas específicas del management service
    async def get_management_stats(self) -> Dict[str, Any]:
        """Obtiene estadísticas específicas del management service."""
        # Obtener estadísticas básicas del worker
        stats = await self.get_worker_stats()
        
        try:
            # Stats de colas
            queue_stats = await self.get_queue_stats()
            stats["queue_stats"] = queue_stats
            
            # Estadísticas específicas del servicio
            # (se podrían implementar métricas adicionales)
            stats["validation_info"] = {
                "tier_limits": {
                    "free": {"max_agents": 3, "max_tools": 5},
                    "pro": {"max_agents": 10, "max_tools": 15},
                    "enterprise": {"max_agents": -1, "max_tools": -1}  # ilimitado
                }
            }
            
        except Exception as e:
            logger.error(f"Error obteniendo estadísticas: {str(e)}")
            stats["error"] = str(e)
        
        return stats
