from typing import Dict, Set
import json
import logging
from fastapi import WebSocket
import asyncio


class WebSocketManager:
    """Manager for WebSocket connections"""
    
    def __init__(self):
        # Map user_id to set of connections
        self.active_connections: Dict[str, Set[WebSocket]] = {}
        self._lock = asyncio.Lock()
        self.logger = logging.getLogger("WebSocketManager")
    
    async def connect(self, websocket: WebSocket, user_id: str):
        """Accept and register a new connection"""
        await websocket.accept()
        
        async with self._lock:
            if user_id not in self.active_connections:
                self.active_connections[user_id] = set()
            self.active_connections[user_id].add(websocket)
        
        self.logger.info(f"User {user_id} connected via WebSocket")
    
    async def disconnect(self, websocket: WebSocket, user_id: str):
        """Remove a connection"""
        async with self._lock:
            if user_id in self.active_connections:
                self.active_connections[user_id].discard(websocket)
                if not self.active_connections[user_id]:
                    del self.active_connections[user_id]
        
        self.logger.info(f"User {user_id} disconnected from WebSocket")
    
    async def send_to_user(self, user_id: str, message: dict):
        """Send message to all connections for a user"""
        async with self._lock:
            connections = self.active_connections.get(user_id, set()).copy()
        
        if not connections:
            return
        
        message_text = json.dumps(message)
        disconnected = []
        
        for websocket in connections:
            try:
                await websocket.send_text(message_text)
            except Exception as e:
                self.logger.error(f"Error sending to user {user_id}: {e}")
                disconnected.append(websocket)
        
        # Clean up disconnected
        if disconnected:
            async with self._lock:
                if user_id in self.active_connections:
                    for ws in disconnected:
                        self.active_connections[user_id].discard(ws)
