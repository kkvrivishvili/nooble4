# Gestión de Caché en Nooble4

Este documento describe cómo utilizar el sistema de gestión de caché estandarizado en Nooble4.

## Componentes

### CacheKeyManager

El `CacheKeyManager` es una clase que genera claves de caché estandarizadas para Redis. Sigue un patrón consistente:

```
{prefix}:{environment}:{service_name}:{cache_type}:{context}
```

Por ejemplo:
- `nooble4:dev:agent_execution:history:tenant-123:session-456`
- `nooble4:prod:user_management:config:user:user-789`

### RedisStateManager

El `RedisStateManager` gestiona la persistencia de objetos Pydantic en Redis, manejando la serialización/deserialización y validación.

## Uso Básico

```python
from common.clients.redis.cache_key_manager import CacheKeyManager
from common.clients.redis.redis_state_manager import RedisStateManager
from common.clients.redis.redis_manager import RedisManager
from pydantic import BaseModel

# Modelo de datos
class ConversationHistory(BaseModel):
    messages: list[dict]
    metadata: dict

# Inicialización
redis_manager = RedisManager(app_settings)
redis_conn = redis_manager.get_client()

# Crear gestor de claves de caché
cache_key_manager = CacheKeyManager(
    environment=app_settings.environment,
    service_name=app_settings.service_name
)

# Crear gestor de estado con el gestor de claves
history_manager = RedisStateManager[ConversationHistory](
    redis_conn=redis_conn,
    state_model=ConversationHistory,
    app_settings=app_settings,
    cache_key_manager=cache_key_manager
)

# Generar clave estandarizada
tenant_id = "tenant-123"
session_id = "session-456"
cache_key = cache_key_manager.get_history_key(tenant_id, session_id)

# Usar la clave para operaciones de caché
history = await history_manager.load_state(cache_key)
```

## Tipos de Claves Predefinidas

El `CacheKeyManager` proporciona métodos para generar claves para casos de uso comunes:

- `get_history_key(tenant_id, session_id)`: Para historiales de conversación
- `get_config_key(entity_id, config_type)`: Para configuraciones
- `get_embedding_key(document_id)`: Para embeddings
- `get_custom_key(cache_type, context)`: Para casos personalizados

## Integración con Servicios Existentes

Para integrar el `CacheKeyManager` en servicios existentes:

1. Inicializar el `CacheKeyManager` en el servicio
2. Pasar el `CacheKeyManager` al `RedisStateManager`
3. Usar los métodos del `CacheKeyManager` para generar claves

```python
# En un handler o servicio
def __init__(self, settings, redis_conn):
    # Inicializar CacheKeyManager
    self.cache_key_manager = CacheKeyManager(
        environment=settings.environment,
        service_name=settings.service_name
    )
    
    # Inicializar RedisStateManager con el CacheKeyManager
    self.history_manager = RedisStateManager[ConversationHistory](
        redis_conn=redis_conn,
        state_model=ConversationHistory,
        app_settings=settings,
        cache_key_manager=self.cache_key_manager
    )
    
    # Ejemplo de uso
    async def get_history(self, tenant_id, session_id):
        cache_key = self.cache_key_manager.get_history_key(tenant_id, session_id)
        return await self.history_manager.load_state(cache_key)
```

## Migración Gradual

Para servicios existentes, se recomienda una migración gradual:

1. Añadir el `CacheKeyManager` a los servicios
2. Reemplazar gradualmente las construcciones manuales de claves
3. Mantener compatibilidad con claves existentes durante la transición
