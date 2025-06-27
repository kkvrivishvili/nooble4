"""
WebSocket Manager para Agent Orchestrator Service.

Gestiona conexiones WebSocket persistentes para chat en tiempo real,
manteniendo el mapeo session_id -> websocket durante toda la conversación.
"""
import json
import logging
import asyncio
from typing import Dict, Set, Optional, Any
from datetime import datetime
import uuid

from fastapi import WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState

from ..models.websocket_model import WebSocketMessage, WebSocketMessageType
from ..models.session_models import SessionState, ConnectionInfo


class WebSocketManager:
    """
    Gestor de conexiones WebSocket para chat en tiempo real.
    
    Mantiene conexiones persistentes por sesión y gestiona
    el envío de mensajes durante toda la conversación.
    """
    
    def __init__(self):
        # Mapeo principal: session_id -> WebSocket
        self.active_connections: Dict[str, WebSocket] = {}
        
        # Información de conexiones: session_id -> ConnectionInfo
        self.connection_info: Dict[str, ConnectionInfo] = {}
        
        # Mapeo inverso: websocket -> session_id (para cleanup)
        self.websocket_to_session: Dict[WebSocket, str] = {}
        
        # Estado de sesiones activas
        self.session_states: Dict[str, SessionState] = {}
        
        # Lock para operaciones concurrentes
        self._lock = asyncio.Lock()
        
        self.logger = logging.getLogger("WebSocketManager")
    
    async def connect(
        self,
        websocket: WebSocket,
        session_id: str,
        tenant_id: str,
        agent_id: str,
        user_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Acepta y registra una nueva conexión WebSocket.
        
        Returns:
            connection_id único para esta conexión
        """
        await websocket.accept()
        
        connection_id = str(uuid.uuid4())
        
        async with self._lock:
            # Si ya existe una conexión para esta sesión, cerrarla
            if session_id in self.active_connections:
                old_ws = self.active_connections[session_id]
                await self._close_websocket(old_ws)
                self.logger.info(f"Reemplazando conexión existente para sesión {session_id}")
            
            # Registrar nueva conexión
            self.active_connections[session_id] = websocket
            self.websocket_to_session[websocket] = session_id
            
            # Crear información de conexión
            conn_info = ConnectionInfo(
                connection_id=connection_id,
                session_id=session_id,
                tenant_id=tenant_id,
                agent_id=agent_id,
                user_id=user_id,
                connected_at=datetime.utcnow(),
                metadata=metadata or {}
            )
            self.connection_info[session_id] = conn_info
            
            # Crear o recuperar estado de sesión
            if session_id not in self.session_states:
                self.session_states[session_id] = SessionState(
                    session_id=session_id,
                    tenant_id=tenant_id,
                    agent_id=agent_id,
                    user_id=user_id,
                    created_at=datetime.utcnow()
                )
            
            # Actualizar último activity
            self.session_states[session_id].last_activity = datetime.utcnow()
            self.session_states[session_id].connection_id = connection_id
        
        self.logger.info(
            f"Nueva conexión WebSocket: {connection_id} "
            f"(session: {session_id}, tenant: {tenant_id}, agent: {agent_id})"
        )
        
        # Enviar confirmación de conexión
        await self.send_to_session(
            session_id,
            WebSocketMessage(
                type=WebSocketMessageType.CONNECTION_ACK,
                data={
                    "connection_id": connection_id,
                    "session_id": session_id,
                    "message": "Conexión establecida"
                }
            )
        )
        
        return connection_id
    
    async def disconnect(self, websocket: WebSocket, session_id: str):
        """Desconecta y limpia una conexión WebSocket"""
        async with self._lock:
            # Verificar que el websocket corresponde a la sesión
            if self.websocket_to_session.get(websocket) == session_id:
                # Limpiar mapeos
                del self.websocket_to_session[websocket]
                del self.active_connections[session_id]
                
                if session_id in self.connection_info:
                    del self.connection_info[session_id]
                
                # Actualizar estado de sesión
                if session_id in self.session_states:
                    self.session_states[session_id].connection_id = None
                    self.session_states[session_id].last_activity = datetime.utcnow()
        
        self.logger.info(f"Conexión WebSocket desconectada para sesión {session_id}")
    
    async def send_to_session(
        self,
        session_id: str,
        message: WebSocketMessage
    ) -> bool:
        """
        Envía un mensaje a una sesión específica.
        
        Returns:
            True si se envió exitosamente, False en caso contrario
        """
        websocket = self.active_connections.get(session_id)
        if not websocket:
            self.logger.warning(f"No hay conexión activa para sesión {session_id}")
            return False
        
        try:
            # Asegurar que el mensaje tiene session_id
            message.session_id = session_id
            
            # Serializar y enviar
            message_data = message.model_dump()
            await websocket.send_json(message_data)
            
            # Actualizar actividad
            if session_id in self.session_states:
                self.session_states[session_id].last_activity = datetime.utcnow()
                self.session_states[session_id].messages_sent += 1
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error enviando mensaje a sesión {session_id}: {e}")
            # Limpiar conexión fallida
            await self._cleanup_failed_connection(websocket, session_id)
            return False
    
    async def broadcast_to_tenant(
        self,
        tenant_id: str,
        message: WebSocketMessage,
        exclude_session: Optional[str] = None
    ) -> int:
        """
        Envía un mensaje a todas las sesiones de un tenant.
        
        Returns:
            Número de mensajes enviados exitosamente
        """
        sent_count = 0
        
        # Obtener todas las sesiones del tenant
        tenant_sessions = [
            session_id
            for session_id, state in self.session_states.items()
            if state.tenant_id == tenant_id and session_id != exclude_session
        ]
        
        for session_id in tenant_sessions:
            if await self.send_to_session(session_id, message):
                sent_count += 1
        
        return sent_count
    
    async def handle_client_message(
        self,
        websocket: WebSocket,
        session_id: str,
        message_data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Procesa mensajes recibidos del cliente.
        
        Returns:
            Datos procesados del mensaje o None si es un mensaje de control
        """
        message_type = message_data.get("type")
        
        # Actualizar actividad
        if session_id in self.session_states:
            self.session_states[session_id].last_activity = datetime.utcnow()
            self.session_states[session_id].messages_received += 1
        
        # Manejar mensajes de control
        if message_type == "ping":
            await self.send_to_session(
                session_id,
                WebSocketMessage(
                    type=WebSocketMessageType.PONG,
                    data={"timestamp": datetime.utcnow().isoformat()}
                )
            )
            return None
        
        # Mensajes de chat pasan a procesamiento
        return message_data
    
    async def get_session_state(self, session_id: str) -> Optional[SessionState]:
        """Obtiene el estado de una sesión"""
        return self.session_states.get(session_id)
    
    async def update_session_task(self, session_id: str, task_id: str):
        """Actualiza el task_id actual de una sesión"""
        if session_id in self.session_states:
            self.session_states[session_id].current_task_id = task_id
            self.session_states[session_id].task_count += 1
    
    async def _cleanup_failed_connection(self, websocket: WebSocket, session_id: str):
        """Limpia una conexión que falló"""
        try:
            await self.disconnect(websocket, session_id)
        except Exception as e:
            self.logger.error(f"Error durante cleanup de conexión: {e}")
    
    async def _close_websocket(self, websocket: WebSocket):
        """Cierra un WebSocket de forma segura"""
        try:
            if websocket.client_state == WebSocketState.CONNECTED:
                await websocket.close()
        except Exception as e:
            self.logger.error(f"Error cerrando WebSocket: {e}")
    
    async def cleanup_inactive_sessions(self, inactive_minutes: int = 30):
        """Limpia sesiones inactivas"""
        now = datetime.utcnow()
        sessions_to_remove = []
        
        async with self._lock:
            for session_id, state in self.session_states.items():
                inactive_time = (now - state.last_activity).total_seconds() / 60
                if inactive_time > inactive_minutes:
                    sessions_to_remove.append(session_id)
            
            for session_id in sessions_to_remove:
                # Cerrar conexión si existe
                if session_id in self.active_connections:
                    websocket = self.active_connections[session_id]
                    await self._close_websocket(websocket)
                    await self.disconnect(websocket, session_id)
                
                # Limpiar estado
                del self.session_states[session_id]
        
        if sessions_to_remove:
            self.logger.info(f"Limpiadas {len(sessions_to_remove)} sesiones inactivas")
    
    def get_stats(self) -> Dict[str, Any]:
        """Obtiene estadísticas del manager"""
        return {
            "active_connections": len(self.active_connections),
            "active_sessions": len(self.session_states),
            "connections_by_tenant": self._get_connections_by_tenant(),
            "timestamp": datetime.utcnow().isoformat()
        }
    
    def _get_connections_by_tenant(self) -> Dict[str, int]:
        """Cuenta conexiones por tenant"""
        tenant_counts = {}
        for state in self.session_states.values():
            tenant_counts[state.tenant_id] = tenant_counts.get(state.tenant_id, 0) + 1
        return tenant_counts