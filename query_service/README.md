# Query Service

## Características y Estado

| Característica | Descripción | Estado |
|----------------|-------------|--------|
| **RAG Workflow** | Búsqueda de documentos + generación de texto | ✅ Operativo |
| **Búsqueda Pura** | Búsqueda vectorial sin generación de texto | ✅ Operativo |
| **LLM Integration** | Groq LLM con sistema de reintentos | ✅ Operativo |
| **Domain Actions** | Comunicación asíncrona vía Redis | ✅ Operativo |
| **Validación por tier** | Límites y capacidades según tier | ✅ Operativo |
| **Control de calidad** | Umbrales de similitud y relevancia | ✅ Operativo |
| **Callbacks asíncronos** | Notificación de resultados | ✅ Operativo |
| **Métricas básicas** | Endpoints para métricas de performance | ✅ Operativo |
| **Caché de búsquedas** | Optimización mediante caché de resultados | ⚠️ Parcial |
| **Análisis avanzado** | Estadísticas detalladas de uso y relevancia | ❌ Pendiente |

## Estructura de Archivos y Carpetas

```plaintext
query_service/
├ __init__.py
├ main.py
├ requirements.txt
├ clients/
│  ├ __init__.py
│  ├ groq_client.py
│  ├ vector_store_client.py
│  └ embedding_client.py
├ config/
│  ├ __init__.py
│  └ settings.py
├ handlers/
│  ├ __init__.py
│  ├ query_handler.py
│  ├ context_handler.py
│  ├ query_callback_handler.py
│  └ embedding_callback_handler.py
├ models/
│  ├ __init__.py
│  └ actions.py
├ services/
│  ├ __init__.py
│  ├ rag_processor.py
│  └ vector_search_service.py
└ workers/
   ├ __init__.py
   └ query_worker.py
```

## Arquitectura

El Query Service implementa un flujo RAG (Retrieval-Augmented Generation) para proporcionar respuestas precisas a consultas en lenguaje natural basadas en documentos relevantes. Integra búsqueda vectorial y generación de texto mediante LLM.

### Diagrama de Integración

```plaintext
┌──────────────────────────────────────────────────────────┐
│                          Clientes                        │
│ Agent Exec │  Ingestion │  Embedding │  UI/Other         │
└──────────────────────────────────────────────────────────┘
            │         │          │           │
            ▼         ▼          ▼           ▼
    ┌────────────────────────────────────────────────┐
    │              Query Service                     │
    │    (FastAPI health + QueryWorker)              │
    └────────────────────────────────────────────────┘
                          │
                          ▼
       ┌──────────────────────────────────────────────┐
       │    Domain Actions Queue: `query.*.actions`   │
       └──────────────────────────────────────────────┘
                          │
                          ▼
       ┌──────────────────────────────────────────────┐
       │             QueryWorker                      │
       └──────────────────────────────────────────────┘
                          │
             ┌────────────┴─────────────┐
             ▼                          ▼
 ┌──────────────────────┐      ┌────────────────────────────┐
 │   QueryHandler       │      │ EmbeddingCallbackHandler   │
 └──────────────────────┘      └────────────────────────────┘
             │                          │
             ▼                          ▼
 ┌──────────────────────┐      ┌────────────────────────┐
 │ VectorStoreClient    │      │ Embedding Service via  │
 │ (search vectors)     │      │ Domain Actions         │
 └──────────────────────┘      └────────────────────────┘
             │                          │
             ▼                          ▼
       ┌──────────────────────────────────────────────┐
       │    GroqClient (LLM Generation)               │
       └──────────────────────────────────────────────┘
                          │
                          ▼
       ┌──────────────────────────────────────────────┐
       │    Callback Queue (Redis)                    │
       └──────────────────────────────────────────────┘
                          │
                          ▼
┌────────────────────────────────────────────────────────┐
│                        Callbacks                       │
│ Agent Exec │ Query Service │ Ingestion │ UI/Other      │
└────────────────────────────────────────────────────────┘
```

### Flujo de Trabajo RAG

```plaintext
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│              │     │              │     │              │
│   Cliente    │────▶│Query Service │────▶│  Embedding   │
│              │     │              │     │   Service    │
└──────────────┘     └──────────────┘     └──────────────┘
       │                    │                    │
       │                    │                    │
       │                    ▼                    │
       │              ┌──────────────┐          │
       │              │  Query con   │          │
       │              │  embedding   │◀─────────┘
       │              └──────────────┘
       │                    │
       │                    ▼
       │              ┌──────────────┐
       │              │  Vector DB   │
       │              │  Búsqueda    │
       │              └──────────────┘
       │                    │
       │                    ▼
       │              ┌──────────────┐
       │              │   LLM via    │
       │              │GroqClient    │
       │              └──────────────┘
       │                    │
       │                    ▼
       │              ┌──────────────┐
       └──────────────│  Respuesta   │
                      │  generada    │
                      └──────────────┘
```

## Componentes Principales

| Componente | Descripción | Estado |
|------------|-------------|--------|
| **QueryHandler** | Lógica principal de búsqueda y generación | ✅ Completo |
| **QueryWorker** | Procesamiento asíncrono de acciones | ✅ Completo |
| **GroqClient** | Cliente para comunicación con LLM | ✅ Completo |
| **VectorStoreClient** | Cliente para búsqueda vectorial | ✅ Completo |
| **EmbeddingClient** | Cliente para obtener embeddings | ✅ Completo |
| **QueryContextHandler** | Manejo de contexto para consultas | ✅ Completo |
| **QueryCallbackHandler** | Manejo de callbacks asíncronos | ✅ Completo |
| **RAGProcessor** | Procesamiento de flujo RAG | ✅ Completo |
| **VectorSearchService** | Servicio de búsqueda vectorial | ✅ Completo |

## Domain Actions

El Query Service implementa dos tipos principales de Domain Actions:

### 1. Acciones de Entrada

```json
// QueryGenerateAction - Genera respuesta con flujo RAG
{
  "action_id": "uuid-action-1",
  "action_type": "query.generate",
  "task_id": "task123",
  "tenant_id": "tenant1",
  "tenant_tier": "professional",
  "data": {
    "collection_id": "docs",
    "query": "¿Qué es Nooble?",
    "query_embedding": [...],  // opcional
    "similarity_top_k": 3,
    "relevance_threshold": 0.6,
    "include_sources": true
  },
  "callback_queue": "myapp.callbacks"
}

// SearchDocsAction - Solo búsqueda sin generación
{
  "action_id": "uuid-action-2",
  "action_type": "query.search",
  "task_id": "task456",
  "tenant_id": "tenant1",
  "tenant_tier": "advance",
  "data": {
    "collection_id": "docs",
    "query": "integración frontend",
    "query_embedding": [...],  // opcional
    "similarity_top_k": 5,
    "relevance_threshold": 0.7,
    "filter": {"metadata.type": "documentation"}
  },
  "callback_queue": "myapp.callbacks"
}
```

### 2. Acciones de Salida/Callback

```json
// QueryCallbackAction - Respuesta al cliente
{
  "action_id": "uuid-callback-1",
  "action_type": "query.callback",
  "task_id": "task123",
  "tenant_id": "tenant1",
  "tenant_tier": "professional",
  "data": {
    "query": "¿Qué es Nooble?",
    "response": "Nooble es una plataforma de...",
    "sources": [
      {
        "document_id": "doc1",
        "content": "Nooble: plataforma avanzada de...",
        "similarity": 0.92,
        "metadata": {...}
      }
    ],
    "metadata": {
      "query_time_ms": 350,
      "model_used": "llama3-8b-8192"
    }
  }
}
```

## API y Endpoints

El Query Service principalmente opera a través de Domain Actions y colas Redis, pero expone los siguientes endpoints HTTP:

```
GET /health           - Verifica estado general
GET /ready            - Verifica conexiones a dependencias
GET /metrics/overview - Métricas básicas de uso
GET /metrics/queues   - Estado de las colas de mensajes
```

## Configuración

Variables de entorno con prefijo `QUERY_`:

```env
# Redis
REDIS_URL=redis://localhost:6379/0
QUERY_ACTIONS_QUEUE_PREFIX=query

# Groq LLM
QUERY_GROQ_API_KEY=tu_api_key
QUERY_DEFAULT_LLM_MODEL=llama3-8b-8192
QUERY_LLM_TIMEOUT_SECONDS=30
QUERY_LLM_RETRY_ATTEMPTS=3

# Vector Store
QUERY_VECTOR_DB_URL=http://localhost:8006
QUERY_SIMILARITY_THRESHOLD=0.7
QUERY_DEFAULT_TOP_K=5

# Timeouts y retries
QUERY_HTTP_TIMEOUT_SECONDS=15
QUERY_MAX_RETRIES=3

# Caché y performance
QUERY_SEARCH_CACHE_TTL=300
QUERY_COLLECTION_CONFIG_CACHE_TTL=600
QUERY_ENABLE_QUERY_TRACKING=true
```

## Health Checks

- `GET /health` ➔ 200 OK si el servicio está funcionando correctamente
- `GET /ready` ➔ 200 OK si todas las dependencias (Redis, LLM API) están disponibles
- `GET /metrics/overview` ➔ Métricas básicas de uso del servicio
- `GET /metrics/queues` ➔ Estado de las colas de mensajes

## Inconsistencias y Próximos Pasos

### Inconsistencias Actuales

- **Persistencia Temporal**: Similar a otros servicios, utiliza Redis para almacenar métricas y datos de estado. Se planea migrar a PostgreSQL para persistencia permanente.

- **Sistema de Caché**: El caché de búsquedas está implementado parcialmente y requiere optimización para evitar consultas repetitivas al vector store.

- **Métricas Limitadas**: Los endpoints de métricas proporcionan información básica pero no hay un dashboard ni análisis detallado.

### Próximos Pasos

1. **Implementar Persistencia**: Migrar métricas y datos de estadísticas a PostgreSQL para almacenamiento permanente.

2. **Optimizar Caché**: Completar y optimizar el sistema de caché de búsquedas y resultados para mejorar rendimiento.

3. **Expandir Métricas**: Añadir métricas detalladas de uso, relevancia de respuestas y tiempos de procesamiento con dashboard.

4. **Integración de Feedback**: Implementar mecanismos para capturar feedback del usuario sobre la relevancia de las respuestas.

5. **Modelos Adicionales**: Añadir soporte para más proveedores de LLM además de Groq (OpenAI, Anthropic, etc.).

6. **Optimización de Prompting**: Mejorar los templates de prompts para diferentes casos de uso y tipos de documentos.
