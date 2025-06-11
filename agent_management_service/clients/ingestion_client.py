"""
Cliente para comunicación con Ingestion Service usando Redis.
"""

import logging
import uuid
import json
from typing import Dict, List, Any, Optional

from common.models.actions import DomainAction, DomainActionResponse
from common.services.domain_queue_manager import DomainQueueManager
from agent_management_service.config.settings import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)

class IngestionClient:
    """Cliente para comunicarse con Ingestion Service via Redis."""
    
    def __init__(self, redis_client):
        """Inicializa el cliente con una conexión a Redis."""
        if not redis_client:
            raise ValueError("Se requiere un cliente Redis para IngestionClient.")
        self.redis_client = redis_client
        self.queue_manager = DomainQueueManager(redis_client)
        self.settings = get_settings()
        self.timeout = 30  # Segundos de espera para la respuesta

    async def _send_request_and_wait_for_response(
        self, 
        action_type: str, 
        tenant_id: str, 
        data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Función genérica para enviar una acción y esperar una respuesta pseudo-síncrona."""
        correlation_id = str(uuid.uuid4())
        callback_queue = f"{self.settings.service_name}:responses:{correlation_id}"
        
        action = DomainAction(
            action_id=f"ing-req-{uuid.uuid4().hex[:12]}",
            action_type=action_type,
            tenant_id=tenant_id,
            origin_service=self.settings.service_name,
            callback_queue_name=callback_queue,
            correlation_id=correlation_id,
            data=data
        )
        
        ingestion_queue = f"ingestion:{tenant_id}:actions"
        
        try:
            await self.queue_manager.enqueue_action(ingestion_queue, action)
            logger.info(f"Esperando respuesta para {action_type} en {callback_queue}")
            
            response_data = await self.redis_client.brpop([callback_queue], timeout=self.timeout)
            
            if not response_data:
                logger.error(f"Timeout esperando respuesta de Ingestion Service para la acción {action_type}")
                return None
            
            response = DomainActionResponse.parse_raw(response_data[1])
            
            if response.correlation_id != correlation_id:
                logger.error("Error de correspondencia de Correlation ID.")
                return None
            
            if not response.success:
                error_msg = response.error.message if response.error else "Error desconocido"
                logger.error(f"Ingestion Service devolvió un error para {action_type}: {error_msg}")
                return None
                
            return response.data

        except Exception as e:
            logger.error(f"Error en la comunicación con Ingestion Service para {action_type}: {str(e)}", exc_info=True)
            return None

    async def validate_collections(
        self,
        collection_ids: List[str],
        tenant_id: str
    ) -> Dict[str, Any]:
        """Valida collections con Ingestion Service via Redis."""
        if not collection_ids:
            return {"valid": True, "invalid_ids": []}
        
        response_data = await self._send_request_and_wait_for_response(
            action_type="ingestion.collections.validate",
            tenant_id=tenant_id,
            data={"collection_ids": collection_ids}
        )
        
        if response_data:
            return response_data
        
        # Fallback en caso de error de comunicación o timeout
        return {"valid": False, "invalid_ids": collection_ids, "error": "Communication error with Ingestion Service"}

    async def list_collections(self, tenant_id: str) -> List[Dict[str, Any]]:
        """Lista collections del tenant via Redis."""
        response_data = await self._send_request_and_wait_for_response(
            action_type="ingestion.collections.list",
            tenant_id=tenant_id,
            data={}
        )
        
        if response_data and 'collections' in response_data:
            return response_data['collections']
            
        # Fallback en caso de error
        return []

