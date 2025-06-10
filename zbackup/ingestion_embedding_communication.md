# Comunicación entre Ingestion Service y Embedding Service

Esta sección describe cómo el `IngestionService` solicita la generación de embeddings al `EmbeddingService` y cómo recibe los resultados.

## 1. IngestionService (EmbeddingClient) -> EmbeddingService (API)

Esta interacción detalla cómo el `IngestionService` envía los chunks de texto al `EmbeddingService` para su vectorización.

*   **Flujo General**: El `IngestionWorker`, después de procesar y fragmentar un documento, utiliza su `EmbeddingClient` para enviar una solicitud HTTP al `EmbeddingService`.
*   **Servicio Emisor**: Ingestion Service
*   **Componente Emisor**: `ingestion_service.clients.EmbeddingClient` (método `generate_embeddings`)
*   **Mecanismo de Envío**: Llamada HTTP POST.
*   **Servicio Receptor**: Embedding Service
*   **Componente Receptor**: Endpoint API del `EmbeddingService` (presumiblemente `POST /api/v1/embeddings/generate`).
*   **URL de Destino**: `f"{settings.EMBEDDING_SERVICE_URL}/api/v1/embeddings/generate"` (configurado en `IngestionService`).
*   **Payload Enviado (JSON, basado en `EmbeddingRequestAction` del `IngestionService`)**:
    ```json
    {
      "document_id": "string",
      "collection_id": "string",
      "tenant_id": "string",
      "chunks": [ { "chunk_id": "string", "text": "string", "metadata": {} } ],
      "model": "string (e.g., text-embedding-ada-002)",
      "task_id": "string (ID de la tarea de ingesta)",
      "callback_queue": "ingestion:callbacks:embedding" // o el valor de settings.EMBEDDING_CALLBACK_QUEUE
    }
    ```
*   **Respuesta HTTP Esperada por `EmbeddingClient`**: `202 Accepted`. Esto significa que el `EmbeddingService` ha recibido la solicitud y la procesará asíncronamente.
*   **Observaciones**:
    *   A diferencia de otras comunicaciones internas que usan Redis directamente para la solicitud, aquí se usa una API HTTP.
    *   El `IngestionService` especifica una `callback_queue` en el payload para que el `EmbeddingService` sepa dónde enviar el resultado.

## 2. EmbeddingService (EmbeddingWorker) -> IngestionService (IngestionWorker)

Esta interacción describe cómo el `EmbeddingService` devuelve los embeddings generados (o un error) al `IngestionService`.

*   **Flujo General**: Después de que el `EmbeddingService` genera los embeddings, envía una acción de callback a la cola especificada por el `IngestionService` en la solicitud original.
*   **Servicio Emisor**: Embedding Service
*   **Componente Emisor**: `embedding_service.workers.EmbeddingWorker` (o la lógica que maneja la acción `embedding.generate.sync` o la solicitud HTTP).
*   **Mecanismo de Envío**: `DomainQueueManager.enqueue_action_to_specific_queue()` (o equivalente, para publicar en una cola específica).
*   **Servicio Receptor**: Ingestion Service
*   **Componente Receptor**: `ingestion_service.workers.IngestionWorker` (método `_handle_embedding_callback` escuchando en `settings.EMBEDDING_CALLBACK_QUEUE`).
*   **Cola de Destino (donde escucha `IngestionWorker`)**: El valor de `settings.EMBEDDING_CALLBACK_QUEUE` del `IngestionService` (e.g., `ingestion:callbacks:embedding`).
*   **Acción/Payload Enviado (Ejemplo basado en `EmbeddingCallbackAction` del `IngestionService`)**:
    ```json
    {
      "task_id": "string (ID original de la tarea de ingesta)",
      "document_id": "string",
      "collection_id": "string",
      "tenant_id": "string",
      "status": "success", // o "error"
      "embeddings": [ /* lista de vectores o datos de embeddings */ ], // si success
      "error_message": "string", // si error
      "error_code": "string" // si error
    }
    ```
*   **Manejo por el `IngestionWorker`**:
    *   El `IngestionWorker` deserializa el mensaje a una `EmbeddingCallbackAction`.
    *   Si `status` es `success`, procede a almacenar los embeddings (TODO actual: guardar en BD vectorial).
    *   Actualiza el estado de la tarea de ingesta y notifica al cliente final vía WebSockets.
*   **Observaciones**:
    *   La respuesta es asíncrona y utiliza colas Redis, cerrando el ciclo iniciado por la solicitud HTTP.
