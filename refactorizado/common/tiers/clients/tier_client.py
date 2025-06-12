# common/tiers/clients/tier_client.py
from typing import Optional
from ..repositories.tier_repository import TierRepository
from ..models.tier_config import TierLimits
from ..models.usage_models import TenantUsage

class TierClient:
    """Cliente para interactuar con el repositorio de tiers"""
    def __init__(self, repository: TierRepository):
        self._repository = repository

    async def get_tier_limits_for_tenant(self, tenant_id: str) -> Optional[TierLimits]:
        # Lógica para obtener el tier del tenant (desde AMS?)
        # y luego devolver la configuración de límites cacheados.
        return await self._repository.get_tier_limits_for_tenant(tenant_id)

    async def get_tenant_usage(self, tenant_id: str) -> TenantUsage:
        # Devuelve el uso actual del tenant.
        return await self._repository.get_tenant_usage(tenant_id)
