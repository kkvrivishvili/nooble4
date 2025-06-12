# common/tiers/services/usage_service.py
from ..repositories.tier_repository import TierRepository
from refactorizado.common.db.redis_pool import RedisPool

class TierUsageService:
    """Servicio para registrar el uso de recursos por parte de los tenants."""

    def __init__(self, redis_pool: RedisPool):
        """
        Inicializa el servicio con un pool de conexiones a Redis.

        Args:
            redis_pool: El pool de conexiones que se pasará al repositorio.
        """
        self._repository = TierRepository(redis_pool=redis_pool)

    async def increment_usage(self, tenant_id: str, resource: str, amount: float = 1.0):
        # Lógica para actualizar el contador en la BBDD.
        print(f"(Usage) Incrementando uso para {tenant_id}, recurso {resource}, cantidad {amount}")
        await self._repository.increment_usage_counter(tenant_id, resource, amount)
