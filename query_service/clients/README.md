# Módulo de Clientes (Query Service)

## 1. Propósito General

El módulo `clients` es el responsable de gestionar toda la comunicación entre el `Query Service` y los servicios externos. Su función principal es abstraer la complejidad de las interacciones de red, ya sea con otros microservicios internos (como el `Embedding Service`) o con APIs de terceros (como `Groq` para LLMs y el `Vector Store`).

Los clientes aquí definidos se apoyan fuertemente en las clases base proporcionadas por el módulo `common` (ej. `BaseHTTPClient`, `BaseRedisClient`), asegurando consistencia en la gestión de errores, reintentos y configuración de red.

## 2. Clientes Implementados

Actualmente, el módulo contiene los siguientes clientes:

-   **`EmbeddingClient`**: Para solicitar la generación de embeddings al `Embedding Service`.
-   **`GroqClient`**: Para interactuar con la API del LLM de Groq.
-   **`VectorClient`**: Para realizar búsquedas en el `Vector Store`.

## 3. Detalles de Implementación y Diseño (Revisión Detallada)

### 3.1. `EmbeddingClient`

-   **Archivo**: `embedding_client.py`
-   **Funcionalidad**: Comunica con el `Embedding Service` vía Redis Streams (usando `BaseRedisClient` de `common`) para generar embeddings.
-   **Implementación Técnica**:
    -   `request_embeddings`: Solicitud asíncrona para múltiples textos, con opción de callback o "fire-and-forget".
    -   `request_query_embedding`: Solicitud pseudo-síncrona para un único texto (ej. una consulta), esperando respuesta.
-   **Conexión con `common`**: Utiliza `BaseRedisClient` y los modelos `DomainAction`/`DomainActionResponse`.
-   **Análisis y Puntos de Interés**:
    -   **Fortalezas**: Clara distinción entre flujos síncronos y asíncronos. Buen uso de `correlation_id` para el patrón pseudo-síncrono.
    -   **Timeout Configurable**: El timeout de 30s en `request_query_embedding` está hardcodeado. **Mejora Sugerida**: Hacer este timeout configurable mediante `QueryServiceSettings` para mayor adaptabilidad.
    -   **Manejo de Errores Específico**: En `request_query_embedding`, si `response.success` es `False`, se lanza una `Exception` genérica. **Mejora Sugerida**: Lanzar una excepción más específica (ej. `EmbeddingGenerationError` o reutilizar `ExternalServiceError` de `common`) para facilitar el manejo de errores por parte de los llamadores.
    -   **`action_type`**: Los `action_type` (`embedding.generate`, `embedding.generate_query`) deben estar perfectamente sincronizados con los esperados por el `EmbeddingService`.

### 3.2. `GroqClient`

-   **Archivo**: `groq_client.py`
-   **Funcionalidad**: Cliente HTTP para la API de Groq, permitiendo generación de texto con LLMs.
-   **Implementación Técnica**:
    -   Extiende `BaseHTTPClient` de `common`.
    -   Implementa reintentos con `tenacity` (configurable para `ServiceUnavailableError`).
    -   Método `generate` con soporte para múltiples parámetros de la API de Groq.
    -   Método `generate_with_messages` para interacciones conversacionales.
    -   Utilidades: `list_models`, `get_model_info`, `health_check`.
-   **Conexión con `common`**: Uso de `BaseHTTPClient` para operaciones HTTP.
-   **Análisis y Puntos de Interés**:
    -   **Fortalezas**: Implementación robusta y completa. El logging detallado de uso de tokens y tiempos es excelente.
    -   **Streaming**: El parámetro `stream` en `generate` está presente pero la funcionalidad no está implementada. Si se requiere a futuro, necesitará desarrollo adicional. Actualmente, el README debe reflejar que no es funcional.
    -   **Manejo de Errores de Groq**: Actualmente maneja `httpx.TimeoutException` y `Exception` genérica. **Mejora Sugerida**: Mapear códigos de error HTTP específicos de Groq (400, 401, 403, 429) a excepciones más descriptivas (ej. `GroqBadRequestError`, `GroqAuthenticationError`, `GroqRateLimitError`) para un diagnóstico y manejo más fino. `BaseHTTPClient` ya tiene una base para esto que se podría extender o especializar.
    -   **Configuración de Reintentos**: Los parámetros de reintento (intentos, backoff) están hardcodeados. **Mejora Sugerida**: Hacerlos configurables desde `QueryServiceSettings`.

### 3.3. `VectorClient`

-   **Archivo**: `vector_client.py`
-   **Funcionalidad**: Cliente para interactuar con una base de datos vectorial (Vector Store).
-   **Implementación Técnica**:
    -   Extiende `BaseHTTPClient`.
    -   Diseñado para ser agnóstico al proveedor del Vector Store (asumiendo una API REST común).
    -   Métodos: `search`, `_parse_search_results`, `get_collections`, `get_collection_info`, `health_check`.
-   **Conexión con `common`**: Uso de `BaseHTTPClient`.
-   **Análisis y Puntos de Interés**:
    -   **Fortalezas**: Buena abstracción que busca aislar del proveedor específico.
    -   **Agnosticismo y `_parse_search_results`**: El intento de ser agnóstico es bueno, pero `_parse_search_results` hace suposiciones sobre el formato de respuesta (ej. `item.get("id")`, `item.get("content", item.get("text"))`). **Consideración**: Si se soportan múltiples backends con APIs divergentes, este método requerirá una estrategia más avanzada (ej. patrón Adapter o un sistema de parsers por proveedor).
    -   **Filtrado**: La construcción de filtros es genérica. Las sintaxis de filtro varían mucho entre Vector Stores. **Consideración**: Para filtrado avanzado, mantener el agnosticismo puede ser un desafío. El diseño actual es adecuado para filtros simples o si el backend puede interpretar una estructura de filtro común.
    -   **Endpoints de API**: Los paths (`/api/v1/search`, etc.) están hardcodeados. **Mejora Sugerida**: Hacerlos configurables si hay variabilidad entre posibles backends o versiones de API.
    -   **`similarity_threshold` vs `score_threshold`**: El parámetro del método `search` es `similarity_threshold`, pero se envía como `score_threshold` en el payload. Aunque funcional si el backend espera `score_threshold`, es una leve inconsistencia semántica. **Recomendación**: Aclarar en el código o la documentación si son intercambiables o si el backend espera específicamente "score", y alinear los nombres si es posible.

## 4. Consideraciones Generales y Patrones

-   **Abstracción y Cohesión**: Los clientes logran una buena abstracción de las comunicaciones externas. Cada cliente tiene una alta cohesión, enfocándose en un único servicio externo.
-   **Configuración Centralizada**: El uso de `QueryServiceSettings` para URLs, API keys y timeouts es una práctica sólida, promoviendo la configuración externa.
-   **Manejo de Errores**: La herencia de `BaseHTTPClient` y el uso de `BaseRedisClient` proporcionan una base sólida para el manejo de errores de red y excepciones. Las mejoras sugeridas apuntan a una granularidad aún mayor para errores específicos de cada servicio.
-   **Extensibilidad**: El diseño modular facilita la adición de nuevos clientes o la modificación de los existentes con un impacto mínimo en el resto del `Query Service`.

Este módulo es fundamental para la robustez y mantenibilidad del sistema, actuando como una capa de aislamiento crucial frente a las complejidades y la volatilidad de los servicios externos.

## 5. Consistencia de Código (Imports y Variables)

Se realizó una revisión de la consistencia del código en los archivos Python del módulo `clients` (`__init__.py`, `embedding_client.py`, `groq_client.py`, `vector_client.py`) con los siguientes hallazgos:

### 5.1. Imports

-   **Organización General**: Los imports están, en su mayoría, bien organizados, agrupando las bibliotecas estándar primero, luego las de terceros, seguidas por los imports del módulo `common` y finalmente los imports relativos del proyecto.
-   **Consistencia**:
    -   En `vector_client.py`, se corrigió la posición de `import time` para agruparlo correctamente con los imports de la biblioteca estándar.
    -   En `__init__.py`, el orden de importación y de `__all__` es alfabético inverso. Aunque funcional, una convención estrictamente alfabética podría considerarse para uniformidad total, pero no es un problema crítico.
-   **Sugerencias Menores (Opcionales)**:
    -   Para una pulcritud máxima, los tipos específicos importados de `typing` (ej., `from typing import List, Optional, Dict, Any`) podrían ordenarse alfabéticamente (ej., `Any, Dict, List, Optional`).
    -   En `embedding_client.py`, el import `from common.clients import BaseRedisClient` es funcional. Una alternativa más explícita, si se prefiere una consistencia absoluta con otros imports de submódulos de `common`, sería `from common.clients.base_redis_client import BaseRedisClient`. Esto depende de las convenciones del proyecto y de cómo `common/clients/__init__.py` expone sus miembros.

### 5.2. Nomenclatura y Estructura de Variables

-   **Convenciones**: Se sigue consistentemente PascalCase para nombres de clases (ej., `EmbeddingClient`, `GroqClient`, `VectorClient`) y snake_case para nombres de funciones, métodos y variables (ej., `request_embeddings`, `api_key`, `query_embedding`).
-   **Claridad**: Los nombres de variables y parámetros son descriptivos y claros, facilitando la comprensión del código.
-   **Logging**: El uso de `self.logger = logging.getLogger(__name__)` es estándar y se aplica consistentemente en todos los clientes.

### 5.3. Conclusión de la Revisión de Consistencia

El módulo `clients` demuestra un alto grado de consistencia en la organización de imports y en la nomenclatura de variables. Las correcciones y sugerencias mencionadas son menores y apuntan a un nivel de pulcritud ideal, pero el código actual es claro, funcional y sigue buenas prácticas generales.
