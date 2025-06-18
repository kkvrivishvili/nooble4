# Query Service

## 1. Descripción General

El **Query Service** es un microservicio asíncrono diseñado para manejar consultas de búsqueda semántica y generación de respuestas mediante RAG (Retrieval-Augmented Generation). Su principal responsabilidad es recibir una pregunta de un usuario, buscar información relevante en una base de datos vectorial y, opcionalmente, usar un Modelo de Lenguaje Grande (LLM) para generar una respuesta coherente basada en el contexto encontrado.

El servicio está construido en Python (3.9+) utilizando FastAPI para la interfaz HTTP (principalmente para health checks, métricas y gestión del ciclo de vida) y se comunica a través de Redis Streams para el procesamiento de tareas asíncronas, que es donde reside la lógica de negocio principal.

## 2. Arquitectura

El servicio sigue una arquitectura de microservicios limpia y desacoplada, organizada en los siguientes módulos:

 <!-- Reemplazar con un diagrama real si es posible -->

- **`main.py` (Punto de Entrada)**: Configura e inicia la aplicación FastAPI. Utiliza el gestor de ciclo de vida (`lifespan`) de FastAPI para inicializar y detener de forma ordenada los recursos críticos, incluyendo el `RedisManager` (para la conexión a Redis) y múltiples instancias de `QueryWorker`. También expone endpoints HTTP para health checks y monitoreo.

- **`workers`**: El motor del servicio. Los `QueryWorker` escuchan constantemente en una cola de Redis (`DomainAction` stream). Cuando llega una nueva tarea, la recogen y la pasan a la capa de servicio.

- **`services`**: Actúa como una fachada (`QueryService`). Recibe la `DomainAction` del worker y la delega al handler apropiado según el tipo de acción (`query.generate` o `query.search`).

- **`handlers`**: Contiene la lógica de negocio principal. Orquesta las llamadas a los diferentes clientes para cumplir con la solicitud.
    - `RAGHandler`: Procesa el flujo completo de RAG (embedding -> búsqueda -> generación).
    - `SearchHandler`: Maneja búsquedas vectoriales puras (embedding -> búsqueda).

- **`clients`**: Abstrae la comunicación con todos los servicios externos:
    - `GroqClient`: Para interactuar con la API del LLM (Groq).
    - `VectorClient`: Para realizar búsquedas en la base de datos vectorial.
    - `EmbeddingClient`: Para solicitar la conversión de texto a embeddings a otro servicio.

- **`models`**: Define todas las estructuras de datos (`payloads`) utilizando Pydantic, garantizando la validación y consistencia de los datos.

- **`config`**: Gestiona toda la configuración del servicio de manera centralizada y segura, cargando desde variables de entorno y archivos `.env`.

- **`common` (Módulo Externo)**: Proporciona clases base, modelos y utilidades compartidas entre todos los microservicios, asegurando consistencia y reutilización de código.

## 3. Interacción con Otros Microservicios

El `Query Service` se integra con otros microservicios de la plataforma de la siguiente manera:

- **`Embedding Service`**: 
    - **Comunicación**: Directa y Asíncrona.
    - **Mecanismo**: El `Query Service` utiliza su `EmbeddingClient` para enviar solicitudes de generación de embeddings al `Embedding Service` a través de Redis Streams (usando objetos `DomainAction`). Espera una respuesta (también vía Redis) que contiene los vectores de embedding.
    - **Propósito**: Obtener los embeddings vectoriales para las preguntas de los usuarios, necesarios para la búsqueda semántica.

- **`Ingestion Service`** (o cualquier servicio que popule la base de datos vectorial):
    - **Comunicación**: Indirecta.
    - **Mecanismo**: El `Ingestion Service` es responsable de procesar documentos, generar sus embeddings (posiblemente usando el `Embedding Service`), y almacenarlos en la base de datos vectorial. El `Query Service` no se comunica directamente con el `Ingestion Service` para las operaciones de consulta. En su lugar, accede a los datos ya procesados y almacenados por el `Ingestion Service` a través de su `VectorClient`.
    - **Propósito**: El `Query Service` consume los datos que el `Ingestion Service` ha preparado y almacenado en la base de datos vectorial.

- **`Agent Execution Service`** (y otros servicios que necesiten realizar consultas):
    - **Comunicación**: Asíncrona, iniciada por el servicio externo.
    - **Mecanismo**: Cualquier servicio, como el `Agent Execution Service`, que necesite realizar una búsqueda semántica o una consulta RAG, debe construir un objeto `DomainAction` y publicarlo en el stream de Redis designado para el `Query Service` (definido por la variable de entorno `REDIS_STREAM_QUERY_SERVICE` o similar, procesado por `QueryWorker`).
    - **Propósito**: Permitir que otros servicios deleguen tareas de búsqueda y generación de respuestas al `Query Service`.

## 4. Flujo de una Solicitud RAG (`query.generate`)

El flujo típico para una solicitud de generación aumentada por recuperación es el siguiente:

1.  Un servicio externo publica una `DomainAction` con `action_type='query.generate'` en el stream de Redis.
2.  Uno de los `QueryWorker` consume el mensaje.
3.  El worker pasa la acción al `QueryService`.
4.  El `QueryService` ve el `action_type` y delega la tarea al `RAGHandler`.
5.  El `RAGHandler` orquesta el flujo:
    a. Llama al `EmbeddingClient` para obtener el vector de la pregunta.
    b. Llama al `VectorClient` con ese vector para recuperar chunks de contexto.
    c. Construye un prompt enriquecido con el contexto y la pregunta.
    d. Llama al `GroqClient` para generar la respuesta.
6.  La respuesta final (por ejemplo, `QueryGenerateResponse`) se empaqueta en un `DomainActionResponse` y se publica en una cola de respuesta de Redis si se especificó un `callback_queue` y `callback_action_type` en la `DomainAction` original. Si no, la acción se considera "fire-and-forget" por parte del `Query Service`.

## 5. Cómo Interactuar con Query Service (Para Otros Microservicios)

Para que otros microservicios (como `Agent Execution Service` o cualquier otro productor de tareas) interactúen con el `Query Service`, deben enviar mensajes a través de Redis Streams utilizando un formato estandarizado: el objeto `DomainAction`.

### a. El Objeto `DomainAction`

Este objeto es la unidad de trabajo estándar. Se recomienda utilizar la clase `DomainAction` definida en el módulo `common` (o una estructura compatible).

Campos clave de `DomainAction`:

- **`action_id` (UUID)**: ID único para la acción (generado por el solicitante).
- **`action_type` (str)**: Tipo de acción a realizar. Para `Query Service`:
    - `"query.generate"`: Para una consulta RAG completa (búsqueda + generación LLM).
    - `"query.search"`: Para una búsqueda vectorial únicamente.
- **`data` (dict)**: Payload específico de la acción. Ver `models/payloads.py` para las estructuras esperadas (`QueryGeneratePayload`, `QuerySearchPayload`).
- **`source_service` (str)**: Nombre del servicio que origina la acción (e.g., `"agent_execution_service"`).
- **`target_service` (str)**: Debe ser `"query_service"`.
- **`timestamp` (datetime)**: Momento de creación de la acción.
- **`trace_id` (UUID, opcional)**: ID para trazar la solicitud a través de múltiples servicios.
- **`correlation_id` (UUID, opcional)**: ID para correlacionar esta acción con otras.
- **`metadata` (dict, opcional)**: Metadatos adicionales, como configuraciones de override para la consulta (e.g., `top_k`, `model_name`).
- **`callback_queue` (str, opcional)**: Nombre del stream de Redis donde `Query Service` debe enviar la respuesta (`DomainActionResponse`).
- **`callback_action_type` (str, opcional)**: El `action_type` que se usará en el `DomainActionResponse` de vuelta (e.g., `"query.generate.result"`).

### b. Payloads de Solicitud (`data`)

Consulte los modelos Pydantic en `query_service/models/payloads.py` para la estructura detallada:

- **Para `action_type='query.generate'`**: Usar `QueryGeneratePayload`.
    - Campos clave: `query_text`, `collection_ids` (opcional), `tenant_id`, `session_id`, `user_id` (opcional), `llm_config` (opcional), `search_config` (opcional), `conversation_history` (opcional).
- **Para `action_type='query.search'`**: Usar `QuerySearchPayload`.
    - Campos clave: `query_text`, `collection_ids` (opcional), `tenant_id`, `session_id`, `top_k` (opcional), `similarity_threshold` (opcional).

### c. Publicación en Redis Streams

1.  **Conexión a Redis**: Utilizar un cliente Redis compatible con streams (e.g., `redis-py` con soporte asíncrono si es necesario).
2.  **Stream de Destino**: El `QueryWorker` escucha en un stream cuyo nombre se configura mediante una variable de entorno (e.g., `REDIS_STREAM_QUERY_SERVICE`, consultar la configuración del `Query Service` desplegado para el valor exacto). Típicamente sigue el formato `[nombre_servicio]:actions` o `domain_actions:[nombre_servicio]`.
3.  **Serialización**: El objeto `DomainAction` (con su `data` payload) debe ser serializado (e.g., a JSON, y luego a bytes) antes de ser añadido al stream.

### d. Recepción de Respuestas (Callbacks)

Si se especifican `callback_queue` y `callback_action_type` en la `DomainAction`:

1.  El `Query Service` procesará la solicitud.
2.  Al finalizar, construirá un objeto `DomainActionResponse`.
    - `success` (bool): Indica si la operación fue exitosa.
    - `data` (dict): Contiene la respuesta (`QueryGenerateResponse`, `QuerySearchResponse`) o detalles del error (`QueryErrorResponse`).
    - `original_action_id` (UUID): El `action_id` de la solicitud original.
    - `trace_id`, `correlation_id`, etc.
3.  Este `DomainActionResponse` será publicado en el `callback_queue` especificado, con el `action_type` indicado en `callback_action_type`.
4.  El servicio solicitante debe tener un worker escuchando en esa `callback_queue` para consumir la respuesta.

### Ejemplo (Conceptual - Python usando una librería común `common.redis`)

```python
# Asumiendo que tienes una instancia de RedisManager y modelos comunes
from common.redis.redis_manager import RedisManager
from common.models.domain_action import DomainAction, DomainActionResponse # Asumiendo que existen
from query_service.models.payloads import QueryGeneratePayload # O una versión común
import uuid
import asyncio

async def send_query_to_query_service(redis_manager: RedisManager, user_query: str):
    query_payload = QueryGeneratePayload(
        query_text=user_query,
        tenant_id="some-tenant",
        session_id=str(uuid.uuid4()),
        # ... otros campos necesarios ...
    )

    action = DomainAction(
        action_id=uuid.uuid4(),
        action_type="query.generate",
        data=query_payload.model_dump(), # Serializar el payload Pydantic
        source_service="my_calling_service",
        target_service="query_service",
        callback_queue="my_calling_service:responses", # Donde espero la respuesta
        callback_action_type="query.generate.result"
    )

    # El nombre del stream debe ser el que QueryService está escuchando
    query_service_stream_name = "query_service:actions" # Ejemplo, verificar config

    await redis_manager.publish_action(query_service_stream_name, action)
    print(f"Acción {action.action_id} enviada a Query Service.")

    # ... (lógica para escuchar en 'my_calling_service:responses' no mostrada) ...

# Para ejecutar (ejemplo)
# async def main():
#     redis_url = "redis://localhost:6379"
#     redis_manager = RedisManager(redis_url)
#     await redis_manager.initialize()
#     await send_query_to_query_service(redis_manager, "¿Qué es RAG?")
#     await redis_manager.close()
# 
# if __name__ == "__main__":
#     asyncio.run(main())
```

**Nota Importante**: Es crucial que los modelos de datos (`DomainAction`, payloads, respuestas) estén estandarizados y sean consistentes entre los servicios. Idealmente, estos modelos deberían provenir de una librería `common` compartida.

## 6. Cómo Ejecutar el Servicio

### Requisitos
- Python 3.9+
- Docker y Docker Compose (para Redis y otros servicios de la plataforma)
- Un archivo `.env` configurado con las variables necesarias.

### Variables de Entorno Clave (`.env`)

```
# Redis
REDIS_URL=redis://localhost:6379

# Query Service
QUERY_GROQ_API_KEY="tu_api_key_de_groq"
QUERY_VECTOR_DB_URL="http://localhost:8006" # URL del servicio de Vector Store

# Logging
LOG_LEVEL=INFO
```

### Instalación de Dependencias

```bash
# Navega al directorio del servicio
cd query_service

# (Opcional) Crea y activa un entorno virtual
python -m venv venv
source venv/bin/activate  # En Windows: venv\Scripts\activate

# Instala las dependencias
pip install -r requirements.txt
```

### Ejecución

El servicio se puede iniciar directamente ejecutando el `main.py`:

```bash
python -m query_service.main
```

Esto iniciará el servidor `uvicorn` con la aplicación FastAPI y lanzará los `QueryWorker` en segundo plano para empezar a procesar tareas de la cola de Redis.

## 7. Endpoints HTTP

El servicio expone algunos endpoints HTTP a través de FastAPI, principalmente para monitoreo:

- `GET /`: Información básica del servicio.
- `GET /health`: Health check simple.
- `GET /health/detailed`: Health check detallado que verifica la conexión con Redis y el estado de los workers.
- `GET /docs`: Documentación interactiva de la API (Swagger UI).

## 8. Inconsistencias y Mejoras Pendientes

Durante el análisis del código, se identificaron los siguientes puntos a mejorar:

1.  **Typo en Nombre de Archivo (Solucionado)**: El archivo `clients/vectror_client.py` ha sido renombrado a `clients/vector_client.py`.
2.  **Fallback de Embedding en Handlers**: Tanto `SearchHandler` como `RAGHandler` implementan mecanismos de fallback para generar embeddings simulados (determinístico basado en hash para búsqueda, aleatorio para RAG) si la llamada al `Embedding Service` falla. Si bien esto permite que el servicio continúe operando, **puede llevar a resultados de búsqueda semánticamente incorrectos o a respuestas RAG engañosas**. Esta decisión de diseño fue tomada para mantener una cierta operatividad incluso con fallos en dependencias, pero se debe ser consciente de sus implicaciones. Para entornos de producción críticos, se recomienda enfáticamente configurar el sistema para que falle la operación si no se puede obtener un embedding real, o implementar una estrategia de reintento más robusta antes de recurrir al fallback.
