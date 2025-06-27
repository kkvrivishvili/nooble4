# Análisis de Configuración: `ingestion_service`

## 1. Resumen del Servicio

El `ingestion_service` es responsable de procesar y ingestar datos de diversas fuentes para que estén disponibles para otros servicios, como el `query_service`. Su correcta configuración es vital para asegurar un flujo de datos fiable y eficiente.

## 2. Propósito del Análisis

Este documento detalla todas las configuraciones para el `ingestion_service`, incluyendo las que están hardcodeadas y las que se gestionan a través del módulo de configuración centralizado (`common/config/service_settings/ingestion.py`).

## Configuraciones Centralizadas (`common/config/service_settings/ingestion.py`)

A continuación se detallan las configuraciones definidas para el servicio:

### a) Información del Servicio
- `service_name`, `environment`, `log_level`: Heredadas de `CommonAppSettings`.
- `redis_queue_prefix`: (str) Prefijo para colas Redis específicas de Ingestión. **Default:** `"ingestion"`.

### b) Configuraciones relacionadas a LLM
*(No se encontraron configuraciones específicas para LLMs en este archivo)*

### c) Configuraciones relacionadas a Embedding
- `embedding_model_default`: (str) Modelo de embedding a solicitar por defecto. **Default:** `"text-embedding-ada-002"`.
- `embedding_service_url`: (Optional[str]) URL base del Embedding Service. **Default:** `None`.
- `embedding_service_timeout_seconds`: (int) Timeout para llamadas al Embedding Service. **Default:** `60`.

### d) Configuraciones relacionadas a la Carga y Procesamiento de Archivos
- `storage_type`: (Enum) Tipo de almacenamiento para archivos (`local`, `s3`, `azure`). **Default:** `local`.
- `local_storage_path`: (str) Ruta base para almacenamiento local. **Default:** `"/tmp/nooble4_ingestion_storage"`.
- `max_file_size_bytes`: (int) Tamaño máximo de archivo subido (10MB). **Default:** `10485760`.
- `max_document_content_size_bytes`: (int) Tamaño máximo de contenido de documento extraído (1MB). **Default:** `1048576`.
- `max_url_content_size_bytes`: (int) Tamaño máximo de contenido descargado de URL (10MB). **Default:** `10485760`.
- `max_chunks_per_document`: (int) Máximo número de fragmentos por documento. **Default:** `1000`.
- `default_chunk_size`: (int) Tamaño predeterminado de fragmentos. **Default:** `512`.
- `default_chunk_overlap`: (int) Superposición predeterminada entre fragmentos. **Default:** `50`.
- `default_chunking_strategy`: (Enum) Estrategia de fragmentación predeterminada. **Default:** `sentence`.

### e) Configuraciones de Ejecución del Servicio
- `worker_count`: (int) Número de workers de ingestión. **Default:** `2`.
- `max_concurrent_tasks`: (int) Máximo de tareas de ingestión concurrentes. **Default:** `5`.
- `worker_sleep_time_seconds`: (float) Tiempo de espera para workers. **Default:** `0.1`.
- `auto_start_workers`: (bool) Iniciar workers automáticamente. **Default:** `True`.
- Nombres de Colas: `document_processing_queue_name`, `chunking_queue_name`, `task_status_queue_name`, `ingestion_actions_queue_name`.

### f) Configuraciones de Conectividad y API
- `admin_api_key`: (Optional[str]) API Key para operaciones de administración. **Default:** `None`.
- `cors_origins`: (List[str]) Orígenes permitidos para CORS. **Default:** `["*"]`.

### g) Configuraciones de TTL y Timeouts
- `job_timeout_seconds`: (int) Timeout de trabajos de ingestión. **Default:** `3600` (1 hora).
- `redis_lock_timeout_seconds`: (int) Timeout de bloqueos Redis. **Default:** `600` (10 minutos).

### h) Configuraciones de Estadísticas y Métricas
*(No se encontraron configuraciones explícitas para métricas en este archivo)*

## 3. Análisis Incremental de Módulos

### `main.py`

**Configuraciones Centralizadas Utilizadas:**
- `log_level`, `service_name`, `service_version`: Usadas para inicializar el logging y mostrar información de inicio.
- `auto_start_workers`: Se utiliza para decidir si el `IngestionWorker` debe iniciarse automáticamente.
- El objeto `settings` completo se pasa correctamente a `RedisManager`, `BaseRedisClient`, `IngestionService` e `IngestionWorker`, permitiendo el acceso a todas las configuraciones centralizadas.

**Configuraciones Hardcodeadas y Observaciones:**
- **Líneas 95-98:** La inicialización de `FastAPI` contiene valores hardcodeados para `title` y `version`. Deberían usar `settings.service_name` y `settings.service_version`.
- **Línea 105:** La configuración de `CORSMiddleware` tiene `allow_origins=["*"]`, lo cual es inseguro. No utiliza la configuración `cors_origins` definida en `CommonAppSettings`.
- **Líneas 143-144:** La llamada a `uvicorn.run` tiene el `host` y el `port` hardcodeados (`"0.0.0.0"`, `8002`). Deberían obtenerse del objeto `settings`.
- **Líneas 121-122:** El endpoint de `/health` tiene valores de fallback hardcodeados para el nombre y la versión del servicio.

### `services/ingestion_service.py`

**Configuraciones Centralizadas Utilizadas:**
- El objeto `app_settings` se pasa correctamente a los handlers (`DocumentProcessorHandler`, `ChunkEnricherHandler`, `QdrantHandler`), lo cual es una buena práctica.
- `service_name` se utiliza para identificar el origen de las acciones enviadas a otros servicios.

**Configuraciones Hardcodeadas y Observaciones:**
- **¡INCONSISTENCIA GRAVE! - Línea 166:** El modelo de embedding se envía hardcodeado como `"text-embedding-ada-002"` al `embedding-service`, ignorando por completo el valor definido en `settings.embedding_model_default`.
- **Línea 90 y 359:** El TTL para el estado de la tarea en Redis está hardcodeado a `86400` segundos (24 horas). Este valor debería ser configurable en `IngestionServiceSettings`.
- **Línea 126:** El tamaño del lote (`batch_size`) para enviar fragmentos a embeber está hardcodeado a `10`. Este valor debería ser configurable para optimizar el rendimiento.
- **Línea 184:** El TTL para los fragmentos temporales en Redis está hardcodeado a `3600` segundos (1 hora). Debería utilizar el valor de `settings.job_timeout_seconds`.
- **Líneas 56-64:** Los tipos de acción (`action_type`) se procesan comparando strings hardcodeados. Sería más robusto usar un Enum.
- **Línea 177:** El nombre del evento de callback (`callback_event_name`) está hardcodeado a `"ingestion.embedding_result"`.

### `handlers/document_processor.py`

**Configuraciones Centralizadas Utilizadas:**
- Este handler **no utiliza directamente ninguna configuración** del objeto `app_settings`. Los parámetros como `chunk_size` y `chunk_overlap` se toman de la petición (`DocumentIngestionRequest`), lo que permite configuración por llamada. Sin embargo, no se usan los valores por defecto de `IngestionServiceSettings` como fallback.

**Configuraciones Hardcodeadas y Observaciones:**
- **Línea 95:** El timeout para las peticiones HTTP al descargar desde una URL está hardcodeado a `30` segundos. Debería ser un valor configurable en `IngestionServiceSettings`.
- **Línea 91:** La codificación de texto para la lectura de archivos está fijada a `'utf-8'`. Aunque es un default razonable, podría ser configurable.

### `handlers/chunk_enricher.py`

**Configuraciones Centralizadas Utilizadas:**
- Este handler **no utiliza ninguna configuración** del objeto `app_settings`.

**Configuraciones Hardcodeadas y Observaciones:**
- **Toda la lógica de enriquecimiento está hardcodeada.** Este handler es un candidato ideal para ser refactorizado y controlado por configuración.
- **Línea 25:** El idioma para las *stopwords* de NLTK está fijado a `'english'`.
- **Línea 31:** El modelo de spaCy está fijado a `"en_core_web_sm"`.
- **Línea 43:** El número máximo de palabras clave a guardar está hardcodeado a `10`.
- **Líneas 104-113:** Hay un gran diccionario de palabras clave tecnológicas para la asignación de etiquetas que está completamente hardcodeado. Esto debería ser configurable para poder añadir nuevas tecnologías fácilmente.
- **Líneas 125-130:** Las palabras clave para detectar el tipo de contenido (código, documentación, tutorial) también están hardcodeadas.

### `handlers/qdrant_handler.py`

**Configuraciones Centralizadas Utilizadas:**
- `qdrant_url`: Usado para conectar con el cliente de Qdrant.
- `qdrant_api_key`: Usado para autenticarse con Qdrant.

**Configuraciones Hardcodeadas y Observaciones:**
- **Línea 23:** El nombre de la colección (`collection_name`) está hardcodeado a `"documents"`. Esto debería ser configurable, ya que podría variar entre entornos.
- **Línea 31:** El tamaño del vector (`vector_size`) está hardcodeado a `1536`. Este es un valor crítico que depende directamente del modelo de embedding utilizado. Debería ser configurable y estar sincronizado con la configuración del `embedding-service`.
- **Línea 45:** La métrica de distancia (`distance`) está fijada a `Distance.COSINE`. Esto también debería ser configurable.
- **Líneas 50-64:** Los campos para los que se crean índices de payload (`tenant_id`, `collection_id`, `document_id`) están hardcodeados.

### `workers/ingestion_worker.py`

**Configuraciones Centralizadas Utilizadas:**
- `app_settings`: El objeto de configuración completo se pasa al `IngestionService` durante la inicialización.

**Configuraciones Hardcodeadas y Observaciones:**
- **No se encontraron configuraciones hardcodeadas.** El worker sigue un buen patrón de diseño, actuando como una capa delgada que delega toda la lógica y el uso de la configuración al `IngestionService`.

## Resumen y Recomendaciones Finales

El análisis del `ingestion_service` revela un buen uso de la configuración centralizada para los parámetros principales de la aplicación. Sin embargo, se han identificado numerosas oportunidades de mejora para eliminar valores hardcodeados y aumentar la flexibilidad del servicio.

**Recomendaciones Clave:**
1.  **Centralizar Parámetros Críticos:** Mover valores como el `embedding_model` en `ingestion_service.py` y el `vector_size` en `qdrant_handler.py` a `IngestionServiceSettings` para asegurar la consistencia con otros servicios.
2.  **Hacer Configurables los Handlers:** Refactorizar `chunk_enricher.py` para que sus reglas de enriquecimiento (listas de palabras clave, modelos de NLP, etc.) se puedan gestionar desde la configuración central.
3.  **Eliminar Constantes Mágicas:** Migrar strings de tipos de acción, eventos y nombres de colecciones a enums o constantes definidas en la configuración para evitar errores y facilitar el mantenimiento.
4.  **Configurar Parámetros de Red:** Externalizar timeouts y otros parámetros de red (como el `timeout` en `document_processor.py`) a la configuración central.

La implementación de estos cambios hará que el `ingestion_service` sea significativamente más robusto, mantenible y fácil de adaptar a futuras necesidades.

### `config/settings.py`
- **Patrón de Diseño Correcto**: Este archivo demuestra un excelente patrón de diseño al no definir una clase de configuración local. Importa y expone directamente `IngestionServiceSettings` desde el paquete `common`, asegurando que el servicio utilice una única fuente de verdad para su configuración.

## 4. Resumen de Hallazgos y Recomendaciones

*Esta sección consolidará los hallazgos finales.*

## 5. Configuraciones Centralizadas Aplicables

A continuación se listan las configuraciones definidas en `common/config/service_settings/ingestion.py`.

- **`redis_queue_prefix`**: `ingestion` - Prefijo para las colas de Redis.
- **`document_processing_queue_name`**: `document:processing` - Cola para procesar documentos.
- **`chunking_queue_name`**: `document:chunking` - Cola para la fragmentación de documentos.
- **`task_status_queue_name`**: `task:status` - Cola para el estado de las tareas.
- **`ingestion_actions_queue_name`**: `ingestion:actions` - Cola para acciones de dominio entrantes.
- **`worker_count`**: `2` - Número de workers de ingestión.
- **`max_concurrent_tasks`**: `5` - Máximo de tareas de ingestión concurrentes.
- **`job_timeout_seconds`**: `3600` - Timeout para trabajos de ingestión.
- **`redis_lock_timeout_seconds`**: `600` - Timeout para bloqueos de Redis.
- **`worker_sleep_time_seconds`**: `0.1` - Tiempo de espera para los workers.
- **`max_file_size_bytes`**: `10485760` (10MB) - Tamaño máximo de archivo.
- **`max_document_content_size_bytes`**: `1048576` (1MB) - Tamaño máximo de contenido de documento.
- **`max_url_content_size_bytes`**: `10485760` (10MB) - Tamaño máximo de contenido de URL.
- **`max_chunks_per_document`**: `1000` - Máximo de fragmentos por documento.
- **`default_chunk_size`**: `512` - Tamaño de fragmento por defecto.
- **`default_chunk_overlap`**: `50` - Superposición de fragmentos por defecto.
- **`default_chunking_strategy`**: `sentence` - Estrategia de fragmentación por defecto.
- **`embedding_model_default`**: `text-embedding-ada-002` - Modelo de embedding por defecto.
- **`embedding_service_url`**: `None` - URL del servicio de embedding.
- **`embedding_service_timeout_seconds`**: `60` - Timeout para el servicio de embedding.
- **`storage_type`**: `local` - Tipo de almacenamiento.
- **`local_storage_path`**: `/tmp/nooble4_ingestion_storage` - Ruta de almacenamiento local.
- **`admin_api_key`**: `None` - API key para operaciones de administración.
- **`auto_start_workers`**: `True` - Iniciar workers automáticamente.
