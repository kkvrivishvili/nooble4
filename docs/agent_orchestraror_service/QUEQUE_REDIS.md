📚 DOCUMENTACIÓN DE IMPLEMENTACIÓN
Configuración Requerida
Variables de Entorno
bash# Redis (requerido)
REDIS_URL=redis://localhost:6379/0

# Orchestrator específico
ORCHESTRATOR_DOMAIN_NAME=orchestrator
ORCHESTRATOR_CALLBACK_QUEUE_PREFIX=orchestrator

# WebSocket
ORCHESTRATOR_MAX_WEBSOCKET_CONNECTIONS=1000
ORCHESTRATOR_WEBSOCKET_PING_INTERVAL=30
ORCHESTRATOR_WEBSOCKET_PING_TIMEOUT=10

# Validación
ORCHESTRATOR_ENABLE_ACCESS_VALIDATION=true
ORCHESTRATOR_VALIDATION_CACHE_TTL=300

# Rate limiting
ORCHESTRATOR_MAX_REQUESTS_PER_SESSION=100

# Logging
ORCHESTRATOR_LOG_LEVEL=INFO
Headers Requeridos para API
Headers Obligatorios
httpX-Tenant-ID: tenant-456          # ID del tenant
X-Agent-ID: agent-123            # ID del agente a usar
X-Tenant-Tier: professional     # Tier (free, advance, professional, enterprise)
X-Session-ID: sess-abc123        # ID de sesión para WebSocket
Headers Opcionales
httpX-Context-Type: agent            # Tipo de contexto (default: agent)
X-User-ID: user-789              # ID del usuario
X-Conversation-ID: conv-def456   # ID de conversación
X-Collection-ID: collection-789  # Collection específica
X-Request-Source: web            # Origen del request
X-Client-Version: 1.2.3          # Versión del cliente
Especificaciones de Colas
Colas que Consume
orchestrator:{tenant_id}:callbacks     # Callbacks desde Agent Execution
Colas que Produce
execution:{context_id}:{tier}           # Tareas para Agent Execution Service
Formato de Callbacks
json{
  "action_type": "execution.callback",
  "task_id": "task-xyz789",
  "status": "completed",
  "result": {
    "response": "Respuesta del agente",
    "sources": [...],
    "agent_info": {...}
  },
  "execution_time": 3.456,
  "tokens_used": {"total": 209}
}
API Endpoints
Chat
POST /api/chat/send              # Enviar mensaje
GET /api/chat/stats              # Estadísticas de chat
GET /api/chat/health             # Health check chat
WebSocket
WS /ws/{session_id}              # Conexión WebSocket
GET /ws/stats                    # Estadísticas WebSocket
GET /ws/health                   # Health check WebSocket
Métricas
GET /metrics/overview            # Métricas generales
GET /metrics/queues              # Métricas de colas
GET /health                      # Health check general
Flujo de Datos
1. Request de Chat
Frontend → POST /api/chat/send (con headers)
↓
Context Handler valida headers
↓ 
Crear ExecutionContext
↓
Encolar en execution:{context_id}:{tier}
↓
Responder task_id al frontend
2. WebSocket Connection
Frontend → WS /ws/{session_id}?tenant_id=...&tier=...
↓
Validar parámetros
↓
Registrar conexión por tenant/tier
↓
Enviar ACK
3. Callback Processing
Agent Execution → orchestrator:{tenant_id}:callbacks
↓
Worker procesa callback
↓
Callback Handler extrae resultado
↓
WebSocket Manager envía a sesión
↓
Frontend recibe respuesta
Validación y Seguridad
Validación de Acceso

Cache en Redis por 5 minutos
Verificación tenant→agent en base de datos
Rate limiting por tier

WebSocket Security

Validación de parámetros requeridos
Rate limiting por conexión
Cleanup automático de conexiones obsoletas

Troubleshooting
Problemas Comunes

"Missing required headers": Verificar que todos los headers obligatorios estén presentes
"Invalid tier": Verificar que tier sea uno de: free, advance, professional, enterprise
"WebSocket connection failed": Verificar parámetros de query en URL WebSocket
"Callback not received": Verificar que Agent Execution Service esté ejecutándose

Debugging
bash# Ver estadísticas de colas
curl http://localhost:8008/metrics/queues

# Ver conexiones WebSocket
curl http://localhost:8008/ws/stats

# Ver métricas generales
curl http://localhost:8008/metrics/overview
Próximos Pasos

Implementar validación real en ContextHandler._check_database_access()
Configurar autenticación JWT para WebSockets
Implementar suscripciones a eventos específicos en WebSocket
Agregar métricas Prometheus para observabilidad
Testing con múltiples tenants y tiers simultáneamente