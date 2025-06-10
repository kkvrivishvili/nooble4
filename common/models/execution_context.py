"""
Execution Context - Modelo unificado para identificar contextos de ejecución.

Este módulo define el contexto de ejecución que puede ser:
- Un agente individual
- Un workflow multi-agente
- Una collection específica
- Otros tipos futuros
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from datetime import datetime
import json


@dataclass
class ExecutionContext:
    """
    Contexto de ejecución unificado para agentes, workflows y collections.
    
    Attributes:
        context_id: Identificador único del contexto (ej: "agent-123", "workflow-456")
        context_type: Tipo de contexto ("agent", "workflow", "collection")
        tenant_id: ID del tenant propietario
        tenant_tier: Tier del tenant (free, advance, professional, enterprise)
        primary_agent_id: ID del agente principal/inicial
        agents: Lista de todos los agentes involucrados
        collections: Lista de todas las collections utilizadas
        metadata: Metadatos específicos del contexto
        created_at: Timestamp de creación
    """
    
    context_id: str
    context_type: str  # "agent", "workflow", "collection"
    tenant_id: str
    tenant_tier: str   # "free", "advance", "professional", "enterprise"
    session_id: Optional[str] = None
    primary_agent_id: str
    agents: List[str]
    collections: List[str]
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
    
    def get_queue_name(self, domain: str) -> str:
        """
        Genera nombre de cola para este contexto.
        
        Args:
            domain: Dominio del servicio (execution, embedding, query, etc.)
            
        Returns:
            Nombre de cola en formato: {domain}:{context_id}:{tier}
        """
        return f"{domain}:{self.context_id}:{self.tenant_tier}"
    
    def get_callback_queue_name(self, target_domain: str) -> str:
        """
        Genera nombre de cola de callback para este contexto.
        
        Args:
            target_domain: Dominio que recibirá el callback
            
        Returns:
            Nombre de cola de callback
        """
        return f"{target_domain}:{self.tenant_id}:callbacks"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convierte a diccionario serializable."""
        return {
            "context_id": self.context_id,
            "context_type": self.context_type,
            "tenant_id": self.tenant_id,
            "tenant_tier": self.tenant_tier,
            "primary_agent_id": self.primary_agent_id,
            "agents": self.agents,
            "collections": self.collections,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ExecutionContext':
        """Crea instancia desde diccionario."""
        data = data.copy()
        if isinstance(data.get("created_at"), str):
            data["created_at"] = datetime.fromisoformat(data["created_at"])
        return cls(**data)
    
    def to_json(self) -> str:
        """Serializa a JSON."""
        return json.dumps(self.to_dict())
    
    @classmethod
    def from_json(cls, json_str: str) -> 'ExecutionContext':
        """Deserializa desde JSON."""
        return cls.from_dict(json.loads(json_str))


class ExecutionContextResolver:
    """
    Resuelve contextos de ejecución desde URLs públicas.
    
    Mapea URLs como usuario.nooble.ai/agente-ventas a ExecutionContext
    """
    
    def __init__(self, db_client=None):
        """
        Inicializa resolver.
        
        Args:
            db_client: Cliente de base de datos para lookups
        """
        self.db_client = db_client
    
    async def resolve_from_url(self, subdomain: str, path: str) -> ExecutionContext:
        """
        Resuelve contexto desde URL pública.
        
        Args:
            subdomain: Subdominio (ej: "usuario" de usuario.nooble.ai)
            path: Path (ej: "agente-ventas" o "workflow-onboarding")
            
        Returns:
            ExecutionContext correspondiente
            
        Raises:
            ValueError: Si no se puede resolver el contexto
        """
        # Determinar tipo desde path
        if path.startswith('agente-') or path.startswith('agent-'):
            return await self._resolve_agent_context(subdomain, path)
        elif path.startswith('workflow-'):
            return await self._resolve_workflow_context(subdomain, path)
        elif path.startswith('kb-') or path.startswith('collection-'):
            return await self._resolve_collection_context(subdomain, path)
        else:
            # Fallback: asumir que es un agente
            return await self._resolve_agent_context(subdomain, path)
    
    async def _resolve_agent_context(self, subdomain: str, agent_slug: str) -> ExecutionContext:
        """
        Resuelve contexto para agente individual.
        
        TODO: Implementar lookup real en base de datos
        Por ahora simula la respuesta esperada.
        """
        # TODO: Reemplazar con llamada real a base de datos
        # agent_info = await self.db_client.agents.get_by_slug_and_subdomain(agent_slug, subdomain)
        
        # Simulación temporal
        agent_info = {
            "id": f"agent-{hash(agent_slug) % 10000}",
            "tenant_id": f"tenant-{hash(subdomain) % 1000}",
            "tenant_tier": "professional",  # TODO: Obtener tier real
            "collection_id": f"collection-{hash(agent_slug) % 100}",
            "config": {"model": "llama3-8b-8192"}
        }
        
        return ExecutionContext(
            context_id=f"agent-{agent_info['id']}",
            context_type="agent",
            tenant_id=agent_info["tenant_id"],
            tenant_tier=agent_info["tenant_tier"],
            primary_agent_id=agent_info["id"],
            agents=[agent_info["id"]],
            collections=[agent_info["collection_id"]],
            metadata={
                "agent_slug": agent_slug,
                "subdomain": subdomain,
                "agent_config": agent_info["config"]
            }
        )
    
    async def _resolve_workflow_context(self, subdomain: str, workflow_slug: str) -> ExecutionContext:
        """
        Resuelve contexto para workflow multi-agente.
        
        TODO: Implementar cuando se desarrollen workflows
        """
        # TODO: Implementar lookup de workflows
        raise NotImplementedError("Workflow resolution será implementado en versión futura")
    
    async def _resolve_collection_context(self, subdomain: str, collection_slug: str) -> ExecutionContext:
        """
        Resuelve contexto para collection específica.
        
        TODO: Implementar si se necesita acceso directo a collections
        """
        # TODO: Implementar lookup de collections
        raise NotImplementedError("Collection resolution será implementado si es necesario")


# Factory functions para casos comunes
def create_agent_context(
    agent_id: str,
    tenant_id: str, 
    tenant_tier: str,
    collection_id: str,
    metadata: Dict[str, Any] = None
) -> ExecutionContext:
    """Factory para crear contexto de agente."""
    return ExecutionContext(
        context_id=f"agent-{agent_id}",
        context_type="agent",
        tenant_id=tenant_id,
        tenant_tier=tenant_tier,
        primary_agent_id=agent_id,
        agents=[agent_id],
        collections=[collection_id] if collection_id else [],
        metadata=metadata or {}
    )


def create_workflow_context(
    workflow_id: str,
    tenant_id: str,
    tenant_tier: str,
    agent_ids: List[str],
    collection_ids: List[str],
    entry_agent_id: str,
    metadata: Dict[str, Any] = None
) -> ExecutionContext:
    """Factory para crear contexto de workflow."""
    return ExecutionContext(
        context_id=f"workflow-{workflow_id}",
        context_type="workflow",
        tenant_id=tenant_id,
        tenant_tier=tenant_tier,
        primary_agent_id=entry_agent_id,
        agents=agent_ids,
        collections=collection_ids,
        metadata=metadata or {}
    )