📚 DOCUMENTACIÓN DE IMPLEMENTACIÓN
Configuración Requerida
Variables de Entorno
bash# Redis (requerido)
REDIS_URL=redis://localhost:6379/0

# Execution específico
EXECUTION_DOMAIN_NAME=execution
EXECUTION_CALLBACK_QUEUE_PREFIX=orchestrator

# Servicios externos
EXECUTION_EMBEDDING_SERVICE_URL=http://localhost:8001
EXECUTION_QUERY_SERVICE_URL=http://localhost:8002
EXECUTION_CONVERSATION_SERVICE_URL=http://localhost:8004
EXECUTION_AGENT_MANAGEMENT_SERVICE_URL=http://localhost:8003

# LangChain
EXECUTION_DEFAULT_AGENT_TYPE=conversational
EXECUTION_MAX_ITERATIONS=5
EXECUTION_MAX_EXECUTION_TIME=120

# Cache y performance
EXECUTION_AGENT_CONFIG_CACHE_TTL=300
EXECUTION_ENABLE_EXECUTION_TRACKING=true

# Worker
EXECUTION_WORKER_SLEEP_SECONDS=1.0

# Logging
EXECUTION_LOG_LEVEL=INFO
Especificaciones de Colas
Colas que Consume
execution:{context_id}:{tier}               # Tareas de ejecución de agentes
embedding.{tenant_id}.callbacks             # Callbacks de embeddings
query.{tenant_id}.callbacks                 # Callbacks de queries
Colas que Produce
orchestrator:{tenant_id}:callbacks          # Callbacks hacia Orchestrator
embedding.{tenant_id}.actions               # Solicitudes de embeddings
query.{tenant_id}.actions                   # Solicitudes de queries RAG
Formato de Entrada (desde Orchestrator)
json{
  "action_type": "execution.agent_run",
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
    "agents": ["agent-456"],
    "collections": ["collection-789"],
    "metadata": {...}
  },
  "callback_queue": "orchestrator:tenant-123:callbacks",
  "message": "¿Qué es Nooble?",
  "message_type": "text",
  "user_info": {...},
  "max_iterations": 5,
  "timeout": 120
}
Formato de Salida (hacia Orchestrator)
json{
  "action_type": "execution.callback",
  "task_id": "task-xyz789",
  "tenant_id": "tenant-123",
  "tenant_tier": "professional",
  "session_id": "sess-abc123",
  "status": "completed",
  "result": {
    "response": "Nooble es una plataforma...",
    "sources": [...],
    "tool_calls": [...],
    "agent_info": {...},
    "status": "completed"
  },
  "execution_time": 4.567,
  "tokens_used": {"total": 245, "input": 123, "output": 122}
}
Flujo de Datos
1. Ejecución de Agente
Orchestrator → execution:{context_id}:{tier}
↓
ExecutionWorker procesa acción
↓
AgentExecutionHandler resuelve contexto
↓
Obtener config de agente (cache/API)
↓
Validar permisos y límites por tier
↓
Obtener historial de conversación
↓
LangChainIntegrator ejecuta agente
↓
Guardar mensajes en conversación
↓
ExecutionCallbackHandler envía resultado
↓
orchestrator:{tenant_id}:callbacks
2. Agente RAG
AgentExecutor detecta tipo RAG
↓
Solicitar embedding → embedding.{tenant_id}.actions
↓
Esperar callback de embedding
↓
Solicitar query RAG → query.{tenant_id}.actions
↓
Esperar callback de query
↓
Procesar respuesta final
↓
Enviar callback completo
Límites por Tier
Free

Max iteraciones: 3
Max herramientas: 2
Timeout: 30s
Cache agente: 5 min

Advance

Max iteraciones: 5
Max herramientas: 5
Timeout: 60s
Cache agente: 5 min

Professional

Max iteraciones: 10
Max herramientas: 10
Timeout: 120s
Cache agente: 5 min

Enterprise

Max iteraciones: 20
Max herramientas: Sin límite
Timeout: 300s
Cache agente: 5 min

API Endpoints
Health y Métricas
GET /health                    # Health check general
GET /ready                     # Readiness check
GET /metrics/overview          # Métricas generales
GET /metrics/queues            # Métricas de colas
Integración con Servicios
Agent Management Service

Obtener configuración de agentes
Cache de configuraciones (5 min TTL)
Validación de permisos

Conversation Service

Obtener historial de conversación
Guardar mensajes user/assistant
Incluir metadatos de ejecución

Embedding Service

Solicitar embeddings para agentes RAG
Callbacks asíncronos
Manejo de timeouts

Query Service

Solicitar consultas RAG
Búsqueda en collections
Callbacks con resultados estructurados

Troubleshooting
Problemas Comunes

"Contexto de ejecución inválido": Verificar formato de ExecutionContext en DomainAction
"Agente no encontrado": Verificar que Agent Management Service esté disponible
"Timeout en ejecución": Verificar límites por tier y configuración de agente
"Error en callback": Verificar que Orchestrator esté consumiendo callbacks

Debugging
bash# Ver estadísticas de ejecución
curl http://localhost:8005/metrics/overview

# Ver estado de colas
curl http://localhost:8005/metrics/queues

# Ver salud del servicio
curl http://localhost:8005/health
Próximos Pasos

Implementar LangChain real en LangChainIntegrator
Configurar herramientas específicas por tipo de agente
Implementar workflows multi-agente
Optimizar cache de configuraciones
Testing con múltiples agentes y tiers simultáneamente