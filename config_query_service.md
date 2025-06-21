# Análisis de Configuración: Query Service

Este documento detalla las configuraciones del `query_service`, diferenciando entre las configuraciones centralizadas en `common/config` y las que están hardcodeadas en el código del servicio.

## 1. Configuraciones Centralizadas (common/config/service_settings/query.py)

A continuación se detallan las configuraciones definidas en el módulo centralizado para el `query_service`.

### a) Configuraciones Específicas del Servicio
- **domain_name**: `query` - Dominio del servicio para colas y logging.

### b) Configuraciones de LLM (Groq)
- **groq_api_key**: Clave de API para Groq. Se espera de la variable de entorno `QUERY_GROQ_API_KEY`.
- **groq_api_base_url**: `https://api.groq.com/openai/v1` - URL base de la API de Groq.
- **default_llm_model**: `llama-3.3-70b-versatile` - Modelo LLM por defecto.
- **available_llm_models**: Lista de modelos LLM disponibles en Groq.
- **llm_temperature**: `0.3` - Temperatura para la generación del LLM.
- **llm_max_tokens**: `1024` - Máximo número de tokens a generar.
- **llm_top_p**: `1.0` - Parámetro Top P.
- **llm_frequency_penalty**: `0.0` - Penalización de frecuencia.
- **llm_presence_penalty**: `0.0` - Penalización de presencia.
- **llm_default_stop_sequences**: `None` - Secuencias de parada por defecto.
- **rag_system_prompt_template**: Prompt de sistema por defecto para RAG.

### c) Configuraciones de Búsqueda y RAG
- **similarity_threshold**: `0.7` - Umbral de similitud para resultados relevantes.
- **default_top_k**: `5` - Número de chunks a recuperar por defecto.
- **max_search_results**: `10` - Número máximo de resultados de búsqueda.
- **rag_context_window**: `4000` - Tamaño máximo del contexto en tokens para RAG.

### d) Configuraciones de Ejecución y Rendimiento
- **worker_count**: `2` - Número de workers para procesar queries.
- **parallel_search_enabled**: `True` - Habilita búsquedas paralelas.

### e) Configuraciones de Conectividad y Tiempos de Espera
- **llm_timeout_seconds**: `60` - Timeout para las llamadas al LLM.
- **embedding_service_timeout**: `30` - Timeout para comunicación con `embedding_service`.
- **search_timeout_seconds**: `10` - Timeout para búsquedas vectoriales.

### f) Configuraciones de Resiliencia (Reintentos)
- **groq_max_retries**: `3` - Número de reintentos del cliente Groq.
- **max_retries**: `3` - Reintentos máximos para otros servicios externos.
- **retry_delay_seconds**: `1.0` - Delay base entre reintentos.
- **retry_backoff_factor**: `2.0` - Factor de backoff para reintentos.

### g) Configuraciones de Métricas
- **enable_query_tracking**: `True` - Habilita el seguimiento de métricas de rendimiento.

## 2. Configuraciones Hardcodeadas y Anulaciones Locales

Durante el análisis del código de `query_service`, se encontraron las siguientes configuraciones que están definidas localmente en `query_service/config/settings.py`, algunas de las cuales anulan los valores de la configuración central.

- **service_name**: `"query_service"` - (Local) Nombre del servicio, no presente en la configuración central.
- **service_version**: `"2.0.0"` - (Local) Versión del servicio, no presente en la configuración central.
- **search_timeout_seconds**: `30` - (Anulación) Sobrescribe el valor de `10` definido en la configuración central.
- **worker_count**: `2` - (Redundante) Define el mismo valor que la configuración central.

## 3. Análisis de Uso de la Configuración

Esta sección detalla dónde y cómo se utilizan las configuraciones dentro del código del servicio.

### `main.py`
- **`settings.log_level`**: Utilizado para configurar el nivel de logging de la aplicación.
- **`settings.service_name`**: Utilizado para el logging y en mensajes informativos de inicio.
- **`settings.service_version`**: Utilizado en mensajes informativos de inicio.
- **`settings.worker_count`**: Utilizado para determinar el número de `QueryWorker` que se deben instanciar y ejecutar.
- **`settings` (objeto completo)**: Se pasa al constructor de `RedisManager` y `QueryWorker`, lo que implica que estos componentes utilizan configuraciones adicionales.

### `workers/query_worker.py`
- **`settings` (objeto completo)**: El worker recibe la configuración y la utiliza para inicializar el `BaseWorker` (heredado) y, lo más importante, la pasa directamente al constructor del `QueryService`. Esto confirma que la lógica principal de uso de la configuración reside en `QueryService`.

### `services/query_service.py`
- **Rol de Orquestador**: Este servicio actúa como un orquestador. No utiliza directamente los parámetros de configuración para la lógica de negocio, sino que inicializa y pasa el objeto `settings` a los siguientes componentes:
    - `EmbeddingClient`
    - `SimpleHandler`
    - `AdvanceHandler`
    - `RAGHandler`
- **Lógica de Ruteo**: La función `process_action` direcciona las solicitudes al handler correspondiente (`_handle_simple`, `_handle_advance`, `_handle_rag`) basándose en el `action.action_type`.
- **Uso de Parámetros**: En el método `_handle_rag`, se observa que los parámetros `top_k` y `similarity_threshold` pueden ser sobrescritos en tiempo de ejecución si vienen en el payload de la acción, de lo contrario, se usan los de `rag_config`.

### `handlers/rag_handler.py`
- **Configuración Hardcodeada**: Se ha detectado una URL hardcodeada para el `VectorClient`: `"http://localhost:6333"`. Se utiliza como fallback si `app_settings.qdrant_url` no existe.
- **INCONSISTENCIA**: El parámetro `qdrant_url` se intenta usar pero **no está definido** en ningún archivo de configuración (`query.py` central o local). Esto debería añadirse a la configuración central para evitar el uso del valor hardcodeado.
- **Uso de Configuración Central**:
    - `search_timeout_seconds`: Se utiliza para establecer el timeout en el `VectorClient`.
- **Configuraciones No Utilizadas**: Este handler se enfoca exclusivamente en la búsqueda vectorial y no utiliza ninguna de las configuraciones relacionadas con la generación de LLM (ej. `default_llm_model`, `llm_temperature`, `groq_api_key`, etc.).
- **Configuración Dinámica**: Los parámetros de búsqueda como `top_k`, `similarity_threshold`, `collection_ids` y el modelo de embedding se reciben a través del objeto `RAGConfig` en el payload de la acción, no desde la configuración del servicio.

### `handlers/simple_handler.py`
- **Configuraciones de LLM Ignoradas**: La mayoría de las configuraciones por defecto para el LLM (`default_llm_model`, `llm_temperature`, `llm_max_tokens`, etc.) **no se utilizan**. El handler depende exclusivamente de los parámetros que se reciben dinámicamente en el `ChatRequest` (`payload`).
- **Configuración Hardcodeada**: 
    - Al inicializar `GroqClient`, se utiliza un **timeout hardcodeado de `60` segundos**, ignorando el parámetro `llm_timeout_seconds` de la configuración central.
    - El `VectorClient` se inicializa con el mismo fallback hardcodeado a `"http://localhost:6333"` si `qdrant_url` no está definida.
- **Uso de Configuración Central**:
    - `groq_api_key`: Se utiliza para la creación del `GroqClient`.
    - `search_timeout_seconds`: Se utiliza para el timeout del `VectorClient`.
- **INCONSISTENCIA**: La falta de `qdrant_url` en la configuración se confirma de nuevo.

### `handlers/advance_handler.py`
- **Configuraciones de LLM Ignoradas**: Confirma la tendencia de ignorar las configuraciones de LLM por defecto. Todos los parámetros (`model`, `temperature`, `max_tokens`, etc.) se toman del `ChatRequest` dinámico.
- **Configuración Hardcodeada**: Implementa una lógica de **timeout dinámico pero hardcodeado** para `GroqClient`: `max(60, payload.max_tokens // 100)`. Esto ignora por completo el ajuste `llm_timeout_seconds`.
- **Uso de Configuración Central**:
    - `groq_api_key`: Se utiliza para la creación del `GroqClient`.
- **Sin Búsqueda Vectorial**: Este handler no utiliza el `VectorClient`.

## 4. Análisis de Clientes

### `clients/groq_client.py`
- **Valores por Defecto Hardcodeados**: El constructor del cliente define valores por defecto para `timeout: int = 60` y `max_retries: int = 3`.
- **INCONSISTENCIA / Configuraciones Ignoradas**:
    - El `timeout` se pasa desde los handlers (donde también está hardcodeado), ignorando por completo el `llm_timeout_seconds` de la configuración central.
    - El `max_retries` se inicializa con su valor por defecto `3`, lo que significa que el parámetro `groq_max_retries` de la configuración central **nunca se utiliza**.

### `clients/vector_client.py`
- **Confirmación de la Causa de la Inconsistencia**: Este cliente confirma el origen del problema con `qdrant_url`. El cliente espera una `base_url` en su constructor. Los handlers intentan pasar `app_settings.qdrant_url`, pero al no estar definida, se utiliza la URL hardcodeada de fallback: `"http://localhost:6333"`.
- **Uso Correcto del Timeout**: El cliente recibe y utiliza correctamente el `search_timeout_seconds` que le pasan los handlers. El valor por defecto de `30` en el constructor del cliente no se utiliza en este flujo, pero es otro ejemplo de un valor de configuración hardcodeado.

### `clients/embedding_client.py`
- **Comunicación vía Redis**: Este cliente no usa HTTP. Se comunica con el `embedding_service` de forma asíncrona a través de Redis, enviando `DomainActions`.
- **INCONSISTENCIA / Configuraciones Ignoradas**:
    - `embedding_service_url`: No se utiliza, ya que la comunicación no es por HTTP.
    - `embedding_service_timeout`: No se utiliza. Los timeouts para las llamadas pseudo-síncronas se rigen por `redis_rpc_timeout_seconds`.
    - `default_embedding_model`: Se ignora. El cliente tiene un modelo por defecto hardcodeado: `"text-embedding-3-small"`.

## 5. Resumen Final y Hallazgos Clave para `query_service`

### Configuraciones Centralizadas Utilizadas
- `groq_api_key`: Clave para el servicio Groq.
- `redis_host`, `redis_port`, `redis_db`, `redis_password`: Para la conexión con Redis.
- `redis_rpc_timeout_seconds`: Timeout para las llamadas síncronas vía Redis.
- `service_queue_name`: Nombre de la cola de Redis para el servicio.
- `enable_query_tracking`: Habilita el seguimiento de consultas.
- `log_level`: Nivel de logging.

### Configuraciones Centralizadas Ignoradas
- `qdrant_url`: **Crítico**. Se intenta usar pero no está definido, causando un fallback a una URL hardcodeada.
- `llm_timeout_seconds`: Ignorado en favor de timeouts hardcodeados en los handlers y clientes de Groq.
- `groq_max_retries`: Ignorado. El `GroqClient` usa su propio valor por defecto hardcodeado (3).
- `default_llm_model`, `llm_temperature`, `llm_max_tokens`, `llm_top_p`, `llm_frequency_penalty`, `llm_presence_penalty`, `llm_stop_sequences`: Todos ignorados. Los handlers dependen de los parámetros dinámicos de la solicitud.
- `default_embedding_model`: Ignorado. El `EmbeddingClient` usa un modelo hardcodeado (`"text-embedding-3-small"`).
- `embedding_service_url`, `embedding_service_timeout`: No aplicables, ya que la comunicación es por Redis.
- `rag_search_top_k`, `rag_similarity_threshold`: No se utilizan. Los handlers usan sus propios valores por defecto o los reciben en la solicitud.

### Overrides y Configuraciones Locales
- `service_name`, `service_version`: Hardcodeados en `query_service/config/settings.py`.
- `search_timeout_seconds`: Se anula de 10 (central) a 30 (local).
- `worker_count`: Se repite el valor de la configuración central.

### Configuraciones Hardcodeadas en el Código
- **URL de VectorClient**: `"http://localhost:6333"` (usada como fallback por la falta de `qdrant_url`).
- **Timeout de GroqClient**: `60` segundos o un cálculo dinámico en los handlers.
- **Reintentos de GroqClient**: `3` reintentos.
- **Modelo de Embedding**: `"text-embedding-3-small"`.

### Inconsistencias Clave y Recomendaciones
1.  **Falta `qdrant_url`**: Es la inconsistencia más crítica. Se debe añadir `qdrant_url` a la configuración central (`common/config/service_settings/query.py`) para eliminar el fallback a la URL hardcodeada.
2.  **Parámetros de Groq no Configurables**: El `timeout` y los `max_retries` para el `GroqClient` deben ser controlados por la configuración central (`llm_timeout_seconds`, `groq_max_retries`). Es necesario refactorizar el `GroqClient` y los handlers para que usen estos valores.
3.  **Configuraciones LLM Inutilizadas**: Las configuraciones por defecto para el LLM no se usan. Se debe evaluar si deben eliminarse o si los handlers deben modificarse para usarlas como fallback cuando no se proveen en la solicitud.
4.  **Modelo de Embedding Hardcodeado**: El `EmbeddingClient` debe usar `default_embedding_model` de la configuración central en lugar del valor hardcodeado.
5.  **Limpieza de Configuraciones**: `embedding_service_url` y `embedding_service_timeout` deberían eliminarse de la configuración de `query` si la comunicación por Redis es la definitiva, para evitar confusiones.
