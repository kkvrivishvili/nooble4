# common/tiers/services/accounting_service.py
import logging

from refactorizado.common.db.redis_pool import RedisPool
from ..clients import TierClient

logger = logging.getLogger(__name__)

class TierAccountingService:
    """Servicio para contabilizar el uso de recursos por parte de un tenant."""

    def __init__(self, redis_pool: RedisPool):
        """
        Inicializa el servicio con un pool de conexiones a Redis.

        Args:
            redis_pool: El pool de conexiones que se pasará al cliente de tiers.
        """
        self._tier_client = TierClient(redis_pool=redis_pool)

    async def increment_usage(self, tenant_id: str, resource_key: str, amount: float = 1.0) -> None:
        """
        Incrementa el contador de uso para un recurso específico después de que la acción
        se haya completado con éxito.

        Args:
            tenant_id: El ID del tenant.
            resource_key: La clave del recurso a incrementar (ej. 'agents.max_count').
            amount: La cantidad a incrementar.
        """
        logger.debug(
            f"Contabilizando uso para tenant '{tenant_id}', recurso '{resource_key}', cantidad: {amount}"
        )
        try:
            await self._tier_client.increment_usage(tenant_id, resource_key, amount)
            logger.info(
                f"Uso contabilizado exitosamente para tenant '{tenant_id}', recurso '{resource_key}'."
            )
        except Exception as e:
            logger.error(
                f"Error al contabilizar el uso para tenant '{tenant_id}', recurso '{resource_key}': {e}",
                exc_info=True
            )
            # Nota: En un sistema real, aquí podría haber una cola de reintentos
            # para no perder la contabilización de uso.
