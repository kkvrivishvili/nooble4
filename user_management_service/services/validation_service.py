"""
Servicio de validación para agentes y configuraciones.
INTEGRADO: Con validación de collections vía Ingestion Service.
"""

import logging
from typing import List, Dict, Any

from agent_management_service.config.settings import get_settings
from agent_management_service.clients.ingestion_client import IngestionClient

settings = get_settings()
logger = logging.getLogger(__name__)

class ValidationService:
    """Servicio para validaciones de agentes."""
    
    def __init__(self, redis_client=None):
        """Inicializa el servicio de validación."""
        self.ingestion_client = IngestionClient(redis_client)
    

    async def validate_collections(self, collection_ids: List[str], tenant_id: str):
        """Valida que las collections existan y sean accesibles."""
        if not settings.enable_collection_validation:
            return
        
        if not collection_ids:
            return
        
        try:
            # Validar collections con Ingestion Service
            valid_collections = await self.ingestion_client.validate_collections(
                collection_ids, tenant_id
            )
            
            if not valid_collections["valid"]:
                invalid_ids = valid_collections.get("invalid_ids", [])
                raise ValueError(f"Collections no válidas: {invalid_ids}")
                
        except Exception as e:
            logger.error(f"Error validando collections: {str(e)}")
            # En caso de error del servicio, permitir continuar en MVP
            logger.warning("Continuando sin validación de collections debido a error del servicio")

