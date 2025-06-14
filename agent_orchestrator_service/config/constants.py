"""
Constantes para el Agent Orchestrator Service.

Este módulo define constantes y valores estáticos utilizados por el servicio
de orquestación de agentes. Las configuraciones variables se gestionan en settings.py.
"""

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

# Constantes de Rate Limiting (si son fijas y no varían por entorno)
# Si estos valores necesitan ser configurables, deben moverse a settings.py
RATE_LIMITING_TIERS = {
    "free": 50,      # 50 requests por sesión por hora
    "advance": 100,  # 100 requests por sesión por hora
    "professional": 300,  # 300 requests por sesión por hora
    "enterprise": 500  # 500 requests por sesión por hora
}

# Constantes para Endpoints
class EndpointPaths:
    HEALTH = "/health"
    WEBSOCKET = "/ws"
    SEND_MESSAGE = "/message"
    SESSION_STATUS = "/session/{session_id}/status"
