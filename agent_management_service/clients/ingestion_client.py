"""
Cliente para comunicación con Ingestion Service.
INTEGRADO: Para validar collections existentes.
"""

import logging
import httpx
from typing import Dict, List, Any, Optional

from agent_management_service.config.settings import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)

class IngestionClient:
    """Cliente para comunicarse con Ingestion Service."""
    
    def __init__(self):
        """Inicializa el cliente."""
        self.base_url = settings.ingestion_service_url
        self.timeout = 30
    
    async def validate_collections(
        self,
        collection_ids: List[str],
        tenant_id: str
    ) -> Dict[str, Any]:
        """Valida collections con Ingestion Service."""
        if not collection_ids:
            return {"valid": True, "invalid_ids": []}
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/api/v1/collections/validate",
                    headers={"X-Tenant-ID": tenant_id},
                    json={"collection_ids": collection_ids}
                )
                
                if response.status_code == 200:
                    return response.json()
                else:
                    logger.error(f"Error validando collections: {response.status_code}")
                    return {"valid": False, "invalid_ids": collection_ids}
                    
        except Exception as e:
            logger.error(f"Error conectando con Ingestion Service: {str(e)}")
            # En MVP, retornar válido si hay error de conexión
            return {"valid": True, "invalid_ids": []}
    
    async def list_collections(self, tenant_id: str) -> List[Dict[str, Any]]:
        """Lista collections del tenant."""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    f"{self.base_url}/api/v1/collections",
                    headers={"X-Tenant-ID": tenant_id}
                )
                
                if response.status_code == 200:
                    return response.json().get("collections", [])
                else:
                    logger.error(f"Error listando collections: {response.status_code}")
                    return []
                    
        except Exception as e:
            logger.error(f"Error conectando con Ingestion Service: {str(e)}")
            return []

