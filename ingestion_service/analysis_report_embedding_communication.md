# Análisis de la Comunicación con `embedding_service` en `ingestion_service`

Fecha del Análisis: 2025-06-18

## 1. Introducción

Este documento analiza el patrón de comunicación pseudo-asíncrona entre `ingestion_service` y `embedding_service`. El `ingestion_service` solicita la generación de embeddings para los chunks de documentos y procesa los resultados de manera asíncrona a través de un mecanismo de callback utilizando Redis Streams.

## 2. Flujo de Comunicación

El proceso de comunicación se puede desglosar en los siguientes pasos:

### 2.1. Envío de Solicitud de Embedding (`IngestionService._send_chunks_for_embedding`)

1.  **Creación de la Acción**: Se crea una `DomainAction` (`embedding_action`) con `action_type = "embedding.batch.process"`. Esta acción contiene:
    *   Los textos de los chunks a embeber.
    *   Los IDs de los chunks (`chunk_ids`).
    *   El `task_id` original de la tarea de ingestión.
    *   Metadatos como `origin_service`, `trace_id`, etc.

2.  **Envío con Callback**: La acción se envía utilizando `self.service_redis_client.send_action_async_with_callback()`:
    ```python
    await self.service_redis_client.send_action_async_with_callback(
        embedding_action,
        callback_event_name="ingestion.embedding_result"
    )
    ```
    - `BaseRedisClient` (del cual `service_redis_client` es una instancia) se encarga de:
        - Generar un `correlation_id` único.
        - Establecer el campo `reply_to_stream` en los metadatos de `embedding_action` a un nombre de stream derivado de `callback_event_name` (ej. `ingestion_service:ingestion.embedding_result`).
        - Publicar `embedding_action` en el stream correspondiente para que `embedding_service` lo consuma (ej. `embedding_service:embedding.batch.process`).

3.  **Almacenamiento Temporal de Contexto**: De forma crucial, antes de que `_send_chunks_for_embedding` termine, se guarda una copia completa del `ChunkModel` (que contiene metadatos además del texto) en Redis con un TTL (Time To Live):
    ```python
    for chunk in chunks:
        await self.direct_redis_conn.setex(
            f"chunk:{chunk.chunk_id}",
            3600,  # 1 hora
            chunk.model_dump_json()
        )
    ```
    Esto es necesario porque la `embedding_action` solo lleva los textos y los IDs. El contexto completo del chunk se recuperará cuando llegue el resultado del embedding.

### 2.2. Procesamiento en `embedding_service` (Asumido)

1.  `embedding_service` consume la `DomainAction` de tipo `embedding.batch.process`.
2.  Genera los embeddings para los textos proporcionados.
3.  Construye una nueva `DomainAction` de respuesta (resultado del embedding).
    *   El `action_type` será `ingestion.embedding_result` (o lo que corresponda al `callback_event_name`).
    *   Los `data` contendrán el `task_id` original, los `chunk_ids` y los `embeddings` generados.
    *   Se incluirá el `correlation_id` de la solicitud original.
4.  Envía esta acción de respuesta al stream especificado en el campo `reply_to_stream` de la solicitud original (ej. `ingestion_service:ingestion.embedding_result`).

### 2.3. Recepción y Procesamiento del Callback (`IngestionWorker` y `IngestionService`)

1.  **Escucha del Worker**: `IngestionWorker` está escuchando en el stream `ingestion_service:ingestion.embedding_result` (entre otros streams configurados para el servicio).
2.  **Manejo por el Worker**: Cuando la acción de respuesta del embedding llega, `IngestionWorker._handle_action()` es invocado.
3.  **Delegación al Servicio**: `_handle_action` llama a `self.ingestion_service.process_action(action_respuesta_embedding)`.
4.  **Enrutamiento en el Servicio**: `IngestionService.process_action` inspecciona el `action.action_type`. Para `ingestion.embedding_result` (que se convierte en `embedding_result` tras el split), la acción se enruta al método `self._handle_embedding_result(action)`.

### 2.4. Manejo del Resultado del Embedding (`IngestionService._handle_embedding_result`)

1.  **Extracción de Datos**: Se extraen `task_id`, `chunk_ids`, y `embeddings` de `action.data`.
2.  **Carga del Estado de la Tarea**: Se carga el estado de `IngestionTask` usando `self.task_state_manager.load_state(f"task:{task_id}")`.
3.  **Procesamiento de Embeddings Individuales**:
    *   Para cada `chunk_id` y su `embedding` correspondiente:
        *   Se recupera el `ChunkModel` completo (que fue almacenado temporalmente) desde Redis: `await self.direct_redis_conn.get(f"chunk:{chunk_id}")`.
        *   Se reconstruye el `ChunkModel` y se le asigna el `embedding`.
        *   Se elimina el `ChunkModel` temporal de Redis: `await self.direct_redis_conn.delete(f"chunk:{chunk_id}")`.
4.  **Almacenamiento en Qdrant**: Los `ChunkModel` (ahora con embeddings) se envían a `self.qdrant_handler.store_chunks()`.
5.  **Actualización del Estado de la Tarea**: Se actualiza `task.processed_chunks`.
6.  **Verificación de Completitud**: Se comprueba si todos los chunks de la tarea han sido procesados (`task.processed_chunks >= task.total_chunks`).
    *   Si está completa, el estado de la tarea se actualiza a `COMPLETED`.
    *   Si no, se actualiza el progreso.
7.  **Guardado del Estado y Notificación**: Se guarda el estado actualizado de `IngestionTask` y se envía una notificación de progreso vía WebSocket.

## 3. Características Clave del Patrón

- **Desacoplamiento**: `ingestion_service` no espera bloqueado a que `embedding_service` termine. La comunicación es asíncrona.
- **Mecanismo de Callback**: Redis Streams y `BaseRedisClient` facilitan el mecanismo de callback, gestionando `reply_to_stream` y `correlation_id`.
- **Gestión de Estado para Contexto**: El almacenamiento temporal de `ChunkModel` en Redis es vital. Permite a `ingestion_service` reconstituir el contexto completo de un chunk cuando recibe el resultado del embedding, ya que el callback solo trae IDs y los vectores de embedding.
- **Robustez**: El sistema maneja el ciclo de vida de la tarea y actualiza su estado en varios puntos, incluyendo el manejo de errores potenciales durante el proceso.

## 4. Conclusión

La comunicación entre `ingestion_service` y `embedding_service` está bien implementada utilizando un patrón de pseudo-asincronía con callbacks sobre Redis Streams. El uso de `BaseRedisClient` simplifica la mecánica de la comunicación. Una parte fundamental y bien gestionada de este patrón es el almacenamiento temporal del contexto del chunk en Redis, lo que permite al `ingestion_service` manejar correctamente los resultados asíncronos del `embedding_service` y continuar con el flujo de ingestión.

Este patrón es eficiente y adecuado para tareas que pueden tomar tiempo, como la generación de embeddings, permitiendo que el `ingestion_service` siga siendo responsivo y maneje múltiples tareas concurrentemente.
