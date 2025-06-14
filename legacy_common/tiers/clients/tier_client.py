# common/tiers/clients/tier_client.py
from typing import Optional
from ..repositories.tier_repository import TierRepository
from refactorizado.common.db.redis_pool import RedisPool
from ..models.tier_config import TierConfig
from ..models.usage_models import TenantUsage


class TierClient:
    """Cliente para interactuar con el sistema de tiers desde otros servicios."""

    def __init__(self, redis_pool: RedisPool):
        """
        Inicializa el cliente con un pool de conexiones a Redis.

        Args:
            redis_pool: El pool de conexiones que se pasará al repositorio.
        """
        self._repository = TierRepository(redis_pool=redis_pool)

    async def get_tier_config_for_tenant(self, tenant_id: str) -> Optional[TierConfig]:
        """
        Obtiene la configuración de tier completa para un tenant.

        Args:
            tenant_id: El ID del tenant.

        Returns:
            La configuración del tier si se encuentra, de lo contrario None.
        """
        return await self._repository.get_tier_config_for_tenant(tenant_id)

    async def get_tenant_usage(self, tenant_id: str) -> TenantUsage:
        """
        Obtiene el uso actual de todos los recursos para un tenant.

        Args:
            tenant_id: El ID del tenant.

        Returns:
            Un objeto TenantUsage con los contadores actuales.
        """
        return await self._repository.get_tenant_usage(tenant_id)

    async def increment_usage(self, tenant_id: str, resource: str, amount: float = 1.0) -> None:
        """
        Incrementa el contador de uso para un recurso específico de un tenant.

        Args:
            tenant_id: El ID del tenant.
            resource: La clave del recurso a incrementar (ej. 'agents.max_count').
            amount: La cantidad a incrementar.
        """
        await self._repository.increment_usage_counter(tenant_id, resource, amount)
