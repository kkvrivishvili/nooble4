# Módulo de Handlers (Query Service)

## 1. Propósito General

El módulo `handlers` es el cerebro del `Query Service`. Su función es orquestar la lógica de negocio principal, coordinando las interacciones entre los diferentes `clients` para procesar una solicitud de principio a fin. Cada handler está diseñado para gestionar un tipo específico de tarea (ej. búsqueda vectorial pura vs. generación de respuestas con RAG).

Estos handlers son invocados por el `QueryService` (en el módulo `services`), que actúa como una fachada, delegando la acción correcta al handler apropiado.

## 2. Patrones y Conexión con `common`

Los handlers siguen un patrón de diseño claro y dependen de las abstracciones del módulo `common`:

- **`BaseHandler`**: Todos los handlers heredan de `common.handlers.BaseHandler`. Esta clase base les proporciona acceso estandarizado a la configuración de la aplicación (`app_settings`), una instancia de `logging` y, opcionalmente, una conexión directa a Redis si fuera necesaria. Esto asegura un comportamiento consistente y reduce el código repetido.
- **Inyección de Dependencias**: Los handlers reciben sus dependencias (como los `clients`) durante la inicialización. Esto facilita las pruebas y el mantenimiento, ya que las dependencias pueden ser reemplazadas por mocks.

## 3. Handlers Implementados

A continuación se detalla cada handler dentro de este módulo.

### 3.1. `SearchHandler`

- **Archivo**: `search_handler.py`
- **Funcionalidad**: Maneja solicitudes de **búsqueda vectorial pura**. Su objetivo es encontrar y devolver los documentos o fragmentos de texto (`chunks`) más relevantes para una consulta, sin realizar ninguna generación de lenguaje natural con un LLM. Es ideal para funcionalidades de "búsqueda semántica" o "encontrar documentos similares".
- **Flujo de Trabajo**:
    1.  Recibe el texto de la consulta y los parámetros de búsqueda.
    2.  Invoca al `EmbeddingClient` para convertir el texto de la consulta en un vector de embedding.
    3.  Usa el `VectorClient` para realizar la búsqueda en la base de datos vectorial con el embedding obtenido.
    4.  Formatea y devuelve una lista estructurada de resultados (`QuerySearchResponse`).
- **Dependencias**: `VectorClient`, `EmbeddingClient` (opcionalmente inyectado).

### 3.2. `RAGHandler`

- **Archivo**: `rag_handler.py`
- **Funcionalidad**: Orquesta el flujo completo de **Retrieval-Augmented Generation (RAG)**. Su propósito es responder preguntas utilizando un LLM, basando la respuesta en el contexto extraído de la base de datos vectorial. Es el núcleo de la funcionalidad de Q&A del servicio.
- **Flujo de Trabajo**:
    1.  **Obtener Embedding**: Al igual que el `SearchHandler`, primero obtiene el embedding de la consulta.
    2.  **Búsqueda (Retrieval)**: Utiliza el `VectorClient` para recuperar los `chunks` de contexto más relevantes.
    3.  **Construir Prompt**: Ensambla un prompt complejo para el LLM, que incluye el contexto recuperado, la pregunta original del usuario y un prompt de sistema (configurable).
    4.  **Generación (Generation)**: Envía el prompt final al `GroqClient` para generar una respuesta en lenguaje natural.
    5.  **Formatear Respuesta**: Empaqueta la respuesta generada junto con metadatos (ej. fuentes utilizadas, uso de tokens) en un objeto `QueryGenerateResponse`.
- **Dependencias**: `VectorClient`, `GroqClient`, `EmbeddingClient`.

## 4. Opinión de la Implementación e Inconsistencias

- **Excelente Separación de Responsabilidades**: La decisión de separar `SearchHandler` de `RAGHandler` es un gran acierto de diseño. Permite que el servicio ofrezca dos funcionalidades distintas (búsqueda y Q&A) de manera limpia y eficiente, reutilizando componentes como el `VectorClient`.

- :warning: **Inconsistencia en Manejo de Errores de Embedding**: Se ha detectado una inconsistencia en cómo los handlers manejan la falla al obtener un embedding:
    - El `RAGHandler` falla si no puede obtener un embedding, lo cual es el comportamiento correcto para un flujo RAG (sin embedding, no hay búsqueda, no hay respuesta).
    - El `SearchHandler`, en su método `_get_query_embedding`, tiene un mecanismo de **fallback a un embedding simulado** si la llamada al `Embedding Service` falla. Este embedding se genera a partir de un hash del texto. Si bien esto puede hacer que el endpoint de búsqueda sea más resiliente, puede devolver resultados **semánticamente incorrectos y engañosos**, ya que la búsqueda no se basaría en el significado real de la consulta. Esta es una decisión de diseño cuestionable para un entorno de producción y debería ser revisada. Podría ser un remanente de desarrollo o una característica que necesita ser documentada cuidadosamente en la API.

Salvo por esa inconsistencia, la arquitectura de los handlers es sólida, modular y sigue buenas prácticas de desarrollo de software.
