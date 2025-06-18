# Módulo de Configuración (Query Service)

## 1. Propósito General

El módulo `config` es el responsable de cargar y proporcionar acceso a toda la configuración necesaria para el `Query Service`. Esto incluye desde información sensible como API keys, hasta parámetros de comportamiento como timeouts, umbrales de similitud, y configuraciones de modelos de lenguaje. La meta es permitir que el servicio se adapte a diferentes entornos (desarrollo, staging, producción) sin modificar el código fuente, utilizando un sistema de configuración centralizado y validado.

## 2. Implementación y Conexión con `common`

La configuración del `Query Service` se gestiona a través de la clase `QueryServiceSettings`. Aunque esta clase se instancia localmente en `query_service.config.settings`, su definición reside en el módulo `common` (`common.config.service_settings.query.QueryServiceSettings`).

### `QueryServiceSettings` (Definida en `common`)

-   **Tecnología**: Utiliza [Pydantic](https://docs.pydantic.dev/) con `pydantic-settings` para la validación de datos y gestión de configuración basada en type hints.
-   **Herencia y Centralización**: `QueryServiceSettings` hereda de `CommonAppSettings` (definida en `common.config.base_settings`). Esto asegura que todas las configuraciones base comunes a los microservicios (como `service_name`, `log_level`, `redis_url`, `http_timeout_seconds`, etc.) se gestionan de forma consistente y centralizada en `common`.
-   **Carga de Configuración**: `pydantic-settings` carga valores con la siguiente precedencia:
    1.  Variables de entorno (con el prefijo `QUERY_` para evitar colisiones, ej. `QUERY_GROQ_API_KEY`).
    2.  Valores de un archivo `.env` en la raíz del proyecto (si existe y está configurado en `SettingsConfigDict`).
    3.  Valores por defecto definidos directamente en la clase `QueryServiceSettings`.
-   **Validación Automática**: Pydantic realiza validación automática de tipos al instanciar la clase. Si una variable de entorno no se puede castear al tipo esperado (ej. un string donde se espera un `int`), Pydantic lanzará un error al inicio, previniendo problemas en tiempo de ejecución.

### `settings.py` (En `query_service.config`)

-   Este archivo es un simple punto de acceso. Su función principal es instanciar `QueryServiceSettings` (la definida en `common`) mediante la función `get_settings()`. Esta función está decorada con `@lru_cache(maxsize=1)`, lo que garantiza que la configuración se carga una sola vez (patrón Singleton) y se reutiliza en todo el servicio, optimizando el rendimiento y la consistencia.

## 3. Parámetros de Configuración Clave

`QueryServiceSettings` define una amplia gama de parámetros, incluyendo:

-   **Conexiones a Servicios Externos**: `groq_api_key`, `groq_api_base_url`, `vector_db_url`.
-   **Parámetros de LLM**: `default_llm_model`, `available_llm_models`, `llm_temperature`, `llm_max_tokens`, `llm_timeout_seconds`.
-   **Búsqueda Vectorial**: `similarity_threshold`, `default_top_k`, `max_search_results`, `search_timeout_seconds`.
-   **RAG**: `rag_context_window`, `rag_system_prompt_template`.
-   **Workers y Rendimiento**: `worker_count`, `parallel_search_enabled`, `enable_query_tracking`.
-   **Reintentos**: `max_retries`, `retry_delay_seconds`, `retry_backoff_factor` (política genérica para clientes).
-   **Logging y Nombres**: `log_level` (heredado), `domain_name` (para colas específicas del servicio).

## 4. Análisis Detallado y Puntos de Interés

-   **Fortalezas del Diseño**:
    -   **Robustez y Claridad**: El uso de Pydantic con type hints y valores por defecto hace que la configuración sea muy clara, autodocumentada y robusta contra errores de tipo o formato.
    -   **Centralización y Reutilización (`common`)**: La herencia de `CommonAppSettings` y la definición de `QueryServiceSettings` en `common` (aunque instanciada localmente) es una excelente práctica para mantener la consistencia entre múltiples servicios.
    -   **Seguridad**: Cargar datos sensibles (API keys) desde variables de entorno es una práctica de seguridad estándar. Es crucial que los archivos `.env` (si se usan en desarrollo) que contengan secretos estén en `.gitignore`.
    -   **Flexibilidad**: El sistema permite una fácil adaptación a diferentes entornos (dev, staging, prod) mediante el uso de distintos archivos `.env` o variables de entorno.

-   **Posibles Mejoras y Consideraciones Avanzadas**:
    -   **Validación Personalizada Avanzada**: Pydantic permite validadores personalizados (usando `@validator` o, en Pydantic V2, `@field_validator`). **Mejora Sugerida**: Para campos críticos, se podrían añadir validadores para asegurar condiciones más complejas. Ejemplos:
        -   Verificar que `default_llm_model` sea uno de los `available_llm_models`.
        -   Asegurar que `similarity_threshold` esté dentro de un rango lógico (ej., 0.0 a 1.0).
        -   Validar el formato de URLs como `vector_db_url`.
    -   **Agrupación de Configuraciones**: Para clases de configuración muy grandes, Pydantic permite anidar modelos (ej. `LLMSettings` como un campo dentro de `QueryServiceSettings`). Para el tamaño actual, la estructura plana es manejable, pero es una opción para el futuro si la complejidad crece.
    -   **Configuración de Reintentos por Cliente**: Actualmente, hay una política de reintentos genérica (`max_retries`, etc.). **Consideración**: Si diferentes clientes (Groq, VectorDB) requieren políticas de reintento muy dispares, se podría considerar tener secciones de configuración de reintentos específicas por cliente (ej. `groq_retry_settings: RetryConfig`, `vector_db_retry_settings: RetryConfig`).
    -   **Consistencia en Nombres de Timeouts**: Los timeouts como `llm_timeout_seconds`, `embedding_service_timeout`, `search_timeout_seconds` son claros. Mantener esta consistencia es bueno.

En general, el sistema de configuración es un punto fuerte del `Query Service`, proporcionando una base sólida, segura y flexible para su operación.
