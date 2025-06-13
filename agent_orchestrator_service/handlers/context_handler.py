"""
Context Handler - Manejo y validación de contextos de ejecución desde headers.

Este módulo se encarga de:
- Extraer contexto desde headers HTTP
- Validar permisos y acceso
- Crear ExecutionContext para encolado
- Cache de validaciones para performance
"""

import logging
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
import json

from fastapi import HTTPException, status
from common.models.execution_context import ExecutionContext, create_agent_context
from agent_orchestrator_service.config.settings import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class ContextHandler:
    """
    Manejador de contextos de ejecución.
    
    Responsable de crear y validar contextos desde headers HTTP
    sin necesidad de lookup completo en base de datos.
    """
    
    def __init__(self, redis_client=None, db_client=None):
        """
        Inicializa handler.
        
        Args:
            redis_client: Cliente Redis para cache de validaciones
            db_client: Cliente DB para validaciones de acceso (opcional)
        """
        self.redis = redis_client
        self.db = db_client
        
        # Cache de validaciones por 5 minutos
        self.validation_cache_ttl = 300
        
        # Tipos de contexto válidos
        self.valid_context_types = {"agent", "workflow", "collection"}
    
    async def create_context_from_headers(
        self,
        tenant_id: str,
        agent_id: str,
        context_type: str = "agent",
        session_id: Optional[str] = None,
        user_id: Optional[str] = None,
        conversation_id: Optional[str] = None,
        collection_id: Optional[str] = None,
        workflow_id: Optional[str] = None,
        **extra_metadata
    ) -> ExecutionContext:
        """
        Crea ExecutionContext desde headers HTTP validados.
        
        Args:
            tenant_id: ID del tenant
            agent_id: ID del agente
            context_type: Tipo de contexto (agent, workflow, collection)
            session_id: ID de sesión para WebSocket
            user_id: ID del usuario (opcional)
            conversation_id: ID de conversación (opcional)
            collection_id: ID de collection específica (opcional)
            workflow_id: ID de workflow (futuro)
            **extra_metadata: Metadatos adicionales
            
        Returns:
            ExecutionContext listo para usar
            
        Raises:
            HTTPException: Si validación falla
        """
        # Validar campos requeridos
        await self._validate_required_fields(tenant_id, agent_id, context_type)
        
        # Validar acceso (con cache)
        await self._validate_access(tenant_id, agent_id, user_id)
        
        # Determinar context_id según tipo
        if context_type == "agent":
            context_id = f"agent-{agent_id}"
            agents = [agent_id]
            collections = [collection_id] if collection_id else []
        elif context_type == "workflow":
            context_id = f"workflow-{workflow_id or agent_id}"
            agents = [agent_id]  # TODO: Expandir cuando se implementen workflows
            collections = [collection_id] if collection_id else []
        elif context_type == "collection":
            context_id = f"collection-{collection_id or agent_id}"
            agents = [agent_id]
            collections = [collection_id] if collection_id else []
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Tipo de contexto inválido: {context_type}"
            )
        
        # Crear metadatos
        metadata = {
            "session_id": session_id,
            "user_id": user_id,
            "conversation_id": conversation_id,
            "created_from": "headers",
            "created_at": datetime.utcnow().isoformat(),
            **extra_metadata
        }
        
        # Crear contexto
        context = ExecutionContext(
            context_id=context_id,
            context_type=context_type,
            tenant_id=tenant_id,
            primary_agent_id=agent_id,
            agents=agents,
            collections=collections,
            metadata=metadata
        )
        
        logger.info(f"Contexto creado: {context_id} para tenant {tenant_id}")
        return context
    
    async def _validate_required_fields(
        self,
        tenant_id: str,
        agent_id: str,
        context_type: str
    ):
        """Valida campos requeridos."""
        
        # Validar que no estén vacíos
        if not tenant_id or not agent_id or not context_type:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Headers requeridos: X-Tenant-ID, X-Agent-ID, X-Context-Type"
            )
        
        # Validar context_type
        if context_type not in self.valid_context_types:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Context type inválido: {context_type}. Válidos: {self.valid_context_types}"
            )
        
        # Validar formato de IDs (básico)
        if len(tenant_id) < 3 or len(agent_id) < 3:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="IDs deben tener al menos 3 caracteres"
            )
    
    async def _validate_access(
        self,
        tenant_id: str,
        agent_id: str,
        user_id: Optional[str] = None
    ):
        """
        Valida que el tenant tiene acceso al agente.
        
        Usa cache en Redis para evitar DB lookups repetitivos.
        """
        # Cache key para validación
        cache_key = f"access_validation:{tenant_id}:{agent_id}"
        
        # Verificar cache primero
        if self.redis:
            cached_result = await self.redis.get(cache_key)
            if cached_result:
                if cached_result == "valid":
                    return  # Acceso válido cacheado
                elif cached_result == "invalid":
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=f"Tenant {tenant_id} no tiene acceso a agent {agent_id}"
                    )
        
        # Si no hay cache, validar acceso
        try:
            is_valid = await self._check_database_access(tenant_id, agent_id, user_id)
            
            # Cachear resultado
            if self.redis:
                cache_value = "valid" if is_valid else "invalid"
                await self.redis.setex(cache_key, self.validation_cache_ttl, cache_value)
            
            if not is_valid:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Tenant {tenant_id} no tiene acceso a agent {agent_id}"
                )
                
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error validando acceso: {str(e)}")
            # En caso de error de DB, permitir por seguridad (temporal)
            # TODO: En producción, considerar fallar cerrado
            logger.warning(f"Permitiendo acceso por error de validación: {tenant_id}:{agent_id}")
    
    async def _check_database_access(
        self,
        tenant_id: str,
        agent_id: str,
        user_id: Optional[str] = None
    ) -> bool:
        """
        Verifica acceso en base de datos.
        
        TODO: Implementar lookup real cuando esté disponible.
        """
        if not self.db:
            # Sin DB configurada, asumir válido (desarrollo)
            logger.warning("Sin DB configurada para validación de acceso")
            return True
        
        try:
            # TODO: Implementar llamada real a DB
            # agent_info = await self.db.agents.get_basic_info(agent_id)
            # return agent_info and agent_info.tenant_id == tenant_id
            
            # Simulación temporal
            logger.info(f"Validando acceso DB: tenant={tenant_id}, agent={agent_id}, user={user_id}")
            return True  # TODO: Reemplazar con lógica real
            
        except Exception as e:
            logger.error(f"Error en lookup de DB: {str(e)}")
            return False
    
    async def invalidate_cache(self, tenant_id: str, agent_id: str):
        """Invalida cache de validación."""
        if self.redis:
            cache_key = f"access_validation:{tenant_id}:{agent_id}"
            await self.redis.delete(cache_key)
    
    async def get_cache_stats(self) -> Dict[str, Any]:
        """Obtiene estadísticas del cache de validaciones."""
        if not self.redis:
            return {"cache": "disabled"}
        
        # Contar keys de validación
        validation_keys = await self.redis.keys("access_validation:*")
        
        return {
            "cache": "enabled",
            "validation_entries": len(validation_keys),
            "ttl_seconds": self.validation_cache_ttl
        }


# Factory function para uso en dependencias de FastAPI
async def get_context_handler(redis_client=None, db_client=None) -> ContextHandler:
    """Factory para obtener ContextHandler configurado."""
    return ContextHandler(redis_client, db_client)