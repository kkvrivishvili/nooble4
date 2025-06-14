# common/tiers/repositories/tier_repository.py
import json
import logging
from typing import Optional, Dict
from datetime import datetime, timezone

from refactorizado.common.db.redis_pool import RedisPool
from ..models.tier_config import TierConfig
from ..models.usage_models import TenantUsage, UsageRecord

logger = logging.getLogger(__name__)

class TierRepository:
    """Abstrae el acceso a los datos de tiers, usando Redis como caché y almacén de contadores."""

    # --- Esquema de Claves de Redis ---
    # 1. Tier de un tenant: 'tenants:{tenant_id}:tier' -> "free" | "pro" | ...
    # 2. Config de un tier: 'tiers:config:{tier_name}' -> JSON string de TierConfig
    # 3. Uso de un tenant:  'tenants:{tenant_id}:usage' -> Hash de {resource_key: count}

    def __init__(self, redis_pool: RedisPool):
        self._redis_pool = redis_pool
        self._db_conn = None  # Placeholder para persistencia en PostgreSQL

    def _get_tenant_tier_key(self, tenant_id: str) -> str:
        return f"tenants:{tenant_id}:tier"

    def _get_tier_config_key(self, tier_name: str) -> str:
        return f"tiers:config:{tier_name}"

    def _get_tenant_usage_key(self, tenant_id: str) -> str:
        return f"tenants:{tenant_id}:usage"

    async def get_tier_config_for_tenant(self, tenant_id: str) -> Optional[TierConfig]:
        """Obtiene la configuración completa del tier para un tenant específico."""
        try:
            redis_client = await self._redis_pool.get_client()
            
            # 1. Obtener el nombre del tier del tenant
            tenant_tier_key = self._get_tenant_tier_key(tenant_id)
            tier_name = await redis_client.get(tenant_tier_key)
            if not tier_name:
                logger.warning(f"No se encontró el tier para el tenant '{tenant_id}'.")
                return None

            # 2. Obtener la configuración para ese tier
            tier_config_key = self._get_tier_config_key(tier_name)
            config_json = await redis_client.get(tier_config_key)
            if not config_json:
                logger.error(f"No se encontró la configuración para el tier '{tier_name}'.")
                return None

            return TierConfig.model_validate_json(config_json)
        except Exception as e:
            logger.error(f"Error al obtener la configuración del tier para '{tenant_id}': {e}", exc_info=True)
            return None

    async def get_tenant_usage(self, tenant_id: str) -> TenantUsage:
        """Obtiene el uso actual de todos los recursos para un tenant desde Redis."""
        usage_records: Dict[str, UsageRecord] = {}
        try:
            redis_client = await self._redis_pool.get_client()
            usage_key = self._get_tenant_usage_key(tenant_id)
            
            # HGETALL devuelve un diccionario de strings, hay que convertir los valores
            raw_usage = await redis_client.hgetall(usage_key)
            
            for resource, amount_str in raw_usage.items():
                usage_records[resource] = UsageRecord(
                    amount=float(amount_str),
                    last_updated=datetime.now(timezone.utc) # Nota: Redis no almacena este timestamp
                )
        except Exception as e:
            logger.error(f"Error al obtener el uso para el tenant '{tenant_id}': {e}", exc_info=True)
        
        return TenantUsage(tenant_id=tenant_id, usage_records=usage_records)

    async def increment_usage_counter(self, tenant_id: str, resource: str, amount: float = 1.0) -> None:
        """Incrementa un contador de uso en Redis de forma atómica."""
        try:
            redis_client = await self._redis_pool.get_client()
            usage_key = self._get_tenant_usage_key(tenant_id)
            await redis_client.hincrbyfloat(usage_key, resource, amount)
        except Exception as e:
            logger.error(
                f"Error al incrementar el contador para tenant '{tenant_id}', recurso '{resource}': {e}",
                exc_info=True
            )

