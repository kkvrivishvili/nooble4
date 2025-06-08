"""
Context Handler - Manejo y validación de contextos de ejecución en Agent Execution.

Este módulo se encarga de:
- Resolver ExecutionContext desde DomainActions
- Validar permisos de ejecución
- Preparar contexto para LangChain
- Cache de configuraciones de agentes
"""

import logging
from typing import Optional, Dict, Any, List
from datetime import datetime
import json

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
        
        # Cache TTL para configuraciones de agentes (5 minutos)
        self.agent_config_cache_ttl = 300
        
        # Clientes para servicios externos
        self.agent_management_client = AgentManagementClient()
        self.conversation_client = ConversationServiceClient()
    
    async def resolve_execution_context(
        self,
        context_dict: Dict[str, Any]
    ) -> ExecutionContext:
        """
        Resuelve ExecutionContext desde diccionario.
        
        Args:
            context_dict: Diccionario con datos del contexto
            
        Returns:
            ExecutionContext válido
            
        Raises:
            ValueError: Si el contexto no es válido
        """
        try:
            # Crear ExecutionContext desde diccionario
            context = ExecutionContext.from_dict(context_dict)
            
            logger.info(f"Contexto resuelto: {context.context_id} (tier: {context.tenant_tier})")
            return context
            
        except Exception as e:
            logger.error(f"Error resolviendo contexto: {str(e)}")
            raise ValueError(f"Contexto de ejecución inválido: {str(e)}")
    
    async def get_agent_configuration(
        self,
        agent_id: str,
        tenant_id: str
    ) -> Dict[str, Any]:
        """
        Obtiene configuración de agente (con cache).
        
        Args:
            agent_id: ID del agente
            tenant_id: ID del tenant
            
        Returns:
            Dict con configuración del agente
            
        Raises:
            ValueError: Si el agente no existe o no es accesible
        """
        # Cache key - Más específico para evitar colisiones
        cache_key = f"agent_execution_config:{tenant_id}:{agent_id}"
        
        # Verificar cache
        if self.redis:
            cached_config = await self.redis.get(cache_key)
            if cached_config:
                try:
                    return json.loads(cached_config)
                except json.JSONDecodeError:
                    logger.warning(f"Config en cache inválida para {agent_id}")
        
        # Obtener desde Agent Management Service
        agent_config = await self.agent_management_client.get_agent(agent_id, tenant_id)
        
        if not agent_config:
            raise ValueError(f"Agente {agent_id} no encontrado para tenant {tenant_id}")
        
        # Cachear configuración
        if self.redis:
            await self.redis.setex(
                cache_key, 
                self.agent_config_cache_ttl, 
                json.dumps(agent_config)
            )
        
        logger.info(f"Configuración de agente obtenida: {agent_id}")
        return agent_config
    
    async def get_conversation_history(
        self,
        session_id: str,
        tenant_id: str,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Obtiene historial de conversación.
        
        Args:
            session_id: ID de la sesión
            tenant_id: ID del tenant
            limit: Número máximo de mensajes
            
        Returns:
            Lista de mensajes del historial
        """
        try:
            history = await self.conversation_client.get_conversation_history(
                session_id=session_id,
                tenant_id=tenant_id,
                limit=limit,
                include_system=True  # Incluir mensajes del sistema
            )
            
            logger.info(f"Historial obtenido: {len(history)} mensajes para sesión {session_id}")
            return history
            
        except Exception as e:
            logger.error(f"Error obteniendo historial: {str(e)}")
            return []  # Retornar lista vacía en caso de error
    
    async def validate_execution_permissions(
        self,
        context: ExecutionContext,
        agent_config: Dict[str, Any]
    ) -> bool:
        """
        Valida permisos de ejecución.
        
        Args:
            context: Contexto de ejecución
            agent_config: Configuración del agente
            
        Returns:
            True si tiene permisos
            
        Raises:
            ValueError: Si no tiene permisos
        """
        # Validar que el agente esté activo
        if not agent_config.get("is_active", True):
            raise ValueError(f"Agente {context.primary_agent_id} está desactivado")
        
        # Validar tier vs capacidades del agente
        agent_tier_required = agent_config.get("minimum_tier", "free")
        tier_hierarchy = {"free": 0, "advance": 1, "professional": 2, "enterprise": 3}
        
        user_tier_level = tier_hierarchy.get(context.tenant_tier, 0)
        required_tier_level = tier_hierarchy.get(agent_tier_required, 0)
        
        if user_tier_level < required_tier_level:
            raise ValueError(
                f"Tier {context.tenant_tier} insuficiente. Se requiere {agent_tier_required}"
            )
        
        # Validar límites por tier
        await self._validate_tier_limits(context)
        
        logger.info(f"Permisos validados para {context.primary_agent_id} (tier: {context.tenant_tier})")
        return True
    
    async def _validate_tier_limits(self, context: ExecutionContext):
        """Valida límites específicos del tier."""
        # Límites por tier (ejemplos)
        tier_limits = {
            "free": {"max_iterations": 3, "max_tools": 2},
            "advance": {"max_iterations": 5, "max_tools": 5},
            "professional": {"max_iterations": 10, "max_tools": 10},
            "enterprise": {"max_iterations": None, "max_tools": None}  # Sin límites
        }
        
        limits = tier_limits.get(context.tenant_tier, tier_limits["free"])
        
        # Aquí se pueden implementar validaciones específicas
        # Por ejemplo, verificar uso actual vs límites
        
        logger.debug(f"Límites para tier {context.tenant_tier}: {limits}")
    
    async def invalidate_agent_cache(self, agent_id: str, tenant_id: str):
        """Invalida cache de configuración de agente."""
        if self.redis:
            cache_key = f"agent_config:{tenant_id}:{agent_id}"
            await self.redis.delete(cache_key)
            logger.info(f"Cache invalidado para agente {agent_id}")
    
    async def get_cache_stats(self) -> Dict[str, Any]:
        """Obtiene estadísticas del cache."""
        if not self.redis:
            return {"cache": "disabled"}
        
        # Contar keys de configuración de agentes
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