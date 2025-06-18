# Query Service

## 1. Descripción General

El **Query Service** es un microservicio asíncrono diseñado para manejar consultas de búsqueda semántica y generación de respuestas mediante RAG (Retrieval-Augmented Generation). Su principal responsabilidad es recibir una pregunta de un usuario, buscar información relevante en una base de datos vectorial y, opcionalmente, usar un Modelo de Lenguaje Grande (LLM) para generar una respuesta coherente basada en el contexto encontrado.

El servicio está construido en Python utilizando FastAPI para la interfaz HTTP (principalmente para health checks) y se comunica a través de Redis Streams para el procesamiento de tareas asíncronas.

## 2. Arquitectura

El servicio sigue una arquitectura de microservicios limpia y desacoplada, organizada en los siguientes módulos:

 <!-- Reemplazar con un diagrama real si es posible -->

- **`main.py` (Punto de Entrada)**: Inicia la aplicación FastAPI y los workers. Gestiona el ciclo de vida de los recursos (como la conexión a Redis).

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

## 3. Flujo de una Solicitud RAG (`query.generate`)

1.  Un servicio externo publica una `DomainAction` con `action_type='query.generate'` en el stream de Redis.
2.  Uno de los `QueryWorker` consume el mensaje.
3.  El worker pasa la acción al `QueryService`.
4.  El `QueryService` ve el `action_type` y delega la tarea al `RAGHandler`.
5.  El `RAGHandler` orquesta el flujo:
    a. Llama al `EmbeddingClient` para obtener el vector de la pregunta.
    b. Llama al `VectorClient` con ese vector para recuperar chunks de contexto.
    c. Construye un prompt enriquecido con el contexto y la pregunta.
    d. Llama al `GroqClient` para generar la respuesta.
6.  La respuesta final se empaqueta en un `DomainActionResponse` y se devuelve a través de Redis (si se solicitó un callback).

## 4. Cómo Ejecutar el Servicio

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

## 5. Endpoints HTTP

El servicio expone algunos endpoints HTTP a través de FastAPI, principalmente para monitoreo:

- `GET /`: Información básica del servicio.
- `GET /health`: Health check simple.
- `GET /health/detailed`: Health check detallado que verifica la conexión con Redis y el estado de los workers.
- `GET /docs`: Documentación interactiva de la API (Swagger UI).

## 6. Inconsistencias y Mejoras Pendientes

Durante el análisis del código, se identificaron los siguientes puntos a mejorar:

1.  **Typo en Nombre de Archivo (Solucionado)**: El archivo `clients/vectror_client.py` ha sido renombrado a `clients/vector_client.py`.
2.  **Fallback de Embedding**: El `SearchHandler` utiliza un embedding simulado si falla la comunicación con el `Embedding Service`. Esto puede llevar a resultados de búsqueda incorrectos y debería ser revisado. Se recomienda que falle la operación si no se puede obtener un embedding real.
