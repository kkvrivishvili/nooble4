"""
Gestor de conexiones WebSocket.

MODIFICADO: Integración con sistema de colas por tier y contexto de tenant.
"""

import json
import logging
import asyncio
from typing import Dict, Any, Optional, List, Set
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
    Gestor de conexiones WebSocket con soporte para tiers.
    
    MODIFICADO: Integra información de tier y tenant para mejor gestión.
    """
    
    def __init__(self):
        # Conexiones activas: connection_id -> WebSocket
        self.active_connections: Dict[str, WebSocket] = {}
        
        # Información de conexiones: connection_id -> ConnectionInfo
        self.connections_info: Dict[str, ConnectionInfo] = {}
        
        # Mapeo por sesión: session_id -> connection_id
        self.session_connections: Dict[str, str] = {}
        
        # NUEVO: Mapeo por tenant: tenant_id -> List[connection_id]
        self.tenant_connections: Dict[str, List[str]] = {}
        
        # NUEVO: Mapeo por tier: tier -> List[connection_id]
        self.tier_connections: Dict[str, List[str]] = {}
        
        # NUEVO: Rate limiting por conexión
        self.connection_rates: Dict[str, List[datetime]] = {}
    
    async def connect(
        self,
        websocket: WebSocket,
        session_id: str,
        tenant_id: str,
        tenant_tier: str,  # NUEVO
        user_id: Optional[str] = None,
        agent_id: Optional[str] = None,  # NUEVO
        user_agent: Optional[str] = None,
        ip_address: Optional[str] = None
    ) -> str:
        """
        Registra una nueva conexión WebSocket.
        
        MODIFICADO: Incluye tenant_tier y agent_id para mejor gestión.
        """
        connection_id = str(uuid4())
        
        # Verificar límite de conexiones
        if len(self.active_connections) >= settings.max_websocket_connections:
            logger.warning("Límite de conexiones WebSocket alcanzado")
            raise Exception("Límite de conexiones alcanzado")
        
        # Verificar si ya hay conexión para esta sesión
        if session_id in self.session_connections:
            old_connection_id = self.session_connections[session_id]
            logger.info(f"Reemplazando conexión existente para sesión {session_id}")
            await self.disconnect(old_connection_id, tenant_id, session_id)
        
        # Registrar conexión
        self.active_connections[connection_id] = websocket
        
        # Crear información de conexión
        connection_info = ConnectionInfo(
            connection_id=connection_id,
            tenant_id=tenant_id,
            tenant_tier=tenant_tier,  # NUEVO
            session_id=session_id,
            user_id=user_id,
            agent_id=agent_id,  # NUEVO
            status=ConnectionStatus.CONNECTED,
            user_agent=user_agent,
            ip_address=ip_address,
            metadata={
                "connected_at": datetime.utcnow().isoformat(),
                "tier": tenant_tier
            }
        )
        
        self.connections_info[connection_id] = connection_info
        
        # Mapeo por sesión
        self.session_connections[session_id] = connection_id
        
        # NUEVO: Mapeo por tenant
        if tenant_id not in self.tenant_connections:
            self.tenant_connections[tenant_id] = []
        self.tenant_connections[tenant_id].append(connection_id)
        
        # NUEVO: Mapeo por tier
        if tenant_tier not in self.tier_connections:
            self.tier_connections[tenant_tier] = []
        self.tier_connections[tenant_tier].append(connection_id)
        
        # Inicializar rate limiting
        self.connection_rates[connection_id] = []
        
        logger.info(f"Nueva conexión WebSocket: {connection_id} (session: {session_id}, tier: {tenant_tier})")
        return connection_id
    
    async def disconnect(self, connection_id: str, tenant_id: str, session_id: str):
        """
        Desconecta y limpia una conexión WebSocket.
        
        MODIFICADO: Limpia mapeos de tier.
        """
        if connection_id not in self.active_connections:
            return
        
        # Obtener información de la conexión
        connection_info = self.connections_info.get(connection_id)
        
        # Limpiar mapeos
        if connection_info:
            # Limpiar mapeo por sesión
            if session_id in self.session_connections:
                del self.session_connections[session_id]
            
            # Limpiar mapeo por tenant
            if tenant_id in self.tenant_connections:
                if connection_id in self.tenant_connections[tenant_id]:
                    self.tenant_connections[tenant_id].remove(connection_id)
                if not self.tenant_connections[tenant_id]:
                    del self.tenant_connections[tenant_id]
            
            # NUEVO: Limpiar mapeo por tier
            if connection_info.tenant_tier in self.tier_connections:
                if connection_id in self.tier_connections[connection_info.tenant_tier]:
                    self.tier_connections[connection_info.tenant_tier].remove(connection_id)
                if not self.tier_connections[connection_info.tenant_tier]:
                    del self.tier_connections[connection_info.tenant_tier]
        
        # Eliminar conexión
        del self.active_connections[connection_id]
        if connection_id in self.connections_info:
            del self.connections_info[connection_id]
        
        # Limpiar rate limiting
        if connection_id in self.connection_rates:
            del self.connection_rates[connection_id]
        
        logger.info(f"Conexión WebSocket desconectada: {connection_id}")
    
    async def send_message(
        self,
        connection_id: str,
        message: WebSocketMessage
    ) -> bool:
        """Envía un mensaje a una conexión específica."""
        if connection_id not in self.active_connections:
            logger.warning(f"Conexión no encontrada: {connection_id}")
            return False
        
        websocket = self.active_connections[connection_id]
        
        try:
            message_data = message.model_dump()
            # Convertir datetime a string para JSON
            if message_data.get("timestamp"):
                message_data["timestamp"] = message_data["timestamp"].isoformat()
            
            await websocket.send_text(json.dumps(message_data))
            
            # NUEVO: Rate limiting tracking
            await self._track_message_rate(connection_id)
            
            return True
            
        except Exception as e:
            logger.error(f"Error enviando mensaje WebSocket: {str(e)}")
            # Desconectar conexión problemática
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
    
    # NUEVO: Métodos para envío por tier
    async def broadcast_to_tier(
        self,
        tier: str,
        message: WebSocketMessage,
        exclude_connection: Optional[str] = None
    ) -> int:
        """Envía mensaje a todas las conexiones de un tier."""
        if tier not in self.tier_connections:
            return 0
        
        count = 0
        connections = self.tier_connections[tier].copy()
        
        for connection_id in connections:
            if connection_id != exclude_connection:
                if await self.send_message(connection_id, message):
                    count += 1
        
        return count
    
    async def send_to_tenant(
        self,
        tenant_id: str,
        message: WebSocketMessage
    ) -> int:
        """Envía un mensaje a todas las conexiones de un tenant."""
        if tenant_id not in self.tenant_connections:
            logger.warning(f"No hay conexiones para tenant: {tenant_id}")
            return 0
        
        count = 0
        connections = self.tenant_connections[tenant_id].copy()
        
        for connection_id in connections:
            if await self.send_message(connection_id, message):
                count += 1
        
        return count
    
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
                "error_code": error_code or "UNKNOWN_ERROR",
                "timestamp": datetime.utcnow().isoformat()
            },
            task_id=task_id
        )
        
        await self.send_message(connection_id, error_message)
    
    async def handle_client_message(
        self,
        connection_id: str,
        message_data: Dict[str, Any],
        tenant_id: str,
        tenant_tier: str
    ):
        """
        Maneja mensajes recibidos del cliente.
        
        MODIFICADO: Incluye información de tenant y tier.
        """
        try:
            message_type = message_data.get("type")
            
            if message_type == "ping":
                # Responder con pong
                pong_message = WebSocketMessage(
                    type=WebSocketMessageType.PONG,
                    data={
                        "message": "pong",
                        "server_time": datetime.utcnow().isoformat()
                    }
                )
                await self.send_message(connection_id, pong_message)
                
                # Actualizar último ping
                if connection_id in self.connections_info:
                    self.connections_info[connection_id].last_ping = datetime.utcnow()
            
            elif message_type == "subscribe":
                # NUEVO: Suscripción a eventos específicos
                await self._handle_subscription(connection_id, message_data, tenant_id, tenant_tier)
            
            else:
                logger.info(f"Mensaje del cliente no manejado: {message_type}")
                
        except Exception as e:
            logger.error(f"Error manejando mensaje del cliente: {str(e)}")
            await self.send_error(connection_id, f"Error procesando mensaje: {str(e)}")
    
    async def _handle_subscription(
        self,
        connection_id: str,
        message_data: Dict[str, Any],
        tenant_id: str,
        tenant_tier: str
    ):
        """Maneja suscripciones a eventos específicos."""
        # TODO: Implementar sistema de suscripciones
        # Por ejemplo: suscribirse a actualizaciones de agentes específicos
        logger.info(f"Subscription request: {message_data} from {connection_id}")
    
    async def _track_message_rate(self, connection_id: str):
        """Rastrea rate de mensajes por conexión."""
        now = datetime.utcnow()
        
        # Limpiar mensajes antiguos (últimos 60 segundos)
        cutoff = now.timestamp() - 60
        self.connection_rates[connection_id] = [
            msg_time for msg_time in self.connection_rates[connection_id]
            if msg_time.timestamp() > cutoff
        ]
        
        # Agregar mensaje actual
        self.connection_rates[connection_id].append(now)
        
        # TODO: Implementar rate limiting si es necesario
        # current_rate = len(self.connection_rates[connection_id])
        # if current_rate > MAX_MESSAGES_PER_MINUTE:
        #     await self.send_error(connection_id, "Rate limit exceeded")
    
    async def get_connection_stats(self) -> Dict[str, Any]:
        """Obtiene estadísticas generales de conexiones."""
        return {
            "total_connections": len(self.active_connections),
            "total_sessions": len(self.session_connections),
            "total_tenants": len(self.tenant_connections),
            "connections_by_tier": {
                tier: len(connections) 
                for tier, connections in self.tier_connections.items()
            },
            "connections_by_tenant": {
                tenant_id: len(connections)
                for tenant_id, connections in self.tenant_connections.items()
            }
        }
    
    # NUEVO: Estadísticas por tenant
    async def get_tenant_stats(self, tenant_id: str) -> Dict[str, Any]:
        """Obtiene estadísticas específicas de un tenant."""
        tenant_connections = self.tenant_connections.get(tenant_id, [])
        
        # Obtener información detallada de conexiones
        connections_detail = []
        for connection_id in tenant_connections:
            if connection_id in self.connections_info:
                info = self.connections_info[connection_id]
                connections_detail.append({
                    "connection_id": connection_id,
                    "session_id": info.session_id,
                    "user_id": info.user_id,
                    "agent_id": info.agent_id,
                    "tier": info.tenant_tier,
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
        
        for connection_id, connection_info in self.connections_info.items():
            if connection_info.last_ping:
                time_since_ping = current_time - connection_info.last_ping
                if time_since_ping.total_seconds() > settings.websocket_ping_timeout * 3:
                    stale_connections.append((connection_id, connection_info))
        
        for connection_id, connection_info in stale_connections:
            logger.info(f"Limpiando conexión obsoleta: {connection_id}")
            await self.disconnect(connection_id, connection_info.tenant_id, connection_info.session_id)


# Instancia global singleton
_websocket_manager_instance = None

def get_websocket_manager() -> WebSocketManager:
    """Obtiene la instancia singleton del WebSocketManager."""
    global _websocket_manager_instance
    if _websocket_manager_instance is None:
        _websocket_manager_instance = WebSocketManager()
    return _websocket_manager_instance