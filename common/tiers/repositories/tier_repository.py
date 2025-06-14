# common/tiers/repositories/tier_repository.py
import asyncio
from typing import Optional, Dict
from ..models.tier_config import AllTiersConfig, TierLimits
from ..models.usage_models import TenantUsage

# --- Simulación de fuentes de datos ---

# Esto simula un archivo de configuración central (p.ej., tiers.yml)
TIERS_CONFIG_DATA = {
    "tiers": {
        "free": {
            "max_agents": 1,
            "allow_custom_templates": False,
            "max_conversation_history": 10,
            "allow_conversation_persistence": False,
            "max_query_length": 500,
            "allowed_query_models": ["default-model"],
            "max_embedding_batch_size": 16,
            "max_daily_embedding_tokens": 10000,
            "max_file_size_mb": 5,
            "max_daily_documents": 5,
            "rate_limit_per_minute": 20,
        },
        "pro": {
            "max_agents": 10,
            "allow_custom_templates": True,
            "max_conversation_history": 100,
            "allow_conversation_persistence": True,
            "max_query_length": 2000,
            "allowed_query_models": ["default-model", "advanced-model"],
            "max_embedding_batch_size": 128,
            "max_daily_embedding_tokens": 500000,
            "max_file_size_mb": 50,
            "max_daily_documents": 100,
            "rate_limit_per_minute": 120,
        },
    }
}

# Esto simula una tabla de tenants en la BBDD (p.ej., la tabla de usuarios de AMS)
TENANT_TIER_MAPPING = {
    "tenant_free_01": "free",
    "tenant_pro_01": "pro",
    "tenant_unknown": "non_existent_tier",
}

# Esto simula una tabla de contadores de uso en PostgreSQL
TENANT_USAGE_DB: Dict[str, Dict[str, int]] = {}

# Esto simula un caché de Redis para las configuraciones de tiers
TIER_CONFIG_CACHE: Optional[AllTiersConfig] = None

# --- Implementación del Repositorio ---

class TierRepository:
    """Abstracción para acceder a la BBDD de configuraciones/uso (simulado)."""

    async def _load_and_cache_config(self) -> AllTiersConfig:
        """Simula la carga de configuración desde un archivo/BBDD y su cacheo."""
        global TIER_CONFIG_CACHE
        if TIER_CONFIG_CACHE is None:
            print("(Repository) Cargando configuración de tiers por primera vez...")
            await asyncio.sleep(0.01) # Simula I/O
            TIER_CONFIG_CACHE = AllTiersConfig(**TIERS_CONFIG_DATA)
        return TIER_CONFIG_CACHE

    async def get_tier_name_for_tenant(self, tenant_id: str) -> Optional[str]:
        """Simula obtener el nombre del tier de un tenant desde una BBDD de usuarios."""
        print(f"(Repository) Obteniendo tier para el tenant {tenant_id}")
        await asyncio.sleep(0.01) # Simula I/O de BBDD
        return TENANT_TIER_MAPPING.get(tenant_id)

    async def get_tier_limits(self, tier_name: str) -> Optional[TierLimits]:
        """Obtiene los límites para un nombre de tier desde la config cacheada."""
        all_configs = await self._load_and_cache_config()
        return all_configs.tiers.get(tier_name)

    async def get_tenant_usage(self, tenant_id: str) -> TenantUsage:
        """Simula obtener el uso actual de un tenant desde la BBDD de uso."""
        print(f"(Repository) Obteniendo uso para el tenant {tenant_id}")
        await asyncio.sleep(0.01) # Simula I/O de BBDD
        usage_data = TENANT_USAGE_DB.get(tenant_id, {})
        return TenantUsage(
            daily_embedding_tokens=usage_data.get("daily_embedding_tokens", 0),
            daily_documents=usage_data.get("daily_documents", 0),
        )

    async def increment_usage_counter(self, tenant_id: str, resource_key: str, amount: float) -> bool:
        """Simula incrementar un contador de uso en la BBDD (operación atómica)."""
        print(f"(Repository) Incrementando uso para {tenant_id}, recurso {resource_key}, cantidad {amount}")
        
        # Simulación de una transacción de BBDD
        async with asyncio.Lock(): # Previene condiciones de carrera en la simulación
            if tenant_id not in TENANT_USAGE_DB:
                TENANT_USAGE_DB[tenant_id] = {}
            
            current_value = TENANT_USAGE_DB[tenant_id].get(resource_key, 0)
            TENANT_USAGE_DB[tenant_id][resource_key] = current_value + int(amount)
            
            print(f"(Repository) Nuevo valor para {resource_key}: {TENANT_USAGE_DB[tenant_id][resource_key]}")
            await asyncio.sleep(0.02) # Simula I/O de BBDD

        return True

