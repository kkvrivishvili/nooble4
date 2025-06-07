# Query Service

## Descripción General

El **Query Service** es responsable de resolver consultas en lenguaje natural mediante un flujo RAG (Retrieval-Augmented Generation). Utiliza un vector store para buscar documentos relevantes y un LLM (Groq) para generar respuestas basadas en contexto.

Funciona de manera asíncrona a través de Domain Actions en Redis y envía resultados mediante colas de callback.

## Características Principales

- **RAG Workflow**: Búsqueda de documentos + generación de texto.
- **Búsqueda Pura**: Acción de búsqueda sin generación de texto (`query.search`).
- **Dominio de Acciones**: Comunicación estructurada con `DomainAction` y colas Redis.
- **LLM con Retries**: GroqClient con tenacity para reintentos exponenciales.
- **Control de Calidad**: Umbrales de similitud y clasificación de relevancia.
- **Configuración Flexible**: Variables de entorno para umbrales, timeouts, modelos.
- **Manejo de Callbacks**: Codificación de `QueryCallbackAction` para entregar resultados o errores.
- **Health Checks**: Endpoints `/health` y `/ready`.

## Estructura de Archivos y Carpetas

```plaintext
query_service/
├ __init__.py
├ main.py
├ requirements.txt
├ README.md
├ config/
│  └ settings.py
├ handlers/
│  ├ __init__.py
│  ├ query_handler.py
│  └ embedding_callback_handler.py
├ clients/
│  ├ __init__.py
│  ├ groq_client.py
│  ├ vector_store_client.py
│  └ embedding_client.py
├ models/
│  └ actions.py
├ services/   # directorio para posibles APIs internas
└ workers/
   ├ __init__.py
   └ query_worker.py
```

## Arquitectura

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

## Componentes

- **FastAPI (main.py)**: Solo health-checks.
- **QueryWorker**: Consume colas `query.generate` y `query.search`, coordina handlers.
- **QueryHandler**: Implementa la lógica de:
  - `handle_query_generate` (flujo RAG). 
  - `handle_search_docs` (búsqueda pura de documentos).
- **EmbeddingCallbackHandler**: Espera e integra vectores de embeddings en RAG.
- **VectorStoreClient**: Busca vectores en el almacén (p. ej. Pinecone).
- **GroqClient**: Genera respuestas con Groq LLM, con retries.
- **DomainAction Models**: `QueryGenerateAction`, `SearchDocsAction`, `QueryCallbackAction`.
- **Configuración**: `config/settings.py` con variables de entorno y valores por defecto.

## Flujo de Trabajo

1. **Encolado**: Otro servicio envía una acción JSON (`query.generate` o `query.search`) a Redis.
2. **Procesamiento**: `QueryWorker` extrae y despacha al handler correspondiente.
3. **Embedding** (solo RAG): `EmbeddingCallbackHandler` proporciona `query_embedding` previo.
4. **Retrieval**: `VectorStoreClient.search_by_embedding()` devuelve documentos.
5. **Generación**: `GroqClient.generate()` crea la respuesta si aplica.
6. **Callback**: `QueryCallbackAction` se encola con resultado o error.
7. **Consumo**: Servicio llamante procesa el callback.

## Configuración

Variables de entorno principales:

```env
# Redis
REDIS_URL=redis://localhost:6379/0
QUERY_ACTIONS_QUEUE_PREFIX=query

# Groq LLM
GROQ_API_KEY=tu_api_key
DEFAULT_LLM_MODEL=llama3-8b-8192
LLM_TIMEOUT_SECONDS=30
LLM_RETRY_ATTEMPTS=3

# Vector Store
VECTOR_DB_URL=http://localhost:8006
SIMILARITY_THRESHOLD=0.7
DEFAULT_TOP_K=5

# Timeouts y retries
HTTP_TIMEOUT_SECONDS=15
MAX_RETRIES=3

# Logging
LOG_LEVEL=INFO
```

## Ejemplo de Uso

```python
import json, asyncio
import aioredis
from common.models.actions import DomainAction
from query_service.models.actions import QueryGenerateAction

async def send_query():
    redis = await aioredis.from_url("redis://localhost:6379/0")
    action = QueryGenerateAction(
        tenant_id="tenant1",
        task_id="task123",
        collection_id="docs",
        query="¿Qué es Nooble?",
        query_embedding=[...],  # opcional si acción RAG asíncrona
        similarity_top_k=3,
        relevance_threshold=0.6,
        include_sources=True,
        callback_queue="myapp.callbacks"
    )
    domain_action = DomainAction.parse_obj(action.dict())
    await redis.lpush(f"query.{action.tenant_id}.actions", domain_action.json())
    print("Action encolada")

asyncio.run(send_query())
```

## Health Checks

- `GET /health` ➔ 200 OK
- `GET /ready`  ➔ 200 OK

---
