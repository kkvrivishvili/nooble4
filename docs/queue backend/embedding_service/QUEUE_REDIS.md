📚 DOCUMENTACIÓN DE IMPLEMENTACIÓN
Configuración Requerida
Variables de Entorno
bash# Redis (requerido)
REDIS_URL=redis://localhost:6379/0

# Embedding específico
EMBEDDING_DOMAIN_NAME=embedding
EMBEDDING_CALLBACK_QUEUE_PREFIX=execution

# OpenAI
EMBEDDING_OPENAI_API_KEY=tu_api_key
EMBEDDING_DEFAULT_EMBEDDING_MODEL=text-embedding-3-small
EMBEDDING_OPENAI_TIMEOUT_SECONDS=30

# Cache y performance
EMBEDDING_EMBEDDING_CACHE_TTL=3600
EMBEDDING_ENABLE_EMBEDDING_TRACKING=true

# Worker
EMBEDDING_WORKER_SLEEP_SECONDS=1.0

# Logging
EMBEDDING_LOG_LEVEL=INFO
Especificaciones de Colas
Colas que Consume
embedding:{context_id}:{tier}               # Generación de embeddings
Colas que Produce
execution:{tenant_id}:callbacks              # Callbacks hacia Execution Service
query:{tenant_id}:callbacks                  # Callbacks hacia Query Service
Formato de Entrada
json{
  "action_type": "embedding.generate",
  "task_id": "task-xyz789",
  "tenant_id": "tenant-123",
  "tenant_tier": "professional",
  "session_id": "sess-abc123",
  "execution_context": {
    "context_id": "query-456",
    "context_type": "query",
    "tenant_id": "tenant-123",
    "tenant_tier": "professional",
    "primary_agent_id": "query-service",
    "agents": ["query-service"],
    "collections": [],
    "metadata": {...}
  },
  "callback_queue": "query:tenant-123:callbacks",
  "texts": ["¿Qué es Nooble?", "Otra consulta"],
  "model": "text-embedding-3-small"
}
Formato de Salida
json{
  "action_type": "embedding.callback",
  "task_id": "task-xyz789",
  "tenant_id": "tenant-123",
  "session_id": "sess-abc123",
  "status": "completed",
  "embeddings": [[0.1, 0.2, ...], [0.3, 0.4, ...]],
  "model": "text-embedding-3-small",
  "dimensions": 1536,
  "total_tokens": 15,
  "processing_time": 1.234
}
Límites por Tier
Free

Max textos/request: 10
Max requests/hora: 100
Max longitud texto: 1000 chars
Cache habilitado: Sí

Advance

Max textos/request: 50
Max requests/hora: 500
Max longitud texto: 2000 chars
Cache habilitado: Sí

Professional

Max textos/request: 100
Max requests/hora: 2000
Max longitud texto: 4000 chars
Cache habilitado: Sí

Enterprise

Max textos/request: 500
Max requests/hora: Sin límite
Max longitud texto: 8000 chars
Cache habilitado: Sí

API Endpoints
Health y Métricas
GET /health                    # Health check general
GET /ready                     # Readiness check
GET /metrics/overview          # Métricas generales
GET /metrics/queues            # Métricas de colas
Cache y Performance
Cache de Embeddings

TTL: 1 hora
Key: embeddings_cache:{tenant_id}:{model}:{text_hash}:{count}
Habilitado para todos los tiers

Métricas por Tenant
embedding_metrics:{tenant_id}:{date}        # Métricas diarias
embedding_processing_times:{tenant_id}      # Tiempos de procesamiento
embedding_rate_limit:{tenant_id}:hour:{ts}  # Rate limiting
Integración con Servicios
Query Service

Recibe requests para embeddings de consultas
Envía callbacks con vectores generados
Tracking de tokens y tiempo

Agent Execution Service

Recibe requests para embeddings de agentes RAG
Callbacks síncronos con resultados
Optimizado para baja latencia