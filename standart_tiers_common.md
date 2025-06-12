# Estándar de Gestión de Tiers - Componentes Comunes (`standart_tiers_common.md`)

Este documento describe los componentes comunes del sistema de gestión de tiers de Nooble4. Estos componentes residirán en el paquete `common/tiers` y proporcionarán la base para la validación de límites en el Agent Orchestrator Service (AOS) y la contabilización de uso en los servicios downstream.

## 1. Objetivos de los Componentes Comunes

*   **Definición Centralizada:** Proveer una única fuente de verdad para los nombres de los tiers y sus límites estáticos.
*   **Abstracción de Contabilización:** Ofrecer una interfaz simple para que los servicios interactúen con el sistema de contabilización de uso, independientemente de su implementación subyacente (ej. Redis).
*   **Reusabilidad:** Crear módulos que puedan ser importados y utilizados por múltiples servicios (AOS y servicios downstream) sin duplicación de código.
*   **Testabilidad:** Facilitar las pruebas unitarias de la lógica de tiers.

## 2. Componentes del Módulo `common/tiers`

### 2.1. Constantes de Tiers (`common/tiers/tiers_constants.py`)

Este archivo define la estructura y los valores estáticos de los tiers y sus límites.

*   **`TierName(str, Enum)`**: Enumeración para los nombres de los tiers.
    ```python
    # common/tiers/tiers_constants.py
    from enum import Enum

    class TierName(str, Enum):
        FREE = "free"
        ADVANCE = "advance"
        PROFESSIONAL = "professional"
        AGENCY = "agency"
        ENTERPRISE = "enterprise"
    ```

*   **`TierResourceKey(str, Enum)`**: Enumeración para las claves de los recursos/límites. Esto ayuda a evitar errores tipográficos y mejora la legibilidad.
    ```python
    # common/tiers/tiers_constants.py (continuación)
    class TierResourceKey(str, Enum):
        # Límites numéricos
        MAX_AGENTS = "max_agents"
        MAX_COLLECTIONS_PER_AGENT = "max_collections_per_agent"
        MAX_DOCUMENTS_PER_COLLECTION = "max_documents_per_collection" 
        QUERIES_PER_HOUR = "queries_per_hour"
        EMBEDDINGS_BATCH_SIZE = "embeddings_batch_size"
        EMBEDDINGS_TEXT_LENGTH = "embeddings_text_length"
        # ... otros límites numéricos

        # Límites de listas (ej. modelos permitidos)
        ALLOWED_LLM_MODELS = "allowed_llm_models"
        ALLOWED_EMBEDDING_MODELS = "allowed_embedding_models"
        # ... otros límites de listas

        # Flags booleanos para características
        CAN_USE_CUSTOM_PROMPTS = "can_use_custom_prompts"
        CAN_PERSIST_CONVERSATIONS = "can_persist_conversations"
        # ... otros flags de características
    ```

*   **`TierLimitSettings(BaseModel)`**: Modelo Pydantic para definir la estructura de los límites de un tier específico. Esto asegura que todos los tiers definan los mismos parámetros y con los tipos correctos.
    ```python
    # common/tiers/tiers_constants.py (continuación)
    from typing import List, Optional, Union, Dict # Asegurar Dict
    from pydantic import BaseModel, Field

    class TierLimitSettings(BaseModel):
        # Límites numéricos (ejemplos)
        max_agents: int = Field(..., description="Número máximo de agentes permitidos.")
        queries_per_hour: int = Field(..., description="Número máximo de queries por hora.")
        # ... otros campos numéricos correspondientes a TierResourceKey

        # Límites de listas (ejemplos)
        allowed_llm_models: List[str] = Field(default_factory=list, description="Lista de modelos LLM permitidos.")
        # ... otros campos de lista

        # Flags booleanos (ejemplos)
        can_use_custom_prompts: bool = Field(False, description="Si el tier puede usar prompts personalizados.")
        # ... otros campos booleanos

        class Config:
            extra = "forbid" # Para asegurar que no se añadan campos no definidos
    ```

*   **`TIER_LIMITS: Dict[TierName, TierLimitSettings]`**: Diccionario principal que mapea cada `TierName` a su instancia de `TierLimitSettings`.
    ```python
    # common/tiers/tiers_constants.py (continuación)
    # from typing import Dict # Ya importado arriba

    TIER_LIMITS: Dict[TierName, TierLimitSettings] = {
        TierName.FREE: TierLimitSettings(
            max_agents=1,
            queries_per_hour=100,
            allowed_llm_models=["default-gpt-3.5"],
            can_use_custom_prompts=False
            # ... inicializar todos los demás campos definidos en TierLimitSettings
        ),
        TierName.ADVANCE: TierLimitSettings(
            max_agents=5,
            queries_per_hour=500,
            allowed_llm_models=["default-gpt-3.5", "advanced-model-1"],
            can_use_custom_prompts=True
            # ... inicializar todos los demás campos
        ),
        # ... definiciones para PROFESSIONAL, AGENCY, ENTERPRISE
    }
    ```

### 2.2. Servicio de Gestión de Uso (`common/tiers/usage_service.py`)

Este módulo abstrae la lógica de consulta de límites estáticos y la interacción con el sistema de contabilización de uso (Redis).

```python
# common/tiers/usage_service.py (Conceptual)
import datetime
from typing import Any, Optional, Union, List
from pydantic import BaseModel 

from common.redis_pool import get_redis_pool 
# from common.utils.queue_manager import QueueManager # Se usará redis_client.lpush directamente por ahora
from common.utils.logging_utils import NoobleLogger 
from common.config import settings # Para TIER_USAGE_TRACKING_ENABLED y nombre de cola

from .tiers_constants import TierName, TierResourceKey, TIER_LIMITS, TierLimitSettings

logger = NoobleLogger(__name__) 

# Nombre de la cola para actualizaciones de uso, definido en settings.py
# Ejemplo: USAGE_UPDATE_QUEUE_NAME = "nooble4:dev:common:queues:usage_updates"
USAGE_UPDATE_QUEUE_NAME = settings.TIER_USAGE_UPDATE_QUEUE_NAME 

# --- Funciones para Consulta de Límites (Usadas principalmente por AOS) ---

def get_tier_settings(tier: TierName) -> Optional[TierLimitSettings]:
    """Devuelve el objeto TierLimitSettings completo para un tier dado."""
    return TIER_LIMITS.get(tier)

def get_static_limit(tier: TierName, resource_key: TierResourceKey) -> Any:
    """
    Recupera un límite estático específico para un tier y recurso.
    Devuelve None si el tier o el recurso no están definidos.
    """
    tier_settings = get_tier_settings(tier)
    if tier_settings:
        if hasattr(tier_settings, resource_key.value):
            return getattr(tier_settings, resource_key.value)
        else:
            logger.warning(f"Resource key '{resource_key.value}' no encontrado en TierLimitSettings para el tier '{tier.value}'.")
            return None 
    logger.warning(f"Tier '{tier.value}' no encontrado en TIER_LIMITS.")
    return None

async def get_current_usage(tenant_id: str, resource_key: TierResourceKey, time_window_dt: Optional[datetime.datetime] = None) -> int:
    """
    Consulta Redis para obtener el uso actual del tenant para el recurso.
    Devuelve 0 si no hay registro o si TIER_USAGE_TRACKING_ENABLED es False.
    """
    if not settings.TIER_USAGE_TRACKING_ENABLED:
        return 0

    redis_client = await get_redis_pool() # Renombrado para claridad
    key = _build_redis_key(tenant_id, resource_key, time_window_dt)
    
    current_value = await redis_client.get(key)
    return int(current_value) if current_value else 0

async def is_limit_exceeded(
    tenant_id: str, 
    tier: TierName, 
    resource_key: TierResourceKey, 
    requested_value: Union[int, str] = 1, 
    current_dt: Optional[datetime.datetime] = None
) -> bool:
    """
    Verifica si el límite para un recurso se excede o no se cumple.
    """
    static_limit_value = get_static_limit(tier, resource_key)

    if static_limit_value is None:
        logger.error(f"Límite estático no definido para tier '{tier.value}', recurso '{resource_key.value}'. Denegando por defecto.")
        return True 

    if isinstance(static_limit_value, bool): 
        return not static_limit_value 
    
    elif isinstance(static_limit_value, list): 
        if not isinstance(requested_value, str):
            logger.error(f"Tipo de 'requested_value' incorrecto para lista de permitidos. Se esperaba str, se obtuvo {type(requested_value)}.")
            return True 
        return requested_value not in static_limit_value 
        
    elif isinstance(static_limit_value, (int, float)): 
        if not isinstance(requested_value, (int, float)):
            logger.error(f"Tipo de 'requested_value' incorrecto para límite numérico. Se esperaba int/float, se obtuvo {type(requested_value)}.")
            return True 
        
        current_usage_val = await get_current_usage(tenant_id, resource_key, current_dt or datetime.datetime.now(datetime.timezone.utc))
        return (current_usage_val + requested_value) > static_limit_value
    
    else:
        logger.error(f"Tipo de límite estático no manejado: {type(static_limit_value)} para recurso '{resource_key.value}'.")
        return True 

# --- Funciones para Actualización de Uso (Usadas por Servicios Downstream vía Publicación en Cola) ---

class UsageUpdateMessage(BaseModel):
    """Modelo Pydantic para los mensajes enviados a la cola de actualización de uso."""
    tenant_id: str
    resource_key: TierResourceKey # Usar el Enum directamente
    amount: int = 1
    timestamp_utc: datetime.datetime = Field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc))

async def publish_usage_update(
    tenant_id: str, 
    resource_key: TierResourceKey, 
    amount: int = 1
):
    """
    Publica un mensaje en la cola Redis para que un worker actualice el contador de uso.
    No hace nada si TIER_USAGE_TRACKING_ENABLED es False, solo loguea.
    """
    if not settings.TIER_USAGE_TRACKING_ENABLED:
        logger.info(f"DEV MODE: Tracking de uso deshabilitado. No se publica actualización para {tenant_id}, {resource_key.value}.")
        return

    message = UsageUpdateMessage(
        tenant_id=tenant_id,
        resource_key=resource_key,
        amount=amount
    )
    
    try:
        # Se usa redis_client.lpush directamente para simplificar, en lugar de QueueManager
        redis_client = await get_redis_pool()
        await redis_client.lpush(USAGE_UPDATE_QUEUE_NAME, message.model_dump_json())
        logger.info(f"Publicada actualización de uso en cola '{USAGE_UPDATE_QUEUE_NAME}' para {tenant_id}, {resource_key.value}, cantidad {amount}.")
    except Exception as e:
        logger.error(f"Error al publicar actualización de uso para {tenant_id}, {resource_key.value}: {e}", exc_info=True)

# --- Funciones Helper ---

def _build_redis_key(tenant_id: str, resource_key: TierResourceKey, time_window_dt: Optional[datetime.datetime] = None) -> str:
    """Construye la clave Redis para un contador de uso."""
    key_base = f"usage:{tenant_id}:{resource_key.value}"
    # Lógica de ventana de tiempo más robusta podría mapear TierResourceKey a granularidad (horaria, diaria, etc.)
    if time_window_dt and resource_key == TierResourceKey.QUERIES_PER_HOUR: # Ejemplo simple
        timestamp_bucket = time_window_dt.strftime("%Y%m%d%H")
        return f"{key_base}:{timestamp_bucket}"
    return key_base
```

### 2.3. Excepciones de Tiers (`common/exceptions/tier_exceptions.py`)

```python
# common/exceptions/tier_exceptions.py 
from .base_exceptions import BaseNoobleError 
from ..tiers.tiers_constants import TierName, TierResourceKey # Importar Enums
from typing import Optional # Para typing

class TierLimitExceededError(BaseNoobleError):
    """Excepción lanzada cuando se excede un límite de tier.""" 
    def __init__(self, message: str, error_code: str, resource_key: Optional[TierResourceKey] = None, tier_name: Optional[TierName] = None, status_code: int = 429):
        super().__init__(
            message=message, 
            error_code=error_code, 
            status_code=status_code 
        )
        self.resource_key = resource_key
        self.tier_name = tier_name
```

## 3. Modo Desarrollo (`TIER_USAGE_TRACKING_ENABLED`)

*   Variable de configuración global en `common/config/settings.py`:
    `TIER_USAGE_TRACKING_ENABLED: bool = Field(default=False, env="TIER_USAGE_TRACKING_ENABLED")`
    `TIER_USAGE_UPDATE_QUEUE_NAME: str = Field(default="nooble4:dev:common:queues:usage_updates", env="TIER_USAGE_UPDATE_QUEUE_NAME")`
*   El módulo `common/tiers/usage_service.py` utiliza `TIER_USAGE_TRACKING_ENABLED` para:
    *   Si `False`: `get_current_usage(...)` devuelve `0`; `publish_usage_update(...)` loguea y no publica.
    *   Si `True`: Lógica normal de Redis y publicación en cola.

---
