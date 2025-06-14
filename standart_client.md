# Estándar de Clientes Inter-Servicios en Nooble4

> **Última Revisión:** 14 de Junio de 2024
> **Estado:** Aprobado y en implementación.
> **Clase de Referencia:** `common.clients.base_redis_client.BaseRedisClient`

## 1. Introducción

Este documento establece el estándar para la implementación de clientes de comunicación inter-servicios dentro del ecosistema Nooble4. El objetivo es asegurar la coherencia, robustez y mantenibilidad de toda la comunicación interna.

## 2. Protocolo de Comunicación: Redis Asíncrono

Toda la comunicación interna entre microservicios **DEBE** realizarse a través de Redis, utilizando un cliente asíncrono (`redis.asyncio`). Esto aplica a todos los patrones de comunicación:

*   **Pseudo-Síncrono (Solicitud/Respuesta)**
*   **Asíncrono (Fire-and-Forget)**
*   **Asíncrono con Callback**

Las llamadas HTTP directas quedan reservadas exclusivamente para APIs expuestas a clientes externos (ej. gateways).

## 3. La Clase Base: `BaseRedisClient`

Se ha implementado una clase `BaseRedisClient` en `common/clients/base_redis_client.py` que centraliza toda la lógica de comunicación. **Todos los clientes específicos de servicio DEBEN heredar de esta clase.**

### 3.1. Responsabilidades

*   **Gestión de Conexión**: Recibe un cliente `redis.asyncio.Redis` ya inicializado, promoviendo la reutilización de conexiones.
*   **Serialización/Deserialización**: Utiliza los modelos Pydantic (`DomainAction`, `DomainActionResponse`) para serializar y validar todos los mensajes.
*   **Nomenclatura de Colas**: Abstrae la lógica de generación de nombres de colas utilizando `QueueManager`.
*   **Implementación de Patrones de Comunicación**: Provee métodos claros y robustos para los patrones de comunicación estándar.

### 3.2. Métodos Principales

#### a) `send_action_async(action: DomainAction)`

Para comunicación "fire-and-forget". El cliente construye el nombre de la cola de acción, asigna el `origin_service` y envía el mensaje sin esperar respuesta.

**Cuándo usarlo**: Para notificaciones, eventos o tareas que no requieren una confirmación inmediata.

**Ejemplo**:
```python
# En un worker...
from common.models.actions import DomainAction

action = DomainAction(
    action_type="ingestion.document.processed",
    data={"document_id": "doc_123", "status": "success"}
)
await self.redis_client.send_action_async(action)
```

#### b) `send_action_pseudo_sync(action: DomainAction, timeout: int = 30) -> DomainActionResponse`

Para comunicación de solicitud/respuesta.

**Cómo funciona**:
1.  Asegura que la `DomainAction` tenga un `correlation_id`.
2.  Genera un nombre de cola de respuesta único para esta solicitud usando el `correlation_id`.
3.  Asigna este nombre de cola al campo `callback_queue_name` de la `DomainAction`.
4.  Envía la acción a la cola del servicio destino.
5.  Realiza un `await` en un `BRPOP` sobre la cola de respuesta, esperando hasta que llegue la `DomainActionResponse` o se cumpla el `timeout`.
6.  Valida la respuesta y la retorna.

**Cuándo usarlo**: Cuando un servicio necesita un resultado de otro para poder continuar su propio flujo.

**Ejemplo**:
```python
# En un worker que necesita la configuración de un agente
from common.models.actions import DomainAction

action = DomainAction(
    action_type="management.agent.get_config",
    data={"agent_id": "agent_abc"}
)
response = await self.redis_client.send_action_pseudo_sync(action)

if response.success:
    agent_config = response.data
    # ... continuar con la lógica
else:
    # ... manejar el error
```

#### c) `send_action_async_with_callback(...)`

Para flujos asíncronos complejos donde una operación de larga duración debe notificar su finalización.

**Cómo funciona**:
1.  El cliente emisor especifica el nombre de la cola de callback en el campo `callback_queue_name` de la `DomainAction`.
2.  El servicio receptor, al finalizar su tarea, utiliza ese `callback_queue_name` para enviar una `DomainAction` de vuelta.

**Cuándo usarlo**: Para operaciones que exceden un timeout razonable (ej. > 30s), como el procesamiento de grandes documentos o entrenamientos de modelos.

## 4. Clientes Específicos

*   **Ubicación**: `service_root/clients/target_service_client.py`
*   **Herencia**: `class EmbeddingServiceClient(BaseRedisClient): ...`
*   **Responsabilidad**: Deben proveer métodos de alto nivel que encapsulen la creación de `DomainAction` específicas. Estos métodos usarán internamente `send_action_async` o `send_action_pseudo_sync`.

**Ejemplo de Cliente Específico**:
```python
# embedding_service/clients/embedding_client.py
from common.clients import BaseRedisClient
from common.models.actions import DomainAction, DomainActionResponse

class EmbeddingServiceClient(BaseRedisClient):

    async def get_embeddings(self, texts: list[str]) -> DomainActionResponse:
        action = DomainAction(
            action_type="embedding.text.generate",
            data={"texts": texts}
        )
        return await self.send_action_pseudo_sync(action)
```

## 5. Pasos de Adopción

1.  **Refactorizar Clientes Existentes**: Todos los clientes de servicios deben ser refactorizados para heredar de `BaseRedisClient`.
2.  **Eliminar Lógica Duplicada**: La lógica de serialización, gestión de colas y patrones de comunicación debe ser eliminada de los clientes específicos.
3.  **Actualizar Workers**: Los workers que usan estos clientes deben ser actualizados para llamar a los nuevos métodos asíncronos.
4.  **Documentación**: Asegurar que los `README.md` de cada servicio reflejen el uso de esta nueva arquitectura de clientes.
