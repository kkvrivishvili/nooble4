# Análisis de Configuración: Embedding Service

Este documento detalla todas las configuraciones para el `embedding_service`, incluyendo las que están hardcodeadas y las que se gestionan a través del módulo de configuración centralizado (`common/config/service_settings/embedding.py`).

## Configuraciones Centralizadas (`common/config/service_settings/embedding.py`)

A continuación se detallan las configuraciones definidas para el servicio:

### a) Información del Servicio
- `domain_name`: (str) Nombre de dominio para colas y lógica del servicio. **Default:** `"embedding"`.
- `service_version`: (str) Versión del servicio de embeddings. **Default:** `"1.0.0"`.

### b) Configuraciones relacionadas a LLM
*(No se encontraron configuraciones específicas para LLMs en este archivo)*

### c) Configuraciones relacionadas a Embedding
- `openai_api_key`: (Optional[str]) API Key para OpenAI. Requerida si se usa el proveedor OpenAI. **Default:** `None`.
- `openai_base_url`: (Optional[str]) URL base para la API de OpenAI (opcional). **Default:** `None`.
- `openai_default_model`: (str) Modelo de embedding por defecto para OpenAI. **Default:** `"text-embedding-3-small"`.
- `default_models_by_provider`: (Dict) Modelos de embedding por defecto para cada proveedor. 
- `default_dimensions_by_model`: (Dict) Dimensiones por defecto para modelos conocidos.
- `preferred_dimensions`: (Optional[int]) Dimensiones preferidas para embeddings. **Default:** `None`.
- `encoding_format`: (Enum) Formato de codificación de embeddings (`float` o `base64`). **Default:** `float`.

### d) Configuraciones relacionadas a la carga de archivos
*(No aplica para este servicio)*

### e) Configuraciones de Ejecución del Servicio
- `worker_count`: (int) Número de workers para procesar embeddings. **Default:** `2`.
- `worker_sleep_seconds`: (float) Tiempo de espera para workers. **Default:** `0.1`.
- `default_batch_size`: (int) Tamaño de lote por defecto para procesamiento. **Default:** `50`.
- `default_max_text_length`: (int) Longitud máxima de texto por defecto. **Default:** `8192`.
- `default_truncation_strategy`: (str) Estrategia de truncamiento por defecto. **Default:** `"end"`.

### f) Configuraciones de Conectividad y Proveedores Externos
- `openai_max_retries`: (int) Reintentos para el cliente OpenAI SDK. **Default:** `3`.
- `openai_timeout_seconds`: (int) Timeout para el cliente OpenAI SDK. **Default:** `30`.
- `provider_timeout_seconds`: (int) Timeout para llamadas a otros proveedores. **Default:** `30`.
- `provider_max_retries`: (int) Reintentos para otros proveedores. **Default:** `3`.
- `provider_retry_backoff_factor`: (float) Factor de backoff para reintentos. **Default:** `0.5`.
- `provider_retry_statuses`: (List[int]) Códigos de estado HTTP que activan un reintento. **Default:** `[408, 429, 500, 502, 503, 504]`.

### g) Configuraciones de TTL y Caché
- `embedding_cache_enabled`: (bool) Habilitar la caché de embeddings. **Default:** `True`.
- `cache_ttl_seconds`: (int) TTL para la caché de embeddings. **Default:** `86400` (24 horas).
- `cache_max_size`: (int) Número máximo de entradas en la caché. **Default:** `10000`.

### h) Configuraciones de Estadísticas y Métricas
- `enable_embedding_tracking`: (bool) Habilitar tracking de métricas. **Default:** `True`.
- `slow_embed_threshold_ms`: (int) Umbral para considerar una generación de embedding como lenta. **Default:** `500`.

---
## Análisis de Uso y Configuraciones Hardcodeadas

### `main.py`

**Configuraciones Centralizadas Utilizadas:**
- `log_level`: Utilizado en `init_logging`.
- `service_name`: Utilizado en `init_logging`, `lifespan` y en los endpoints de health/metrics.
- `service_version`: Utilizado en `lifespan` y en los endpoints de health.
- `environment`: Utilizado en el endpoint de health.
- `redis_url`: Utilizado indirectamente a través de `RedisManager(settings=settings)`.
- `worker_count`: Utilizado para determinar el número de workers a crear.

**Configuraciones Hardcodeadas y Observaciones:**
- **Línea 57 (`num_workers = getattr(settings, 'worker_count', 2)`):** Se utiliza un valor de fallback hardcodeado (`2`) para `worker_count`. Aunque la configuración central ya define un default de `2`, esta es una repetición y una fuente potencial de inconsistencia si el default central cambia y este no.
- **Línea 113 (`allow_origins=["*"]`):** La configuración de CORS permite todos los orígenes (`*`). Esto es una práctica insegura para entornos de producción y debería ser configurable. El propio código lo advierte en un comentario.
- **Línea 178 (`health_status["components"]["openai_api"] = {"status": "unknown", "note": "No check implemented"}`):** El health check para la API de OpenAI no está implementado y devuelve un estado `unknown` hardcodeado.

---
### `workers/embedding_worker.py`

**Configuraciones Centralizadas Utilizadas:**
- `app_settings`: El objeto de configuración completo se pasa a `BaseWorker`, `BaseRedisClient` y `EmbeddingService`.

**Configuraciones Hardcodeadas y Observaciones:**
- No se han encontrado configuraciones hardcodeadas en este archivo. Actúa principalmente como un orquestador, pasando la configuración a los componentes relevantes, lo cual es una buena práctica.

---
### `services/embedding_service.py`

**Configuraciones Centralizadas Utilizadas:**
- `app_settings`: El objeto de configuración completo se pasa a los handlers (`OpenAIHandler`, `ValidationHandler`).
- `openai_default_model`: Se utiliza como modelo de fallback en `_handle_batch_process`.
- `enable_embedding_tracking`: Controla si se registran las métricas en `_track_metrics`.

**Configuraciones Hardcodeadas y Observaciones:**
- **Líneas 77, 80, 83:** Los tipos de acción (`embedding.generate`, `embedding.generate_query`, `embedding.batch_process`) están hardcodeados como strings. Sería más robusto definirlos como constantes en un modelo compartido.
- **Línea 140, 177:** El valor de `completion_tokens` se asume como `0`. Aunque es correcto para embeddings, es una asunción hardcodeada.
- **Línea 255 (`await self.direct_redis_conn.expire(metrics_key, 86400 * 7)`):** El TTL para las métricas de Redis está hardcodeado a 7 días. Este valor debería ser extraído a la configuración central (ej. `metrics_ttl_seconds`).
- **Líneas 223-233:** En caso de un fallo en el procesamiento por lotes, se construye una respuesta de error con valores hardcodeados (`model="unknown"`, `dimensions=0`, `status="failed"`).

---
### `handlers/openai_handler.py`

**Configuraciones Centralizadas Utilizadas:**
- `openai_api_key`, `openai_base_url`, `openai_timeout_seconds`, `openai_max_retries`: Utilizadas para configurar el `OpenAIClient`.
- `openai_default_model`: Usado como modelo de fallback.
- `default_dimensions_by_model`: Para obtener las dimensiones por defecto del modelo.
- `preferred_dimensions`: Aplicado a los modelos de la familia `v3` si no se especifican dimensiones en la petición.

**Configuraciones Hardcodeadas y Observaciones:**
- **Línea 45 (`1536`):** Se usa un valor de fallback hardcodeado para las dimensiones del modelo por defecto. Debería haber una única fuente de verdad en la configuración.
- **Línea 75 (`encoding_format = encoding_format or "float"`):** El formato de codificación por defecto está hardcodeado a `"float"`. Debería usar `self.app_settings.encoding_format`.
- **Línea 78 (`if dimensions is None and "text-embedding-3" in model`):** La lógica para aplicar `preferred_dimensions` se basa en un string hardcodeado. Esto podría ser más robusto si se usara una lista configurable de modelos que soportan esta característica.
- **Líneas 137-141:** La función `validate_model` utiliza una lista estática y hardcodeada de modelos válidos. Esta lista debería ser configurable para poder añadir nuevos modelos sin modificar el código.
- **Línea 162 (`total_chars // 4`):** La estimación de tokens se basa en una heurística muy simple (4 caracteres por token). El propio comentario del código sugiere que debería usarse una librería como `tiktoken` para mayor precisión. Esta lógica debería ser configurable o reemplazable.

---
### `handlers/validation_handler.py`

**Configuraciones Centralizadas Utilizadas:**
- `default_max_text_length`: Usado para validar la longitud de cada texto.
- `default_batch_size`: Usado para validar el número de textos en una petición.

**Configuraciones Hardcodeadas y Observaciones:**
- **Líneas 32-36 (`self.valid_models`):** Se utiliza una lista estática y hardcodeada de modelos válidos. **¡INCONSISTENCIA GRAVE!** Esta lista es una duplicación de la que se encuentra en `openai_handler.py`. La lista de modelos soportados debe definirse en un único lugar, preferiblemente en la configuración central, para evitar errores cuando se añadan o eliminen modelos.
- **Línea 108 (`total_chars // 4`):** La lógica de estimación de tokens está duplicada de `openai_handler.py`, utilizando la misma heurística hardcodeada. Esta función debería estar en un módulo de utilidad compartido para ser reutilizada por ambos handlers.

---
**Análisis del servicio completado.**