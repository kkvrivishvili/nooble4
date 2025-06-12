# common/tiers/services/usage_service.py
from ..repositories.tier_repository import TierRepository

class TierUsageService:
    """Encargado de la lógica de contabilidad: incrementar contadores, etc."""
    def __init__(self, repository: TierRepository):
        self._repository = repository

    async def increment_usage(self, tenant_id: str, resource: str, amount: float = 1.0):
        # Lógica para actualizar el contador en la BBDD.
        print(f"(Usage) Incrementando uso para {tenant_id}, recurso {resource}, cantidad {amount}")
        await self._repository.increment_usage_counter(tenant_id, resource, amount)
