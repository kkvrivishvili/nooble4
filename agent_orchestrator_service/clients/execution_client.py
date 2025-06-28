"""
Cliente para comunicación con Agent Execution Service.
Simplificado para usar DomainAction directamente.
"""
import logging
from typing import Dict, Any, Optional
from datetime import datetime

from common.models.actions import DomainAction, DomainActionResponse
from common.errors.exceptions import ExternalServiceError
from common.clients.base_redis_client import BaseRedisClient
from common.config.service_settings import OrchestratorSettings


class ExecutionClient:
    """Cliente para Agent Execution Service vía Redis DomainActions."""
    
    def __init__(
        self,
        redis_client: BaseRedisClient,
        settings: OrchestratorSettings
    ):
        self.redis_client = redis_client
        self.default_timeout = 30
        self._logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
    
    async def send_chat_message(
        self,
        action: DomainAction,
        timeout: Optional[int] = None
    ) -> DomainActionResponse:
        """
        Envía un mensaje de chat al Execution Service.
        
        Args:
            action: DomainAction con toda la información necesaria
            timeout: Timeout opcional (usa default si no se especifica)
            
        Returns:
            DomainActionResponse del Execution Service
        """
        actual_timeout = timeout if timeout is not None else self.default_timeout
        
        try:
            response = await self.redis_client.send_action_pseudo_sync(
                action,
                timeout=actual_timeout
            )
            
            return response
            
        except TimeoutError as e:
            self._logger.error(f"Timeout en chat: {e}")
            raise ExternalServiceError(f"Timeout esperando respuesta: {str(e)}")
        except Exception as e:
            self._logger.error(f"Error en chat: {e}", exc_info=True)
            raise ExternalServiceError(f"Error comunicándose con Execution Service: {str(e)}")