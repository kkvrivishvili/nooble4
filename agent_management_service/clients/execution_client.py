"""
Cliente para comunicación con Agent Execution Service.
INTEGRADO: Para invalidación de cache.
"""

import logging
import httpx
from typing import Dict, Any

from agent_management_service.config.settings import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)

class ExecutionClient:
    """Cliente para comunicarse con Agent Execution Service."""
    
    def __init__(self):
        """Inicializa el cliente."""
        self.base_url = settings.execution_service_url
        self.timeout = 10
    
    async def invalidate_agent_cache(self, agent_id: str, tenant_id: str) -> bool:
        """Invalida cache de agente en Execution Service."""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/internal/cache/invalidate/{agent_id}",
                    headers={"X-Tenant-ID": tenant_id}
                )
                
                return response.status_code == 200
                
        except Exception as e:
            logger.error(f"Error invalidando cache: {str(e)}")
            return False
