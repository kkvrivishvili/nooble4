# common/tiers/services/validation_service.py
from typing import Any, Dict, Callable, Awaitable
from ..clients.tier_client import TierClient
from ..exceptions import TierLimitExceededError
from ..models.tier_config import TierResourceKey, TierLimits
from ..models.usage_models import TenantUsage

class TierValidationService:
    """Contiene la lógica pura de validación de límites y permisos."""

    def __init__(self, tier_client: TierClient):
        self._tier_client = tier_client
        self._validation_map: Dict[TierResourceKey, Callable[..., Awaitable[None]]] = {
            TierResourceKey.MAX_AGENTS: self._validate_max_agents,
            TierResourceKey.MAX_DAILY_DOCUMENTS: self._validate_daily_documents,
            TierResourceKey.MAX_QUERY_LENGTH: self._validate_max_query_length,
            TierResourceKey.ALLOWED_QUERY_MODELS: self._validate_allowed_model,
        }

    async def validate(self, tenant_id: str, resource_key: TierResourceKey, **kwargs: Any) -> None:
        """
        Método principal que despacha la validación al método específico.

        Args:
            tenant_id: El ID del tenant a validar.
            resource_key: La clave del recurso a validar.
            **kwargs: Argumentos adicionales necesarios para la validación (e.g., `value`).

        Raises:
            TierLimitExceededError: Si la validación falla.
            NotImplementedError: Si no hay un método de validación para el recurso.
        """
        print(f"(ValidationService) Iniciando validación para {tenant_id} en recurso {resource_key.value}")
        validator = self._validation_map.get(resource_key)

        if not validator:
            raise NotImplementedError(f"No hay un método de validación implementado para el recurso '{resource_key.value}'")

        limits = await self._tier_client.get_tier_limits_for_tenant(tenant_id)
        if not limits:
            raise TierLimitExceededError(
                f"No se pudo determinar la configuración del tier para el tenant '{tenant_id}'.",
                resource_key=resource_key.value
            )

        # El uso solo se obtiene si es necesario para la validación
        usage = await self._tier_client.get_tenant_usage(tenant_id)

        await validator(limits=limits, usage=usage, **kwargs)
        print(f"(ValidationService) Validación exitosa para {tenant_id} en recurso {resource_key.value}")

    # --- Métodos de validación específicos ---

    async def _validate_max_agents(self, limits: TierLimits, usage: TenantUsage, **kwargs: Any) -> None:
        """Valida si el tenant puede crear más agentes."""
        # Esta validación es compleja porque requiere saber cuántos agentes ya tiene el tenant.
        # Este dato no está en `usage`, debería ser consultado a otro servicio (AMS) o BBDD.
        # Por ahora, se simula que siempre es válido.
        print(f"Validando MAX_AGENTS (límite: {limits.max_agents}). Simulación: OK")
        # Ejemplo real:
        # current_agents = await self._ams_client.get_agent_count(tenant_id)
        # if current_agents >= limits.max_agents:
        #     raise TierLimitExceededError(...)

    async def _validate_daily_documents(self, limits: TierLimits, usage: TenantUsage, **kwargs: Any) -> None:
        """Valida si el tenant puede ingestar más documentos hoy."""
        if usage.daily_documents >= limits.max_daily_documents:
            raise TierLimitExceededError(
                f"Límite diario de ingesta de documentos ({limits.max_daily_documents}) alcanzado.",
                resource_key=TierResourceKey.MAX_DAILY_DOCUMENTS.value
            )
        print(f"Validando MAX_DAILY_DOCUMENTS (usados: {usage.daily_documents}, límite: {limits.max_daily_documents}): OK")

    async def _validate_max_query_length(self, limits: TierLimits, usage: TenantUsage, **kwargs: Any) -> None:
        """Valida la longitud de una query."""
        query_length = kwargs.get("value")
        if not isinstance(query_length, int):
            raise TypeError("El argumento 'value' debe ser un entero para la validación de longitud.")
        
        if query_length > limits.max_query_length:
            raise TierLimitExceededError(
                f"La longitud de la query ({query_length}) excede el límite de {limits.max_query_length} caracteres.",
                resource_key=TierResourceKey.MAX_QUERY_LENGTH.value
            )
        print(f"Validando MAX_QUERY_LENGTH (valor: {query_length}, límite: {limits.max_query_length}): OK")

    async def _validate_allowed_model(self, limits: TierLimits, usage: TenantUsage, **kwargs: Any) -> None:
        """Valida si un modelo de lenguaje está permitido."""
        model_name = kwargs.get("value")
        if not isinstance(model_name, str):
            raise TypeError("El argumento 'value' debe ser un string para la validación de modelo.")

        if model_name not in limits.allowed_query_models:
            raise TierLimitExceededError(
                f"El modelo '{model_name}' no está permitido para este tier.",
                resource_key=TierResourceKey.ALLOWED_QUERY_MODELS.value
            )
        print(f"Validando ALLOWED_QUERY_MODELS (modelo: {model_name}, permitidos: {limits.allowed_query_models}): OK")

