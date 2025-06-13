"""
Context Handler - Manejo y validación de contextos de ejecución en Agent Execution.

Este módulo se encarga de:
- Resolver ExecutionContext desde DomainActions
- Validar permisos de ejecución
- Preparar contexto para el agente
- Cache de configuraciones de agentes
"""

import logging
import json
import datetime
from typing import Dict, Any, Optional, List

from common.models.execution_context import ExecutionContext
from agent_execution_service.config.settings import get_settings
from agent_execution_service.clients.agent_management_client import AgentManagementClient
from agent_execution_service.clients.conversation_client import ConversationServiceClient

logger = logging.getLogger(__name__)
settings = get_settings()


class ExecutionContextHandler:
    """
    Manejador de contextos de ejecución para Agent Execution Service.

    Responsable de resolver y validar contextos desde DomainActions
    y preparar el entorno para la ejecución de agentes.
    """

    def __init__(self, redis_client=None):
        """
        Inicializa handler.

        Args:
            redis_client: Cliente Redis para cache (opcional)
        """
        self.redis = redis_client
        self.settings = get_settings()
        self.agent_config_cache_ttl = self.settings.agent_config_cache_ttl
        self.conversation_history_cache_ttl = self.settings.conversation_cache_ttl
        self.default_history_limit = self.settings.default_conversation_cache_limit
        self.agent_management_client = AgentManagementClient()
        self.conversation_client = ConversationServiceClient()

    async def resolve_execution_context(
        self,
        context_dict: Dict[str, Any]
    ) -> ExecutionContext:
        """
        Resuelve ExecutionContext desde diccionario.
        """
        try:
            context = ExecutionContext.from_dict(context_dict)
            logger.info(f"Contexto resuelto: {context.context_id}")
            return context
        except Exception as e:
            logger.error(f"Error resolviendo contexto: {str(e)}")
            raise ValueError(f"Contexto de ejecución inválido: {str(e)}")

    async def get_agent_config(
        self,
        agent_id: str,
        tenant_id: str,
        session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Obtiene configuración de agente (con cache).
        """
        global_cache_key = f"agent_config:{tenant_id}:{agent_id}"
        session_cache_key = f"agent_config:{tenant_id}:{agent_id}:{session_id}" if session_id else None

        if self.redis and session_cache_key:
            cached_config = await self.redis.get(session_cache_key)
            if cached_config:
                try:
                    logger.debug(f"Cache hit por sesión para agente {agent_id}")
                    return json.loads(cached_config)
                except json.JSONDecodeError:
                    logger.warning(f"Config en cache por sesión inválida para {agent_id}")

        if self.redis:
            cached_config = await self.redis.get(global_cache_key)
            if cached_config:
                try:
                    config = json.loads(cached_config)
                    logger.debug(f"Cache hit global para agente {agent_id}")
                    if session_cache_key:
                        await self.redis.setex(session_cache_key, self.agent_config_cache_ttl, cached_config)
                    return config
                except json.JSONDecodeError:
                    logger.warning(f"Config en cache global inválida para {agent_id}")

        agent_config = await self.agent_management_client.get_agent_config(agent_id, tenant_id)
        if not agent_config:
            raise ValueError(f"Agente {agent_id} no encontrado para tenant {tenant_id}")

        if self.redis:
            config_json = json.dumps(agent_config)
            await self.redis.setex(global_cache_key, self.agent_config_cache_ttl, config_json)
            if session_cache_key:
                await self.redis.setex(session_cache_key, self.agent_config_cache_ttl, config_json)
            logger.debug(f"Configuración almacenada en caché para agente {agent_id}")
        
        return agent_config

    async def get_conversation_history(
        self,
        session_id: str,
        tenant_id: str,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Obtiene el historial de conversación (con caché).
        """
        effective_limit = limit or self.default_history_limit
        cache_key = f"conversation_history:{tenant_id}:{session_id}"

        if self.redis:
            cached_history = await self.redis.get(cache_key)
            if cached_history:
                try:
                    history = json.loads(cached_history)
                    logger.info(f"Historial obtenido desde cache para sesión {session_id}")
                    return history[:effective_limit]
                except json.JSONDecodeError:
                    logger.warning(f"Historial en cache inválido para sesión {session_id}")

        history = await self._fetch_conversation_history_from_service(session_id, tenant_id, effective_limit)

        if self.redis and history:
            await self.redis.setex(cache_key, self.conversation_history_cache_ttl, json.dumps(history))
        
        return history[:effective_limit]

    async def _fetch_conversation_history_from_service(self, session_id: str, tenant_id: str, limit: int) -> List[Dict[str, Any]]:
        """Obtiene historial desde Conversation Service."""
        try:
            history = await self.conversation_client.get_conversation_history(
                tenant_id=tenant_id, session_id=session_id, limit=limit
            )
            return history or []
        except Exception as e:
            logger.error(f"Error en fetch de historial: {str(e)}")
            return []

    async def save_message(
        self,
        session_id: str,
        tenant_id: str,
        role: str,
        content: str,
        message_type: str = "text",
        metadata: Optional[Dict[str, Any]] = None,
        processing_time: Optional[float] = None,
        wait_for_persistence: bool = False
    ) -> bool:
        """
        Guarda un mensaje en la conversación con soporte de caché local.
        """
        message = {
            "role": role,
            "content": content,
            "message_type": message_type,
            "metadata": metadata or {},
            "created_at": datetime.datetime.now().isoformat(),
            "session_id": session_id,
            "tenant_id": tenant_id,
        }

        cache_updated = False
        if self.redis:
            try:
                cache_key = f"conversation_history:{tenant_id}:{session_id}"
                cached_history = await self.redis.get(cache_key)
                history = json.loads(cached_history) if cached_history else []
                history.insert(0, message)
                history = history[:self.default_history_limit]
                await self.redis.setex(cache_key, self.conversation_history_cache_ttl, json.dumps(history))
                cache_updated = True
                logger.debug(f"Mensaje añadido a caché local para sesión {session_id}")
            except Exception as e:
                logger.warning(f"Error actualizando caché de conversación: {str(e)}")

        try:
            save_result = await self.conversation_client.save_message(
                session_id=session_id,
                tenant_id=tenant_id,
                role=role,
                content=content,
                message_type=message_type,
                metadata=metadata,
                processing_time=processing_time,
                wait_for_response=wait_for_persistence
            )
            if wait_for_persistence and not save_result:
                logger.warning(f"Error confirmado al guardar mensaje en BD para sesión {session_id}")
                return False
            return cache_updated or not wait_for_persistence
        except Exception as e:
            logger.error(f"Error enviando mensaje al servicio de conversación: {str(e)}")
            return cache_updated

    async def invalidate_conversation_cache(self, session_id: str, tenant_id: str) -> bool:
        """
        Invalida el cache de historial de conversación para una sesión específica.
        """
        if not self.redis:
            return False
        try:
            cache_key = f"conversation_history:{tenant_id}:{session_id}"
            deleted = await self.redis.delete(cache_key)
            if deleted:
                logger.debug(f"Caché de conversación para sesión {session_id} invalidado")
            return bool(deleted)
        except Exception as e:
            logger.warning(f"Error al invalidar caché de conversación: {str(e)}")
            return False

    async def handle_session_closed(self, session_id: str, tenant_id: str) -> bool:
        """
        Este método ha sido deshabilitado intencionalmente.
        """
        logger.debug(f"Método handle_session_closed deshabilitado para sesión {session_id}")
        return True

    async def validate_execution_permissions(
        self,
        context: ExecutionContext,
        agent_config: Dict[str, Any]
    ) -> bool:
        """
        Valida permisos de ejecución.
        """
        if not agent_config.get("is_active", True):
            raise ValueError(f"Agente {context.primary_agent_id} está desactivado")
        
        # Aquí irían futuras validaciones de permisos, si fueran necesarias.
        
        logger.info(f"Permisos validados para {context.primary_agent_id}")
        return True

    async def invalidate_agent_cache(self, agent_id: str, tenant_id: str, session_id: Optional[str] = None):
        """
        Invalida cache de configuración de agente.
        """
        if not self.redis:
            return

        global_cache_key = f"agent_config:{tenant_id}:{agent_id}"
        if session_id:
            session_cache_key = f"agent_config:{tenant_id}:{agent_id}:{session_id}"
            await self.redis.delete(session_cache_key)
            logger.info(f"Cache por sesión invalidado para agente {agent_id}")
        else:
            await self.redis.delete(global_cache_key)
            logger.info(f"Cache global invalidado para agente {agent_id}")
            pattern = f"agent_config:{tenant_id}:{agent_id}:*"
            async for key in self.redis.scan_iter(match=pattern):
                await self.redis.delete(key)
            logger.info(f"Invalidadas todas las cachés por sesión para agente {agent_id}")

    async def get_cache_stats(self) -> Dict[str, Any]:
        """Obtiene estadísticas del cache."""
        if not self.redis:
            return {"cache": "disabled"}
        
        config_keys = await self.redis.keys("agent_config:*")
        return {
            "cache": "enabled",
            "agent_configs": len(config_keys),
            "ttl_seconds": self.agent_config_cache_ttl
        }


# Factory function
async def get_context_handler(redis_client=None) -> ExecutionContextHandler:
    """Factory para obtener ExecutionContextHandler configurado."""
    return ExecutionContextHandler(redis_client)