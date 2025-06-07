📚 DOCUMENTACIÓN DE IMPLEMENTACIÓN
Configuración Requerida
Variables de Entorno
bash# Redis (requerido)
REDIS_URL=redis://localhost:6379/0

# Query específico
QUERY_DOMAIN_NAME=query
QUERY_CALLBACK_QUEUE_PREFIX=execution

# Groq LLM
QUERY_GROQ_API_KEY=tu_api_key
QUERY_DEFAULT_LLM_MODEL=llama3-8b-8192
QUERY_LLM_TIMEOUT_SECONDS=30

# Vector Store
QUERY_VECTOR_DB_URL=http://localhost:8006
QUERY_SIMILARITY_THRESHOLD=0.7
QUERY_DEFAULT_TOP_K=5

# Cache y performance
QUERY_SEARCH_CACHE_TTL=300
QUERY_COLLECTION_CONFIG_CACHE_TTL=600
QUERY_ENABLE_QUERY_TRACKING=true

# Worker
QUERY_WORKER_SLEEP_SECONDS=1.0

# Logging
QUERY_LOG_LEVEL=INFO
Especificaciones de Colas
Colas que Consume
query:{context_id}:{tier}                   # Consultas RAG y búsquedas
embedding.{tenant_id}.callbacks             # Callbacks de embeddings
Colas que Produce
execution:{tenant_id}:callbacks              # Callbacks hacia Execution Service
embedding:{context_id}:{tier}               # Solicitudes de embeddings
Formato de Entrada (desde Execution Service)
json{
  "action_type": "query.generate",
  "task_id": "task-xyz789",
  "tenant_id": "tenant-123",
  "tenant_tier": "professional",
  "session_id": "sess-abc123",
  "execution_context": {
    "context_id": "agent-456",
    "context_type": "agent",
    "tenant_id": "tenant-123",
    "tenant_tier": "professional",
    "primary_agent_id": "agent-456",
    "collections": ["collection-789"],
    "metadata": {...}
  },
  "callback_queue": "execution:tenant-123:callbacks",
  "query": "¿Qué es Nooble?",
  "query_embedding": [0.1, 0.2, ...],
  "collection_id": "collection-789",
  "similarity_top_k": 5,
  "relevance_threshold": 0.75,
  "include_sources": true,
  "max_sources": 3
}
Formato de Salida (hacia Execution Service)
json{
  "action_type": "query.callback",
  "task_id": "task-xyz789",
  "tenant_id": "tenant-123",
  "session_id": "sess-abc123",
  "status": "completed",
  "result": {
    "response": "Nooble es una plataforma...",
    "sources": [...],
    "metadata": {
      "query": "¿Qué es Nooble?",
      "collection_id": "collection-789",
      "found_documents": 5,
      "processing_time": 2.345,
      "model_used": "llama3-8b-8192"
    }
  },
  "processing_time": 2.345,
  "tokens_used": 189
}
Límites por Tier
Free

Max consultas/hora: 50
Max resultados: 5
Max longitud query: 500 chars
Cache habilitado: Sí

Advance

Max consultas/hora: 200
Max resultados: 10
Max longitud query: 1000 chars
Cache habilitado: Sí

Professional

Max consultas/hora: 1000
Max resultados: 20
Max longitud query: 2000 chars
Cache habilitado: Sí

Enterprise

Max consultas/hora: Sin límite
Max resultados: 50
Max longitud query: 5000 chars
Cache habilitado: Sí

Flujo de Datos
1. Consulta RAG Completa
Execution → query:{context_id}:{tier}
↓
QueryWorker procesa por prioridad
↓
QueryHandler resuelve contexto
↓
Obtener config colección (cache/DB)
↓
Validar permisos y límites por tier
↓
RAGProcessor busca documentos
↓
VectorSearchService ejecuta búsqueda
↓
GroqClient genera respuesta con contexto
↓
QueryCallbackHandler envía resultado
↓
execution:{tenant_id}:callbacks
2. Búsqueda de Documentos
Cliente → query:{context_id}:{tier}
↓
QueryWorker procesa SearchDocsAction
↓
VectorSearchService busca documentos
↓
Filtrar por umbral y límites
↓
QueryCallbackHandler envía resultados
↓
{callback_queue}
API Endpoints
Health y Métricas
GET /health                    # Health check general
GET /ready                     # Readiness check
GET /metrics/overview          # Métricas generales
GET /metrics/queues            # Métricas de colas
Cache y Performance
Cache de Búsquedas

TTL: 5 minutos
Key: search_cache:{collection_id}:{embedding_hash}:{top_k}:{threshold}
Habilitado para todos los tiers

Cache de Configuraciones

TTL: 10 minutos
Key: collection_config:{tenant_id}:{collection_id}
Invalidación automática en updates

Métricas por Tenant
query_metrics:{tenant_id}:{date}         # Métricas diarias
search_metrics:{tenant_id}:{date}        # Métricas de búsqueda
query_processing_times:{tenant_id}       # Tiempos de procesamiento
search_times:{tenant_id}                 # Tiempos de búsqueda
**Integración con Servicios