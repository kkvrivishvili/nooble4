"""
Modelos del Agent Orchestrator Service.

Actualizado con nuevos modelos de sesión.
"""

# Modelos WebSocket (necesarios para la comunicación frontend)
from .websocket_model import (
    WebSocketMessage, WebSocketMessageType, ConnectionInfo, ConnectionStatus
)

# Domain Actions
from .actions_model import (
    WebSocketSendAction, WebSocketBroadcastAction,
    ChatProcessAction, ChatStatusAction, ChatCancelAction,
    ExecutionCallbackAction, ChatSendMessageAction
)

# Modelos de sesión (NUEVO)
from .session_models import (
    SessionState, ConnectionInfo as SessionConnectionInfo,
    ChatTask, ConversationContext
)

__all__ = [
    # Modelos WebSocket
    'WebSocketMessage', 'WebSocketMessageType', 'ConnectionInfo', 'ConnectionStatus',
    
    # Domain Actions
    'WebSocketSendAction', 'WebSocketBroadcastAction',
    'ChatProcessAction', 'ChatStatusAction', 'ChatCancelAction',
    'ExecutionCallbackAction', 'ChatSendMessageAction',
    
    # Modelos de sesión
    'SessionState', 'SessionConnectionInfo', 'ChatTask', 'ConversationContext'
]