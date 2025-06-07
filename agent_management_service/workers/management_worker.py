"""
Worker para Agent Management Service.
INTEGRADO: Con sistema de colas por tier existente.
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
    """Worker para procesar Domain Actions de gestión de agentes."""
    
    def __init__(self, redis_client=None, action_processor=None):
        """Inicializa worker."""
        action_processor = action_processor or ActionProcessor(redis_client)
        super().__init__(redis_client, action_processor)
        
        # Definir domain específico
        self.domain = settings.domain_name  # "management"
        
        # Registrar handlers
        self.action_processor.register_handler(
            "management.validate_agent",
            self._handle_agent_validation
        )
        
        self.action_processor.register_handler(
            "management.invalidate_cache",
            self._handle_cache_invalidation
        )
    
    def create_action_from_data(self, action_data: Dict[str, Any]) -> DomainAction:
        """Crea objeto de acción apropiado según los datos."""
        action_type = action_data.get("action_type")
        
        if action_type == "management.validate_agent":
            return AgentValidationAction.parse_obj(action_data)
        elif action_type == "management.invalidate_cache":
            return CacheInvalidationAction.parse_obj(action_data)
        else:
            return DomainAction.parse_obj(action_data)
    
    async def _handle_agent_validation(self, action: DomainAction) -> Dict[str, Any]:
        """Handler para validación de agentes."""
        try:
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
        """Handler para invalidación de cache."""
        try:
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
        """Envía resultado como callback."""
        # Para management service, usualmente no necesitamos enviar callbacks
        # pero podríamos implementarlo si es necesario
        pass
    
    async def _send_error_callback(self, action_data: Dict[str, Any], error_message: str):
        """Envía callback de error."""
        logger.error(f"Error en worker de management: {error_message}")
