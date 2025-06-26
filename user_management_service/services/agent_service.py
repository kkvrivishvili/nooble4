"""
Servicio principal para gestión de agentes.
INTEGRADO: Con validación de collections y cache con Redis.
"""

import logging
import json
from typing import Dict, List, Any, Optional
from datetime import datetime

from agent_management_service.config.settings import get_settings
from agent_management_service.models.agent_model import Agent, CreateAgentRequest, UpdateAgentRequest
from agent_management_service.services.validation_service import ValidationService
from agent_management_service.clients.ingestion_client import IngestionClient
from agent_management_service.clients.execution_client import ExecutionClient

settings = get_settings()
logger = logging.getLogger(__name__)

class AgentService:
    """Servicio principal para gestión de agentes."""
    
    def __init__(self, redis_client=None):
        """Inicializa el servicio."""
        self.redis = redis_client
        self.validation_service = ValidationService(redis_client)
        self.ingestion_client = IngestionClient(redis_client)
        self.execution_client = ExecutionClient(redis_client)
        
        # Cache TTL
        self.cache_ttl = settings.user_config_cache_ttl
    
    async def create_agent(
        self,
        tenant_id: str,
        request: CreateAgentRequest
    ) -> Agent:
        """Crea un nuevo agente."""
        logger.info(f"Creando agente {request.name} para tenant {tenant_id}")
        
        # Validar collections si están especificadas
        if request.collections:
            await self.validation_service.validate_collections(
                request.collections, tenant_id
            )
        
        # Crear agente
        agent = Agent(
            tenant_id=tenant_id,
            name=request.name,
            description=request.description,
            slug=request.slug,
            type=request.type,
            model=request.model or "llama3-8b-8192",
            temperature=request.temperature or 0.7,
            max_tokens=request.max_tokens or 2048,
            system_prompt=request.system_prompt,
            tools=request.tools,
            collections=request.collections,
            max_iterations=request.max_iterations or 5,
            max_history_messages=request.max_history_messages or 10,
            is_public=request.is_public,
            tags=request.tags,
            template_id=request.template_id,
            created_from_template=bool(request.template_id)
        )
        
        # TODO: Guardar en base de datos
        # Por ahora guardamos en Redis para el MVP
        await self._save_agent_to_cache(agent)
        
        logger.info(f"Agente {agent.name} creado exitosamente: {agent.id}")
        return agent
    
    async def get_agent(self, agent_id: str, tenant_id: str) -> Optional[Agent]:
        """Obtiene un agente por ID."""
        # Verificar cache primero
        cached_agent = await self._get_agent_from_cache(agent_id)
        if cached_agent and cached_agent.tenant_id == tenant_id:
            return cached_agent
        
        # TODO: Buscar en base de datos
        logger.warning(f"Agente {agent_id} no encontrado en cache")
        return None
    
    async def update_agent(
        self,
        agent_id: str,
        tenant_id: str,
        request: UpdateAgentRequest
    ) -> Optional[Agent]:
        """Actualiza un agente existente."""
        # Obtener agente actual
        agent = await self.get_agent(agent_id, tenant_id)
        if not agent:
            return None
        
        # Actualizar campos especificados
        update_data = request.dict(exclude_unset=True)
        
        # Validar nuevas collections si se especifican
        if 'collections' in update_data and update_data['collections']:
            await self.validation_service.validate_collections(
                update_data['collections'], tenant_id
            )
        
        # Aplicar actualizaciones
        for field, value in update_data.items():
            setattr(agent, field, value)
        
        agent.updated_at = datetime.utcnow()
        
        # Guardar cambios
        await self._save_agent_to_cache(agent)
        
        # Invalidar cache en Execution Service
        await self.execution_client.invalidate_agent_cache(agent_id, tenant_id)
        
        logger.info(f"Agente {agent_id} actualizado exitosamente")
        return agent
    
    async def update_agent_config(self, agent_id: str, tenant_id: str, update_data: Dict[str, Any]) -> Optional[Agent]:
        """Actualiza la configuración de un agente desde una acción de worker."""
        agent = await self.get_agent(agent_id, tenant_id)
        if not agent:
            return None

        # Validar nuevas collections si se especifican
        if 'collections' in update_data and update_data['collections']:
            await self.validation_service.validate_collections(
                update_data['collections'], tenant_id
            )

        # Aplicar actualizaciones
        update_request = UpdateAgentRequest(**update_data)
        for field, value in update_request.dict(exclude_unset=True).items():
            setattr(agent, field, value)

        agent.updated_at = datetime.utcnow()

        # Guardar cambios
        await self._save_agent_to_cache(agent)

        # Invalidar cache en Execution Service
        await self.execution_client.invalidate_agent_cache(agent_id, tenant_id)

        logger.info(f"Agente {agent_id} actualizado exitosamente desde worker")
        return agent

    async def delete_agent_config(self, agent_id: str, tenant_id: str) -> bool:
        """Elimina la configuración de un agente desde una acción de worker."""
        return await self.delete_agent(agent_id, tenant_id)

    async def delete_agent(self, agent_id: str, tenant_id: str) -> bool:
        """Elimina un agente (soft delete)."""
        agent = await self.get_agent(agent_id, tenant_id)
        if not agent:
            return False
        
        # Soft delete
        agent.deleted_at = datetime.utcnow()
        agent.is_active = False
        
        # Guardar cambios
        await self._save_agent_to_cache(agent)
        
        # Invalidar cache en Execution Service
        await self.execution_client.invalidate_agent_cache(agent_id, tenant_id)
        
        logger.info(f"Agente {agent_id} eliminado exitosamente")
        return True
    
    async def list_agents(
        self,
        tenant_id: str,
        page: int = 1,
        page_size: int = 20,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Agent]:
        """Lista agentes del tenant."""
        # TODO: Implementar con base de datos real
        # Por ahora retornamos lista vacía
        return []

    async def update_collection_status(
        self,
        collection_id: str,
        tenant_id: str,
        status: str,
        message: Optional[str] = None
    ):
        """
        Updates the status of a document collection based on ingestion notifications.
        
        This is a 'fire-and-forget' operation from the perspective of the caller.
        """
        logger.info(
            f"Updating status for collection {collection_id} of tenant {tenant_id} "
            f"to '{status}' with message: '{message}'"
        )
        
        # TODO: This should eventually update a persistent database record for the collection.
        # For now, we'll use Redis to store the status, simulating the update.
        if self.redis:
            collection_key = f"collection_status:{tenant_id}:{collection_id}"
            await self.redis.hset(
                collection_key,
                mapping={
                    "status": status,
                    "message": message or "",
                    "updated_at": datetime.utcnow().isoformat(),
                }
            )
            logger.info(f"Stored/Updated status for collection {collection_id} in Redis.")

        return
    
    async def increment_usage(self, agent_id: str, tenant_id: str):
        """Incrementa contador de uso del agente."""
        agent = await self.get_agent(agent_id, tenant_id)
        if agent:
            agent.usage_count += 1
            agent.last_used_at = datetime.utcnow()
            await self._save_agent_to_cache(agent)
    

    async def _save_agent_to_cache(self, agent: Agent):
        """Guarda agente en cache Redis."""
        if not self.redis:
            return
        
        cache_key = f"agent:{agent.tenant_id}:{agent.id}"
        await self.redis.setex(
            cache_key,
            self.cache_ttl,
            agent.json()
        )
    
    async def _get_agent_from_cache(self, agent_id: str) -> Optional[Agent]:
        """Obtiene agente desde cache Redis."""
        if not self.redis:
            return None
        
        # Buscar en todas las claves posibles (no tenemos tenant_id aquí)
        pattern = f"agent:*:{agent_id}"
        keys = await self.redis.keys(pattern)
        
        if keys:
            cached_data = await self.redis.get(keys[0])
            if cached_data:
                return Agent.parse_raw(cached_data)
        
        return None
