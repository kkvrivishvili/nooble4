"""
Servicio principal de orquestación refactorizado.
"""
import logging
from typing import Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
import uuid

from fastapi import WebSocket

from common.services.base_service import BaseService
from common.models.actions import DomainAction, DomainActionResponse
from common.models.config_models import ExecutionConfig, QueryConfig, RAGConfig
from common.errors.exceptions import InvalidActionError, ExternalServiceError
from common.clients.base_redis_client import BaseRedisClient
from common.config.service_settings import OrchestratorSettings

from ..clients import ExecutionClient, ManagementClient
from ..models.session_models import SessionState


class OrchestrationService(BaseService):
    """
    Servicio principal de orquestación refactorizado.
    
    - Gestiona sesiones y conexiones WebSocket
    - Cachea configuraciones de agentes
    - Coordina comunicación con otros servicios
    """
    
    def __init__(
        self,
        app_settings: OrchestratorSettings,
        service_redis_client: Optional[BaseRedisClient] = None,
        direct_redis_conn=None
    ):
        super().__init__(app_settings, service_redis_client, direct_redis_conn)
        
        if not service_redis_client:
            raise ValueError("service_redis_client es requerido")
        
        # Clientes para otros servicios
        self.execution_client = ExecutionClient(
            redis_client=service_redis_client,
            settings=app_settings
        )
        
        self.management_client = ManagementClient(
            redis_client=service_redis_client,
            settings=app_settings
        )
        
        # Estado en memoria
        self.sessions: Dict[str, SessionState] = {}
        self.websocket_connections: Dict[str, WebSocket] = {}
        
        # Configuración
        self.config_cache_ttl = 300  # 5 minutos
        
        self._logger.info("OrchestrationService inicializado")
    
    async def create_session(
        self,
        session_id: uuid.UUID,
        tenant_id: uuid.UUID,
        agent_id: uuid.UUID,
        user_id: Optional[uuid.UUID],
        agent_config: Optional[Dict[str, Any]] = None
    ) -> SessionState:
        """Crea una nueva sesión con configuración pre-cargada."""
        session_state = SessionState(
            session_id=session_id,
            tenant_id=tenant_id,
            agent_id=agent_id,
            user_id=user_id,
            agent_config=agent_config,
            config_fetched_at=datetime.utcnow() if agent_config else None
        )
        
        self.sessions[str(session_id)] = session_state
        
        self._logger.info(
            f"Sesión creada",
            extra={
                "session_id": str(session_id),
                "tenant_id": str(tenant_id),
                "agent_id": str(agent_id)
            }
        )
        
        return session_state
    
    async def get_session_state(self, session_id: str) -> Optional[SessionState]:
        """Obtiene el estado de una sesión."""
        return self.sessions.get(session_id)
    
    async def register_websocket_connection(
        self,
        session_id: str,
        websocket: WebSocket,
        connection_id: str
    ):
        """Registra una conexión WebSocket para una sesión."""
        session_state = self.sessions.get(session_id)
        if not session_state:
            raise ValueError(f"Sesión {session_id} no encontrada")
        
        # Actualizar estado
        session_state.connection_id = connection_id
        session_state.websocket_connected = True
        session_state.last_activity = datetime.utcnow()
        
        # Guardar WebSocket
        self.websocket_connections[session_id] = websocket
        
        self._logger.info(f"WebSocket conectado para sesión {session_id}")
    
    async def unregister_websocket_connection(
        self,
        session_id: str,
        connection_id: str
    ):
        """Desregistra una conexión WebSocket."""
        session_state = self.sessions.get(session_id)
        if session_state and session_state.connection_id == connection_id:
            session_state.websocket_connected = False
            session_state.connection_id = None
            session_state.last_activity = datetime.utcnow()
        
        # Remover WebSocket
        self.websocket_connections.pop(session_id, None)
        
        self._logger.info(f"WebSocket desconectado para sesión {session_id}")
    
    async def get_agent_configurations(
        self,
        tenant_id: str,
        agent_id: str,
        session_id: str,
        task_id: str,
        user_id: Optional[str] = None
    ) -> Tuple[ExecutionConfig, QueryConfig, RAGConfig]:
        """
        Obtiene las configuraciones del agente.
        Usa cache de sesión si está disponible y fresco.
        """
        # Verificar cache
        session_state = self.sessions.get(session_id)
        if session_state and session_state.agent_config and session_state.config_fetched_at:
            # Verificar si el cache es válido
            age = (datetime.utcnow() - session_state.config_fetched_at).seconds
            if age < self.config_cache_ttl:
                self._logger.debug(f"Usando configuración cacheada para sesión {session_id}")
                config = session_state.agent_config
                return (
                    ExecutionConfig(**config["execution_config"]),
                    QueryConfig(**config["query_config"]),
                    RAGConfig(**config["rag_config"])
                )
        
        # Obtener del Management Service
        self._logger.info(f"Obteniendo configuración del Management Service para agente {agent_id}")
        configs = await self.management_client.get_agent_configurations(
            tenant_id=tenant_id,
            agent_id=agent_id,
            session_id=session_id,
            task_id=task_id,
            user_id=user_id
        )
        
        # Actualizar cache si tenemos sesión
        if session_state:
            session_state.agent_config = {
                "execution_config": configs[0].model_dump(),
                "query_config": configs[1].model_dump(),
                "rag_config": configs[2].model_dump()
            }
            session_state.config_fetched_at = datetime.utcnow()
        
        return configs
    
    async def process_chat_message(
        self,
        session_id: str,
        task_id: uuid.UUID,
        message: str,
        message_type: str = "text",
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Procesa un mensaje de chat."""
        session_state = self.sessions.get(session_id)
        if not session_state:
            raise ValueError(f"Sesión {session_id} no encontrada")
        
        # Actualizar estado
        session_state.last_activity = datetime.utcnow()
        session_state.active_task_id = task_id
        session_state.total_tasks += 1
        
        # Obtener configuraciones (usa cache si disponible)
        execution_config, query_config, rag_config = await self.get_agent_configurations(
            tenant_id=str(session_state.tenant_id),
            agent_id=str(session_state.agent_id),
            session_id=session_id,
            task_id=str(task_id),
            user_id=str(session_state.user_id) if session_state.user_id else None
        )
        
        # Crear DomainAction
        action = DomainAction(
            action_id=uuid.uuid4(),
            action_type="execution.chat.process",
            timestamp=datetime.utcnow(),
            # IDs de contexto
            tenant_id=session_state.tenant_id,
            session_id=session_state.session_id,
            task_id=task_id,
            agent_id=session_state.agent_id,
            user_id=session_state.user_id,
            # Origen
            origin_service=self.service_name,
            # Configuraciones
            execution_config=execution_config,
            query_config=query_config,
            rag_config=rag_config,
            # Datos del mensaje
            data={
                "message": message,
                "message_type": message_type,
                "metadata": metadata or {}
            },
            metadata={
                "mode": metadata.get("mode", "simple") if metadata else "simple"
            }
        )
        
        # Enviar al Execution Service
        self._logger.info(
            f"Enviando mensaje al Execution Service",
            extra={
                "session_id": session_id,
                "task_id": str(task_id),
                "action_id": str(action.action_id)
            }
        )
        
        try:
            response = await self.execution_client.send_chat_message(action)
            
            if not response.success:
                error_msg = response.error.message if response.error else "Error desconocido"
                raise ExternalServiceError(f"Execution Service error: {error_msg}")
            
            # Limpiar task activo
            session_state.active_task_id = None
            
            return response.data or {}
            
        except Exception as e:
            # Limpiar task activo en caso de error
            session_state.active_task_id = None
            raise
    
    async def cleanup_inactive_sessions(self, inactive_minutes: int = 30):
        """Limpia sesiones inactivas."""
        now = datetime.utcnow()
        sessions_to_remove = []
        
        for session_id, session_state in self.sessions.items():
            inactive_time = (now - session_state.last_activity).total_seconds() / 60
            if inactive_time > inactive_minutes:
                sessions_to_remove.append(session_id)
        
        for session_id in sessions_to_remove:
            # Cerrar WebSocket si existe
            websocket = self.websocket_connections.get(session_id)
            if websocket:
                try:
                    await websocket.close()
                except:
                    pass
                del self.websocket_connections[session_id]
            
            # Remover sesión
            del self.sessions[session_id]
            self._logger.info(f"Sesión {session_id} limpiada por inactividad")
        
        return len(sessions_to_remove)
    
    async def process_action(self, action: DomainAction) -> Optional[Dict[str, Any]]:
        """
        Procesa Domain Actions (para compatibilidad con BaseService).
        La mayoría del procesamiento es vía WebSocket.
        """
        # Este método es principalmente para compatibilidad
        # El procesamiento real ocurre en process_chat_message
        raise InvalidActionError(f"Action type {action.action_type} no soportado")