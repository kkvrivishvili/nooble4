"""
Constantes para el Agent Orchestrator Service.

Este módulo define constantes y valores estáticos utilizados por el servicio
de orquestación de agentes.
"""

# Constantes Generales del Servicio
SERVICE_NAME = "agent-orchestrator-service"
DEFAULT_DOMAIN = "orchestrator"
VERSION = "1.0.0"

# Constantes de WebSocket
WEBSOCKET_PING_INTERVAL_SECONDS = 30
WEBSOCKET_PING_TIMEOUT_SECONDS = 10
MAX_WEBSOCKET_CONNECTIONS = 1000

# Tipos de Mensajes WebSocket
class WebSocketMessageTypes:
    ERROR = "error"
    INFO = "info"
    RESPONSE = "response" 
    CHUNK = "chunk"
    TOOL_CALL = "tool_call"
    THINKING = "thinking"
    DONE = "done"
    START = "start"

# Constantes de Colas y Processing
CALLBACK_QUEUE_PREFIX = "orchestrator"
DEFAULT_WORKER_SLEEP_SECONDS = 1.0

# Constantes de Rate Limiting
MAX_REQUESTS_PER_SESSION_DEFAULT = 100
RATE_LIMITING_TIERS = {
    "free": 50,      # 50 requests por sesión por hora
    "advance": 100,  # 100 requests por sesión por hora
    "professional": 300,  # 300 requests por sesión por hora
    "enterprise": 500  # 500 requests por sesión por hora
}

# Constantes para Headers Requeridos
REQUIRED_HEADERS = [
    "X-Tenant-ID",
    "X-Agent-ID",
    "X-Tenant-Tier",
    "X-Session-ID"
]

# Constantes para Validación y Cache
VALIDATION_CACHE_TTL_SECONDS = 300  # 5 minutos

# Constantes para Endpoints
class EndpointPaths:
    HEALTH = "/health"
    WEBSOCKET = "/ws"
    SEND_MESSAGE = "/message"
    SESSION_STATUS = "/session/{session_id}/status"
