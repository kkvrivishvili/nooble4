# Estándar de Clientes Inter-Servicios en Nooble4

> **Última Revisión:** 15 de Junio de 2025
> **Estado:** Implementado y Activo.
> **Clase de Referencia:** `common.clients.base_redis_client.BaseRedisClient`

## 1. Introducción

Este documento establece el estándar para la implementación de clientes de comunicación inter-servicios dentro del ecosistema Nooble4. El objetivo es asegurar la coherencia, robustez y mantenibilidad de toda la comunicación interna, aprovechando Redis Streams para envíos asíncronos y Redis Lists para respuestas y callbacks.

## 2. Protocolo de Comunicación: Redis Asíncrono con Streams y Listas

Toda la comunicación interna entre microservicios **DEBE** realizarse a través de Redis, utilizando un cliente asíncrono (`redis.asyncio`). Los patrones de comunicación se implementan de la siguiente manera:

*   **Envío de Acciones (Solicitudes):** Se utiliza **Redis Streams** (comando `XADD`). Esto permite que múltiples workers de un servicio consuman de un mismo stream (patrón de consumidor competitivo).
*   **Recepción de Respuestas (Pseudo-Síncrono):** Se utiliza **Redis Lists** (comando `BRPOP` sobre una cola de respuesta única y temporal).
*   **Recepción de Callbacks (Asíncrono con Callback):** Se utiliza **Redis Lists** (escucha en una cola de callback específica).

Las llamadas HTTP directas quedan reservadas exclusivamente para APIs expuestas a clientes externos (ej. gateways).

## 3. La Clase Base: `BaseRedisClient`

Se ha implementado una clase `BaseRedisClient` en `common/clients/base_redis_client.py` que centraliza toda la lógica de comunicación. **Todos los clientes específicos de servicio DEBEN heredar de esta clase.**

### 3.1. Responsabilidades

*   **Gestión de Conexión**: Recibe un cliente `redis.asyncio.Redis` ya inicializado (generalmente de un `RedisManager`), promoviendo la reutilización de conexiones.
*   **Serialización/Deserialización**: Utiliza los modelos Pydantic (`DomainAction`, `DomainActionResponse`) para serializar y validar todos los mensajes.
*   **Nomenclatura de Streams y Colas**: Abstrae la lógica de generación de nombres de streams de acción y colas de respuesta/callback utilizando `QueueManager`.
*   **Implementación de Patrones de Comunicación**: Provee métodos claros y robustos para los patrones de comunicación estándar.

### 3.2. Métodos Principales

#### a) `async def send_action_async(self, action: DomainAction)`

Para comunicación "fire-and-forget".

**Cómo funciona**:
1.  El cliente asigna el `origin_service` a la `DomainAction` (si no está ya presente).
2.  Utiliza `QueueManager` para determinar el nombre del **Redis Stream** del servicio destino (basado en `action.target_service`).
3.  Envía la `DomainAction` (serializada como JSON) a este stream usando el comando `XADD`. El payload se almacena en un campo del mensaje del stream (e.g., `'data'`).

**Cuándo usarlo**: Para notificaciones, eventos o tareas que no requieren una confirmación inmediata y donde el procesamiento puede ser manejado por uno de varios workers en el servicio destino.

**Ejemplo**:
```python
# En un worker...
from common.models.actions import DomainAction
import uuid

# Suponiendo que self.redis_client es una instancia de BaseRedisClient
# y self.service_name es el nombre del servicio actual.
action = DomainAction(
    action_id=str(uuid.uuid4()),
    action_type="ingestion.document.processed",
    origin_service=self.service_name, # BaseRedisClient puede setearlo si es None
    target_service="downstream_processing_service",
    tenant_id="some_tenant",
    data={"document_id": "doc_123", "status": "success"}
)
await self.redis_client.send_action_async(action)
```

#### b) `async def send_action_pseudo_sync(self, action: DomainAction, timeout: int = 30) -> Optional[DomainActionResponse]`

Para comunicación de solicitud/respuesta.

**Cómo funciona**:
1.  Asegura que la `DomainAction` tenga un `correlation_id`.
2.  Utiliza `QueueManager` para generar un nombre de **cola de respuesta Redis (Lista)** único para esta solicitud, usualmente incorporando el `correlation_id`.
3.  Asigna este nombre de cola al campo `action.callback_queue_name`.
4.  Utiliza `QueueManager` para determinar el nombre del **Redis Stream** del servicio destino (basado en `action.target_service`).
5.  Envía la `DomainAction` a este stream usando `XADD`.
6.  Realiza un `await` en un `BRPOP` sobre la cola de respuesta (Lista), esperando hasta que llegue la `DomainActionResponse` o se cumpla el `timeout`.
7.  Deserializa y valida la respuesta (`DomainActionResponse`). Retorna la respuesta o `None` en caso de timeout/error.

**Cuándo usarlo**: Cuando un servicio necesita un resultado de otro para poder continuar su propio flujo y la respuesta se espera en un tiempo razonable.

**Ejemplo**:
```python
# En un worker que necesita la configuración de un agente
from common.models.actions import DomainAction, DomainActionResponse
import uuid

# Suponiendo que self.redis_client es una instancia de BaseRedisClient
# y self.service_name es el nombre del servicio actual.
action = DomainAction(
    action_id=str(uuid.uuid4()),
    action_type="management.agent.get_config",
    origin_service=self.service_name,
    target_service="agent_management_service",
    tenant_id="some_tenant",
    data={"agent_id": "agent_abc"}
)
response: Optional[DomainActionResponse] = await self.redis_client.send_action_pseudo_sync(action)

if response and response.success:
    agent_config = response.data # response.data será un modelo Pydantic específico
    # ... continuar con la lógica
else:
    # ... manejar el error o la ausencia de respuesta
    error_detail = response.error if response else None
    print(f"Error obteniendo config: {error_detail or 'Timeout'}")
```

#### c) `async def send_action_async_with_callback(self, action: DomainAction)`

Para flujos asíncronos complejos donde una operación de larga duración debe notificar su finalización o progreso mediante una nueva `DomainAction` (el callback).

**Cómo funciona**:
1.  El cliente emisor asegura que la `DomainAction` tenga `correlation_id`, `trace_id`, `callback_queue_name` (la **Lista Redis** donde espera el callback) y `callback_action_type`.
2.  Utiliza `QueueManager` para determinar el nombre del **Redis Stream** del servicio destino.
3.  Envía la `DomainAction` inicial a este stream usando `XADD`.
4.  El servicio emisor es responsable de tener un worker o mecanismo escuchando en la `callback_queue_name` (Lista) para la `DomainAction` de callback.
5.  El servicio receptor, al finalizar su tarea o en puntos intermedios, construye una nueva `DomainAction` (el callback) con el `callback_action_type` especificado, propaga `correlation_id` y `trace_id`, y la envía (usando `LPUSH`) a la `callback_queue_name` (Lista) indicada en la acción original.

**Cuándo usarlo**: Para operaciones que exceden un timeout razonable para pseudo-síncrono (ej. > 30-60s), o cuando se esperan múltiples actualizaciones de estado.

## 4. Clientes Específicos de Servicio

Aunque `BaseRedisClient` puede ser usado directamente, se recomienda crear clientes específicos por servicio para mejorar la legibilidad y el encapsulamiento de la lógica de creación de `DomainAction`.

*   **Ubicación**: `service_root/clients/target_service_client.py` (ej. `query_service/clients/embedding_service_client.py` sería un cliente que el `query_service` usa para hablar con `embedding_service`).
*   **Herencia**: `class EmbeddingServiceClient(BaseRedisClient): ...`
*   **Responsabilidad**: Deben proveer métodos de alto nivel que encapsulen la creación de `DomainAction` específicas para el servicio destino. Estos métodos usarán internamente los métodos `send_action_async`, `send_action_pseudo_sync`, o `send_action_async_with_callback` de `BaseRedisClient`.

**Ejemplo de Cliente Específico**:
```python
# En query_service/clients/embedding_service_client.py

from common.clients import BaseRedisClient
from common.models.actions import DomainAction, DomainActionResponse
from common.config import CommonAppSettings # Para tipado
from redis.asyncio import Redis as AIORedis # Para tipado
import uuid
from typing import Optional # Añadido para Optional

class EmbeddingServiceClient(BaseRedisClient):
    TARGET_SERVICE_NAME = "embedding_service" # Constante para el servicio destino

    # El constructor hereda de BaseRedisClient, no necesita redefinirse 
    # a menos que haya lógica adicional.
    # def __init__(self, service_name: str, redis_client: AIORedis, settings: CommonAppSettings):
    #     super().__init__(service_name, redis_client, settings)

    async def get_embeddings(self, texts: list[str], tenant_id: str, session_id: Optional[str] = None) -> Optional[DomainActionResponse]:
        action = DomainAction(
            action_id=str(uuid.uuid4()),
            action_type="embedding.text.generate", # Acción específica del servicio de embedding
            # origin_service se establece por BaseRedisClient con el service_name pasado en su __init__
            target_service=self.TARGET_SERVICE_NAME,
            tenant_id=tenant_id,
            session_id=session_id,
            # data debe ser un modelo Pydantic si es complejo, o un dict simple
            data={"texts": texts} 
        )
        return await self.send_action_pseudo_sync(action)

    async def notify_model_updated(self, model_name: str, tenant_id: str) -> None:
        action = DomainAction(
            action_id=str(uuid.uuid4()),
            action_type="embedding.model.updated_notification",
            target_service=self.TARGET_SERVICE_NAME,
            tenant_id=tenant_id,
            data={"model_name": model_name}
        )
        await self.send_action_async(action)
```

## 5. Gestión de Conexiones con `RedisManager`

La instancia de `redis.asyncio.Redis` que se pasa a `BaseRedisClient` (y a sus subclases) debe ser gestionada por `RedisManager` a nivel de servicio. Esto asegura que la conexión se inicializa correctamente al arrancar el servicio y se cierra de forma ordenada al apagarlo.

Consultar `common/clients/README.md` para más detalles sobre `RedisManager`.

## 6. Pasos de Adopción y Mantenimiento

1.  **Uso de `RedisManager`**: Asegurar que cada servicio inicialice y cierre `RedisManager` y provea la conexión Redis a sus instancias de `BaseRedisClient`.
2.  **Clientes Específicos**: Crear o refactorizar clientes específicos de servicio heredando de `BaseRedisClient` para encapsular la lógica de creación de `DomainAction` y la definición del `target_service`.
3.  **Actualizar Componentes**: Workers, services, y otros componentes que necesiten comunicarse con otros servicios deben usar estos clientes estandarizados.
4.  **Documentación**: Mantener actualizados los `README.md` de cada servicio y este documento para reflejar la arquitectura de clientes y cualquier cambio futuro.
