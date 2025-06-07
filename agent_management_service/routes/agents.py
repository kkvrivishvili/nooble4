"""
Rutas para gestión de agentes.
INTEGRADO: Con sistema de headers de tenant y tier.
"""

import logging
from typing import Dict, List, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Header, Query, Path
from fastapi.responses import JSONResponse

from agent_management_service.config.settings import get_settings
from agent_management_service.models.agent_model import (
    Agent, CreateAgentRequest, UpdateAgentRequest, 
    AgentResponse, AgentListResponse
)
from agent_management_service.services.agent_service import AgentService
from common.redis_pool import get_redis_client

settings = get_settings()
logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/agents",
    tags=["agents"]
)

async def get_agent_service():
    """Dependency para obtener AgentService."""
    redis_client = await get_redis_client()
    return AgentService(redis_client)

@router.post("/", response_model=AgentResponse)
async def create_agent(
    request: CreateAgentRequest,
    tenant_id: str = Header(..., alias="X-Tenant-ID"),
    tenant_tier: str = Header(..., alias="X-Tenant-Tier"),
    agent_service: AgentService = Depends(get_agent_service)
):
    """Crea un nuevo agente."""
    try:
        agent = await agent_service.create_agent(tenant_id, tenant_tier, request)
        return AgentResponse(
            success=True,
            message="Agente creado exitosamente",
            agent=agent
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error creando agente: {str(e)}")
        raise HTTPException(status_code=500, detail="Error interno del servidor")

@router.get("/{agent_id}", response_model=AgentResponse)
async def get_agent(
    agent_id: str = Path(...),
    tenant_id: str = Header(..., alias="X-Tenant-ID"),
    agent_service: AgentService = Depends(get_agent_service)
):
    """Obtiene un agente por ID."""
    agent = await agent_service.get_agent(agent_id, tenant_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agente no encontrado")
    
    return AgentResponse(
        success=True,
        message="Agente encontrado",
        agent=agent
    )

@router.put("/{agent_id}", response_model=AgentResponse)
async def update_agent(
    agent_id: str,
    request: UpdateAgentRequest,
    tenant_id: str = Header(..., alias="X-Tenant-ID"),
    tenant_tier: str = Header(..., alias="X-Tenant-Tier"),
    agent_service: AgentService = Depends(get_agent_service)
):
    """Actualiza un agente existente."""
    try:
        agent = await agent_service.update_agent(agent_id, tenant_id, tenant_tier, request)
        if not agent:
            raise HTTPException(status_code=404, detail="Agente no encontrado")
        
        return AgentResponse(
            success=True,
            message="Agente actualizado exitosamente",
            agent=agent
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error actualizando agente: {str(e)}")
        raise HTTPException(status_code=500, detail="Error interno del servidor")

@router.delete("/{agent_id}")
async def delete_agent(
    agent_id: str,
    tenant_id: str = Header(..., alias="X-Tenant-ID"),
    agent_service: AgentService = Depends(get_agent_service)
):
    """Elimina un agente."""
    success = await agent_service.delete_agent(agent_id, tenant_id)
    if not success:
        raise HTTPException(status_code=404, detail="Agente no encontrado")
    
    return {"success": True, "message": "Agente eliminado exitosamente"}

@router.get("/", response_model=AgentListResponse)
async def list_agents(
    tenant_id: str = Header(..., alias="X-Tenant-ID"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    agent_service: AgentService = Depends(get_agent_service)
):
    """Lista agentes del tenant."""
    agents = await agent_service.list_agents(tenant_id, page, page_size)
    
    return AgentListResponse(
        success=True,
        message="Lista de agentes",
        agents=agents,
        total=len(agents),  # TODO: Implementar count real
        page=page,
        page_size=page_size
    )

