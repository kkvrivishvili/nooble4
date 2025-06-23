"""Rutas (endpoints) del Agent Management Service.

Expone los routers para los diferentes recursos del servicio.
"""

from agent_management_service.routes.agents import router as agents_router
from agent_management_service.routes.templates import router as templates_router
from agent_management_service.routes.health import router as health_router

__all__ = ['agents_router', 'templates_router', 'health_router']
