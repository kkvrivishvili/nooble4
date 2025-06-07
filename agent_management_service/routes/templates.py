"""
Rutas para gestión de templates.
"""

import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Header, Query, Body

from agent_management_service.models.template_model import TemplateResponse, TemplateListResponse
from agent_management_service.models.agent_model import CreateAgentRequest, AgentResponse
from agent_management_service.services.template_service import TemplateService
from agent_management_service.services.agent_service import AgentService
from common.redis_pool import get_redis_client

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/templates",
    tags=["templates"]
)

async def get_template_service():
    """Dependency para obtener TemplateService."""
    return TemplateService()

async def get_agent_service():
    """Dependency para obtener AgentService."""
    redis_client = await get_redis_client()
    return AgentService(redis_client)

@router.get("/", response_model=TemplateListResponse)
async def list_templates(
    tenant_id: str = Header(..., alias="X-Tenant-ID"),
    tenant_tier: str = Header(..., alias="X-Tenant-Tier"),
    category: Optional[str] = Query(None),
    template_service: TemplateService = Depends(get_template_service)
):
    """Lista templates disponibles."""
    templates = await template_service.list_templates(tenant_id, tenant_tier, category)
    
    return TemplateListResponse(
        success=True,
        message="Lista de templates",
        templates=templates
    )

@router.get("/{template_id}", response_model=TemplateResponse)
async def get_template(
    template_id: str,
    tenant_id: str = Header(..., alias="X-Tenant-ID"),
    template_service: TemplateService = Depends(get_template_service)
):
    """Obtiene un template específico."""
    template = await template_service.get_template(template_id, tenant_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template no encontrado")
    
    return TemplateResponse(
        success=True,
        message="Template encontrado",
        template=template
    )

@router.post("/from-template", response_model=AgentResponse)
async def create_agent_from_template(
    request: dict = Body(...),
    tenant_id: str = Header(..., alias="X-Tenant-ID"),
    tenant_tier: str = Header(..., alias="X-Tenant-Tier"),
    template_service: TemplateService = Depends(get_template_service),
    agent_service: AgentService = Depends(get_agent_service)
):
    """Crea agente desde template."""
    try:
        template_id = request.get("template_id")
        name = request.get("name")
        customizations = request.get("customizations", {})
        
        if not template_id or not name:
            raise HTTPException(status_code=400, detail="template_id y name son requeridos")
        
        # Generar configuración desde template
        config = await template_service.create_agent_from_template(
            template_id, tenant_id, tenant_tier, name, customizations
        )
        
        # Crear request para agente
        agent_request = CreateAgentRequest(**config)
        
        # Crear agente
        agent = await agent_service.create_agent(tenant_id, tenant_tier, agent_request)
        
        return AgentResponse(
            success=True,
            message="Agente creado desde template exitosamente",
            agent=agent
        )
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error creando agente desde template: {str(e)}")
        raise HTTPException(status_code=500, detail="Error interno del servidor")
