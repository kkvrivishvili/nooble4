# common/tiers/services/usage_service.py
from ..repositories.tier_repository import TierRepository
from ..models.tier_config import TierResourceKey

class TierUsageService:
    """Encargado de la lógica de contabilidad: incrementar contadores, etc."""
    def __init__(self, repository: TierRepository):
        self._repository = repository

    async def increment_usage(self, tenant_id: str, resource_key: TierResourceKey, amount: float = 1.0):
        """
        Registra el consumo de un recurso para un tenant.

        Args:
            tenant_id: El ID del tenant que consume el recurso.
            resource_key: La clave estandarizada del recurso consumido.
            amount: La cantidad a incrementar.
        """
        # Aquí se podría añadir lógica adicional, como verificar si el tracking está habilitado
        # en la configuración del servicio antes de llamar al repositorio.
        print(f"(UsageService) Registrando uso para {tenant_id}, recurso {resource_key.value}, cantidad {amount}")
        await self._repository.increment_usage_counter(tenant_id, resource_key.value, amount)

