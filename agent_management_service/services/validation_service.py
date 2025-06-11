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
    
    async def validate_tenant_limits(self, tenant_id: str, tenant_tier: str):
        """Valida límites del tenant."""
        limits = settings.tier_limits.get(tenant_tier, {})
        max_agents = limits.get("max_agents")
        
        if max_agents is not None:
            # TODO: Contar agentes actuales del tenant en base de datos
            current_count = 0  # Placeholder
            
            if current_count >= max_agents:
                raise ValueError(f"Límite de agentes alcanzado para tier {tenant_tier}: {max_agents}")
    
    async def validate_agent_config(self, config: Dict[str, Any], tenant_tier: str):
        """Valida configuración de agente según tier."""
        limits = settings.tier_limits.get(tenant_tier, {})
        
        # Validar herramientas
        available_tools = limits.get("available_tools", [])
        if available_tools != ["all"]:
            config_tools = config.get("tools", [])
            invalid_tools = [tool for tool in config_tools if tool not in available_tools]
            if invalid_tools:
                raise ValueError(f"Herramientas no disponibles para tier {tenant_tier}: {invalid_tools}")
        
        # Validar modelo
        available_models = limits.get("available_models", [])
        if available_models != ["all"]:
            model = config.get("model")
            if model and model not in available_models:
                raise ValueError(f"Modelo {model} no disponible para tier {tenant_tier}")
        
        # Validar número de collections
        max_collections = limits.get("max_collections_per_agent")
        if max_collections is not None:
            collections = config.get("collections", [])
            if len(collections) > max_collections:
                raise ValueError(f"Máximo {max_collections} collections permitidas para tier {tenant_tier}")
    
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

