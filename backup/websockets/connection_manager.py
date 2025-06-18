"""
Gestor de conexiones WebSocket para el servicio de ingestión.

Este módulo implementa la infraestructura necesaria para:
- Gestionar conexiones WebSocket activas
- Agrupar conexiones por task_id
- Transmitir eventos a los clientes conectados
"""

import json
import logging
import asyncio
from typing import Dict, List, Set, Any, Optional
from fastapi import WebSocket, WebSocketDisconnect

from ingestion_service.models.events import WebSocketEvent, EventType
from common.context import with_context, Context

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Gestiona las conexiones WebSocket activas y la transmisión de eventos."""
    
    def __init__(self):
        """Inicializa el gestor de conexiones."""
        # Conexiones indexadas por task_id
        self.active_connections: Dict[str, Set[WebSocket]] = {}
        # Conexiones indexadas por tenant_id
        self.tenant_connections: Dict[str, Set[WebSocket]] = {}
        # Lock para operaciones thread-safe
        self.lock = asyncio.Lock()
    
    async def connect(self, websocket: WebSocket, task_id: str, tenant_id: str) -> None:
        """Establece una nueva conexión WebSocket.
        
        Args:
            websocket: Conexión WebSocket
            task_id: ID de la tarea a la que se suscribe
            tenant_id: ID del tenant
        """
        await websocket.accept()
        
        async with self.lock:
            # Añadir a las conexiones de la tarea
            if task_id not in self.active_connections:
                self.active_connections[task_id] = set()
            self.active_connections[task_id].add(websocket)
            
            # Añadir a las conexiones del tenant
            if tenant_id not in self.tenant_connections:
                self.tenant_connections[tenant_id] = set()
            self.tenant_connections[tenant_id].add(websocket)
            
        logger.info(
            f"Nueva conexión WebSocket aceptada: task_id={task_id}, "
            f"tenant_id={tenant_id}"
        )
        
        # Enviar mensaje de confirmación de conexión
        await websocket.send_json({
            "event_type": "connection_established",
            "task_id": task_id,
            "data": {"status": "connected", "message": "Connected successfully"}
        })
    
    async def disconnect(self, websocket: WebSocket, task_id: str, tenant_id: str) -> None:
        """Cierra una conexión WebSocket.
        
        Args:
            websocket: Conexión WebSocket a cerrar
            task_id: ID de la tarea asociada
            tenant_id: ID del tenant
        """
        async with self.lock:
            # Eliminar de las conexiones de la tarea
            if task_id in self.active_connections and websocket in self.active_connections[task_id]:
                self.active_connections[task_id].remove(websocket)
                if not self.active_connections[task_id]:
                    del self.active_connections[task_id]
            
            # Eliminar de las conexiones del tenant
            if tenant_id in self.tenant_connections and websocket in self.tenant_connections[tenant_id]:
                self.tenant_connections[tenant_id].remove(websocket)
                if not self.tenant_connections[tenant_id]:
                    del self.tenant_connections[tenant_id]
        
        logger.info(f"Conexión WebSocket cerrada: task_id={task_id}, tenant_id={tenant_id}")
    
    @with_context
    async def broadcast_to_task(
        self, 
        task_id: str, 
        event: WebSocketEvent,
        ctx: Optional[Context] = None
    ) -> int:
        """Transmite un evento a todas las conexiones suscritas a una tarea.
        
        Args:
            task_id: ID de la tarea
            event: Evento a transmitir
            ctx: Contexto de la operación
            
        Returns:
            int: Número de conexiones a las que se transmitió el evento
        """
        if task_id not in self.active_connections:
            return 0
        
        count = 0
        connections = set(self.active_connections[task_id])  # Copia para evitar problemas de concurrencia
        
        for websocket in connections:
            try:
                await websocket.send_json(event.dict())
                count += 1
            except Exception as e:
                logger.error(f"Error al enviar evento por WebSocket: {e}")
                # Desconectamos si hay error pero sin bloquear la broadcast
                asyncio.create_task(
                    self.disconnect(websocket, task_id, event.tenant_id)
                )
        
        logger.debug(
            f"Evento {event.event_type} transmitido a {count} conexiones "
            f"para la tarea {task_id}"
        )
        return count
    
    @with_context
    async def broadcast_to_tenant(
        self, 
        tenant_id: str, 
        event: WebSocketEvent,
        ctx: Optional[Context] = None
    ) -> int:
        """Transmite un evento a todas las conexiones del tenant.
        
        Args:
            tenant_id: ID del tenant
            event: Evento a transmitir
            ctx: Contexto de la operación
            
        Returns:
            int: Número de conexiones a las que se transmitió el evento
        """
        if tenant_id not in self.tenant_connections:
            return 0
        
        count = 0
        connections = set(self.tenant_connections[tenant_id])  # Copia para evitar problemas de concurrencia
        
        for websocket in connections:
            try:
                await websocket.send_json(event.dict())
                count += 1
            except Exception as e:
                logger.error(f"Error al enviar evento por WebSocket: {e}")
                # Identificar la tarea para esta conexión
                task_id = event.task_id if hasattr(event, 'task_id') else "unknown"
                asyncio.create_task(
                    self.disconnect(websocket, task_id, tenant_id)
                )
        
        return count


# Instancia global del gestor de conexiones
connection_manager = ConnectionManager()
