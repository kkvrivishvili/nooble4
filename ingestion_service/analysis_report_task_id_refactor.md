# Refactorización del Manejo de `task_id` en la Comunicación entre Servicios

Date: 2025-06-18

## Objetivo

Alinear el manejo del `task_id` con la estandarización de `DomainAction`, donde los identificadores comunes como `task_id` son atributos de primer nivel del objeto `DomainAction` y no parte del diccionario `data` específico de la acción. Esta refactorización se centra en la comunicación entre `ingestion_service` y `embedding_service` para la acción `embedding.batch.process`.

## Problema Identificado

Previamente, `ingestion_service` enviaba el `task_id` tanto como un atributo de primer nivel del `DomainAction` como dentro del diccionario `action.data` al comunicarse con `embedding_service`. `embedding_service` leía el `task_id` desde `action.data` para su procesamiento interno y para la construcción de la respuesta.

Esto no se alineaba completamente con la práctica estándar de mantener los identificadores de contexto (como `task_id`) fuera del payload (`data`) específico de la acción.

## Cambios Realizados

1.  **`ingestion_service/services/ingestion_service.py`**
    *   **Método `_send_chunks_for_embedding`:**
        *   Al construir el `DomainAction` para `embedding_service` (tipo `embedding.batch.process`), el `task_id` (obtenido de `task.task_id`) se sigue asignando correctamente al atributo de primer nivel `task_id` del `DomainAction`.
        *   Se eliminó la clave `"task_id": task.task_id` del diccionario `data` del `DomainAction`. El `action.data` ahora solo contiene información específica del lote de embeddings (`texts`, `chunk_ids`, `model`).

2.  **`embedding_service/models/payloads.py`**
    *   **`EmbeddingBatchPayload`:**
        *   Se eliminó el campo `task_id: Optional[str]`. Este payload, que parsea el `action.data` de la solicitud entrante, ya no espera `task_id` dentro de `data`.
    *   **`EmbeddingBatchResponse`:**
        *   Se mantuvo el campo `task_id: Optional[str]`. Este modelo define la estructura de la respuesta que `embedding_service` genera. El `task_id` se incluye aquí para que `ingestion_service` lo reciba en el callback.

3.  **`embedding_service/services/embedding_service.py`**
    *   **Método `_handle_batch_process`:**
        *   Se modificó para obtener el `task_id` relevante directamente del atributo de primer nivel `action.task_id` del `DomainAction` entrante.
        *   Este `action.task_id` se almacena en una variable local (`current_task_id`).
        *   Al construir el `EmbeddingBatchResponse` (que se enviará de vuelta a `ingestion_service` como el `action.data` del callback), el campo `task_id` de la respuesta se puebla utilizando `current_task_id`.
        *   Los logs de error dentro de este método ahora también utilizan `current_task_id`.

## Flujo de `task_id` Corregido

1.  **`ingestion_service` -> `embedding_service` (Acción `embedding.batch.process`):**
    *   `DomainAction.task_id = uuid.UUID(ingestion_task.task_id)` (atributo de primer nivel).
    *   `DomainAction.data` (parseado como `EmbeddingBatchPayload` por `embedding_service`) ya no contiene `task_id`.

2.  **`embedding_service` (Procesamiento en `_handle_batch_process`):**
    *   Lee `task_id` desde `action.task_id`.
    *   Crea `EmbeddingBatchResponse` donde `response.task_id` se establece con el valor de `action.task_id`.

3.  **`embedding_service` -> `ingestion_service` (Acción de Callback `ingestion.embedding_result`):**
    *   `DomainAction.data` (que es el `EmbeddingBatchResponse.model_dump()`) contiene el `task_id`.
    *   `ingestion_service` (`_handle_embedding_result`) lee este `task_id` desde `action.data['task_id']` para su lógica de procesamiento de resultados (esto no requirió cambios, ya que estaba implementado así).

## Conclusión

Con esta refactorización, el envío inicial del `task_id` desde `ingestion_service` a `embedding_service` se alinea con la estructura estándar de `DomainAction`. El `task_id` se propaga consistentemente como un atributo de primer nivel en la solicitud, y luego se incluye en el cuerpo de datos (`EmbeddingBatchResponse`) de la respuesta de callback para que `ingestion_service` pueda procesarlo. Esto mejora la claridad y consistencia del protocolo de comunicación entre servicios.
