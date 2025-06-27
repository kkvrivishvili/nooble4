"""
Cliente para comunicación con Agent Management Service.
"""
import logging
import uuid
from typing import Dict, Any, Optional, Tuple
from datetime import datetime

from common.models.actions import DomainAction
from common.models.config_models import ExecutionConfig, QueryConfig, RAGConfig
from common.errors.exceptions import ExternalServiceError
from common.clients.base_redis_client import BaseRedisClient
from common.config.service_settings import OrchestratorSettings


class ManagementClient:
    """Cliente para Agent Management Service vía Redis DomainActions."""
    
    def __init__(
        self,
        redis_client: BaseRedisClient,
        settings: OrchestratorSettings
    ):
        """
        Inicializa el cliente.
        
        Args:
            redis_client: Cliente Redis base para comunicación
            settings: Configuración del servicio
        """
        if not redis_client:
            raise ValueError("redis_client es requerido")
        if not settings:
            raise ValueError("settings son requeridas")
            
        self.redis_client = redis_client
        self.default_timeout = 10  # Timeout corto para obtener configs
        self._logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
    
    async def get_agent_configurations(
        self,
        tenant_id: str,
        agent_id: str,
        session_id: str,
        user_id: Optional[str] = None,
        timeout: Optional[int] = None
    ) -> Tuple[ExecutionConfig, QueryConfig, RAGConfig]:
        """
        Obtiene las configuraciones del agente desde Management Service.
        
        Args:
            tenant_id: ID del tenant
            agent_id: ID del agente
            session_id: ID de la sesión
            user_id: ID del usuario (opcional)
            timeout: Timeout personalizado
            
        Returns:
            Tupla con (ExecutionConfig, QueryConfig, RAGConfig)
            
        Raises:
            ExternalServiceError: Si falla la comunicación o el agente no existe
        """
        # Crear DomainAction para solicitar configuraciones
        action = DomainAction(
            action_id=uuid.uuid4(),
            action_type="management.agent.get_config",
            timestamp=datetime.utcnow(),
            tenant_id=uuid.UUID(tenant_id),
            session_id=uuid.UUID(session_id),
            task_id=uuid.uuid4(),  # Task temporal para esta consulta
            agent_id=uuid.UUID(agent_id),
            user_id=uuid.UUID(user_id) if user_id else None,
            origin_service=self.redis_client.service_name,
            data={
                "agent_id": agent_id,
                "config_types": ["execution", "query", "rag"]
            }
        )
        
        actual_timeout = timeout if timeout is not None else self.default_timeout
        
        try:
            # Enviar y esperar respuesta
            response = await self.redis_client.send_action_pseudo_sync(
                action,
                timeout=actual_timeout
            )
            
            if not response.success or response.data is None:
                error_detail = response.error
                error_message = f"Management Service error: {error_detail.message if error_detail else 'Unknown error'}"
                self._logger.error(error_message, extra={
                    "action_id": str(action.action_id),
                    "agent_id": agent_id,
                    "error_detail": error_detail.model_dump() if error_detail else None
                })
                raise ExternalServiceError(error_message, error_detail=error_detail)
            
            # Extraer y validar configuraciones
            config_data = response.data
            
            # Validar que existan las configuraciones
            if not all(k in config_data for k in ["execution_config", "query_config", "rag_config"]):
                raise ExternalServiceError(
                    "Respuesta incompleta del Management Service: faltan configuraciones"
                )
            
            # Parsear configuraciones usando modelos Pydantic
            execution_config = ExecutionConfig(**config_data["execution_config"])
            query_config = QueryConfig(**config_data["query_config"])
            rag_config = RAGConfig(**config_data["rag_config"])
            
            self._logger.info(
                f"Configuraciones obtenidas exitosamente para agent_id={agent_id}",
                extra={
                    "tenant_id": tenant_id,
                    "agent_id": agent_id,
                    "has_execution": bool(execution_config),
                    "has_query": bool(query_config),
                    "has_rag": bool(rag_config)
                }
            )
            
            return execution_config, query_config, rag_config
            
        except TimeoutError as e:
            self._logger.error(f"Timeout obteniendo configuraciones: {e}")
            raise ExternalServiceError(f"Timeout esperando respuesta del Management Service: {str(e)}")
        except Exception as e:
            self._logger.error(f"Error obteniendo configuraciones: {e}", exc_info=True)
            raise ExternalServiceError(f"Error comunicándose con Management Service: {str(e)}")
    
    async def validate_agent_access(
        self,
        tenant_id: str,
        agent_id: str,
        user_id: Optional[str] = None,
        timeout: Optional[int] = None
    ) -> bool:
        """
        Valida que el tenant tiene acceso al agente.
        
        Args:
            tenant_id: ID del tenant
            agent_id: ID del agente
            user_id: ID del usuario (opcional)
            timeout: Timeout personalizado
            
        Returns:
            True si tiene acceso, False en caso contrario
        """
        try:
            # Intentar obtener configuraciones como forma de validación
            await self.get_agent_configurations(
                tenant_id=tenant_id,
                agent_id=agent_id,
                session_id=str(uuid.uuid4()),  # Session temporal
                user_id=user_id,
                timeout=timeout
            )
            return True
        except ExternalServiceError:
            return False