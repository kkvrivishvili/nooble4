# Estándar de Gestión de Tiers - Interacción Downstream y Worker (`standart_tiers_downstream.md`)

Este documento describe cómo los servicios downstream (Agent Execution Service, Query Service, Embedding Service, Ingestion Service, Conversation Service) y un worker dedicado (`UsageUpdateWorker`) interactúan con el sistema de gestión de tiers. El enfoque principal de los servicios downstream es reportar el uso de recursos, mientras que el worker se encarga de actualizar los contadores persistentes.

## 1. Objetivos de la Interacción Downstream

*   **Contabilización Precisa:** Asegurar que el consumo de recursos por parte de los tenants se registre de manera fiable y oportuna.
*   **Desacoplamiento:** Permitir que los servicios downstream se centren en su lógica de negocio principal, delegando la actualización de contadores a un sistema asíncrono.
*   **Resiliencia:** La publicación asíncrona de actualizaciones de uso minimiza el impacto de fallos temporales en el sistema de contabilización sobre la funcionalidad principal del servicio.

## 2. Integración de Componentes Comunes en Servicios Downstream

Los servicios downstream que consumen recursos limitados por tier integrarán:

*   De `common.tiers.tiers_constants`:
    *   `TierResourceKey` (Enum) - para identificar qué recurso se está consumiendo.
*   De `common.tiers.usage_service`:
    *   `publish_usage_update(tenant_id: str, resource_key: TierResourceKey, amount: int = 1)`

Los servicios recibirán el `tenant_id` a través de la `DomainAction` entrante y/o el `ExecutionContext` asociado.

## 3. Lógica de Reporte de Uso en Servicios Downstream

1.  **Identificación del Punto de Consumo:** Cada servicio debe identificar los puntos en su código donde un recurso limitado por tier es efectivamente consumido. Esto ocurre típicamente *después* de que la operación principal del servicio se ha completado con éxito.

2.  **Llamada a `publish_usage_update`:**
    *   Una vez que el recurso ha sido consumido, el servicio llamará a:
        `await publish_usage_update(tenant_id, relevant_TierResourceKey, amount_consumed)`
    *   `tenant_id`: Obtenido de la `DomainAction` o `ExecutionContext`.
    *   `relevant_TierResourceKey`: El `TierResourceKey` específico que corresponde al recurso consumido.
    *   `amount_consumed`: Generalmente `1`, pero puede ser mayor si la acción consume múltiples unidades de un recurso (ej. `EMBEDDINGS_BATCH_SIZE` podría ser el número de textos procesados).

3.  **Manejo de Errores en la Publicación:**
    *   La función `publish_usage_update` (según `standart_tiers_common.md`) ya maneja internamente los errores de publicación (ej. problemas de conexión con Redis para la cola) y los loguea, pero no relanza la excepción para no interrumpir el flujo principal del servicio. Esto es una decisión de diseño para priorizar la finalización de la tarea del servicio.

**Ejemplos de Reporte de Uso:**

*   **Query Service (QS):** Después de generar y retornar exitosamente una respuesta a una query.
    ```python
    # En el handler de Query Service, tras una query exitosa
    # ... lógica de la query ...
    await publish_usage_update(tenant_id, TierResourceKey.QUERIES_PER_HOUR, 1) 
    ```
*   **Embedding Service (ES):** Después de generar embeddings para un lote de textos.
    ```python
    # En el handler de Embedding Service, tras generar N embeddings
    # ... lógica de embeddings ...
    num_texts = len(request_data.texts) # Ejemplo
    await publish_usage_update(tenant_id, TierResourceKey.EMBEDDINGS_BATCH_SIZE, num_texts) # O una clave más específica si es necesario
    ```
*   **Agent Execution Service (AES):** Si una ejecución de agente cuenta como una "unidad de trabajo" específica o consume un recurso particular.
    ```python
    # En AES, si una ejecución completa cuenta como una "acción de agente"
    # ... lógica de ejecución de agente ...
    # await publish_usage_update(tenant_id, TierResourceKey.AGENT_ACTIONS_PER_DAY, 1) # Si existiera tal TierResourceKey
    ```
    La granularidad exacta de qué constituye un "uso" a reportar por AES dependerá de la definición de los `TierResourceKey`.

**Importante:** Los servicios downstream **NO realizan validación de tiers**. Asumen que la solicitud ya ha sido validada por AOS. Su única responsabilidad relacionada con tiers es reportar el uso.

## 4. `UsageUpdateWorker`

Se creará un nuevo worker (`UsageUpdateWorker`) cuya única responsabilidad es procesar los mensajes de actualización de uso.

*   **Consumo de la Cola:**
    *   El worker escuchará la cola definida en `settings.TIER_USAGE_UPDATE_QUEUE_NAME` (ej. `"nooble4:dev:common:queues:usage_updates"`) utilizando `BRPOP` (o una variante asíncrona).

*   **Procesamiento de Mensajes:**
    1.  Al recibir un mensaje, lo deserializará de JSON al modelo Pydantic `UsageUpdateMessage` (definido en `common.tiers.usage_service`).
    2.  Obtendrá una conexión a Redis usando `await common.redis_pool.get_redis_pool()`.
    3.  Construirá la clave Redis para el contador usando la función `_build_redis_key(tenant_id, resource_key, time_window_dt)` (esta función puede ser importada de `common.tiers.usage_service` o replicada si es necesario para el worker).
        *   `tenant_id` y `resource_key` vienen del `UsageUpdateMessage`.
        *   `time_window_dt` (del `UsageUpdateMessage.timestamp_utc`) es crucial para recursos con ventana de tiempo (ej. `QUERIES_PER_HOUR`).
    4.  Incrementará el contador en Redis: `await redis_client.incrby(key, message.amount)`.
    5.  **Gestión de Expiración (TTL):** Si el `resource_key` corresponde a un límite con ventana de tiempo, el worker debe establecer o actualizar el `EXPIRE` de la clave Redis.
        *   Ejemplo para `QUERIES_PER_HOUR`: El TTL podría ser `3600 segundos` (1 hora) más un pequeño buffer (ej. 5-10 minutos) para asegurar que la clave no expire prematuramente justo antes del final de la hora. El TTL se calcula desde el inicio de la ventana horaria.
        *   La lógica para determinar el TTL correcto basado en `resource_key` y `timestamp_utc` residirá en el worker.
    6.  Registrará la operación (éxito o error).

*   **Estructura del Worker:**
    *   Puede seguir un patrón similar a otros workers del sistema (un bucle principal, manejo de señales para cierre, etc.), pero no necesariamente heredará de `BaseWorker` si este está muy acoplado al procesamiento de `DomainAction`.
    *   Será un proceso independiente.

*   **Manejo de Errores en el Worker:**
    *   Errores de deserialización, conexión a Redis, etc., deben ser logueados.
    *   Considerar una estrategia para mensajes que fallan repetidamente (ej. mover a una Dead Letter Queue después de N intentos), aunque para la contabilización de uso, si un mensaje no se puede procesar, podría ser aceptable perder esa actualización específica si la alternativa es bloquear la cola.

*   **Idempotencia:**
    *   `INCRBY` es atómico. Si el worker se reinicia y reprocesa un mensaje de la cola (si `BRPOP` no fue seguido de un `LREM` o similar, o si el mensaje no fue eliminado antes del crash), podría haber doble contabilización.
    *   Para una primera implementación, se puede asumir que la probabilidad de esto es baja y el impacto aceptable. Mejoras futuras podrían incluir mecanismos de deduplicación si se observa como un problema.

## 5. Configuración

*   `settings.TIER_USAGE_TRACKING_ENABLED`: Controla si `publish_usage_update` realmente publica en la cola. El `UsageUpdateWorker` solo se ejecutará si esta variable está a `True` o se desplegará condicionalmente.
*   `settings.TIER_USAGE_UPDATE_QUEUE_NAME`: Define la cola Redis que el worker consume y a la que los servicios publican.
