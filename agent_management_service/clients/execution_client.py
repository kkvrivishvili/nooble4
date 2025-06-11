"""
Cliente para comunicación con Agent Execution Service.
Refactorizado para usar DomainActions sobre Redis para invalidación de caché.
"""

import logging
import uuid

from common.models.actions import DomainAction
from common.services.domain_queue_manager import DomainQueueManager
from agent_management_service.config.settings import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)

class ExecutionClient:
    """Cliente para comunicarse con Agent Execution Service via Redis."""
    
    def __init__(self, redis_client):
        """Inicializa el cliente con una conexión a Redis."""
        if not redis_client:
            raise ValueError("Se requiere un cliente Redis para ExecutionClient.")
        self.redis_client = redis_client
        self.queue_manager = DomainQueueManager(redis_client)
        self.settings = get_settings()

    async def invalidate_agent_cache(self, agent_id: str, tenant_id: str) -> bool:
        """Encola una acción para invalidar la caché de un agente en Execution Service."""
        action = DomainAction(
            action_id=f"exec-cache-inv-{uuid.uuid4().hex[:12]}",
            action_type="execution.cache.invalidate",
            tenant_id=tenant_id,
            origin_service=self.settings.service_name,  # "agent_management"
            data={"agent_id": agent_id}
        )
        
        # La cola del servicio de ejecución es específica del tenant
        queue_name = f"execution:{tenant_id}:actions"
        
        try:
            await self.queue_manager.enqueue_action(queue_name, action)
            logger.info(f"Acción de invalidación de caché encolada para el agente {agent_id} en el tenant {tenant_id} a la cola {queue_name}")
            return True
        except Exception as e:
            logger.error(f"Error al encolar la acción de invalidación de caché para el agente {agent_id}: {str(e)}", exc_info=True)
            return False
