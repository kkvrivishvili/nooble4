# Módulo de Configuración (Query Service)

## 1. Propósito General

El módulo `config` centraliza la gestión de toda la configuración del `Query Service`. Su objetivo es proporcionar un único punto de acceso a todos los parámetros necesarios para que el servicio funcione correctamente, desde credenciales de API hasta configuraciones de comportamiento y rendimiento.

Utiliza un enfoque basado en `Pydantic` y `pydantic-settings`, lo que permite una configuración fuertemente tipada, validada y cargada de manera jerárquica desde múltiples fuentes (variables de entorno, archivos `.env`).

## 2. Patrones y Conexión con `common`

La gestión de la configuración sigue un patrón de herencia y especialización, dependiendo en gran medida del módulo `common` para mantener la consistencia en todo el ecosistema de microservicios.

- **`common/config/base_settings.py`**: Define `CommonAppSettings`, una clase base que contiene configuraciones compartidas por todos los servicios (ej. `redis_url`, `log_level`, `service_name`).
- **`common/config/service_settings/query.py`**: Aquí se define `QueryServiceSettings`, que hereda de `CommonAppSettings`. Esta clase especializada añade y/o sobrescribe las configuraciones que son exclusivas del `Query Service`.
- **`query_service/config/settings.py`**: Este es el punto de entrada final. Importa `QueryServiceSettings` y la instancia a través de una función `get_settings()` cacheada con `lru_cache`. Esto asegura que la configuración se carga una sola vez y se reutiliza como un singleton en toda la aplicación, optimizando el rendimiento.

Este patrón es una excelente práctica de diseño, ya que promueve la reutilización (DRY - Don't Repeat Yourself) y mantiene una clara separación entre la configuración base y la específica del servicio.

## 3. Implementación Técnica

La clase `QueryServiceSettings` utiliza `pydantic-settings` para cargar automáticamente los valores desde:

1.  **Variables de entorno**: Busca variables con el prefijo `QUERY_`. Por ejemplo, `QUERY_GROQ_API_KEY` se mapeará al campo `groq_api_key`.
2.  **Archivo `.env`**: Si existe un archivo `.env` en la raíz del proyecto, cargará las variables definidas allí.
3.  **Valores por defecto**: Si no se encuentra ninguna de las anteriores, se utilizan los valores definidos en la clase.

La función `get_settings()` en `query_service/config/settings.py` asegura que solo haya una instancia de esta clase de configuración en toda la aplicación.

## 4. Parámetros de Configuración Clave

La configuración se puede agrupar en las siguientes categorías:

- **Configuración del Servicio**: `domain_name`, `worker_count`.
- **API de Groq**: `groq_api_key`, `groq_api_base_url`.
- **Parámetros de LLM**: `default_llm_model`, `llm_temperature`, `llm_max_tokens`, `llm_timeout_seconds`, y los parámetros de penalización. También incluye `available_llm_models` para validar los modelos solicitados.
- **Vector Store**: `vector_db_url`, `similarity_threshold`, `default_top_k`.
- **RAG (Retrieval-Augmented Generation)**: `rag_context_window`, `rag_system_prompt_template`.
- **Rendimiento y Resiliencia**: `max_retries`, `retry_delay_seconds`, `enable_query_tracking`.

## 5. Opinión de la Implementación

La implementación de la configuración es **excepcional** y sigue las mejores prácticas modernas para aplicaciones en Python:

- **Fuertemente Tipada**: El uso de Pydantic previene errores comunes al forzar los tipos de datos correctos (ej. `int`, `float`, `str`).
- **Validación Automática**: Pydantic se encarga de validar que los valores cumplan con las restricciones definidas.
- **Centralizada y Jerárquica**: La herencia desde `CommonAppSettings` es limpia y escalable.
- **Segura**: Fomenta el uso de variables de entorno para información sensible como las API keys, evitando que se guarden en el código fuente.

No se observan inconsistencias ni debilidades en este módulo. Es un ejemplo claro de cómo debe gestionarse la configuración en un microservicio moderno.
