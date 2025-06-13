"""
Gestor de conexiones WebSocket.
"""

import json
import logging
import asyncio
from typing import Dict, Any, Optional, List
from datetime import datetime
from uuid import uuid4
from fastapi import WebSocket

from agent_orchestrator_service.models.websocket_model import (
    WebSocketMessage, WebSocketMessageType,
    ConnectionInfo, ConnectionStatus
)
from agent_orchestrator_service.config.settings import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

class WebSocketManager:
    """
    Gestor de conexiones WebSocket.
    """

    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.connections_info: Dict[str, ConnectionInfo] = {}
        self.session_connections: Dict[str, str] = {}
        self.tenant_connections: Dict[str, List[str]] = {}
        self.connection_rates: Dict[str, List[datetime]] = {}

    async def connect(
        self,
        websocket: WebSocket,
        session_id: str,
        tenant_id: str,
        tenant_tier: str,
        user_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        user_agent: Optional[str] = None,
        ip_address: Optional[str] = None
    ) -> str:
        """Registra una nueva conexión WebSocket."""
        connection_id = str(uuid4())

        if len(self.active_connections) >= settings.max_websocket_connections:
            logger.warning("Límite de conexiones WebSocket alcanzado")
            raise Exception("Límite de conexiones alcanzado")

        if session_id in self.session_connections:
            old_connection_id = self.session_connections[session_id]
            logger.info(f"Reemplazando conexión existente para sesión {session_id}")
            # Asumimos que el tenant_id es el mismo para la misma sesión
            await self.disconnect(old_connection_id, tenant_id, session_id)

        self.active_connections[connection_id] = websocket

        connection_info = ConnectionInfo(
            connection_id=connection_id,
            tenant_id=tenant_id,
            tenant_tier=tenant_tier,
            session_id=session_id,
            user_id=user_id,
            status=ConnectionStatus.CONNECTED,
            user_agent=user_agent,
            ip_address=ip_address,
            metadata={
                "connected_at": datetime.utcnow().isoformat(),
                "agent_id": agent_id
            }
        )

        self.connections_info[connection_id] = connection_info
        self.session_connections[session_id] = connection_id

        if tenant_id not in self.tenant_connections:
            self.tenant_connections[tenant_id] = []
        self.tenant_connections[tenant_id].append(connection_id)

        self.connection_rates[connection_id] = []

        logger.info(f"Nueva conexión WebSocket: {connection_id} (session: {session_id}, tenant: {tenant_id})")
        return connection_id

    async def disconnect(self, connection_id: str, tenant_id: str, session_id: str):
        """Desconecta y limpia una conexión WebSocket."""
        if connection_id not in self.active_connections:
            return

        if session_id in self.session_connections:
            del self.session_connections[session_id]

        if tenant_id in self.tenant_connections:
            if connection_id in self.tenant_connections[tenant_id]:
                self.tenant_connections[tenant_id].remove(connection_id)
            if not self.tenant_connections[tenant_id]:
                del self.tenant_connections[tenant_id]

        if connection_id in self.active_connections:
            del self.active_connections[connection_id]
        if connection_id in self.connections_info:
            del self.connections_info[connection_id]
        if connection_id in self.connection_rates:
            del self.connection_rates[connection_id]

        logger.info(f"Conexión WebSocket desconectada: {connection_id}")

    async def send_message(
        self,
        connection_id: str,
        message: WebSocketMessage
    ) -> bool:
        """Envía un mensaje a una conexión específica."""
        websocket = self.active_connections.get(connection_id)
        if not websocket:
            logger.warning(f"Conexión no encontrada: {connection_id}")
            return False

        try:
            message_data = message.model_dump()
            if message_data.get("timestamp"):
                message_data["timestamp"] = message_data["timestamp"].isoformat()
            
            await websocket.send_text(json.dumps(message_data))
            await self._track_message_rate(connection_id)
            return True
        except Exception as e:
            logger.error(f"Error enviando mensaje WebSocket a {connection_id}: {str(e)}")
            connection_info = self.connections_info.get(connection_id)
            if connection_info:
                await self.disconnect(connection_id, connection_info.tenant_id, connection_info.session_id)
            return False

    async def send_to_session(
        self,
        session_id: str,
        message: WebSocketMessage
    ) -> bool:
        """Envía un mensaje a una sesión específica."""
        connection_id = self.session_connections.get(session_id)
        if not connection_id:
            logger.warning(f"No hay conexión para sesión: {session_id}")
            return False
        return await self.send_message(connection_id, message)

    async def send_to_tenant(
        self,
        tenant_id: str,
        message: WebSocketMessage,
        exclude_connection: Optional[str] = None
    ) -> int:
        """Envía un mensaje a todas las conexiones de un tenant."""
        connections_to_send = self.tenant_connections.get(tenant_id, [])
        if not connections_to_send:
            logger.warning(f"No hay conexiones para tenant: {tenant_id}")
            return 0

        tasks = [
            self.send_message(conn_id, message)
            for conn_id in connections_to_send
            if conn_id != exclude_connection
        ]
        results = await asyncio.gather(*tasks)
        return sum(1 for r in results if r)

    async def send_error(
        self,
        connection_id: str,
        error: str,
        task_id: Optional[str] = None,
        error_code: Optional[str] = None
    ):
        """Envía un mensaje de error a una conexión."""
        error_message = WebSocketMessage(
            type=WebSocketMessageType.ERROR,
            data={
                "error": error,
                "error_code": error_code or "UNKNOWN_ERROR"
            },
            task_id=task_id
        )
        await self.send_message(connection_id, error_message)

    async def handle_client_message(
        self,
        connection_id: str,
        message_data: Dict[str, Any]
    ):
        """Maneja mensajes recibidos del cliente."""
        try:
            message_type = message_data.get("type")
            if message_type == "ping":
                pong_message = WebSocketMessage(
                    type=WebSocketMessageType.PONG,
                    data={"message": "pong", "server_time": datetime.utcnow().isoformat()}
                )
                await self.send_message(connection_id, pong_message)
                if connection_id in self.connections_info:
                    self.connections_info[connection_id].last_ping = datetime.utcnow()
            elif message_type == "subscribe":
                await self._handle_subscription(connection_id, message_data)
            else:
                logger.info(f"Mensaje del cliente no manejado: {message_type}")
        except Exception as e:
            logger.error(f"Error manejando mensaje del cliente {connection_id}: {str(e)}")
            await self.send_error(connection_id, f"Error procesando mensaje: {str(e)}")

    async def _handle_subscription(
        self,
        connection_id: str,
        message_data: Dict[str, Any]
    ):
        """Maneja suscripciones a eventos específicos."""
        logger.info(f"Subscription request: {message_data} from {connection_id}")

    async def _track_message_rate(self, connection_id: str):
        """Rastrea rate de mensajes por conexión."""
        now = datetime.utcnow()
        self.connection_rates.setdefault(connection_id, [])
        cutoff = now.timestamp() - 60
        self.connection_rates[connection_id] = [
            msg_time for msg_time in self.connection_rates[connection_id]
            if msg_time.timestamp() > cutoff
        ]
        self.connection_rates[connection_id].append(now)

    async def get_connection_stats(self) -> Dict[str, Any]:
        """Obtiene estadísticas generales de conexiones."""
        return {
            "total_connections": len(self.active_connections),
            "total_sessions": len(self.session_connections),
            "total_tenants": len(self.tenant_connections),
            "connections_by_tenant": {
                tenant_id: len(connections)
                for tenant_id, connections in self.tenant_connections.items()
            }
        }

    async def get_tenant_stats(self, tenant_id: str) -> Dict[str, Any]:
        """Obtiene estadísticas específicas de un tenant."""
        tenant_connections = self.tenant_connections.get(tenant_id, [])
        connections_detail = []
        for conn_id in tenant_connections:
            if conn_id in self.connections_info:
                info = self.connections_info[conn_id]
                connections_detail.append({
                    "connection_id": conn_id,
                    "session_id": info.session_id,
                    "user_id": info.user_id,
                    "agent_id": info.metadata.get("agent_id"),
                    "connected_at": info.connected_at.isoformat(),
                    "last_ping": info.last_ping.isoformat() if info.last_ping else None
                })
        return {
            "tenant_id": tenant_id,
            "total_connections": len(tenant_connections),
            "connections": connections_detail
        }

    async def cleanup_stale_connections(self):
        """Limpia conexiones obsoletas."""
        current_time = datetime.utcnow()
        stale_connections = []
        for conn_id, conn_info in self.connections_info.items():
            # Considerar obsoleto si no hubo ping en un tiempo
            ping_timeout = settings.websocket_ping_timeout * 3
            if conn_info.last_ping and (current_time - conn_info.last_ping).total_seconds() > ping_timeout:
                stale_connections.append((conn_id, conn_info))
            # Considerar obsoleto si no hay ping y la conexión es antigua
            elif not conn_info.last_ping and (current_time - conn_info.connected_at).total_seconds() > ping_timeout:
                 stale_connections.append((conn_id, conn_info))

        for conn_id, conn_info in stale_connections:
            logger.info(f"Limpiando conexión obsoleta: {conn_id}")
            await self.disconnect(conn_id, conn_info.tenant_id, conn_info.session_id)


_websocket_manager_instance = None

def get_websocket_manager() -> WebSocketManager:
    """Obtiene la instancia singleton del WebSocketManager."""
    global _websocket_manager_instance
    if _websocket_manager_instance is None:
        _websocket_manager_instance = WebSocketManager()
    return _websocket_manager_instance