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
from typing import Dict, Any, Optional, List, Union
from uuid import UUID

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
        
        # Obtener configuraciones desde settings
        self.settings = get_settings()
        
        # Cache TTL para configuraciones de agentes (desde settings)
        self.agent_config_cache_ttl = self.settings.agent_config_cache_ttl
        
        # Cache TTL para historiales de conversación (desde settings)
        self.conversation_history_cache_ttl = self.settings.conversation_cache_ttl
        
        # Límite predeterminado de mensajes para historial en caché
        self.default_history_limit = self.settings.default_conversation_cache_limit
        
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
    
    async def get_agent_config(
        self,
        agent_id: str,
        tenant_id: str,
        session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Obtiene configuración de agente (con cache).
        
        Args:
            agent_id: ID del agente
            tenant_id: ID del tenant
            session_id: ID de la sesión (opcional)
            
        Returns:
            Dict con configuración del agente
            
        Raises:
            ValueError: Si el agente no existe o no es accesible
        """
            # Claves de caché - Enfoque dual
        global_cache_key = f"agent_config:{tenant_id}:{agent_id}"
        session_cache_key = None if not session_id else f"agent_config:{tenant_id}:{agent_id}:{session_id}"
        
        # Verificar caché específica por sesión primero (si hay session_id)
        if self.redis and session_id and session_cache_key:
            session_cached_config = await self.redis.get(session_cache_key)
            if session_cached_config:
                try:
                    logger.debug(f"Cache hit por sesión para agente {agent_id}, sesión {session_id}")
                    return json.loads(session_cached_config)
                except json.JSONDecodeError:
                    logger.warning(f"Config en cache por sesión inválida para {agent_id}")
        
        # Verificar caché global
        if self.redis:
            global_cached_config = await self.redis.get(global_cache_key)
            if global_cached_config:
                try:
                    config = json.loads(global_cached_config)
                    logger.debug(f"Cache hit global para agente {agent_id}")
                    
                    # Si hay session_id, almacenar también en caché por sesión
                    if session_id and session_cache_key:
                        await self.redis.setex(
                            session_cache_key,
                            self.agent_config_cache_ttl,
                            global_cached_config  # Reutilizar el JSON ya serializado
                        )
                        logger.debug(f"Replicada config global a caché por sesión {session_id}")
                    
                    return config
                except json.JSONDecodeError:
                    logger.warning(f"Config en cache global inválida para {agent_id}")
        
        # Obtener desde Agent Management Service
        agent_config = await self.agent_management_client.get_agent_config(agent_id, tenant_id)
        
        if not agent_config:
            raise ValueError(f"Agente {agent_id} no encontrado para tenant {tenant_id}")
        
        # Cachear configuración (enfoque dual)
        if self.redis:
            # Serializar una sola vez para eficiencia
            config_json = json.dumps(agent_config)
            
            # Almacenar en caché global
            await self.redis.setex(
                global_cache_key, 
                self.agent_config_cache_ttl, 
                config_json
            )
            logger.debug(f"Configuración almacenada en caché global: {agent_id}")
            
            # Almacenar también en caché por sesión si hay session_id
            if session_id and session_cache_key:
                await self.redis.setex(
                    session_cache_key, 
                    self.agent_config_cache_ttl, 
                    config_json  # Reutilizar el JSON ya serializado
                )
                logger.debug(f"Configuración almacenada en caché por sesión: {agent_id}, sesión {session_id}")
        
        logger.info(f"Configuración de agente obtenida: {agent_id}")
        return agent_config
    
    async def invalidate_agent_config_cache(self, agent_id: str, tenant_id: str):
        """
        Invalida la caché para una configuración de agente específica.

        Elimina tanto la entrada de caché global como todas las entradas de caché
        específicas de la sesión para el agente.

        Args:
            agent_id: ID del agente a invalidar.
            tenant_id: ID del tenant al que pertenece el agente.
        """
        if not self.redis:
            logger.warning("No se puede invalidar la caché de agente: cliente Redis no disponible.")
            return

        global_cache_key = f"agent_config:{tenant_id}:{agent_id}"
        session_key_pattern = f"agent_config:{tenant_id}:{agent_id}:*"

        try:
            # Eliminar la caché global
            deleted_global = await self.redis.delete(global_cache_key)
            if deleted_global > 0:
                logger.info(f"Caché global para el agente {agent_id} (tenant: {tenant_id}) invalidada.")

            # Buscar y eliminar cachés de sesión
            session_keys = await self.redis.keys(session_key_pattern)
            if session_keys:
                deleted_sessions = await self.redis.delete(*session_keys)
                if deleted_sessions > 0:
                    logger.info(f"{deleted_sessions} cachés de sesión para el agente {agent_id} (tenant: {tenant_id}) invalidadas.")
            
        except Exception as e:
            logger.error(f"Error al invalidar la caché para el agente {agent_id}: {str(e)}")
    
    async def get_conversation_history(
        self,
        session_id: str,
        tenant_id: str,
        limit: int = 10,
        is_new_conversation: bool = False,
        tenant_tier: str = "free"
    ) -> List[Dict[str, Any]]:
        """
        Obtiene historial de conversación con soporte de caché.
        
        Args:
            session_id: ID de la sesión
            tenant_id: ID del tenant
            limit: Número máximo de mensajes
            is_new_conversation: Indica si es una conversación nueva (primer mensaje)
            
        Returns:
            Lista de mensajes del historial
        """
        # Si no hay Redis disponible, pasar directamente al servicio
        # Obtener configuraciones específicas del tier
        tier_config = self.settings.tier_limits.get(tenant_tier, self.settings.tier_limits["free"])
        
        # Determinar límites según tier
        cache_ttl = tier_config.get("conversation_cache_ttl", self.conversation_history_cache_ttl)
        cache_limit = tier_config.get("conversation_cache_limit", self.default_history_limit)
        
        # Asegurar que el límite solicitado no exceda el límite del tier
        effective_limit = min(limit, cache_limit)
        
        logger.debug(f"Obteniendo historial para tier {tenant_tier}: "
                   f"TTL={cache_ttl}s, limit={effective_limit} (tier max: {cache_limit})")
        
        if not self.redis:
            return await self._fetch_conversation_history_from_service(session_id, tenant_id, effective_limit)

        # Clave de caché para este historial específico
        cache_key = f"conversation_history:{tenant_id}:{session_id}"

        # Optimización para conversaciones nuevas
        if is_new_conversation:
            await self.redis.setex(cache_key, cache_ttl, json.dumps([]))
            return []

        # Intenta obtener de caché primero
        cached_history = await self.redis.get(cache_key)
        if cached_history:
            try:
                history = json.loads(cached_history)
                return history[:effective_limit]  # Limitar al número solicitado o máximo del tier
            except json.JSONDecodeError as e:
                # Si hay error en el formato de caché, ignorar y continuar con llamada al servicio
                logger.warning(f"Error decodificando caché de conversación: {str(e)}")

        # Si no hay caché o hay error, obtener del servicio
        history = await self._fetch_conversation_history_from_service(session_id, tenant_id, effective_limit, tenant_tier)
        return history
    
    async def _fetch_conversation_history_from_service(self, session_id: str, tenant_id: str, limit: int, tenant_tier: str = "free") -> List[Dict[str, Any]]:
        """Obtiene historial directamente del servicio de conversación y lo guarda en caché."""
        try:
            # Obtener configuraciones específicas del tier
            tier_config = self.settings.tier_limits.get(tenant_tier, self.settings.tier_limits["free"])
            cache_ttl = tier_config.get("conversation_cache_ttl", self.conversation_history_cache_ttl)
            
            # Obtener desde servicio de conversación
            history = await self.conversation_client.get_conversation_history(
                tenant_id=tenant_id,
                session_id=session_id,
                limit=limit
            )
            
            # Actualizar caché si es posible, usando TTL según tier
            if self.redis and history is not None:
                try:
                    cache_key = f"conversation_history:{tenant_id}:{session_id}"
                    await self.redis.setex(
                        cache_key, 
                        cache_ttl,  # Usar TTL según tier
                        json.dumps(history)
                    )
                    logger.debug(f"Caché de historial actualizado para sesión {session_id} (tier {tenant_tier}, TTL={cache_ttl}s)")
                except Exception as e:
                    logger.warning(f"Error actualizando caché tras consulta al servicio: {str(e)}")
            
            return history or []
            
        except Exception as e:
            logger.error(f"Error obteniendo historial de conversación: {str(e)}")
            return []  # Retornar lista vacía en caso de error
            
    async def save_conversation_message(
        self,
        session_id: str,
        tenant_id: str,
        role: str,
        content: str,
        message_type: str = "text",
        metadata: Optional[Dict[str, Any]] = None,
        processing_time: Optional[float] = None,
        wait_for_persistence: Optional[bool] = None,
        tenant_tier: str = "free"
    ) -> bool:
        """
        Guarda un mensaje en la conversación con soporte de caché local.
        
        El mensaje se añade a la caché local inmediatamente y se envía al
        servicio de conversación para persistencia de forma asíncrona.
        
        Args:
            session_id: ID de la sesión
            tenant_id: ID del tenant
            role: Rol del mensaje (user/assistant/system)
            content: Contenido del mensaje
            message_type: Tipo de mensaje
            metadata: Metadatos adicionales
            processing_time: Tiempo de procesamiento
            wait_for_persistence: Si es True, espera confirmación de guardado en BD
            
        Returns:
            bool: True si se guardó exitosamente en caché (y en BD si wait_for_persistence=True)
        """
        # Preparar mensaje con timestamp actual
        timestamp = datetime.datetime.now().isoformat()
        message = {
            "role": role,
            "content": content,
            "message_type": message_type,
            "metadata": metadata or {},
            "created_at": timestamp,
            "session_id": session_id,
            "tenant_id": tenant_id,
        }
        
        # Obtener configuraciones específicas del tier
        tier_config = self.settings.tier_limits.get(tenant_tier, self.settings.tier_limits["free"])
        
        # Determinar límites según tier
        cache_ttl = tier_config.get("conversation_cache_ttl", self.conversation_history_cache_ttl)
        cache_limit = tier_config.get("conversation_cache_limit", self.default_history_limit)
        
        # Si wait_for_persistence no se especificó, usar configuración del tier
        if wait_for_persistence is None:
            wait_for_persistence = tier_config.get("wait_for_persistence", False)
        
        logger.debug(f"Usando configuración de tier {tenant_tier}: "
                   f"TTL={cache_ttl}s, limit={cache_limit}, wait={wait_for_persistence}")
        
        # Si tenemos Redis disponible, actualizamos la caché local primero
        cache_updated = False
        if self.redis:
            try:
                cache_key = f"conversation_history:{tenant_id}:{session_id}"
                
                # Intentar obtener historial existente
                cached_history = await self.redis.get(cache_key)
                history = []
                
                if cached_history:
                    try:
                        history = json.loads(cached_history)
                    except json.JSONDecodeError:
                        # Si la caché está corrupta, inicializar con lista vacía
                        history = []
                
                # Añadir nuevo mensaje al inicio (los mensajes más recientes van primero)
                history.insert(0, message)
                
                # Limitar historial en caché según tier para evitar uso excesivo de memoria
                if len(history) > cache_limit:
                    history = history[:cache_limit]
                
                # Actualizar caché con el nuevo historial usando TTL según tier
                await self.redis.setex(
                    cache_key,
                    cache_ttl,
                    json.dumps(history)
                )
                cache_updated = True
                logger.debug(f"Mensaje añadido a caché local para sesión {session_id} (tier {tenant_tier})")
                
            except Exception as e:
                logger.warning(f"Error actualizando caché de conversación: {str(e)}")
        
        # Enviar mensaje al servicio para persistencia
        # Si wait_for_persistence=True, esperar confirmación
        # Si no, enviar de forma asíncrona y continuar
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
                
            # Si la caché se actualizó o no estamos esperando confirmación, considerar éxito
            return cache_updated or not wait_for_persistence
            
        except Exception as e:
            logger.error(f"Error enviando mensaje al servicio de conversación: {str(e)}")
            # Si la caché se actualizó, considerar éxito parcial
            return cache_updated
    
    async def invalidate_conversation_cache(self, session_id: str, tenant_id: str, tenant_tier: str = "free") -> bool:
        """
        Invalida el cache de historial de conversación para una sesión específica.
        
        Args:
            session_id: ID de sesión
            tenant_id: ID de tenant
            tenant_tier: Nivel de servicio del tenant
            
        Returns:
            bool: True si la operación fue exitosa, False en caso contrario
        """
        if not self.redis:
            return False
            
        try:
            cache_key = f"conversation_history:{tenant_id}:{session_id}"
            deleted = await self.redis.delete(cache_key)
            
            if deleted:
                logger.debug(f"Caché de conversación para sesión {session_id} invalidado (tier {tenant_tier})")
                return True
            else:
                logger.debug(f"No se encontró caché para sesión {session_id} para invalidar (tier {tenant_tier})")
                return False
                
        except Exception as e:
            logger.warning(f"Error al invalidar caché de conversación para tier {tenant_tier}: {str(e)}")
            return False
    
    async def handle_session_closed(self, session_id: str, tenant_id: str, tenant_tier: str = "free") -> bool:
        """
        Este método ha sido deshabilitado intencionalmente.
        Se mantiene la firma para compatibilidad con el código existente.
        
        Args:
            session_id: ID de sesión cerrada (no utilizado)
            tenant_id: ID del tenant (no utilizado)
            tenant_tier: Nivel de servicio del tenant (no utilizado)
            
        Returns:
            bool: Siempre devuelve True para evitar errores en código que lo llama
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
    
    async def invalidate_agent_cache(self, agent_id: str, tenant_id: str, session_id: Optional[str] = None):
        """Invalida cache de configuración de agente.
        
        Args:
            agent_id: ID del agente
            tenant_id: ID del tenant
            session_id: ID de la sesión (opcional). Si se proporciona, sólo se invalida la caché
                       específica de esa sesión. Si no, se invalida la caché global y todas las
                       cachés de sesión para este agente.
        """
        if not self.redis:
            return
            
        # Clave de caché global
        global_cache_key = f"agent_config:{tenant_id}:{agent_id}"
        
        if session_id:
            # Invalidar sólo la caché de esta sesión específica
            session_cache_key = f"agent_config:{tenant_id}:{agent_id}:{session_id}"
            await self.redis.delete(session_cache_key)
            logger.info(f"Cache por sesión invalidado para agente {agent_id}, tenant {tenant_id}, sesión {session_id}")
        else:
            # Invalidar caché global
            await self.redis.delete(global_cache_key)
            logger.info(f"Cache global invalidado para agente {agent_id}, tenant {tenant_id}")
            
            # Invalidar todas las cachés por sesión para este agente usando SCAN
            # El patrón de búsqueda incluye todos los keys que tengan el formato agent_config:{tenant_id}:{agent_id}:*
            pattern = f"agent_config:{tenant_id}:{agent_id}:*"
            cursor = '0'
            deleted_count = 0
            
            # Usar SCAN para buscar todas las claves que coincidan con el patrón
            while True:
                cursor, keys = await self.redis.scan(cursor=cursor, match=pattern, count=100)
                if keys:
                    deleted_count += len(keys)
                    for key in keys:
                        await self.redis.delete(key)
                # Si cursor es 0, hemos completado el escaneo
                if cursor == '0' or cursor == 0:
                    break
            
            if deleted_count > 0:
                logger.info(f"Invalidadas {deleted_count} cachés por sesión para agente {agent_id}, tenant {tenant_id}")
    
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