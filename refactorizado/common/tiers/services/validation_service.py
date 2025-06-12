# common/tiers/services/validation_service.py
from ..clients.tier_client import TierClient
from ..exceptions import TierLimitExceededError

class TierValidationService:
    """Contiene la lógica pura de validación de límites y permisos."""
    def __init__(self, tier_client: TierClient):
        self._tier_client = tier_client

    async def validate(self, tenant_id: str, resource: str, **kwargs):
        """Método genérico de validación."""
        # Este método podría usar un diccionario o un patrón strategy
        # para llamar al método de validación específico.
        print(f"Validando recurso '{resource}' para el tenant '{tenant_id}' con argumentos {kwargs}")
        # Placeholder: por defecto, la validación es exitosa.
        return True

    async def validate_agent_creation(self, tenant_id: str):
        limits = await self._tier_client.get_tier_limits_for_tenant(tenant_id)
        # Aquí iría la lógica para comparar con el número actual de agentes del tenant.
        # if current_agents >= limits.max_agents:
        #     raise TierLimitExceededError("Número máximo de agentes alcanzado.")
        print(f"(Validation) Validando creación de agente para {tenant_id}")
        return True

    async def validate_query_length(self, tenant_id: str, length: int):
        limits = await self._tier_client.get_tier_limits_for_tenant(tenant_id)
        # if length > limits.max_query_length:
        #     raise TierLimitExceededError("Longitud de query excede el límite del tier.")
        print(f"(Validation) Validando longitud de query ({length}) para {tenant_id}")
        return True
