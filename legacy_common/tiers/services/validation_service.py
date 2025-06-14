# common/tiers/services/validation_service.py
import logging
import asyncio
from typing import Any

from refactorizado.common.db.redis_pool import RedisPool
from ..clients import TierClient
from ..exceptions import TierLimitExceededError

logger = logging.getLogger(__name__)

class TierValidationService:
    """Servicio para validar si una acción está permitida según el tier del tenant."""

    def __init__(self, redis_pool: RedisPool):
        self._tier_client = TierClient(redis_pool=redis_pool)

    async def validate(self, tenant_id: str, resource_key: str, request_value: Any = 1):
        """
        Valida si un tenant puede usar un recurso, comparando su uso actual con los límites de su tier.

        Args:
            tenant_id: El ID del tenant que realiza la acción.
            resource_key: La clave única del recurso a validar (ej. 'agents.max_count').
            request_value: El valor de la solicitud actual (ej. 1 para crear un agente, o la longitud de un texto).
                           Por defecto es 1 para límites de tipo contador.

        Raises:
            TierLimitExceededError: Si el uso actual más el valor solicitado excede el límite.
            AttributeError: Si la configuración del tier o el límite para el recurso no se encuentran.
        """
        logger.debug(f"Iniciando validación para tenant '{tenant_id}' sobre recurso '{resource_key}'.")

        # 1. Obtener la configuración del tier y el uso actual en paralelo
        tier_config, tenant_usage = await asyncio.gather(
            self._tier_client.get_tier_config_for_tenant(tenant_id),
            self._tier_client.get_tenant_usage(tenant_id)
        )

        if not tier_config:
            # Si no hay configuración de tier, se deniega por defecto por seguridad.
            raise AttributeError(f"No se pudo encontrar la configuración del tier para el tenant '{tenant_id}'.")

        # 2. Extraer el límite para el recurso específico
        # Navegamos por el modelo TierLimits usando getattr para encontrar el límite correcto.
        limit_value = tier_config.limits
        for key in resource_key.split('.'):
            if not hasattr(limit_value, key):
                 raise AttributeError(f"El límite para '{resource_key}' no está definido en el tier '{tier_config.name}'.")
            limit_value = getattr(limit_value, key)

        if limit_value is None or limit_value < 0:
            # Un límite de None o negativo significa que no hay límite (acceso ilimitado).
            logger.debug(f"Recurso '{resource_key}' no tiene límite para el tier '{tier_config.name}'. Validación exitosa.")
            return

        # 3. Extraer el uso actual para el recurso
        current_usage = tenant_usage.usage_records.get(resource_key, None)
        current_usage_amount = current_usage.amount if current_usage else 0

        # 4. Comparar y decidir
        if (current_usage_amount + request_value) > limit_value:
            error_msg = (
                f"Límite del tier '{tier_config.name}' excedido para el recurso '{resource_key}'. "
                f"Límite: {limit_value}, Uso actual: {current_usage_amount}, Solicitado: {request_value}."
            )
            logger.warning(error_msg)
            raise TierLimitExceededError(
                message=error_msg,
                resource_key=resource_key,
                tier_name=tier_config.name
            )

        logger.info(f"Validación exitosa para tenant '{tenant_id}' en recurso '{resource_key}'.")
