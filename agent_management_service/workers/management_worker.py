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
from common.services.action_processor import ActionProcessor
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
        self.domain = settings.domain_name  # "management"
        
        # Control de inicialización
        self.initialized = False
    
    async def initialize(self):
        """Inicializa el worker de forma asíncrona."""
        if self.initialized:
            return
            
        await self._initialize_handlers()
        self.initialized = True
        logger.info("ImprovedManagementWorker inicializado correctamente")
    
    async def start(self):
        """Extiende el start para asegurar inicialización."""
        # Asegurar inicialización antes de procesar acciones
        await self.initialize()
        
        # Continuar con el comportamiento normal del BaseWorker
        await super().start()
        
    async def _initialize_handlers(self):
        """Inicializa todos los handlers necesarios."""
        # Registrar handlers en el action_processor
        self.action_processor.register_handler(
            "management.validate_agent",
            self._handle_agent_validation
        )
        
        self.action_processor.register_handler(
            "management.invalidate_cache",
            self._handle_cache_invalidation
        )
        
        logger.info("ManagementWorker: Handlers inicializados")
    
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
    
    async def _handle_agent_validation(self, action: DomainAction) -> Dict[str, Any]:
        """
        Handler para validación de agentes.
        
        Args:
            action: Acción de validación
            
        Returns:
            Resultado de la validación
        """
        try:
            # Verificar inicialización
            if not self.initialized:
                await self.initialize()
                
            validation_action = AgentValidationAction.parse_obj(action.dict())
            
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
    
    async def _handle_cache_invalidation(self, action: DomainAction) -> Dict[str, Any]:
        """
        Handler para invalidación de cache.
        
        Args:
            action: Acción de invalidación
            
        Returns:
            Resultado de la invalidación
        """
        try:
            # Verificar inicialización
            if not self.initialized:
                await self.initialize()
                
            cache_action = CacheInvalidationAction.parse_obj(action.dict())
            
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
        # pero podríamos implementarlo si es necesario
        if action.callback_queue and result.get("success"):
            logger.debug(f"Callback disponible para {action.task_id} pero no implementado")
    
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
