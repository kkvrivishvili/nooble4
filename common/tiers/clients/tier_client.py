# common/tiers/clients/tier_client.py
from typing import Optional
from ..repositories.tier_repository import TierRepository
from ..models.tier_config import TierLimits
from ..models.usage_models import TenantUsage

class TierClient:
    """Cliente de alto nivel para interactuar con el sistema de tiers."""
    def __init__(self, repository: TierRepository):
        self._repository = repository

    async def get_tier_limits_for_tenant(self, tenant_id: str) -> Optional[TierLimits]:
        """
        Obtiene los límites de tier para un tenant específico.

        Este método encapsula la lógica de obtener primero el nombre del tier
        del tenant y luego buscar la configuración de límites para ese tier.
        """
        print(f"(Client) Solicitando límites para el tenant {tenant_id}")
        tier_name = await self._repository.get_tier_name_for_tenant(tenant_id)
        if not tier_name:
            print(f"(Client) No se pudo encontrar un tier para el tenant {tenant_id}")
            return None
        
        print(f"(Client) Tenant {tenant_id} tiene el tier '{tier_name}'. Buscando límites.")
        return await self._repository.get_tier_limits(tier_name)

    async def get_tenant_usage(self, tenant_id: str) -> TenantUsage:
        """Obtiene el uso de recursos actual para un tenant."""
        print(f"(Client) Solicitando uso para el tenant {tenant_id}")
        return await self._repository.get_tenant_usage(tenant_id)

