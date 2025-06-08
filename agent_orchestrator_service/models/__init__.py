"""
Modelos del Agent Orchestrator Service.

Define los modelos de Domain Actions y WebSockets para orquestación.
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

__all__ = [
    # Modelos WebSocket
    'WebSocketMessage', 'WebSocketMessageType', 'ConnectionInfo', 'ConnectionStatus',
    
    # Domain Actions
    'WebSocketSendAction', 'WebSocketBroadcastAction',
    'ChatProcessAction', 'ChatStatusAction', 'ChatCancelAction',
    'ExecutionCallbackAction', 'ChatSendMessageAction'
]