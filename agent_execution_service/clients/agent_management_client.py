"""
Cliente para comunicarse con Agent Management Service.
"""

import logging
import httpx
from typing import Dict, Any, Optional
from uuid import UUID
from tenacity import retry, stop_after_attempt, wait_exponential

from config.settings import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

class AgentManagementClient:
    """Cliente para comunicarse con Agent Management Service."""
    
    def __init__(self):
        self.base_url = settings.agent_management_service_url
        self.timeout = settings.http_timeout_seconds
        
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10)
    )
    async def get_agent(
        self,
        agent_id: UUID,
        tenant_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Obtiene la configuración de un agente.
        
        Args:
            agent_id: ID del agente
            tenant_id: ID del tenant
            
        Returns:
            Dict con configuración del agente o None si no existe
        """
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    f"{self.base_url}/api/v1/agents/{agent_id}",
                    headers={"X-Tenant-ID": tenant_id}
                )
                response.raise_for_status()
                
                result = response.json()
                if result.get("success", False) and result.get("agent"):
                    return result["agent"]
                
                return None
                
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                logger.warning(f"Agente no encontrado: {agent_id}")
                return None
            logger.error(f"Error HTTP obteniendo agente: {e.response.status_code}")
            raise
        except Exception as e:
            logger.error(f"Error en Agent Management Service: {str(e)}")
            raise
