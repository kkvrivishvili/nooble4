# Informe de Auditoría y Hoja de Ruta: Ingestion & Query Services

**Versión**: 2.0
**Fecha de Auditoría**: 26 de junio de 2024
**Autor**: Cascade AI

## 1. Diagnóstico General y Puntuación de Salud

- **Puntuación de Salud del Sistema**: **6.5 / 10 (Requiere Intervención)**
- **Diagnóstico**: La arquitectura base es conceptualmente sólida, pero su implementación actual presenta **vulnerabilidades críticas en el ciclo de vida de los datos y una resiliencia insuficiente ante fallos**. La compatibilidad en el "camino feliz" (happy path) es alta, pero los casos de error y las operaciones de mantenimiento no se manejan de forma robusta. **Se requiere acción inmediata para evitar la corrupción de datos y la inestabilidad del servicio.**

---

## 2. Plan de Acción Ejecutivo (Próximos 3 Pasos)

1.  **Corregir la Eliminación de Documentos (🔥 Crítico)**: La funcionalidad de borrado está rota. Se debe reparar inmediatamente para permitir la gestión de datos.
2.  **Fortalecer la Resiliencia de la Ingesta (🟧 Alto)**: Implementar un mecanismo de timeout para evitar que las tareas de ingesta queden "colgadas" indefinidamente.
3.  **Mejorar la Detección de Errores de Búsqueda (🟧 Alto)**: Modificar el cliente de Qdrant para que notifique los fallos de búsqueda en lugar de silenciarlos.

---

## 3. Análisis Detallado de Hallazgos

A continuación se presenta un análisis exhaustivo de cada hallazgo identificado.

### Hallazgo #1: La eliminación de documentos está rota
- **Severidad**: 🔥 **CRÍTICO**
- **Área**: Ciclo de Vida del Dato (CRUD)

#### Descripción del Problema
La función `_handle_delete_document` en `IngestionService` intenta eliminar un documento llamando a `qdrant_handler.delete_document`. Sin embargo, la llamada omite el parámetro `agent_id`, que es obligatorio en la firma del método del handler.

#### Evidencia (Código)
```python
# ingestion_service/services/ingestion_service.py:364
async def _handle_delete_document(self, action: DomainAction) -> Dict[str, Any]:
    document_id = action.data.get("document_id")
    # ...
    # BUG: La llamada no incluye agent_id
    deleted_count = await self.qdrant_handler.delete_document(
        action.tenant_id,
        document_id
    )
    # ...

# ingestion_service/handlers/qdrant_handler.py:129
async def delete_document(
    self, 
    tenant_id: str,
    agent_id: str,  # Parámetro requerido
    document_id: str
) -> int:
    # ...
```

#### Causa Raíz
El `DomainAction` que dispara la eliminación no fue diseñado para transportar el `agent_id`. Por lo tanto, el `IngestionService` no tiene forma de obtenerlo y pasarlo al `QdrantHandler`.

#### Impacto de Negocio/Técnico
- **Técnico**: La funcionalidad está 100% inoperable y produce un `TypeError` en tiempo de ejecución.
- **Negocio**: Es imposible para los usuarios o administradores eliminar datos, lo que puede tener implicaciones de cumplimiento (GDPR) y de gestión de costos de almacenamiento.

#### Solución Propuesta
1.  **Modificar el Payload**: El cliente que origina la acción de eliminación debe incluir `agent_id` en el `action.data`.
2.  **Actualizar el Servicio**: `IngestionService` debe extraer el `agent_id` del `action.data` y pasarlo a la llamada del handler.

```python
# Propuesta de corrección en ingestion_service/services/ingestion_service.py
async def _handle_delete_document(self, action: DomainAction) -> Dict[str, Any]:
    document_id = action.data.get("document_id")
    agent_id = action.data.get("agent_id") # <-- AÑADIR ESTA LÍNEA
    if not document_id or not agent_id:
        raise ValueError("document_id and agent_id are required for deletion")
    
    deleted_count = await self.qdrant_handler.delete_document(
        action.tenant_id,
        agent_id, # <-- AÑADIR ESTE PARÁMETRO
        document_id
    )
    # ...
```

---

### Hallazgo #2: Tareas de ingestión "colgadas" por falta de timeout
- **Severidad**: 🟧 **ALTO**
- **Área**: Resiliencia

#### Descripción del Problema
El `IngestionService` envía chunks al `embedding_service` y espera un callback (`_handle_embedding_result`) para continuar. Si el `embedding_service` falla y nunca envía el callback, la `IngestionTask` queda permanentemente en estado `EMBEDDING`.

#### Causa Raíz
No existe un mecanismo de timeout o de vigilancia (watchdog) a nivel de la tarea de ingestión para detectar la falta de progreso.

#### Impacto de Negocio/Técnico
- **Técnico**: Acumulación de tareas "zombis" en Redis, consumo innecesario de memoria y dificultad para depurar fallos reales.
- **Negocio**: Falta de fiabilidad en el proceso de ingesta. Los usuarios no son notificados de que sus documentos no se procesaron correctamente.

#### Solución Propuesta
1.  **Añadir `expires_at` a `IngestionTask`**: En `ingestion_models.py`, añadir un campo `expires_at: Optional[datetime]` al modelo `IngestionTask`.
2.  **Establecer Expiración**: Al crear la tarea, calcular `expires_at` (ej. `utcnow() + timedelta(minutes=15)`).
3.  **Implementar un "Sweeper"**: Crear un proceso de barrido (ej. un `BackgroundTask` de FastAPI o un cron job) que periódicamente busque tareas cuyo `expires_at` haya pasado y su estado no sea final (`COMPLETED` o `FAILED`). Estas tareas deben ser marcadas como `FAILED` con un motivo de "timeout".

---

### Hallazgo #3: Errores de búsqueda en Qdrant son silenciados
- **Severidad**: 🟧 **ALTO**
- **Área**: Resiliencia

#### Descripción del Problema
El `QdrantClient` en `query_service` tiene un bloque `try...except` genérico que captura cualquier error durante la búsqueda y simplemente devuelve una lista vacía.

#### Evidencia (Código)
```python
# query_service/clients/qdrant_client.py:122
except Exception as e:
    self.logger.error(f"Error searching in documents collection for agent_id={agent_id}: {e}")
    return [] # <-- El error se silencia
```

#### Causa Raíz
Un intento de hacer el cliente más "robusto" al no propagar excepciones, pero con el efecto secundario de ocultar problemas críticos de la base de datos.

#### Impacto de Negocio/Técnico
- **Técnico**: Imposibilidad de diagnosticar problemas con Qdrant (conectividad, timeouts, queries malformadas). El sistema no puede auto-sanarse ni reintentar.
- **Negocio**: El usuario final recibe respuestas de baja calidad (o ninguna) sin ninguna indicación de que hay un problema técnico subyacente.

#### Solución Propuesta
1.  **Crear Excepción Personalizada**: Definir una excepción `QdrantClientError` en un módulo de excepciones comunes.
2.  **Relanzar Excepción**: En el `QdrantClient`, capturar la excepción original y relanzarla como `QdrantClientError`, preservando el contexto.
3.  **Capturar en el Handler**: El `RAGHandler` en `query_service` debe ser modificado para capturar `QdrantClientError` y devolver una respuesta de error HTTP apropiada (ej. 503 Service Unavailable).

---

### Hallazgo #4: Ingestas parciales silenciosas por chunks fallidos
- **Severidad**: 🟨 **MEDIO**
- **Área**: Integridad de Datos

#### Descripción del Problema
Cuando un chunk llega del `embedding_service` sin un vector de embedding, `_handle_embedding_result` lo ignora y continúa. La tarea puede finalizar como `COMPLETED` aunque falten chunks.

#### Causa Raíz
Falta de un mecanismo de contabilidad para los chunks que fallan individualmente dentro de un lote.

#### Impacto de Negocio/Técnico
- **Técnico**: Corrupción silenciosa de los datos. La base de datos vectorial no contiene toda la información del documento fuente.
- **Negocio**: La calidad de las respuestas del RAG se degrada, ya que el LLM no tendrá acceso a todo el contexto, sin que nadie se dé cuenta del problema de datos.

#### Solución Propuesta
1.  **Añadir `failed_chunks` a `IngestionTask`**: En `ingestion_models.py`, añadir un campo `failed_chunks: int = 0` al modelo `IngestionTask`.
2.  **Incrementar Contador**: En `_handle_embedding_result`, cuando se omita un chunk, incrementar `task.failed_chunks`.
3.  **Reflejar en el Resultado Final**: Al completar la tarea, incluir el recuento de `failed_chunks` en el resultado. Considerar marcar la tarea como `COMPLETED_WITH_ERRORS` si `failed_chunks > 0`.

---

### Hallazgo #5: Estado de tarea inconsistente por desajuste de datos
- **Severidad**: 🟨 **MEDIO**
- **Área**: Integridad de Datos

#### Descripción del Problema
En `_handle_embedding_result`, si el número de `chunk_ids` recibidos no coincide con el número de `embeddings`, la función registra un error y retorna. No se hace nada más.

#### Causa Raíz
Manejo de errores incompleto para un caso de corrupción de datos entre servicios.

#### Impacto de Negocio/Técnico
- **Técnico**: La tarea queda en un estado "limbo" (`EMBEDDING` o `STORING`) y nunca se resuelve, similar al problema de timeout pero causado por datos corruptos.
- **Negocio**: Similar al problema de timeout, genera falta de fiabilidad y visibilidad.

#### Solución Propuesta
- **Marcar Tarea como Fallida**: En el bloque que detecta el desajuste, cargar la `IngestionTask`, actualizar su estado a `FAILED` con un mensaje de error claro ("Chunk/embedding count mismatch"), y guardarla.

---

## 4. Fortalezas Arquitectónicas (Lo que funciona bien)

- **Arquitectura de Colección Única**: El uso de una sola colección `"documents"` con filtros es una estrategia moderna y eficiente que simplifica el mantenimiento y escala bien.
- **Consistencia de Modelos de Datos**: El uso de Pydantic y la coherencia en los campos (`content`, `tenant_id`, etc.) entre `ChunkModel` y `RAGChunk` es excelente y previene una clase entera de bugs.
- **Aislamiento de Datos por Agente**: El filtrado obligatorio por `agent_id` en las búsquedas es una medida de seguridad crítica que está bien implementada.

---

## 5. Hoja de Ruta de Implementación

| Prio. | Tarea | Descripción Detallada | Componentes Afectados | Esfuerzo |
| :--- | :--- | :--- | :--- | :--- |
| 🔥 1 | **Corregir bug de eliminación** | Añadir `agent_id` al payload de la acción de eliminación y actualizar el `IngestionService` para usarlo. | `ingestion_service`, Cliente que llama a la acción | **Pequeño** |
| 🟧 2 | **Implementar timeout en `IngestionTask`** | Añadir campo `expires_at` a `IngestionTask`. Crear un `BackgroundTask` que verifique tareas expiradas y las marque como `FAILED`. | `ingestion_service` (modelos, servicio) | **Mediano** |
| 🟧 3 | **Propagar excepciones en `QdrantClient`** | Reemplazar el `except Exception` por un relanzamiento de una excepción personalizada. Capturar la nueva excepción en los handlers del `query_service`. | `query_service` (cliente, handlers) | **Pequeño** |
| 🟨 4 | **Rastrear `failed_chunks`** | Añadir contador `failed_chunks` a `IngestionTask`. Incrementar el contador cuando un chunk no pueda ser procesado. | `ingestion_service` (modelos, servicio) | **Pequeño** |
| 🟨 5 | **Marcar tarea como `FAILED` en desajuste** | En `_handle_embedding_result`, si las longitudes de `chunk_ids` y `embeddings` no coinciden, marcar la tarea como `FAILED`. | `ingestion_service` | **Pequeño** |

---

## 6. Anexo: Recomendaciones Estratégicas a Largo Plazo

- **Implementar Métricas y Alertas**: Usar un sistema como Prometheus/Grafana para implementar las métricas sugeridas en la V1 de este informe. Crear alertas para `failed_tasks > 0` o `qdrant_errors > 0`.
- **Testing de Integración**: Crear tests de integración que simulen explícitamente los escenarios de fallo aquí descritos (ej. un `embedding_service` que no responde) para asegurar que las correcciones funcionan y prevenir regresiones.
- **Refactorizar `_handle_embedding_result`**: Esta función ha crecido en complejidad. Considerar refactorizarla en sub-funciones más pequeñas y manejables para mejorar la legibilidad.


**Fecha de Análisis**: 26 de junio de 2024
**Autor**: Cascade AI

## 1. Resumen Ejecutivo

La integración entre `ingestion_service` y `query_service` a través de Qdrant es **funcionalmente compatible** en su flujo principal de datos. Ambos servicios utilizan una arquitectura de **colección única** con **filtros virtuales**, lo que representa una base sólida y eficiente.

Sin embargo, este análisis profundo ha identificado **1 bug crítico, 2 debilidades de alta prioridad en resiliencia y 2 brechas de integridad de datos de media prioridad**. La funcionalidad de eliminación de documentos está actualmente **rota**. Se requiere acción inmediata para asegurar la estabilidad y fiabilidad del sistema.

## 2. Hallazgos Clave

| Severidad | Área | Hallazgo |
| :--- | :--- | :--- |
| 🔥 **CRÍTICO** | Ciclo de Vida del Dato | **La eliminación de documentos está rota**. Falta el `agent_id` en la llamada a la API. |
| 🟧 **ALTO** | Resiliencia | Las tareas de ingestión pueden quedar **"colgadas" indefinidamente** si el `embedding_service` no responde. |
| 🟧 **ALTO** | Resiliencia | Los errores de búsqueda en Qdrant **se silencian**, devolviendo un resultado vacío en lugar de notificar la falla. |
| 🟨 **MEDIO** | Integridad de Datos | **No se rastrean los chunks que fallan** durante el proceso de embedding, resultando en ingestas parciales silenciosas. |
| 🟨 **MEDIO** | Integridad de Datos | Un desajuste en los datos de embedding **deja la tarea en un estado inconsistente** en lugar de marcarla como fallida. |
| ✅ **POSITIVO** | Arquitectura | El modelo de colección única con filtros virtuales es **eficiente y escalable**. |
| ✅ **POSITIVO** | Consistencia | Los modelos de datos (`ChunkModel`, `RAGChunk`) y los campos clave son **totalmente compatibles**. |

---

## 3. Análisis Detallado por Área

### 3.1. Arquitectura y Flujo de Datos (✅ Sólido)

- **Modelo**: Se utiliza una única colección física (`"documents"`) en Qdrant. La separación lógica por `tenant_id`, `agent_id` y `collection_id` se realiza mediante filtros, lo cual es una práctica recomendada.
- **Flujo de Ingesta**: `IngestionService` → `ChunkModel` → `QdrantHandler` → `PointStruct` (con `id=chunk_id` y payload completo).
- **Flujo de Consulta**: `QueryService` → `QdrantClient` → Búsqueda en `"documents"` con filtros de seguridad → `RAGChunk`.
- **Conclusión**: El flujo de datos principal es coherente y no presenta inconsistencias.

### 3.2. Ciclo de Vida del Dato: CRUD (🔥 Bug Crítico)

- **Creación (Create)**: Funciona correctamente a través del `IngestionService`.
- **Lectura (Read)**: Funciona correctamente a través del `QueryService`.
- **Actualización (Update)**: No aplica directamente, se gestiona re-ingestando.
- **Eliminación (Delete)**: **Está ROTA.**
  - **Causa Raíz**: `IngestionService._handle_delete_document` no pasa el `agent_id` requerido por `QdrantHandler.delete_document`.
  - **Impacto**: Cualquier intento de eliminar un documento resultará en un `TypeError` en tiempo de ejecución, impidiendo la limpieza de datos y violando el ciclo de vida del dato.

### 3.3. Manejo de Errores y Resiliencia (🟧 Debilidades de Alta Prioridad)

1.  **Tareas de Ingestión Colgadas**:
    - **Causa Raíz**: El `IngestionService` espera indefinidamente un callback del `embedding_service` (`_handle_embedding_result`). Si este nunca llega, la tarea permanece en estado `EMBEDDING`.
    - **Impacto**: Acumulación de tareas fantasma, consumo de recursos en Redis y falta de visibilidad sobre fallos reales.
2.  **Errores de Búsqueda Silenciados**:
    - **Causa Raíz**: El `QdrantClient` captura cualquier excepción durante la búsqueda y devuelve una lista vacía.
    - **Impacto**: El sistema no puede distinguir entre "no hay resultados" y "el servicio de base de datos falló". Esto impide implementar lógicas de reintento o notificar al usuario sobre problemas de infraestructura.

### 3.4. Integridad de Datos (🟨 Brechas de Media Prioridad)

1.  **Ingestas Parciales Silenciosas**:
    - **Causa Raíz**: Si un chunk llega sin embedding, `_handle_embedding_result` lo omite con solo un `warning`. No se actualiza ningún contador de fallos.
    - **Impacto**: Un documento puede ser marcado como `COMPLETED` cuando en realidad solo una parte de sus chunks fue almacenada, afectando la calidad de las búsquedas RAG.
2.  **Estado Inconsistente por Desajuste de Datos**:
    - **Causa Raíz**: Si el número de `chunk_ids` y `embeddings` no coincide en el callback, la función simplemente retorna, sin actualizar el estado de la tarea.
    - **Impacto**: La tarea queda en un estado intermedio (`STORING` o `EMBEDDING`), pero nunca se completará ni se marcará como fallida.

### 3.5. Seguridad y Aislamiento (✅ Sólido)

- El uso de filtros `must` con `tenant_id` y `agent_id` en `QdrantClient.search` garantiza un aislamiento de datos estricto y seguro durante las consultas. La seguridad del sistema depende críticamente de la correcta aplicación de estos filtros en todas las operaciones de lectura y escritura.

---

## 4. Plan de Acción Priorizado

| Prioridad | Tarea | Archivos a Modificar | Quién lo implementa |
| :--- | :--- | :--- | :--- |
| 🔥 **CRÍTICA** | **Corregir bug de eliminación** | 1. `ingestion_service/services/ingestion_service.py`<br>2. Modificar el payload del `DomainAction` de eliminación. | Backend Team |
| 🟧 **ALTA** | **Implementar timeout en `IngestionTask`** | 1. `ingestion_service/models/ingestion_models.py`<br>2. `ingestion_service/services/ingestion_service.py`<br>3. (Opcional) Un nuevo servicio de "barrido". | Backend Team |
| 🟧 **ALTA** | **Propagar excepciones en `QdrantClient`** | 1. `query_service/clients/qdrant_client.py`<br>2. `query_service/handlers/rag_handler.py` (para capturar la nueva excepción). | Backend Team |
| 🟨 **MEDIA** | **Rastrear `failed_chunks` en `IngestionTask`** | 1. `ingestion_service/models/ingestion_models.py`<br>2. `ingestion_service/services/ingestion_service.py` | Backend Team |
| 🟨 **MEDIA** | **Marcar tarea como `FAILED` en desajuste** | 1. `ingestion_service/services/ingestion_service.py` | Backend Team |

## 5. Recomendaciones Adicionales: Métricas y Observabilidad

Para prevenir estos problemas a futuro, se recomienda implementar las siguientes métricas:

- **Contador de Tareas de Ingestión por Estado**: `ingestion_tasks_status_total{status="failed|completed|hanging"}`.
- **Contador de Chunks Fallidos**: `ingestion_chunks_failed_total`.
- **Histograma de Latencia de Búsqueda en Qdrant**: `qdrant_search_latency_seconds`.
- **Contador de Errores de Qdrant**: `qdrant_client_errors_total{operation="search|upsert|delete"}`.