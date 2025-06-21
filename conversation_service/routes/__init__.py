"""
Rutas para Conversation Service.
"""

from .crm_routes import router as crm_router
from .health import router as health_router

__all__ = [
    "crm_router",
    "health_router",
]
