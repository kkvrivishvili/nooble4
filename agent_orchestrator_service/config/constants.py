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

# Constantes de Rate Limiting
# (La configuración de rate limiting ahora se gestiona en OrchestratorSettings)

# Constantes para Endpoints
class EndpointPaths:
    HEALTH = "/health"
    WEBSOCKET = "/ws"
    SEND_MESSAGE = "/message"
    SESSION_STATUS = "/session/{session_id}/status"
